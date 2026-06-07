import pandas as pd
import yfinance as yf


def load_price_data(ticker: str) -> pd.DataFrame:
    """
    Loads 2 years of daily stock price data using yfinance.
    Adds 50-day and 150-day moving averages.
    """

    data = yf.download(
        ticker, period="2y", interval="1d", auto_adjust=False, progress=False
    )

    if data.empty:
        return pd.DataFrame()

    # Handles yfinance multi-index column issues
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.dropna()

    data["50DMA"] = data["Close"].rolling(window=50).mean()
    data["150DMA"] = data["Close"].rolling(window=150).mean()

    return data
