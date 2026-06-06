import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.price_data import load_price_data
from src.scoring import calculate_heartbeat, calculate_chart_score, get_action_label
from src.watchlist import evaluate_watchlist
from src.database import load_scan_history, load_latest_scan
from src.fundamentals import load_fundamentals, calculate_fundamental_score
from src.valuation import build_valuation_summary


# -----------------------------
# Page Setup
# -----------------------------
st.set_page_config(
    page_title="Stock Evaluator",
    layout="wide"
)

st.title("Stock Evaluator Dashboard")
st.caption("Version 1: 150DMA Heartbeat + Profit Locker")


# -----------------------------
# Cached Data Loaders
# -----------------------------
@st.cache_data(ttl=3600)
def get_cached_price_data(ticker: str):
    return load_price_data(ticker)


@st.cache_data(ttl=3600)
def get_cached_fundamentals(ticker: str):
    return load_fundamentals(ticker)


@st.cache_data(ttl=300)
def get_cached_scan_history():
    return load_scan_history(limit=500)


@st.cache_data(ttl=300)
def get_cached_latest_scan():
    return load_latest_scan()


# -----------------------------
# Formatting Helpers
# -----------------------------
def format_money(value):
    if value is None:
        return "N/A"

    abs_value = abs(value)

    if abs_value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"

    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"

    return f"${value:,.2f}"


def format_percent(value):
    if value is None:
        return "N/A"

    return f"{value * 100:.2f}%"


def format_growth_percent(value):
    if value is None:
        return "N/A"

    return f"{value:.2f}%"


def format_number(value):
    if value is None:
        return "N/A"

    return f"{value:.2f}"


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.header("Controls")

mode = st.sidebar.radio(
    "Dashboard Mode",
    ["Single Ticker", "Watchlist Scanner", "Score History"],
    key="dashboard_mode"
)

st.sidebar.markdown("---")
st.sidebar.write("Core rules:")
st.sidebar.write("150DMA = heartbeat")
st.sidebar.write("25%+ above 150DMA = caution")
st.sidebar.write("35%+ above 150DMA = profit locker")


