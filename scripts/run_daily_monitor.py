from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.full_evaluator import DEFAULT_VALUATION_ASSUMPTIONS, evaluate_full_watchlist
from src.full_scan_database import save_full_scan_results
from src.institution_map import load_institution_universe
from src.institutional_holdings import (
    load_institution_holdings_sample,
    merge_holdings_with_universe,
)
from src.monitor import build_latest_monitor_report
from src.monitor_alert_database import save_monitor_alerts
from src.watchlist_loader import load_watchlist_tickers

EXPORT_DIR = Path("data/exports")


def get_institutional_holdings_fallback() -> pd.DataFrame:
    """
    Terminal version of institutional holdings loader.

    Uses Sample CSV because SEC/FMP loading is better controlled inside Streamlit.
    """

    try:
        universe_df = load_institution_universe("data/smart_money_universe.csv")
        holdings_df = load_institution_holdings_sample(
            "data/institution_holdings_sample.csv"
        )

        merged_df = merge_holdings_with_universe(
            holdings_df=holdings_df,
            universe_df=universe_df,
        )

        return merged_df
    except Exception as error:
        print(f"Warning: could not load institutional holdings fallback: {error}")
        return pd.DataFrame()


def run_daily_monitor(max_tickers: int | None = None) -> dict:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 80)
    print("DAILY STOCK MONITOR RUNNER")
    print("=" * 80)

    tickers = load_watchlist_tickers("data/watchlist.csv")

    if max_tickers is not None:
        tickers = tickers[: int(max_tickers)]

    if not tickers:
        print("No tickers found in data/watchlist.csv.")
        return {
            "status": "error",
            "message": "No tickers found.",
        }

    print(f"Tickers loaded: {len(tickers)}")
    print(", ".join(tickers[:25]))

    institutional_holdings_df = get_institutional_holdings_fallback()

    print(f"Institutional holding rows loaded: {len(institutional_holdings_df)}")

    print("-" * 80)
    print("Running full evaluator...")

    scan_results_df = evaluate_full_watchlist(
        tickers=tickers,
        institutional_holdings_df=institutional_holdings_df,
        manual_smart_money_score=0,
        valuation_assumptions=DEFAULT_VALUATION_ASSUMPTIONS,
    )

    if scan_results_df.empty:
        print("No scan results generated.")
        return {
            "status": "error",
            "message": "No scan results generated.",
        }

    saved_rows = save_full_scan_results(scan_results_df)

    scan_export_path = EXPORT_DIR / f"daily_full_scan_{run_timestamp}.csv"
    scan_results_df.to_csv(scan_export_path, index=False)

    print(f"Saved scan rows to database: {saved_rows}")
    print(f"Exported full scan: {scan_export_path}")

    print("-" * 80)
    print("Building monitor comparison...")

    change_df, monitor_summary, monitor_timestamps = build_latest_monitor_report()

    monitor_export_path = EXPORT_DIR / f"daily_monitor_report_{run_timestamp}.csv"

    if not change_df.empty:
        change_df.to_csv(monitor_export_path, index=False)

    print(f"Monitor rows: {monitor_summary.get('rows', 0)}")
    print(f"Alerts: {monitor_summary.get('alerts', 0)}")
    print(f"Upgrades: {monitor_summary.get('upgrades', 0)}")
    print(f"Downgrades: {monitor_summary.get('downgrades', 0)}")
    print(f"Profit Locker triggers: {monitor_summary.get('profit_locker_triggers', 0)}")
    print(f"Broke below 150DMA: {monitor_summary.get('broke_below_150dma', 0)}")

    if monitor_timestamps:
        print("Scan timestamps compared:")

        for timestamp in monitor_timestamps:
            print(f"- {timestamp}")

    if not change_df.empty:
        print(f"Exported monitor report: {monitor_export_path}")

    saved_alert_rows = save_monitor_alerts(
        monitor_df=change_df,
        monitor_timestamps=monitor_timestamps,
        save_only_important=True,
    )

    print(f"Saved important monitor alerts: {saved_alert_rows}")

    print("=" * 80)
    print("DAILY MONITOR COMPLETE")
    print("=" * 80)

    return {
        "status": "ok",
        "tickers": len(tickers),
        "scan_rows": len(scan_results_df),
        "saved_rows": saved_rows,
        "monitor_rows": monitor_summary.get("rows", 0),
        "alerts": monitor_summary.get("alerts", 0),
        "saved_alert_rows": saved_alert_rows,
        "scan_export_path": str(scan_export_path),
        "monitor_export_path": str(monitor_export_path),
    }


if __name__ == "__main__":
    max_tickers_arg = None

    if len(sys.argv) > 1:
        try:
            max_tickers_arg = int(sys.argv[1])
        except Exception:
            max_tickers_arg = None

    result = run_daily_monitor(max_tickers=max_tickers_arg)

    if result.get("status") != "ok":
        sys.exit(1)
