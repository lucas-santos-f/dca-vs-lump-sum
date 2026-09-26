import pandas as pd
import pytest

from dca_vs_lump.strategies import monthly_rate, rolling_windows, simulate, summarize


def series(values, start="2020-01-31"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="ME"), dtype=float)


RISING = series([100, 110, 121, 133.1, 146.41])
FALLING = series([100, 50, 50, 50])
FLAT = series([100] * 6)


def test_lump_sum_beats_dca_in_a_rising_market():
    final = simulate(RISING, 1200, months=2, horizon=3).iloc[-1]
    assert final["lump_sum"] == pytest.approx(1200 * 1.331)
    # 600 at 100 -> 6 shares, 600 at 110 -> 5.4545 shares, valued at 133.1
    assert final["dca"] == pytest.approx((6 + 600 / 110) * 133.1)
    assert final["lump_sum"] > final["dca"]


def test_dca_beats_lump_sum_after_an_early_crash():
    final = simulate(FALLING, 1000, months=2, horizon=3).iloc[-1]
    assert final["lump_sum"] == pytest.approx(500.0)
    assert final["dca"] == pytest.approx(750.0)  # 5 shares + 10 shares at 50


def test_one_month_dca_is_the_same_as_lump_sum():
    path = simulate(RISING, 1000, months=1, horizon=4)
    assert path["dca"].to_list() == pytest.approx(path["lump_sum"].to_list())


def test_dca_is_fully_invested_after_the_last_tranche():
    path = simulate(FLAT, 900, months=3, horizon=5)
    assert path["dca_cash"].to_list() == pytest.approx([600, 300, 0, 0, 0, 0])
    assert path["dca_invested"].iloc[-1] == pytest.approx(900)


def test_cash_interest_is_invested_with_the_later_tranches():
    rate = monthly_rate(0.12)
    path = simulate(FLAT, 1000, months=2, horizon=2, cash_rate=0.12)
    # 500 invested at once, the other 500 waits a month and grows
    assert path["dca"].iloc[-1] == pytest.approx(500 + 500 * (1 + rate))
    assert path["dca_cash"].iloc[-1] == 0


def test_monthly_rate_compounds_back_to_the_annual_rate():
    assert (1 + monthly_rate(0.05)) ** 12 == pytest.approx(1.05)
    assert monthly_rate(0.0) == 0


def test_simulation_is_indexed_by_month_from_the_start_date():
    path = simulate(RISING, 100, months=2, horizon=3)
    assert list(path.index) == list(RISING.index[:4])


@pytest.mark.parametrize(
    ("months", "horizon", "message"),
    [(0, 3, "at least one month"), (4, 3, "at least as long"), (2, 10, "Need 11 monthly prices")],
)
def test_invalid_periods_are_rejected(months, horizon, message):
    with pytest.raises(ValueError, match=message):
        simulate(RISING, 100, months=months, horizon=horizon)


def test_rolling_windows_start_at_every_month_with_a_full_horizon():
    windows = rolling_windows(RISING, 1000, months=2, horizon=2)
    assert list(windows.index) == list(RISING.index[:3])
    assert (windows["lump_vs_dca"] > 0).all()
    assert windows["lump_sum_return"].iloc[0] == pytest.approx(21.0)


def test_rolling_windows_skip_months_before_the_fund_existed():
    prices = pd.concat([series([float("nan")] * 2, start="2019-11-30"), RISING])
    windows = rolling_windows(prices, 1000, months=2, horizon=2)
    assert windows.index[0] == RISING.index[0]


def test_summary_counts_wins_and_worst_cases():
    prices = series([100, 50, 60, 100, 100])
    windows = rolling_windows(prices, 1000, months=2, horizon=2)
    # DCA wins the window starting at 100 (the crash), lump sum wins the two after it
    summary = summarize(windows)
    assert summary.windows == 3
    assert summary.lump_win_rate == pytest.approx(200 / 3)
    assert summary.lump_worst_return == pytest.approx(-40.0)
    assert summary.lump_worst_start == prices.index[0]
    assert summary.median_difference == pytest.approx(windows["lump_vs_dca"].median())


def test_summary_of_no_windows_is_an_error():
    empty = rolling_windows(RISING, 1000, 1, 1).iloc[0:0]
    with pytest.raises(ValueError, match="No windows"):
        summarize(empty)


def test_a_tie_does_not_count_as_a_lump_sum_win():
    windows = rolling_windows(RISING, 1000, months=1, horizon=2)
    assert summarize(windows).lump_win_rate == 0
