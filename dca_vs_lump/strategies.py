# Lump sum vs DCA on month-end prices.
#
# Money goes in at the close of a month; month 0 is the start date. DCA buys
# in `months` tranches at months 0..months-1, the cash waiting on the side
# earns `cash_rate` a year. Both get valued at month `horizon`.

from dataclasses import dataclass

import numpy as np
import pandas as pd

MONTHS_PER_YEAR = 12
# one-month DCA vs lump sum comes out ~1e-14 apart from float noise, that's a tie
TIE_TOLERANCE = 1e-9


def monthly_rate(annual_rate: float) -> float:
    return float((1 + annual_rate) ** (1 / MONTHS_PER_YEAR) - 1)


def _check(prices, months, horizon):
    if months < 1:
        raise ValueError("DCA needs at least one month")
    if horizon < months:
        raise ValueError("The horizon must be at least as long as the DCA period")
    if len(prices) <= horizon:
        raise ValueError(f"Need {horizon + 1} monthly prices, got {len(prices)}")


def simulate(prices: pd.Series, amount: float, months: int, horizon: int, cash_rate: float = 0.0) -> pd.DataFrame:
    """Month-by-month value of both strategies starting at prices.index[0]."""
    _check(prices, months, horizon)
    path = prices.iloc[: horizon + 1].to_numpy(dtype=float)
    grow = 1 + monthly_rate(cash_rate)

    cash = np.zeros(len(path))
    shares = np.zeros(len(path))
    balance, held = float(amount), 0.0
    for t, px in enumerate(path):
        if t > 0:
            balance *= grow
        if t < months:
            # tranche = amount / months
            # ^ ignored the interest earned while waiting, so DCA ended with
            # leftover cash. Splitting what's left over the tranches left
            # invests the interest too and lands on exactly 0 at the end.
            tranche = balance / (months - t)
            held += tranche / px
            balance -= tranche
        cash[t], shares[t] = balance, held

    invested = shares * path
    return pd.DataFrame(
        {
            "lump_sum": amount * path / path[0],
            "dca": invested + cash,
            "dca_invested": invested,
            "dca_cash": cash,
        },
        index=prices.index[: horizon + 1],
    )


def rolling_windows(prices, amount, months, horizon, cash_rate=0.0):
    """One row per possible start month: final value of each strategy and the gap."""
    prices = prices.dropna()  # months before the fund existed
    _check(prices, months, horizon)

    rows = []
    for i in range(len(prices) - horizon):
        last = simulate(prices.iloc[i:], amount, months, horizon, cash_rate).iloc[-1]
        rows.append((prices.index[i], last["lump_sum"], last["dca"]))

    out = pd.DataFrame(rows, columns=["start", "lump_sum", "dca"]).set_index("start")
    out["lump_sum_return"] = 100 * (out["lump_sum"] / amount - 1)
    out["dca_return"] = 100 * (out["dca"] / amount - 1)
    # +5 means lump sum ended with 5% more money than DCA
    out["lump_vs_dca"] = 100 * (out["lump_sum"] / out["dca"] - 1)
    return out


@dataclass
class Summary:
    windows: int
    first_start: pd.Timestamp
    last_start: pd.Timestamp
    lump_win_rate: float  # %
    mean_difference: float
    median_difference: float
    lump_worst_return: float
    dca_worst_return: float
    lump_worst_start: pd.Timestamp
    dca_worst_start: pd.Timestamp


def summarize(windows: pd.DataFrame) -> Summary:
    if windows.empty:
        raise ValueError("No windows to summarize")
    diff = windows["lump_vs_dca"]
    return Summary(
        windows=len(windows),
        first_start=windows.index[0],
        last_start=windows.index[-1],
        lump_win_rate=float(100 * (diff > TIE_TOLERANCE).mean()),
        mean_difference=float(diff.mean()),
        median_difference=float(diff.median()),
        lump_worst_return=float(windows["lump_sum_return"].min()),
        dca_worst_return=float(windows["dca_return"].min()),
        lump_worst_start=windows.index[int(windows["lump_sum_return"].argmin())],
        dca_worst_start=windows.index[int(windows["dca_return"].argmin())],
    )
