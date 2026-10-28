# Pre-registered spec — GLD overnight vs day

Written 2026-10-29, **before** any GLD data was downloaded or any result was seen. Agreed with the user in chat.
Changes after this point must be logged in "Amendments" with the reason, and mark any test segment as no longer untouched.

## Hypothesis
Gold's return is earned mostly **overnight** (US close → next US open, i.e. Asian + London hours), not during the
US session. If true, "hold overnight only" beats "hold during the day only", and may beat buy-and-hold after costs.
Who is on the other side: US-hours sellers/hedgers vs. Asia/London buyers (physical demand, central banks).
Default assumption (Edge rules): **there is no edge** until the tests below say otherwise.

## Universe and data
- Instrument: **GLD** (SPDR Gold Shares, NYSE Arca), USD. Source: Yahoo Finance via `yfinance`,
  `auto_adjust=False` raw Open/Close (GLD pays no dividends, has never split; expense ratio is inside the price).
- Bar: daily. `Open` = first price of the regular session (09:30 ET), `Close` = regular-session close (16:00 ET).
  Price type: trade prices (no bid/ask available) — spread is modelled as a cost.
- Period: 2005-01-03 → 2026-10-28 (last complete session at download).
- Raw file kept unchanged; SHA-256 recorded. QC: sorted unique dates, no NaN/inf, low <= open/close <= high,
  gaps vs. the NYSE calendar, extreme moves listed (not removed).

## Rules (no parameters to fit)
For day t with previous session close C[t-1], open O[t], close C[t]:
- **Night**: buy at C[t-1] (market-on-close), sell at O[t] (market-on-open). Return n_t = O[t]/C[t-1] - 1.
- **Day**: buy at O[t], sell at C[t]. Return d_t = C[t]/O[t] - 1.
- **Buy & hold**: hold continuously; (1+n_t)(1+d_t) = C[t]/C[t-1] (accounting identity, checked).
- Sizing: 100% of equity, long only, no leverage, no shorting, cash earns 0 (no interest modelled). No taxes.
- Each Night/Day trade = 2 fills. Equity per trade: (1-c)(1+r)(1-c), c = cost per fill.
- Weekend/holiday nights are included in the following session's night (Friday close → Monday open).

## Costs
Commission $0. Spread + slippage **c = 1 bp per fill** (base). Stress: **2 bp** (double) and **5 bp**. Also 0 bp to show the raw effect.
Buy & hold pays 1 fill at the start only.

## Time split (locked)
| Segment | Dates | Use |
|---|---|---|
| Research | 2005-01-03 → 2016-12-30 | Look at everything |
| Validation | 2017-01-03 → 2021-12-31 | Check the same fixed rules |
| Final test | 2022-01-03 → 2026-10-28 | Used **once**, after everything above is written down |

## Mandatory tests and thresholds (set before seeing results)
1. **Sample size**: >= 500 trades per segment for Night and Day (each trades every session).
2. **Null**: (a) buy & hold; (b) random rule — each session hold either night or day at random, 1,000 seeds
   (numpy `SeedSequence(20261029).spawn(1000)`); Night must beat the 95th percentile of the random rule.
3. **Significance**: mean night return > mean day return, HAC (Newey-West, 5 lags) t-stat > 2 on the research segment.
4. **Cost stress**: Night must still beat buy & hold (CAGR) at 2 bp/fill; report 5 bp.
5. **Stability**: per-year results; Night must beat Day in >= 60% of years. Weekday breakdown (Monday night includes the weekend).
6. **Out of sample**: Night > Day (cumulative, after 1 bp) in validation **and** final test.

Decision per Edge rules: reject / revise / paper trade / limited live test. Any failed or unrun test caps the decision at "revise".

## Amendments
(none)

## Results recorded BEFORE opening the final test (2026-10-29)
Command: `py -3 research/gld_overnight/analyze.py` → `out/results_research_validation.json`.
Data: `data/raw/yahoo/GLD_1d_2005-01-03_2026-10-28.csv`, SHA-256 `1df588a477e4e5e4ee930b35240442a113a077826f28efb1b1e246a3b51d48bc`,
downloaded 2026-10-29 with yfinance 1.7.0. QC (`out/qc.json`): 5,490 sessions (5,489 daily returns), sorted/unique, no NaN, no OHLC violations, no splits/dividends; 2 calendar gaps are real
NYSE closures (2007-01-02 Ford funeral, 2012-10-29/30 Sandy); 38 open==prev-close days spread over all years with
normal ranges/volume → treated as genuine $0.01-tick ties, nothing changed. Research segment starts 2005-01-04
(the first session has no previous close).

| Test | Threshold | Research 2005–16 | Validation 2017–21 | Status |
|---|---|---|---|---|
| Sample size | >= 500 trades/segment | ~3,000 | ~1,260 | pass |
| Null: random night/day (1 bp) | > 95th pct | 95.6th | 95.7th | pass (barely) |
| Null: buy & hold (1 bp, CAGR) | night > hold | 3.28% vs 8.12% | 4.82% vs 9.30% | **fail** |
| Significance night − day | HAC t > 2 | t = 1.68 | t = 1.83 | **fail** |
| Cost stress: night > hold at 2 bp | | −1.79% vs 8.11% | −0.33% vs 9.30% | **fail** |
| Stability: years night > day | >= 60% | 12/17 years (2005–2021) | | pass |
| Out of sample: night > day (1 bp) | | | 4.82% vs −5.72% | pass |

Raw effect (0 bp): night CAGR 8.62% / 10.24% vs day −0.46% / −0.85% vs hold 8.12% / 9.30% — essentially all of
GLD's return came overnight. The tradeable version fails: two fills a day at 1 bp each cost ~5% a year.

## Final test (opened once, 2026-10-29, after the section above was written; rules unchanged)
Command: `py -3 research/gld_overnight/analyze.py --final` → `out/results_with_final.json`.
2022-01-03 → 2026-10-28, ~1,210 sessions.
- 0 bp: night CAGR 17.43% / day 0.21% / hold 17.68%. 1 bp: night 11.65% / day −4.71% / hold 17.67%. 2 bp: night 6.16%. 5 bp: night −8.74%.
- night − day 6.47 bp/day, HAC t 2.18; random null: night at 97.3rd pct; years night > day 16/22 (2005–2026).
- Night beats day out of sample: pass. Night beats buy & hold after costs: **fail** (again).

## Decision: **reject** as a trading strategy
The *pattern* is real and stable: over 22 years and all three segments, essentially all of GLD's return arrived
overnight and the US day session earned ~0 before costs. But "hold only overnight" never beat simply holding GLD,
in any segment, at any realistic cost — it pays two fills a day to skip a part of the day that earns ~0 anyway,
and it also forgoes nothing worth skipping. Research-segment night−day significance (t = 1.68) missed the pre-set
threshold. Possible use (not tested here, would need its own spec): execution timing for a long-term holder —
add to positions at the close rather than the open. Historical results do not guarantee future performance.
