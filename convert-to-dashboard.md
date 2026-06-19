Convert `@EDA_Refactored.ipynb` into a professional Streamlit dashboard with this exact layout:

## Layout Structure
- **Header**: Title + date range filter (applies globally)
    - Title: left
    - Date range filter: right
- **KPI Row**: 4 cards (Total Revenue, Monthly Growth, Average order Value, Total Orders)
    - Trend indicators for Total Revenue, Average Order Value and Total Orders
    - Use red for negative trends and green for positive trend
- **Charts Grid**: 2x2 layout
  - Revenue trend line chart:
      - solid line for the current period
      - dashed line for the previous period
      - Add grid lines for easier reading
      - Y-axis formatting - show values as $300K instead of $300,000
  - Top 10 categories bar chart sorted descending:
      - Use blue gradient (light shade for lower values)
      - Format values as $300K and $2M  
  - Revenue by state: US choropleth map Color-coded by revenue amount
      - Use blue gradient
  - Bar chart showing satisfaction vs delivery time:
	- x-axis: Delivery time buckets (1-3 days, 4-7 days, etc.)
	- y-axis: Average review score
- **Bottom Row**: 2 cards 
   - Average delivery time with trend indicator
   - Review Score:
   	- Large number with stars
   	- Subtitle: "Average Review Score"

## Key Requirements
- Use Plotly for all charts
- Filter update charts correctly
- Professional styling with trend arrows/colors
- Do not use icons
- Use uniform card heights for each row
- Show two decimal places for each trend indicator
- Include requirements.txt and README.md
