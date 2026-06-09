import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

FMP_SYMBOL_OWNERSHIP_ENDPOINT = (
    "https://financialmodelingprep.com/api/v4/"
    "institutional-ownership/institutional-holders/symbol-ownership"
)

TARGETS_PATH = Path("data/institutional_targets.csv")
UNIVERSE_PATH = Path("data/smart_money_universe.csv")

TARGET_COLUMNS = [
    "institution",
    "sector",
    "ticker",
    "company",
    "market_value_billions",
    "position_change_qoq_pct",
    "shares_change_qoq_pct",
    "flow_status",
    "report_date",
]


ALIAS_RULES = {
    "JPMorgan Chase": ["jpmorgan", "jp morgan", "jpmorgan chase"],
    "Bank of America": ["bank of america", "bofa", "merrill lynch"],
    "Citigroup": ["citigroup", "citi", "citibank"],
    "Blackstone": ["blackstone"],
    "Apollo Global Management": ["apollo"],
    "KKR": ["kkr", "kohlberg"],
    "Ares Management": ["ares"],
    "Brookfield Asset Management": ["brookfield"],
    "The Carlyle Group": ["carlyle"],
    "TPG": ["tpg"],
    "Blue Owl Capital": ["blue owl"],
    "Bridgewater Associates": ["bridgewater"],
    "Renaissance Technologies": ["renaissance"],
    "Citadel Advisors": ["citadel"],
    "Millennium Management": ["millennium"],
    "Two Sigma": ["two sigma"],
    "BNP Paribas": ["bnp paribas"],
    "HSBC Holdings": ["hsbc"],
    "Crédit Agricole": ["credit agricole", "crédit agricole"],
}


def load_fmp_api_key() -> Optional[str]:
    """
    Loads FMP API key from environment variable.
    Local example:
    export FMP_API_KEY="your_key_here"
    """
    return os.getenv("FMP_API_KEY")


def safe_float(value):
    """
    Converts API values to float safely.
    """
    try:
        if value is None or pd.isna(value):
            return None

        if isinstance(value, str):
            value = value.replace(",", "").replace("$", "").replace("%", "").strip()

        return float(value)
    except Exception:
        return None


def get_first_existing_value(row: dict, possible_keys: list):
    """
    FMP field names can vary by endpoint/version, so this checks multiple possible keys.
    """
    for key in possible_keys:
        if key in row and row.get(key) not in [None, ""]:
            return row.get(key)

    return None


def normalize_name(value: str) -> str:
    """
    Normalizes institution names for matching.
    """
    if value is None:
        return ""

    return (
        str(value)
        .lower()
        .replace("&", "and")
        .replace(".", "")
        .replace(",", "")
        .replace(" llc", "")
        .replace(" inc", "")
        .replace(" corp", "")
        .replace(" corporation", "")
        .replace(" co", "")
        .strip()
    )


def load_target_tickers(file_path: str = str(TARGETS_PATH)) -> pd.DataFrame:
    """
    Loads the ticker universe used for live FMP institutional ownership scans.
    """
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        return pd.DataFrame(columns=["ticker", "company", "sector"])

    required_columns = ["ticker", "company", "sector"]

    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns in institutional_targets.csv: {missing_columns}"
        )

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["company"] = df["company"].astype(str).str.strip()
    df["sector"] = df["sector"].astype(str).str.strip()

    return df


def load_institution_universe_names(file_path: str = str(UNIVERSE_PATH)) -> list:
    """
    Loads institution names from smart_money_universe.csv for matching.
    """
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        return []

    if "institution" not in df.columns:
        return []

    return df["institution"].astype(str).str.strip().tolist()


def match_tracked_institution(
    holder_name: str, tracked_institutions: list
) -> Optional[str]:
    """
    Matches raw API holder name to your tracked universe institutions.
    """
    raw_name = normalize_name(holder_name)

    if not raw_name:
        return None

    for institution in tracked_institutions:
        clean_institution = normalize_name(institution)

        if clean_institution and (
            clean_institution in raw_name or raw_name in clean_institution
        ):
            return institution

    for institution, aliases in ALIAS_RULES.items():
        for alias in aliases:
            clean_alias = normalize_name(alias)

            if clean_alias and clean_alias in raw_name:
                return institution

    return None


def get_latest_close_price(ticker: str) -> Optional[float]:
    """
    Uses yfinance as a price fallback when FMP does not provide market value.
    """
    try:
        data = yf.download(
            ticker,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=False,
        )

        if data.empty:
            return None

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        return float(data["Close"].dropna().iloc[-1])
    except Exception:
        return None


def get_flow_label(net_qoq_change_pct: float) -> str:
    """
    Converts QoQ change into a flow label.
    """
    if net_qoq_change_pct is None:
        return "Unknown"

    if net_qoq_change_pct >= 5:
        return "Accumulating"
    elif net_qoq_change_pct >= 1:
        return "Slight Accumulating"
    elif net_qoq_change_pct > -1:
        return "Neutral"
    elif net_qoq_change_pct > -5:
        return "Slight Reducing"
    else:
        return "Reducing"


