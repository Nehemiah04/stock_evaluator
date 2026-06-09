import pandas as pd
import plotly.graph_objects as go


def safe_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([0] * len(df))

    return pd.to_numeric(df[column], errors="coerce").fillna(0)


def build_portfolio_allocation_pie(df: pd.DataFrame):
    if df is None or df.empty:
        return go.Figure()

    if "ticker" not in df.columns or "market_value" not in df.columns:
        return go.Figure()

    chart_df = df.copy()
    chart_df["market_value"] = safe_numeric(chart_df, "market_value")

    fig = go.Figure()

    fig.add_trace(
        go.Pie(
            labels=chart_df["ticker"],
            values=chart_df["market_value"],
            hole=0.35,
            textinfo="label+percent",
        )
    )

    fig.update_layout(
        title="Portfolio Allocation by Market Value",
        height=550,
    )

    return fig


def build_portfolio_value_bar(df: pd.DataFrame):
    if df is None or df.empty:
        return go.Figure()

    required_columns = ["ticker", "market_value", "cost_basis"]

    if any(column not in df.columns for column in required_columns):
        return go.Figure()

    chart_df = df.copy()
    chart_df["market_value"] = safe_numeric(chart_df, "market_value")
    chart_df["cost_basis"] = safe_numeric(chart_df, "cost_basis")

    chart_df = chart_df.sort_values(
        by="market_value",
        ascending=False,
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=chart_df["ticker"],
            y=chart_df["market_value"],
            name="Market Value",
        )
    )

    fig.add_trace(
        go.Bar(
            x=chart_df["ticker"],
            y=chart_df["cost_basis"],
            name="Cost Basis",
        )
    )

    fig.update_layout(
        title="Market Value vs Cost Basis",
        xaxis_title="Ticker",
        yaxis_title="Dollars",
        barmode="group",
        height=550,
    )

    return fig


def build_portfolio_gain_loss_chart(df: pd.DataFrame):
    if df is None or df.empty:
        return go.Figure()

    required_columns = ["ticker", "unrealized_gain_loss", "unrealized_gain_loss_pct"]

    if any(column not in df.columns for column in required_columns):
        return go.Figure()

    chart_df = df.copy()
    chart_df["unrealized_gain_loss"] = safe_numeric(chart_df, "unrealized_gain_loss")
    chart_df["unrealized_gain_loss_pct"] = safe_numeric(
        chart_df, "unrealized_gain_loss_pct"
    )

    chart_df = chart_df.sort_values(
        by="unrealized_gain_loss",
        ascending=False,
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=chart_df["ticker"],
            y=chart_df["unrealized_gain_loss"],
            text=chart_df["unrealized_gain_loss_pct"].round(2).astype(str) + "%",
            textposition="outside",
            name="Unrealized Gain/Loss",
        )
    )

    fig.update_layout(
        title="Unrealized Gain/Loss by Holding",
        xaxis_title="Ticker",
        yaxis_title="Unrealized Gain/Loss ($)",
        height=550,
    )

    return fig


def build_portfolio_score_weight_scatter(df: pd.DataFrame):
    if df is None or df.empty:
        return go.Figure()

    required_columns = [
        "ticker",
        "portfolio_weight_pct",
        "final_score",
        "unrealized_gain_loss_pct",
    ]

    if any(column not in df.columns for column in required_columns):
        return go.Figure()

    chart_df = df.copy()
    chart_df["portfolio_weight_pct"] = safe_numeric(chart_df, "portfolio_weight_pct")
    chart_df["final_score"] = safe_numeric(chart_df, "final_score")
    chart_df["unrealized_gain_loss_pct"] = safe_numeric(
        chart_df, "unrealized_gain_loss_pct"
    )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=chart_df["portfolio_weight_pct"],
            y=chart_df["final_score"],
            mode="markers+text",
            text=chart_df["ticker"],
            textposition="top center",
            marker=dict(
                size=(chart_df["portfolio_weight_pct"] + 2) * 3,
            ),
            customdata=chart_df[
                [
                    "ticker",
                    "portfolio_weight_pct",
                    "final_score",
                    "unrealized_gain_loss_pct",
                ]
            ],
            hovertemplate=(
                "Ticker: %{customdata[0]}<br>"
                "Portfolio Weight: %{customdata[1]:.2f}%<br>"
                "Final Score: %{customdata[2]:.0f}/100<br>"
                "Gain/Loss: %{customdata[3]:.2f}%"
                "<extra></extra>"
            ),
            name="Holdings",
        )
    )

    fig.add_hline(
        y=75,
        line_dash="dash",
        annotation_text="High Score Zone",
    )

    fig.update_layout(
        title="Portfolio Weight vs Final Score",
        xaxis_title="Portfolio Weight (%)",
        yaxis_title="Final Score",
        height=650,
        yaxis=dict(range=[0, 100]),
    )

    return fig


def build_portfolio_profit_locker_table(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    if "profit_locker_status" not in df.columns:
        return pd.DataFrame()

    table_df = df.copy()

    table_df["profit_locker_status"] = table_df["profit_locker_status"].astype(str)

    risk_df = table_df[
        table_df["profit_locker_status"]
        .str.lower()
        .str.contains("locker|caution|warning|extended", na=False)
    ]

    preferred_columns = [
        "ticker",
        "current_price",
        "dma_150",
        "distance_from_150dma",
        "profit_locker_status",
        "portfolio_weight_pct",
        "market_value",
        "final_score",
        "final_action",
    ]

    available_columns = [
        column for column in preferred_columns if column in risk_df.columns
    ]

    return risk_df[available_columns].copy()


def build_portfolio_risk_summary(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "highest_weight_ticker": "N/A",
            "highest_weight_pct": 0,
            "lowest_score_ticker": "N/A",
            "lowest_score": 0,
            "profit_locker_positions": 0,
            "below_150dma_positions": 0,
        }

    working_df = df.copy()

    working_df["portfolio_weight_pct"] = safe_numeric(
        working_df, "portfolio_weight_pct"
    )
    working_df["final_score"] = safe_numeric(working_df, "final_score")
    working_df["distance_from_150dma"] = safe_numeric(
        working_df, "distance_from_150dma"
    )

    if "ticker" not in working_df.columns:
        working_df["ticker"] = "N/A"

    highest_weight_row = working_df.sort_values(
        by="portfolio_weight_pct",
        ascending=False,
    ).iloc[0]

    lowest_score_row = working_df.sort_values(
        by="final_score",
        ascending=True,
    ).iloc[0]

    if "profit_locker_status" in working_df.columns:
        profit_locker_positions = (
            working_df["profit_locker_status"]
            .astype(str)
            .str.lower()
            .str.contains("locker|caution|warning|extended", na=False)
            .sum()
        )
    else:
        profit_locker_positions = 0

    below_150dma_positions = (working_df["distance_from_150dma"] < 0).sum()

    return {
        "highest_weight_ticker": highest_weight_row["ticker"],
        "highest_weight_pct": highest_weight_row["portfolio_weight_pct"],
        "lowest_score_ticker": lowest_score_row["ticker"],
        "lowest_score": lowest_score_row["final_score"],
        "profit_locker_positions": int(profit_locker_positions),
        "below_150dma_positions": int(below_150dma_positions),
    }
