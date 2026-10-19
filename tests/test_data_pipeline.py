"""Data pipeline tests. Expected values are written by hand, not computed by the code under test."""
from __future__ import annotations

import lzma
import struct
from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.data_loader import resample_bars
from src.data_quality import (
    check_calendar, check_integrity, check_outliers, check_values, scheduled_open, trading_day,
)
from src.modules.dukascopy import DayFile, combine_bid_ask, decode_candles

UTC = "UTC"


def _bi5(records):
    return lzma.compress(b"".join(struct.pack(">5if", *r) for r in records), format=lzma.FORMAT_ALONE)


# ---------- decoder ----------

def test_url_month_is_zero_based():
    assert DayFile("XAUUSD", "BID", date(2025, 1, 2)).url.endswith("/XAUUSD/2025/00/02/BID_candles_min_1.bi5")
    assert DayFile("XAUUSD", "ASK", date(2026, 12, 31)).url.endswith("/2026/11/31/ASK_candles_min_1.bi5")


def test_decode_field_order_and_scale():
    # record order in file: time, open, close, low, high, volume
    payload = _bi5([(0, 2623655, 2622828, 2622448, 2623905, 0.5), (60, 2622828, 2624000, 2622800, 2624100, 0.25)])
    df = decode_candles(payload, date(2025, 1, 2), 1000)
    assert list(df["date"]) == [pd.Timestamp("2025-01-02 00:00", tz=UTC), pd.Timestamp("2025-01-02 00:01", tz=UTC)]
    assert df.loc[0, ["open", "high", "low", "close"]].tolist() == [2623.655, 2623.905, 2622.448, 2622.828]
    assert df.loc[1, "volume"] == 0.25


def test_decode_empty_payload():
    assert decode_candles(b"", date(2025, 1, 4), 1000).empty


def test_combine_bid_ask_spread_and_ticks():
    t = pd.to_datetime(["2025-01-02 10:00", "2025-01-02 10:01"]).tz_localize(UTC)
    bid = pd.DataFrame({"date": t, "open": [10.0, 10.0], "high": [11.0, 10.0], "low": [9.0, 10.0], "close": [10.5, 10.0], "volume": [1.0, 0.0]})
    ask = bid.assign(open=[10.2, 10.2], high=[11.2, 10.2], low=[9.2, 10.2], close=[10.8, 10.2], volume=[2.0, 0.0])
    out = combine_bid_ask(bid, ask)
    assert out["spread_close"].round(9).tolist() == [0.3, 0.2]
    assert out["mid_close"].round(9).tolist() == [10.65, 10.1]
    assert out["has_ticks"].tolist() == [True, False]


# ---------- calendar ----------

@pytest.mark.parametrize("ts,expected", [
    ("2025-01-08 21:59", True),   # Wed 16:59 NY (winter, UTC-5)
    ("2025-01-08 22:00", False),  # Wed 17:00 NY daily break
    ("2025-01-08 23:00", True),   # Wed 18:00 NY reopen
    ("2025-07-09 21:00", False),  # Wed 17:00 NY in summer (UTC-4)
    ("2025-07-09 20:59", True),
    ("2025-01-10 22:00", False),  # Fri 17:00 NY weekend
    ("2025-01-11 12:00", False),  # Saturday
    ("2025-01-12 22:59", False),  # Sun 17:59 NY
    ("2025-01-12 23:00", True),   # Sun 18:00 NY open
])
def test_scheduled_open(ts, expected):
    s = pd.Series([pd.Timestamp(ts, tz=UTC)])
    assert bool(scheduled_open(s).iat[0]) is expected


def test_trading_day_rolls_at_17_ny():
    s = pd.Series(pd.to_datetime(["2025-01-08 22:59", "2025-01-08 23:00"]).tz_localize(UTC))
    # 22:59 UTC = 17:59 NY (break, still Wed); 23:00 UTC = 18:00 NY -> Thursday's session
    assert [str(d) for d in trading_day(s)] == ["2025-01-08", "2025-01-09"]


# ---------- integrity / values ----------

