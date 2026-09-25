from __future__ import annotations

from math import ceil

import pandas as pd

from core.utils import write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Apply six deterministic data-corruption scenarios and write an audit log.

    Pseudo-code:
    1. Drop mot so latest records.
    2. Blank summary o mot so dong.
    3. Inject noise vao text.
    4. Lam title bi truncate.
    5. Lam published date cu di.
    6. Add duplicate rows.
    7. Rebuild `text_for_embedding`.
    8. Ghi corruption log vao output_log_path.
    """
    required = {
        "paper_id",
        "title",
        "summary",
        "published",
        "authors_joined",
        "categories_joined",
        "text_for_embedding",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Cannot corrupt dataframe; missing columns: {sorted(missing)}")
    if len(df) < 10:
        raise ValueError("At least 10 rows are required for the corruption suite.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    original_rows = len(corrupted)
    events: list[dict] = []

    latest_count = max(1, ceil(original_rows * 0.20))
    latest_indices = (
        pd.to_datetime(corrupted["published"], errors="coerce")
        .sort_values(ascending=False)
        .index[:latest_count]
        .tolist()
    )
    dropped_ids = corrupted.loc[latest_indices, "paper_id"].astype(str).tolist()
    corrupted = corrupted.drop(index=latest_indices).reset_index(drop=True)
    events.append(
        {
            "type": "drop_latest_records",
            "count": len(dropped_ids),
            "paper_ids": dropped_ids,
            "parameter": {"fraction": 0.20},
        }
    )

    def take(start: int, count: int) -> list[int]:
        return [position % len(corrupted) for position in range(start, start + count)]

    blank_indices = take(0, 2)
    corrupted.loc[blank_indices, "summary"] = ""
    corrupted.loc[blank_indices, "summary_chars"] = 0
    events.append(
        {
            "type": "blank_summary",
            "count": len(blank_indices),
            "paper_ids": corrupted.loc[blank_indices, "paper_id"].astype(str).tolist(),
        }
    )

    noise_indices = take(2, 2)
    noise = " ### NOISE_@@@_CORRUPTED_DATA ###"
    corrupted.loc[noise_indices, "summary"] = corrupted.loc[noise_indices, "summary"].astype(str) + noise
    corrupted.loc[noise_indices, "summary_chars"] = corrupted.loc[noise_indices, "summary"].str.len()
    events.append(
        {
            "type": "inject_noise",
            "count": len(noise_indices),
            "paper_ids": corrupted.loc[noise_indices, "paper_id"].astype(str).tolist(),
            "parameter": {"noise": noise.strip()},
        }
    )

    truncate_indices = take(4, 2)
    corrupted.loc[truncate_indices, "title"] = corrupted.loc[truncate_indices, "title"].astype(str).str[:7]
    events.append(
        {
            "type": "truncate_title",
            "count": len(truncate_indices),
            "paper_ids": corrupted.loc[truncate_indices, "paper_id"].astype(str).tolist(),
            "parameter": {"max_characters": 7},
        }
    )

    stale_count = max(6, ceil(len(corrupted) * 0.30))
    stale_indices = take(6, stale_count)
    stale_dates = pd.to_datetime(corrupted.loc[stale_indices, "published"], errors="coerce") - pd.Timedelta(days=365)
    corrupted.loc[stale_indices, "published"] = stale_dates.dt.strftime("%Y-%m-%d").values
    if "age_days" in corrupted.columns:
        corrupted.loc[stale_indices, "age_days"] = (
            pd.to_numeric(corrupted.loc[stale_indices, "age_days"], errors="coerce").fillna(0).astype(int) + 365
        )
    events.append(
        {
            "type": "stale_date",
            "count": len(stale_indices),
            "paper_ids": corrupted.loc[stale_indices, "paper_id"].astype(str).tolist(),
            "parameter": {"days_subtracted": 365},
        }
    )

    duplicate_source_indices = take(1, 2)
    duplicate_rows = corrupted.loc[duplicate_source_indices].copy(deep=True)
    duplicate_ids = duplicate_rows["paper_id"].astype(str).tolist()
    corrupted = pd.concat([corrupted, duplicate_rows], ignore_index=True)
    events.append(
        {
            "type": "duplicate_rows",
            "count": len(duplicate_rows),
            "paper_ids": duplicate_ids,
        }
    )

    corrupted["text_for_embedding"] = corrupted.apply(
        lambda row: "\n".join(
            [
                f"Title: {row['title']}",
                f"Authors: {row['authors_joined']}",
                f"Published: {row['published']}",
                f"Categories: {row['categories_joined']}",
                f"Summary: {row['summary']}",
            ]
        ),
        axis=1,
    )

    write_json(
        output_log_path,
        {
            "original_rows": original_rows,
            "corrupted_rows": len(corrupted),
            "corruption_types": 6,
            "events": events,
        },
    )
    return corrupted.reset_index(drop=True)
