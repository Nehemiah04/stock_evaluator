import pandas as pd
import plotly.graph_objects as go


ALERT_COLUMNS = [
    "ticker",
    "alert_level",
    "alert_type",
    "alert_message",
    "final_score",
    "distance_from_150dma",
    "profit_locker_status",
    "valuation_score",
    "margin_of_safety",
    "institutional_smart_money_score",
    "institutional_net_qoq_flow_pct",
]


def safe_float(value, default=0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default

        return float(value)
    except Exception:
        return default


def get_alert_priority(alert_level: str) -> int:
    priority_map = {
        "Critical": 4,
        "Warning": 3,
        "Caution": 2,
        "Positive": 1,
        "Info": 0,
    }

    return priority_map.get(alert_level, 0)


def build_alert_row(
    row: pd.Series,
    alert_level: str,
    alert_type: str,
    alert_message: str,
) -> dict:
    return {
        "ticker": row.get("ticker", "N/A"),
        "alert_level": alert_level,
        "alert_type": alert_type,
        "alert_message": alert_message,
        "final_score": safe_float(row.get("final_score")),
        "distance_from_150dma": safe_float(row.get("distance_from_150dma")),
        "profit_locker_status": row.get("profit_locker_status", "N/A"),
        "valuation_score": safe_float(row.get("valuation_score")),
        "margin_of_safety": safe_float(row.get("margin_of_safety")),
        "institutional_smart_money_score": safe_float(
            row.get("institutional_smart_money_score")
        ),
        "institutional_net_qoq_flow_pct": safe_float(
            row.get("institutional_net_qoq_flow_pct")
        ),
    }


def generate_alerts_for_stock(row: pd.Series) -> list:
    alerts = []

    ticker = str(row.get("ticker", "N/A")).upper()
    final_score = safe_float(row.get("final_score"))
    distance_from_150dma = safe_float(row.get("distance_from_150dma"))
    valuation_score = safe_float(row.get("valuation_score"))
    margin_of_safety = safe_float(row.get("margin_of_safety"))
    institutional_score = safe_float(row.get("institutional_smart_money_score"))
    institutional_flow = safe_float(row.get("institutional_net_qoq_flow_pct"))
    chart_score = safe_float(row.get("chart_score"))
    fundamental_score = safe_float(row.get("fundamental_score"))

    if distance_from_150dma >= 35:
        alerts.append(
            build_alert_row(
                row,
                "Critical",
                "Profit Locker",
                f"{ticker} is {distance_from_150dma:.2f}% above the 150DMA. Consider trimming, locking profit, or waiting for a reset.",
            )
        )

    elif distance_from_150dma >= 25:
        alerts.append(
            build_alert_row(
                row,
                "Warning",
                "Extended Above 150DMA",
                f"{ticker} is {distance_from_150dma:.2f}% above the 150DMA. Upside may be stretched short term.",
            )
        )

    if distance_from_150dma < 0:
        alerts.append(
            build_alert_row(
                row,
                "Warning",
                "Below 150DMA",
                f"{ticker} is below the 150DMA. The heartbeat trend is weakening.",
            )
        )

    if final_score >= 75 and distance_from_150dma >= 25:
        alerts.append(
            build_alert_row(
                row,
                "Caution",
                "Great Stock, Bad Entry Risk",
                f"{ticker} has a strong final score but is extended above the 150DMA. Quality may be good, but entry timing is risky.",
            )
        )

    if valuation_score <= 40:
        alerts.append(
            build_alert_row(
                row,
                "Caution",
                "Valuation Risk",
                f"{ticker} has a valuation score of {valuation_score:.0f}/100. Valuation may be stretched.",
            )
        )

    if margin_of_safety < 0:
        alerts.append(
            build_alert_row(
                row,
                "Caution",
                "Negative Margin of Safety",
                f"{ticker} appears above estimated intrinsic value based on your valuation assumptions.",
            )
        )

    if institutional_score < 0:
        alerts.append(
            build_alert_row(
                row,
                "Warning",
                "Institutional Selling Pressure",
                f"{ticker} has a negative institutional smart money score of {institutional_score:.2f}/5.",
            )
        )

    if institutional_flow < 0:
        alerts.append(
            build_alert_row(
                row,
                "Caution",
                "Negative Institutional Flow",
                f"{ticker} has negative institutional net QoQ flow of {institutional_flow:.2f}%.",
            )
        )

    if final_score >= 75 and distance_from_150dma >= 0 and distance_from_150dma < 25 and institutional_score >= 0:
        alerts.append(
            build_alert_row(
                row,
                "Positive",
                "Strong Setup",
                f"{ticker} has a strong final score, is above the 150DMA, and is not in the Profit Locker zone.",
            )
        )

    if chart_score < 50 and fundamental_score >= 70:
        alerts.append(
            build_alert_row(
                row,
                "Info",
                "Fundamentals Strong, Chart Weak",
                f"{ticker} has decent fundamentals but the chart score is weak. Watch for a better technical setup.",
            )
        )

    return alerts


def build_watchlist_alerts(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=ALERT_COLUMNS)

    alerts = []

    for _, row in df.iterrows():
        alerts.extend(generate_alerts_for_stock(row))

    if not alerts:
        return pd.DataFrame(columns=ALERT_COLUMNS)

    alert_df = pd.DataFrame(alerts)

    alert_df["alert_priority"] = alert_df["alert_level"].apply(get_alert_priority)

    alert_df = alert_df.sort_values(
        by=["alert_priority", "final_score"],
        ascending=[False, False],
    )

    return alert_df.drop(columns=["alert_priority"])


def build_alert_summary(alert_df: pd.DataFrame) -> dict:
    if alert_df is None or alert_df.empty:
        return {
            "total_alerts": 0,
            "critical_alerts": 0,
            "warning_alerts": 0,
            "caution_alerts": 0,
            "positive_alerts": 0,
        }

    return {
        "total_alerts": len(alert_df),
        "critical_alerts": len(alert_df[alert_df["alert_level"] == "Critical"]),
        "warning_alerts": len(alert_df[alert_df["alert_level"] == "Warning"]),
        "caution_alerts": len(alert_df[alert_df["alert_level"] == "Caution"]),
        "positive_alerts": len(alert_df[alert_df["alert_level"] == "Positive"]),
    }


def build_alert_severity_chart(alert_df: pd.DataFrame):
    if alert_df is None or alert_df.empty:
        return go.Figure()

    counts = (
        alert_df["alert_level"]
        .value_counts()
        .reindex(["Critical", "Warning", "Caution", "Positive", "Info"])
        .fillna(0)
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=counts.index,
            y=counts.values,
            text=counts.values,
            textposition="outside",
            name="Alert Count",
        )
    )

    fig.update_layout(
        title="Alert Count by Severity",
        xaxis_title="Alert Severity",
        yaxis_title="Count",
        height=450,
    )

    return fig


def build_profit_locker_distance_chart(df: pd.DataFrame):
    if df is None or df.empty:
        return go.Figure()

    if "ticker" not in df.columns or "distance_from_150dma" not in df.columns:
        return go.Figure()

    chart_df = df.copy()

    chart_df["distance_from_150dma"] = pd.to_numeric(
        chart_df["distance_from_150dma"],
        errors="coerce",
    ).fillna(0)

    chart_df = chart_df.sort_values(
        by="distance_from_150dma",
        ascending=False,
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=chart_df["ticker"],
            y=chart_df["distance_from_150dma"],
            text=chart_df["distance_from_150dma"].round(2),
            textposition="outside",
            name="Distance From 150DMA",
        )
    )

    fig.add_hline(
        y=25,
        line_dash="dash",
        annotation_text="Caution Zone: 25%",
    )

    fig.add_hline(
        y=35,
        line_dash="dash",
        annotation_text="Profit Locker Zone: 35%",
    )

    fig.update_layout(
        title="Profit Locker Distance From 150DMA",
        xaxis_title="Ticker",
        yaxis_title="Distance From 150DMA (%)",
        height=550,
    )

    return fig
