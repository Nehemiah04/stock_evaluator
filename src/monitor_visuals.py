import pandas as pd
import plotly.graph_objects as go


def safe_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if df is None or df.empty or column not in df.columns:
        return pd.Series(dtype=float)

    return pd.to_numeric(df[column], errors="coerce").fillna(0)


def build_monitor_status_chart(df: pd.DataFrame):
    if df is None or df.empty or "monitor_status" not in df.columns:
        return go.Figure()

    counts = df["monitor_status"].astype(str).value_counts()

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=counts.index,
            y=counts.values,
            text=counts.values,
            textposition="outside",
            name="Monitor Status Count",
        )
    )

    fig.update_layout(
        title="Monitor Status Breakdown",
        xaxis_title="Monitor Status",
        yaxis_title="Count",
        height=500,
    )

    return fig


def build_score_change_chart(df: pd.DataFrame, top_n: int = 20):
    if df is None or df.empty:
        return go.Figure()

    required_columns = ["ticker", "final_score_change"]

    if any(column not in df.columns for column in required_columns):
        return go.Figure()

    chart_df = df.copy()
    chart_df["final_score_change"] = safe_numeric(chart_df, "final_score_change")
    chart_df["abs_score_change"] = chart_df["final_score_change"].abs()

    chart_df = chart_df.sort_values(
        by="abs_score_change",
        ascending=False,
    ).head(top_n)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=chart_df["ticker"],
            y=chart_df["final_score_change"],
            text=chart_df["final_score_change"].round(2),
            textposition="outside",
            name="Final Score Change",
        )
    )

    fig.add_hline(
        y=5,
        line_dash="dash",
        annotation_text="Upgrade threshold",
    )

    fig.add_hline(
        y=-5,
        line_dash="dash",
        annotation_text="Downgrade threshold",
    )

    fig.update_layout(
        title="Biggest Final Score Changes",
        xaxis_title="Ticker",
        yaxis_title="Final Score Change",
        height=550,
    )

    return fig


def build_150dma_change_scatter(df: pd.DataFrame):
    if df is None or df.empty:
        return go.Figure()

    required_columns = [
        "ticker",
        "previous_distance_from_150dma",
        "distance_from_150dma",
        "final_score",
    ]

    if any(column not in df.columns for column in required_columns):
        return go.Figure()

    chart_df = df.copy()

    chart_df["previous_distance_from_150dma"] = safe_numeric(
        chart_df,
        "previous_distance_from_150dma",
    )

    chart_df["distance_from_150dma"] = safe_numeric(
        chart_df,
        "distance_from_150dma",
    )

    chart_df["final_score"] = safe_numeric(chart_df, "final_score")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=chart_df["previous_distance_from_150dma"],
            y=chart_df["distance_from_150dma"],
            mode="markers+text",
            text=chart_df["ticker"],
            textposition="top center",
            marker=dict(
                size=(chart_df["final_score"] / 5).clip(lower=6, upper=25),
            ),
            customdata=chart_df[
                [
                    "ticker",
                    "previous_distance_from_150dma",
                    "distance_from_150dma",
                    "final_score",
                ]
            ],
            hovertemplate=(
                "Ticker: %{customdata[0]}<br>"
                "Previous Distance: %{customdata[1]:.2f}%<br>"
                "Latest Distance: %{customdata[2]:.2f}%<br>"
                "Final Score: %{customdata[3]:.0f}/100"
                "<extra></extra>"
            ),
            name="150DMA Movement",
        )
    )

    fig.add_hline(
        y=0,
        line_dash="dash",
        annotation_text="Latest 150DMA line",
    )

    fig.add_vline(
        x=0,
        line_dash="dash",
        annotation_text="Previous 150DMA line",
    )

    fig.add_hline(
        y=25,
        line_dash="dash",
        annotation_text="Latest caution zone",
    )

    fig.add_hline(
        y=35,
        line_dash="dash",
        annotation_text="Latest Profit Locker zone",
    )

    fig.update_layout(
        title="150DMA Position Change",
        xaxis_title="Previous Distance From 150DMA (%)",
        yaxis_title="Latest Distance From 150DMA (%)",
        height=650,
    )

    return fig


def build_profit_locker_change_table(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    if "profit_locker_change" not in df.columns:
        return pd.DataFrame()

    table_df = df.copy()
    profit_locker_change = table_df["profit_locker_change"].astype(str)

    table_df = table_df[
        profit_locker_change.isin(
            [
                "New Profit Locker trigger",
                "New extended/caution trigger",
                "Reset below caution zone",
            ]
        )
    ]

    preferred_columns = [
        "ticker",
        "profit_locker_change",
        "distance_from_150dma",
        "previous_distance_from_150dma",
        "distance_from_150dma_change",
        "final_score",
        "final_score_change",
        "profit_locker_status",
        "monitor_status",
    ]

    available_columns = [
        column for column in preferred_columns if column in table_df.columns
    ]

    return table_df[available_columns].copy()


def build_top_monitor_movers_table(
    df: pd.DataFrame,
    top_n: int = 20,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    if "final_score_change" not in df.columns:
        return pd.DataFrame()

    table_df = df.copy()
    table_df["final_score_change"] = safe_numeric(table_df, "final_score_change")
    table_df["abs_score_change"] = table_df["final_score_change"].abs()

    preferred_columns = [
        "ticker",
        "monitor_status",
        "final_score",
        "previous_final_score",
        "final_score_change",
        "score_change_label",
        "distance_from_150dma",
        "dma_cross_signal",
        "profit_locker_change",
    ]

    available_columns = [
        column for column in preferred_columns if column in table_df.columns
    ]

    table_df = table_df.sort_values(
        by="abs_score_change",
        ascending=False,
    ).head(top_n)

    return table_df[available_columns].copy()
