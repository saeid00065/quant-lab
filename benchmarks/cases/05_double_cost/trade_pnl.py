"""PnL of one EURUSD round trip, account currency USD."""

UNITS = 100_000          # 1 standard lot
SPREAD = 0.0002          # 2 pips, quoted ask - bid

# Quotes at the moments of the fills (bid, ask)
ENTRY_BID, ENTRY_ASK = 1.1000, 1.1002
EXIT_BID, EXIT_ASK = 1.1050, 1.1052


def round_trip_pnl() -> float:
    entry_fill = ENTRY_ASK          # a buy is filled at the ask
    exit_fill = EXIT_BID            # a sell is filled at the bid
    gross = UNITS * (exit_fill - entry_fill)
    spread_cost = UNITS * SPREAD * 2
    return gross - spread_cost


if __name__ == "__main__":
    print(f"PnL: {round_trip_pnl():.2f} USD")
