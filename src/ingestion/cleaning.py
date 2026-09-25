from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def _parse_published(value: str) -> datetime | None:
    """Parse ``YYYY-MM-DD`` (or ``YYYY-MM`` / ``YYYY``) into an aware UTC datetime."""
    text = normalize_whitespace(str(value or ""))
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            parsed = datetime.strptime(text[: len(fmt)], fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """TODO(student): clean raw records thanh dataframe san sang de embed.

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
    run_date = _as_aware(run_date)
    rows: list[dict] = []
    for record in records:
        title = normalize_whitespace(record.title or "")
        summary = normalize_whitespace(record.summary or "")
        authors = [normalize_whitespace(a) for a in (record.authors or []) if str(a).strip()]
        categories = [normalize_whitespace(c) for c in (record.categories or []) if str(c).strip()]
        paper_id = normalize_whitespace(record.paper_id or "")
        if not paper_id or not title or not summary:
            continue
        published_dt = _parse_published(record.published)
        if published_dt is None:
            continue
        age_days = (run_date - published_dt).days
        authors_joined = compact_join(authors)
        categories_joined = compact_join(categories)
        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {published_dt.date().isoformat()}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        )
        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "primary_category": normalize_whitespace(record.primary_category or ""),
                "published": published_dt.date().isoformat(),
                "updated": normalize_whitespace(record.updated or ""),
                "abs_url": normalize_whitespace(record.abs_url or ""),
                "pdf_url": normalize_whitespace(record.pdf_url or ""),
                "comment": normalize_whitespace(record.comment or ""),
                "age_days": age_days,
                "summary_chars": len(summary),
                "text_for_embedding": text_for_embedding,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates(subset="paper_id", keep="first")
    df = df.sort_values(["published", "paper_id"], kind="mergesort").reset_index(drop=True)
    return df
