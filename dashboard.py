"""Streamlit dashboard for the e-commerce sales analysis.

A professional business-intelligence dashboard built on the same data and
metrics as ``EDA_Refactored.ipynb``. It reuses :mod:`data_loader` and
:mod:`business_metrics` without modification — this file only adds a global
date-range filter, comparison-period logic, and a Plotly-based presentation
layer.

Run with::

    streamlit run dashboard.py
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

import data_loader as dl
import business_metrics as bm

# ---------------------------------------------------------------------------
# Configuration & colour scheme
# ---------------------------------------------------------------------------
DATA_PATH = "ecommerce_data/"

COLOR_CURRENT = "#1f4e79"    # deep blue   - current period (solid line)
COLOR_PREVIOUS = "#9bb8d3"   # muted blue  - previous period (dashed line)
BLUE_SCALE = "Blues"         # sequential blue gradient for bars / choropleth
COLOR_BAR = "#2e75b6"        # single-series categorical bar
COLOR_POSITIVE = "#1e8e3e"   # green - favourable trend
COLOR_NEGATIVE = "#d93025"   # red   - unfavourable trend
COLOR_GRID = "rgba(0,0,0,0.08)"

PLOT_BG = "white"
CHART_HEIGHT = 360

st.set_page_config(page_title="E-commerce Sales Dashboard", layout="wide")


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def money_short(value: float) -> str:
    """Format a dollar amount compactly: 300_000 -> "$300K", 2_000_000 -> "$2M"."""
    if value is None or pd.isna(value):
        return "—"
    amount = abs(value)
    sign = "-" if value < 0 else ""
    if amount >= 1_000_000_000:
        text = f"{amount / 1_000_000_000:.1f}B"
    elif amount >= 1_000_000:
        text = f"{amount / 1_000_000:.1f}M"
    elif amount >= 1_000:
        text = f"{amount / 1_000:.0f}K"
    else:
        return f"{sign}${amount:,.0f}"
    text = text.replace(".0", "")  # 2.0M -> 2M, 300.0K -> 300K
    return f"{sign}${text}"


def money_full(value: float) -> str:
    """Format a dollar amount in full: 3360294.74 -> "$3,360,295"."""
    if value is None or pd.isna(value):
        return "—"
    return f"${value:,.0f}"


def axis_money_ticks(max_value: float, n: int = 6) -> tuple[list, list]:
    """Return evenly spaced tick positions and compact "$300K"-style labels."""
    if not max_value or max_value <= 0:
        return [0], ["$0"]
    step = max_value / (n - 1)
    vals = [step * i for i in range(n)]
    return vals, [money_short(v) for v in vals]


# ---------------------------------------------------------------------------
# Data loading & period filtering
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading sales data…")
def load_data() -> pd.DataFrame:
    """Load the analysis-ready, delivered-orders sales table (cached)."""
    return dl.load_sales_data(DATA_PATH)


def filter_date_range(sales: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Filter the sales table to rows whose purchase date is within [start, end]."""
    ts = sales["purchase_timestamp"]
    mask = (ts >= pd.Timestamp(start)) & (ts < pd.Timestamp(end) + pd.Timedelta(days=1))
    return sales[mask].copy()


def previous_period(start: date, end: date) -> tuple[date, date]:
    """The immediately preceding period of equal length (for comparisons)."""
    duration = end - start
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - duration
    return prev_start, prev_end


# ---------------------------------------------------------------------------
# Trend / KPI rendering (HTML cards for uniform height & professional styling)
# ---------------------------------------------------------------------------
def trend_html(pct: float | None, lower_is_better: bool = False) -> str:
    """Build the coloured arrow + percentage line shown under a KPI value.

    Green for a favourable move, red for an unfavourable one. ``lower_is_better``
    inverts the judgement (e.g. delivery time: a decrease is good).
    """
    if pct is None or pd.isna(pct):
        return '<div class="trend trend-flat">— no prior period</div>'
    favourable = (pct < 0) if lower_is_better else (pct > 0)
    color = COLOR_POSITIVE if favourable else COLOR_NEGATIVE
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
    return (
        f'<div class="trend" style="color:{color}">'
        f'{arrow} {abs(pct):.2f}% vs prev. period</div>'
    )


def kpi_card(label: str, value: str, trend: str = "") -> str:
    """A single KPI card (label, large value, optional trend line)."""
    filler = "<div class='trend trend-flat'>&nbsp;</div>"
    return (
        '<div class="card kpi-card">'
        f'<div class="card-label">{label}</div>'
        f'<div class="card-value">{value}</div>'
        f'{trend or filler}'
        "</div>"
    )


