import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import pandas as pd
import requests


SEC_MANAGERS_PATH = Path("data/sec_13f_managers.csv")
CUSIP_MAP_PATH = Path("data/sec_13f_cusip_sector_map.csv")

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


def get_sec_headers() -> dict:
    """
    SEC requests should include a descriptive User-Agent.
    Replace the default with your own email if you want.
    """
    user_agent = os.getenv(
        "SEC_USER_AGENT",
        "stock_evaluator/1.0 contact@example.com"
    )

    return {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }


def get_sec_archive_headers() -> dict:
    user_agent = os.getenv(
        "SEC_USER_AGENT",
        "stock_evaluator/1.0 contact@example.com"
    )

    return {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
    }


def normalize_cik(cik) -> str:
    return str(cik).strip().zfill(10)


def cik_no_leading_zeros(cik) -> str:
    return str(int(str(cik).strip()))


def clean_cusip(cusip: str) -> str:
    if cusip is None:
        return ""

    return (
        str(cusip)
        .upper()
        .replace(" ", "")
        .replace("-", "")
        .strip()
    )


def load_sec_managers(file_path: str = str(SEC_MANAGERS_PATH)) -> pd.DataFrame:
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        return pd.DataFrame(columns=["institution", "cik", "type"])

    required_columns = ["institution", "cik", "type"]
    missing_columns = [column for column in required_columns if column not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing required columns in sec_13f_managers.csv: {missing_columns}")

    df["institution"] = df["institution"].astype(str).str.strip()
    df["cik"] = df["cik"].astype(str).str.strip()
    df["type"] = df["type"].astype(str).str.strip()

    return df


def load_cusip_map(file_path: str = str(CUSIP_MAP_PATH)) -> pd.DataFrame:
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        return pd.DataFrame(columns=["cusip", "ticker", "company", "sector"])

    required_columns = ["cusip", "ticker", "company", "sector"]
    missing_columns = [column for column in required_columns if column not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing required columns in sec_13f_cusip_sector_map.csv: {missing_columns}")

    df["cusip"] = df["cusip"].apply(clean_cusip)
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["company"] = df["company"].astype(str).str.strip()
    df["sector"] = df["sector"].astype(str).str.strip()

    return df


def sec_get_json(url: str, archive: bool = False) -> Optional[dict]:
    try:
        headers = get_sec_archive_headers() if archive else get_sec_headers()

        response = requests.get(
            url,
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            return None

        return response.json()

    except Exception:
        return None


def sec_get_text(url: str) -> Optional[str]:
    try:
        response = requests.get(
            url,
            headers=get_sec_archive_headers(),
            timeout=30,
        )

        if response.status_code != 200:
            return None

        return response.text

    except Exception:
        return None


def get_recent_13f_filings(cik: str, max_filings: int = 2) -> list:
    """
    Pulls recent 13F-HR filings for a manager from SEC submissions JSON.
    """

    normalized_cik = normalize_cik(cik)

    url = f"https://data.sec.gov/submissions/CIK{normalized_cik}.json"

    payload = sec_get_json(url)

    if not payload:
        return []

    recent = payload.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    accession_numbers = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])

    filings = []

    for form, accession, filing_date, report_date in zip(
        forms,
        accession_numbers,
        filing_dates,
        report_dates,
    ):
        if str(form).upper() in ["13F-HR", "13F-HR/A"]:
            filings.append(
                {
                    "form": form,
                    "accession_number": accession,
                    "filing_date": filing_date,
                    "report_date": report_date if report_date else filing_date,
                }
            )

        if len(filings) >= max_filings:
            break

    return filings


def get_filing_index(cik: str, accession_number: str) -> Optional[dict]:
    cik_clean = cik_no_leading_zeros(cik)
    accession_clean = accession_number.replace("-", "")

    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_clean}/{accession_clean}/index.json"
    )

    return sec_get_json(url, archive=True)


def find_information_table_xml_url(cik: str, accession_number: str) -> Optional[str]:
    """
    Finds the XML information table file inside a 13F filing folder.
    """

    index_payload = get_filing_index(cik, accession_number)

    if not index_payload:
        return None

    cik_clean = cik_no_leading_zeros(cik)
    accession_clean = accession_number.replace("-", "")

    items = index_payload.get("directory", {}).get("item", [])

    xml_candidates = []

    for item in items:
        name = item.get("name", "")
        name_lower = name.lower()

        if not name_lower.endswith(".xml"):
            continue

        if (
            "infotable" in name_lower
            or "informationtable" in name_lower
            or "form13f" in name_lower
            or "primary_doc" not in name_lower
        ):
            xml_candidates.append(name)

    if not xml_candidates:
        for item in items:
            name = item.get("name", "")
            if name.lower().endswith(".xml"):
                xml_candidates.append(name)

    if not xml_candidates:
        return None

    file_name = xml_candidates[0]

    return (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_clean}/{accession_clean}/{file_name}"
    )


def strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def find_child_text_by_name(element, target_name: str) -> Optional[str]:
    target_name = target_name.lower()

    for child in element.iter():
        clean_tag = strip_namespace(child.tag).lower()

        if clean_tag == target_name:
            return child.text

    return None


def parse_13f_information_table(xml_text: str) -> pd.DataFrame:
    """
    Parses a 13F XML information table into raw CUSIP holdings.
    """

    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except Exception:
        return pd.DataFrame()

    rows = []

    for element in root.iter():
        if strip_namespace(element.tag).lower() != "infotable":
            continue

        name_of_issuer = find_child_text_by_name(element, "nameOfIssuer")
        title_of_class = find_child_text_by_name(element, "titleOfClass")
        cusip = find_child_text_by_name(element, "cusip")
        value_text = find_child_text_by_name(element, "value")
        shares_text = find_child_text_by_name(element, "sshPrnamt")

        try:
            value_thousands = float(str(value_text).replace(",", "").strip())
        except Exception:
            value_thousands = 0

        try:
            shares = float(str(shares_text).replace(",", "").strip())
        except Exception:
            shares = 0

        rows.append(
            {
                "name_of_issuer": name_of_issuer,
                "title_of_class": title_of_class,
                "cusip": clean_cusip(cusip),
                "value_thousands": value_thousands,
                "shares": shares,
            }
        )

    return pd.DataFrame(rows)


def get_flow_label(change_pct: float) -> str:
    if change_pct >= 5:
        return "Accumulating"
    elif change_pct >= 1:
        return "Slight Accumulating"
    elif change_pct > -1:
        return "Neutral"
    elif change_pct > -5:
        return "Slight Reducing"
    else:
        return "Reducing"


def calculate_pct_change(current_value: float, previous_value: float) -> float:
    if previous_value is None or previous_value == 0:
        if current_value > 0:
            return 100.0
        return 0.0

    pct_change = ((current_value - previous_value) / abs(previous_value)) * 100

    return clip_change_pct(pct_change, cap=100)


def fetch_manager_13f_pair(cik: str) -> tuple:
    """
    Fetches latest and previous 13F information tables for a manager.
    """

    filings = get_recent_13f_filings(cik, max_filings=2)

    if not filings:
        return pd.DataFrame(), pd.DataFrame(), None

    latest_filing = filings[0]
    previous_filing = filings[1] if len(filings) > 1 else None

    latest_url = find_information_table_xml_url(
        cik=cik,
        accession_number=latest_filing["accession_number"],
    )

    if not latest_url:
        return pd.DataFrame(), pd.DataFrame(), latest_filing["report_date"]

    latest_xml = sec_get_text(latest_url)

    if not latest_xml:
        return pd.DataFrame(), pd.DataFrame(), latest_filing["report_date"]

    latest_df = parse_13f_information_table(latest_xml)

    previous_df = pd.DataFrame()

    if previous_filing is not None:
        previous_url = find_information_table_xml_url(
            cik=cik,
            accession_number=previous_filing["accession_number"],
        )

        if previous_url:
            previous_xml = sec_get_text(previous_url)

            if previous_xml:
                previous_df = parse_13f_information_table(previous_xml)

    return latest_df, previous_df, latest_filing["report_date"]


def convert_manager_holdings_to_standard_rows(
    institution: str,
    institution_type: str,
    latest_df: pd.DataFrame,
    previous_df: pd.DataFrame,
    report_date: str,
    cusip_map_df: pd.DataFrame,
) -> list:
    """
    Converts one manager's 13F holdings into your app's standard format.
    """

    if latest_df.empty:
        return []

    latest = latest_df.copy()
    previous = previous_df.copy()

    latest["cusip"] = latest["cusip"].apply(clean_cusip)

    if not previous.empty:
        previous["cusip"] = previous["cusip"].apply(clean_cusip)
        previous = previous[
            [
                "cusip",
                "value_thousands",
                "shares",
            ]
        ].rename(
            columns={
                "value_thousands": "previous_value_thousands",
                "shares": "previous_shares",
            }
        )
    else:
        previous = pd.DataFrame(
            columns=[
                "cusip",
                "previous_value_thousands",
                "previous_shares",
            ]
        )

    merged = latest.merge(
        previous,
        on="cusip",
        how="left",
    )

    merged = merged.merge(
        cusip_map_df,
        on="cusip",
        how="inner",
    )

    rows = []

    for _, row in merged.iterrows():
        current_value_thousands = float(row.get("value_thousands", 0) or 0)
        previous_value_thousands = row.get("previous_value_thousands", 0)

        if pd.isna(previous_value_thousands):
            previous_value_thousands = 0

        current_shares = float(row.get("shares", 0) or 0)
        previous_shares = row.get("previous_shares", 0)

        if pd.isna(previous_shares):
            previous_shares = 0

        position_change_pct = calculate_pct_change(
            current_value=current_value_thousands,
            previous_value=previous_value_thousands,
        )

        shares_change_pct = calculate_pct_change(
            current_value=current_shares,
            previous_value=previous_shares,
        )

        # 13F value is reported in thousands of dollars.
        market_value_billions = current_value_thousands / 1_000_000

        rows.append(
            {
                "institution": institution,
                "sector": row["sector"],
                "ticker": row["ticker"],
                "company": row["company"],
                "market_value_billions": market_value_billions,
                "position_change_qoq_pct": position_change_pct,
                "shares_change_qoq_pct": shares_change_pct,
                "flow_status": get_flow_label(position_change_pct),
                "report_date": report_date,
            }
        )

    return rows



