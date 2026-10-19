import pandas as pd
import pytest

from dca_vs_lump.strategies import monthly_rate, rolling_windows, simulate, summarize


def series(values, start="2020-01-31"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="ME"), dtype=float)


RISING = series([100, 110, 121, 133.1, 146.41])
FALLING = series([100, 50, 50, 50])
FLAT = series([100] * 6)


def test_rising_market_lump_wins():
    final = simulate(RISING, 1200, months=2, horizon=3).iloc[-1]
    assert final["lump_sum"] == pytest.approx(1200 * 1.331)
    # 600 at 100 -> 6 shares, 600 at 110 -> 5.4545 shares, valued at 133.1
    assert final["dca"] == pytest.approx((6 + 600 / 110) * 133.1)
    assert final["lump_sum"] > final["dca"]


def test_early_crash_dca_wins():
    final = simulate(FALLING, 1000, months=2, horizon=3).iloc[-1]
    assert final["lump_sum"] == pytest.approx(500.0)
    assert final["dca"] == pytest.approx(750.0)  # 5 shares + 10 shares at 50


def test_one_month_dca_equals_lump():
    path = simulate(RISING, 1000, months=1, horizon=4)
    assert path["dca"].to_list() == pytest.approx(path["lump_sum"].to_list())


def test_dca_cash_runs_out():
    path = simulate(FLAT, 900, months=3, horizon=5)
    assert path["dca_cash"].to_list() == pytest.approx([600, 300, 0, 0, 0, 0])
    assert path["dca_invested"].iloc[-1] == pytest.approx(900)


def test_cash_interest_gets_invested():
    rate = monthly_rate(0.12)
    path = simulate(FLAT, 1000, months=2, horizon=2, cash_rate=0.12)
    # 500 invested at once, the other 500 waits a month and grows
    assert path["dca"].iloc[-1] == pytest.approx(500 + 500 * (1 + rate))
    assert path["dca_cash"].iloc[-1] == 0


def test_monthly_rate():
    assert (1 + monthly_rate(0.05)) ** 12 == pytest.approx(1.05)
    assert monthly_rate(0.0) == 0


@pytest.mark.parametrize(
    ("months", "horizon", "message"),
    [(0, 3, "at least one month"), (4, 3, "at least as long"), (2, 10, "Need 11 monthly prices")],
)
def test_bad_periods(months, horizon, message):
    with pytest.raises(ValueError, match=message):
        simulate(RISING, 100, months=months, horizon=horizon)


def test_windows():
    windows = rolling_windows(RISING, 1000, months=2, horizon=2)
    assert list(windows.index) == list(RISING.index[:3])
    assert (windows["lump_vs_dca"] > 0).all()
    assert windows["lump_sum_return"].iloc[0] == pytest.approx(21.0)


def test_windows_skip_leading_nans():
    prices = pd.concat([series([float("nan")] * 2, start="2019-11-30"), RISING])
    windows = rolling_windows(prices, 1000, months=2, horizon=2)
    assert windows.index[0] == RISING.index[0]


def test_summary():
    prices = series([100, 50, 60, 100, 100])
    windows = rolling_windows(prices, 1000, months=2, horizon=2)
    # crash right after the first start -> DCA wins that one, lump sum the other two
    summary = summarize(windows)
    assert summary.windows == 3
    assert summary.lump_win_rate == pytest.approx(200 / 3)
    assert summary.lump_worst_return == pytest.approx(-40.0)
    assert summary.lump_worst_start == prices.index[0]
    assert summary.median_difference == pytest.approx(windows["lump_vs_dca"].median())


def test_summary_empty():
    empty = rolling_windows(RISING, 1000, 1, 1).iloc[0:0]
    with pytest.raises(ValueError, match="No windows"):
        summarize(empty)


def test_tie_is_not_a_win():
    windows = rolling_windows(RISING, 1000, months=1, horizon=2)
    assert summarize(windows).lump_win_rate == 0
