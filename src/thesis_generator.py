def safe_get(dictionary: dict, key: str, default="N/A"):
    if dictionary is None:
        return default

    return dictionary.get(key, default)


def format_percent_value(value):
    try:
        if value is None:
            return "N/A"

        return f"{float(value):.2f}%"
    except Exception:
        return "N/A"


def format_score(value, denominator=100):
    try:
        return f"{float(value):.0f}/{denominator}"
    except Exception:
        return f"N/A/{denominator}"


def get_chart_read(metrics: dict, chart_score: float) -> str:
    distance = safe_get(metrics, "distance_from_150dma", 0)
    heartbeat_status = safe_get(metrics, "heartbeat_status", "N/A")
    profit_locker_status = safe_get(metrics, "profit_locker_status", "N/A")

    try:
        distance = float(distance)
    except Exception:
        distance = 0

    if distance >= 35:
        return (
            f"The chart is very extended at {distance:.2f}% above the 150DMA. "
            "This supports a Profit Locker review. "
            f"Heartbeat status: {heartbeat_status}. "
            f"Profit Locker status: {profit_locker_status}."
        )

    if distance >= 25:
        return (
            f"The chart is strong but extended at {distance:.2f}% above the 150DMA. "
            "This is a caution zone where new buying may carry weaker risk/reward. "
            f"Heartbeat status: {heartbeat_status}."
        )

    if distance >= 0:
        return (
            f"The stock is trading above the 150DMA by {distance:.2f}%, "
            "which means the main heartbeat trend is intact. "
            f"Chart score: {format_score(chart_score)}."
        )

    return (
        f"The stock is trading {abs(distance):.2f}% below the 150DMA, "
        "which means the heartbeat trend is weak or broken. "
        f"Chart score: {format_score(chart_score)}."
    )


def get_fundamental_read(fundamentals: dict, fundamental_score: float) -> str:
    revenue_growth = safe_get(fundamentals, "revenue_yoy_growth", None)
    gross_margin = safe_get(fundamentals, "gross_margin", None)
    operating_margin = safe_get(fundamentals, "operating_margin", None)
    fcf_margin = safe_get(fundamentals, "fcf_margin", None)

    return (
        f"Fundamental score is {format_score(fundamental_score)}. "
        f"Revenue growth is {format_percent_value(revenue_growth)}, "
        "gross margin is "
        f"{format_percent_value((gross_margin or 0) * 100 if gross_margin != 'N/A' else None)}, "
        "operating margin is "
        f"{format_percent_value((operating_margin or 0) * 100 if operating_margin != 'N/A' else None)}, "
        "and FCF margin is "
        f"{format_percent_value((fcf_margin or 0) * 100 if fcf_margin != 'N/A' else None)}."
    )


def get_valuation_read(valuation: dict) -> str:
    valuation_score = safe_get(valuation, "valuation_score", 0)
    valuation_label = safe_get(valuation, "valuation_label", "N/A")
    margin_of_safety = safe_get(valuation, "margin_of_safety", None)
    valuation_method = safe_get(valuation, "valuation_method", "N/A")

    if margin_of_safety is None:
        margin_text = "Margin of safety is unavailable."
    else:
        try:
            margin_text = f"Margin of safety is {float(margin_of_safety):.2f}%."
        except Exception:
            margin_text = "Margin of safety is unavailable."

    return (
        f"Valuation score is {format_score(valuation_score)} "
        f"with a label of {valuation_label}. "
        f"{margin_text} Primary valuation method: {valuation_method}."
    )


def get_smart_money_read(
    smart_money: dict,
    institutional_smart_money: dict,
    final_smart_money_score: float,
) -> str:
    manual_label = safe_get(smart_money, "smart_money_label", "N/A")
    institutional_label = safe_get(
        institutional_smart_money,
        "institutional_smart_money_label",
        "N/A",
    )
    institutional_flow = safe_get(
        institutional_smart_money,
        "net_qoq_flow_pct",
        0,
    )
    holding_count = safe_get(
        institutional_smart_money,
        "holding_count",
        0,
    )

    return (
        f"Final smart money score used is {format_score(final_smart_money_score, denominator=5)}. "
        f"Manual smart money label: {manual_label}. "
        f"Institutional label: {institutional_label}. "
        f"Institutional net QoQ flow: {institutional_flow}%. "
        f"Tracked institutional holding rows: {holding_count}."
    )


