import os

import altair as alt
import pandas as pd
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.title("Basket Craft Dashboard")


@st.cache_resource
def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
    )


@st.cache_data(ttl=600)
def get_headline_metrics():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT order_month, revenue, orders, items_sold,
               ROUND(revenue / NULLIF(orders, 0), 2) AS aov
        FROM (
            SELECT
                DATE_TRUNC('month', TO_TIMESTAMP(created_at, 9)) AS order_month,
                SUM(price_usd)           AS revenue,
                COUNT(DISTINCT order_id) AS orders,
                SUM(items_purchased)     AS items_sold
            FROM orders
            GROUP BY 1
            ORDER BY order_month DESC
            LIMIT 2
        ) sub
        ORDER BY order_month ASC
    """)
    rows = cur.fetchall()
    if len(rows) < 2:
        st.error("Need at least two months of order data to display headline metrics.")
        st.stop()
    prior, current = rows[0], rows[1]
    return {
        "month": current[0].strftime("%B %Y"),
        "revenue": {"value": float(current[1]), "delta": float(current[1] - prior[1])},
        "orders": {"value": int(current[2]), "delta": int(current[2] - prior[2])},
        "items_sold": {"value": int(current[3]), "delta": int(current[3] - prior[3])},
        "aov": {"value": float(current[4]), "delta": float(current[4] - prior[4])},
    }


metrics = get_headline_metrics()

st.subheader(f"Headline metrics — {metrics['month']}")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Total Revenue",
    f"${metrics['revenue']['value']:,.0f}",
    f"${metrics['revenue']['delta']:+,.0f} vs prior month",
)
col2.metric(
    "Total Orders",
    f"{metrics['orders']['value']:,}",
    f"{metrics['orders']['delta']:+,} vs prior month",
)
col3.metric(
    "Avg Order Value",
    f"${metrics['aov']['value']:,.2f}",
    f"${metrics['aov']['delta']:+,.2f} vs prior month",
)
col4.metric(
    "Items Sold",
    f"{metrics['items_sold']['value']:,}",
    f"{metrics['items_sold']['delta']:+,} vs prior month",
)

st.divider()


@st.cache_data(ttl=600)
def get_monthly_revenue():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            DATE_TRUNC('month', TO_TIMESTAMP(created_at, 9)) AS month,
            SUM(price_usd) AS revenue
        FROM orders
        GROUP BY 1
        ORDER BY 1
    """)
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["month", "revenue"]).assign(
        month=lambda df: pd.to_datetime(df["month"]),
        revenue=lambda df: df["revenue"].astype(float),
    )


@st.cache_data(ttl=600)
def get_bundle_pairs():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            p1.product_name AS product,
            p2.product_name AS paired_with,
            COUNT(DISTINCT oi1.order_id) AS co_orders
        FROM order_items oi1
        JOIN order_items oi2 ON oi2.order_id = oi1.order_id
                            AND oi2.product_id != oi1.product_id
        JOIN products p1 ON p1.product_id = oi1.product_id
        JOIN products p2 ON p2.product_id = oi2.product_id
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
    """)
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["product", "paired_with", "co_orders"])


@st.cache_data(ttl=600)
def get_product_revenue_by_month():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            DATE_TRUNC('month', TO_TIMESTAMP(o.created_at, 9)) AS month,
            p.product_name,
            SUM(oi.price_usd) AS revenue
        FROM order_items oi
        JOIN orders  o ON o.order_id  = oi.order_id
        JOIN products p ON p.product_id = oi.product_id
        GROUP BY 1, 2
        ORDER BY 1
    """)
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["month", "product_name", "revenue"]).assign(
        month=lambda df: pd.to_datetime(df["month"]),
        revenue=lambda df: df["revenue"].astype(float),
    )


st.subheader("Revenue trend")

df = get_monthly_revenue()
latest = df["month"].max()

WINDOWS = {
    "Last 3 months": 3,
    "Last 6 months": 6,
    "Last 12 months": 12,
    "All time": None,
}

window_label = st.sidebar.selectbox("Date range", list(WINDOWS.keys()), index=2)

bundle_df = get_bundle_pairs()
all_products = sorted(bundle_df["product"].unique())
st.sidebar.divider()
selected_product = st.sidebar.selectbox("Bundle finder — pick a product", all_products)
months_back = WINDOWS[window_label]

if months_back is None:
    filtered = df
else:
    cutoff = latest - pd.DateOffset(months=months_back - 1)
    filtered = df[df["month"] >= cutoff]

chart = (
    alt.Chart(filtered)
    .mark_line(point=True)
    .encode(
        x=alt.X("month:T", title="Month", axis=alt.Axis(format="%b %Y", labelAngle=-45)),
        y=alt.Y("revenue:Q", title="Revenue ($)", axis=alt.Axis(format="$,.0f"), scale=alt.Scale(zero=False)),
        tooltip=[
            alt.Tooltip("month:T", title="Month", format="%B %Y"),
            alt.Tooltip("revenue:Q", title="Revenue", format="$,.2f"),
        ],
    )
    .properties(height=380)
    .interactive()
)
st.altair_chart(chart, use_container_width=True)

st.divider()
st.subheader("Top products by revenue")

prod_df = get_product_revenue_by_month()
prod_filtered = prod_df[prod_df["month"] >= cutoff] if months_back else prod_df

prod_totals = (
    prod_filtered.groupby("product_name", as_index=False)["revenue"]
    .sum()
    .sort_values("revenue", ascending=False)
)

bar = (
    alt.Chart(prod_totals)
    .mark_bar()
    .encode(
        x=alt.X("revenue:Q", title="Revenue ($)", axis=alt.Axis(format="$,.0f")),
        y=alt.Y("product_name:N", title=None, sort="-x"),
        tooltip=[
            alt.Tooltip("product_name:N", title="Product"),
            alt.Tooltip("revenue:Q", title="Revenue", format="$,.2f"),
        ],
    )
    .properties(height=180)
)
st.altair_chart(bar, use_container_width=True)

st.divider()
st.subheader("Bundle finder")
st.caption(f"Orders that also contained **{selected_product}**")

pairs = (
    bundle_df[bundle_df["product"] == selected_product]
    .sort_values("co_orders", ascending=False)
)

bundle_chart = (
    alt.Chart(pairs)
    .mark_bar()
    .encode(
        x=alt.X("co_orders:Q", title="Orders bought together"),
        y=alt.Y("paired_with:N", title=None, sort="-x"),
        tooltip=[
            alt.Tooltip("paired_with:N", title="Product"),
            alt.Tooltip("co_orders:Q", title="Co-purchase orders", format=","),
        ],
    )
    .properties(height=160)
)
st.altair_chart(bundle_chart, use_container_width=True)
