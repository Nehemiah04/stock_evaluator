import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.price_data import load_price_data
from src.scoring import calculate_heartbeat, calculate_chart_score, get_action_label
from src.full_evaluator import evaluate_full_watchlist, DEFAULT_VALUATION_ASSUMPTIONS
from src.watchlist_loader import load_watchlist_tickers
from src.database import load_scan_history, load_latest_scan
from src.fundamentals import load_fundamentals, calculate_fundamental_score
from src.valuation import build_valuation_summary
from src.final_score import calculate_final_score, get_final_label, get_final_action
from src.smart_money import build_smart_money_summary
from src.institution_map import (
    load_institution_universe,
    build_institution_summary,
    build_institution_heatmap_figure,
    prepare_institution_table,
)
from src.institutional_holdings import (
    load_institution_holdings_sample,
    merge_holdings_with_universe,
    build_holdings_summary,
    build_institution_sector_treemap,
    build_sector_institution_treemap,
    prepare_holdings_table,
)
from src.institutional_connector import build_live_institutional_holdings
from src.sec_13f_connector import build_sec_13f_holdings
from src.institutional_scoring import (
    build_institutional_smart_money_summary,
    build_institutional_score_table,
    build_top_flow_tables,
)
from src.full_scan_database import (
    save_full_scan_results,
    load_full_scan_history,
    load_latest_full_scan,
)
from src.watchlist_filters import (
    apply_watchlist_filters,
    sort_watchlist_results,
    get_watchlist_display_columns,
)
from src.watchlist_visuals import (
    build_top_final_score_chart,
    build_score_breakdown_chart,
    build_150dma_risk_scatter,
    build_institutional_flow_chart,
)
from src.alerts import (
    build_watchlist_alerts,
    build_alert_summary,
    build_alert_severity_chart,
    build_profit_locker_distance_chart,
)
from src.portfolio import (
    load_portfolio_positions,
    build_portfolio_dashboard,
    build_portfolio_summary,
    get_portfolio_display_columns,
)
from src.portfolio_visuals import (
    build_portfolio_allocation_pie,
    build_portfolio_value_bar,
    build_portfolio_gain_loss_chart,
    build_portfolio_score_weight_scatter,
    build_portfolio_profit_locker_table,
    build_portfolio_risk_summary,
)
from src.portfolio_rebalance import (
    load_portfolio_targets,
    build_rebalance_plan,
    build_rebalance_summary,
    get_rebalance_display_columns,
)
from src.thesis_generator import generate_stock_thesis, build_thesis_markdown
from src.thesis_reports import (
    build_batch_thesis_report,
    build_thesis_summary_table,
)

