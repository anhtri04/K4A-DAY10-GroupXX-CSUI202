# Corruption, Observability, and Repair Report

## Three-state comparison

| Metric or signal | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| `samples` | 10 | 10 | 10 |
| `retrieval_hit_rate` | 1.0000 | 0.5000 | 1.0000 |
| `mean_token_f1` | 1.0000 | 0.7788 | 1.0000 |
| `judge_accuracy` | 1.0000 | 0.8000 | 1.0000 |
| `mean_judge_score` | 5 | 4 | 5 |
| Quality gate | PASS | FAIL | PASS |
| Freshness SLA | PASS | FAIL | PASS |
| Stale ratio | 0.0417 | 0.3333 | 0.0417 |
| Repair matches baseline | N/A | N/A | PASS |

## Interpretation

- Controlled corruption changed retrieval hit rate by **-0.5000** and mean token F1 by **-0.2212** relative to baseline.
- The corrupted quality gate was **FAIL**; freshness was **FAIL**.
- Repair regenerated the dataset from the immutable raw snapshot and rebuilt a separate vector collection; the repaired dataset matches baseline: **PASS**.
