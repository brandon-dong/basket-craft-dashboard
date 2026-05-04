# Basket Craft Dashboard

**Live app:** https://basket-craft-dashboard-brandon-dong.streamlit.app/

A Streamlit dashboard connected to Snowflake that tracks Basket Craft's sales performance.

## Features

- Headline metrics (revenue, orders, AOV, items sold) with month-over-month deltas
- Revenue trend chart with adjustable date-range filter (3 / 6 / 12 months or all time)
- Top products by revenue bar chart
- Bundle finder — shows which products are most frequently bought together

## Local setup

1. Copy `.env.example` to `.env` and fill in your Snowflake credentials.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the app:
   ```
   streamlit run app.py
   ```

## Deployment

Deployed on [Streamlit Cloud](https://streamlit.io/cloud). Snowflake credentials are stored in the app's **Secrets** (`Settings → Secrets`) as TOML key-value pairs.
