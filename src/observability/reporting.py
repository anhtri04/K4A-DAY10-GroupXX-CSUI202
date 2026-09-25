from __future__ import annotations

from typing import Any

from core.utils import write_text


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if value is None:
        return "N/A"
    return str(value)


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write the baseline source, evaluation, quality, and freshness report.

    Pseudo-code:
    1. Gom source summary.
    2. In metrics retrieval/evaluation.
    3. In data quality va freshness.
    4. Ghi markdown vao report_path.
    """
    ragas = metrics.get("ragas", {})
    ragas_summary = ragas.get("skipped") or ragas.get("error") or ragas
    lines = [
        "# Phase 1 — Baseline Data Pipeline Report",
        "",
        "## Source and dataset",
        "",
        "| Signal | Value |",
        "| --- | ---: |",
    ]
    for key, value in source_summary.items():
        lines.append(f"| `{key}` | {_format_value(value)} |")

    lines.extend(
        [
            "",
            "## Retrieval and answer evaluation",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
        ]
    )
    for key in ("samples", "retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        lines.append(f"| `{key}` | {_format_value(metrics.get(key))} |")
    lines.extend(["", f"Ragas: `{_format_value(ragas_summary)}`", ""])

    lines.extend(
        [
            "## Data quality",
            "",
            f"Overall quality gate: **{_format_value(quality.get('success', False))}**",
            "",
            "| Check | Result | Unexpected |",
            "| --- | --- | ---: |",
        ]
    )
    for check in quality.get("checks", []):
        lines.append(
            f"| `{check.get('name')}` | {_format_value(check.get('success'))} | "
            f"{_format_value(check.get('unexpected_count', 0))} |"
        )

    lines.extend(
        [
            "",
            "## Freshness SLA",
            "",
            "| Signal | Value |",
            "| --- | ---: |",
        ]
    )
    for key in (
        "latest_published",
        "oldest_published",
        "stale_rows",
        "total_rows",
        "stale_ratio",
        "is_fresh",
    ):
        lines.append(f"| `{key}` | {_format_value(freshness.get(key))} |")
    lines.append("")
    write_text(report_path, "\n".join(lines))


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
) -> None:
    """Write the evidence-based baseline/corrupted/repaired comparison report."""
    baseline_quality = baseline_quality or {}
    baseline_freshness = baseline_freshness or {}
    lines = [
        "# Corruption, Observability, and Repair Report",
        "",
        "## Three-state comparison",
        "",
        "| Metric or signal | Baseline | Corrupted | Repaired |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ("samples", "retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        lines.append(
            f"| `{key}` | {_format_value(baseline_metrics.get(key))} | "
            f"{_format_value(corrupted_metrics.get(key))} | {_format_value(repaired_metrics.get(key))} |"
        )
    lines.extend(
        [
            f"| Quality gate | {_format_value(baseline_quality.get('success'))} | "
            f"{_format_value(corrupted_quality.get('success'))} | "
            f"{_format_value(repaired_quality.get('success'))} |",
            f"| Freshness SLA | {_format_value(baseline_freshness.get('is_fresh'))} | "
            f"{_format_value(corrupted_freshness.get('is_fresh'))} | "
            f"{_format_value(repaired_freshness.get('is_fresh'))} |",
            f"| Stale ratio | {_format_value(baseline_freshness.get('stale_ratio'))} | "
            f"{_format_value(corrupted_freshness.get('stale_ratio'))} | "
            f"{_format_value(repaired_freshness.get('stale_ratio'))} |",
            f"| Repair matches baseline | N/A | N/A | "
            f"{_format_value(repaired_metrics.get('repair_matches_baseline'))} |",
            "",
            "## Interpretation",
            "",
        ]
    )

    hit_drop = float(baseline_metrics.get("retrieval_hit_rate", 0.0)) - float(
        corrupted_metrics.get("retrieval_hit_rate", 0.0)
    )
    f1_drop = float(baseline_metrics.get("mean_token_f1", 0.0)) - float(
        corrupted_metrics.get("mean_token_f1", 0.0)
    )
    lines.append(
        f"- Controlled corruption changed retrieval hit rate by **{-hit_drop:+.4f}** and mean token F1 by "
        f"**{-f1_drop:+.4f}** relative to baseline."
    )
    lines.append(
        f"- The corrupted quality gate was **{_format_value(corrupted_quality.get('success'))}**; "
        f"freshness was **{_format_value(corrupted_freshness.get('is_fresh'))}**."
    )
    lines.append(
        "- Repair regenerated the dataset from the immutable raw snapshot and rebuilt a separate vector collection; "
        f"the repaired dataset matches baseline: **{_format_value(repaired_metrics.get('repair_matches_baseline'))}**."
    )
    lines.append("")
    write_text(report_path, "\n".join(lines))
