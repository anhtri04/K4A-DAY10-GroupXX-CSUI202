from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import safe_slug, write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run the GX 1.x quality gate plus freshness monitoring.

    Pseudo-code:
    1. Check row count.
    2. Check `paper_id` not null va unique.
    3. Check `title` not null.
    4. Check do dai `summary`.
    5. Check freshness bang `age_days`.
    6. Ghi ket qua vao `data/quality/`.
    """
    import great_expectations as gx
    from great_expectations import expectations as gxe

    required = {"paper_id", "title", "summary", "text_for_embedding", "age_days", "published"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Cannot run quality checks; missing columns: {sorted(missing)}")

    context = gx.get_context(mode="ephemeral")
    suffix = safe_slug(report_name)
    data_source = context.data_sources.add_pandas(name=f"papers_source_{suffix}")
    data_asset = data_source.add_dataframe_asset(name=f"papers_asset_{suffix}")
    batch_definition = data_asset.add_batch_definition_whole_dataframe(f"papers_batch_{suffix}")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    checks = [
        (
            "row_count_between_5_and_5000",
            gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000),
        ),
        ("paper_id_not_null", gxe.ExpectColumnValuesToNotBeNull(column="paper_id")),
        ("title_not_null", gxe.ExpectColumnValuesToNotBeNull(column="title")),
        (
            "text_for_embedding_not_null",
            gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"),
        ),
        ("paper_id_unique", gxe.ExpectColumnValuesToBeUnique(column="paper_id")),
        (
            "summary_length_between_30_and_100000",
            gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30, max_value=100000),
        ),
    ]

    check_results: list[dict[str, Any]] = []
    for name, expectation in checks:
        result = batch.validate(expectation)
        result_payload = result.to_json_dict()
        details = result_payload.get("result", {})
        check_results.append(
            {
                "name": name,
                "expectation_type": expectation.__class__.__name__,
                "success": bool(result.success),
                "observed_value": details.get("observed_value"),
                "unexpected_count": details.get("unexpected_count", 0),
                "unexpected_percent": details.get("unexpected_percent", 0.0),
            }
        )

    freshness_path = (
        settings.paths.freshness_report
        if suffix == "baseline"
        else settings.paths.quality_dir / f"{suffix}_freshness_report.json"
    )
    freshness = build_freshness_report(df, settings, freshness_path)
    gx_success = all(item["success"] for item in check_results)
    payload = {
        "report_name": report_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "success": gx_success and freshness["is_fresh"],
        "gx_success": gx_success,
        "freshness_success": freshness["is_fresh"],
        "checks": check_results,
        "freshness": freshness,
    }

    report_path = settings.paths.quality_dir / f"{suffix}_quality_report.json"
    write_json(report_path, payload)
    write_json(settings.paths.gx_dir / f"{suffix}_validation.json", payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Build and persist a freshness SLA report.

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
    if "published" not in df.columns:
        raise ValueError("Freshness reporting requires the 'published' column.")

    published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    if "age_days" in df.columns:
        ages = pd.to_numeric(df["age_days"], errors="coerce")
    else:
        now = pd.Timestamp.now(tz="UTC")
        ages = (now - published).dt.days

    total_rows = int(len(df))
    stale_mask = ages > settings.freshness_threshold_days
    stale_rows = int(stale_mask.fillna(True).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    valid_published = published.dropna()
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "threshold_days": settings.freshness_threshold_days,
        "maximum_stale_ratio": 0.25,
        "latest_published": valid_published.max().date().isoformat() if not valid_published.empty else None,
        "oldest_published": valid_published.min().date().isoformat() if not valid_published.empty else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "is_fresh": bool(total_rows > 0 and stale_ratio <= 0.25),
    }
    write_json(report_path, payload)
    return payload
