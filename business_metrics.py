"""Business-metric calculations for the e-commerce analysis.

This module contains **calculations only** — no I/O and no plotting. Every
function takes an already-prepared, already-filtered sales table (the output
of :func:`data_loader.build_sales_dataset` passed through
:func:`data_loader.filter_period`) and returns a number, a Series or a small
DataFrame.

The functions are grouped into four business areas:

* Revenue analysis     – revenue, orders, average order value, growth trends
* Product analysis     – revenue and share by product category
* Geographic analysis  – revenue by customer state
* Customer experience  – review scores and delivery performance

A :func:`build_summary` helper assembles the headline KPIs (optionally with
year-over-year comparison) into a single dictionary, and
:func:`format_summary` renders that dictionary as a readable report.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def pct_change(current: float, previous: float) -> Optional[float]:
    """Return the percentage change from ``previous`` to ``current``.

    Returns ``None`` when ``previous`` is zero or missing, so callers can
    render "n/a" instead of dividing by zero.
    """
    if previous in (0, None) or pd.isna(previous):
        return None
    return (current - previous) / previous * 100.0


# ---------------------------------------------------------------------------
# Revenue analysis
# ---------------------------------------------------------------------------


def total_revenue(sales: pd.DataFrame) -> float:
    """Total revenue = sum of item prices for the period."""
    return float(sales["price"].sum())


def total_orders(sales: pd.DataFrame) -> int:
    """Number of distinct orders in the period."""
    return int(sales["order_id"].nunique())


def average_order_value(sales: pd.DataFrame) -> float:
    """Average revenue per order (AOV).

    Item prices are summed to the order level first, then averaged, so a
    multi-item order counts once.
    """
    order_totals = sales.groupby("order_id")["price"].sum()
    return float(order_totals.mean()) if len(order_totals) else 0.0


def monthly_revenue(sales: pd.DataFrame) -> pd.Series:
    """Revenue summed by calendar month, indexed 1-12 and sorted.

    Returns a Series named ``revenue`` indexed by ``purchase_month``.
    """
    series = sales.groupby("purchase_month")["price"].sum().sort_index()
    series.name = "revenue"
    return series


def monthly_growth(sales: pd.DataFrame) -> pd.Series:
    """Month-over-month revenue growth as a fraction (e.g. 0.05 = +5%)."""
    return monthly_revenue(sales).pct_change()


def average_monthly_growth(sales: pd.DataFrame) -> float:
    """Mean of the month-over-month growth rates, as a percentage."""
    growth = monthly_growth(sales).mean()
    return float(growth * 100.0) if pd.notna(growth) else 0.0


# ---------------------------------------------------------------------------
# Product analysis
# ---------------------------------------------------------------------------


def revenue_by_category(sales: pd.DataFrame) -> pd.Series:
    """Revenue by product category, sorted high to low.

    Returns a Series named ``revenue`` indexed by ``product_category_name``.
    """
    series = (
        sales.groupby("product_category_name")["price"]
        .sum()
        .sort_values(ascending=False)
    )
    series.name = "revenue"
    return series


def category_revenue_share(sales: pd.DataFrame) -> pd.Series:
    """Each category's share of total revenue, as a percentage (sorted)."""
    revenue = revenue_by_category(sales)
    total = revenue.sum()
    share = revenue / total * 100.0 if total else revenue * 0.0
    share.name = "revenue_share_pct"
    return share


# ---------------------------------------------------------------------------
# Geographic analysis
# ---------------------------------------------------------------------------


def revenue_by_state(sales: pd.DataFrame) -> pd.DataFrame:
    """Revenue by customer state, sorted high to low.

    Returns a DataFrame with columns ``customer_state`` and ``revenue``.
    """
    grouped = (
        sales.groupby("customer_state")["price"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={"price": "revenue"})
    )
    return grouped


# ---------------------------------------------------------------------------
# Customer experience analysis
# ---------------------------------------------------------------------------

# Buckets (in days) used to summarise delivery speed.
DELIVERY_SPEED_BUCKETS = ["1-3 days", "4-7 days", "8+ days"]


def categorize_delivery_speed(days: float) -> str:
    """Map a delivery time in days to a human-readable speed bucket."""
    if pd.isna(days):
        return "unknown"
    if days <= 3:
        return "1-3 days"
    if days <= 7:
        return "4-7 days"
    return "8+ days"


def _order_level_experience(sales: pd.DataFrame) -> pd.DataFrame:
    """One row per order with its ``delivery_days`` and ``review_score``.

    Rows without a review score are dropped, matching the original analysis
    which only looked at delivery/review behaviour for reviewed orders.
    """
    cols = ["order_id", "delivery_days", "review_score"]
    return sales[cols].dropna(subset=["review_score"]).drop_duplicates("order_id")


def average_review_score(sales: pd.DataFrame) -> float:
    """Average review score (1-5) across reviewed orders in the period."""
    experience = _order_level_experience(sales)
    return float(experience["review_score"].mean()) if len(experience) else 0.0


