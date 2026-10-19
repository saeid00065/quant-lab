# Task

`data.csv` is a daily OHLCV file for a US stock that trades on the NYSE (regular sessions only). Before it is used for any backtest, run a data-quality check and report every problem you find.

Notes:
- Prices are trade prices, not adjusted. `date` is the session date.
- 2024-02-19 was an NYSE holiday (Presidents' Day). Weekends are not sessions.
- **Do not modify `data.csv`.** If you want a cleaned copy, write it to a new file.

## Answer format
Write `answer.json` in this folder. Use `YYYY-MM-DD` dates; empty list if none.

```json
{
  "duplicate_dates": [],
  "ohlc_violations": [],
  "missing_values": [],
  "missing_sessions": [],
  "out_of_order": false,
  "notes": "..."
}
```

- `duplicate_dates`: dates that appear more than once.
- `ohlc_violations`: dates where the bar is impossible (not low <= open, close <= high, or low > high).
- `missing_values`: dates with an empty or non-numeric price field.
- `missing_sessions`: NYSE sessions in the file's date range that have no row.
- `out_of_order`: whether the rows are not sorted by date.
