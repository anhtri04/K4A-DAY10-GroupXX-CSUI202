from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json


def _resolve_report_path(settings: Settings, report_name: str) -> Path:
    name = (report_name or "baseline").strip().lower()
    if name == "baseline":
        return settings.paths.baseline_quality_report
    if name == "corrupted":
        return settings.paths.corrupted_quality_report
    return settings.paths.quality_dir / f"{report_name}_quality_report.json"


def _manual_checks(df: pd.DataFrame, threshold_days: int) -> dict[str, Any]:
    """Pandas ground truth for the 4 required expectations + freshness."""
    total = len(df)
    row_count_ok = 5 <= total <= 5000
    paper_id_ok = bool(total) and df["paper_id"].notna().all() and (df["paper_id"].astype(str).str.strip() != "").all()
    title_ok = bool(total) and df["title"].notna().all() and (df["title"].astype(str).str.strip() != "").all()
    text_ok = (
        bool(total)
        and "text_for_embedding" in df.columns
        and df["text_for_embedding"].notna().all()
        and (df["text_for_embedding"].astype(str).str.strip() != "").all()
    )
    unique_ok = bool(total) and not df["paper_id"].astype(str).duplicated().any()
    summary_ok = bool(total) and "summary" in df.columns and (df["summary"].astype(str).str.len() >= 30).all()
    if "age_days" in df.columns:
        stale_rows = int((pd.to_numeric(df["age_days"], errors="coerce").fillna(10**9) > threshold_days).sum())
    else:
        stale_rows = 0
    stale_ratio = (stale_rows / total) if total else 1.0
    is_fresh = stale_ratio <= 0.25
    success = all([row_count_ok, paper_id_ok, title_ok, text_ok, unique_ok, summary_ok])
    return {
        "row_count_ok": bool(row_count_ok),
        "paper_id_not_null": bool(paper_id_ok),
        "title_not_null": bool(title_ok),
        "text_for_embedding_not_null": bool(text_ok),
        "paper_id_unique": bool(unique_ok),
        "summary_length_ok": bool(summary_ok),
        "success": bool(success),
        "total_rows": int(total),
        "stale_rows": int(stale_rows),
        "stale_ratio": float(stale_ratio),
        "is_fresh": bool(is_fresh),
    }


def _run_gx_suite(df: pd.DataFrame, suite_name: str) -> dict[str, Any]:
    """Run the 4 required expectations through GX 1.x (ephemeral, RAM-only).

    Raises on any GX API mismatch so the caller can fall back to manual checks.
    """
    import great_expectations as gx
    import great_expectations.expectations as gxe

    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = gx.ExpectationSuite(name=suite_name)
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    for column in ("paper_id", "title", "text_for_embedding"):
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=column))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))

    validation_def = gx.ValidationDefinition(data=batch_def, suite=suite, name=f"{suite_name}_validation")
    result = validation_def.run(batch_parameters={"dataframe": df})
    return {
        "gx_success": bool(result.success),
        "gx_results": [r.to_json_dict() for r in result.results],
        "batch_id": str(getattr(batch, "id", batch_def.name)),
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """TODO(student): tao bo data quality checks.

    Pseudo-code:
    1. Check row count.
    2. Check `paper_id` not null va unique.
    3. Check `title` not null.
    4. Check do dai `summary`.
    5. Check freshness bang `age_days`.
    6. Ghi ket qua vao `data/quality/`.
    """
    threshold = settings.freshness_threshold_days
    manual = _manual_checks(df, threshold)
    payload: dict[str, Any] = {
        "report_name": report_name,
        "suite": "papers_quality",
        "row_count": manual["total_rows"],
        "checks": {
            "row_count_5_5000": manual["row_count_ok"],
            "paper_id_not_null": manual["paper_id_not_null"],
            "title_not_null": manual["title_not_null"],
            "text_for_embedding_not_null": manual["text_for_embedding_not_null"],
            "paper_id_unique": manual["paper_id_unique"],
            "summary_min_length_30": manual["summary_length_ok"],
        },
        "freshness": {
            "threshold_days": threshold,
            "stale_rows": manual["stale_rows"],
            "total_rows": manual["total_rows"],
            "stale_ratio": manual["stale_ratio"],
            "is_fresh": manual["is_fresh"],
        },
        "success": manual["success"],
        "engine": "manual",
    }
    try:
        gx_info = _run_gx_suite(df, f"papers_{report_name}")
        payload["engine"] = "great_expectations"
        payload["gx"] = gx_info
        # GX is authoritative when it runs; keep manual as cross-check.
        payload["success"] = bool(gx_info["gx_success"] and manual["success"])
    except Exception as exc:
        payload["gx_error"] = f"{type(exc).__name__}: {exc}"
    report_path = _resolve_report_path(settings, report_name)
    write_json(report_path, payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """TODO(student): tong hop freshness report.

    Pseudo-code:
    1. Tim latest va oldest published date.
    2. Dem so dong stale.
    3. Tao payload:
       - latest_published
       - oldest_published
       - stale_rows
       - total_rows
       - is_fresh
    4. Ghi JSON report.
    """
    threshold = settings.freshness_threshold_days
    total = len(df)
    published = pd.to_datetime(df["published"], errors="coerce") if "published" in df.columns else pd.Series([], dtype="datetime64[ns]")
    if "age_days" in df.columns:
        ages = pd.to_numeric(df["age_days"], errors="coerce")
        stale_rows = int((ages > threshold).sum())
    else:
        stale_rows = 0
    stale_ratio = (stale_rows / total) if total else 1.0
    payload = {
        "threshold_days": threshold,
        "total_rows": int(total),
        "stale_rows": int(stale_rows),
        "stale_ratio": float(stale_ratio),
        "is_fresh": bool(stale_ratio <= 0.25),
        "latest_published": published.max().date().isoformat() if total and published.notna().any() else None,
        "oldest_published": published.min().date().isoformat() if total and published.notna().any() else None,
    }
    write_json(Path(report_path), payload)
    return payload
