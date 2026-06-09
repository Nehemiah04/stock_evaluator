from pathlib import Path

import pandas as pd

NASDAQ_TRADED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
DEFAULT_UNIVERSE_PATH = Path("data/market_universe.csv")


def clean_symbol(symbol: str) -> str:
    symbol = str(symbol).strip().upper()

    # yfinance usually uses "-" instead of "." for class shares.
    symbol = symbol.replace(".", "-")

    return symbol


def download_nasdaq_traded_universe() -> pd.DataFrame:
    df = pd.read_csv(
        NASDAQ_TRADED_URL,
        sep="|",
        dtype=str,
    )

    if "Symbol" in df.columns:
        df = df[df["Symbol"].notna()]
        df = df[df["Symbol"].astype(str).str.upper() != "FILE CREATION TIME"]

    return df


def build_market_universe(
    include_etfs: bool = False,
    include_test_issues: bool = False,
    include_nextshares: bool = False,
) -> pd.DataFrame:
    df = download_nasdaq_traded_universe()

    rename_map = {
        "Symbol": "ticker",
        "Security Name": "security_name",
        "Listing Exchange": "listing_exchange",
        "Market Category": "market_category",
        "ETF": "is_etf",
        "Test Issue": "is_test_issue",
        "Financial Status": "financial_status",
        "CQS Symbol": "cqs_symbol",
        "NASDAQ Symbol": "nasdaq_symbol",
        "NextShares": "is_nextshares",
    }

    df = df.rename(columns=rename_map)

    required_columns = [
        "ticker",
        "security_name",
        "listing_exchange",
        "market_category",
        "is_etf",
        "is_test_issue",
        "financial_status",
        "cqs_symbol",
        "nasdaq_symbol",
        "is_nextshares",
    ]

    for column in required_columns:
        if column not in df.columns:
            df[column] = ""

    df["ticker"] = df["ticker"].apply(clean_symbol)

    df = df[df["ticker"] != ""]
    df = df[~df["ticker"].str.contains(r"\$", regex=True, na=False)]

    if not include_etfs:
        df = df[df["is_etf"].astype(str).str.upper() != "Y"]

    if not include_test_issues:
        df = df[df["is_test_issue"].astype(str).str.upper() != "Y"]

    if not include_nextshares:
        df = df[df["is_nextshares"].astype(str).str.upper() != "Y"]

    df = df.drop_duplicates(subset=["ticker"])
    df = df.sort_values("ticker").reset_index(drop=True)

    return df[required_columns]


def save_market_universe(
    universe_df: pd.DataFrame,
    path: Path = DEFAULT_UNIVERSE_PATH,
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    universe_df.to_csv(path, index=False)

    return len(universe_df)


def load_market_universe(
    path: Path = DEFAULT_UNIVERSE_PATH,
) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path, dtype=str)


def load_market_universe_tickers(
    path: Path = DEFAULT_UNIVERSE_PATH,
    max_tickers: int | None = None,
) -> list[str]:
    df = load_market_universe(path)

    if df.empty or "ticker" not in df.columns:
        return []

    tickers = (
        df["ticker"]
        .dropna()
        .astype(str)
        .str.upper()
        .str.strip()
        .drop_duplicates()
        .tolist()
    )

    if max_tickers is not None:
        tickers = tickers[: int(max_tickers)]

    return tickers
