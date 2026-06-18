# E-commerce Sales Analysis

A refactored, configurable analysis of e-commerce sales data. It reworks the
original exploratory notebook (`EDA.ipynb`) into a documented, modular project:
the **same metrics and charts**, reorganised into clear sections with reusable
code in two Python modules.

## Project structure

```
.
├── EDA.ipynb                # Original exploratory notebook (kept for reference)
├── EDA_Refactored.ipynb     # Refactored, documented analysis notebook
├── data_loader.py           # Data loading, cleaning, joining and filtering
├── business_metrics.py      # Business-metric calculations (no I/O, no plotting)
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── ecommerce_data/          # Raw CSV extracts
    ├── orders_dataset.csv
    ├── order_items_dataset.csv
    ├── products_dataset.csv
    ├── customers_dataset.csv
    ├── order_reviews_dataset.csv
    └── order_payments_dataset.csv
```

## What changed in the refactor

- **Structure & docs** — the notebook now has a table of contents, a data
  dictionary, and markdown headers explaining each section (Introduction →
  Loading & Configuration → Preparation → Metrics → Summary).
- **Modular code** — all loading/cleaning moved to `data_loader.py`; all metric
  math moved to `business_metrics.py`. Every function has a docstring.
- **No more warnings** — the original `SettingWithCopyWarning` chains and
  per-row `.apply(lambda)` date parsing are replaced by a single, vectorised
  transformation. Reviews are de-duplicated to one score per order and
  left-joined so revenue rows are never dropped or inflated.
- **Configurable period** — instead of hard-coded 2023/2022 filters, a single
  config block selects the analysis year, comparison year and (optionally) a
  month. All metrics and charts regenerate for whatever period you choose.
- **Better charts** — every plot has a descriptive title with the date range,
  axis labels with units, value labels, and a consistent business colour
  scheme.

## Setup

Requires Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

### Run the notebook

```bash
jupyter lab EDA_Refactored.ipynb   # or: jupyter notebook
```

Configure the analysis in the first code cell, then **Run All**:

```python
DATA_PATH = "ecommerce_data/"
ANALYSIS_YEAR = 2023        # Year to analyse
COMPARISON_YEAR = 2022      # Year to compare against (None to skip)
ANALYSIS_MONTH = None       # Specific month 1-12, or None for the full year
```

Examples:

- Full year 2023 vs 2022 → defaults above.
- March 2023 only → `ANALYSIS_MONTH = 3`.
- 2022 with no comparison → `ANALYSIS_YEAR = 2022`, `COMPARISON_YEAR = None`.

### Use the modules directly

```python
import data_loader as dl
import business_metrics as bm

# Load, clean and join all tables into one delivered-sales table.
sales = dl.load_sales_data("ecommerce_data/")

# Filter to any period (year and/or month).
current = dl.filter_period(sales, year=2023, month=None)
previous = dl.filter_period(sales, year=2022)

# Calculate metrics.
bm.total_revenue(current)            # 3360294.74
bm.average_order_value(current)      # 724.98
bm.revenue_by_category(current)      # Series, sorted high to low
bm.revenue_by_state(current)         # DataFrame: customer_state, revenue
bm.average_review_score(current)     # 4.10

# Year-over-year comparison and a printable summary.
summary = bm.build_summary(current, previous)
print(bm.format_summary(summary, "2023"))
```

## Modules

### `data_loader.py`

Everything that happens *before* metrics are calculated.

| Function | Purpose |
|---|---|
| `load_raw_data(data_path)` | Read all CSVs into a dict of DataFrames |
| `build_sales_dataset(raw, status="delivered")` | Clean and join into one order-item table enriched with category, state, review score and derived date/delivery fields |
| `filter_period(sales, year, month)` | Filter to a configurable year and/or month |
| `load_sales_data(data_path, status)` | Convenience wrapper for the three steps above |

### `business_metrics.py`

Calculations only — each takes a filtered sales table.

| Area | Functions |
|---|---|
| Revenue | `total_revenue`, `total_orders`, `average_order_value`, `monthly_revenue`, `monthly_growth`, `average_monthly_growth` |
| Product | `revenue_by_category`, `category_revenue_share` |
| Geography | `revenue_by_state` |
| Customer experience | `average_review_score`, `review_score_distribution`, `average_delivery_days`, `review_by_delivery_bucket`, `fast_delivery_share`, `high_satisfaction_share` |
| Reporting | `pct_change`, `build_summary`, `format_summary` |

## Key business metrics

- **Total revenue** — sum of delivered item prices.
- **Average order value (AOV)** — average revenue per order.
- **Month-over-month growth** — percentage change in monthly revenue.
- **Revenue by category / state** — concentration of sales by product line and region.
- **Average review score** — mean customer rating (1–5).
- **Delivery performance** — average delivery days and review score by delivery-speed bucket.

## Headline results (2023 vs 2022)

| Metric | 2023 | vs 2022 |
|---|---|---|
| Total revenue | $3,360,294.74 | −2.5% |
| Total orders | 4,635 | −2.4% |
| Average order value | $724.98 | −0.1% |
| Average review score | 4.10 / 5.0 | — |
| Average delivery time | 8.0 days | — |

Top categories: **electronics**, **home & garden**. Top states: **CA, TX, FL**.
Orders delivered in 1–3 days score highest (4.19), so faster delivery is
associated with better reviews.

## Notes

- All revenue is based on **delivered** orders only. Change the `status`
  argument of `load_sales_data` / `build_sales_dataset` to analyse other
  statuses (e.g. `None` for all orders).
- The original `EDA.ipynb` is retained unchanged for reference and comparison.
