import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.price_data import load_price_data
from src.scoring import calculate_heartbeat, calculate_chart_score, get_action_label
from src.watchlist import evaluate_watchlist
from src.database import load_scan_history, load_latest_scan
from src.fundamentals import load_fundamentals, calculate_fundamental_score
from src.valuation import build_valuation_summary
from src.final_score import calculate_final_score, get_final_label, get_final_action
from src.smart_money import build_smart_money_summary
from src.institution_map import (
    load_institution_universe,
    build_institution_summary,
    build_institution_heatmap_figure,
    prepare_institution_table
)
from src.institutional_holdings import (
    load_institution_holdings_sample,
    merge_holdings_with_universe,
    build_holdings_summary,
    build_institution_sector_treemap,
    build_sector_institution_treemap,
    prepare_holdings_table
)


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

@st.cache_data(ttl=3600)
def get_cached_institution_universe():
    return load_institution_universe("data/smart_money_universe.csv")

@st.cache_data(ttl=3600)
def get_cached_institution_holdings_sample():
    return load_institution_holdings_sample("data/institution_holdings_sample.csv")


# -----------------------------
# Formatting Helpers
# -----------------------------
def is_missing(value):
    if value is None:
        return True

    try:
        return pd.isna(value)
    except Exception:
        return False


def format_money(value):
    if is_missing(value):
        return "N/A"

    abs_value = abs(value)

    if abs_value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"

    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"

    return f"${value:,.2f}"


def format_percent(value):
    if is_missing(value):
        return "N/A"

    return f"{value * 100:.2f}%"


def format_growth_percent(value):
    if is_missing(value):
        return "N/A"

    return f"{value:.2f}%"


def format_number(value):
    if is_missing(value):
        return "N/A"

    return f"{value:.2f}"


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.header("Controls")

