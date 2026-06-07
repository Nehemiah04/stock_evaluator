import pandas as pd

from src.database import save_scan_results
from src.price_data import load_price_data
from src.scoring import calculate_heartbeat, calculate_chart_score, get_action_label


def load_watchlist(file_path: str = "data/watchlist.csv") -> pd.DataFrame:
    """
    Loads the user's watchlist CSV.
    Expected columns: ticker, company
    """

    try:
        watchlist = pd.read_csv(file_path)
    except FileNotFoundError:
        return pd.DataFrame(columns=["ticker", "company"])

    if "ticker" not in watchlist.columns:
        raise ValueError("watchlist.csv must contain a 'ticker' column.")

    if "company" not in watchlist.columns:
        watchlist["company"] = ""

    watchlist["ticker"] = watchlist["ticker"].astype(str).str.upper().str.strip()
    watchlist["company"] = watchlist["company"].astype(str).str.strip()

    return watchlist


def evaluate_watchlist(file_path: str = "data/watchlist.csv") -> pd.DataFrame:
    """
    Loops through each ticker in the watchlist and calculates the stock evaluator metrics.
    """

    watchlist = load_watchlist(file_path)

    results = []

    for _, row in watchlist.iterrows():
        ticker = row["ticker"]
        company = row.get("company", "")

        try:
            data = load_price_data(ticker)

            if data.empty or len(data) < 160:
                results.append(
                    {
                        "Ticker": ticker,
                        "Company": company,
                        "Current Price": None,
                        "150DMA": None,
                        "Distance from 150DMA": None,
                        "Heartbeat Status": "Not enough data",
                        "Profit Locker Status": "N/A",
                        "Chart Score": 0,
                        "Action Label": "Needs more data",
                    }
                )
                continue

            metrics = calculate_heartbeat(data)
            chart_score = calculate_chart_score(metrics)
            action_label = get_action_label(metrics, chart_score)

            results.append(
                {
                    "Ticker": ticker,
                    "Company": company,
                    "Current Price": round(metrics["current_price"], 2),
                    "150DMA": round(metrics["dma_150"], 2),
                    "Distance from 150DMA": round(metrics["distance_from_150dma"], 2),
                    "Heartbeat Status": metrics["heartbeat_status"],
                    "Profit Locker Status": metrics["profit_locker_status"],
                    "Chart Score": chart_score,
                    "Action Label": action_label,
                }
            )

        except Exception as error:
            results.append(
                {
                    "Ticker": ticker,
                    "Company": company,
                    "Current Price": None,
                    "150DMA": None,
                    "Distance from 150DMA": None,
                    "Heartbeat Status": f"Error: {error}",
                    "Profit Locker Status": "N/A",
                    "Chart Score": 0,
                    "Action Label": "Error",
                }
            )

    results_df = pd.DataFrame(results)

    save_scan_results(results_df)

    results_df.to_csv("exports/watchlist_results.csv", index=False)

    return results_df