# -----------------------------
# Page Setup
# -----------------------------
st.set_page_config(
    page_title="Stock Evaluator",
    layout="wide",
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


@st.cache_data(ttl=3600)
def get_cached_live_institution_holdings(
    api_key: str, report_date: str, page_limit: int
):
    return build_live_institutional_holdings(
        api_key=api_key,
        report_date=report_date,
        page_limit=page_limit,
    )


@st.cache_data(ttl=3600)
def get_cached_sec_13f_holdings(manager_limit: int):
    return build_sec_13f_holdings(
        manager_limit=manager_limit,
    )


@st.cache_data(ttl=3600)
def get_cached_watchlist_tickers():
    return load_watchlist_tickers("data/watchlist.csv")


@st.cache_data(ttl=300)
def get_cached_full_scan_history():
    return load_full_scan_history(limit=1000)


@st.cache_data(ttl=300)
def get_cached_latest_full_scan():
    return load_latest_full_scan()


@st.cache_data(ttl=3600)
def get_cached_portfolio_positions():
    return load_portfolio_positions("data/portfolio.csv")


@st.cache_data(ttl=3600)
def get_cached_portfolio_targets():
    return load_portfolio_targets("data/portfolio_targets.csv")


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


def get_active_institutional_holdings_for_scoring() -> pd.DataFrame:
    """
    Gets the best available institutional holdings data for Single Ticker scoring.

    Priority:
    1. SEC 13F data loaded in Institution Map
    2. FMP live data loaded in Institution Map
    3. Sample CSV fallback
    """

    sec_df = st.session_state.get("sec_13f_holdings_df", pd.DataFrame())

    if not sec_df.empty:
        holdings_df = sec_df
    else:
        live_df = st.session_state.get("live_institutional_holdings_df", pd.DataFrame())

        if not live_df.empty:
            holdings_df = live_df
        else:
            holdings_df = get_cached_institution_holdings_sample()

    institution_df = get_cached_institution_universe()

    merged_df = merge_holdings_with_universe(
        holdings_df=holdings_df,
        universe_df=institution_df,
    )

    return merged_df


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.header("Controls")

mode = st.sidebar.radio(
    "Dashboard Mode",
    [
        "Single Ticker",
        "Watchlist Scanner",
        "Score History",
        "Institution Map",
        "Portfolio",
    ],
    key="dashboard_mode",
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
        key="single_ticker_input",
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
                    key="dcf_growth_rate_input",
                )

                discount_rate_input = st.number_input(
                    "Discount Rate / Required Return (%)",
                    min_value=1.0,
                    max_value=50.0,
                    value=10.0,
                    step=0.5,
                    key="discount_rate_input",
                )

                terminal_growth_rate_input = st.number_input(
                    "Terminal Growth Rate (%)",
                    min_value=0.0,
                    max_value=10.0,
                    value=3.0,
                    step=0.25,
                    key="terminal_growth_rate_input",
                )

                dcf_years_input = st.number_input(
                    "DCF Projection Years",
                    min_value=1,
                    max_value=10,
                    value=5,
                    step=1,
                    key="dcf_years_input",
                )

                eps_growth_rate_input = st.number_input(
                    "EPS Growth Rate (%)",
                    min_value=-50.0,
                    max_value=100.0,
                    value=10.0,
                    step=1.0,
                    key="eps_growth_rate_input",
                )

                future_pe_input = st.number_input(
                    "Future P/E Multiple",
                    min_value=1.0,
                    max_value=100.0,
                    value=25.0,
                    step=1.0,
                    key="future_pe_input",
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
                    "Unknown",
                ]

                insider_signal_input = st.selectbox(
                    "Insider Buying/Selling Signal",
                    smart_money_options,
                    index=3,
                    key="insider_signal_input",
                )

                officer_signal_input = st.selectbox(
                    "Senior Officer Signal",
                    smart_money_options,
                    index=3,
                    key="officer_signal_input",
                )

                institutional_signal_input = st.selectbox(
                    "Institutional Flow Signal",
                    smart_money_options,
                    index=3,
                    key="institutional_signal_input",
                )

                politician_signal_input = st.selectbox(
                    "Politician Trading Signal",
                    smart_money_options,
                    index=3,
                    key="politician_signal_input",
                )

                smart_money_notes_input = st.text_area(
                    "Smart Money Notes",
                    value="",
                    key="smart_money_notes_input",
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
                eps_years=5,
            )

            smart_money = build_smart_money_summary(
                insider_signal=insider_signal_input,
                politician_signal=politician_signal_input,
                institutional_signal=institutional_signal_input,
                officer_signal=officer_signal_input,
                notes=smart_money_notes_input,
            )

            institutional_holdings_for_scoring = (
                get_active_institutional_holdings_for_scoring()
            )

            if (
                not institutional_holdings_for_scoring.empty
                and "ticker" in institutional_holdings_for_scoring.columns
            ):
                ticker_institutional_holdings = institutional_holdings_for_scoring[
                    institutional_holdings_for_scoring["ticker"].astype(str).str.upper()
                    == ticker
                ]
            else:
                ticker_institutional_holdings = pd.DataFrame()

            institutional_smart_money = build_institutional_smart_money_summary(
                ticker_institutional_holdings,
                ticker=ticker,
            )

            manual_smart_money_score = smart_money.get("smart_money_score", 0)
            institutional_smart_money_score = institutional_smart_money.get(
                "institutional_smart_money_score",
                0,
            )

            if institutional_smart_money.get("holding_count", 0) > 0:
                final_smart_money_score = round(
                    (manual_smart_money_score * 0.35)
                    + (institutional_smart_money_score * 0.65),
                    2,
                )
            else:
                final_smart_money_score = manual_smart_money_score

            final_score_data = calculate_final_score(
                chart_score=chart_score,
                fundamental_score=fundamental_score,
                valuation_score=valuation.get("valuation_score", 0),
                smart_money_score=final_smart_money_score,
            )

            final_score = final_score_data["final_score"]
            final_label = get_final_label(final_score)

            final_action = get_final_action(
                final_score=final_score,
                chart_action_label=action_label,
                valuation_label=valuation.get("valuation_label", "N/A"),
                profit_locker_status=metrics["profit_locker_status"],
            )

            # -----------------------------
            # Final Score
            # -----------------------------
            st.subheader("Final Evaluator Score")

            s1, s2, s3 = st.columns(3)

            s1.metric(
                "Final Score",
                f"{final_score}/100",
            )

            s2.metric(
                "Final Label",
                final_label,
            )

            s3.metric(
                "Final Action",
                final_action,
            )

            score_breakdown = {
                "Category": [
                    "Chart Heartbeat",
                    "Fundamentals",
                    "Valuation",
                    "Smart Money",
                    "Final Score",
                ],
                "Score": [
                    f"{chart_score}/100",
                    f"{fundamental_score}/100",
                    f"{valuation.get('valuation_score', 0)}/100",
                    f"{final_score_data['smart_money_normalized']:.0f}/100",
                    f"{final_score}/100",
                ],
                "Weight": [
                    "30%",
                    "35%",
                    "25%",
                    "10%",
                    "100%",
                ],
            }

            st.table(pd.DataFrame(score_breakdown).astype(str))

            # -----------------------------
            # Chart Heartbeat
            # -----------------------------
            st.subheader(f"{ticker} Stock Heartbeat")

            col1, col2, col3, col4, col5 = st.columns(5)

            col1.metric(
                "Current Price",
                f"${metrics['current_price']:,.2f}",
            )

            col2.metric(
                "150DMA",
                f"${metrics['dma_150']:,.2f}",
            )

            col3.metric(
                "Distance from 150DMA",
                f"{metrics['distance_from_150dma']:.2f}%",
            )

            col4.metric(
                "Chart Score",
                f"{chart_score}/100",
            )

            col5.metric(
                "Action Label",
                action_label,
            )

            st.info(f"Heartbeat Status: {metrics['heartbeat_status']}")
            st.warning(f"Profit Locker Status: {metrics['profit_locker_status']}")

            fig = go.Figure()

            fig.add_trace(
                go.Scatter(
                    x=data.index,
                    y=data["Close"],
                    mode="lines",
                    name="Close Price",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=data.index,
                    y=data["50DMA"],
                    mode="lines",
                    name="50DMA",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=data.index,
                    y=data["150DMA"],
                    mode="lines",
                    name="150DMA",
                )
            )

            fig.update_layout(
                title=f"{ticker} Price vs 50DMA and 150DMA",
                xaxis_title="Date",
                yaxis_title="Price",
                height=650,
                hovermode="x unified",
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
                    "Valuation Score",
                    "Smart Money Score",
                    "Smart Money Label",
                    "Institutional Smart Money Score",
                    "Final Smart Money Used",
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
                    f"{valuation.get('valuation_score', 0)}/100",
                    f"{smart_money.get('smart_money_score', 0)}/5",
                    smart_money.get("smart_money_label", "N/A"),
                    f"{institutional_smart_money.get('institutional_smart_money_score', 0)}/5",
                    f"{final_smart_money_score}/5",
                ],
            }

            st.table(pd.DataFrame(summary_data).astype(str))

            # -----------------------------
            # Fundamentals
            # -----------------------------
            st.subheader("Fundamentals")

            f1, f2, f3, f4 = st.columns(4)

            f1.metric(
                "Revenue YoY Growth",
                format_growth_percent(fundamentals.get("revenue_yoy_growth")),
            )

            f2.metric(
                "Gross Margin",
                format_percent(fundamentals.get("gross_margin")),
            )

            f3.metric(
                "Operating Margin",
                format_percent(fundamentals.get("operating_margin")),
            )

            f4.metric(
                "Fundamental Score",
                f"{fundamental_score}/100",
            )

            f5, f6, f7, f8 = st.columns(4)

            f5.metric(
                "FCF Margin",
                format_percent(fundamentals.get("fcf_margin")),
            )

            f6.metric(
                "Cash",
                format_money(fundamentals.get("cash")),
            )

            f7.metric(
                "Debt / Equity",
                format_number(fundamentals.get("debt_to_equity")),
            )

            f8.metric(
                "Cash Runway",
                fundamentals.get("cash_runway_label", "N/A"),
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
                    "Fundamental Score",
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
                    f"{fundamental_score}/100",
                ],
            }

            st.table(pd.DataFrame(fundamental_table).astype(str))

            # -----------------------------
            # Valuation
            # -----------------------------
            st.subheader("Valuation")

            margin_of_safety = valuation.get("margin_of_safety")

            v1, v2, v3, v4 = st.columns(4)

            v1.metric(
                "Primary Intrinsic Value",
                format_money(valuation.get("primary_intrinsic_value")),
            )

            v2.metric(
                "Current Price",
                format_money(metrics.get("current_price")),
            )

            v3.metric(
                "Margin of Safety",
                "N/A" if margin_of_safety is None else f"{margin_of_safety:.2f}%",
            )

            v4.metric(
                "Valuation Score",
                f"{valuation.get('valuation_score')}/100",
            )

            v5, v6, v7, v8 = st.columns(4)

            v5.metric(
                "Valuation Label",
                valuation.get("valuation_label", "N/A"),
            )

            v6.metric(
                "Valuation Method",
                valuation.get("valuation_method", "N/A"),
            )

            v7.metric(
                "DCF Value",
                format_money(valuation.get("dcf_value")),
            )

            v8.metric(
                "EPS/P/E Value",
                format_money(valuation.get("eps_pe_value")),
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
                    "Valuation Label",
                ],
                "Value": [
                    format_money(metrics.get("current_price")),
                    format_money(valuation.get("dcf_value")),
                    format_money(valuation.get("eps_pe_value")),
                    format_money(valuation.get("asset_value")),
                    format_money(valuation.get("primary_intrinsic_value")),
                    valuation.get("valuation_method", "N/A"),
                    (
                        "N/A"
                        if valuation.get("margin_of_safety") is None
                        else f"{valuation.get('margin_of_safety'):.2f}%"
                    ),
                    f"{valuation.get('valuation_score')}/100",
                    valuation.get("valuation_label", "N/A"),
                ],
            }

            st.table(pd.DataFrame(valuation_table).astype(str))

            # -----------------------------
            # Smart Money Map
            # -----------------------------
            st.subheader("Smart Money Map")

            sm1, sm2, sm3 = st.columns(3)

            sm1.metric(
                "Smart Money Score",
                f"{smart_money.get('smart_money_score', 0)}/5",
            )

            sm2.metric(
                "Smart Money Label",
                smart_money.get("smart_money_label", "N/A"),
            )

            sm3.metric(
                "Smart Money Action",
                smart_money.get("smart_money_action", "N/A"),
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
                    "Notes",
                ],
                "Result": [
                    smart_money.get("insider_signal", "N/A"),
                    smart_money.get("officer_signal", "N/A"),
                    smart_money.get("institutional_signal", "N/A"),
                    smart_money.get("politician_signal", "N/A"),
                    f"{smart_money.get('smart_money_score', 0)}/5",
                    smart_money.get("smart_money_label", "N/A"),
                    smart_money.get("smart_money_action", "N/A"),
                    smart_money.get("notes", ""),
                ],
            }

            st.table(pd.DataFrame(smart_money_table).astype(str))

            st.subheader("Institutional Smart Money Score")

            ism1, ism2, ism3, ism4 = st.columns(4)

            ism1.metric(
                "Institutional Score",
                f"{institutional_smart_money.get('institutional_smart_money_score', 0)}/5",
            )

            ism2.metric(
                "Net QoQ Flow",
                f"{institutional_smart_money.get('net_qoq_flow_pct', 0):.2f}%",
            )

            ism3.metric(
                "Institutions",
                institutional_smart_money.get("institution_count", 0),
            )

            ism4.metric(
                "Final Smart Money Used",
                f"{final_smart_money_score}/5",
            )

            st.table(
                build_institutional_score_table(institutional_smart_money).astype(str)
            )

            st.markdown("---")
            st.subheader("AI-Style Thesis Generator")

            thesis = generate_stock_thesis(
                ticker=ticker,
                metrics=metrics,
                fundamentals=fundamentals,
                valuation=valuation,
                smart_money=smart_money,
                institutional_smart_money=institutional_smart_money,
                chart_score=chart_score,
                fundamental_score=fundamental_score,
                final_smart_money_score=final_smart_money_score,
                final_score=final_score,
                final_label=final_label,
                final_action=final_action,
            )

            thesis_markdown = build_thesis_markdown(thesis)

            st.markdown(thesis_markdown)

            st.download_button(
                label="Download Thesis as Markdown",
                data=thesis_markdown,
                file_name=f"{ticker}_stock_thesis.md",
                mime="text/markdown",
                key="download_single_ticker_thesis",
            )


