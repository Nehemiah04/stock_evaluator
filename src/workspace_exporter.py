from datetime import datetime
from pathlib import Path
import re
import zipfile

import pandas as pd

from src.full_scan_database import load_latest_full_scan, load_full_scan_history
from src.monitor_alert_database import load_monitor_alert_history
from src.research_notes_database import load_research_notes

EXPORT_BASE_DIR = Path("data/research_workspace")


def safe_write_csv(df: pd.DataFrame, file_path: Path) -> bool:
    if df is None or df.empty:
        return False

    file_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(file_path, index=False)
    return True


def to_float(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default

        return float(value)
    except Exception:
        return default


def safe_filename_part(value, fallback: str = "note") -> str:
    cleaned_value = str(value or fallback).strip()
    cleaned_value = cleaned_value.replace("/", "-").replace("\\", "-")
    cleaned_value = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned_value)
    cleaned_value = cleaned_value.strip("._-")

    return cleaned_value or fallback


def prepare_best_ideas_table(df: pd.DataFrame, min_score: float = 70) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    working_df = df.copy()

    if "final_score" not in working_df.columns:
        return pd.DataFrame()

    working_df["final_score"] = pd.to_numeric(
        working_df["final_score"],
        errors="coerce",
    ).fillna(0)

    working_df = working_df[working_df["final_score"] >= min_score]

    preferred_columns = [
        "ticker",
        "final_score",
        "final_label",
        "final_action",
        "current_price",
        "distance_from_150dma",
        "profit_locker_status",
        "chart_score",
        "fundamental_score",
        "valuation_score",
        "final_smart_money_score",
        "institutional_smart_money_score",
        "institutional_net_qoq_flow_pct",
        "valuation_label",
        "margin_of_safety",
    ]

    available_columns = [
        column for column in preferred_columns if column in working_df.columns
    ]

    if not available_columns:
        return pd.DataFrame()

    return working_df[available_columns].sort_values(
        by="final_score",
        ascending=False,
    )


def prepare_alert_queue(alert_history_df: pd.DataFrame) -> pd.DataFrame:
    if alert_history_df is None or alert_history_df.empty:
        return pd.DataFrame()

    working_df = alert_history_df.copy()

    preferred_columns = [
        "saved_at",
        "ticker",
        "monitor_status",
        "final_score",
        "previous_final_score",
        "final_score_change",
        "score_change_label",
        "distance_from_150dma",
        "dma_cross_signal",
        "profit_locker_change",
        "profit_locker_status",
        "valuation_score_change",
        "institutional_score_change",
        "institutional_flow_change",
    ]

    available_columns = [
        column for column in preferred_columns if column in working_df.columns
    ]

    return working_df[available_columns]


def prepare_research_notes_index(notes_df: pd.DataFrame) -> pd.DataFrame:
    if notes_df is None or notes_df.empty:
        return pd.DataFrame()

    preferred_columns = [
        "created_at",
        "source",
        "ticker",
        "title",
        "tags",
        "note_id",
        "notion_url",
    ]

    available_columns = [
        column for column in preferred_columns if column in notes_df.columns
    ]

    return notes_df[available_columns].copy()


def build_workspace_summary_markdown(
    latest_scan_df: pd.DataFrame,
    best_ideas_df: pd.DataFrame,
    alert_queue_df: pd.DataFrame,
    notes_df: pd.DataFrame,
) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    latest_scan_count = (
        0 if latest_scan_df is None or latest_scan_df.empty else len(latest_scan_df)
    )
    best_ideas_count = (
        0 if best_ideas_df is None or best_ideas_df.empty else len(best_ideas_df)
    )
    alert_count = (
        0 if alert_queue_df is None or alert_queue_df.empty else len(alert_queue_df)
    )
    note_count = 0 if notes_df is None or notes_df.empty else len(notes_df)

    top_ideas_text = "No top ideas available."

    if best_ideas_df is not None and not best_ideas_df.empty:
        top_rows = []

        for _, row in best_ideas_df.head(10).iterrows():
            ticker = row.get("ticker", "N/A")
            final_score = to_float(row.get("final_score", 0))
            final_action = row.get("final_action", "N/A")
            profit_locker_status = row.get("profit_locker_status", "N/A")

            top_rows.append(
                f"- **{ticker}** - Final Score: {final_score:.0f}/100 | "
                f"Action: {final_action} | Profit Locker: {profit_locker_status}"
            )

        top_ideas_text = "\n".join(top_rows)

    alert_text = "No saved monitor alerts available."

    if alert_queue_df is not None and not alert_queue_df.empty:
        alert_rows = []

        for _, row in alert_queue_df.head(10).iterrows():
            ticker = row.get("ticker", "N/A")
            monitor_status = row.get("monitor_status", "N/A")
            score_change = to_float(row.get("final_score_change", 0))
            profit_locker_change = row.get("profit_locker_change", "N/A")

            alert_rows.append(
                f"- **{ticker}** - {monitor_status} | "
                f"Score Change: {score_change:.2f} | "
                f"Profit Locker Change: {profit_locker_change}"
            )

        alert_text = "\n".join(alert_rows)

    return f"""
# Research Workspace Export

Generated: {generated_at}

## Export Summary

- Latest scan rows: {latest_scan_count}
- Best ideas: {best_ideas_count}
- Saved monitor alerts: {alert_count}
- Research notes: {note_count}

## Top Ideas

{top_ideas_text}

## Alert Queue

{alert_text}

## Suggested Workflow

1. Review `best_ideas.csv`.
2. Check `alert_queue.csv` for urgent monitor changes.
3. Open `latest_full_scan.csv` for the full ranked universe.
4. Review `research_notes_index.csv` for saved thesis reports.
5. Use the Markdown thesis files in `notes_markdown/` for deeper review.

## Files Included

- latest_full_scan.csv
- full_scan_history.csv
- best_ideas.csv
- monitor_alert_history.csv
- alert_queue.csv
- research_notes_index.csv
- workspace_summary.md
- notes_markdown/
""".strip()


