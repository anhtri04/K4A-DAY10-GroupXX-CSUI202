# Phase 1 — Baseline Data Pipeline Report

## Source and dataset

| Signal | Value |
| --- | ---: |
| `source` | Crossref REST API |
| `raw_records` | 24 |
| `clean_records` | 24 |
| `evaluation_questions` | 10 |
| `embedding_model` | sentence-transformers/all-MiniLM-L6-v2 |
| `collection` | papers-baseline |
| `source_mode` | offline-snapshot |

## Retrieval and answer evaluation

| Metric | Value |
| --- | ---: |
| `samples` | 10 |
| `retrieval_hit_rate` | 1.0000 |
| `mean_token_f1` | 1.0000 |
| `judge_accuracy` | 1.0000 |
| `mean_judge_score` | 5 |

Ragas: `Set RUN_RAGAS=1 to enable the slower Ragas pass.`

## Data quality

Overall quality gate: **PASS**

| Check | Result | Unexpected |
| --- | --- | ---: |
| `row_count_between_5_and_5000` | PASS | 0 |
| `paper_id_not_null` | PASS | 0 |
| `title_not_null` | PASS | 0 |
| `text_for_embedding_not_null` | PASS | 0 |
| `paper_id_unique` | PASS | 0 |
| `summary_length_between_30_and_100000` | PASS | 0 |

## Freshness SLA

| Signal | Value |
| --- | ---: |
| `latest_published` | 2026-07-22 |
| `oldest_published` | 2026-03-28 |
| `stale_rows` | 1 |
| `total_rows` | 24 |
| `stale_ratio` | 0.0417 |
| `is_fresh` | PASS |