# -----------------------------
# Watchlist Scanner 2.0
# -----------------------------
elif mode == "Watchlist Scanner":
    st.subheader("Watchlist Scanner 2.0")

    st.write(
        "This scans tickers from data/watchlist.csv using the full evaluator engine: "
        "chart score, fundamentals, valuation, institutional smart money, and final score."
    )

    watchlist_tickers = get_cached_watchlist_tickers()

    if not watchlist_tickers:
        st.error("No tickers found. Check data/watchlist.csv.")
    else:
        st.success(f"Loaded {len(watchlist_tickers)} tickers from data/watchlist.csv.")

        with st.expander("Scanner Settings", expanded=True):
            max_scan_count = st.number_input(
                "Maximum tickers to scan",
                min_value=1,
                max_value=max(1, len(watchlist_tickers)),
                value=min(10, len(watchlist_tickers)),
                step=1,
                key="watchlist_max_scan_count",
            )

            selected_scan_tickers = st.multiselect(
                "Choose tickers to scan",
                watchlist_tickers,
                default=watchlist_tickers[: int(max_scan_count)],
                key="watchlist_selected_tickers",
            )

            manual_scanner_smart_money_score = st.number_input(
                "Manual Smart Money Score for Scanner (-5 to +5)",
                min_value=-5.0,
                max_value=5.0,
                value=0.0,
                step=0.5,
                key="manual_scanner_smart_money_score",
            )

        with st.expander("Scanner Valuation Assumptions", expanded=False):
            scanner_dcf_growth_rate = st.number_input(
                "DCF FCF Growth Rate (%)",
                min_value=-50.0,
                max_value=100.0,
                value=DEFAULT_VALUATION_ASSUMPTIONS["dcf_growth_rate"] * 100,
                step=1.0,
                key="scanner_dcf_growth_rate",
            )

            scanner_discount_rate = st.number_input(
                "Discount Rate / Required Return (%)",
                min_value=1.0,
                max_value=50.0,
                value=DEFAULT_VALUATION_ASSUMPTIONS["discount_rate"] * 100,
                step=0.5,
                key="scanner_discount_rate",
            )

            scanner_terminal_growth_rate = st.number_input(
                "Terminal Growth Rate (%)",
                min_value=0.0,
                max_value=10.0,
                value=DEFAULT_VALUATION_ASSUMPTIONS["terminal_growth_rate"] * 100,
                step=0.25,
                key="scanner_terminal_growth_rate",
            )

            scanner_dcf_years = st.number_input(
                "DCF Projection Years",
                min_value=1,
                max_value=10,
                value=int(DEFAULT_VALUATION_ASSUMPTIONS["dcf_years"]),
                step=1,
                key="scanner_dcf_years",
            )

            scanner_eps_growth_rate = st.number_input(
                "EPS Growth Rate (%)",
                min_value=-50.0,
                max_value=100.0,
                value=DEFAULT_VALUATION_ASSUMPTIONS["eps_growth_rate"] * 100,
                step=1.0,
                key="scanner_eps_growth_rate",
            )

            scanner_future_pe = st.number_input(
                "Future P/E Multiple",
                min_value=1.0,
                max_value=100.0,
                value=float(DEFAULT_VALUATION_ASSUMPTIONS["future_pe"]),
                step=1.0,
                key="scanner_future_pe",
            )

        scanner_valuation_assumptions = {
            "dcf_growth_rate": scanner_dcf_growth_rate / 100,
            "discount_rate": scanner_discount_rate / 100,
            "terminal_growth_rate": scanner_terminal_growth_rate / 100,
            "dcf_years": int(scanner_dcf_years),
            "eps_growth_rate": scanner_eps_growth_rate / 100,
            "future_pe": scanner_future_pe,
            "eps_years": 5,
        }

        institutional_holdings_for_scanner = (
            get_active_institutional_holdings_for_scoring()
        )

        scanner_info_col1, scanner_info_col2, scanner_info_col3 = st.columns(3)

        scanner_info_col1.metric(
            "Selected Tickers",
            len(selected_scan_tickers),
        )

        scanner_info_col2.metric(
            "Institutional Holding Rows Available",
            len(institutional_holdings_for_scanner),
        )

        scanner_info_col3.metric(
            "Manual Smart Money",
            f"{manual_scanner_smart_money_score}/5",
        )

        if st.button("Run Full Watchlist Scan", key="run_full_watchlist_scan"):
            if not selected_scan_tickers:
                st.warning("Select at least one ticker to scan.")
            else:
                with st.spinner("Running full watchlist scan..."):
                    scan_results_df = evaluate_full_watchlist(
                        tickers=selected_scan_tickers,
                        institutional_holdings_df=institutional_holdings_for_scanner,
                        manual_smart_money_score=manual_scanner_smart_money_score,
                        valuation_assumptions=scanner_valuation_assumptions,
                    )

                    saved_count = save_full_scan_results(scan_results_df)

                    st.session_state["full_watchlist_scan_results_df"] = scan_results_df
                    st.session_state["full_watchlist_saved_count"] = saved_count

                    st.cache_data.clear()

        scan_results_df = st.session_state.get(
            "full_watchlist_scan_results_df",
            pd.DataFrame(),
        )

        if scan_results_df.empty:
            st.info("Run the full watchlist scan to see ranked results.")
        else:
            st.subheader("Ranked Watchlist Results")

            saved_count = st.session_state.get("full_watchlist_saved_count", 0)

            if saved_count:
                st.success(f"Saved {saved_count} full scan rows to data/stocks.db.")

            st.markdown("### Scanner Filters")

            filter_col1, filter_col2, filter_col3 = st.columns(3)

            min_final_score_filter = filter_col1.slider(
                "Minimum Final Score",
                min_value=0,
                max_value=100,
                value=0,
                step=5,
                key="filter_min_final_score",
            )

            min_chart_score_filter = filter_col2.slider(
                "Minimum Chart Score",
                min_value=0,
                max_value=100,
                value=0,
                step=5,
                key="filter_min_chart_score",
            )

            min_fundamental_score_filter = filter_col3.slider(
                "Minimum Fundamental Score",
                min_value=0,
                max_value=100,
                value=0,
                step=5,
                key="filter_min_fundamental_score",
            )

            filter_col4, filter_col5, filter_col6 = st.columns(3)

            min_valuation_score_filter = filter_col4.slider(
                "Minimum Valuation Score",
                min_value=0,
                max_value=100,
                value=0,
                step=5,
                key="filter_min_valuation_score",
            )

            min_institutional_score_filter = filter_col5.slider(
                "Minimum Institutional Score",
                min_value=-5.0,
                max_value=5.0,
                value=-5.0,
                step=0.5,
                key="filter_min_institutional_score",
            )

            sort_option = filter_col6.selectbox(
                "Sort Results By",
                [
                    "Final Score",
                    "Chart Score",
                    "Fundamental Score",
                    "Valuation Score",
                    "Smart Money Score",
                    "Institutional Score",
                    "Institutional Flow",
                    "Margin of Safety",
                    "Distance From 150DMA",
                ],
                index=0,
                key="watchlist_sort_option",
            )

            toggle_col1, toggle_col2, toggle_col3, toggle_col4, toggle_col5 = (
                st.columns(5)
            )

            require_ok_status_filter = toggle_col1.checkbox(
                "Only OK rows",
                value=True,
                key="filter_require_ok_status",
            )

            require_above_150dma_filter = toggle_col2.checkbox(
                "Above 150DMA only",
                value=False,
                key="filter_above_150dma",
            )

            hide_profit_locker_filter = toggle_col3.checkbox(
                "Hide Profit Locker warnings",
                value=False,
                key="filter_hide_profit_locker",
            )

            require_positive_margin_filter = toggle_col4.checkbox(
                "Positive Margin of Safety",
                value=False,
                key="filter_positive_margin",
            )

            require_institutional_accumulation_filter = toggle_col5.checkbox(
                "Institutional accumulation",
                value=False,
                key="filter_institutional_accumulation",
            )

            ascending_sort = st.checkbox(
                "Sort ascending instead of descending",
                value=False,
                key="watchlist_sort_ascending",
            )

            filtered_scan_df = apply_watchlist_filters(
                scan_results_df,
                min_final_score=min_final_score_filter,
                min_chart_score=min_chart_score_filter,
                min_fundamental_score=min_fundamental_score_filter,
                min_valuation_score=min_valuation_score_filter,
                min_institutional_score=min_institutional_score_filter,
                require_ok_status=require_ok_status_filter,
                require_above_150dma=require_above_150dma_filter,
                hide_profit_locker_warning=hide_profit_locker_filter,
                require_positive_margin_of_safety=require_positive_margin_filter,
                require_institutional_accumulation=require_institutional_accumulation_filter,
            )

            filtered_scan_df = sort_watchlist_results(
                filtered_scan_df,
                sort_option=sort_option,
                ascending=ascending_sort,
            )

            result_metric_col1, result_metric_col2, result_metric_col3 = st.columns(3)

            result_metric_col1.metric(
                "Total Scan Rows",
                len(scan_results_df),
            )

            result_metric_col2.metric(
                "Filtered Rows",
                len(filtered_scan_df),
            )

            if not filtered_scan_df.empty and "final_score" in filtered_scan_df.columns:
                top_score = pd.to_numeric(
                    filtered_scan_df["final_score"],
                    errors="coerce",
                ).max()
            else:
                top_score = 0

            result_metric_col3.metric(
                "Top Final Score",
                f"{top_score:.0f}",
            )

            preferred_columns = get_watchlist_display_columns()

            available_columns = [
                column
                for column in preferred_columns
                if column in filtered_scan_df.columns
            ]

            display_df = filtered_scan_df[available_columns].copy()

            st.markdown("### Top Ideas Table")

            if display_df.empty:
                st.warning("No stocks match the current filters.")
            else:
                st.dataframe(
                    display_df,
                    width="stretch",
                    hide_index=True,
                )

            filtered_csv = filtered_scan_df.to_csv(index=False)

            st.download_button(
                label="Download Filtered Results as CSV",
                data=filtered_csv,
                file_name="filtered_watchlist_results.csv",
                mime="text/csv",
                key="download_filtered_watchlist_results_csv",
            )

            full_csv = scan_results_df.to_csv(index=False)

            st.download_button(
                label="Download Full Watchlist Scan as CSV",
                data=full_csv,
                file_name="full_watchlist_scan.csv",
                mime="text/csv",
                key="download_full_watchlist_scan_csv",
            )
            st.markdown("---")
            st.subheader("Watchlist Visual Dashboard")

            chart_tab1, chart_tab2, chart_tab3, chart_tab4 = st.tabs(
                [
                    "Top Final Scores",
                    "Score Breakdown",
                    "150DMA Risk Map",
                    "Institutional Flow",
                ]
            )

            with chart_tab1:
                st.plotly_chart(
                    build_top_final_score_chart(filtered_scan_df),
                    width="stretch",
                )

            with chart_tab2:
                st.plotly_chart(
                    build_score_breakdown_chart(filtered_scan_df),
                    width="stretch",
                )

            with chart_tab3:
                st.plotly_chart(
                    build_150dma_risk_scatter(filtered_scan_df),
                    width="stretch",
                )

            with chart_tab4:
                st.plotly_chart(
                    build_institutional_flow_chart(filtered_scan_df),
                    width="stretch",
                )
            st.markdown("---")
            st.subheader("Profit Locker + Alert Dashboard")

            alert_df = build_watchlist_alerts(filtered_scan_df)
            alert_summary = build_alert_summary(alert_df)

            alert_col1, alert_col2, alert_col3, alert_col4, alert_col5 = st.columns(5)

            alert_col1.metric(
                "Total Alerts",
                alert_summary["total_alerts"],
            )

            alert_col2.metric(
                "Critical",
                alert_summary["critical_alerts"],
            )

            alert_col3.metric(
                "Warnings",
                alert_summary["warning_alerts"],
            )

            alert_col4.metric(
                "Cautions",
                alert_summary["caution_alerts"],
            )

            alert_col5.metric(
                "Positive Setups",
                alert_summary["positive_alerts"],
            )

            alert_tabs = st.tabs(
                [
                    "Alert Table",
                    "Alert Severity Chart",
                    "Profit Locker Distance",
                ]
            )

            with alert_tabs[0]:
                if alert_df.empty:
                    st.success("No alerts triggered under the current filters.")
                else:
                    st.dataframe(
                        alert_df,
                        width="stretch",
                        hide_index=True,
                    )

                    alert_csv = alert_df.to_csv(index=False)

                    st.download_button(
                        label="Download Alert Table as CSV",
                        data=alert_csv,
                        file_name="watchlist_alerts.csv",
                        mime="text/csv",
                        key="download_watchlist_alerts_csv",
                    )

            with alert_tabs[1]:
                st.plotly_chart(
                    build_alert_severity_chart(alert_df),
                    width="stretch",
                )

            with alert_tabs[2]:
                st.plotly_chart(
                    build_profit_locker_distance_chart(filtered_scan_df),
                    width="stretch",
                )

            st.markdown("---")
            st.subheader("Watchlist Thesis Reports")

            thesis_col1, thesis_col2 = st.columns(2)

            max_watchlist_theses = thesis_col1.number_input(
                "Maximum watchlist theses to include",
                min_value=1,
                max_value=max(1, len(filtered_scan_df)),
                value=min(10, max(1, len(filtered_scan_df))),
                step=1,
                key="max_watchlist_theses",
            )

            thesis_source_choice = thesis_col2.selectbox(
                "Watchlist thesis source",
                ["Filtered Results", "Full Scan Results"],
                index=0,
                key="watchlist_thesis_source_choice",
            )

            if thesis_source_choice == "Filtered Results":
                thesis_source_df = filtered_scan_df
            else:
                thesis_source_df = scan_results_df

            thesis_summary_df = build_thesis_summary_table(thesis_source_df)

            st.markdown("### Thesis Summary Table")

            if thesis_summary_df.empty:
                st.warning("No thesis summary data available.")
            else:
                st.dataframe(
                    thesis_summary_df,
                    width="stretch",
                    hide_index=True,
                )

            watchlist_thesis_report = build_batch_thesis_report(
                df=thesis_source_df,
                report_title="Watchlist Thesis Report",
                source_label=thesis_source_choice,
                max_reports=int(max_watchlist_theses),
            )

            with st.expander("Preview Watchlist Thesis Report", expanded=False):
                st.markdown(watchlist_thesis_report)

            st.download_button(
                label="Download Watchlist Thesis Report",
                data=watchlist_thesis_report,
                file_name="watchlist_thesis_report.md",
                mime="text/markdown",
                key="download_watchlist_thesis_report",
            )