def export_research_notes_markdown(notes_df: pd.DataFrame, notes_dir: Path) -> int:
    if notes_df is None or notes_df.empty:
        return 0

    notes_dir.mkdir(parents=True, exist_ok=True)

    saved_count = 0

    for _, row in notes_df.iterrows():
        ticker = safe_filename_part(row.get("ticker", "NOTE"), fallback="NOTE")
        source = safe_filename_part(row.get("source", "Research"), fallback="Research")
        note_id = safe_filename_part(
            row.get("note_id", saved_count), fallback=str(saved_count)
        )
        content = str(row.get("content", ""))

        file_name = f"{ticker}_{source}_{note_id}.md"
        file_path = notes_dir / file_name

        file_path.write_text(content)
        saved_count += 1

    return saved_count


def zip_export_folder(export_folder: Path) -> Path:
    zip_path = export_folder.with_suffix(".zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in export_folder.rglob("*"):
            if file_path.is_file():
                zip_file.write(
                    file_path,
                    arcname=file_path.relative_to(export_folder),
                )

    return zip_path


def build_research_workspace_export(
    min_best_idea_score: float = 70,
    scan_history_limit: int = 1000,
    alert_history_limit: int = 1000,
    notes_limit: int = 1000,
) -> dict:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    export_folder = EXPORT_BASE_DIR / f"research_workspace_{timestamp}"
    export_folder.mkdir(parents=True, exist_ok=True)

    latest_scan_df = load_latest_full_scan()
    full_scan_history_df = load_full_scan_history(limit=scan_history_limit)
    alert_history_df = load_monitor_alert_history(limit=alert_history_limit)
    notes_df = load_research_notes(limit=notes_limit)

    best_ideas_df = prepare_best_ideas_table(
        latest_scan_df,
        min_score=min_best_idea_score,
    )

    alert_queue_df = prepare_alert_queue(alert_history_df)
    notes_index_df = prepare_research_notes_index(notes_df)

    exported_files = []

    file_map = {
        "latest_full_scan.csv": latest_scan_df,
        "full_scan_history.csv": full_scan_history_df,
        "best_ideas.csv": best_ideas_df,
        "monitor_alert_history.csv": alert_history_df,
        "alert_queue.csv": alert_queue_df,
        "research_notes_index.csv": notes_index_df,
    }

    for file_name, df in file_map.items():
        file_path = export_folder / file_name

        if safe_write_csv(df, file_path):
            exported_files.append(str(file_path))

    summary_markdown = build_workspace_summary_markdown(
        latest_scan_df=latest_scan_df,
        best_ideas_df=best_ideas_df,
        alert_queue_df=alert_queue_df,
        notes_df=notes_df,
    )

    summary_path = export_folder / "workspace_summary.md"
    summary_path.write_text(summary_markdown)
    exported_files.append(str(summary_path))

    notes_dir = export_folder / "notes_markdown"
    notes_saved = export_research_notes_markdown(notes_df, notes_dir)

    if notes_saved > 0:
        exported_files.append(str(notes_dir))

    zip_path = zip_export_folder(export_folder)

    return {
        "export_folder": str(export_folder),
        "zip_path": str(zip_path),
        "exported_files": exported_files,
        "latest_scan_rows": 0 if latest_scan_df.empty else len(latest_scan_df),
        "full_history_rows": (
            0 if full_scan_history_df.empty else len(full_scan_history_df)
        ),
        "best_ideas_rows": 0 if best_ideas_df.empty else len(best_ideas_df),
        "alert_history_rows": 0 if alert_history_df.empty else len(alert_history_df),
        "research_notes_rows": 0 if notes_df.empty else len(notes_df),
        "notes_markdown_files": notes_saved,
        "summary_markdown": summary_markdown,
    }
