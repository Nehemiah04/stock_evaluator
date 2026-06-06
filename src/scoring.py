import pandas as pd


def calculate_heartbeat(data: pd.DataFrame) -> dict:
    """
    Calculates the stock's chart heartbeat using the 50DMA and 150DMA.
    """

    current_price = float(data["Close"].iloc[-1])
    dma_50 = float(data["50DMA"].iloc[-1])
    dma_150 = float(data["150DMA"].iloc[-1])

    distance_from_150dma = ((current_price - dma_150) / dma_150) * 100

    dma_150_30_days_ago = float(data["150DMA"].iloc[-30])
    dma_150_slope = dma_150 - dma_150_30_days_ago

    if current_price > dma_150 and dma_150_slope > 0:
        heartbeat_status = "Healthy uptrend"
    elif current_price > dma_150 and dma_150_slope <= 0:
        heartbeat_status = "Improving, but not confirmed"
    elif current_price < dma_150 and dma_150_slope > 0:
        heartbeat_status = "Warning: price below rising 150DMA"
    elif current_price < dma_150 and dma_150_slope <= 0:
        heartbeat_status = "Broken trend"
    else:
        heartbeat_status = "Neutral"

    if distance_from_150dma >= 35:
        profit_locker_status = "Red: extremely extended"
    elif distance_from_150dma >= 25:
        profit_locker_status = "Orange: overextended"
    elif distance_from_150dma >= 15:
        profit_locker_status = "Yellow: extended"
    elif current_price < dma_150:
        profit_locker_status = "Red: trend risk"
    else:
        profit_locker_status = "Green: trend intact"

    return {
        "current_price": current_price,
        "dma_50": dma_50,
        "dma_150": dma_150,
        "distance_from_150dma": distance_from_150dma,
        "dma_150_slope": dma_150_slope,
        "heartbeat_status": heartbeat_status,
        "profit_locker_status": profit_locker_status,
    }


def calculate_chart_score(metrics: dict) -> int:
    """
    Scores the chart setup from 0 to 100.
    """

    score = 0

    current_price = metrics["current_price"]
    dma_150 = metrics["dma_150"]
    distance = metrics["distance_from_150dma"]
    heartbeat_status = metrics["heartbeat_status"]

    if current_price > dma_150:
        score += 40

    if heartbeat_status == "Healthy uptrend":
        score += 30
    elif heartbeat_status == "Improving, but not confirmed":
        score += 15
    elif heartbeat_status == "Warning: price below rising 150DMA":
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

    if current_price < dma_150:
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
    elif heartbeat == "Warning: price below rising 150DMA":
        return "Caution: trend under pressure"
    elif heartbeat == "Broken trend":
        return "Avoid: broken chart"
    else:
        return "Neutral"