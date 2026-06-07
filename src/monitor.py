from pathlib import Path
import sqlite3

import pandas as pd

DB_PATH = Path("data/stocks.db")


def get_connection(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def load_recent_full_scan_timestamps(
    limit: int = 2,
    db_path: Path = DB_PATH,
) -> list:
    query = """
        SELECT DISTINCT scan_timestamp
        FROM full_scan_results
        ORDER BY scan_timestamp DESC
        LIMIT ?
    """

    try:
        with get_connection(db_path) as conn:
            df = pd.read_sql_query(query, conn, params=(limit,))

        if df.empty:
            return []

        return df["scan_timestamp"].tolist()
    except Exception:
        return []


def load_full_scan_by_timestamp(
    scan_timestamp: str,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    query = """
        SELECT *
        FROM full_scan_results
        WHERE scan_timestamp = ?
    """

    try:
        with get_connection(db_path) as conn:
            return pd.read_sql_query(query, conn, params=(scan_timestamp,))
    except Exception:
        return pd.DataFrame()


def safe_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([0] * len(df))

    return pd.to_numeric(df[column], errors="coerce").fillna(0)


def classify_score_change(change: float) -> str:
    if change >= 10:
        return "Major upgrade"

    if change >= 5:
        return "Upgrade"

    if change <= -10:
        return "Major downgrade"

    if change <= -5:
        return "Downgrade"

    return "Stable"


def detect_150dma_cross(previous_distance: float, latest_distance: float) -> str:
    if previous_distance < 0 and latest_distance >= 0:
        return "Crossed above 150DMA"

    if previous_distance >= 0 and latest_distance < 0:
        return "Broke below 150DMA"

    return "No cross"


def detect_profit_locker_change(
    previous_distance: float,
    latest_distance: float,
) -> str:
    if previous_distance < 35 and latest_distance >= 35:
        return "New Profit Locker trigger"

    if previous_distance < 25 and latest_distance >= 25:
        return "New extended/caution trigger"

    if previous_distance >= 25 and latest_distance < 25:
        return "Reset below caution zone"

    return "No new Profit Locker change"


def build_monitor_status(row: pd.Series) -> str:
    score_label = row.get("score_change_label", "Stable")
    dma_signal = row.get("dma_cross_signal", "No cross")
    profit_signal = row.get("profit_locker_change", "No new Profit Locker change")

    if profit_signal == "New Profit Locker trigger":
        return "Alert: new Profit Locker trigger"

    if dma_signal == "Broke below 150DMA":
        return "Alert: broke below 150DMA"

    if score_label in ["Major downgrade", "Downgrade"]:
        return f"Alert: {score_label.lower()}"

    if score_label in ["Major upgrade", "Upgrade"]:
        return f"Positive: {score_label.lower()}"

    if dma_signal == "Crossed above 150DMA":
        return "Positive: crossed above 150DMA"

    return "Stable"


def build_monitor_change_report(
    latest_df: pd.DataFrame,
    previous_df: pd.DataFrame,
) -> pd.DataFrame:
    if latest_df is None or latest_df.empty:
        return pd.DataFrame()

    if previous_df is None or previous_df.empty:
        latest_only = latest_df.copy()
        latest_only["monitor_status"] = "No previous scan to compare"
        latest_only["score_change_label"] = "Stable"
        latest_only["dma_cross_signal"] = "No previous scan"
        latest_only["profit_locker_change"] = "No previous scan"
        latest_only["final_score_change"] = 0
        latest_only["distance_from_150dma_change"] = 0
        latest_only["valuation_score_change"] = 0
        latest_only["institutional_score_change"] = 0
        latest_only["institutional_flow_change"] = 0
        return latest_only

    latest = latest_df.copy()
    previous = previous_df.copy()

    latest["ticker"] = latest["ticker"].astype(str).str.upper().str.strip()
    previous["ticker"] = previous["ticker"].astype(str).str.upper().str.strip()

    latest_columns = [
        "ticker",
        "scan_timestamp",
        "final_score",
        "final_label",
        "final_action",
        "distance_from_150dma",
        "profit_locker_status",
        "chart_score",
        "fundamental_score",
        "valuation_score",
        "final_smart_money_score",
        "institutional_smart_money_score",
        "institutional_net_qoq_flow_pct",
    ]

    previous_columns = [
        column for column in latest_columns if column in previous.columns
    ]

    latest_columns = [column for column in latest_columns if column in latest.columns]

    latest = latest[latest_columns].copy()
    previous = previous[previous_columns].copy()

    previous = previous.rename(
        columns={
            "scan_timestamp": "previous_scan_timestamp",
            "final_score": "previous_final_score",
            "final_label": "previous_final_label",
            "final_action": "previous_final_action",
            "distance_from_150dma": "previous_distance_from_150dma",
            "profit_locker_status": "previous_profit_locker_status",
            "chart_score": "previous_chart_score",
            "fundamental_score": "previous_fundamental_score",
            "valuation_score": "previous_valuation_score",
            "final_smart_money_score": "previous_final_smart_money_score",
            "institutional_smart_money_score": (
                "previous_institutional_smart_money_score"
            ),
            "institutional_net_qoq_flow_pct": (
                "previous_institutional_net_qoq_flow_pct"
            ),
        }
    )

    merged = latest.merge(
        previous,
        on="ticker",
        how="left",
    )

    numeric_pairs = [
        ("final_score", "previous_final_score", "final_score_change"),
        (
            "distance_from_150dma",
            "previous_distance_from_150dma",
            "distance_from_150dma_change",
        ),
        ("chart_score", "previous_chart_score", "chart_score_change"),
        (
            "fundamental_score",
            "previous_fundamental_score",
            "fundamental_score_change",
        ),
        ("valuation_score", "previous_valuation_score", "valuation_score_change"),
        (
            "final_smart_money_score",
            "previous_final_smart_money_score",
            "smart_money_score_change",
        ),
        (
            "institutional_smart_money_score",
            "previous_institutional_smart_money_score",
            "institutional_score_change",
        ),
        (
            "institutional_net_qoq_flow_pct",
            "previous_institutional_net_qoq_flow_pct",
            "institutional_flow_change",
        ),
    ]

    for latest_col, previous_col, change_col in numeric_pairs:
        if latest_col not in merged.columns:
            merged[latest_col] = 0

        if previous_col not in merged.columns:
            merged[previous_col] = 0

        merged[latest_col] = pd.to_numeric(
            merged[latest_col],
            errors="coerce",
        ).fillna(0)
        merged[previous_col] = pd.to_numeric(
            merged[previous_col],
            errors="coerce",
        ).fillna(0)

        merged[change_col] = merged[latest_col] - merged[previous_col]

    merged["score_change_label"] = merged["final_score_change"].apply(
        classify_score_change
    )

    merged["dma_cross_signal"] = merged.apply(
        lambda row: detect_150dma_cross(
            row.get("previous_distance_from_150dma", 0),
            row.get("distance_from_150dma", 0),
        ),
        axis=1,
    )

    merged["profit_locker_change"] = merged.apply(
        lambda row: detect_profit_locker_change(
            row.get("previous_distance_from_150dma", 0),
            row.get("distance_from_150dma", 0),
        ),
        axis=1,
    )

    merged["monitor_status"] = merged.apply(
        lambda row: build_monitor_status(row),
        axis=1,
    )

    priority_map = {
        "Major downgrade": 5,
        "New Profit Locker trigger": 4,
        "Broke below 150DMA": 4,
        "Downgrade": 3,
        "Major upgrade": 2,
        "Upgrade": 1,
        "Stable": 0,
    }

    merged["monitor_priority"] = (
        merged["score_change_label"].map(priority_map).fillna(0)
    )

    merged.loc[
        merged["profit_locker_change"] == "New Profit Locker trigger",
        "monitor_priority",
    ] = 5

    merged.loc[
        merged["dma_cross_signal"] == "Broke below 150DMA",
        "monitor_priority",
    ] = 5

    merged = merged.sort_values(
        by=["monitor_priority", "final_score_change"],
        ascending=[False, True],
    )

    return merged


def build_monitor_summary(change_df: pd.DataFrame) -> dict:
    if change_df is None or change_df.empty:
        return {
            "rows": 0,
            "alerts": 0,
            "upgrades": 0,
            "downgrades": 0,
            "profit_locker_triggers": 0,
            "broke_below_150dma": 0,
        }

    status_series = change_df.get("monitor_status", pd.Series(dtype=str)).astype(str)
    score_label_series = change_df.get(
        "score_change_label",
        pd.Series(dtype=str),
    ).astype(str)
    profit_locker_series = change_df.get(
        "profit_locker_change",
        pd.Series(dtype=str),
    ).astype(str)
    dma_cross_series = change_df.get(
        "dma_cross_signal",
        pd.Series(dtype=str),
    ).astype(str)

    return {
        "rows": len(change_df),
        "alerts": status_series.str.contains("Alert", case=False, na=False).sum(),
        "upgrades": score_label_series.str.contains(
            "upgrade",
            case=False,
            na=False,
        ).sum(),
        "downgrades": score_label_series.str.contains(
            "downgrade",
            case=False,
            na=False,
        ).sum(),
        "profit_locker_triggers": (
            profit_locker_series == "New Profit Locker trigger"
        ).sum(),
        "broke_below_150dma": (dma_cross_series == "Broke below 150DMA").sum(),
    }


def get_monitor_display_columns() -> list:
    return [
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
        "scan_timestamp",
        "previous_scan_timestamp",
    ]


def build_latest_monitor_report() -> tuple[pd.DataFrame, dict, list]:
    timestamps = load_recent_full_scan_timestamps(limit=2)

    if not timestamps:
        empty_summary = build_monitor_summary(pd.DataFrame())
        return pd.DataFrame(), empty_summary, []

    latest_df = load_full_scan_by_timestamp(timestamps[0])

    previous_df = pd.DataFrame()

    if len(timestamps) > 1:
        previous_df = load_full_scan_by_timestamp(timestamps[1])

    change_df = build_monitor_change_report(
        latest_df=latest_df,
        previous_df=previous_df,
    )

    summary = build_monitor_summary(change_df)

    return change_df, summary, timestamps
