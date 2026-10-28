"""GLD overnight vs day — runs the tests pre-registered in SPEC.md on the raw Yahoo file.

Usage:
    py -3 research/gld_overnight/analyze.py            # research + validation only
    py -3 research/gld_overnight/analyze.py --final    # adds the final test segment (use once)
Outputs: research/gld_overnight/out/results_<stage>.json, yearly.csv, equity_<stage>.csv

Metric definitions (daily sessions, 252 per year):
    CAGR = final_equity ** (252 / sessions) - 1;  vol = std(daily) * sqrt(252);  Sharpe = mean/std * sqrt(252), rf = 0
    max drawdown = min(equity / running peak - 1);  win rate = share of trades with net return > 0
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = ROOT / "data" / "raw" / "yahoo" / "GLD_1d_2005-01-03_2026-10-28.csv"
OUT = HERE / "out"
SEGMENTS = {"research": ("2005-01-03", "2016-12-30"), "validation": ("2017-01-03", "2021-12-31"),
            "final": ("2022-01-03", "2026-10-28")}
COSTS_BP = [0.0, 1.0, 2.0, 5.0]
SEED, N_RANDOM = 20261029, 1000


def load() -> pd.DataFrame:
    df = pd.read_csv(RAW, parse_dates=["Date"]).rename(columns=str.lower)
    df["night"] = df["open"] / df["close"].shift(1) - 1   # buy prev close, sell open
    df["day"] = df["close"] / df["open"] - 1              # buy open, sell close
    df["hold"] = df["close"] / df["close"].shift(1) - 1
    df = df.iloc[1:].reset_index(drop=True)              # first row has no previous close
    gap = ((1 + df["night"]) * (1 + df["day"]) - (1 + df["hold"])).abs().max()
    assert gap < 1e-12, f"accounting identity broken: {gap}"
    return df


def equity(rets: np.ndarray, c: float, fills_per_trade: int) -> np.ndarray:
    return np.cumprod((1 - c) ** fills_per_trade * (1 + rets))


def stats(rets: np.ndarray, c: float, kind: str) -> dict:
    if kind == "hold":
        daily = (1 + rets).copy()
        daily[0] *= 1 - c                                  # one buy at the start
        eq, net = np.cumprod(daily), daily - 1
    else:
        net = (1 - c) ** 2 * (1 + rets) - 1
        eq = np.cumprod(1 + net)
    n = len(rets)
    sd = net.std(ddof=1)
    return {"sessions": n, "trades": n if kind != "hold" else 1, "total_return": eq[-1] - 1,
            "cagr": eq[-1] ** (252 / n) - 1, "vol": sd * math.sqrt(252),
            "sharpe": net.mean() / sd * math.sqrt(252) if sd > 0 else float("nan"),
            "max_drawdown": float((eq / np.maximum.accumulate(eq) - 1).min()),
            "win_rate": float((net > 0).mean()) if kind != "hold" else float("nan"),
            "mean_trade_bp": net.mean() * 1e4 if kind != "hold" else float("nan")}


def newey_west_t(x: np.ndarray, lags: int = 5) -> float:
    """t-stat of mean(x) with Newey-West (Bartlett) variance."""
    n, m = len(x), x.mean()
    e = x - m
    s = e @ e / n + 2 * sum((1 - L / (lags + 1)) * (e[L:] @ e[:-L] / n) for L in range(1, lags + 1))
    return float(m / math.sqrt(s / n))


def random_null(seg: pd.DataFrame, c: float) -> np.ndarray:
    """Each session hold night or day at random (same trade count and duration mix as the rules)."""
    n_, d_ = seg["night"].to_numpy(), seg["day"].to_numpy()
    finals = np.empty(N_RANDOM)
    for k, child in enumerate(np.random.SeedSequence(SEED).spawn(N_RANDOM)):
        pick = np.random.default_rng(child).random(len(seg)) < 0.5
        finals[k] = np.prod((1 - c) ** 2 * (1 + np.where(pick, n_, d_)))
    return finals


def analyse_segment(seg: pd.DataFrame) -> dict:
    res = {"dates": [str(seg["date"].iloc[0].date()), str(seg["date"].iloc[-1].date())], "by_cost": {}}
    for bp in COSTS_BP:
        c = bp / 1e4
        res["by_cost"][f"{bp:g}bp"] = {k: stats(seg[k].to_numpy(), c, k) for k in ("night", "day", "hold")}
    diff = (seg["night"] - seg["day"]).to_numpy()
    res["night_minus_day_mean_bp"] = diff.mean() * 1e4
    res["night_minus_day_hac_t"] = newey_west_t(diff)
    res["night_mean_hac_t"] = newey_west_t(seg["night"].to_numpy())
    res["day_mean_hac_t"] = newey_west_t(seg["day"].to_numpy())
    null = random_null(seg, 1e-4)
    night_final = res["by_cost"]["1bp"]["night"]["total_return"] + 1
    res["random_null_1bp"] = {"p95_final": float(np.percentile(null, 95)), "median_final": float(np.median(null)),
                              "night_final": night_final, "night_percentile": float((null < night_final).mean() * 100)}
    wd = seg.assign(wd=seg["date"].dt.day_name())
    res["night_mean_bp_by_weekday"] = (wd.groupby("wd")["night"].mean() * 1e4).round(2).to_dict()
    res["day_mean_bp_by_weekday"] = (wd.groupby("wd")["day"].mean() * 1e4).round(2).to_dict()
    return res


def yearly(df: pd.DataFrame, c: float = 1e-4) -> pd.DataFrame:
    g = df.groupby(df["date"].dt.year)
    return pd.DataFrame({
        "night": g["night"].apply(lambda r: np.prod((1 - c) ** 2 * (1 + r)) - 1),
        "day": g["day"].apply(lambda r: np.prod((1 - c) ** 2 * (1 + r)) - 1),
        "hold": g["hold"].apply(lambda r: np.prod(1 + r) - 1),
        "sessions": g.size()})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true", help="include the final test segment (use once)")
    args = ap.parse_args()
    df = load()
    names = ["research", "validation"] + (["final"] if args.final else [])
    stage = "with_final" if args.final else "research_validation"
    out = {"data_file": str(RAW.relative_to(ROOT)), "seed": SEED, "random_null_runs": N_RANDOM, "segments": {}}
    curves = []
    for name in names:
        a, b = SEGMENTS[name]
        seg = df[(df["date"] >= a) & (df["date"] <= b)].reset_index(drop=True)
        out["segments"][name] = analyse_segment(seg)
        for k in ("night", "day", "hold"):
            curves.append(pd.DataFrame({"date": seg["date"], "segment": name, "strategy": k,
                                        "equity_1bp": equity(seg[k].to_numpy(), 1e-4, 2 if k != "hold" else 0)}))
    last = SEGMENTS[names[-1]][1]
    yr = yearly(df[df["date"] <= last])
    out["years_night_beats_day"] = f"{int((yr['night'] > yr['day']).sum())}/{len(yr)}"
    OUT.mkdir(exist_ok=True)
    (OUT / f"results_{stage}.json").write_text(json.dumps(out, indent=1, default=float))
    yr.to_csv(OUT / f"yearly_{stage}.csv", float_format="%.6f")
    pd.concat(curves).to_csv(OUT / f"equity_{stage}.csv", index=False, float_format="%.6f")

    for name, r in out["segments"].items():
        print(f"\n=== {name} {r['dates'][0]} -> {r['dates'][1]}")
        for cost, s in r["by_cost"].items():
            print(f"  {cost:>4}: " + " | ".join(
                f"{k} CAGR {v['cagr']*100:6.2f}% DD {v['max_drawdown']*100:6.1f}% Sh {v['sharpe']:5.2f}" for k, v in s.items()))
        print(f"  night-day mean {r['night_minus_day_mean_bp']:.2f} bp/day, HAC t {r['night_minus_day_hac_t']:.2f}; "
              f"night t {r['night_mean_hac_t']:.2f}, day t {r['day_mean_hac_t']:.2f}")
        rn = r["random_null_1bp"]
        print(f"  random null (1bp): night final {rn['night_final']:.3f} vs null p95 {rn['p95_final']:.3f} "
              f"(night at {rn['night_percentile']:.1f} pct)")
        print(f"  night bp by weekday: {r['night_mean_bp_by_weekday']}")
    print(f"\nyears night beats day (1bp): {out['years_night_beats_day']}")


if __name__ == "__main__":
    main()
