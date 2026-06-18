"""Data loading, cleaning, and preparation for the e-commerce analysis.

This module is responsible for everything that happens *before* business
metrics are calculated:

1. Reading the raw CSV extracts from the ``ecommerce_data`` directory.
2. Cleaning them (parsing timestamps, de-duplicating reviews).
3. Joining them into a single, analysis-ready "sales" table at the
   order-item grain, enriched with product, customer and review attributes.
4. Filtering that table to a configurable year / month period.

The output of :func:`build_sales_dataset` is the canonical table that the
``business_metrics`` module consumes. Keeping all I/O and reshaping here means
the notebook and the metrics module never touch raw files directly.
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd

# Mapping of logical dataset name -> CSV file name on disk.
DATASET_FILES = {
    "orders": "orders_dataset.csv",
    "order_items": "order_items_dataset.csv",
    "products": "products_dataset.csv",
    "customers": "customers_dataset.csv",
    "reviews": "order_reviews_dataset.csv",
    "payments": "order_payments_dataset.csv",
}

# Order statuses that represent realised revenue. Orders that were never
# delivered (cancelled, returned, still in transit) are excluded from sales
# metrics by default.
DELIVERED_STATUS = "delivered"


def load_raw_data(data_path: str = "ecommerce_data/") -> dict[str, pd.DataFrame]:
    """Load every raw CSV extract into a dictionary of DataFrames.

    Parameters
    ----------
    data_path:
        Directory containing the ``*_dataset.csv`` files.

    Returns
    -------
    dict[str, pandas.DataFrame]
        Keyed by the logical names in :data:`DATASET_FILES`
        (``"orders"``, ``"order_items"``, ``"products"``, ``"customers"``,
        ``"reviews"``, ``"payments"``).

    Raises
    ------
    FileNotFoundError
        If any expected CSV file is missing.
    """
    raw: dict[str, pd.DataFrame] = {}
    for name, file_name in DATASET_FILES.items():
        file_path = os.path.join(data_path, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Expected data file not found: {file_path}")
        raw[name] = pd.read_csv(file_path)
    return raw


def _clean_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Parse the timestamp columns of the orders table to ``datetime``."""
    orders = orders.copy()
    timestamp_columns = [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]
    for column in timestamp_columns:
        if column in orders.columns:
            orders[column] = pd.to_datetime(orders[column], errors="coerce")
    return orders


def _one_review_per_order(reviews: pd.DataFrame) -> pd.DataFrame:
    """Reduce the reviews table to a single score per order.

    An order can technically receive more than one review. To keep the
    order-item grain of the sales table intact (and avoid inflating revenue
    when joining), we collapse reviews to one row per ``order_id`` using the
    earliest review.
    """
    reviews = reviews.copy()
    reviews["review_creation_date"] = pd.to_datetime(
        reviews["review_creation_date"], errors="coerce"
    )
    reviews = reviews.sort_values("review_creation_date")
    deduped = reviews.drop_duplicates(subset="order_id", keep="first")
    return deduped[["order_id", "review_score"]]


def build_sales_dataset(
    raw: dict[str, pd.DataFrame],
    status: Optional[str] = DELIVERED_STATUS,
) -> pd.DataFrame:
    """Join the raw tables into one analysis-ready sales table.

    The result is at the **order-item grain** (one row per item within an
    order) and is enriched with product category, customer location, review
    score and derived time / delivery fields.

    Parameters
    ----------
    raw:
        Output of :func:`load_raw_data`.
    status:
        Order status to keep (default ``"delivered"``). Pass ``None`` to keep
        all statuses.

    Returns
    -------
    pandas.DataFrame
        Columns: ``order_id``, ``order_item_id``, ``product_id``, ``price``,
        ``order_status``, ``customer_id``, ``customer_state``,
        ``customer_city``, ``product_category_name``, ``purchase_timestamp``,
        ``delivered_customer_date``, ``purchase_year``, ``purchase_month``,
        ``delivery_days`` and ``review_score``.

    Notes
    -----
    Reviews are joined with a **left** merge so that orders without a review
    are retained for revenue metrics (their ``review_score`` is ``NaN`` and is
    ignored by the customer-experience calculations).
    """
    orders = _clean_orders(raw["orders"])
    order_items = raw["order_items"]
    products = raw["products"]
    customers = raw["customers"]
    reviews = _one_review_per_order(raw["reviews"])

    sales = order_items[["order_id", "order_item_id", "product_id", "price"]].merge(
        orders[
            [
                "order_id",
                "customer_id",
                "order_status",
                "order_purchase_timestamp",
                "order_delivered_customer_date",
            ]
        ],
        on="order_id",
        how="inner",
    )

    if status is not None:
        sales = sales[sales["order_status"] == status]

    sales = sales.merge(
        products[["product_id", "product_category_name"]], on="product_id", how="left"
    )
    sales = sales.merge(
        customers[["customer_id", "customer_state", "customer_city"]],
        on="customer_id",
        how="left",
    )
    sales = sales.merge(reviews, on="order_id", how="left")

    # Standardise column names and derive analysis fields.
    sales = sales.rename(
        columns={
            "order_purchase_timestamp": "purchase_timestamp",
            "order_delivered_customer_date": "delivered_customer_date",
        }
    )
    sales["purchase_year"] = sales["purchase_timestamp"].dt.year
    sales["purchase_month"] = sales["purchase_timestamp"].dt.month
    sales["delivery_days"] = (
        sales["delivered_customer_date"] - sales["purchase_timestamp"]
    ).dt.days

    return sales.reset_index(drop=True)


def filter_period(
    sales: pd.DataFrame,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> pd.DataFrame:
    """Filter the sales table to a configurable year and/or month.

    Parameters
    ----------
    sales:
        Sales table from :func:`build_sales_dataset`.
    year:
        Calendar year to keep, or ``None`` for all years.
    month:
        Calendar month (1-12) to keep, or ``None`` for the full year.

    Returns
    -------
    pandas.DataFrame
        The filtered sales table (a copy).
    """
    filtered = sales
    if year is not None:
        filtered = filtered[filtered["purchase_year"] == year]
    if month is not None:
        filtered = filtered[filtered["purchase_month"] == month]
    return filtered.copy()


def load_sales_data(
    data_path: str = "ecommerce_data/",
    status: Optional[str] = DELIVERED_STATUS,
) -> pd.DataFrame:
    """Convenience wrapper: load, clean and build the sales table in one call.

    Equivalent to ``build_sales_dataset(load_raw_data(data_path), status)``.
    """
    return build_sales_dataset(load_raw_data(data_path), status=status)
