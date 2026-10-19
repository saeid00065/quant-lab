# Task

`trade_pnl.py` computes the profit of one long EURUSD round trip (buy 100,000 units, then sell them). There is no commission and no swap/financing; the only cost is the bid/ask spread. Account currency is USD.

Check whether the costs are applied correctly. Do not edit the file.

## Answer format
Write `answer.json` in this folder:

```json
{
  "cost_bug_found": true,
  "bug_line": 0,
  "correct_pnl_usd": 0.0,
  "explanation": "..."
}
```

`bug_line` = the line number in `trade_pnl.py` of the wrong cost (0 if none). `correct_pnl_usd` = the correct PnL in USD.
