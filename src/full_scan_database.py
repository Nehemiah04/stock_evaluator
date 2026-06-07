from datetime import datetime
from pathlib import Path
import sqlite3

import pandas as pd

DB_PATH = Path("data/stocks.db")

FULL_SCAN_COLUMNS = [
    "scan_id",
    "scan_timestamp",
    "ticker",
    "status",
    "final_score",
    "final_label",
    "final_action",
    "current_price",
    "dma_150",
    "distance_from_150dma",
    "profit_locker_status",
    "chart_score",
    "fundamental_score",
    "valuation_score",
    "final_smart_money_score",
    "institutional_smart_money_score",
    "institutional_smart_money_label",
    "institutional_holding_count",
    "institutional_net_qoq_flow_pct",
    "valuation_label",
    "valuation_method",
    "primary_intrinsic_value",
    "margin_of_safety",
    "heartbeat_status",
    "revenue_yoy_growth",
    "gross_margin",
    "operating_margin",
    "fcf_margin",
    "cash",
    "total_debt",
    "debt_to_equity",
    "current_ratio",
    "error",
]


def get_connection(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def prepare_full_scan_for_database(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes full evaluator scan results before saving to SQLite.
    """

    if results_df is None or results_df.empty:
        return pd.DataFrame(columns=FULL_SCAN_COLUMNS)

    df = results_df.copy()

    scan_timestamp = datetime.now().isoformat(timespec="seconds")
    scan_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    df["scan_id"] = scan_id
    df["scan_timestamp"] = scan_timestamp

    for column in FULL_SCAN_COLUMNS:
        if column not in df.columns:
            df[column] = None

    df = df[FULL_SCAN_COLUMNS]

    return df


def save_full_scan_results(results_df: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    """
    Saves full watchlist scan results to data/stocks.db.
    """

    df = prepare_full_scan_for_database(results_df)

    if df.empty:
        return 0

    with get_connection(db_path) as conn:
        df.to_sql(
            "full_scan_results",
            conn,
            if_exists="append",
            index=False,
        )

    return len(df)


def load_full_scan_history(limit: int = 1000, db_path: Path = DB_PATH) -> pd.DataFrame:
    """
    Loads full evaluator scan history.
    """

    query = """
        SELECT *
        FROM full_scan_results
        ORDER BY scan_timestamp DESC, final_score DESC
        LIMIT ?
    """

    try:
        with get_connection(db_path) as conn:
            return pd.read_sql_query(query, conn, params=(limit,))
    except Exception:
        return pd.DataFrame()


def load_latest_full_scan(db_path: Path = DB_PATH) -> pd.DataFrame:
    """
    Loads the most recent full evaluator scan.
    """

    latest_query = """
        SELECT MAX(scan_timestamp) AS latest_scan_timestamp
        FROM full_scan_results
    """

    data_query = """
        SELECT *
        FROM full_scan_results
        WHERE scan_timestamp = ?
        ORDER BY final_score DESC
    """

    try:
        with get_connection(db_path) as conn:
            latest_df = pd.read_sql_query(latest_query, conn)

            if latest_df.empty:
                return pd.DataFrame()

            latest_scan_timestamp = latest_df.loc[0, "latest_scan_timestamp"]

            if latest_scan_timestamp is None:
                return pd.DataFrame()

            return pd.read_sql_query(
                data_query,
                conn,
                params=(latest_scan_timestamp,),
            )

    except Exception:
        return pd.DataFrame()
