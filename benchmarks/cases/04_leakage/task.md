# Task

`strategy.py` is a strategy candidate that someone wants to backtest. The signal for bar t is decided at the close of bar t and traded at the next bar's open.

Review the code for **look-ahead (future) leakage**: any value used for the bar-t signal that would not be known at the close of bar t. Do not fix the file; only review it.

## Answer format
Write `answer.json` in this folder:

```json
{
  "leak_found": true,
  "leak_lines": [0],
  "explanation": "..."
}
```

`leak_lines` = the line numbers in `strategy.py` where future information enters (the line that creates it, one number per leak).
