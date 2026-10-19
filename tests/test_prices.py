from datetime import date

import pandas as pd
import pytest

from dca_vs_lump.prices import load_prices, parse_stooq_csv, save_prices, to_monthly

STOOQ_CSV = """Date,Open,High,Low,Close,Volume
2024-01-30,100,101,99,100.5,1000
2024-01-31,100,102,99,101.0,1000
2024-02-29,101,103,100,102.0,1000
2024-03-01,102,104,101,103.0,1000
"""


def daily(values, start):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_to_monthly():
    prices = daily(range(1, 61), "2024-01-01")  # Jan 1 .. Mar 22 on business days
    monthly = to_monthly(prices, today=date(2024, 6, 1))
    assert list(monthly.index.strftime("%Y-%m-%d")) == ["2024-01-31", "2024-02-29", "2024-03-31"]
    assert monthly.iloc[0] == 23  # Jan 2024 has 23 business days


def test_to_monthly_drops_current_month():
    prices = daily(range(1, 61), "2024-01-01")
    monthly = to_monthly(prices, today=date(2024, 3, 22))
    assert monthly.index[-1] == pd.Timestamp("2024-02-29")


def test_stooq_csv():
    close = parse_stooq_csv(STOOQ_CSV, "SPY")
    assert close.name == "SPY"
    assert close.loc["2024-02-29"] == 102.0
    assert len(close) == 4


def test_stooq_captcha_page():
    with pytest.raises(ValueError, match="did not return a CSV"):
        parse_stooq_csv("<!DOCTYPE html><html>verify you are human</html>", "SPY")


def test_csv_roundtrip(tmp_path):
    prices = pd.DataFrame(
        {"SPY": [1.5, 2.25], "GLD": [float("nan"), 3.0]},
        index=pd.to_datetime(["2024-01-31", "2024-02-29"]),
    )
    path = tmp_path / "prices.csv"
    save_prices(prices, path)
    loaded = load_prices(path)
    pd.testing.assert_frame_equal(loaded, prices, check_names=False, check_freq=False)
