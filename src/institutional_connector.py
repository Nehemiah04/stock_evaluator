import os
from typing import Optional

import pandas as pd


def load_fmp_api_key() -> Optional[str]:
    return os.getenv("FMP_API_KEY")


def fetch_fmp_institutional_holdings_placeholder(
    ticker: str,
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """
    Placeholder for future FMP / SEC / 13F connector.

    Target output columns:
    institution
    sector
    ticker
    company
    market_value_billions
    position_change_qoq_pct
    shares_change_qoq_pct
    flow_status
    report_date
    """

    if api_key is None:
        api_key = load_fmp_api_key()

    if not api_key:
        return pd.DataFrame()

    return pd.DataFrame()