mode = st.sidebar.radio(
    "Dashboard Mode",
    ["Single Ticker", "Watchlist Scanner", "Score History", "Institution Map"],
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
            with st.expander("Smart Money Map Inputs", expanded=False):
                smart_money_options = [
                    "Strong Bullish",
                    "Bullish",
                    "Slightly Bullish",
                    "Neutral",
                    "Slightly Bearish",
                    "Bearish",
                    "Strong Bearish",
                    "Unknown"
                ]

                insider_signal_input = st.selectbox(
                    "Insider Buying/Selling Signal",
                    smart_money_options,
                    index=3,
                    key="insider_signal_input"
                )

                officer_signal_input = st.selectbox(
                    "Senior Officer Signal",
                    smart_money_options,
                    index=3,
                    key="officer_signal_input"
                )

                institutional_signal_input = st.selectbox(
                    "Institutional Flow Signal",
                    smart_money_options,
                    index=3,
                    key="institutional_signal_input"
                )

                politician_signal_input = st.selectbox(
                    "Politician Trading Signal",
                    smart_money_options,
                    index=3,
                    key="politician_signal_input"
                )

                smart_money_notes_input = st.text_area(
                    "Smart Money Notes",
                    value="",
                    key="smart_money_notes_input"
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
            smart_money = build_smart_money_summary(
                insider_signal=insider_signal_input,
                politician_signal=politician_signal_input,
                institutional_signal=institutional_signal_input,
                officer_signal=officer_signal_input,
                notes=smart_money_notes_input
            )

            final_score_data = calculate_final_score(
                chart_score=chart_score,
                fundamental_score=fundamental_score,
                valuation_score=valuation.get("valuation_score", 0),
                smart_money_score=smart_money.get("smart_money_score", 0)
            )
            final_score = final_score_data["final_score"]
            final_label = get_final_label(final_score)

            final_action = get_final_action(
                final_score=final_score,
                chart_action_label=action_label,
                valuation_label=valuation.get("valuation_label", "N/A"),
                profit_locker_status=metrics["profit_locker_status"]
            )

            # -----------------------------
            # Final Score
            # -----------------------------
            st.subheader("Final Evaluator Score")

            s1, s2, s3 = st.columns(3)

            s1.metric(
                "Final Score",
                f"{final_score}/100"
            )

            s2.metric(
                "Final Label",
                final_label
            )

            s3.metric(
                "Final Action",
                final_action
            )

            score_breakdown = {
                "Category": [
                    "Chart Heartbeat",
                    "Fundamentals",
                    "Valuation",
                    "Smart Money",
                    "Final Score"
                ],
                "Score": [
                    f"{chart_score}/100",
                    f"{fundamental_score}/100",
                    f"{valuation.get('valuation_score', 0)}/100",
                    f"{final_score_data['smart_money_normalized']:.0f}/100",
                    f"{final_score}/100"
                ],
                "Weight": [
                    "30%",
                    "35%",
                    "25%",
                    "10%",
                    "100%"
                ]
            }

            st.table(pd.DataFrame(score_breakdown))

            # -----------------------------
            # Chart Heartbeat
            # -----------------------------
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

            # -----------------------------
            # Evaluator Summary
            # -----------------------------
            st.subheader("Evaluator Summary")

            summary_data = {
                "Factor": [
                    "Final Score",
                    "Final Label",
                    "Final Action",
                    "Chart Heartbeat",
                    "150DMA Status",
                    "Profit Locker",
                    "Chart Action Label",
                    "Chart Score",
                    "Fundamental Score",
                    "Valuation Score"
                    "Smart Money Score",
                    "Smart Money Label",
                ],
                "Result": [
                    f"{final_score}/100",
                    final_label,
                    final_action,
                    metrics["heartbeat_status"],
                    f"{metrics['distance_from_150dma']:.2f}% from 150DMA",
                    metrics["profit_locker_status"],
                    action_label,
                    f"{chart_score}/100",
                    f"{fundamental_score}/100",
                    f"{valuation.get('valuation_score', 0)}/100"
                    f"{smart_money.get('smart_money_score', 0)}/5",
                    smart_money.get("smart_money_label", "N/A"),
                ]
            }

            st.table(pd.DataFrame(summary_data))

            # -----------------------------
            # Fundamentals
            # -----------------------------
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

            # -----------------------------
            # Valuation
            # -----------------------------
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
            # Smart Money Map
            # -----------------------------
            st.subheader("Smart Money Map")

            sm1, sm2, sm3 = st.columns(3)

            sm1.metric(
                "Smart Money Score",
                f"{smart_money.get('smart_money_score', 0)}/5"
            )

            sm2.metric(
                "Smart Money Label",
                smart_money.get("smart_money_label", "N/A")
            )

            sm3.metric(
                "Smart Money Action",
                smart_money.get("smart_money_action", "N/A")
            )

            smart_money_table = {
                "Factor": [
                    "Insider Signal",
                    "Senior Officer Signal",
                    "Institutional Signal",
                    "Politician Signal",
                    "Smart Money Score",
                    "Smart Money Label",
                    "Smart Money Action",
                    "Notes"
                ],
                "Result": [
                    smart_money.get("insider_signal", "N/A"),
                    smart_money.get("officer_signal", "N/A"),
                    smart_money.get("institutional_signal", "N/A"),
                    smart_money.get("politician_signal", "N/A"),
                    f"{smart_money.get('smart_money_score', 0)}/5",
                    smart_money.get("smart_money_label", "N/A"),
                    smart_money.get("smart_money_action", "N/A"),
                    smart_money.get("notes", "")
                ]
            }

            st.table(pd.DataFrame(smart_money_table))


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
        
# -----------------------------
# Institution Smart Money Heat Map
# -----------------------------
elif mode == "Institution Map":
    st.subheader("Institutional Smart Money Heat Map")

    st.write(
        "This section shows a Finviz-style institutional heat map. "
        "Universe view shows institution size and trackability. "
        "Sector exposure views show sample holdings, sector allocation, top holdings, exposure %, and QoQ flow. "
        "Green means accumulating. Red means reducing."
    )

    institution_df = get_cached_institution_universe()
    holdings_df = get_cached_institution_holdings_sample()

    merged_holdings_df = merge_holdings_with_universe(
        holdings_df=holdings_df,
        universe_df=institution_df
    )

    if institution_df.empty:
        st.error("No institution universe found. Check data/smart_money_universe.csv.")
    else:
        universe_summary = build_institution_summary(institution_df)

        u1, u2, u3, u4, u5 = st.columns(5)

        u1.metric(
            "Institutions Tracked",
            universe_summary["institution_count"]
        )

        u2.metric(
            "Total Assets / AUM",
            f"${universe_summary['total_assets_or_aum']:.2f}T"
        )

        u3.metric(
            "High Trackability",
            universe_summary["high_trackability_count"]
        )

        u4.metric(
            "Banks",
            universe_summary["bank_count"]
        )

        u5.metric(
            "PE / Alt / Hedge",
            universe_summary["alt_manager_count"] + universe_summary["hedge_fund_count"]
        )

    if merged_holdings_df.empty:
        st.warning("No holdings sample data found. Check data/institution_holdings_sample.csv.")
    else:
        holdings_summary = build_holdings_summary(merged_holdings_df)

        h1, h2, h3, h4, h5 = st.columns(5)

        h1.metric(
            "Tracked Holding Rows",
            holdings_summary["holding_count"]
        )

        h2.metric(
            "Institutions With Holdings",
            holdings_summary["institution_count"]
        )

        h3.metric(
            "Sectors Tracked",
            holdings_summary["sector_count"]
        )

        h4.metric(
            "Sample Market Value",
            f"${holdings_summary['total_market_value']:.2f}B"
        )

        h5.metric(
            "Net QoQ Flow",
            f"{holdings_summary['net_qoq_change']:.2f}%"
        )

    st.markdown("---")

    heatmap_tabs = st.tabs(
        [
            "Universe Heat Map",
            "Institution → Sector",
            "Sector → Institution",
            "Holdings Table",
            "6B-6 API Connector"
        ]
    )

    with heatmap_tabs[0]:
        st.subheader("Institution Universe Heat Map")

        st.write(
            "Box size = assets/AUM. Color = how easy the institution is to track with public data."
        )

        if institution_df.empty:
            st.error("No institution universe found.")
        else:
            type_options = sorted(institution_df["type"].unique().tolist())
            trackability_options = sorted(institution_df["trackability"].unique().tolist())
            country_options = sorted(institution_df["country"].unique().tolist())

            filter_col1, filter_col2, filter_col3 = st.columns(3)

            selected_types = filter_col1.multiselect(
                "Filter by institution type",
                type_options,
                default=type_options,
                key="universe_type_filter"
            )

            selected_trackability = filter_col2.multiselect(
                "Filter by trackability",
                trackability_options,
                default=trackability_options,
                key="universe_trackability_filter"
            )

            selected_countries = filter_col3.multiselect(
                "Filter by country",
                country_options,
                default=country_options,
                key="universe_country_filter"
            )

            filtered_universe_df = institution_df[
                institution_df["type"].isin(selected_types)
                & institution_df["trackability"].isin(selected_trackability)
                & institution_df["country"].isin(selected_countries)
            ]

            fig = build_institution_heatmap_figure(filtered_universe_df)

            st.plotly_chart(fig, width="stretch")

            table_df = prepare_institution_table(filtered_universe_df)

            st.dataframe(
                table_df,
                width="stretch",
                hide_index=True
            )

    with heatmap_tabs[1]:
        st.subheader("Institution → Sector Exposure")

        st.write(
            "6B-3 and 6B-5: Box size = sample reported market value. "
            "Color = weighted QoQ position change. "
            "Hover over tiles to see top holdings, exposure %, QoQ change, and flow details."
        )

        if merged_holdings_df.empty:
            st.warning("No holdings data available.")
        else:
            institution_options = sorted(
                merged_holdings_df["institution"].unique().tolist()
            )

            sector_options = sorted(
                merged_holdings_df["sector"].unique().tolist()
            )

            inst_filter_col, sector_filter_col = st.columns(2)

            selected_institutions = inst_filter_col.multiselect(
                "Filter institutions",
                institution_options,
                default=institution_options,
                key="institution_sector_institution_filter"
            )

            selected_sectors = sector_filter_col.multiselect(
                "Filter sectors",
                sector_options,
                default=sector_options,
                key="institution_sector_sector_filter"
            )

            filtered_holdings_df = merged_holdings_df[
                merged_holdings_df["institution"].isin(selected_institutions)
                & merged_holdings_df["sector"].isin(selected_sectors)
            ]

            fig = build_institution_sector_treemap(filtered_holdings_df)

            st.plotly_chart(fig, width="stretch")

    with heatmap_tabs[2]:
        st.subheader("Sector → Institution Exposure")

        st.write(
            "6B-4 and 6B-5: This view answers which sectors are attracting institutional money. "
            "Hover over tiles to see top holdings, sector exposure %, QoQ change, and flow details."
        )

        if merged_holdings_df.empty:
            st.warning("No holdings data available.")
        else:
            sector_options = sorted(
                merged_holdings_df["sector"].unique().tolist()
            )

            institution_options = sorted(
                merged_holdings_df["institution"].unique().tolist()
            )

            sector_filter_col, inst_filter_col = st.columns(2)

            selected_sectors = sector_filter_col.multiselect(
                "Filter sectors",
                sector_options,
                default=sector_options,
                key="sector_institution_sector_filter"
            )

            selected_institutions = inst_filter_col.multiselect(
                "Filter institutions",
                institution_options,
                default=institution_options,
                key="sector_institution_institution_filter"
            )

            filtered_holdings_df = merged_holdings_df[
                merged_holdings_df["sector"].isin(selected_sectors)
                & merged_holdings_df["institution"].isin(selected_institutions)
            ]

            fig = build_sector_institution_treemap(filtered_holdings_df)

            st.plotly_chart(fig, width="stretch")

    with heatmap_tabs[3]:
        st.subheader("Holdings Table")

        st.write(
            "This is the sample holdings data powering the sector heat maps."
        )

        if merged_holdings_df.empty:
            st.warning("No holdings data available.")
        else:
            holdings_table = prepare_holdings_table(merged_holdings_df)

            st.dataframe(
                holdings_table,
                width="stretch",
                hide_index=True
            )

            csv = holdings_table.to_csv(index=False)

            st.download_button(
                label="Download Holdings Table as CSV",
                data=csv,
                file_name="institution_holdings_sample.csv",
                mime="text/csv",
                key="download_institution_holdings_csv"
            )

    with heatmap_tabs[4]:
        st.subheader("6B-6 API Connector Roadmap")

        st.write(
            "This tab is the placeholder for replacing the sample CSV with a real FMP / SEC / 13F connector."
        )

        st.code(
            """
Next connector steps:

1. Choose data provider:
   - FMP for easier institutional ownership API
   - SEC 13F for official but harder raw filings
   - Quiver / sec-api.io for packaged alternative data

2. Add API key:
   export FMP_API_KEY="your_key_here"

3. Build connector output columns:
   institution
   sector
   ticker
   company
   market_value_billions
   position_change_qoq_pct
   shares_change_qoq_pct
   flow_status
   report_date

4. Replace:
   get_cached_institution_holdings_sample()

With:
   get_cached_live_institution_holdings()
            """,
            language="text"
        )