def generate_stock_thesis(
    ticker: str,
    metrics: dict,
    fundamentals: dict,
    valuation: dict,
    smart_money: dict,
    institutional_smart_money: dict,
    chart_score: float,
    fundamental_score: float,
    final_smart_money_score: float,
    final_score: float,
    final_label: str,
    final_action: str,
) -> dict:
    distance = safe_get(metrics, "distance_from_150dma", 0)
    valuation_score = safe_get(valuation, "valuation_score", 0)
    institutional_score = safe_get(
        institutional_smart_money,
        "institutional_smart_money_score",
        0,
    )

    try:
        distance = float(distance)
    except Exception:
        distance = 0

    try:
        valuation_score = float(valuation_score)
    except Exception:
        valuation_score = 0

    try:
        institutional_score = float(institutional_score)
    except Exception:
        institutional_score = 0

    bull_points = []

    if final_score >= 75:
        bull_points.append("The stock has a strong overall evaluator score.")

    if chart_score >= 70:
        bull_points.append(
            "The chart trend is constructive based on the 150DMA heartbeat system."
        )

    if fundamental_score >= 70:
        bull_points.append(
            "The fundamental score is strong enough to support a quality thesis."
        )

    if valuation_score >= 60:
        bull_points.append(
            "Valuation does not appear to be the main weakness under the current assumptions."
        )

    if institutional_score > 0:
        bull_points.append("Institutional smart money data is supportive.")

    if not bull_points:
        bull_points.append(
            "The bull case is not obvious yet; the stock needs stronger confirmation from scores or trend."
        )

    bear_points = []

    if distance >= 35:
        bear_points.append(
            "The stock is in the Profit Locker zone and may be overextended above the 150DMA."
        )
    elif distance >= 25:
        bear_points.append(
            "The stock is extended above the 150DMA, making entry timing riskier."
        )

    if valuation_score <= 40:
        bear_points.append(
            "Valuation score is weak, which could limit forward returns."
        )

    if institutional_score < 0:
        bear_points.append("Institutional smart money data is negative.")

    if chart_score < 50:
        bear_points.append(
            "The chart score is weak, meaning the trend setup may not be healthy."
        )

    if not bear_points:
        bear_points.append(
            "The bear case is not dominant, but valuation, trend, and institutional flow should still be monitored."
        )

    base_case = (
        f"{ticker} currently has a final evaluator score of {format_score(final_score)} "
        f"with a label of {final_label}. The dashboard action is: {final_action}."
    )

    tracking_metrics = [
        "Distance from 150DMA",
        "Profit Locker status",
        "Revenue growth",
        "Operating margin",
        "FCF margin",
        "Valuation score",
        "Margin of safety",
        "Institutional smart money score",
        "Institutional net QoQ flow",
    ]

    thesis_summary = (
        f"{ticker} is best viewed as a "
        f"{final_label.lower() if isinstance(final_label, str) else 'rated'} setup. "
        "The key decision is whether the current chart position offers enough margin "
        "of safety relative to the stock's quality, valuation, and smart money support."
    )

    return {
        "ticker": ticker,
        "base_case": base_case,
        "bull_case": bull_points,
        "bear_case": bear_points,
        "chart_read": get_chart_read(metrics, chart_score),
        "fundamental_read": get_fundamental_read(fundamentals, fundamental_score),
        "valuation_read": get_valuation_read(valuation),
        "smart_money_read": get_smart_money_read(
            smart_money,
            institutional_smart_money,
            final_smart_money_score,
        ),
        "tracking_metrics": tracking_metrics,
        "thesis_summary": thesis_summary,
    }


def build_thesis_markdown(thesis: dict) -> str:
    ticker = thesis.get("ticker", "N/A")

    bull_case = "\n".join([f"- {point}" for point in thesis.get("bull_case", [])])
    bear_case = "\n".join([f"- {point}" for point in thesis.get("bear_case", [])])
    tracking_metrics = "\n".join(
        [f"- {metric}" for metric in thesis.get("tracking_metrics", [])]
    )

    return f"""
# {ticker} Stock Thesis

## Base Case
{thesis.get("base_case", "N/A")}

## Bull Case
{bull_case}

## Bear Case
{bear_case}

## Chart Read
{thesis.get("chart_read", "N/A")}

## Fundamental Read
{thesis.get("fundamental_read", "N/A")}

## Valuation Read
{thesis.get("valuation_read", "N/A")}

## Smart Money Read
{thesis.get("smart_money_read", "N/A")}

## Key Metrics to Track
{tracking_metrics}

## Thesis Summary
{thesis.get("thesis_summary", "N/A")}
""".strip()
