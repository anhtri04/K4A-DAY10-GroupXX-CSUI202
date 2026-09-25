from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path

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


def _strip_tags(text: str) -> str:
    """Remove JATS/HTML tags like <jats:p> and normalize whitespace."""
    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    return normalize_whitespace(no_tags)


def _parse_date_parts(value) -> str:
    """Parse Crossref ``date-parts`` ([[Y, M, D]]) into ``YYYY-MM-DD``.

    Handles partial dates ([Y] or [Y, M]) by defaulting missing parts to 1.
    Returns "" when unparseable.
    """
    try:
        parts = value.get("date-parts", [[]])[0] if isinstance(value, dict) else []
        if not parts:
            return ""
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (ValueError, TypeError, IndexError):
        return ""


def _parse_authors(raw_authors) -> list[str]:
    authors: list[str] = []
    for author in raw_authors or []:
        if not isinstance(author, dict):
            continue
        given = normalize_whitespace(str(author.get("given", "") or ""))
        family = normalize_whitespace(str(author.get("family", "") or ""))
        full = normalize_whitespace(f"{given} {family}".strip())
        if full:
            authors.append(full)
    return authors


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """TODO(student): parse Crossref payload thanh list PaperRecord.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    items = payload.get("message", {}).get("items", []) if isinstance(payload, dict) else []
    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        doi = normalize_whitespace(str(item.get("DOI", "") or ""))
        raw_title = item.get("title", [])
        title = normalize_whitespace(str(raw_title[0]) if raw_title else "")
        if not doi or not title:
            continue
        summary = _strip_tags(str(item.get("abstract", "") or ""))
        authors = _parse_authors(item.get("author", []))
        categories = [normalize_whitespace(str(c)) for c in (item.get("subject", []) or []) if str(c).strip()]
        primary_category = categories[0] if categories else ""
        published = _parse_date_parts(item.get("published")) or _parse_date_parts(item.get("created"))
        created_dt = str((item.get("created") or {}).get("date-time", "") or "")
        updated = created_dt[:10] if len(created_dt) >= 10 else published
        url = normalize_whitespace(str(item.get("URL", "") or ""))
        abs_url = url or f"https://doi.org/{doi}"
        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=url or abs_url,
                comment=f"Crossref record {doi}",
            )
        )
    return records


def _save_records(records: list[PaperRecord], path: Path) -> None:
    write_json(path, [asdict(record) for record in records])


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """TODO(student): goi source API, luu raw response, parse thanh records.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.

    Offline fallback: neu API loi (mat mang / 429 / 503) ma snapshot local
    da ton tai thi doc lai snapshot thay vi crash.
    Neu `refresh_source=False` va ca 2 file raw da ton tai thi bo qua API
    va load thang tu snapshot (che do Dev/Offline).
    """
    raw_response_path = settings.paths.raw_api_response
    raw_records_path = settings.paths.raw_records_json

    # Dev/Offline fast path: reuse snapshots when refresh is not requested.
    if not settings.refresh_source and raw_response_path.exists() and raw_records_path.exists():
        return load_raw_records(raw_records_path)

    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "select": "DOI,title,abstract,author,subject,published,created,URL",
    }
    url = "https://api.crossref.org/works"
    headers = {"User-Agent": "Day10-Data-Pipeline-Lab/0.1.0 (mailto:student@example.com)"}

    payload: dict | None = None
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code in (429, 500, 502, 503):
                last_error = RuntimeError(f"Crossref status {response.status_code}")
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            payload = response.json()
            break
        except Exception as exc:  # network error, timeout, bad JSON, ...
            last_error = exc
            time.sleep(2**attempt)

    if payload is None:
        # Offline rescue: fall back to local snapshot instead of crashing.
        if raw_response_path.exists() and raw_records_path.exists():
            return load_raw_records(raw_records_path)
        raise RuntimeError(f"Crossref fetch failed and no local snapshot found: {last_error}")

    write_json(raw_response_path, payload)
    records = parse_crossref_payload(payload)
    _save_records(records, raw_records_path)
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """TODO(student): doc JSON snapshot va map thanh `PaperRecord`."""
    raw = read_json(path)
    if isinstance(raw, dict) and "records" in raw:
        raw = raw["records"]
    allowed = {field.name for field in fields(PaperRecord)}
    records: list[PaperRecord] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        records.append(PaperRecord(**{key: item.get(key) for key in allowed}))
    return records
