from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import date
from html import unescape
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref API payload into normalized paper records.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    def first_text(value: Any) -> str:
        if isinstance(value, list):
            value = value[0] if value else ""
        return normalize_whitespace(str(value or ""))

    def clean_markup(value: Any) -> str:
        text = unescape(first_text(value))
        text = re.sub(r"<[^>]+>", " ", text)
        return normalize_whitespace(text)

    def crossref_date(item: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if not isinstance(value, dict):
                continue
            parts = value.get("date-parts")
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                raw = parts[0]
                try:
                    year = int(raw[0])
                    month = int(raw[1]) if len(raw) > 1 else 1
                    day = int(raw[2]) if len(raw) > 2 else 1
                    return date(year, month, day).isoformat()
                except (TypeError, ValueError):
                    pass
            timestamp = value.get("date-time")
            if timestamp:
                return str(timestamp)[:10]
        return ""

    items = payload.get("message", {}).get("items", [])
    if not isinstance(items, list):
        return []

    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = first_text(item.get("DOI")).lower()
        title = clean_markup(item.get("title"))
        summary = clean_markup(item.get("abstract"))
        if not paper_id or not title or not summary or paper_id in seen_ids:
            continue

        authors: list[str] = []
        for author in item.get("author", []) or []:
            if not isinstance(author, dict):
                continue
            name = normalize_whitespace(
                " ".join(
                    part
                    for part in (str(author.get("given") or ""), str(author.get("family") or ""))
                    if part
                )
            )
            if name:
                authors.append(name)

        categories = [
            clean_markup(category)
            for category in (item.get("subject", []) or [])
            if clean_markup(category)
        ]
        published = crossref_date(item, "published", "published-online", "published-print", "issued")
        updated = crossref_date(item, "indexed", "created") or published
        abs_url = first_text(item.get("URL")) or f"https://doi.org/{paper_id}"

        pdf_url = ""
        for link in item.get("link", []) or []:
            if not isinstance(link, dict):
                continue
            content_type = str(link.get("content-type") or "").lower()
            if "pdf" in content_type:
                pdf_url = first_text(link.get("URL"))
                break
        if not pdf_url:
            resource = item.get("resource", {})
            if isinstance(resource, dict):
                primary = resource.get("primary", {})
                if isinstance(primary, dict):
                    pdf_url = first_text(primary.get("URL"))
        pdf_url = pdf_url or abs_url

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "Uncategorized",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=f"Crossref record {paper_id}",
            )
        )
        seen_ids.add(paper_id)
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref records with retries and offline snapshot fallback.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    if settings.paths.raw_records_json.exists() and not settings.refresh_source:
        return load_raw_records(settings.paths.raw_records_json)

    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {
        "User-Agent": "day10-data-observability-lab/0.1 (educational use)",
        "Accept": "application/json",
    }
    endpoint = "https://api.crossref.org/works"
    payload: dict[str, Any] | None = None
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            response = requests.get(endpoint, params=params, headers=headers, timeout=30)
            if response.status_code in {429, 503}:
                raise requests.HTTPError(f"Crossref returned retryable status {response.status_code}")
            response.raise_for_status()
            candidate = response.json()
            if not isinstance(candidate, dict):
                raise ValueError("Crossref response is not a JSON object.")
            payload = candidate
            write_json(settings.paths.raw_api_response, payload)
            break
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)

    if payload is None:
        if settings.paths.raw_api_response.exists():
            payload = read_json(settings.paths.raw_api_response)
        elif settings.paths.raw_records_json.exists():
            return load_raw_records(settings.paths.raw_records_json)
        else:
            raise RuntimeError("Unable to fetch Crossref data and no offline snapshot is available.") from last_error

    records = parse_crossref_payload(payload)
    if not records and settings.paths.raw_records_json.exists():
        return load_raw_records(settings.paths.raw_records_json)
    if not records:
        raise ValueError("Crossref payload did not contain any valid paper records.")

    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load a normalized raw JSON snapshot as `PaperRecord` objects."""
    payload = read_json(path)
    if isinstance(payload, dict):
        payload = payload.get("records", [])
    if not isinstance(payload, list):
        raise ValueError(f"Raw records file must contain a JSON list: {path}")

    allowed = {field.name for field in fields(PaperRecord)}
    records: list[PaperRecord] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        values = {name: row.get(name) for name in allowed}
        values["authors"] = [str(item) for item in (values.get("authors") or [])]
        values["categories"] = [str(item) for item in (values.get("categories") or [])]
        for name in allowed - {"authors", "categories"}:
            values[name] = str(values.get(name) or "")
        if values["paper_id"] and values["title"]:
            records.append(PaperRecord(**values))
    if not records:
        raise ValueError(f"No valid PaperRecord entries found in {path}")
    return records
