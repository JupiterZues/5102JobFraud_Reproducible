"""Run validation-only TF-IDF ablation and bootstrap uncertainty analysis."""

from __future__ import annotations

import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


RANDOM_STATE = 42
BOOTSTRAP_REPLICATES = 2_000
REVIEW_BUDGET = 0.05

MODULE_DIR = Path(__file__).resolve().parents[1]
ROOT = MODULE_DIR.parent
CLEAN_PATH = ROOT / "data" / "processed" / "jobs_clean.csv"
PREDICTIONS_PATH = MODULE_DIR / "predictions" / "selected_model_predictions.csv"
REPORT_DIR = MODULE_DIR / "reports"
FIGURE_DIR = REPORT_DIR / "figures"


def build_pipeline(ngram_range: tuple[int, int]) -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=ngram_range,
                    min_df=3,
                    max_df=0.95,
                    max_features=60_000,
                    sublinear_tf=True,
                    dtype=np.float32,
                ),
            ),
            (
                "classifier",
                LinearSVC(
                    C=1.0,
                    class_weight="balanced",
                    dual="auto",
                    max_iter=20_000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def top_budget_metrics(
    y_true: np.ndarray,
    scores: np.ndarray,
    budget: float = REVIEW_BUDGET,
) -> dict[str, float | int]:
    flagged_count = max(1, int(np.ceil(len(y_true) * budget)))
    order = np.argsort(-scores, kind="stable")
    true_positives = int(y_true[order[:flagged_count]].sum())
    positives = int(y_true.sum())
    return {
        "flagged_count": flagged_count,
        "true_positives": true_positives,
        "precision": true_positives / flagged_count,
        "recall": true_positives / positives if positives else 0.0,
    }


def run_ablation(frame: pd.DataFrame) -> pd.DataFrame:
    train = frame[frame["split"].eq("train")].reset_index(drop=True)
    validation = frame[frame["split"].eq("validation")].reset_index(drop=True)
    cv = StratifiedKFold(
        n_splits=3,
        shuffle=True,
        random_state=RANDOM_STATE,
    )

    rows: list[dict[str, object]] = []
    for label, ngram_range in [
        ("unigram", (1, 1)),
        ("unigram_bigram", (1, 2)),
    ]:
        print(f"Running ablation: {label}", flush=True)
        pipeline = build_pipeline(ngram_range)
        cv_scores = cross_val_score(
            pipeline,
            train["text_all"],
            train["fraudulent"],
            cv=cv,
            scoring="average_precision",
            n_jobs=1,
        )

        started = time.perf_counter()
        pipeline.fit(train["text_all"], train["fraudulent"])
        fit_seconds = time.perf_counter() - started
        scores = pipeline.decision_function(validation["text_all"])
        budget_metrics = top_budget_metrics(
            validation["fraudulent"].to_numpy(),
            scores,
        )

        rows.append(
            {
                "configuration": label,
                "ngram_range": str(ngram_range),
                "vocabulary_size": int(
                    len(pipeline.named_steps["tfidf"].vocabulary_)
                ),
                "cv_average_precision_mean": float(cv_scores.mean()),
                "cv_average_precision_std": float(cv_scores.std()),
                "validation_average_precision": float(
                    average_precision_score(
                        validation["fraudulent"],
                        scores,
                    )
                ),
                "validation_roc_auc": float(
                    roc_auc_score(validation["fraudulent"], scores)
                ),
                "validation_precision_at_5pct": float(
                    budget_metrics["precision"]
                ),
                "validation_recall_at_5pct": float(
                    budget_metrics["recall"]
                ),
                "fit_seconds": float(fit_seconds),
            }
        )

    return pd.DataFrame(rows)


def bootstrap_metric(
    y_true: np.ndarray,
    scores: np.ndarray,
    metric,
    rng: np.random.Generator,
) -> tuple[float, float, float, int]:
    values = []
    for _ in range(BOOTSTRAP_REPLICATES):
        indices = rng.integers(0, len(y_true), len(y_true))
        y_sample = y_true[indices]
        score_sample = scores[indices]
        if y_sample.min() == y_sample.max():
            continue
        values.append(float(metric(y_sample, score_sample)))

    estimates = np.asarray(values)
    return (
        float(estimates.mean()),
        float(np.quantile(estimates, 0.025)),
        float(np.quantile(estimates, 0.975)),
        int(len(estimates)),
    )


def run_bootstrap() -> pd.DataFrame:
    predictions = pd.read_csv(PREDICTIONS_PATH, dtype={"job_id": str})
    rows = []
    rng = np.random.default_rng(RANDOM_STATE)

    for split_name in ["validation", "test"]:
        part = predictions[predictions["split"].eq(split_name)]
        y_true = part["y_true"].to_numpy()
        scores = part["score"].to_numpy()

        metrics = [
            (
                "average_precision",
                average_precision_score,
                float(average_precision_score(y_true, scores)),
            ),
            (
                "roc_auc",
                roc_auc_score,
                float(roc_auc_score(y_true, scores)),
            ),
            (
                "recall_at_5pct",
                lambda y, score: top_budget_metrics(y, score)["recall"],
                float(top_budget_metrics(y_true, scores)["recall"]),
            ),
            (
                "precision_at_5pct",
                lambda y, score: top_budget_metrics(y, score)["precision"],
                float(top_budget_metrics(y_true, scores)["precision"]),
            ),
        ]

        for metric_name, metric, point_estimate in metrics:
            bootstrap_mean, lower, upper, valid_replicates = bootstrap_metric(
                y_true,
                scores,
                metric,
                rng,
            )
            rows.append(
                {
                    "split": split_name,
                    "metric": metric_name,
                    "point_estimate": point_estimate,
                    "bootstrap_mean": bootstrap_mean,
                    "ci_95_lower": lower,
                    "ci_95_upper": upper,
                    "valid_replicates": valid_replicates,
                    "replicates_requested": BOOTSTRAP_REPLICATES,
                }
            )

    return pd.DataFrame(rows)


def make_ablation_figure(ablation: pd.DataFrame) -> None:
    labels = ["Unigram", "Unigram + bigram"]
    positions = np.arange(len(ablation))
    width = 0.34

    figure, axis = plt.subplots(figsize=(8, 5))
    axis.bar(
        positions - width / 2,
        ablation["cv_average_precision_mean"],
        width,
        yerr=ablation["cv_average_precision_std"],
        capsize=4,
        label="3-fold CV AP",
        color="#6baed6",
    )
    axis.bar(
        positions + width / 2,
        ablation["validation_average_precision"],
        width,
        label="Validation AP",
        color="#08519c",
    )
    axis.set_xticks(positions, labels)
    axis.set_ylim(0, 1)
    axis.set_ylabel("Average Precision")
    axis.set_title("TF-IDF Ablation for the Selected Linear SVM")
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(
        FIGURE_DIR / "tfidf_ablation.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)


def main() -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    FIGURE_DIR.mkdir(exist_ok=True)

    frame = pd.read_csv(CLEAN_PATH, dtype={"job_id": str})
    ablation = run_ablation(frame)
    ablation.to_csv(REPORT_DIR / "tfidf_ablation.csv", index=False)
    make_ablation_figure(ablation)

    uncertainty = run_bootstrap()
    uncertainty.to_csv(REPORT_DIR / "bootstrap_uncertainty.csv", index=False)

    summary = {
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "random_state": RANDOM_STATE,
        "review_budget": REVIEW_BUDGET,
        "ablation": ablation.to_dict(orient="records"),
        "uncertainty": uncertainty.to_dict(orient="records"),
        "notes": [
            "The ablation uses training and validation data only.",
            "The selected model and test predictions were not changed.",
            "Bootstrap intervals resample records independently within each split.",
        ],
    }
    (REPORT_DIR / "ablation_and_uncertainty.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\nTF-IDF ablation")
    print(ablation.to_string(index=False))
    print("\nBootstrap uncertainty")
    print(uncertainty.to_string(index=False))


if __name__ == "__main__":
    main()
