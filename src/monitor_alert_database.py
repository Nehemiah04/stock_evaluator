from datetime import datetime
from pathlib import Path
import hashlib
import sqlite3

import pandas as pd

DB_PATH = Path("data/stocks.db")

MONITOR_ALERT_COLUMNS = [
    "alert_id",
    "saved_at",
    "latest_scan_timestamp",
    "previous_scan_timestamp",
    "ticker",
    "monitor_status",
    "final_score",
    "previous_final_score",
    "final_score_change",
    "score_change_label",
    "distance_from_150dma",
    "previous_distance_from_150dma",
    "distance_from_150dma_change",
    "dma_cross_signal",
    "profit_locker_change",
    "profit_locker_status",
    "valuation_score_change",
    "institutional_score_change",
    "institutional_flow_change",
]


def get_connection(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def create_monitor_alerts_table(db_path: Path = DB_PATH):
    with get_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS monitor_alerts (
                alert_id TEXT PRIMARY KEY,
                saved_at TEXT,
                latest_scan_timestamp TEXT,
                previous_scan_timestamp TEXT,
                ticker TEXT,
                monitor_status TEXT,
                final_score REAL,
                previous_final_score REAL,
                final_score_change REAL,
                score_change_label TEXT,
                distance_from_150dma REAL,
                previous_distance_from_150dma REAL,
                distance_from_150dma_change REAL,
                dma_cross_signal TEXT,
                profit_locker_change TEXT,
                profit_locker_status TEXT,
                valuation_score_change REAL,
                institutional_score_change REAL,
                institutional_flow_change REAL
            )
            """)


def safe_value(row, column: str, default=None):
    try:
        value = row.get(column, default)

        if pd.isna(value):
            return default

        return value
    except Exception:
        return default


def to_number(value, default=0.0):
    try:
        if value is None or pd.isna(value):
            return default

        return float(value)
    except Exception:
        return default


def filter_important_monitor_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    working_df = df.copy()

    for column in [
        "monitor_status",
        "score_change_label",
        "dma_cross_signal",
        "profit_locker_change",
    ]:
        if column not in working_df.columns:
            working_df[column] = ""

        working_df[column] = working_df[column].astype(str)

    important_profit_locker_changes = [
        "New Profit Locker trigger",
        "New extended/caution trigger",
        "Reset below caution zone",
    ]

    important_mask = (
        working_df["monitor_status"].str.contains(
            "Alert|Positive",
            case=False,
            na=False,
        )
        | (working_df["score_change_label"] != "Stable")
        | ~working_df["dma_cross_signal"].isin(["No cross", "No previous scan"])
        | working_df["profit_locker_change"].isin(important_profit_locker_changes)
    )

    return working_df[important_mask].copy()


def build_alert_id(saved_at: str, ticker: str, row: pd.Series) -> str:
    row_hash = hashlib.sha256(str(row.to_dict()).encode("utf-8")).hexdigest()[:16]
    alert_id = f"{saved_at}_{ticker}_{row_hash}"

    return alert_id.replace(":", "-").replace(" ", "_")


def save_monitor_alerts(
    monitor_df: pd.DataFrame,
    monitor_timestamps: list | None = None,
    save_only_important: bool = True,
    db_path: Path = DB_PATH,
) -> int:
    create_monitor_alerts_table(db_path)

    if monitor_df is None or monitor_df.empty:
        return 0

    if save_only_important:
        df = filter_important_monitor_rows(monitor_df)
    else:
        df = monitor_df.copy()

    if df.empty:
        return 0

    saved_at = datetime.now().isoformat(timespec="seconds")

    latest_scan_timestamp = ""
    previous_scan_timestamp = ""

    if monitor_timestamps:
        if len(monitor_timestamps) >= 1:
            latest_scan_timestamp = monitor_timestamps[0]

        if len(monitor_timestamps) >= 2:
            previous_scan_timestamp = monitor_timestamps[1]

    rows = []

    for _, row in df.iterrows():
        ticker = str(safe_value(row, "ticker", "")).upper().strip()

        rows.append(
            {
                "alert_id": build_alert_id(saved_at, ticker, row),
                "saved_at": saved_at,
                "latest_scan_timestamp": latest_scan_timestamp,
                "previous_scan_timestamp": previous_scan_timestamp,
                "ticker": ticker,
                "monitor_status": str(safe_value(row, "monitor_status", "")),
                "final_score": to_number(safe_value(row, "final_score", 0)),
                "previous_final_score": to_number(
                    safe_value(row, "previous_final_score", 0)
                ),
                "final_score_change": to_number(
                    safe_value(row, "final_score_change", 0)
                ),
                "score_change_label": str(safe_value(row, "score_change_label", "")),
                "distance_from_150dma": to_number(
                    safe_value(row, "distance_from_150dma", 0)
                ),
                "previous_distance_from_150dma": to_number(
                    safe_value(row, "previous_distance_from_150dma", 0)
                ),
                "distance_from_150dma_change": to_number(
                    safe_value(row, "distance_from_150dma_change", 0)
                ),
                "dma_cross_signal": str(safe_value(row, "dma_cross_signal", "")),
                "profit_locker_change": str(
                    safe_value(row, "profit_locker_change", "")
                ),
                "profit_locker_status": str(
                    safe_value(row, "profit_locker_status", "")
                ),
                "valuation_score_change": to_number(
                    safe_value(row, "valuation_score_change", 0)
                ),
                "institutional_score_change": to_number(
                    safe_value(row, "institutional_score_change", 0)
                ),
                "institutional_flow_change": to_number(
                    safe_value(row, "institutional_flow_change", 0)
                ),
            }
        )

    alert_df = pd.DataFrame(rows)

    if alert_df.empty:
        return 0

    alert_df = alert_df[MONITOR_ALERT_COLUMNS]

    with get_connection(db_path) as conn:
        alert_df.to_sql(
            "monitor_alerts",
            conn,
            if_exists="append",
            index=False,
        )

    return len(alert_df)


def load_monitor_alert_history(
    limit: int = 500,
    ticker_filter: str = "",
    status_filter: str = "All",
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    create_monitor_alerts_table(db_path)

    query = """
        SELECT *
        FROM monitor_alerts
        ORDER BY saved_at DESC
        LIMIT ?
    """

    with get_connection(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=(limit,))

    if df.empty:
        return df

    if ticker_filter:
        ticker_filter = str(ticker_filter).upper().strip()

        df = df[
            df["ticker"].astype(str).str.upper().str.contains(ticker_filter, na=False)
        ]

    if status_filter != "All":
        df = df[
            df["monitor_status"]
            .astype(str)
            .str.contains(status_filter, case=False, na=False)
        ]

    return df
