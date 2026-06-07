from datetime import datetime

import pandas as pd


def safe_float(value, default=0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default

        return float(value)
    except Exception:
        return default


def safe_text(value, default="N/A") -> str:
    try:
        if value is None or pd.isna(value):
            return default

        value = str(value).strip()

        if value == "":
            return default

        return value
    except Exception:
        return default


def format_money(value) -> str:
    value = safe_float(value)

    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"

    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"

    return f"${value:,.2f}"


def format_percent(value) -> str:
    return f"{safe_float(value):.2f}%"


def get_entry_risk_label(distance_from_150dma: float) -> str:
    if distance_from_150dma >= 35:
        return "Profit Locker zone"

    if distance_from_150dma >= 25:
        return "Extended / caution zone"

    if distance_from_150dma >= 0:
        return "Above 150DMA"

    return "Below 150DMA"


def get_score_quality_label(final_score: float) -> str:
    if final_score >= 85:
        return "Elite setup"

    if final_score >= 75:
        return "Strong setup"

    if final_score >= 60:
        return "Watchlist candidate"

    if final_score >= 45:
        return "Mixed setup"

    return "Weak setup"


def get_primary_risk(row: pd.Series) -> str:
    distance = safe_float(row.get("distance_from_150dma"))
    valuation_score = safe_float(row.get("valuation_score"))
    institutional_score = safe_float(row.get("institutional_smart_money_score"))
    margin_of_safety = safe_float(row.get("margin_of_safety"))

    if distance >= 35:
        return "Profit Locker risk: stock is very extended above 150DMA."

    if distance >= 25:
        return "Entry timing risk: stock is stretched above 150DMA."

    if distance < 0:
        return "Trend risk: stock is below 150DMA."

    if valuation_score <= 40:
        return "Valuation risk: valuation score is weak."

    if margin_of_safety < 0:
        return "Intrinsic value risk: margin of safety is negative."

    if institutional_score < 0:
        return "Smart money risk: institutional score is negative."

    return "No dominant red flag from the current scoring model."


def get_bull_points(row: pd.Series) -> list:
    final_score = safe_float(row.get("final_score"))
    chart_score = safe_float(row.get("chart_score"))
    fundamental_score = safe_float(row.get("fundamental_score"))
    valuation_score = safe_float(row.get("valuation_score"))
    institutional_score = safe_float(row.get("institutional_smart_money_score"))
    distance = safe_float(row.get("distance_from_150dma"))

    points = []

    if final_score >= 75:
        points.append("Strong overall evaluator score.")

    if chart_score >= 70 and distance >= 0:
        points.append("Constructive chart trend above the 150DMA.")

    if fundamental_score >= 70:
        points.append("Strong fundamental score supports the quality case.")

    if valuation_score >= 60:
        points.append(
            "Valuation score is not a major weakness under current assumptions."
        )

    if institutional_score > 0:
        points.append("Institutional smart money signal is supportive.")

    if not points:
        points.append(
            "Bull case needs more confirmation from trend, fundamentals, valuation, or smart money."
        )

    return points


def get_bear_points(row: pd.Series) -> list:
    final_score = safe_float(row.get("final_score"))
    chart_score = safe_float(row.get("chart_score"))
    valuation_score = safe_float(row.get("valuation_score"))
    institutional_score = safe_float(row.get("institutional_smart_money_score"))
    distance = safe_float(row.get("distance_from_150dma"))
    margin_of_safety = safe_float(row.get("margin_of_safety"))

    points = []

    if distance >= 35:
        points.append(
            "Stock is in the Profit Locker zone and may need trimming or patience."
        )
    elif distance >= 25:
        points.append("Stock is extended above the 150DMA, so entry timing is riskier.")

    if distance < 0:
        points.append("Stock is below the 150DMA, meaning the heartbeat trend is weak.")

    if valuation_score <= 40:
        points.append("Valuation score is weak.")

    if margin_of_safety < 0:
        points.append(
            "Margin of safety is negative under current valuation assumptions."
        )

    if institutional_score < 0:
        points.append("Institutional smart money signal is negative.")

    if chart_score < 50:
        points.append("Chart score is weak.")

    if final_score < 50:
        points.append("Overall final score is weak.")

    if not points:
        points.append(
            "Bear case is not dominant, but valuation, trend, and smart money should still be monitored."
        )

    return points


def build_single_row_thesis(row: pd.Series, source_label: str = "Watchlist") -> str:
    ticker = safe_text(row.get("ticker"))
    final_score = safe_float(row.get("final_score"))
    final_label = safe_text(row.get("final_label"))
    final_action = safe_text(row.get("final_action"))
    current_price = safe_float(row.get("current_price"))
    distance = safe_float(row.get("distance_from_150dma"))
    profit_locker_status = safe_text(row.get("profit_locker_status"))
    chart_score = safe_float(row.get("chart_score"))
    fundamental_score = safe_float(row.get("fundamental_score"))
    valuation_score = safe_float(row.get("valuation_score"))
    smart_money_score = safe_float(row.get("final_smart_money_score"))
    institutional_score = safe_float(row.get("institutional_smart_money_score"))
    institutional_flow = safe_float(row.get("institutional_net_qoq_flow_pct"))
    margin_of_safety = safe_float(row.get("margin_of_safety"))

    score_quality = get_score_quality_label(final_score)
    entry_risk = get_entry_risk_label(distance)
    primary_risk = get_primary_risk(row)

    bull_points = "\n".join([f"- {point}" for point in get_bull_points(row)])
    bear_points = "\n".join([f"- {point}" for point in get_bear_points(row)])

    return f"""
## {ticker} Thesis

**Source:** {source_label}
**Current Price:** {format_money(current_price)}
**Final Score:** {final_score:.0f}/100
**Final Label:** {final_label}
**Final Action:** {final_action}
**Setup Quality:** {score_quality}
**Entry Risk:** {entry_risk}

### Base Case
{ticker} currently screens as a **{score_quality.lower()}** with a final score of **{final_score:.0f}/100**. The model action is: **{final_action}**.

### Bull Case
{bull_points}

### Bear Case
{bear_points}

### Key Metrics
- Chart Score: {chart_score:.0f}/100
- Fundamental Score: {fundamental_score:.0f}/100
- Valuation Score: {valuation_score:.0f}/100
- Smart Money Score Used: {smart_money_score:.2f}/5
- Institutional Smart Money Score: {institutional_score:.2f}/5
- Institutional Net QoQ Flow: {institutional_flow:.2f}%
- Distance From 150DMA: {distance:.2f}%
- Margin of Safety: {margin_of_safety:.2f}%
- Profit Locker Status: {profit_locker_status}

### Primary Risk
{primary_risk}

### Tracking Plan
Track the 150DMA trend, Profit Locker status, valuation score, margin of safety, revenue growth, FCF margin, and institutional net QoQ flow.
""".strip()


def prepare_report_df(
    df: pd.DataFrame,
    max_reports: int | None = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    report_df = df.copy()

    if "ticker" not in report_df.columns:
        return pd.DataFrame()

    if "final_score" in report_df.columns:
        report_df["final_score"] = pd.to_numeric(
            report_df["final_score"],
            errors="coerce",
        ).fillna(0)

        report_df = report_df.sort_values(
            by="final_score",
            ascending=False,
        )

    if max_reports is not None:
        report_df = report_df.head(int(max_reports))

    return report_df


def build_thesis_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    report_df = prepare_report_df(df)

    if report_df.empty:
        return pd.DataFrame()

    rows = []

    for _, row in report_df.iterrows():
        final_score = safe_float(row.get("final_score"))
        distance = safe_float(row.get("distance_from_150dma"))

        rows.append(
            {
                "ticker": safe_text(row.get("ticker")),
                "final_score": final_score,
                "final_label": safe_text(row.get("final_label")),
                "final_action": safe_text(row.get("final_action")),
                "setup_quality": get_score_quality_label(final_score),
                "entry_risk": get_entry_risk_label(distance),
                "primary_risk": get_primary_risk(row),
            }
        )

    return pd.DataFrame(rows)


def build_batch_thesis_report(
    df: pd.DataFrame,
    report_title: str,
    source_label: str,
    max_reports: int | None = None,
) -> str:
    report_df = prepare_report_df(df, max_reports=max_reports)

    if report_df.empty:
        return f"# {report_title}\n\nNo thesis report data available."

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_sections = [
        f"# {report_title}",
        "",
        f"Generated: {generated_at}",
        f"Source: {source_label}",
        f"Stocks Included: {len(report_df)}",
        "",
        "## Executive Summary",
        (
            "This report converts the stock evaluator scores into thesis summaries. "
            "It is rule-based and should be used as a research starting point, not as financial advice."
        ),
        "",
    ]

    for _, row in report_df.iterrows():
        report_sections.append(
            build_single_row_thesis(
                row=row,
                source_label=source_label,
            )
        )
        report_sections.append("\n---\n")

    return "\n".join(report_sections).strip()