def clip_change_pct(value: float, cap: float = 100.0) -> float:
    """
    Caps extreme percentage changes so one tiny previous holding
    does not distort the whole heat map.
    """

    try:
        if value is None or pd.isna(value):
            return 0.0

        value = float(value)

        if value > cap:
            return cap

        if value < -cap:
            return -cap

        return value

    except Exception:
        return 0.0


def clean_sec_13f_output(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans SEC 13F output before sending it to the heat maps.

    Fixes:
    - Unrealistically large market values
    - Extreme QoQ percentage changes
    - Duplicate institution/ticker rows
    """

    if df.empty:
        return df

    df = df.copy()

    numeric_columns = [
        "market_value_billions",
        "position_change_qoq_pct",
        "shares_change_qoq_pct",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    # Some 13F XML files/APIs can make value scaling look 1,000x too large.
    # If the total is absurdly large, scale it down by 1,000.
    total_market_value = df["market_value_billions"].sum()

    if total_market_value > 50_000:
        df["market_value_billions"] = df["market_value_billions"] / 1000

    df["position_change_qoq_pct"] = df["position_change_qoq_pct"].apply(
        lambda value: clip_change_pct(value, cap=100)
    )

    df["shares_change_qoq_pct"] = df["shares_change_qoq_pct"].apply(
        lambda value: clip_change_pct(value, cap=100)
    )

    rows = []

    group_columns = [
        "institution",
        "sector",
        "ticker",
        "company",
        "report_date",
    ]

    for keys, group in df.groupby(group_columns):
        institution, sector, ticker, company, report_date = keys

        market_value = group["market_value_billions"].sum()

        if market_value > 0:
            position_change = (
                group["position_change_qoq_pct"] * group["market_value_billions"]
            ).sum() / market_value

            shares_change = (
                group["shares_change_qoq_pct"] * group["market_value_billions"]
            ).sum() / market_value
        else:
            position_change = group["position_change_qoq_pct"].mean()
            shares_change = group["shares_change_qoq_pct"].mean()

        position_change = clip_change_pct(position_change)
        shares_change = clip_change_pct(shares_change)

        rows.append(
            {
                "institution": institution,
                "sector": sector,
                "ticker": ticker,
                "company": company,
                "market_value_billions": market_value,
                "position_change_qoq_pct": position_change,
                "shares_change_qoq_pct": shares_change,
                "flow_status": get_flow_label(position_change),
                "report_date": report_date,
            }
        )

    clean_df = pd.DataFrame(rows)

    if clean_df.empty:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    clean_df = clean_df[TARGET_COLUMNS]

    return clean_df


def build_sec_13f_holdings(
    manager_limit: int = 5,
    sleep_seconds: float = 0.25,
) -> pd.DataFrame:
    """
    Builds SEC 13F holdings using free official SEC filing data.
    """

    managers_df = load_sec_managers()
    cusip_map_df = load_cusip_map()

    if managers_df.empty or cusip_map_df.empty:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    all_rows = []

    managers_df = managers_df.head(manager_limit)

    for _, manager in managers_df.iterrows():
        institution = manager["institution"]
        cik = manager["cik"]
        institution_type = manager["type"]

        latest_df, previous_df, report_date = fetch_manager_13f_pair(cik)

        rows = convert_manager_holdings_to_standard_rows(
            institution=institution,
            institution_type=institution_type,
            latest_df=latest_df,
            previous_df=previous_df,
            report_date=report_date,
            cusip_map_df=cusip_map_df,
        )

        all_rows.extend(rows)

        time.sleep(sleep_seconds)

    if not all_rows:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    result_df = pd.DataFrame(all_rows)

    for column in TARGET_COLUMNS:
        if column not in result_df.columns:
            result_df[column] = None

    result_df = result_df[TARGET_COLUMNS]
    result_df = clean_sec_13f_output(result_df)

    return result_df
