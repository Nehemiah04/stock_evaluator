import os
import sys
import json
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.institutional_connector import (
    fetch_fmp_symbol_ownership,
    load_institution_universe_names,
    match_tracked_institution,
)


def main():
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    report_date = sys.argv[2] if len(sys.argv) > 2 else "2025-12-31"
    page = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    api_key = os.getenv("FMP_API_KEY")

    if not api_key:
        print("ERROR: FMP_API_KEY is not set.")
        print("Run this first:")
        print("read -s FMP_API_KEY")
        print("export FMP_API_KEY")
        return

    endpoint = (
        "https://financialmodelingprep.com/api/v4/"
        "institutional-ownership/institutional-holders/symbol-ownership"
    )

    params_without_key = {
        "symbol": ticker,
        "date": report_date,
        "page": page,
    }

    params_with_key = {
        **params_without_key,
        "apikey": api_key,
    }

    print("=" * 80)
    print("FMP 13F DEBUG")
    print("=" * 80)
    print(f"Ticker: {ticker}")
    print(f"Report date: {report_date}")
    print(f"Page: {page}")
    print(f"Endpoint: {endpoint}")
    print(f"Params without key: {params_without_key}")
    print("-" * 80)

    response = requests.get(endpoint, params=params_with_key, timeout=30)

    print(f"HTTP status: {response.status_code}")
    print(f"Content type: {response.headers.get('content-type')}")
    print("-" * 80)

    text_preview = response.text[:1000]
    print("Raw response preview:")
    print(text_preview)
    print("-" * 80)

    try:
        payload = response.json()
    except Exception as error:
        print(f"Could not parse JSON: {error}")
        return

    if isinstance(payload, dict):
        print("Payload type: dict")
        print(f"Payload keys: {list(payload.keys())}")

        for key, value in payload.items():
            if isinstance(value, str):
                print(f"{key}: {value[:300]}")
            else:
                print(f"{key}: {type(value)}")

        rows = []

        for possible_key in ["data", "results", "holdings"]:
            if possible_key in payload and isinstance(payload[possible_key], list):
                rows = payload[possible_key]
                break

    elif isinstance(payload, list):
        print("Payload type: list")
        rows = payload

    else:
        print(f"Unexpected payload type: {type(payload)}")
        return

    print(f"Rows returned: {len(rows)}")

    if not rows:
        print("-" * 80)
        print("No rows returned.")
        print("Try another date like 2025-12-31, 2025-09-30, or 2025-06-30.")
        return

    print("-" * 80)
    print("First row keys:")
    print(list(rows[0].keys()))

    print("-" * 80)
    print("First row sample:")
    print(json.dumps(rows[0], indent=2)[:2000])

    tracked_institutions = load_institution_universe_names()
    matched_rows = []

    for row in rows[:50]:
        holder_name = (
            row.get("holder")
            or row.get("holderName")
            or row.get("investorName")
            or row.get("institution")
            or row.get("institutionName")
            or row.get("name")
            or row.get("companyName")
        )

        matched = match_tracked_institution(holder_name, tracked_institutions)

        matched_rows.append(
            {
                "holder_name": holder_name,
                "matched": matched,
            }
        )

    print("-" * 80)
    print("Holder name matching preview:")
    for item in matched_rows[:25]:
        print(f"{item['holder_name']}  --->  {item['matched']}")

    matched_count = sum(1 for item in matched_rows if item["matched"] is not None)

    print("-" * 80)
    print(f"Matched count in first 50 rows: {matched_count}")


if __name__ == "__main__":
    main()