CSS = """
<style>
  .block-container { padding-top: 2rem; padding-bottom: 2rem; }
  .dash-title {
      font-size: 1.9rem; font-weight: 700; color: #1a1a1a;
      margin: 0; line-height: 2.4rem;
  }
  .dash-subtitle { color: #6b7280; font-size: 0.95rem; margin-top: 0.1rem; }
  .card {
      background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px;
      padding: 1.1rem 1.3rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
  .kpi-card { height: 132px; display: flex; flex-direction: column; justify-content: center; }
  .stat-card { height: 150px; display: flex; flex-direction: column; justify-content: center; }
  .card-label {
      color: #6b7280; font-size: 0.8rem; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.04em;
  }
  .card-value { color: #111827; font-size: 2.0rem; font-weight: 700; margin: 0.25rem 0; }
  .trend { font-size: 0.85rem; font-weight: 600; }
  .trend-flat { color: #9ca3af; }
  .stars { color: #f5a623; font-size: 1.6rem; letter-spacing: 0.1rem; }
  .stars .empty { color: #d1d5db; }
</style>
"""


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def _base_layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#111827")),
        height=CHART_HEIGHT,
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PLOT_BG,
        font=dict(color="#374151"),
    )
    return fig


def revenue_trend_chart(current: pd.DataFrame, previous: pd.DataFrame) -> go.Figure:
    """Monthly revenue: solid current period, dashed previous period overlaid."""
    cur = current.set_index("purchase_timestamp")["price"].resample("MS").sum()
    prev = previous.set_index("purchase_timestamp")["price"].resample("MS").sum()

    cur_labels = [d.strftime("%b %Y") for d in cur.index]
    prev_labels = [d.strftime("%b %Y") for d in prev.index]
    n = max(len(cur), len(prev))
    # Current-period months drive the x-axis ticks; fall back to previous labels
    # for any extra positions when the previous period spans more months.
    ticktext = (cur_labels + prev_labels)[:n] if len(cur_labels) < n else cur_labels

    fig = go.Figure()
    if len(prev):
        fig.add_trace(go.Scatter(
            x=list(range(len(prev))), y=prev.values, name="Previous period",
            mode="lines+markers", line=dict(color=COLOR_PREVIOUS, width=2, dash="dash"),
            marker=dict(size=6),
            customdata=prev_labels,
            hovertemplate="%{customdata}<br>%{y:$,.0f}<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=list(range(len(cur))), y=cur.values, name="Current period",
        mode="lines+markers", line=dict(color=COLOR_CURRENT, width=3),
        marker=dict(size=7),
        customdata=cur_labels,
        hovertemplate="%{customdata}<br>%{y:$,.0f}<extra></extra>",
    ))

    maxv = max(cur.max() if len(cur) else 0, prev.max() if len(prev) else 0)
    tickvals, ticklabels = axis_money_ticks(maxv)
    _base_layout(fig, "Revenue Trend")
    fig.update_xaxes(
        tickmode="array", tickvals=list(range(n)), ticktext=ticktext[:n],
        showgrid=True, gridcolor=COLOR_GRID, tickangle=-30,
    )
    fig.update_yaxes(
        tickmode="array", tickvals=tickvals, ticktext=ticklabels,
        showgrid=True, gridcolor=COLOR_GRID, rangemode="tozero",
    )
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.0,
                                  xanchor="right", x=1, font=dict(size=11)))
    return fig


def top_categories_chart(current: pd.DataFrame) -> go.Figure:
    """Top 10 categories by revenue, descending, blue gradient (light = low)."""
    revenue = bm.revenue_by_category(current).head(10)
    # Sort ascending so the largest bar sits at the top of a horizontal chart.
    revenue = revenue.sort_values()
    labels = [c.replace("_", " ").title() for c in revenue.index]

    fig = go.Figure(go.Bar(
        x=revenue.values, y=labels, orientation="h",
        marker=dict(color=revenue.values, colorscale=BLUE_SCALE, showscale=False),
        text=[money_short(v) for v in revenue.values],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>%{x:$,.0f}<extra></extra>",
    ))
    tickvals, ticklabels = axis_money_ticks(revenue.max())
    _base_layout(fig, "Top 10 Categories by Revenue")
    fig.update_xaxes(tickmode="array", tickvals=tickvals, ticktext=ticklabels,
                     showgrid=True, gridcolor=COLOR_GRID, rangemode="tozero")
    fig.update_yaxes(showgrid=False)
    fig.update_layout(margin=dict(l=10, r=60, t=50, b=10))
    return fig


