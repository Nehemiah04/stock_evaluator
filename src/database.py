import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/stocks.db")


def get_connection():
    """
    Creates a connection to the SQLite database.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def create_tables():
    """
    Creates the scan_results table if it does not already exist.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            company TEXT,
            current_price REAL,
            dma_150 REAL,
            distance_from_150dma REAL,
            heartbeat_status TEXT,
            profit_locker_status TEXT,
            chart_score INTEGER,
            action_label TEXT
        )
        """)

    conn.commit()
    conn.close()


def save_scan_results(results_df: pd.DataFrame):
    """
    Saves a watchlist scan DataFrame into the SQLite database.
    """

    if results_df.empty:
        return

    create_tables()

    scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows_to_save = []

    for _, row in results_df.iterrows():
        rows_to_save.append(
            {
                "scan_date": scan_date,
                "ticker": row.get("Ticker"),
                "company": row.get("Company"),
                "current_price": row.get("Current Price"),
                "dma_150": row.get("150DMA"),
                "distance_from_150dma": row.get("Distance from 150DMA"),
                "heartbeat_status": row.get("Heartbeat Status"),
                "profit_locker_status": row.get("Profit Locker Status"),
                "chart_score": row.get("Chart Score"),
                "action_label": row.get("Action Label"),
            }
        )

    clean_df = pd.DataFrame(rows_to_save)

    conn = get_connection()
    clean_df.to_sql("scan_results", conn, if_exists="append", index=False)
    conn.close()


def load_scan_history(limit: int = 200) -> pd.DataFrame:
    """
    Loads recent scan history from SQLite.
    """

    create_tables()

    conn = get_connection()

    query = """
        SELECT
            scan_date,
            ticker,
            company,
            current_price,
            dma_150,
            distance_from_150dma,
            heartbeat_status,
            profit_locker_status,
            chart_score,
            action_label
        FROM scan_results
        ORDER BY scan_date DESC, ticker ASC
        LIMIT ?
    """

    history_df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()

    return history_df


def load_latest_scan() -> pd.DataFrame:
    """
    Loads only the most recent scan batch.
    """

    create_tables()

    conn = get_connection()

    latest_date_query = """
        SELECT MAX(scan_date) as latest_scan_date
        FROM scan_results
    """

    latest_date_df = pd.read_sql_query(latest_date_query, conn)

    if latest_date_df.empty or latest_date_df["latest_scan_date"].iloc[0] is None:
        conn.close()
        return pd.DataFrame()

    latest_scan_date = latest_date_df["latest_scan_date"].iloc[0]

    query = """
        SELECT
            scan_date,
            ticker,
            company,
            current_price,
            dma_150,
            distance_from_150dma,
            heartbeat_status,
            profit_locker_status,
            chart_score,
            action_label
        FROM scan_results
        WHERE scan_date = ?
        ORDER BY chart_score DESC
    """

    latest_df = pd.read_sql_query(query, conn, params=(latest_scan_date,))
    conn.close()

    return latest_df
