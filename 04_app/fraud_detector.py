"""Reusable inference logic for the job-fraud screening demo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
DEFAULT_MODEL_PATH = ROOT / "02_modelling" / "models" / "selected_model.joblib"
DEFAULT_THRESHOLD_PATH = APP_DIR / "thresholds.json"

TEXT_COLUMNS = [
    "title",
    "company_profile",
    "description",
    "requirements",
    "benefits",
]

PRIORITY_ORDER = {
    "High - top 5%": 1,
    "Medium - top 10%": 2,
    "Low - top 20%": 3,
    "Routine review": 4,
}


def combine_text(
    title: str = "",
    company_profile: str = "",
    description: str = "",
    requirements: str = "",
    benefits: str = "",
) -> str:
    """Build the model input in the same order used during training."""
    values = [
        title,
        company_profile,
        description,
        requirements,
        benefits,
    ]
    return " ".join(
        value.strip() for value in values if isinstance(value, str) and value.strip()
    )


class FraudDetector:
    """Load the frozen model and expose ranking-based predictions."""

    def __init__(
        self,
        model_path: Path | str = DEFAULT_MODEL_PATH,
        threshold_path: Path | str = DEFAULT_THRESHOLD_PATH,
    ) -> None:
        self.model_path = Path(model_path)
        self.threshold_path = Path(threshold_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model not found: {self.model_path}. "
                "See the project README for reconstruction instructions."
            )
        if not self.threshold_path.exists():
            raise FileNotFoundError(f"Threshold file not found: {self.threshold_path}")

        self.model = joblib.load(self.model_path)
        self.thresholds = json.loads(
            self.threshold_path.read_text(encoding="utf-8")
        )["validation_cutoffs"]

    def score_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.asarray([], dtype=float)
        return self.model.decision_function(texts)

    def priority(self, score: float) -> str:
        if score >= float(self.thresholds["top_5pct"]):
            return "High - top 5%"
        if score >= float(self.thresholds["top_10pct"]):
            return "Medium - top 10%"
        if score >= float(self.thresholds["top_20pct"]):
            return "Low - top 20%"
        return "Routine review"

    def score_record(self, record: dict[str, Any]) -> tuple[float, str]:
        text = combine_text(
            **{column: str(record.get(column, "") or "") for column in TEXT_COLUMNS}
        )
        if not text:
            raise ValueError("At least one text field must be provided.")
        score = float(self.score_texts([text])[0])
        return score, self.priority(score)

    def score_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            raise ValueError("The uploaded file contains no rows.")

        data = frame.copy()
        for column in TEXT_COLUMNS:
            if column not in data:
                data[column] = ""
            data[column] = data[column].fillna("").astype(str)

        texts = [
            combine_text(**{column: row[column] for column in TEXT_COLUMNS})
            for _, row in data.iterrows()
        ]
        if not any(texts):
            raise ValueError("Every uploaded row has empty text.")

        scores = self.score_texts(texts)
        data["risk_score"] = scores
        data["review_flag"] = np.where(
            scores >= float(self.thresholds["top_5pct"]),
            "priority_review",
            "no_priority_flag",
        )
        data["priority"] = [self.priority(float(score)) for score in scores]
        data["priority_order"] = data["priority"].map(PRIORITY_ORDER)
        data = data.sort_values(
            ["risk_score", "priority_order"],
            ascending=[False, True],
            kind="stable",
        ).reset_index(drop=True)
        data.insert(0, "review_rank", np.arange(1, len(data) + 1))
        return data.drop(columns="priority_order")


def threshold_rows(thresholds: dict[str, float]) -> list[dict[str, float | str]]:
    return [
        {
            "Review budget": "Top 5%",
            "Cutoff score": float(thresholds["top_5pct"]),
            "Priority label": "High",
        },
        {
            "Review budget": "Top 10%",
            "Cutoff score": float(thresholds["top_10pct"]),
            "Priority label": "Medium",
        },
        {
            "Review budget": "Top 20%",
            "Cutoff score": float(thresholds["top_20pct"]),
            "Priority label": "Low",
        },
    ]
