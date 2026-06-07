import os
import re

import requests

NOTION_API_BASE_URL = "https://api.notion.com/v1"
NOTION_API_VERSION = "2022-06-28"
MAX_RICH_TEXT_LENGTH = 1900
MAX_BLOCKS_PER_REQUEST = 100


class NotionExportError(Exception):
    pass


def get_notion_token(token: str | None = None) -> str:
    token = (token or "").strip()

    if token:
        return token

    return (
        os.getenv("NOTION_TOKEN")
        or os.getenv("NOTION_API_KEY")
        or os.getenv("NOTION_INTEGRATION_TOKEN")
        or ""
    ).strip()


def normalize_notion_id(value: str) -> str:
    value = str(value or "").strip()

    if not value:
        return ""

    matches = re.findall(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32}",
        value,
    )

    if not matches:
        return value

    raw_id = matches[-1].replace("-", "")

    return (
        f"{raw_id[0:8]}-"
        f"{raw_id[8:12]}-"
        f"{raw_id[12:16]}-"
        f"{raw_id[16:20]}-"
        f"{raw_id[20:32]}"
    )


def build_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


def notion_request(
    method: str,
    endpoint: str,
    token: str,
    payload: dict | None = None,
) -> dict:
    url = f"{NOTION_API_BASE_URL}{endpoint}"

    response = requests.request(
        method,
        url,
        headers=build_headers(token),
        json=payload,
        timeout=30,
    )

    if response.status_code >= 400:
        raise NotionExportError(
            f"Notion returned {response.status_code}: {response.text}"
        )

    if not response.text:
        return {}

    return response.json()


def chunk_text(text: str, chunk_size: int = MAX_RICH_TEXT_LENGTH) -> list[str]:
    text = str(text or "")

    if not text:
        return [""]

    return [
        text[index : index + chunk_size] for index in range(0, len(text), chunk_size)
    ]


def make_rich_text(text: str) -> list:
    return [
        {
            "type": "text",
            "text": {
                "content": chunk,
            },
        }
        for chunk in chunk_text(text)
    ]


def make_text_block(block_type: str, text: str) -> dict:
    return {
        "object": "block",
        "type": block_type,
        block_type: {
            "rich_text": make_rich_text(text),
        },
    }


def flush_paragraph(paragraph_lines: list[str], blocks: list[dict]):
    if not paragraph_lines:
        return

    paragraph = " ".join(line.strip() for line in paragraph_lines if line.strip())

    if paragraph:
        blocks.append(make_text_block("paragraph", paragraph))

    paragraph_lines.clear()


def content_to_notion_blocks(content: str) -> list[dict]:
    blocks = []
    paragraph_lines = []

    for raw_line in str(content or "").splitlines():
        line = raw_line.strip()

        if not line:
            flush_paragraph(paragraph_lines, blocks)
            continue

        if line in {"---", "***", "___"}:
            flush_paragraph(paragraph_lines, blocks)
            blocks.append(
                {
                    "object": "block",
                    "type": "divider",
                    "divider": {},
                }
            )
            continue

        if line.startswith("### "):
            flush_paragraph(paragraph_lines, blocks)
            blocks.append(make_text_block("heading_3", line[4:].strip()))
            continue

        if line.startswith("## "):
            flush_paragraph(paragraph_lines, blocks)
            blocks.append(make_text_block("heading_2", line[3:].strip()))
            continue

        if line.startswith("# "):
            flush_paragraph(paragraph_lines, blocks)
            blocks.append(make_text_block("heading_1", line[2:].strip()))
            continue

        if line.startswith("- "):
            flush_paragraph(paragraph_lines, blocks)
            blocks.append(make_text_block("bulleted_list_item", line[2:].strip()))
            continue

        paragraph_lines.append(line)

    flush_paragraph(paragraph_lines, blocks)

    return blocks


def append_blocks_to_page(page_id: str, blocks: list[dict], token: str):
    if not blocks:
        return

    for index in range(0, len(blocks), MAX_BLOCKS_PER_REQUEST):
        notion_request(
            "PATCH",
            f"/blocks/{page_id}/children",
            token=token,
            payload={
                "children": blocks[index : index + MAX_BLOCKS_PER_REQUEST],
            },
        )


def get_database_properties(database_id: str, token: str) -> dict:
    database = notion_request("GET", f"/databases/{database_id}", token=token)
    return database.get("properties", {})


def find_title_property_name(database_properties: dict) -> str:
    for name, config in database_properties.items():
        if config.get("type") == "title":
            return name

    return "Name"


def build_database_property_value(property_config: dict, value: str):
    property_type = property_config.get("type")

    if property_type == "rich_text":
        return {"rich_text": make_rich_text(value)}

    if property_type == "select":
        return {"select": {"name": value}}

    if property_type == "multi_select":
        values = [
            {"name": item.strip()} for item in str(value).split(",") if item.strip()
        ]
        return {"multi_select": values}

    if property_type == "url":
        return {"url": value}

    return None


def build_database_properties(
    database_id: str,
    token: str,
    title: str,
    source: str,
    ticker: str,
    tags: str,
) -> dict:
    database_properties = get_database_properties(database_id, token)
    title_property_name = find_title_property_name(database_properties)

    properties = {
        title_property_name: {
            "title": make_rich_text(title),
        }
    }

    optional_values = {
        "Source": source,
        "Ticker": ticker,
        "Tags": tags,
    }

    for property_name, value in optional_values.items():
        if property_name not in database_properties:
            continue

        property_value = build_database_property_value(
            database_properties[property_name],
            value,
        )

        if property_value is not None:
            properties[property_name] = property_value

    return properties


def create_notion_page(
    token: str,
    destination_id: str,
    destination_type: str,
    title: str,
    source: str,
    ticker: str,
    tags: str,
) -> dict:
    destination_id = normalize_notion_id(destination_id)
    destination_type = str(destination_type or "Page").strip().lower()

    if destination_type == "database":
        parent = {"database_id": destination_id}
        properties = build_database_properties(
            database_id=destination_id,
            token=token,
            title=title,
            source=source,
            ticker=ticker,
            tags=tags,
        )
    else:
        parent = {"page_id": destination_id}
        properties = {
            "title": make_rich_text(title),
        }

    return notion_request(
        "POST",
        "/pages",
        token=token,
        payload={
            "parent": parent,
            "properties": properties,
        },
    )


def publish_to_notion_workspace(
    title: str,
    content: str,
    source: str,
    ticker: str = "",
    tags: str = "",
    token: str | None = None,
    destination_id: str = "",
    destination_type: str = "Page",
) -> dict:
    token = get_notion_token(token)

    if not token:
        raise NotionExportError(
            "Add a Notion integration token in the sidebar or set NOTION_TOKEN."
        )

    if not str(destination_id or "").strip():
        raise NotionExportError(
            "Add a Notion destination page or database ID in the sidebar."
        )

    page = create_notion_page(
        token=token,
        destination_id=destination_id,
        destination_type=destination_type,
        title=title,
        source=source,
        ticker=ticker,
        tags=tags,
    )

    blocks = content_to_notion_blocks(content)

    append_blocks_to_page(
        page_id=page["id"],
        blocks=blocks,
        token=token,
    )

    return {
        "id": page.get("id"),
        "url": page.get("url"),
    }
