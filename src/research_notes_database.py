from datetime import datetime
from pathlib import Path
import hashlib
import sqlite3

import pandas as pd

DB_PATH = Path("data/stocks.db")

RESEARCH_NOTE_COLUMNS = [
    "note_id",
    "created_at",
    "source",
    "ticker",
    "title",
    "tags",
    "content",
    "notion_url",
    "destination_type",
    "destination_id",
]


def get_connection(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def create_research_notes_table(db_path: Path = DB_PATH):
    with get_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_notes (
                note_id TEXT PRIMARY KEY,
                created_at TEXT,
                source TEXT,
                ticker TEXT,
                title TEXT,
                tags TEXT,
                content TEXT,
                notion_url TEXT,
                destination_type TEXT,
                destination_id TEXT
            )
            """)


def safe_text(value) -> str:
    if value is None:
        return ""

    return str(value).strip()


def build_note_id(
    created_at: str,
    title: str,
    source: str,
    ticker: str,
    content: str,
) -> str:
    raw_value = f"{created_at}|{title}|{source}|{ticker}|{content}"
    note_hash = hashlib.sha256(raw_value.encode("utf-8")).hexdigest()[:16]

    return f"{created_at}_{ticker or source}_{note_hash}".replace(":", "-").replace(
        " ",
        "_",
    )


def save_research_note(
    title: str,
    content: str,
    source: str,
    ticker: str = "",
    tags: str = "",
    notion_url: str = "",
    destination_type: str = "",
    destination_id: str = "",
    db_path: Path = DB_PATH,
) -> str:
    create_research_notes_table(db_path)

    cleaned_content = safe_text(content)

    if not cleaned_content:
        return ""

    created_at = datetime.now().isoformat(timespec="seconds")
    cleaned_title = safe_text(title)
    cleaned_source = safe_text(source)
    cleaned_ticker = safe_text(ticker).upper()

    note_id = build_note_id(
        created_at=created_at,
        title=cleaned_title,
        source=cleaned_source,
        ticker=cleaned_ticker,
        content=cleaned_content,
    )

    note_df = pd.DataFrame(
        [
            {
                "note_id": note_id,
                "created_at": created_at,
                "source": cleaned_source,
                "ticker": cleaned_ticker,
                "title": cleaned_title,
                "tags": safe_text(tags),
                "content": cleaned_content,
                "notion_url": safe_text(notion_url),
                "destination_type": safe_text(destination_type),
                "destination_id": safe_text(destination_id),
            }
        ],
        columns=RESEARCH_NOTE_COLUMNS,
    )

    with get_connection(db_path) as conn:
        note_df.to_sql(
            "research_notes",
            conn,
            if_exists="append",
            index=False,
        )

    return note_id


def load_research_notes(
    limit: int = 1000,
    source_filter: str = "",
    ticker_filter: str = "",
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    create_research_notes_table(db_path)

    query = """
        SELECT *
        FROM research_notes
        ORDER BY created_at DESC
        LIMIT ?
    """

    try:
        with get_connection(db_path) as conn:
            df = pd.read_sql_query(query, conn, params=(int(limit),))
    except Exception:
        return pd.DataFrame(columns=RESEARCH_NOTE_COLUMNS)

    if df.empty:
        return df

    if source_filter:
        df = df[
            df["source"].astype(str).str.contains(source_filter, case=False, na=False)
        ]

    if ticker_filter:
        ticker_filter = str(ticker_filter).upper().strip()
        df = df[
            df["ticker"].astype(str).str.upper().str.contains(ticker_filter, na=False)
        ]

    return df
