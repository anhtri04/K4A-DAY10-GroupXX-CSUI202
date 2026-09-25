from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json

# 10 questions spread as evenly as possible over the 4 required types.
_QUESTION_PLAN = (
    "summary",
    "authors",
    "date",
    "categories",
    "summary",
    "authors",
    "date",
    "categories",
    "summary",
    "authors",
)


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """TODO(student): tao bo evaluation set tu cleaned dataframe.

    Pseudo-code:
    1. Kiem tra so luong document toi thieu.
    2. Chon mot so paper dai dien.
    3. Tao nhieu loai cau hoi:
       - summary
       - authors
       - date
       - categories
    4. Moi row can co:
       - id
       - question_type
       - question
       - ground_truth
       - ground_truth_doc_ids
    5. Ghi file JSON vao output_path.
    """
    if len(df) < len(_QUESTION_PLAN):
        raise ValueError(f"Need at least {len(_QUESTION_PLAN)} documents, got {len(df)}.")
    # Deterministically spread picks across the dataframe (sorted by published).
    ordered = df.sort_values(["published", "paper_id"], kind="mergesort").reset_index(drop=True)
    step = len(ordered) / len(_QUESTION_PLAN)
    picks = [ordered.iloc[int(round(i * step))] for i in range(len(_QUESTION_PLAN))]

    test_set: list[dict[str, Any]] = []
    for position, (question_type, row) in enumerate(zip(_QUESTION_PLAN, picks, strict=True), start=1):
        title = normalize_whitespace(str(row["title"]))
        paper_id = normalize_whitespace(str(row["paper_id"]))
        if question_type == "summary":
            question = f"What is the summary of the paper '{title}'?"
            ground_truth = first_sentence(str(row["summary"]))
        elif question_type == "authors":
            question = f"Who authored the paper '{title}'?"
            ground_truth = normalize_whitespace(str(row["authors_joined"]))
        elif question_type == "date":
            question = f"When was the paper '{title}' published?"
            ground_truth = normalize_whitespace(str(row["published"]))
        else:  # categories
            question = f"What categories does the paper '{title}' belong to?"
            ground_truth = normalize_whitespace(str(row["categories_joined"]))
        test_set.append(
            {
                "id": f"eval_{position:03d}",
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )
    write_json(Path(output_path), test_set)
    return test_set
