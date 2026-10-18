# Quant Lab Dashboard

This repo contains a **Streamlit** multi-page dashboard for a quantitative lab.

It currently includes:
- Data loading (CSV upload + built-in synthetic sample)
- Indicator explorer (SMA/EMA/RSI/MACD)
- Signal generation (SMA crossover example)
- Backtesting (vectorized equity curve + metrics)
- Basic parameter optimization (grid search)
- Simple reporting (download metrics / trades)

## Quick start

1. Create a virtualenv (optional but recommended)
2. Install deps:

```bash
pip install -r requirements.txt
```

3. Run:

```bash
streamlit run app.py
```

## Where to extend

- Backend logic: `src/`
- UI pages: `pages/`