# -----------------------------
# Single Ticker Dashboard
# -----------------------------
if mode == "Single Ticker":
    ticker = st.sidebar.text_input(
        "Enter ticker",
        value="NVDA",
        key="single_ticker_input"
    ).upper()

    if not ticker:
        st.warning("Enter a ticker to begin.")
    else:
        data = get_cached_price_data(ticker)

        if data.empty or len(data) < 160:
            st.error("Not enough price data found for this ticker.")
        else:
            metrics = calculate_heartbeat(data)
            chart_score = calculate_chart_score(metrics)
            action_label = get_action_label(metrics, chart_score)

            fundamentals = get_cached_fundamentals(ticker)
            fundamental_score = calculate_fundamental_score(fundamentals)

            with st.expander("Valuation Assumptions", expanded=False):
                dcf_growth_rate_input = st.number_input(
                    "DCF FCF Growth Rate (%)",
                    min_value=-50.0,
                    max_value=100.0,
                    value=10.0,
                    step=1.0,
                    key="dcf_growth_rate_input"
                )

                discount_rate_input = st.number_input(
                    "Discount Rate / Required Return (%)",
                    min_value=1.0,
                    max_value=50.0,
                    value=10.0,
                    step=0.5,
                    key="discount_rate_input"
                )

                terminal_growth_rate_input = st.number_input(
                    "Terminal Growth Rate (%)",
                    min_value=0.0,
                    max_value=10.0,
                    value=3.0,
                    step=0.25,
                    key="terminal_growth_rate_input"
                )

                dcf_years_input = st.number_input(
                    "DCF Projection Years",
                    min_value=1,
                    max_value=10,
                    value=5,
                    step=1,
                    key="dcf_years_input"
                )

                eps_growth_rate_input = st.number_input(
                    "EPS Growth Rate (%)",
                    min_value=-50.0,
                    max_value=100.0,
                    value=10.0,
                    step=1.0,
                    key="eps_growth_rate_input"
                )

                future_pe_input = st.number_input(
                    "Future P/E Multiple",
                    min_value=1.0,
                    max_value=100.0,
                    value=25.0,
                    step=1.0,
                    key="future_pe_input"
                )

            valuation = build_valuation_summary(
                fundamentals=fundamentals,
                current_price=metrics["current_price"],
                dcf_growth_rate=dcf_growth_rate_input / 100,
                discount_rate=discount_rate_input / 100,
                terminal_growth_rate=terminal_growth_rate_input / 100,
                dcf_years=int(dcf_years_input),
                eps_growth_rate=eps_growth_rate_input / 100,
                future_pe=future_pe_input,
                eps_years=5
            )

            st.subheader(f"{ticker} Stock Heartbeat")

            col1, col2, col3, col4, col5 = st.columns(5)

            col1.metric(
                "Current Price",
                f"${metrics['current_price']:,.2f}"
            )

            col2.metric(
                "150DMA",
                f"${metrics['dma_150']:,.2f}"
            )

            col3.metric(
                "Distance from 150DMA",
                f"{metrics['distance_from_150dma']:.2f}%"
            )

            col4.metric(
                "Chart Score",
                f"{chart_score}/100"
            )

            col5.metric(
                "Action Label",
                action_label
            )

            st.info(f"Heartbeat Status: {metrics['heartbeat_status']}")
            st.warning(f"Profit Locker Status: {metrics['profit_locker_status']}")

            # Chart
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=data.index,
                y=data["Close"],
                mode="lines",
                name="Close Price"
            ))

            fig.add_trace(go.Scatter(
                x=data.index,
                y=data["50DMA"],
                mode="lines",
                name="50DMA"
            ))

            fig.add_trace(go.Scatter(
                x=data.index,
                y=data["150DMA"],
                mode="lines",
                name="150DMA"
            ))

            fig.update_layout(
                title=f"{ticker} Price vs 50DMA and 150DMA",
                xaxis_title="Date",
                yaxis_title="Price",
                height=650,
                hovermode="x unified"
            )

            st.plotly_chart(fig, width="stretch")

            # Evaluator Summary
            st.subheader("Evaluator Summary")

            summary_data = {
                "Factor": [
                    "Chart Heartbeat",
                    "150DMA Status",
                    "Profit Locker",
                    "Action Label",
                    "Final Version 1 Score"
                ],
                "Result": [
                    metrics["heartbeat_status"],
                    f"{metrics['distance_from_150dma']:.2f}% from 150DMA",
                    metrics["profit_locker_status"],
                    action_label,
                    f"{chart_score}/100"
                ]
            }

            st.table(pd.DataFrame(summary_data))

            # Fundamentals
            st.subheader("Fundamentals")

            f1, f2, f3, f4 = st.columns(4)

            f1.metric(
                "Revenue YoY Growth",
                format_growth_percent(fundamentals.get("revenue_yoy_growth"))
            )

            f2.metric(
                "Gross Margin",
                format_percent(fundamentals.get("gross_margin"))
            )

            f3.metric(
                "Operating Margin",
                format_percent(fundamentals.get("operating_margin"))
            )

            f4.metric(
                "Fundamental Score",
                f"{fundamental_score}/100"
            )

            f5, f6, f7, f8 = st.columns(4)

            f5.metric(
                "FCF Margin",
                format_percent(fundamentals.get("fcf_margin"))
            )

            f6.metric(
                "Cash",
                format_money(fundamentals.get("cash"))
            )

            f7.metric(
                "Debt / Equity",
                format_number(fundamentals.get("debt_to_equity"))
            )

            f8.metric(
                "Cash Runway",
                fundamentals.get("cash_runway_label", "N/A")
            )

            fundamental_table = {
                "Metric": [
                    "Revenue",
                    "Revenue YoY Growth",
                    "Gross Profit",
                    "Gross Margin",
                    "Operating Income",
                    "Operating Margin",
                    "Operating Cash Flow",
                    "Capital Expenditure",
                    "Free Cash Flow",
                    "FCF Margin",
                    "Cash",
                    "Total Debt",
                    "Debt / Equity",
                    "Current Ratio",
                    "Cash Runway",
                    "Fundamental Score"
                ],
                "Value": [
                    format_money(fundamentals.get("revenue")),
                    format_growth_percent(fundamentals.get("revenue_yoy_growth")),
                    format_money(fundamentals.get("gross_profit")),
                    format_percent(fundamentals.get("gross_margin")),
                    format_money(fundamentals.get("operating_income")),
                    format_percent(fundamentals.get("operating_margin")),
                    format_money(fundamentals.get("operating_cash_flow")),
                    format_money(fundamentals.get("capital_expenditure")),
                    format_money(fundamentals.get("free_cash_flow")),
                    format_percent(fundamentals.get("fcf_margin")),
                    format_money(fundamentals.get("cash")),
                    format_money(fundamentals.get("total_debt")),
                    format_number(fundamentals.get("debt_to_equity")),
                    format_number(fundamentals.get("current_ratio")),
                    fundamentals.get("cash_runway_label", "N/A"),
                    f"{fundamental_score}/100"
                ]
            }

            st.table(pd.DataFrame(fundamental_table))

            # Valuation
            st.subheader("Valuation")

            margin_of_safety = valuation.get("margin_of_safety")

            v1, v2, v3, v4 = st.columns(4)

            v1.metric(
                "Primary Intrinsic Value",
                format_money(valuation.get("primary_intrinsic_value"))
            )

            v2.metric(
                "Current Price",
                format_money(metrics.get("current_price"))
            )

            v3.metric(
                "Margin of Safety",
                "N/A" if margin_of_safety is None else f"{margin_of_safety:.2f}%"
            )

            v4.metric(
                "Valuation Score",
                f"{valuation.get('valuation_score')}/100"
            )

            v5, v6, v7, v8 = st.columns(4)

            v5.metric(
                "Valuation Label",
                valuation.get("valuation_label", "N/A")
            )

            v6.metric(
                "Valuation Method",
                valuation.get("valuation_method", "N/A")
            )

            v7.metric(
                "DCF Value",
                format_money(valuation.get("dcf_value"))
            )

            v8.metric(
                "EPS/P/E Value",
                format_money(valuation.get("eps_pe_value"))
            )

            valuation_table = {
                "Metric": [
                    "Current Price",
                    "DCF Value",
                    "EPS x Growth x P/E Value",
                    "Asset Value",
                    "Primary Intrinsic Value",
                    "Valuation Method",
                    "Margin of Safety",
                    "Valuation Score",
                    "Valuation Label"
                ],
                "Value": [
                    format_money(metrics.get("current_price")),
                    format_money(valuation.get("dcf_value")),
                    format_money(valuation.get("eps_pe_value")),
                    format_money(valuation.get("asset_value")),
                    format_money(valuation.get("primary_intrinsic_value")),
                    valuation.get("valuation_method", "N/A"),
                    "N/A" if valuation.get("margin_of_safety") is None else f"{valuation.get('margin_of_safety'):.2f}%",
                    f"{valuation.get('valuation_score')}/100",
                    valuation.get("valuation_label", "N/A")
                ]
            }

            st.table(pd.DataFrame(valuation_table))


