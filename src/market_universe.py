from pathlib import Path

import pandas as pd

NASDAQ_TRADED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
DEFAULT_UNIVERSE_PATH = Path("data/market_universe.csv")

UNSUPPORTED_SECURITY_KEYWORDS = [
    "warrant",
    "rights",
    "right to",
    "unit",
    "units",
    "preferred",
    "preference",
    "etf",
    "etn",
    "fund",
    "notes due",
    "senior notes",
    "subordinated notes",
]


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


def is_supported_common_stock_row(row) -> bool:
    ticker = clean_symbol(row.get("ticker", ""))
    security_name = str(row.get("security_name", "")).strip().lower()

    if not ticker or "$" in ticker:
        return False

    if str(row.get("is_etf", "")).strip().upper() == "Y":
        return False

    if str(row.get("is_test_issue", "")).strip().upper() == "Y":
        return False

    if str(row.get("is_nextshares", "")).strip().upper() == "Y":
        return False

    if any(keyword in security_name for keyword in UNSUPPORTED_SECURITY_KEYWORDS):
        if "common stock" not in security_name:
            return False

        if any(
            keyword in security_name
            for keyword in ["warrant", "rights", "unit", "preferred", "fund", "etf"]
        ):
            return False

    return True


def filter_supported_common_stocks(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    working_df = df.copy()

    for column in [
        "ticker",
        "security_name",
        "is_etf",
        "is_test_issue",
        "is_nextshares",
    ]:
        if column not in working_df.columns:
            working_df[column] = ""

    supported_mask = working_df.apply(is_supported_common_stock_row, axis=1)

    return working_df[supported_mask].reset_index(drop=True)


def filter_supported_tickers(
    tickers: list[str], universe_df: pd.DataFrame
) -> tuple[list[str], list[str]]:
    if not tickers:
        return [], []

    if universe_df is None or universe_df.empty or "ticker" not in universe_df.columns:
        return tickers, []

    universe_df = universe_df.copy()
    universe_df["ticker"] = universe_df["ticker"].apply(clean_symbol)

    known_tickers = set(universe_df["ticker"].dropna().astype(str))
    supported_tickers = set(
        filter_supported_common_stocks(universe_df)["ticker"].dropna().astype(str)
    )

    kept_tickers = []
    excluded_tickers = []

    for ticker in tickers:
        clean_ticker = clean_symbol(ticker)

        if clean_ticker in known_tickers and clean_ticker not in supported_tickers:
            excluded_tickers.append(clean_ticker)
        else:
            kept_tickers.append(clean_ticker)

    return kept_tickers, excluded_tickers


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
    supported_common_only: bool = False,
) -> list[str]:
    df = load_market_universe(path)

    if df.empty or "ticker" not in df.columns:
        return []

    if supported_common_only:
        df = filter_supported_common_stocks(df)

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
