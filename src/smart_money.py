def score_signal(signal: str) -> int:
    """
    Converts a manual smart money signal into a score.
    Score range is -5 to +5.
    """

    signal_scores = {
        "Strong Bullish": 5,
        "Bullish": 3,
        "Slightly Bullish": 1,
        "Neutral": 0,
        "Slightly Bearish": -1,
        "Bearish": -3,
        "Strong Bearish": -5,
        "Unknown": 0
    }

    return signal_scores.get(signal, 0)


def calculate_smart_money_score(
    insider_signal: str,
    politician_signal: str,
    institutional_signal: str,
    officer_signal: str
) -> dict:
    """
    Calculates the total Smart Money score.

    Weighting:
    Insider activity: 35%
    Senior officer activity: 25%
    Institutional activity: 25%
    Politician activity: 15%

    Final score range: -5 to +5.
    """

    insider_weight = 0.35
    officer_weight = 0.25
    institutional_weight = 0.25
    politician_weight = 0.15

    insider_score = score_signal(insider_signal)
    officer_score = score_signal(officer_signal)
    institutional_score = score_signal(institutional_signal)
    politician_score = score_signal(politician_signal)

    weighted_score = (
        insider_score * insider_weight
        + officer_score * officer_weight
        + institutional_score * institutional_weight
        + politician_score * politician_weight
    )

    weighted_score = round(weighted_score, 2)

    return {
        "smart_money_score": weighted_score,
        "insider_score": insider_score,
        "officer_score": officer_score,
        "institutional_score": institutional_score,
        "politician_score": politician_score,
        "insider_weight": insider_weight,
        "officer_weight": officer_weight,
        "institutional_weight": institutional_weight,
        "politician_weight": politician_weight,
    }


def get_smart_money_label(score: float) -> str:
    """
    Converts Smart Money score into a label.
    """

    if score >= 4:
        return "Strong bullish confirmation"
    elif score >= 2:
        return "Bullish confirmation"
    elif score > 0:
        return "Slight bullish confirmation"
    elif score == 0:
        return "Neutral / no clear signal"
    elif score > -2:
        return "Slight bearish warning"
    elif score > -4:
        return "Bearish warning"
    else:
        return "Strong bearish warning"


def get_smart_money_action(score: float) -> str:
    """
    Converts Smart Money score into an action note.
    """

    if score >= 3:
        return "Smart money supports the thesis"
    elif score > 0:
        return "Smart money slightly supports the setup"
    elif score == 0:
        return "No clear smart money edge"
    elif score > -3:
        return "Smart money is a caution flag"
    else:
        return "Smart money is strongly against the setup"


def build_smart_money_summary(
    insider_signal: str,
    politician_signal: str,
    institutional_signal: str,
    officer_signal: str,
    notes: str = ""
) -> dict:
    """
    Builds full Smart Money summary.
    """

    score_data = calculate_smart_money_score(
        insider_signal=insider_signal,
        politician_signal=politician_signal,
        institutional_signal=institutional_signal,
        officer_signal=officer_signal
    )

    smart_money_score = score_data["smart_money_score"]
    smart_money_label = get_smart_money_label(smart_money_score)
    smart_money_action = get_smart_money_action(smart_money_score)

    return {
        "smart_money_score": smart_money_score,
        "smart_money_label": smart_money_label,
        "smart_money_action": smart_money_action,
        "insider_signal": insider_signal,
        "politician_signal": politician_signal,
        "institutional_signal": institutional_signal,
        "officer_signal": officer_signal,
        "notes": notes,
        **score_data
    }