"""Streamlit front end: invest a lump sum now, or spread it over a few months?"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dca_vs_lump.prices import TICKERS, load_prices
from dca_vs_lump.strategies import MONTHS_PER_YEAR, rolling_windows, simulate, summarize

LUMP, DCA = "#2a78d6", "#eb6834"
SURFACE = "#fcfcfb"
INK, INK_2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
CHART_CONFIG = {"displayModeBar": False}

st.set_page_config(page_title="DCA vs Lump Sum", layout="wide")


@st.cache_data
def get_prices() -> pd.DataFrame:
    return load_prices()


@st.cache_data
def get_windows(ticker: str, amount: float, months: int, horizon: int, cash_rate: float) -> pd.DataFrame:
    return rolling_windows(get_prices()[ticker], amount, months, horizon, cash_rate)


def base_layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK_2, size=13),
        hoverlabel=dict(bgcolor="white", font_color=INK, bordercolor=GRID),
        legend=dict(orientation="h", y=1.08, x=0, title=None),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, color=MUTED)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, color=MUTED)
    return fig


def path_chart(path: pd.DataFrame, amount: float) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(
        x=path.index,
        y=path["lump_sum"],
        name="Lump sum",
        line=dict(color=LUMP, width=2.5),
        hovertemplate="%{x|%b %Y}<br>Lump sum: <b>$%{y:,.0f}</b><extra></extra>",
    )
    fig.add_scatter(
        x=path.index,
        y=path["dca"],
        name="DCA",
        line=dict(color=DCA, width=2.5),
        customdata=path[["dca_cash"]].values,
        hovertemplate=(
            "%{x|%b %Y}<br>DCA: <b>$%{y:,.0f}</b><br>still in cash: $%{customdata[0]:,.0f}<extra></extra>"
        ),
    )
    fig.add_hline(y=amount, line=dict(color=MUTED, width=1, dash="dot"))
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    return base_layout(fig, 380)


def histogram(diff: pd.Series, chosen: float) -> go.Figure:
    edge = max(abs(diff.min()), abs(diff.max()))
    size = max(edge / 25, 0.5)
    bins = dict(start=-size * (edge // size + 1), end=size * (edge // size + 1), size=size)
    fig = go.Figure()
    fig.add_histogram(
        x=diff[diff > 0],
        xbins=bins,
        name="Lump sum ahead",
        marker=dict(color=LUMP, line=dict(color=SURFACE, width=1)),
        hovertemplate="%{y} periods<extra></extra>",
    )
    fig.add_histogram(
        x=diff[diff <= 0],
        xbins=bins,
        name="DCA ahead",
        marker=dict(color=DCA, line=dict(color=SURFACE, width=1)),
        hovertemplate="%{y} periods<extra></extra>",
    )
    fig.add_vline(x=chosen, line=dict(color=INK, width=1.5, dash="dash"))
    fig.update_layout(barmode="overlay", bargap=0)
    fig.update_xaxes(ticksuffix="%", title=dict(text="Lump sum result vs DCA", font=dict(size=12)))
    fig.update_yaxes(title=dict(text="Number of periods", font=dict(size=12)))
    return base_layout(fig, 340)


def difference_by_start(diff: pd.Series, chosen: pd.Timestamp) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(
        x=diff.index,
        y=diff.where(diff > 0),
        name="Lump sum ahead",
        marker=dict(color=LUMP, line=dict(width=0)),
        hovertemplate="Start %{x|%b %Y}<br>lump sum %{y:+.1f}% vs DCA<extra></extra>",
    )
    fig.add_bar(
        x=diff.index,
        y=diff.where(diff <= 0),
        name="DCA ahead",
        marker=dict(color=DCA, line=dict(width=0)),
        hovertemplate="Start %{x|%b %Y}<br>lump sum %{y:+.1f}% vs DCA<extra></extra>",
    )
    fig.add_vline(x=chosen, line=dict(color=INK, width=1.5, dash="dash"))
    fig.update_layout(barmode="overlay", bargap=0)
    fig.update_yaxes(ticksuffix="%")
    return base_layout(fig, 340)


def signed(value: float) -> str:
    return f"{value:+.1f}%"


prices = get_prices()

st.sidebar.header("Your situation")
ticker = st.sidebar.selectbox(
    "Invest in", list(TICKERS), format_func=lambda t: f"{t} · {TICKERS[t]}", key="ticker"
)
amount = st.sidebar.number_input("Amount", min_value=1_000.0, value=100_000.0, step=10_000.0, format="%.0f")
months = st.sidebar.slider("Spread it over (months)", 1, 24, 12, help="DCA invests an equal part each month.")
years = st.sidebar.slider(
    "Compare after (years)", 1, 10, 10, help="How long after the first purchase the two are compared."
)
cash_rate = st.sidebar.number_input(
    "Interest on cash waiting to be invested (% per year)",
    min_value=0.0,
    max_value=10.0,
    value=0.0,
    step=0.5,
    format="%.1f",
    help="What the uninvested part of the DCA money earns meanwhile, e.g. in a savings account.",
)
horizon = years * MONTHS_PER_YEAR

st.title("DCA vs Lump Sum")
st.markdown(
    "You have a large amount to invest. Put it all in **today**, or split it and buy a bit every month "
    "(**dollar-cost averaging**, DCA)? Here is what actually happened with real prices, "
    "for every possible start month."
)

series = prices[ticker].dropna()
if months > horizon:
    st.info("The comparison period has to be at least as long as the DCA period. Increase the years.")
    st.stop()
if len(series) <= horizon:
    st.info(f"{ticker} doesn't have {years} years of history yet. Pick a shorter period.")
    st.stop()

if months == 1:
    st.info("Spread over one month, DCA is the same as investing everything at once. Pick 2 months or more.")
    st.stop()

windows = get_windows(ticker, amount, months, horizon, cash_rate / 100)
summary = summarize(windows)
diff = windows["lump_vs_dca"]
period = f"{years}-year" if years > 1 else "1-year"
since = summary.first_start.strftime("%b %Y")

k1, k2, k3, k4 = st.columns(4)
k1.metric(
    "Lump sum came out ahead in",
    f"{summary.lump_win_rate:.0f}% of periods",
    help=f"Share of the {summary.windows} {period} periods, one per start month since {since}.",
)
k2.metric(
    "Typical gap",
    signed(summary.median_difference),
    help="Median of how much more (+) or less (-) lump sum ended with, compared with DCA.",
)
k3.metric(
    f"Worst {period} result · lump sum",
    signed(summary.lump_worst_return),
    help=f"Total return, starting {summary.lump_worst_start:%b %Y}.",
)
k4.metric(
    f"Worst {period} result · DCA",
    signed(summary.dca_worst_return),
    help=f"Total return, starting {summary.dca_worst_start:%b %Y}.",
)
st.markdown(
    f"Investing everything at once in **{ticker}** beat spreading it over {months} months in "
    f"**{summary.lump_win_rate:.0f}%** of the {summary.windows} {period} periods that started between "
    f"{since} and {summary.last_start:%b %Y}. On average it ended **{summary.mean_difference:+.1f}%** "
    "compared with DCA. DCA mostly wins when the market falls soon after the start date."
)

starts = list(windows.index)
start = st.select_slider(
    "Start date for the detailed view",
    options=starts,
    value=starts[-1],
    format_func=lambda d: d.strftime("%b %Y"),
)
path = simulate(series.loc[start:], amount, months, horizon, cash_rate / 100)
final = path.iloc[-1]

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader(f"Starting {start:%B %Y}")
    st.caption(f"Value of each portfolio month by month. Dotted line: the ${amount:,.0f} you started with.")
    st.plotly_chart(path_chart(path, amount), width="stretch", config=CHART_CONFIG)
with right:
    st.subheader(f"After {years} year{'s' if years > 1 else ''}")
    winner = "Lump sum" if final["lump_sum"] > final["dca"] else "DCA"
    m1, m2 = st.columns(2)
    m1.metric("Lump sum", f"${final['lump_sum']:,.0f}", signed(100 * (final["lump_sum"] / amount - 1)))
    m2.metric("DCA", f"${final['dca']:,.0f}", signed(100 * (final["dca"] / amount - 1)))
    st.markdown(
        f"**{winner}** ended ahead by **${abs(final['lump_sum'] - final['dca']):,.0f}** "
        f"({abs(diff.loc[start]):.1f}%)."
    )
    ranked = int((diff < diff.loc[start]).mean() * 100)
    st.caption(f"This start date did better for lump sum than {ranked}% of all start dates.")

h_left, h_right = st.columns(2, gap="large")
with h_left:
    st.subheader("How often, and by how much")
    st.caption(
        "Each start month is one period. Right of zero: lump sum ended with more money. "
        "Dashed line: your start date."
    )
    st.plotly_chart(histogram(diff, float(diff.loc[start])), width="stretch", config=CHART_CONFIG)
with h_right:
    st.subheader("Result by start date")
    st.caption(
        "How much more (above zero) or less lump sum ended with, for each possible start month. "
        "Dashed line: your start date."
    )
    st.plotly_chart(difference_by_start(diff, start), width="stretch", config=CHART_CONFIG)

st.divider()
st.caption(
    f"Monthly closing prices from Yahoo Finance, adjusted for dividends (reinvested), "
    f"through {prices.index[-1]:%B %Y}. Taxes and trading costs are ignored. "
    "Past results don't predict future ones. For education only, not investment advice."
)