# -----------------------------
# Watchlist Scanner
# -----------------------------
elif mode == "Watchlist Scanner":
    st.subheader("Watchlist Scanner")

    st.write("This scans every ticker inside data/watchlist.csv and saves the results to data/stocks.db.")

    if st.button("Scan Watchlist", key="scan_watchlist_button"):
        st.cache_data.clear()

        watchlist_results = evaluate_watchlist("data/watchlist.csv")

        if watchlist_results.empty:
            st.error("No watchlist data found. Check data/watchlist.csv.")
        else:
            st.success("Watchlist scan complete. Results saved to data/stocks.db.")

            st.dataframe(
                watchlist_results,
                width="stretch",
                hide_index=True
            )

            csv = watchlist_results.to_csv(index=False)

            st.download_button(
                label="Download Watchlist Results as CSV",
                data=csv,
                file_name="watchlist_results.csv",
                mime="text/csv",
                key="download_watchlist_csv"
            )


# -----------------------------
# Score History
# -----------------------------
elif mode == "Score History":
    st.subheader("Score History")

    st.write("This shows previous watchlist scans saved inside data/stocks.db.")

    history_choice = st.radio(
        "Choose history view",
        ["Latest Scan", "Full History"],
        horizontal=True,
        key="history_choice"
    )

    if history_choice == "Latest Scan":
        history_df = get_cached_latest_scan()
    else:
        history_df = get_cached_scan_history()

    if history_df.empty:
        st.warning("No scan history found yet. Run the Watchlist Scanner first.")
    else:
        st.dataframe(
            history_df,
            width="stretch",
            hide_index=True
        )

        csv = history_df.to_csv(index=False)

        st.download_button(
            label="Download History as CSV",
            data=csv,
            file_name="scan_history.csv",
            mime="text/csv",
            key="download_scan_history_csv"
        )