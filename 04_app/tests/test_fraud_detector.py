from pathlib import Path
import sys

import pandas as pd
import pytest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from fraud_detector import FraudDetector, combine_text


def test_combine_text_uses_training_order() -> None:
    assert combine_text("A", "", "B", "C", "") == "A B C"


def test_single_record_returns_score_and_priority() -> None:
    detector = FraudDetector()
    score, priority = detector.score_record(
        {
            "description": (
                "Work from home. Apply using below link. "
                "No experience necessary. Weekly payments."
            )
        }
    )
    assert isinstance(score, float)
    assert priority in {
        "High - top 5%",
        "Medium - top 10%",
        "Low - top 20%",
        "Routine review",
    }


def test_batch_scoring_sorts_descending() -> None:
    detector = FraudDetector()
    frame = pd.DataFrame(
        [
            {
                "job_id": "1",
                "description": "Apply using below link. No experience necessary.",
            },
            {
                "job_id": "2",
                "description": "Maintain backend software services with Python and SQL.",
            },
        ]
    )
    result = detector.score_frame(frame)
    assert list(result["review_rank"]) == [1, 2]
    assert result.loc[0, "risk_score"] >= result.loc[1, "risk_score"]


def test_empty_record_is_rejected() -> None:
    detector = FraudDetector()
    with pytest.raises(ValueError):
        detector.score_record({"description": "   "})
