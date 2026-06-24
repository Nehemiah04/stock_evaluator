import pandas as pd


def calculate_heartbeat(
    data: pd.DataFrame,
    long_dma_column: str = "150DMA",
) -> dict:
    """
    Calculates the stock's chart heartbeat using the 50DMA and a long-term DMA.

    The 150DMA remains the default so watchlists, scans, and monitoring retain
    their existing behavior. Callers can select another precomputed moving
    average column when needed.
    """

    current_price = float(data["Close"].iloc[-1])
    dma_50 = float(data["50DMA"].iloc[-1])
    long_dma = float(data[long_dma_column].iloc[-1])

    distance_from_long_dma = ((current_price - long_dma) / long_dma) * 100

    long_dma_30_days_ago = float(data[long_dma_column].iloc[-30])
    long_dma_slope = long_dma - long_dma_30_days_ago

    if current_price > long_dma and long_dma_slope > 0:
        heartbeat_status = "Healthy uptrend"
    elif current_price > long_dma and long_dma_slope <= 0:
        heartbeat_status = "Improving, but not confirmed"
    elif current_price < long_dma and long_dma_slope > 0:
        heartbeat_status = f"Warning: price below rising {long_dma_column}"
    elif current_price < long_dma and long_dma_slope <= 0:
        heartbeat_status = "Broken trend"
    else:
        heartbeat_status = "Neutral"

    if distance_from_long_dma >= 35:
        profit_locker_status = "Red: extremely extended"
    elif distance_from_long_dma >= 25:
        profit_locker_status = "Orange: overextended"
    elif distance_from_long_dma >= 15:
        profit_locker_status = "Yellow: extended"
    elif current_price < long_dma:
        profit_locker_status = "Red: trend risk"
    else:
        profit_locker_status = "Green: trend intact"

    metrics = {
        "current_price": current_price,
        "dma_50": dma_50,
        "long_dma": long_dma,
        "long_dma_label": long_dma_column,
        "distance_from_long_dma": distance_from_long_dma,
        "long_dma_slope": long_dma_slope,
        "heartbeat_status": heartbeat_status,
        "profit_locker_status": profit_locker_status,
    }

    # Preserve the established data contract for every existing 150DMA caller.
    if long_dma_column == "150DMA":
        metrics.update(
            {
                "dma_150": long_dma,
                "distance_from_150dma": distance_from_long_dma,
                "dma_150_slope": long_dma_slope,
            }
        )

    return metrics


def calculate_chart_score(metrics: dict) -> int:
    """
    Scores the chart setup from 0 to 100.
    """

    score = 0

    current_price = metrics["current_price"]
    long_dma = metrics.get("long_dma", metrics.get("dma_150"))
    distance = metrics.get(
        "distance_from_long_dma",
        metrics.get("distance_from_150dma"),
    )
    heartbeat_status = metrics["heartbeat_status"]

    if current_price > long_dma:
        score += 40

    if heartbeat_status == "Healthy uptrend":
        score += 30
    elif heartbeat_status == "Improving, but not confirmed":
        score += 15
    elif heartbeat_status.startswith("Warning: price below rising "):
        score += 5
    elif heartbeat_status == "Broken trend":
        score -= 20

    if 0 <= distance <= 15:
        score += 20
    elif 15 < distance <= 25:
        score += 10
    elif 25 < distance <= 35:
        score += 0
    elif distance > 35:
        score -= 10

    if current_price < long_dma:
        score -= 20

    return max(0, min(score, 100))


def get_action_label(metrics: dict, chart_score: int) -> str:
    """
    Converts the chart score and Profit Locker signal into an action label.
    """

    profit_locker = metrics["profit_locker_status"]
    heartbeat = metrics["heartbeat_status"]

    if "extremely extended" in profit_locker:
        return "Profit Locker: do not chase"
    elif "overextended" in profit_locker:
        return "Extended: wait for pullback"
    elif heartbeat == "Healthy uptrend" and chart_score >= 80:
        return "Strong chart setup"
    elif heartbeat == "Improving, but not confirmed":
        return "Watchlist: improving"
    elif heartbeat.startswith("Warning: price below rising "):
        return "Caution: trend under pressure"
    elif heartbeat == "Broken trend":
        return "Avoid: broken chart"
    else:
        return "Neutral"