def review_score_distribution(sales: pd.DataFrame) -> pd.Series:
    """Share of orders at each review score (1-5), as a fraction summing to 1.

    Returns a Series named ``share`` indexed by ``review_score``.
    """
    experience = _order_level_experience(sales)
    distribution = (
        experience["review_score"].value_counts(normalize=True).sort_index()
    )
    distribution.name = "share"
    return distribution


def average_delivery_days(sales: pd.DataFrame) -> float:
    """Average delivery time in days across reviewed, delivered orders."""
    experience = _order_level_experience(sales)
    return float(experience["delivery_days"].mean()) if len(experience) else 0.0


def review_by_delivery_bucket(sales: pd.DataFrame) -> pd.DataFrame:
    """Average review score for each delivery-speed bucket.

    Returns a DataFrame with columns ``delivery_bucket`` and ``review_score``,
    ordered fast to slow.
    """
    experience = _order_level_experience(sales).copy()
    experience["delivery_bucket"] = experience["delivery_days"].apply(
        categorize_delivery_speed
    )
    grouped = (
        experience.groupby("delivery_bucket")["review_score"].mean().reset_index()
    )
    # Order the buckets logically rather than alphabetically.
    order = {bucket: i for i, bucket in enumerate(DELIVERY_SPEED_BUCKETS)}
    grouped["__sort"] = grouped["delivery_bucket"].map(order)
    grouped = grouped.sort_values("__sort").drop(columns="__sort")
    return grouped.reset_index(drop=True)


def fast_delivery_share(sales: pd.DataFrame, max_days: int = 3) -> float:
    """Percentage of reviewed orders delivered within ``max_days`` days."""
    experience = _order_level_experience(sales)
    if not len(experience):
        return 0.0
    fast = (experience["delivery_days"] <= max_days).mean()
    return float(fast * 100.0)


def high_satisfaction_share(sales: pd.DataFrame, min_score: int = 4) -> float:
    """Percentage of reviewed orders rated ``min_score`` or higher."""
    experience = _order_level_experience(sales)
    if not len(experience):
        return 0.0
    high = (experience["review_score"] >= min_score).mean()
    return float(high * 100.0)


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------


def build_summary(
    current: pd.DataFrame,
    previous: Optional[pd.DataFrame] = None,
) -> dict:
    """Assemble headline KPIs into a nested dictionary.

    Parameters
    ----------
    current:
        Filtered sales table for the analysis period.
    previous:
        Optional filtered sales table for a comparison period. When provided,
        growth rates (percentage change vs. the comparison period) are added.

    Returns
    -------
    dict
        Nested under ``"revenue"``, ``"customer_experience"`` and, when a
        comparison period is given, ``"growth"`` (percentage changes).
    """
    summary = {
        "revenue": {
            "total_revenue": total_revenue(current),
            "total_orders": total_orders(current),
            "average_order_value": average_order_value(current),
            "average_monthly_growth_pct": average_monthly_growth(current),
        },
        "customer_experience": {
            "average_review_score": average_review_score(current),
            "high_satisfaction_pct": high_satisfaction_share(current),
            "average_delivery_days": average_delivery_days(current),
            "fast_delivery_pct": fast_delivery_share(current),
        },
    }

    if previous is not None:
        summary["growth"] = {
            "revenue_growth_pct": pct_change(
                total_revenue(current), total_revenue(previous)
            ),
            "orders_growth_pct": pct_change(
                total_orders(current), total_orders(previous)
            ),
            "aov_growth_pct": pct_change(
                average_order_value(current), average_order_value(previous)
            ),
        }

    return summary


def format_summary(summary: dict, period_label: str = "") -> str:
    """Render :func:`build_summary` output as a readable text report."""

    def money(value: float) -> str:
        return f"${value:,.2f}"

    def pct(value: Optional[float]) -> str:
        return "n/a" if value is None else f"{value:+.1f}%"

    revenue = summary["revenue"]
    experience = summary["customer_experience"]
    growth = summary.get("growth", {})

    header = f"BUSINESS METRICS SUMMARY{(' - ' + period_label) if period_label else ''}"
    lines = [header, "=" * 60, "", "REVENUE PERFORMANCE:"]
    lines.append(f"  Total Revenue:       {money(revenue['total_revenue'])}")
    lines.append(f"  Total Orders:        {revenue['total_orders']:,}")
    lines.append(f"  Average Order Value: {money(revenue['average_order_value'])}")
    if "revenue_growth_pct" in growth:
        lines.append(f"  Revenue Growth:      {pct(growth['revenue_growth_pct'])}")
        lines.append(f"  Orders Growth:       {pct(growth['orders_growth_pct'])}")
        lines.append(f"  AOV Growth:          {pct(growth['aov_growth_pct'])}")

    lines += ["", "CUSTOMER EXPERIENCE:"]
    lines.append(
        f"  Average Review Score: {experience['average_review_score']:.2f}/5.0"
    )
    lines.append(
        f"  High Satisfaction (4+): {experience['high_satisfaction_pct']:.1f}%"
    )
    lines.append(
        f"  Average Delivery Time:  {experience['average_delivery_days']:.1f} days"
    )
    lines.append(
        f"  Fast Delivery (<=3 days): {experience['fast_delivery_pct']:.1f}%"
    )

    return "\n".join(lines)