def _frame(times, close, has_ticks=None):
    t = pd.to_datetime(times).tz_localize(UTC)
    c = np.asarray(close, dtype=float)
    d = {"date": t}
    for side, off in (("bid", 0.0), ("ask", 0.2)):
        d |= {f"{side}_open": c + off, f"{side}_high": c + off + 1, f"{side}_low": c + off - 1, f"{side}_close": c + off,
              f"{side}_volume": np.ones(len(c))}
    df = pd.DataFrame(d)
    for f in ("open", "high", "low", "close"):
        df[f"mid_{f}"] = (df[f"bid_{f}"] + df[f"ask_{f}"]) / 2
    df["spread_close"] = df["ask_close"] - df["bid_close"]
    df["has_ticks"] = True if has_ticks is None else has_ticks
    return df


def test_integrity_counts_duplicates_and_missing_minutes():
    df = _frame(["2025-01-08 10:00", "2025-01-08 10:01", "2025-01-08 10:01", "2025-01-08 10:05"], [1, 2, 2, 3])
    r = check_integrity(df)
    assert r["duplicate_timestamps"] == 1
    assert r["missing_grid_minutes"] == 3  # 10:02, 10:03, 10:04
    assert r["non_positive_steps"] == 1    # the duplicate
    assert r["monotonic_increasing"] is True


def test_values_flags_bad_ohlc_and_crossed_quotes():
    df = _frame(["2025-01-08 10:00", "2025-01-08 10:01", "2025-01-08 10:02"], [100, 100, 100])
    df.loc[1, "bid_high"] = 98.0           # high below low (99) and below open/close
    df.loc[2, "ask_close"] = 99.5          # ask below bid close (100)
    df.loc[0, "bid_volume"] = -1.0
    r = check_values(df)
    assert r["by_side"]["bid"]["high_below_low"] == 1
    assert r["by_side"]["bid"]["open_outside_range"] == 1
    assert r["by_side"]["bid"]["volume_negative"] == 1
    assert r["crossed_close"] == 1
    assert r["by_side"]["ask"]["nan"] == 0


# ---------- gaps ----------

def test_calendar_separates_break_from_unexpected_gap():
    # Wed 2025-01-08 winter: break 22:00-23:00 UTC. 20 minutes 15:00-15:19 UTC have no ticks.
    t = pd.date_range("2025-01-08 14:00", "2025-01-08 23:59", freq="1min")
    ticks = np.ones(len(t), dtype=bool)
    ticks[(t >= "2025-01-08 15:00") & (t < "2025-01-08 15:20")] = False
    ticks[(t >= "2025-01-08 16:00") & (t < "2025-01-08 16:02")] = False   # short quiet run (2 min)
    ticks[(t >= "2025-01-08 22:00") & (t < "2025-01-08 23:00")] = False   # scheduled break
    df = _frame(t, np.full(len(t), 100.0), has_ticks=ticks)
    r = check_calendar(df, min_gap_minutes=5, holiday_coverage=0.0)
    assert r["unexpected_gaps_count"] == 1
    assert r["unexpected_gaps_top"][0] == {"start": "2025-01-08T15:00:00+00:00", "minutes": 20}
    assert r["quiet_minutes_short"] == 2
    assert r["scheduled_closed_minutes"] == 60
    assert r["ticks_in_scheduled_closure"] == 0


def test_outlier_flags_single_jump():
    t = pd.date_range("2025-01-08 10:00", periods=400, freq="1min")
    rng = np.random.default_rng(0)
    close = 2000 * np.exp(np.cumsum(rng.normal(0, 1e-4, len(t))))
    close[300:] *= 1.02  # +2% jump at bar 300 (~200 sigma)
    r = check_outliers(_frame(t, close), k=12, window=200)
    assert r["flagged"] == 1
    assert r["top"][0]["date"] == t[300].tz_localize(UTC).isoformat()


# ---------- resampling / look-ahead ----------

def test_resample_5min_values_and_availability():
    t = pd.date_range("2025-01-08 10:00", periods=10, freq="1min")
    close = np.arange(10, dtype=float) + 100   # 100..109
    df = _frame(t, close)
    out = resample_bars(df, "5min")
    assert len(out) == 2
    first = out.iloc[0]
    assert first["date"] == pd.Timestamp("2025-01-08 10:00", tz=UTC)
    assert first["available_at"] == pd.Timestamp("2025-01-08 10:05", tz=UTC)
    assert first["bid_open"] == 100 and first["bid_close"] == 104
    assert first["bid_high"] == 105 and first["bid_low"] == 99
    assert first["minutes"] == 5


