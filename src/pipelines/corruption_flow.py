from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import dataframe_records, now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_corruption_report
from pipelines.phase1 import main as run_phase1
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run corruption, evaluation, raw-source repair, and comparison.

    Pseudo-code:
    1. Load baseline metrics va clean dataset.
    2. Tao corrupted dataframe.
    3. Save corrupted artifacts.
    4. Rebuild index va evaluate.
    5. Run quality checks/freshness tren corrupted data.
    6. Repair lai tu raw records.
    7. Evaluate repaired dataset.
    8. Tao comparison report.
    """
    settings = load_settings()
    baseline_requirements = [
        settings.paths.clean_json,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
    ]
    if any(not path.exists() for path in baseline_requirements):
        print("Baseline artifacts are missing; running Phase 1 first.")
        run_phase1()

    baseline_df = pd.DataFrame(read_json(settings.paths.clean_json))
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline_quality = read_json(settings.paths.baseline_quality_report)
    baseline_freshness = read_json(settings.paths.freshness_report)

    corrupted_df = corrupt_clean_dataframe(baseline_df, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, dataframe_records(corrupted_df))
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings=settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    corrupted_evaluation = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")

    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, now_utc())
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, dataframe_records(repaired_df))
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings=settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    repaired_evaluation = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")

    repair_matches_baseline = dataframe_records(repaired_df) == dataframe_records(baseline_df)
    repaired_evaluation.summary["repair_matches_baseline"] = repair_matches_baseline
    repaired_evaluation.summary["repaired_rows"] = len(repaired_df)
    write_json(settings.paths.repaired_metrics, repaired_evaluation.summary)

    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_evaluation.summary,
        repaired_metrics=repaired_evaluation.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_quality["freshness"],
        repaired_freshness=repaired_quality["freshness"],
        baseline_quality=baseline_quality,
        baseline_freshness=baseline_freshness,
    )

    print("Corruption and repair pipeline completed successfully.")
    print("State       Hit Rate   Token F1   Quality   Freshness")
    print(
        f"Baseline    {baseline_metrics['retrieval_hit_rate']:.4f}     "
        f"{baseline_metrics['mean_token_f1']:.4f}     "
        f"{baseline_quality['success']}      {baseline_freshness['is_fresh']}"
    )
    print(
        f"Corrupted   {corrupted_evaluation.summary['retrieval_hit_rate']:.4f}     "
        f"{corrupted_evaluation.summary['mean_token_f1']:.4f}     "
        f"{corrupted_quality['success']}     {corrupted_quality['freshness']['is_fresh']}"
    )
    print(
        f"Repaired    {repaired_evaluation.summary['retrieval_hit_rate']:.4f}     "
        f"{repaired_evaluation.summary['mean_token_f1']:.4f}     "
        f"{repaired_quality['success']}      {repaired_quality['freshness']['is_fresh']}"
    )
    print(f"Repair matches baseline: {repair_matches_baseline}")
    print(f"Report: {settings.paths.comparison_report}")
