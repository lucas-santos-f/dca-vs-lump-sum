# dca-vs-lump-sum

You have a chunk of money to invest. Put it all in now, or spread it over the next N months? This backtests both on real ETF prices for every start month since 1993 and shows how often each one won.

![screenshot](docs/screenshot.png)

Short answer for SPY, $100k, 12-month DCA, compared after 10 years: lump sum came out ahead in 77% of the 284 windows, by 4.2% on average. DCA wins when the market drops right after you start (May 2008 start: DCA +28.5%). Earning 4% on the waiting cash narrows it but lump sum still wins ~70% of the time.

## Run

```
pip install -r requirements.txt
streamlit run app.py
```

No keys needed, monthly prices are in `data/monthly_prices.csv`. To refresh: `python scripts/update_prices.py` (Yahoo Finance, falls back to Stooq).

## How it's computed

Month-end closes. Lump sum buys everything at month 0. DCA buys at months 0..N-1, each tranche is `cash left / tranches left`, so whatever interest the waiting cash earned gets invested too. Both valued at the horizon. The rolling view repeats that for every start month that has enough history after it.

Taxes, fees and spreads are ignored (they'd favor lump sum slightly, one trade vs N).

## Gotchas

- Stooq prices aren't dividend-adjusted. If a ticker falls back to Stooq the script says so; SPY would look ~1.5%/yr worse.
- When Stooq serves its captcha page, download the CSV by hand and use `--file SPY path/to/spy_us_d.csv`.
- The current month is dropped on purpose so the newest window isn't a partial month.

Tests: `pip install -r requirements-dev.txt && pytest`

Not investment advice.
