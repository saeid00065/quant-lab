# Task

Simulate the trades below on `data.csv` and report the account result. Do the calculation yourself; the rules are complete.

## Data
- `data.csv`: 10 daily bars of a US stock (NYSE sessions). Prices are trade prices, not adjusted. The `date` column is the session date; there is no intraday data.
- 2024-01-15 is missing on purpose: it is a market holiday (MLK Day).

## Rules
- Account: 10,000 USD cash, no other positions. Long only, no leverage, no interest.
- Signals are decided at the **close** of a bar and filled at the **open of the next bar**.
- Buy signals at the close of 2024-01-04 and 2024-01-12. Sell (exit) signal at the close of 2024-01-10.
- Every order is exactly **50 shares**, market order.
- Slippage: 0.05% of the open price against you (buy fill = open × 1.0005, sell fill = open × 0.9995).
- Fee: 0.1% of the fill notional (qty × fill price), paid in cash on every fill.
- At the end of the data, a position still open is **not** closed: mark it at the last close.

## Answer format
Write `answer.json` in this folder:

```json
{
  "trades": [
    {"side": "buy", "fill_date": "YYYY-MM-DD", "fill_price": 0.0, "qty": 50, "fee": 0.0}
  ],
  "realized_pnl": 0.0,
  "open_position": {"qty": 0, "entry_price": 0.0, "mark_price": 0.0},
  "final_cash": 0.0,
  "final_equity": 0.0,
  "notes": "..."
}
```

`trades` lists every fill in time order. `realized_pnl` covers closed trades only and includes their fees. `final_equity` = final cash + open position value at the mark price.