# -----------------------------
# Score History
# -----------------------------
# -----------------------------
# Score History
# -----------------------------
elif mode == "Score History":
    st.subheader("Score History")

    st.write(
        "This page shows both the older watchlist scan history and the newer Full Evaluator scan history."
    )

    history_tabs = st.tabs(
        [
            "Full Evaluator Latest Scan",
            "Full Evaluator History",
            "Legacy Scanner History",
        ]
    )

    with history_tabs[0]:
        st.subheader("Latest Full Evaluator Scan")

        latest_full_scan_df = get_cached_latest_full_scan()

        if latest_full_scan_df.empty:
            st.warning(
                "No full evaluator scan history found yet. Run Watchlist Scanner 2.0 first."
            )
        else:
            st.dataframe(
                latest_full_scan_df,
                width="stretch",
                hide_index=True,
            )

            csv = latest_full_scan_df.to_csv(index=False)

            st.download_button(
                label="Download Latest Full Evaluator Scan as CSV",
                data=csv,
                file_name="latest_full_evaluator_scan.csv",
                mime="text/csv",
                key="download_latest_full_evaluator_scan_csv",
            )

    with history_tabs[1]:
        st.subheader("Full Evaluator Scan History")

        full_history_df = get_cached_full_scan_history()

        if full_history_df.empty:
            st.warning(
                "No full evaluator scan history found yet. Run Watchlist Scanner 2.0 first."
            )
        else:
            st.dataframe(
                full_history_df,
                width="stretch",
                hide_index=True,
            )

            csv = full_history_df.to_csv(index=False)

            st.download_button(
                label="Download Full Evaluator History as CSV",
                data=csv,
                file_name="full_evaluator_scan_history.csv",
                mime="text/csv",
                key="download_full_evaluator_history_csv",
            )

    with history_tabs[2]:
        st.subheader("Legacy Scanner History")

        st.write("This shows older watchlist scans saved inside data/stocks.db.")

        history_choice = st.radio(
            "Choose legacy history view",
            ["Latest Scan", "Full History"],
            horizontal=True,
            key="legacy_history_choice",
        )

        if history_choice == "Latest Scan":
            history_df = get_cached_latest_scan()
        else:
            history_df = get_cached_scan_history()

        if history_df.empty:
            st.warning("No legacy scan history found yet.")
        else:
            st.dataframe(
                history_df,
                width="stretch",
                hide_index=True,
            )

            csv = history_df.to_csv(index=False)

            st.download_button(
                label="Download Legacy History as CSV",
                data=csv,
                file_name="legacy_scan_history.csv",
                mime="text/csv",
                key="download_legacy_scan_history_csv",
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

    st.markdown("### Holdings Data Source")

    data_source = st.selectbox(
        "Choose holdings data source",
        ["Sample CSV", "SEC 13F Free", "FMP Live API"],
        key="institutional_data_source",
    )

    holdings_df = pd.DataFrame()

    if data_source == "Sample CSV":
        holdings_df = get_cached_institution_holdings_sample()

    elif data_source == "SEC 13F Free":
        st.info(
            "SEC 13F Free mode pulls official EDGAR 13F filings, parses the XML information table, "
            "maps CUSIPs to tickers/sectors using data/sec_13f_cusip_sector_map.csv, and feeds the same heat maps."
        )

        sec_manager_limit_input = st.number_input(
            "Number of SEC 13F managers to scan",
            min_value=1,
            max_value=15,
            value=5,
            step=1,
            key="sec_13f_manager_limit_input",
        )

        if st.button("Load SEC 13F Holdings", key="load_sec_13f_holdings"):
            with st.spinner("Loading SEC 13F filings from EDGAR..."):
                sec_df = get_cached_sec_13f_holdings(
                    manager_limit=int(sec_manager_limit_input)
                )

                st.session_state["sec_13f_holdings_df"] = sec_df

        holdings_df = st.session_state.get(
            "sec_13f_holdings_df",
            pd.DataFrame(),
        )

        if holdings_df.empty:
            st.warning(
                "No SEC 13F holdings loaded yet. Click Load SEC 13F Holdings. "
                "If it still returns empty, you may need to expand data/sec_13f_cusip_sector_map.csv with more CUSIPs."
            )

    elif data_source == "FMP Live API":
        try:
            fmp_key_from_env = st.secrets.get("FMP_API_KEY", "")
        except Exception:
            fmp_key_from_env = ""

        fmp_api_key_input = st.text_input(
            "FMP API Key",
            value=fmp_key_from_env,
            type="password",
            key="fmp_api_key_input",
        )

        fmp_report_date_input = st.text_input(
            "13F Report Date",
            value="2026-03-31",
            key="fmp_report_date_input",
        )

        fmp_page_limit_input = st.number_input(
            "FMP Pages Per Ticker",
            min_value=1,
            max_value=5,
            value=1,
            step=1,
            key="fmp_page_limit_input",
        )

        if st.button(
            "Load FMP Live Institutional Holdings", key="load_fmp_live_holdings"
        ):
            with st.spinner("Loading live institutional holdings from FMP..."):
                live_df = get_cached_live_institution_holdings(
                    api_key=fmp_api_key_input,
                    report_date=fmp_report_date_input,
                    page_limit=int(fmp_page_limit_input),
                )

                st.session_state["live_institutional_holdings_df"] = live_df

        holdings_df = st.session_state.get(
            "live_institutional_holdings_df",
            pd.DataFrame(),
        )

        if holdings_df.empty:
            st.warning(
                "No live FMP institutional data loaded. Your FMP key may be valid, but the institutional ownership / 13F endpoint "
                "may be restricted under your current subscription. Use Sample CSV for now, or upgrade to a plan that includes "
                "institutional ownership data. The SEC 13F connector is the free official-data path."
            )

    merged_holdings_df = merge_holdings_with_universe(
        holdings_df=holdings_df,
        universe_df=institution_df,
    )

    if institution_df.empty:
        st.error("No institution universe found. Check data/smart_money_universe.csv.")
    else:
        universe_summary = build_institution_summary(institution_df)

        u1, u2, u3, u4, u5 = st.columns(5)

        u1.metric(
            "Institutions Tracked",
            universe_summary["institution_count"],
        )

        u2.metric(
            "Total Assets / AUM",
            f"${universe_summary['total_assets_or_aum']:.2f}T",
        )

        u3.metric(
            "High Trackability",
            universe_summary["high_trackability_count"],
        )

        u4.metric(
            "Banks",
            universe_summary["bank_count"],
        )

        u5.metric(
            "PE / Alt / Hedge",
            universe_summary["alt_manager_count"]
            + universe_summary["hedge_fund_count"],
        )

    institutional_score_summary = build_institutional_smart_money_summary(
        merged_holdings_df
    )

    if merged_holdings_df.empty:
        st.warning("No holdings data found.")
    else:
        holdings_summary = build_holdings_summary(merged_holdings_df)

        h1, h2, h3, h4, h5 = st.columns(5)

        h1.metric(
            "Tracked Holding Rows",
            holdings_summary["holding_count"],
        )

        h2.metric(
            "Institutions With Holdings",
            holdings_summary["institution_count"],
        )

        h3.metric(
            "Sectors Tracked",
            holdings_summary["sector_count"],
        )

        h4.metric(
            "Market Value",
            f"${holdings_summary['total_market_value']:.2f}B",
        )

        h5.metric(
            "Net QoQ Flow",
            f"{holdings_summary['net_qoq_change']:.2f}%",
        )

        st.subheader("Institutional Smart Money Score")

        score_col1, score_col2, score_col3, score_col4 = st.columns(4)

        score_col1.metric(
            "Institutional Score",
            f"{institutional_score_summary.get('institutional_smart_money_score', 0)}/5",
        )

        score_col2.metric(
            "Institutional Label",
            institutional_score_summary.get("institutional_smart_money_label", "N/A"),
        )

        score_col3.metric(
            "Accumulating",
            institutional_score_summary.get("accumulating_count", 0),
        )

        score_col4.metric(
            "Reducing",
            institutional_score_summary.get("reducing_count", 0),
        )

    heatmap_tabs = st.tabs(
        [
            "Universe Heat Map",
            "Institution → Sector",
            "Sector → Institution",
            "Holdings Table",
            "Smart Money Score",
            "6B-6 API Connector",
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
            trackability_options = sorted(
                institution_df["trackability"].unique().tolist()
            )
            country_options = sorted(institution_df["country"].unique().tolist())

            filter_col1, filter_col2, filter_col3 = st.columns(3)

            selected_types = filter_col1.multiselect(
                "Filter by institution type",
                type_options,
                default=type_options,
                key="universe_type_filter",
            )

            selected_trackability = filter_col2.multiselect(
                "Filter by trackability",
                trackability_options,
                default=trackability_options,
                key="universe_trackability_filter",
            )

            selected_countries = filter_col3.multiselect(
                "Filter by country",
                country_options,
                default=country_options,
                key="universe_country_filter",
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
                hide_index=True,
            )

    with heatmap_tabs[1]:
        st.subheader("Institution → Sector Exposure")

        st.write(
            "Box size = reported market value. "
            "Color = weighted QoQ position change. "
            "Hover over tiles to see top holdings, exposure %, QoQ change, and flow details."
        )

        if merged_holdings_df.empty:
            st.warning("No holdings data available.")
        else:
            institution_options = sorted(
                merged_holdings_df["institution"].unique().tolist()
            )

            sector_options = sorted(merged_holdings_df["sector"].unique().tolist())

            inst_filter_col, sector_filter_col = st.columns(2)

            selected_institutions = inst_filter_col.multiselect(
                "Filter institutions",
                institution_options,
                default=institution_options,
                key="institution_sector_institution_filter",
            )

            selected_sectors = sector_filter_col.multiselect(
                "Filter sectors",
                sector_options,
                default=sector_options,
                key="institution_sector_sector_filter",
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
            "This view answers which sectors are attracting institutional money. "
            "Hover over tiles to see top holdings, sector exposure %, QoQ change, and flow details."
        )

        if merged_holdings_df.empty:
            st.warning("No holdings data available.")
        else:
            sector_options = sorted(merged_holdings_df["sector"].unique().tolist())

            institution_options = sorted(
                merged_holdings_df["institution"].unique().tolist()
            )

            sector_filter_col, inst_filter_col = st.columns(2)

            selected_sectors = sector_filter_col.multiselect(
                "Filter sectors",
                sector_options,
                default=sector_options,
                key="sector_institution_sector_filter",
            )

            selected_institutions = inst_filter_col.multiselect(
                "Filter institutions",
                institution_options,
                default=institution_options,
                key="sector_institution_institution_filter",
            )

            filtered_holdings_df = merged_holdings_df[
                merged_holdings_df["sector"].isin(selected_sectors)
                & merged_holdings_df["institution"].isin(selected_institutions)
            ]

            fig = build_sector_institution_treemap(filtered_holdings_df)

            st.plotly_chart(fig, width="stretch")

    with heatmap_tabs[3]:
        st.subheader("Holdings Table")

        st.write("This is the holdings data powering the sector heat maps.")

        if merged_holdings_df.empty:
            st.warning("No holdings data available.")
        else:
            holdings_table = prepare_holdings_table(merged_holdings_df)

            st.dataframe(
                holdings_table,
                width="stretch",
                hide_index=True,
            )

            csv = holdings_table.to_csv(index=False)

            st.download_button(
                label="Download Holdings Table as CSV",
                data=csv,
                file_name="institution_holdings.csv",
                mime="text/csv",
                key="download_institution_holdings_csv",
            )

    with heatmap_tabs[4]:
        st.subheader("Institutional Smart Money Score")

        st.write(
            "This score converts institutional accumulation/reduction into a -5 to +5 Smart Money Score."
        )

        st.table(
            build_institutional_score_table(institutional_score_summary).astype(str)
        )

        flow_tables = build_top_flow_tables(merged_holdings_df)

        flow_col1, flow_col2 = st.columns(2)

        with flow_col1:
            st.subheader("Top Accumulating Sectors")
            st.dataframe(
                flow_tables["top_accumulating_sectors"],
                width="stretch",
                hide_index=True,
            )

            st.subheader("Top Accumulating Institutions")
            st.dataframe(
                flow_tables["top_accumulating_institutions"],
                width="stretch",
                hide_index=True,
            )

        with flow_col2:
            st.subheader("Top Reducing Sectors")
            st.dataframe(
                flow_tables["top_reducing_sectors"],
                width="stretch",
                hide_index=True,
            )

            st.subheader("Top Reducing Institutions")
            st.dataframe(
                flow_tables["top_reducing_institutions"],
                width="stretch",
                hide_index=True,
            )

    with heatmap_tabs[5]:
        st.subheader("6B-6 API Connector")

        st.write(
            "This tab shows which connector is currently being used and whether data is actually flowing into the heat maps."
        )

        connector_col1, connector_col2, connector_col3, connector_col4 = st.columns(4)

        connector_col1.metric(
            "Current Source",
            data_source,
        )

        connector_col2.metric(
            "Holdings Rows",
            len(holdings_df),
        )

        connector_col3.metric(
            "Merged Rows",
            len(merged_holdings_df),
        )

        connector_col4.metric(
            "Institutions Matched",
            (
                0
                if merged_holdings_df.empty
                else merged_holdings_df["institution"].nunique()
            ),
        )

        st.markdown("---")

        if data_source == "Sample CSV":
            st.success(
                "Sample CSV mode is active. Data is coming from data/institution_holdings_sample.csv."
            )

        elif data_source == "SEC 13F Free":
            st.success(
                "SEC 13F Free mode is active. Data is being pulled from official SEC EDGAR filings, "
                "then mapped through data/sec_13f_cusip_sector_map.csv."
            )

            st.info(
                "If the SEC data looks too large, too small, or incomplete, the next fix is to improve the SEC parser "
                "and expand the CUSIP-to-sector mapping file."
            )

        elif data_source == "FMP Live API":
            st.warning(
                "FMP Live API mode requires an FMP subscription that includes institutional ownership / 13F endpoints. "
                "If your plan does not include it, this connector will return no holdings."
            )

        st.markdown("### Connector Output Preview")

        if merged_holdings_df.empty:
            st.warning("No connector data is currently available.")
        else:
            preview_columns = [
                "institution",
                "sector",
                "ticker",
                "company",
                "market_value_billions",
                "position_change_qoq_pct",
                "shares_change_qoq_pct",
                "flow_status",
                "report_date",
            ]

            available_columns = [
                column
                for column in preview_columns
                if column in merged_holdings_df.columns
            ]

            st.dataframe(
                merged_holdings_df[available_columns].head(50),
                width="stretch",
                hide_index=True,
            )

        st.markdown("### Connector Roadmap")

        st.code(
            """
Current connector flow:

1. Sample CSV uses data/institution_holdings_sample.csv.
2. SEC 13F Free pulls official EDGAR 13F filings and maps CUSIPs to sectors.
3. FMP Live API requires a paid plan that includes institutional ownership / 13F endpoints.
4. All sources are normalized into the same heat map format.

Next upgrades:
- Fix SEC value scaling if market values look unrealistic
- Add more CUSIPs to data/sec_13f_cusip_sector_map.csv
- Add a ticker-level institutional score
- Feed institutional flow into the Final Evaluator Score
            """,
            language="text",
        )

# -----------------------------
# Portfolio Dashboard
# -----------------------------
elif mode == "Portfolio":
    st.subheader("Portfolio Dashboard")

    st.write(
        "This section evaluates your current portfolio using the full stock evaluator engine."
    )

    positions_df = get_cached_portfolio_positions()

    if positions_df.empty:
        st.error("No portfolio positions found. Check data/portfolio.csv.")
    else:
        st.success(
            f"Loaded {len(positions_df)} portfolio positions from data/portfolio.csv."
        )

        st.dataframe(
            positions_df,
            width="stretch",
            hide_index=True,
        )

        with st.expander("Portfolio Valuation Assumptions", expanded=False):
            portfolio_dcf_growth_rate = st.number_input(
                "DCF FCF Growth Rate (%)",
                min_value=-50.0,
                max_value=100.0,
                value=DEFAULT_VALUATION_ASSUMPTIONS["dcf_growth_rate"] * 100,
                step=1.0,
                key="portfolio_dcf_growth_rate",
            )

            portfolio_discount_rate = st.number_input(
                "Discount Rate / Required Return (%)",
                min_value=1.0,
                max_value=50.0,
                value=DEFAULT_VALUATION_ASSUMPTIONS["discount_rate"] * 100,
                step=0.5,
                key="portfolio_discount_rate",
            )

            portfolio_terminal_growth_rate = st.number_input(
                "Terminal Growth Rate (%)",
                min_value=0.0,
                max_value=10.0,
                value=DEFAULT_VALUATION_ASSUMPTIONS["terminal_growth_rate"] * 100,
                step=0.25,
                key="portfolio_terminal_growth_rate",
            )

            portfolio_future_pe = st.number_input(
                "Future P/E Multiple",
                min_value=1.0,
                max_value=100.0,
                value=float(DEFAULT_VALUATION_ASSUMPTIONS["future_pe"]),
                step=1.0,
                key="portfolio_future_pe",
            )

        portfolio_valuation_assumptions = {
            "dcf_growth_rate": portfolio_dcf_growth_rate / 100,
            "discount_rate": portfolio_discount_rate / 100,
            "terminal_growth_rate": portfolio_terminal_growth_rate / 100,
            "dcf_years": 5,
            "eps_growth_rate": portfolio_dcf_growth_rate / 100,
            "future_pe": portfolio_future_pe,
            "eps_years": 5,
        }

        manual_portfolio_smart_money_score = st.number_input(
            "Manual Smart Money Score for Portfolio (-5 to +5)",
            min_value=-5.0,
            max_value=5.0,
            value=0.0,
            step=0.5,
            key="manual_portfolio_smart_money_score",
        )

        institutional_holdings_for_portfolio = (
            get_active_institutional_holdings_for_scoring()
        )

        if st.button("Evaluate Portfolio", key="evaluate_portfolio_button"):
            with st.spinner("Evaluating portfolio positions..."):
                portfolio_tickers = positions_df["ticker"].tolist()

                portfolio_evaluator_df = evaluate_full_watchlist(
                    tickers=portfolio_tickers,
                    institutional_holdings_df=institutional_holdings_for_portfolio,
                    manual_smart_money_score=manual_portfolio_smart_money_score,
                    valuation_assumptions=portfolio_valuation_assumptions,
                )

                portfolio_dashboard_df = build_portfolio_dashboard(
                    positions_df=positions_df,
                    evaluator_df=portfolio_evaluator_df,
                )

                st.session_state["portfolio_dashboard_df"] = portfolio_dashboard_df

        portfolio_dashboard_df = st.session_state.get(
            "portfolio_dashboard_df",
            pd.DataFrame(),
        )

        if portfolio_dashboard_df.empty:
            st.info(
                "Click Evaluate Portfolio to calculate portfolio value, risk, and scores."
            )
        else:
            portfolio_summary = build_portfolio_summary(portfolio_dashboard_df)

            p1, p2, p3, p4, p5 = st.columns(5)

            p1.metric(
                "Holdings",
                portfolio_summary["holding_count"],
            )

            p2.metric(
                "Market Value",
                format_money(portfolio_summary["total_market_value"]),
            )

            p3.metric(
                "Cost Basis",
                format_money(portfolio_summary["total_cost_basis"]),
            )

            p4.metric(
                "Unrealized Gain/Loss",
                format_money(portfolio_summary["total_unrealized_gain_loss"]),
                delta=f"{portfolio_summary['total_unrealized_gain_loss_pct']:.2f}%",
            )

            p5.metric(
                "Weighted Final Score",
                f"{portfolio_summary['weighted_final_score']:.0f}/100",
            )

            st.warning(
                f"Profit Locker / caution positions: {portfolio_summary['profit_locker_count']}"
            )

            display_columns = [
                column
                for column in get_portfolio_display_columns()
                if column in portfolio_dashboard_df.columns
            ]

            st.subheader("Portfolio Holdings Evaluation")

            st.dataframe(
                portfolio_dashboard_df[display_columns],
                width="stretch",
                hide_index=True,
            )

            csv = portfolio_dashboard_df.to_csv(index=False)

            st.download_button(
                label="Download Portfolio Evaluation as CSV",
                data=csv,
                file_name="portfolio_evaluation.csv",
                mime="text/csv",
                key="download_portfolio_evaluation_csv",
            )
            st.markdown("---")
            st.subheader("Portfolio Visual Dashboard")

            portfolio_risk_summary = build_portfolio_risk_summary(
                portfolio_dashboard_df
            )

            risk_col1, risk_col2, risk_col3, risk_col4 = st.columns(4)

            risk_col1.metric(
                "Highest Weight Holding",
                portfolio_risk_summary["highest_weight_ticker"],
                delta=f"{portfolio_risk_summary['highest_weight_pct']:.2f}%",
            )

            risk_col2.metric(
                "Lowest Score Holding",
                portfolio_risk_summary["lowest_score_ticker"],
                delta=f"{portfolio_risk_summary['lowest_score']:.0f}/100",
            )

            risk_col3.metric(
                "Profit Locker Positions",
                portfolio_risk_summary["profit_locker_positions"],
            )

            risk_col4.metric(
                "Below 150DMA Positions",
                portfolio_risk_summary["below_150dma_positions"],
            )

            portfolio_visual_tabs = st.tabs(
                [
                    "Allocation",
                    "Value vs Cost",
                    "Gain/Loss",
                    "Score vs Weight",
                    "Profit Locker Table",
                ]
            )

            with portfolio_visual_tabs[0]:
                st.plotly_chart(
                    build_portfolio_allocation_pie(portfolio_dashboard_df),
                    width="stretch",
                )

            with portfolio_visual_tabs[1]:
                st.plotly_chart(
                    build_portfolio_value_bar(portfolio_dashboard_df),
                    width="stretch",
                )

            with portfolio_visual_tabs[2]:
                st.plotly_chart(
                    build_portfolio_gain_loss_chart(portfolio_dashboard_df),
                    width="stretch",
                )

            with portfolio_visual_tabs[3]:
                st.plotly_chart(
                    build_portfolio_score_weight_scatter(portfolio_dashboard_df),
                    width="stretch",
                )

            with portfolio_visual_tabs[4]:
                profit_locker_table = build_portfolio_profit_locker_table(
                    portfolio_dashboard_df
                )

                if profit_locker_table.empty:
                    st.success(
                        "No portfolio holdings are currently in the Profit Locker / caution zone."
                    )
                else:
                    st.warning(
                        "These holdings may need trimming, review, or tighter risk management."
                    )

                    st.dataframe(
                        profit_locker_table,
                        width="stretch",
                        hide_index=True,
                    )

            st.markdown("---")
            st.subheader("Portfolio Rebalance Plan")

            targets_df = get_cached_portfolio_targets()

            if targets_df.empty:
                st.warning(
                    "No target allocation file found. Check data/portfolio_targets.csv."
                )
            else:
                rebalance_df = build_rebalance_plan(
                    portfolio_df=portfolio_dashboard_df,
                    targets_df=targets_df,
                )

                rebalance_summary = build_rebalance_summary(rebalance_df)

                rb1, rb2, rb3, rb4 = st.columns(4)

                rb1.metric(
                    "Add Candidates",
                    rebalance_summary["add_candidates"],
                )

                rb2.metric(
                    "Trim Candidates",
                    rebalance_summary["trim_candidates"],
                )

                rb3.metric(
                    "Profit Locker Candidates",
                    rebalance_summary["profit_locker_candidates"],
                )

                rb4.metric(
                    "Review Candidates",
                    rebalance_summary["review_candidates"],
                )

                display_columns = [
                    column
                    for column in get_rebalance_display_columns()
                    if column in rebalance_df.columns
                ]

                st.dataframe(
                    rebalance_df[display_columns],
                    width="stretch",
                    hide_index=True,
                )

                rebalance_csv = rebalance_df.to_csv(index=False)

                st.download_button(
                    label="Download Rebalance Plan as CSV",
                    data=rebalance_csv,
                    file_name="portfolio_rebalance_plan.csv",
                    mime="text/csv",
                    key="download_portfolio_rebalance_plan_csv",
                )

            st.markdown("---")
            st.subheader("Portfolio Thesis Reports")

            max_portfolio_theses = st.number_input(
                "Maximum portfolio theses to include",
                min_value=1,
                max_value=max(1, len(portfolio_dashboard_df)),
                value=min(10, max(1, len(portfolio_dashboard_df))),
                step=1,
                key="max_portfolio_theses",
            )

            portfolio_thesis_summary_df = build_thesis_summary_table(
                portfolio_dashboard_df
            )

            st.markdown("### Portfolio Thesis Summary Table")

            if portfolio_thesis_summary_df.empty:
                st.warning("No portfolio thesis summary data available.")
            else:
                st.dataframe(
                    portfolio_thesis_summary_df,
                    width="stretch",
                    hide_index=True,
                )

            portfolio_thesis_report = build_batch_thesis_report(
                df=portfolio_dashboard_df,
                report_title="Portfolio Thesis Report",
                source_label="Portfolio",
                max_reports=int(max_portfolio_theses),
            )

            with st.expander("Preview Portfolio Thesis Report", expanded=False):
                st.markdown(portfolio_thesis_report)

            st.download_button(
                label="Download Portfolio Thesis Report",
                data=portfolio_thesis_report,
                file_name="portfolio_thesis_report.md",
                mime="text/markdown",
                key="download_portfolio_thesis_report",
            )