def test_resample_skips_filler_bars():
    t = pd.date_range("2025-01-08 10:00", periods=5, freq="1min")
    df = _frame(t, [100, 101, 999, 103, 104], has_ticks=[True, True, False, True, True])
    out = resample_bars(df, "5min")
    assert out.iloc[0]["bid_high"] == 105  # 999 filler excluded
    assert out.iloc[0]["minutes"] == 4


def test_resample_no_lookahead_truncation():
    """Bars that finished before a cut-off must not change when later data is removed or altered."""
    t = pd.date_range("2025-01-08 10:00", periods=600, freq="1min")
    rng = np.random.default_rng(1)
    df = _frame(t, 2000 + np.cumsum(rng.normal(0, 1, len(t))))
    for rule in ("5min", "15min", "1h"):
        full = resample_bars(df, rule)
        for cut in (97, 250, 431):
            cut_ts = df["date"].iat[cut]
            altered = df.copy()
            altered.loc[cut:, [c for c in df if c.endswith(("open", "high", "low", "close"))]] *= 1.5
            part = resample_bars(altered, rule)
            done_full = full[full["available_at"] <= cut_ts].reset_index(drop=True)
            done_part = part[part["available_at"] <= cut_ts].reset_index(drop=True)
            pd.testing.assert_frame_equal(done_full, done_part)
            assert len(done_full) > 0


def test_resample_daily_uses_trading_day():
    # Wed 22:30 UTC is in the break, Wed 23:10 UTC belongs to Thursday's trading day.
    t = pd.to_datetime(["2025-01-08 21:00", "2025-01-08 23:10", "2025-01-09 10:00"])
    df = _frame(t, [100, 200, 300])
    out = resample_bars(df, "1D")
    assert [str(d) for d in out["trading_day"]] == ["2025-01-08", "2025-01-09"]
    assert out["bid_open"].tolist() == [100, 200]
    assert out["bid_close"].tolist() == [100, 300]
    assert out.iloc[1]["available_at"] == pd.Timestamp("2025-01-09 10:01", tz=UTC)


# ---------- end to end (synthetic raw files in Dukascopy format; technical test only) ----------

def test_get_data_build_end_to_end(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("get_data", "scripts/get_data.py")
    gd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gd)

    raw = tmp_path / "raw"
    # Wed 2025-01-08 has ticks 10:00-10:09 UTC, the rest are filler; Sat 2025-01-11 is an empty file.
    for side, off in (("BID", 0), ("ASK", 250)):  # ask = bid + $0.25
        recs = []
        for m in range(1440):
            p = 2650000 + (m - 600) * 10 if 600 <= m < 610 else 2650000
            v = 1.0 if 600 <= m < 610 else 0.0
            recs.append((m * 60, p + off, p + off, p + off - 50, p + off + 50, v))
        for d, payload in ((date(2025, 1, 8), _bi5(recs)), (date(2025, 1, 11), b"")):
            f = DayFile("XAUUSD", side, d).path(raw)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(payload)

    rep = gd.build("XAUUSD", date(2025, 1, 8), date(2025, 1, 11), csv=True, raw=raw,
                   proc=tmp_path / "proc", qc_dir=tmp_path / "qc", dashboard=None)

    one = pd.read_parquet(tmp_path / "proc/XAUUSD_1m.parquet")
    assert len(one) == 1440 and one["date"].is_monotonic_increasing and one["date"].is_unique
    assert int(one["has_ticks"].sum()) == 10
    assert np.allclose(one["spread_close"], 0.25)
    assert rep["files"]["BID"] == {"files": 4, "ok": 1, "empty": 1, "missing": 2,
                                   "missing_or_empty_weekdays": ["2025-01-09", "2025-01-10"]}
    csv = pd.read_csv(tmp_path / "proc/csv/XAUUSD_1m_2025.csv")
    assert len(csv) == 10
    assert csv.iloc[0]["date"] == "2025-01-08 10:00:00"
    assert csv.iloc[0]["bid_close"] == 2650.0 and csv.iloc[0]["ask_close"] == 2650.25
    m5 = pd.read_parquet(tmp_path / "proc/XAUUSD_5m.parquet")
    assert len(m5) == 2 and m5["minutes"].tolist() == [5, 5]
