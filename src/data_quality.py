"""Data quality checks for 1-minute bid/ask bars (AGENTS.md "Data validation").

Every check only *reports*; nothing here drops, fills, sorts or adjusts data.
Input frame columns: date (UTC, bar start), bid_/ask_/mid_ open/high/low/close,
bid_volume, ask_volume, spread_close, has_ticks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NY = "America/New_York"
LONDON = "Europe/London"

# Spot gold (Dukascopy/OTC) schedule in New York time: daily break 17:00-18:00 Mon-Thu,
# weekend from Fri 17:00 to Sun 18:00. Verified against the data by
# `ticks_in_scheduled_closure` (should be ~0).
BREAK_START_H, BREAK_END_H = 17, 18

# Sessions in local time (DST aware). Bars whose start falls in [start, end).
SESSIONS = {
    "asia": ("Asia/Tokyo", 9, 15),
    "london": (LONDON, 8, 17),
    "new_york": (NY, 8, 17),
}


def scheduled_open(ts: pd.Series) -> pd.Series:
    """True when the market is scheduled to be open at bar start `ts` (UTC)."""
    ny = ts.dt.tz_convert(NY)
    wd = ny.dt.weekday
    h = ny.dt.hour
    closed = (
        (wd == 5)
        | ((wd == 4) & (h >= BREAK_START_H))
        | ((wd == 6) & (h < BREAK_END_H))
        | (wd.between(0, 3) & (h >= BREAK_START_H) & (h < BREAK_END_H))
    )
    return ~closed


def trading_day(ts: pd.Series) -> pd.Series:
    """Trading day label: a session that opens 18:00 NY belongs to the next calendar day."""
    ny = ts.dt.tz_convert(NY)
    return (ny + pd.Timedelta(hours=24 - BREAK_END_H)).dt.date


def session_mask(ts: pd.Series, name: str) -> pd.Series:
    tz, start, end = SESSIONS[name]
    local = ts.dt.tz_convert(tz)
    return local.dt.weekday.lt(5) & local.dt.hour.ge(start) & local.dt.hour.lt(end)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """(start_idx, length) of consecutive True runs."""
    if not mask.any():
        return []
    m = np.concatenate([[False], mask, [False]]).astype(np.int8)
    d = np.diff(m)
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return list(zip(starts.tolist(), (ends - starts).tolist()))


def _q(s: pd.Series) -> dict:
    s = s.dropna()
    if s.empty:
        return {"n": 0}
    return {
        "n": int(len(s)), "mean": float(s.mean()), "median": float(s.median()),
        "p95": float(s.quantile(0.95)), "p99": float(s.quantile(0.99)),
        "min": float(s.min()), "max": float(s.max()),
    }


def check_integrity(df: pd.DataFrame, freq: str = "1min") -> dict:
    ts = df["date"]
    step = pd.Timedelta(freq)
    diffs = ts.diff().dropna()
    return {
        "rows": int(len(df)),
        "timezone": str(ts.dt.tz),
        "first": ts.min().isoformat() if len(ts) else None,
        "last": ts.max().isoformat() if len(ts) else None,
        "duplicate_timestamps": int(ts.duplicated().sum()),
        "monotonic_increasing": bool(ts.is_monotonic_increasing),
        "off_grid_timestamps": int((ts.dt.floor(freq) != ts).sum()),
        "non_positive_steps": int((diffs <= pd.Timedelta(0)).sum()),
        "missing_grid_minutes": int(((diffs // step) - 1).clip(lower=0).sum()),
    }


def check_values(df: pd.DataFrame) -> dict:
    out: dict = {"by_side": {}}
    for side in ("bid", "ask", "mid"):
        o, h, l, c = (df[f"{side}_{f}"] for f in ("open", "high", "low", "close"))
        num = df[[f"{side}_{f}" for f in ("open", "high", "low", "close")]]
        out["by_side"][side] = {
            "nan": int(num.isna().sum().sum()),
            "inf": int(np.isinf(num.to_numpy(dtype=float)).sum()),
            "non_positive": int((num <= 0).sum().sum()),
            "high_below_low": int((h < l).sum()),
            "open_outside_range": int(((o < l) | (o > h)).sum()),
            "close_outside_range": int(((c < l) | (c > h)).sum()),
        }
    for side in ("bid", "ask"):
        v = df[f"{side}_volume"]
        out["by_side"][side] |= {
            "volume_negative": int((v < 0).sum()),
            "volume_zero": int((v == 0).sum()),
        }
    out["crossed_close"] = int((df["ask_close"] < df["bid_close"]).sum())
    out["crossed_any"] = int(
        ((df["ask_low"] < df["bid_low"]) | (df["ask_high"] < df["bid_high"]) | (df["ask_open"] < df["bid_open"])).sum()
    )
    out["side_missing"] = {
        "bid_only": int((df["ask_close"].isna() & df["bid_close"].notna()).sum()),
        "ask_only": int((df["bid_close"].isna() & df["ask_close"].notna()).sum()),
    }
    return out


def check_calendar(df: pd.DataFrame, *, min_gap_minutes: int = 5, holiday_coverage: float = 0.5, top: int = 15) -> dict:
    """Classify no-tick minutes: scheduled closure, holiday/low-activity day, short quiet, unexpected gap."""
    d = df[["date", "has_ticks"]].copy()
    d["open"] = scheduled_open(d["date"]).to_numpy()
    d["tday"] = trading_day(d["date"]).to_numpy()

    per_day = d[d["open"]].groupby("tday").agg(open_min=("open", "size"), tick_min=("has_ticks", "sum"))
    per_day["coverage"] = per_day["tick_min"] / per_day["open_min"]
    low_days = per_day[per_day["coverage"] < holiday_coverage]
    low_set = set(low_days.index)

    in_low_day = d["tday"].isin(low_set).to_numpy()
    no_tick_open = (~d["has_ticks"].to_numpy()) & d["open"].to_numpy() & ~in_low_day
    gaps, quiet = [], 0
    for s, n in _runs(no_tick_open):
        if n >= min_gap_minutes:
            gaps.append({"start": d["date"].iat[s].isoformat(), "minutes": int(n)})
        else:
            quiet += n
    gaps.sort(key=lambda g: -g["minutes"])

    return {
        "schedule": "New York time: daily break 17:00-18:00 Mon-Thu, weekend Fri 17:00 -> Sun 18:00",
        "scheduled_open_minutes": int(d["open"].sum()),
        "scheduled_closed_minutes": int((~d["open"]).sum()),
        "ticks_in_scheduled_closure": int((d["has_ticks"] & ~d["open"]).sum()),
        "trading_days": int(len(per_day)),
        "low_activity_days": [
            {"day": str(k), "coverage": round(float(r.coverage), 3), "tick_minutes": int(r.tick_min)}
            for k, r in low_days.iterrows()
        ],
        "quiet_minutes_short": int(quiet),
        "unexpected_gaps_count": len(gaps),
        "unexpected_gap_minutes": int(sum(g["minutes"] for g in gaps)),
        "unexpected_gaps_top": gaps[:top],
        "coverage_open_hours": float(d.loc[d["open"] & ~in_low_day, "has_ticks"].mean()),
    }


def check_spread(df: pd.DataFrame) -> dict:
    t = df[df["has_ticks"]]
    out = {"all": _q(t["spread_close"])}
    for name in SESSIONS:
        out[name] = _q(t.loc[session_mask(t["date"], name), "spread_close"])
    by_year = t.groupby(t["date"].dt.year)["spread_close"].median()
    out["median_by_year"] = {int(k): float(v) for k, v in by_year.items()}
    return out


def check_outliers(df: pd.DataFrame, *, k: float = 12.0, window: int = 600, top: int = 15) -> dict:
    """Flag 1-minute mid log-returns larger than k robust sigmas (rolling median abs deviation).

    Returns are measured between consecutive bars WITH ticks, so weekend gaps are included
    and labelled; they are reported, not treated as errors.
    """
    t = df.loc[df["has_ticks"], ["date", "mid_close", "mid_high", "mid_low"]].reset_index(drop=True)
    r = np.log(t["mid_close"]).diff()
    mad = r.abs().rolling(window, min_periods=60).median().shift(1)
    z = r.abs() / (1.4826 * mad)
    gap_min = t["date"].diff().dt.total_seconds() / 60
    flagged = t.assign(ret=r, z=z, gap_minutes=gap_min)[z > k].sort_values("z", ascending=False)
    rng = np.log(t["mid_high"] / t["mid_low"])
    return {
        "threshold_sigma": k,
        "window_bars": window,
        "flagged": int(len(flagged)),
        "flagged_after_gap": int((flagged["gap_minutes"] > 1).sum()),
        "top": [
            {"date": row.date.isoformat(), "ret_pct": round(float(row.ret) * 100, 3), "z": round(float(row.z), 1),
             "gap_minutes": int(row.gap_minutes)}
            for row in flagged.head(top).itertuples()
        ],
        "largest_bar_range_pct": round(float(rng.max()) * 100, 3),
        "largest_bar_range_at": t["date"].iat[int(rng.idxmax())].isoformat() if len(t) else None,
    }


def monthly_table(df: pd.DataFrame) -> list[dict]:
    d = df[["date", "has_ticks", "spread_close", "mid_close", "bid_volume"]].copy()
    d["open"] = scheduled_open(d["date"])
    d["month"] = d["date"].dt.strftime("%Y-%m")
    d["london"] = session_mask(d["date"], "london")
    d["new_york"] = session_mask(d["date"], "new_york")
    rows = []
    for m, g in d.groupby("month"):
        o = g[g["open"]]
        t = g[g["has_ticks"]]
        rows.append({
            "month": m,
            "open_minutes": int(len(o)),
            "tick_minutes": int(o["has_ticks"].sum()),
            "coverage": round(float(o["has_ticks"].mean()), 4) if len(o) else None,
            "london_cov": round(float(o.loc[o["london"], "has_ticks"].mean()), 4) if o["london"].any() else None,
            "ny_cov": round(float(o.loc[o["new_york"], "has_ticks"].mean()), 4) if o["new_york"].any() else None,
            "spread_median": round(float(t["spread_close"].median()), 3) if len(t) else None,
            "close_last": round(float(t["mid_close"].iat[-1]), 2) if len(t) else None,
            "tick_volume": round(float(t["bid_volume"].sum()), 1),
        })
    return rows


def daily_closes(df: pd.DataFrame) -> list[list]:
    """[trading_day, mid close] for the price chart (one row per trading day with ticks)."""
    t = df.loc[df["has_ticks"], ["date", "mid_close"]]
    s = t.groupby(trading_day(t["date"]).to_numpy())["mid_close"].last()
    return [[str(k), round(float(v), 2)] for k, v in s.items()]


def run_all(df: pd.DataFrame) -> dict:
    return {
        "integrity": check_integrity(df),
        "values": check_values(df),
        "calendar": check_calendar(df),
        "spread": check_spread(df),
        "outliers": check_outliers(df),
        "monthly": monthly_table(df),
        "filler_bars": int((~df["has_ticks"]).sum()),
    }