def fetch_fmp_symbol_ownership(
    symbol: str,
    report_date: str,
    api_key: str,
    page: int = 0,
) -> list:
    """
    Pulls institutional holders for one symbol/date/page from FMP.

    Endpoint target:
    /api/v4/institutional-ownership/institutional-holders/symbol-ownership
    """

    params = {
        "symbol": symbol,
        "date": report_date,
        "page": page,
        "apikey": api_key,
    }

    try:
        response = requests.get(
            FMP_SYMBOL_OWNERSHIP_ENDPOINT,
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            return []

        payload = response.json()

        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            for key in ["data", "results", "holdings"]:
                if key in payload and isinstance(payload[key], list):
                    return payload[key]

        return []

    except Exception:
        return []


def normalize_fmp_rows_for_symbol(
    raw_rows: list,
    ticker: str,
    company: str,
    sector: str,
    report_date: str,
    tracked_institutions: list,
    price: Optional[float],
) -> list:
    """
    Converts raw FMP rows into your app's standard holdings format.
    """

    normalized_rows = []

    for row in raw_rows:
        if not isinstance(row, dict):
            continue

        holder_name = get_first_existing_value(
            row,
            [
                "holder",
                "holderName",
                "investorName",
                "institution",
                "institutionName",
                "name",
                "companyName",
            ],
        )

        matched_institution = match_tracked_institution(
            holder_name=holder_name,
            tracked_institutions=tracked_institutions,
        )

        if matched_institution is None:
            continue

        shares = safe_float(
            get_first_existing_value(
                row,
                [
                    "sharesNumber",
                    "shares",
                    "share",
                    "numberOfShares",
                    "securities",
                ],
            )
        )

        shares_change_pct = safe_float(
            get_first_existing_value(
                row,
                [
                    "changeInSharesNumberPercentage",
                    "changeInSharesPercentage",
                    "sharesChangePct",
                    "changePct",
                    "change",
                ],
            )
        )

        position_change_pct = safe_float(
            get_first_existing_value(
                row,
                [
                    "positionChangePct",
                    "changeInPositionPercentage",
                    "changeInSharesNumberPercentage",
                    "changeInSharesPercentage",
                    "changePct",
                    "change",
                ],
            )
        )

        market_value_raw = safe_float(
            get_first_existing_value(
                row,
                [
                    "marketValue",
                    "marketValueUsd",
                    "value",
                    "valueUsd",
                    "reportedValue",
                ],
            )
        )

        market_value_billions = None

        if market_value_raw is not None and market_value_raw > 0:
            # FMP usually reports dollar value, so convert dollars to billions.
            market_value_billions = market_value_raw / 1_000_000_000

        elif shares is not None and price is not None:
            market_value_billions = (shares * price) / 1_000_000_000

        else:
            market_value_billions = 0

        if position_change_pct is None:
            position_change_pct = 0

        if shares_change_pct is None:
            shares_change_pct = position_change_pct

        api_report_date = get_first_existing_value(
            row,
            ["date", "reportDate", "filingDate", "acceptedDate"],
        )

        normalized_rows.append(
            {
                "institution": matched_institution,
                "sector": sector,
                "ticker": ticker,
                "company": company,
                "market_value_billions": market_value_billions,
                "position_change_qoq_pct": position_change_pct,
                "shares_change_qoq_pct": shares_change_pct,
                "flow_status": get_flow_label(position_change_pct),
                "report_date": api_report_date if api_report_date else report_date,
            }
        )

    return normalized_rows


def build_live_institutional_holdings(
    api_key: Optional[str] = None,
    report_date: str = "2026-03-31",
    page_limit: int = 1,
    sleep_seconds: float = 0.25,
) -> pd.DataFrame:
    """
    Builds live institutional holdings data from FMP.

    It scans the tickers in data/institutional_targets.csv,
    matches holders to data/smart_money_universe.csv,
    and returns the same columns as the sample CSV.
    """

    if api_key is None:
        api_key = load_fmp_api_key()

    if not api_key:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    targets_df = load_target_tickers()
    tracked_institutions = load_institution_universe_names()

    if targets_df.empty or not tracked_institutions:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    all_rows = []

    for _, target in targets_df.iterrows():
        ticker = target["ticker"]
        company = target["company"]
        sector = target["sector"]

        price = get_latest_close_price(ticker)

        for page in range(int(page_limit)):
            raw_rows = fetch_fmp_symbol_ownership(
                symbol=ticker,
                report_date=report_date,
                api_key=api_key,
                page=page,
            )

            normalized_rows = normalize_fmp_rows_for_symbol(
                raw_rows=raw_rows,
                ticker=ticker,
                company=company,
                sector=sector,
                report_date=report_date,
                tracked_institutions=tracked_institutions,
                price=price,
            )

            all_rows.extend(normalized_rows)

            time.sleep(sleep_seconds)

    if not all_rows:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    live_df = pd.DataFrame(all_rows)

    for column in TARGET_COLUMNS:
        if column not in live_df.columns:
            live_df[column] = None

    live_df = live_df[TARGET_COLUMNS]

    return live_df


def fetch_sec_13f_holdings(manager_limit: int = 5) -> pd.DataFrame:
    """
    Fetches official SEC 13F holdings using the free EDGAR connector.
    """

    from src.sec_13f_connector import build_sec_13f_holdings

    return build_sec_13f_holdings(manager_limit=manager_limit)
