from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build the fixed ten-question evaluation set from clean documents.

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
    required = {"paper_id", "title", "summary", "authors_joined", "published", "categories_joined"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Cannot build test set; missing columns: {sorted(missing)}")

    candidates = df.drop_duplicates(subset=["paper_id"]).reset_index(drop=True)
    if len(candidates) < 10:
        raise ValueError("At least 10 unique documents are required to build the benchmark.")

    question_types = [
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
    ]
    test_set: list[dict[str, Any]] = []
    for position, question_type in enumerate(question_types):
        row = candidates.iloc[position]
        title = normalize_whitespace(str(row["title"]))
        if question_type == "summary":
            question = f"What is the summary of the paper '{title}'?"
            ground_truth = first_sentence(str(row["summary"]))
        elif question_type == "authors":
            question = f"Who authored the paper '{title}'?"
            ground_truth = normalize_whitespace(str(row["authors_joined"]))
        elif question_type == "date":
            question = f"When was the paper '{title}' published?"
            ground_truth = str(row["published"])
        else:
            question = f"What categories describe the paper '{title}'?"
            ground_truth = normalize_whitespace(str(row["categories_joined"]))

        test_set.append(
            {
                "id": f"eval_{position + 1:03d}",
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [str(row["paper_id"])],
            }
        )

    write_json(output_path, test_set)
    return test_set
