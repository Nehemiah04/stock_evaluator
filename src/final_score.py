def calculate_final_score(
    chart_score: int,
    fundamental_score: int,
    valuation_score: int,
    smart_money_score: int = 0,
) -> dict:
    """
    Combines chart, fundamentals, valuation, and smart money into one final score.

    Current weights:
    Chart Heartbeat: 30%
    Fundamentals: 35%
    Valuation: 25%
    Smart Money: 10%

    Smart money is optional for now and defaults to 0.
    """

    chart_weight = 0.30
    fundamental_weight = 0.35
    valuation_weight = 0.25
    smart_money_weight = 0.10

    # Convert smart money from -5/+5 style into 0-100 style
    smart_money_normalized = ((smart_money_score + 5) / 10) * 100

    final_score = (
        chart_score * chart_weight
        + fundamental_score * fundamental_weight
        + valuation_score * valuation_weight
        + smart_money_normalized * smart_money_weight
    )

    final_score = round(final_score)

    return {
        "final_score": max(0, min(final_score, 100)),
        "chart_weight": chart_weight,
        "fundamental_weight": fundamental_weight,
        "valuation_weight": valuation_weight,
        "smart_money_weight": smart_money_weight,
        "smart_money_normalized": smart_money_normalized,
    }


def get_final_label(final_score: int) -> str:
    """
    Converts final score into an investor-style label.
    """

    if final_score >= 90:
        return "Elite candidate"
    elif final_score >= 80:
        return "Strong watchlist / buy on pullback"
    elif final_score >= 70:
        return "Good setup, needs confirmation"
    elif final_score >= 60:
        return "Speculative / incomplete setup"
    elif final_score >= 50:
        return "Weak setup"
    else:
        return "Avoid"


def get_final_action(
    final_score: int,
    chart_action_label: str,
    valuation_label: str,
    profit_locker_status: str,
    long_dma_label: str = "150DMA",
) -> str:
    """
    Creates a practical action based on score, chart, valuation, and Profit Locker status.
    """

    if "extremely extended" in profit_locker_status:
        return "Profit Locker: do not chase; consider trimming if position is oversized"

    if "overextended" in profit_locker_status:
        return "Wait for pullback; trend is strong but entry risk is elevated"

    if "broken" in chart_action_label.lower():
        return f"Avoid until chart recovers above the {long_dma_label}"

    if final_score >= 85 and valuation_label in [
        "Strong undervaluation",
        "Attractive",
        "Decent",
    ]:
        return "High-quality setup; consider buy zone"

    if final_score >= 75:
        return "Strong watchlist; wait for better entry or confirmation"

    if final_score >= 60:
        return "Monitor only; setup is incomplete"

    return "Avoid for now"
