from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a deterministic embedding-ready dataframe.

    Pseudo-code:
    1. Normalize title, summary, authors, categories.
    2. Parse published/updated date.
    3. Tinh age_days.
    4. Tao cot helper:
       - authors_joined
       - categories_joined
       - summary_chars
       - text_for_embedding
    5. Drop duplicates va filter row xau.
    6. Sort dataframe va return.
    """
    if not records:
        raise ValueError("Cannot build a clean dataframe from an empty record list.")

    run_timestamp = pd.Timestamp(run_date)
    if run_timestamp.tzinfo is not None:
        run_timestamp = run_timestamp.tz_convert("UTC").tz_localize(None)

    def clean_list(values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = normalize_whitespace(str(value or ""))
            key = item.casefold()
            if item and key not in seen:
                cleaned.append(item)
                seen.add(key)
        return cleaned

    def parse_date(value: str) -> pd.Timestamp | None:
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(parsed):
            return None
        return pd.Timestamp(parsed).tz_convert("UTC").tz_localize(None)

    rows: list[dict[str, Any]] = []
    for record in records:
        paper_id = normalize_whitespace(record.paper_id).lower()
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)
        authors = clean_list(record.authors)
        categories = clean_list(record.categories)
        published_at = parse_date(record.published)
        updated_at = parse_date(record.updated) or published_at
        if not paper_id or not title or len(summary) < 30 or published_at is None:
            continue

        authors_joined = compact_join(authors) or "Unknown"
        categories_joined = compact_join(categories) or "Uncategorized"
        published = published_at.date().isoformat()
        updated = updated_at.date().isoformat() if updated_at is not None else published
        text_for_embedding = "\n".join(
            [
                f"Title: {title}",
                f"Authors: {authors_joined}",
                f"Published: {published}",
                f"Categories: {categories_joined}",
                f"Summary: {summary}",
            ]
        )
        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": normalize_whitespace(record.primary_category) or categories_joined.split(",")[0],
                "published": published,
                "updated": updated,
                "abs_url": normalize_whitespace(record.abs_url),
                "pdf_url": normalize_whitespace(record.pdf_url),
                "comment": normalize_whitespace(record.comment),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "age_days": max(0, int((run_timestamp - published_at).days)),
                "text_for_embedding": text_for_embedding,
            }
        )

    if not rows:
        raise ValueError("Cleaning removed every record; inspect the raw data contract.")

    dataframe = pd.DataFrame(rows)
    dataframe = dataframe.drop_duplicates(subset=["paper_id"], keep="first")
    dataframe = dataframe.sort_values(["published", "paper_id"], ascending=[False, True])
    return dataframe.reset_index(drop=True)
