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
    "sector",
    "industry",
    "quote_type",
    "fundamental_profile",
    "fundamental_data_quality",
    "missing_fundamental_fields",
    "revenue_yoy_growth",
    "gross_margin",
    "operating_margin",
    "net_income_yoy_growth",
    "return_on_equity",
    "equity_to_assets",
    "cash_to_debt",
    "fcf_margin",
    "cash",
    "total_debt",
    "debt_to_equity",
    "current_ratio",
    "error",
]

GROWTH_METRIC_COLUMNS = [
    "scan_id",
    "scan_timestamp",
    "ticker",
    "metric",
    "sector_relative_grade",
    "value",
    "sector_median",
    "diff_to_sector",
    "five_year_average",
    "diff_to_five_year_average",
]

TEXT_COLUMNS = {
    "scan_id",
    "scan_timestamp",
    "ticker",
    "status",
    "final_label",
    "final_action",
    "profit_locker_status",
    "institutional_smart_money_label",
    "valuation_label",
    "valuation_method",
    "heartbeat_status",
    "sector",
    "industry",
    "quote_type",
    "fundamental_profile",
    "fundamental_data_quality",
    "missing_fundamental_fields",
    "error",
    "metric",
    "sector_relative_grade",
}


def get_connection(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def get_sqlite_column_type(column: str) -> str:
    if column in TEXT_COLUMNS:
        return "TEXT"

    return "REAL"


def ensure_table_columns(conn, table_name: str, columns: list[str]):
    existing_columns = {
        row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }

    if not existing_columns:
        return

    for column in columns:
        if column in existing_columns:
            continue

        column_type = get_sqlite_column_type(column)
        conn.execute(f'ALTER TABLE {table_name} ADD COLUMN "{column}" {column_type}')


def add_scan_metadata(results_df: pd.DataFrame) -> pd.DataFrame:
    df = results_df.copy()

    if "scan_timestamp" not in df.columns or df["scan_timestamp"].isna().all():
        df["scan_timestamp"] = datetime.now().isoformat(timespec="seconds")

    if "scan_id" not in df.columns or df["scan_id"].isna().all():
        df["scan_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")

    return df


def prepare_full_scan_for_database(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes full evaluator scan results before saving to SQLite.
    """

    if results_df is None or results_df.empty:
        return pd.DataFrame(columns=FULL_SCAN_COLUMNS)

    df = add_scan_metadata(results_df)

    for column in FULL_SCAN_COLUMNS:
        if column not in df.columns:
            df[column] = None

    df = df[FULL_SCAN_COLUMNS]

    return df


def prepare_growth_metrics_for_database(results_df: pd.DataFrame) -> pd.DataFrame:
    if results_df is None or results_df.empty or "growth_metrics" not in results_df.columns:
        return pd.DataFrame(columns=GROWTH_METRIC_COLUMNS)

    df = add_scan_metadata(results_df)
    growth_rows = []

    for _, row in df.iterrows():
        ticker = row.get("ticker")
        growth_metrics = row.get("growth_metrics", [])

        if not isinstance(growth_metrics, list):
            continue

        for metric in growth_metrics:
            if not isinstance(metric, dict):
                continue

            growth_rows.append(
                {
                    "scan_id": row.get("scan_id"),
                    "scan_timestamp": row.get("scan_timestamp"),
                    "ticker": ticker,
                    "metric": metric.get("metric"),
                    "sector_relative_grade": metric.get("sector_relative_grade"),
                    "value": metric.get("value"),
                    "sector_median": metric.get("sector_median"),
                    "diff_to_sector": metric.get("diff_to_sector"),
                    "five_year_average": metric.get("five_year_average"),
                    "diff_to_five_year_average": metric.get(
                        "diff_to_five_year_average"
                    ),
                }
            )

    if not growth_rows:
        return pd.DataFrame(columns=GROWTH_METRIC_COLUMNS)

    growth_df = pd.DataFrame(growth_rows)

    for column in GROWTH_METRIC_COLUMNS:
        if column not in growth_df.columns:
            growth_df[column] = None

    return growth_df[GROWTH_METRIC_COLUMNS]


def save_full_scan_results(results_df: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    """
    Saves full watchlist scan results to data/stocks.db.
    """

    if results_df is None or results_df.empty:
        return 0

    metadata_df = add_scan_metadata(results_df)
    df = prepare_full_scan_for_database(metadata_df)
    growth_df = prepare_growth_metrics_for_database(metadata_df)

    if df.empty:
        return 0

    with get_connection(db_path) as conn:
        ensure_table_columns(conn, "full_scan_results", FULL_SCAN_COLUMNS)

        df.to_sql(
            "full_scan_results",
            conn,
            if_exists="append",
            index=False,
        )

        if not growth_df.empty:
            ensure_table_columns(conn, "full_scan_growth_metrics", GROWTH_METRIC_COLUMNS)

            growth_df.to_sql(
                "full_scan_growth_metrics",
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