def revenue_by_state_chart(current: pd.DataFrame) -> go.Figure:
    """US choropleth of revenue by state, blue gradient."""
    state_revenue = bm.revenue_by_state(current)
    fig = px.choropleth(
        state_revenue, locations="customer_state", color="revenue",
        locationmode="USA-states", scope="usa", color_continuous_scale=BLUE_SCALE,
    )
    fig.update_traces(hovertemplate="%{location}<br>%{z:$,.0f}<extra></extra>")
    _base_layout(fig, "Revenue by State")
    maxv = state_revenue["revenue"].max() if len(state_revenue) else 0
    tickvals, ticklabels = axis_money_ticks(maxv, n=5)
    fig.update_layout(
        geo=dict(bgcolor=PLOT_BG, lakecolor=PLOT_BG),
        coloraxis_colorbar=dict(title="Revenue", tickvals=tickvals, ticktext=ticklabels),
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def satisfaction_delivery_chart(current: pd.DataFrame) -> go.Figure:
    """Average review score by delivery-time bucket."""
    by_bucket = bm.review_by_delivery_bucket(current)
    fig = go.Figure(go.Bar(
        x=by_bucket["delivery_bucket"], y=by_bucket["review_score"],
        marker=dict(color=COLOR_BAR),
        text=[f"{v:.2f}" for v in by_bucket["review_score"]],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>Avg score %{y:.2f}<extra></extra>",
    ))
    _base_layout(fig, "Satisfaction vs Delivery Time")
    fig.update_xaxes(title_text="Delivery time", showgrid=False)
    fig.update_yaxes(title_text="Average review score", range=[0, 5.3],
                     showgrid=True, gridcolor=COLOR_GRID)
    return fig


def stars_html(score: float) -> str:
    """Render a 0–5 score as filled/empty star glyphs (rounded to nearest half)."""
    full = int(score)
    half = (score - full) >= 0.5
    empty = 5 - full - (1 if half else 0)
    stars = "★" * full + ("⯨" if half else "") + f'<span class="empty">{"☆" * empty}</span>'
    return f'<div class="stars">{stars}</div>'


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    sales = load_data()

    data_min = sales["purchase_timestamp"].min().date()
    data_max = sales["purchase_timestamp"].max().date()
    default_start = max(date(2023, 1, 1), data_min)
    default_end = min(date(2023, 12, 31), data_max)

    # ---- Header: title (left) + date range filter (right) ----
    head_left, head_right = st.columns([3, 2])
    with head_left:
        st.markdown('<div class="dash-title">E-commerce Sales Dashboard</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="dash-subtitle">Delivered-order revenue & customer '
                    'experience</div>', unsafe_allow_html=True)
    with head_right:
        date_range = st.date_input(
            "Date range", value=(default_start, default_end),
            min_value=data_min, max_value=data_max,
        )
    if not isinstance(date_range, (list, tuple)) or len(date_range) != 2:
        st.info("Select a start and end date to view the dashboard.")
        st.stop()
    start, end = date_range

    current = filter_date_range(sales, start, end)
    prev_start, prev_end = previous_period(start, end)
    previous = filter_date_range(sales, prev_start, prev_end)

    if current.empty:
        st.warning("No delivered orders in the selected date range.")
        st.stop()

    # ---- Metrics ----
    revenue = bm.total_revenue(current)
    orders = bm.total_orders(current)
    aov = bm.average_order_value(current)
    avg_growth = bm.average_monthly_growth(current)
    delivery = bm.average_delivery_days(current)
    review = bm.average_review_score(current)

    has_prev = not previous.empty
    rev_trend = bm.pct_change(revenue, bm.total_revenue(previous)) if has_prev else None
    ord_trend = bm.pct_change(orders, bm.total_orders(previous)) if has_prev else None
    aov_trend = bm.pct_change(aov, bm.average_order_value(previous)) if has_prev else None
    del_trend = (bm.pct_change(delivery, bm.average_delivery_days(previous))
                 if has_prev else None)

    growth_color = COLOR_POSITIVE if avg_growth >= 0 else COLOR_NEGATIVE
    growth_value = f'<span style="color:{growth_color}">{avg_growth:+.2f}%</span>'

    # ---- KPI row: 4 uniform cards ----
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi_card("Total Revenue", money_full(revenue), trend_html(rev_trend)),
                unsafe_allow_html=True)
    k2.markdown(kpi_card("Monthly Growth", growth_value), unsafe_allow_html=True)
    k3.markdown(kpi_card("Average Order Value", f"${aov:,.2f}", trend_html(aov_trend)),
                unsafe_allow_html=True)
    k4.markdown(kpi_card("Total Orders", f"{orders:,}", trend_html(ord_trend)),
                unsafe_allow_html=True)

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

    # ---- Charts grid: 2x2 ----
    config = {"displayModeBar": False}
    r1c1, r1c2 = st.columns(2)
    r1c1.plotly_chart(revenue_trend_chart(current, previous),
                      use_container_width=True, config=config)
    r1c2.plotly_chart(top_categories_chart(current),
                      use_container_width=True, config=config)

    r2c1, r2c2 = st.columns(2)
    r2c1.plotly_chart(revenue_by_state_chart(current),
                      use_container_width=True, config=config)
    r2c2.plotly_chart(satisfaction_delivery_chart(current),
                      use_container_width=True, config=config)

    # ---- Bottom row: 2 uniform cards ----
    b1, b2 = st.columns(2)
    b1.markdown(
        '<div class="card stat-card">'
        '<div class="card-label">Average Delivery Time</div>'
        f'<div class="card-value">{delivery:.1f} days</div>'
        f'{trend_html(del_trend, lower_is_better=True)}'
        "</div>",
        unsafe_allow_html=True,
    )
    b2.markdown(
        '<div class="card stat-card">'
        f'<div class="card-value">{review:.2f}</div>'
        f'{stars_html(review)}'
        '<div class="card-label" style="margin-top:0.35rem">Average Review Score</div>'
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
