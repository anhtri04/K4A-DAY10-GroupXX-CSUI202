from __future__ import annotations

from core.config import load_settings
from core.utils import dataframe_records, now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


def main() -> None:
    """Run the complete clean-data baseline pipeline.

    Pseudo-code:
    1. Load settings.
    2. Load hoac fetch raw records.
    3. Clean data.
    4. Save clean CSV/JSON.
    5. Build Chroma index.
    6. Tao hoac load evaluation set.
    7. Evaluate.
    8. Run quality checks va freshness report.
    9. Tao markdown report.
    10. Co the demo agent tren vai sample question.
    """
    settings = load_settings()
    records = fetch_source_records(settings)
    clean_df = build_clean_dataframe(records, now_utc())
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, dataframe_records(clean_df))

    index = LocalEmbeddingIndex.build(
        clean_df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )

    if settings.paths.eval_testset.exists() and not settings.refresh_test_set:
        test_set = read_json(settings.paths.eval_testset)
    else:
        test_set = build_test_set(clean_df, settings.paths.eval_testset)

    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = quality["freshness"]

    source_summary = {
        "source": settings.source_api,
        "raw_records": len(records),
        "clean_records": len(clean_df),
        "evaluation_questions": len(test_set),
        "embedding_model": settings.embedding_model,
        "collection": settings.baseline_collection_name,
        "source_mode": "live-refresh" if settings.refresh_source else "offline-snapshot",
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=evaluation.summary,
        quality=quality,
        freshness=freshness,
    )

    demo_answers = []
    for item in test_set[:3]:
        result = answer_question(item["question"], settings=settings, index=index)
        demo_answers.append(
            {
                "question": item["question"],
                "answer": result.answer,
                "retrieved_doc_ids": result.retrieved_doc_ids,
            }
        )
    write_json(settings.paths.demo_answers, demo_answers)

    print("Baseline pipeline completed successfully.")
    print(f"Clean rows: {len(clean_df)}")
    print(f"Evaluation questions: {len(test_set)}")
    print(f"Retrieval hit rate: {evaluation.summary['retrieval_hit_rate']:.4f}")
    print(f"Mean token F1: {evaluation.summary['mean_token_f1']:.4f}")
    print(f"Quality gate: {quality['success']}")
    print(f"Report: {settings.paths.baseline_report}")
