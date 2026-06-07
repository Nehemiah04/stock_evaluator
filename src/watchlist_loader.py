import pandas as pd


def load_watchlist_tickers(file_path: str = "data/watchlist.csv") -> list:
    """
    Loads ticker symbols from data/watchlist.csv.

    Works with either:
    - ticker column
    - symbol column
    - first column fallback
    """

    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        return []

    if df.empty:
        return []

    lower_columns = {
        column.lower().strip(): column
        for column in df.columns
    }

    if "ticker" in lower_columns:
        ticker_column = lower_columns["ticker"]
    elif "symbol" in lower_columns:
        ticker_column = lower_columns["symbol"]
    else:
        ticker_column = df.columns[0]

    tickers = (
        df[ticker_column]
        .dropna()
        .astype(str)
        .str.upper()
        .str.strip()
        .tolist()
    )

    clean_tickers = []

    for ticker in tickers:
        if ticker and ticker not in clean_tickers:
            clean_tickers.append(ticker)

    return clean_tickers
