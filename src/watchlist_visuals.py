import pandas as pd
import plotly.graph_objects as go


def prepare_numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([0] * len(df))

    return pd.to_numeric(df[column], errors="coerce").fillna(0)


def build_top_final_score_chart(df: pd.DataFrame, top_n: int = 15):
    if df is None or df.empty:
        return go.Figure()

    chart_df = df.copy()

    if "ticker" not in chart_df.columns or "final_score" not in chart_df.columns:
        return go.Figure()

    chart_df["final_score"] = prepare_numeric_column(chart_df, "final_score")

    chart_df = chart_df.sort_values(
        by="final_score",
        ascending=False,
    ).head(top_n)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=chart_df["ticker"],
            y=chart_df["final_score"],
            text=chart_df["final_score"].round(0),
            textposition="outside",
            name="Final Score",
        )
    )

    fig.update_layout(
        title="Top Stocks by Final Score",
        xaxis_title="Ticker",
        yaxis_title="Final Score",
        height=500,
        yaxis=dict(range=[0, 100]),
    )

    return fig


def build_score_breakdown_chart(df: pd.DataFrame, top_n: int = 10):
    if df is None or df.empty:
        return go.Figure()

    required_columns = [
        "ticker",
        "chart_score",
        "fundamental_score",
        "valuation_score",
        "final_smart_money_score",
        "final_score",
    ]

    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]

    if missing_columns:
        return go.Figure()

    chart_df = df.copy()

    for column in required_columns:
        if column != "ticker":
            chart_df[column] = prepare_numeric_column(chart_df, column)

    chart_df = chart_df.sort_values(
        by="final_score",
        ascending=False,
    ).head(top_n)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=chart_df["ticker"],
            y=chart_df["chart_score"],
            name="Chart Score",
        )
    )

    fig.add_trace(
        go.Bar(
            x=chart_df["ticker"],
            y=chart_df["fundamental_score"],
            name="Fundamental Score",
        )
    )

    fig.add_trace(
        go.Bar(
            x=chart_df["ticker"],
            y=chart_df["valuation_score"],
            name="Valuation Score",
        )
    )

    fig.add_trace(
        go.Bar(
            x=chart_df["ticker"],
            y=chart_df["final_smart_money_score"] * 20,
            name="Smart Money Score x20",
        )
    )

    fig.update_layout(
        title="Score Breakdown by Ticker",
        xaxis_title="Ticker",
        yaxis_title="Component Score",
        barmode="group",
        height=550,
    )

    return fig


def build_150dma_risk_scatter(df: pd.DataFrame):
    if df is None or df.empty:
        return go.Figure()

    required_columns = [
        "ticker",
        "final_score",
        "distance_from_150dma",
        "institutional_smart_money_score",
    ]

    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]

    if missing_columns:
        return go.Figure()

    chart_df = df.copy()

    chart_df["final_score"] = prepare_numeric_column(chart_df, "final_score")
    chart_df["distance_from_150dma"] = prepare_numeric_column(
        chart_df, "distance_from_150dma"
    )
    chart_df["institutional_smart_money_score"] = prepare_numeric_column(
        chart_df,
        "institutional_smart_money_score",
    )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=chart_df["distance_from_150dma"],
            y=chart_df["final_score"],
            mode="markers+text",
            text=chart_df["ticker"],
            textposition="top center",
            marker=dict(
                size=(chart_df["institutional_smart_money_score"].abs() + 1) * 8,
            ),
            name="Stocks",
            customdata=chart_df[
                [
                    "ticker",
                    "final_score",
                    "distance_from_150dma",
                    "institutional_smart_money_score",
                ]
            ],
            hovertemplate=(
                "Ticker: %{customdata[0]}<br>"
                "Final Score: %{customdata[1]:.0f}<br>"
                "Distance from 150DMA: %{customdata[2]:.2f}%<br>"
                "Institutional Score: %{customdata[3]:.2f}/5"
                "<extra></extra>"
            ),
        )
    )

    fig.add_hline(
        y=75,
        line_dash="dash",
        annotation_text="High Score Zone",
    )

    fig.add_vline(
        x=25,
        line_dash="dash",
        annotation_text="Extended Zone",
    )

    fig.add_vline(
        x=35,
        line_dash="dash",
        annotation_text="Profit Locker Zone",
    )

    fig.update_layout(
        title="Final Score vs Distance From 150DMA",
        xaxis_title="Distance From 150DMA (%)",
        yaxis_title="Final Score",
        height=650,
        yaxis=dict(range=[0, 100]),
    )

    return fig


def build_institutional_flow_chart(df: pd.DataFrame, top_n: int = 15):
    if df is None or df.empty:
        return go.Figure()

    required_columns = [
        "ticker",
        "institutional_net_qoq_flow_pct",
    ]

    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]

    if missing_columns:
        return go.Figure()

    chart_df = df.copy()

    chart_df["institutional_net_qoq_flow_pct"] = prepare_numeric_column(
        chart_df,
        "institutional_net_qoq_flow_pct",
    )

    chart_df = chart_df.sort_values(
        by="institutional_net_qoq_flow_pct",
        ascending=False,
    ).head(top_n)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=chart_df["ticker"],
            y=chart_df["institutional_net_qoq_flow_pct"],
            text=chart_df["institutional_net_qoq_flow_pct"].round(2),
            textposition="outside",
            name="Institutional Net QoQ Flow %",
        )
    )

    fig.update_layout(
        title="Top Institutional Flow by Ticker",
        xaxis_title="Ticker",
        yaxis_title="Institutional Net QoQ Flow %",
        height=500,
    )

    return fig
