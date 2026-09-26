"""Lump sum vs dollar-cost averaging (DCA) on a monthly price series.

Conventions used everywhere in this module:

- ``prices`` is a Series of month-end prices with a DatetimeIndex. Money is
  invested at the close of a month, so month 0 is the start date.
- Lump sum buys with the whole amount at month 0.
- DCA splits the amount into ``months`` tranches bought at months
  0 .. months-1. Money waiting to be invested sits in cash earning
  ``cash_rate`` per year. Each tranche invests an equal share of the cash
  still waiting (balance / tranches left), so the interest is invested too
  and nothing is left in cash after the last tranche. At a 0% rate every
  tranche is exactly ``amount / months``.
- Both portfolios are valued at month ``horizon`` (``horizon >= months``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MONTHS_PER_YEAR = 12


def monthly_rate(annual_rate: float) -> float:
    """Compound monthly rate equivalent to an annual rate (0.04 -> ~0.00327)."""
    return float((1 + annual_rate) ** (1 / MONTHS_PER_YEAR) - 1)


def _check(prices: pd.Series, months: int, horizon: int) -> None:
    if months < 1:
        raise ValueError("DCA needs at least one month")
    if horizon < months:
        raise ValueError("The horizon must be at least as long as the DCA period")
    if len(prices) <= horizon:
        raise ValueError(f"Need {horizon + 1} monthly prices, got {len(prices)}")


def simulate(
    prices: pd.Series, amount: float, months: int, horizon: int, cash_rate: float = 0.0
) -> pd.DataFrame:
    """Month-by-month value of both strategies from ``prices.index[0]``.

    Returns a DataFrame indexed by date with columns ``lump_sum``, ``dca``,
    ``dca_invested`` (market value of the DCA shares) and ``dca_cash``.
    """
    _check(prices, months, horizon)
    path = prices.iloc[: horizon + 1].to_numpy(dtype=float)
    growth = 1 + monthly_rate(cash_rate)

    cash = np.zeros(len(path))
    shares = np.zeros(len(path))
    balance, held = float(amount), 0.0
    for t, price in enumerate(path):
        if t > 0:
            balance *= growth
        if t < months:
            tranche = balance / (months - t)
            held += tranche / price
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


def rolling_windows(
    prices: pd.Series, amount: float, months: int, horizon: int, cash_rate: float = 0.0
) -> pd.DataFrame:
    """Run the comparison for every start month that has a full horizon of data.

    One row per start date with the final value of each strategy, their
    total returns (%) and ``lump_vs_dca``: how much more (or less, if
    negative) lump sum ended with, as a % of the DCA result.
    """
    prices = prices.dropna()
    _check(prices, months, horizon)
    rows = []
    for start in range(len(prices) - horizon):
        final = simulate(prices.iloc[start:], amount, months, horizon, cash_rate).iloc[-1]
        rows.append((prices.index[start], final["lump_sum"], final["dca"]))

    out = pd.DataFrame(rows, columns=["start", "lump_sum", "dca"]).set_index("start")
    out["lump_sum_return"] = 100 * (out["lump_sum"] / amount - 1)
    out["dca_return"] = 100 * (out["dca"] / amount - 1)
    out["lump_vs_dca"] = 100 * (out["lump_sum"] / out["dca"] - 1)
    return out


@dataclass
class Summary:
    windows: int
    first_start: pd.Timestamp
    last_start: pd.Timestamp
    lump_win_rate: float  # % of windows where lump sum ended ahead
    mean_difference: float  # average lump_vs_dca, %
    median_difference: float
    lump_worst_return: float  # worst total return of each strategy over the horizon, %
    dca_worst_return: float
    lump_worst_start: pd.Timestamp
    dca_worst_start: pd.Timestamp


def summarize(windows: pd.DataFrame) -> Summary:
    """Headline numbers from the output of :func:`rolling_windows`."""
    if windows.empty:
        raise ValueError("No windows to summarize")
    diff = windows["lump_vs_dca"]
    return Summary(
        windows=len(windows),
        first_start=windows.index[0],
        last_start=windows.index[-1],
        lump_win_rate=float(100 * (diff > 0).mean()),
        mean_difference=float(diff.mean()),
        median_difference=float(diff.median()),
        lump_worst_return=float(windows["lump_sum_return"].min()),
        dca_worst_return=float(windows["dca_return"].min()),
        lump_worst_start=windows["lump_sum_return"].idxmin(),
        dca_worst_start=windows["dca_return"].idxmin(),
    )
