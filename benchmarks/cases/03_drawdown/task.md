# Task

`equity.csv` is the daily end-of-day equity curve of an account (USD, no deposits or withdrawals). Report its drawdown statistics.

## Definitions
- Drawdown at day t = equity_t / max(equity up to and including t) − 1.
- Max drawdown = the most negative drawdown (a negative number, e.g. −0.10 for −10%).
- Peak date = the date of the running maximum just before the max drawdown; trough date = the date of the max drawdown.
- Recovery date = the first date after the trough on which equity is ≥ the peak equity (null if never).
- Total return = last equity / first equity − 1.

## Answer format
Write `answer.json` in this folder:

```json
{
  "max_drawdown": 0.0,
  "peak_date": "YYYY-MM-DD",
  "trough_date": "YYYY-MM-DD",
  "recovery_date": "YYYY-MM-DD",
  "total_return": 0.0,
  "notes": "..."
}
```
