"""Train and select transparent TF-IDF baselines for the job-fraud task."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression


RANDOM_STATE = 42
MODULE_DIR = Path(__file__).resolve().parents[1]
ROOT = MODULE_DIR.parent
CLEAN_PATH = ROOT / "data" / "processed" / "jobs_clean.csv"
MODEL_DIR = MODULE_DIR / "models"
PREDICTION_DIR = MODULE_DIR / "predictions"
REPORT_DIR = MODULE_DIR / "reports"

REVIEW_BUDGETS = (0.05, 0.10, 0.20)


def ranking_scores(estimator, texts) -> np.ndarray:
    """Return one continuous fraud score per record for any candidate model."""
    try:
        return estimator.decision_function(texts)
    except AttributeError:
        return estimator.predict_proba(texts)[:, 1]


def make_pipeline(classifier) -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    min_df=3,
                    max_df=0.95,
                    max_features=60_000,
                    sublinear_tf=True,
                    dtype=np.float32,
                ),
            ),
            ("classifier", classifier),
        ]
    )


def top_budget_metrics(
    y_true: np.ndarray,
    scores: np.ndarray,
    budgets: tuple[float, ...] = REVIEW_BUDGETS,
) -> list[dict[str, float | int]]:
    order = np.argsort(-scores, kind="stable")
    positives = int(y_true.sum())
    rows = []

    for budget in budgets:
        flagged_count = max(1, int(np.ceil(len(y_true) * budget)))
        selected = order[:flagged_count]
        true_positives = int(y_true[selected].sum())
        precision = true_positives / flagged_count
        recall = true_positives / positives if positives else 0.0
        rows.append(
            {
                "review_budget": budget,
                "flagged_count": flagged_count,
                "true_positives": true_positives,
                "precision": precision,
                "recall": recall,
            }
        )

    return rows


def main() -> None:
    MODEL_DIR.mkdir(exist_ok=True)
    PREDICTION_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)

    frame = pd.read_csv(CLEAN_PATH, dtype={"job_id": str})
    train = frame[frame["split"].eq("train")].reset_index(drop=True)
    validation = frame[frame["split"].eq("validation")].reset_index(drop=True)
    test = frame[frame["split"].eq("test")].reset_index(drop=True)

    for name, part in [
        ("train", train),
        ("validation", validation),
        ("test", test),
    ]:
        if part.empty:
            raise ValueError(f"Empty split: {name}")
        if part["text_all"].isna().any():
            raise ValueError(f"Missing text in {name}")

    x_train = train["text_all"]
    y_train = train["fraudulent"]
    x_validation = validation["text_all"]
    y_validation = validation["fraudulent"]
    x_test = test["text_all"]

    cv = StratifiedKFold(
        n_splits=3,
        shuffle=True,
        random_state=RANDOM_STATE,
    )

    candidates = {
        "logistic_regression": (
            make_pipeline(
                LogisticRegression(
                    class_weight="balanced",
                    solver="liblinear",
                    max_iter=3_000,
                    random_state=RANDOM_STATE,
                )
            ),
            {"classifier__C": [0.1, 1.0, 10.0]},
        ),
        "linear_svm": (
            make_pipeline(
                LinearSVC(
                    class_weight="balanced",
                    dual="auto",
                    max_iter=20_000,
                    random_state=RANDOM_STATE,
                )
            ),
            {"classifier__C": [0.01, 0.1, 1.0]},
        ),
        "complement_nb": (
            make_pipeline(ComplementNB()),
            {"classifier__alpha": [0.1, 1.0]},
        ),
    }

    comparison_rows: list[dict[str, object]] = []
    budget_rows: list[dict[str, object]] = []
    fitted: dict[str, GridSearchCV] = {}
    validation_scores: dict[str, np.ndarray] = {}

    for model_name, (pipeline, parameter_grid) in candidates.items():
        print(f"\nTraining {model_name}", flush=True)
        search = GridSearchCV(
            estimator=pipeline,
            param_grid=parameter_grid,
            scoring={
                "average_precision": "average_precision",
                "roc_auc": "roc_auc",
            },
            refit="average_precision",
            cv=cv,
            n_jobs=1,
            verbose=2,
            return_train_score=False,
        )
        search.fit(x_train, y_train)
        fitted[model_name] = search

        score = ranking_scores(search, x_validation)
        validation_scores[model_name] = score

        validation_ap = float(average_precision_score(y_validation, score))
        validation_roc_auc = float(roc_auc_score(y_validation, score))
        best_index = search.best_index_

        comparison_rows.append(
            {
                "model": model_name,
                "best_params": json.dumps(search.best_params_, sort_keys=True),
                "cv_average_precision_mean": float(
                    search.cv_results_["mean_test_average_precision"][best_index]
                ),
                "cv_average_precision_std": float(
                    search.cv_results_["std_test_average_precision"][best_index]
                ),
                "cv_roc_auc_mean": float(
                    search.cv_results_["mean_test_roc_auc"][best_index]
                ),
                "validation_average_precision": validation_ap,
                "validation_roc_auc": validation_roc_auc,
            }
        )

        for budget_result in top_budget_metrics(y_validation.to_numpy(), score):
            budget_rows.append({"model": model_name, **budget_result})

        print(
            f"Best parameters: {search.best_params_}\n"
            f"Validation AP: {validation_ap:.6f}; "
            f"ROC-AUC: {validation_roc_auc:.6f}",
            flush=True,
        )

    comparison = pd.DataFrame(comparison_rows).sort_values(
        "validation_average_precision",
        ascending=False,
    )
    comparison.to_csv(REPORT_DIR / "model_comparison.csv", index=False)

    budget_table = pd.DataFrame(budget_rows)
    budget_table.to_csv(REPORT_DIR / "validation_review_budget.csv", index=False)

    validation_budget_10 = (
        comparison.reset_index(drop=True).assign(
            candidate_rank=lambda data: np.arange(1, len(data) + 1)
        ).merge(
            budget_table[budget_table["review_budget"].eq(0.10)][
                ["model", "precision", "recall"]
            ].rename(
                columns={
                    "precision": "validation_precision_at_10pct",
                    "recall": "validation_recall_at_10pct",
                }
            ),
            on="model",
            how="left",
        )
    )
    validation_budget_10.to_csv(
        REPORT_DIR / "model_selection.csv",
        index=False,
    )

    selected_model_name = str(comparison.iloc[0]["model"])
    selected_search = fitted[selected_model_name]
    selected_pipeline = selected_search.best_estimator_

    all_prediction_parts = []
    for model_name, search in fitted.items():
        for split_name, part in [
            ("validation", validation),
            ("test", test),
        ]:
            score = ranking_scores(search, part["text_all"])
            all_prediction_parts.append(
                pd.DataFrame(
                    {
                        "model": model_name,
                        "job_id": part["job_id"].to_numpy(),
                        "split": split_name,
                        "y_true": part["fraudulent"].to_numpy(),
                        "score": score,
                    }
                )
            )

    all_predictions = pd.concat(all_prediction_parts, ignore_index=True)
    all_predictions.to_csv(
        PREDICTION_DIR / "model_predictions.csv",
        index=False,
    )

    selected_rows = []
    for split_name, part in [
        ("validation", validation),
        ("test", test),
    ]:
        score = ranking_scores(selected_pipeline, part["text_all"])
        selected_rows.append(
            pd.DataFrame(
                {
                    "job_id": part["job_id"].to_numpy(),
                    "split": split_name,
                    "y_true": part["fraudulent"].to_numpy(),
                    "score": score,
                    "model": selected_model_name,
                }
            )
        )
    selected_predictions = pd.concat(selected_rows, ignore_index=True)
    selected_predictions.to_csv(
        PREDICTION_DIR / "selected_model_predictions.csv",
        index=False,
    )

    joblib.dump(
        selected_pipeline,
        MODEL_DIR / "selected_model.joblib",
        compress=3,
    )

    selected_validation = selected_predictions[
        selected_predictions["split"].eq("validation")
    ]
    report = {
        "selected_model": selected_model_name,
        "selection_metric": "validation_average_precision",
        "best_parameters": selected_search.best_params_,
        "training_rows": int(len(train)),
        "validation_rows": int(len(validation)),
        "test_rows": int(len(test)),
        "validation_average_precision": float(
            comparison.iloc[0]["validation_average_precision"]
        ),
        "validation_roc_auc": float(comparison.iloc[0]["validation_roc_auc"]),
        "validation_review_budget": top_budget_metrics(
            selected_validation["y_true"].to_numpy(),
            selected_validation["score"].to_numpy(),
        ),
        "notes": [
            "Model selection used the validation split only.",
            "Test predictions were generated once and were not used for tuning.",
            "Scores are decision-function values; only their ranking is used.",
        ],
    }
    (REPORT_DIR / "model_selection.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\nModel comparison")
    print(comparison.to_string(index=False))
    print("\nValidation review-budget results")
    print(budget_table.to_string(index=False))
    print(f"\nSelected model: {selected_model_name}")
    print(f"Model comparison: {REPORT_DIR / 'model_comparison.csv'}")
    print(
        "Selected predictions: "
        f"{PREDICTION_DIR / 'selected_model_predictions.csv'}"
    )


if __name__ == "__main__":
    main()
