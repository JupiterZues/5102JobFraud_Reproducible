"""Evaluate the frozen model on the held-out test split."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)


EVALUATION_DIR = Path(__file__).resolve().parents[1]
ROOT = EVALUATION_DIR.parent
MODEL_STAGE = ROOT / "02_modelling"
DATA_PATH = ROOT / "data" / "processed" / "jobs_clean.csv"
PREDICTIONS_PATH = MODEL_STAGE / "predictions" / "selected_model_predictions.csv"
MODEL_PATH = MODEL_STAGE / "models" / "selected_model.joblib"
OUTPUT_DIR = EVALUATION_DIR / "outputs"
FIGURE_DIR = OUTPUT_DIR / "figures"

REVIEW_BUDGETS = (0.05, 0.10, 0.20)


def budget_metrics(
    y_true: np.ndarray,
    scores: np.ndarray,
    budget: float,
) -> dict[str, float | int]:
    flagged_count = max(1, int(np.ceil(len(y_true) * budget)))
    order = np.argsort(-scores, kind="stable")
    predicted = np.zeros(len(y_true), dtype=int)
    predicted[order[:flagged_count]] = 1

    tn, fp, fn, tp = confusion_matrix(y_true, predicted).ravel()
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    prevalence = y_true.mean()

    return {
        "review_budget": budget,
        "flagged_count": flagged_count,
        "true_positives": int(tp),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_negatives": int(tn),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "lift_vs_prevalence": float(precision / prevalence) if prevalence else 0.0,
        "share_of_all_fraud_caught": float(recall),
    }


def make_pr_figure(
    y_true: np.ndarray,
    scores: np.ndarray,
    budget_table: pd.DataFrame,
) -> None:
    precision, recall, _ = precision_recall_curve(y_true, scores)
    ap = average_precision_score(y_true, scores)
    prevalence = y_true.mean()

    figure, axis = plt.subplots(figsize=(8, 6))
    axis.plot(
        recall,
        precision,
        color="#1f4e79",
        linewidth=2.2,
        label=f"Linear SVM (AP = {ap:.4f})",
    )
    axis.axhline(
        prevalence,
        linestyle="--",
        color="gray",
        linewidth=1.4,
        label=f"Prevalence = {prevalence:.4f}",
    )
    for _, row in budget_table.iterrows():
        axis.scatter(
            row["recall"],
            row["precision"],
            s=70,
            zorder=5,
        )
        axis.annotate(
            f"{row['review_budget']:.0%}",
            (row["recall"], row["precision"]),
            xytext=(8, 6),
            textcoords="offset points",
        )

    axis.set_title("Test Precision-Recall Curve")
    axis.set_xlabel("Recall")
    axis.set_ylabel("Precision")
    axis.set_xlim(0, 1.01)
    axis.set_ylim(0, 1.01)
    axis.grid(alpha=0.25)
    axis.legend(loc="lower left")
    figure.tight_layout()
    figure.savefig(
        FIGURE_DIR / "test_pr_curve.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)


def extract_top_features() -> pd.DataFrame:
    model = joblib.load(MODEL_PATH)
    vectorizer = model.named_steps["tfidf"]
    classifier = model.named_steps["classifier"]
    feature_names = vectorizer.get_feature_names_out()
    coefficients = classifier.coef_.ravel()

    fraud_indices = np.argsort(coefficients)[-20:][::-1]
    real_indices = np.argsort(coefficients)[:20]
    rows = [
        {
            "direction": "fraud",
            "feature": feature_names[index],
            "coefficient": float(coefficients[index]),
        }
        for index in fraud_indices
    ]
    rows.extend(
        {
            "direction": "real",
            "feature": feature_names[index],
            "coefficient": float(coefficients[index]),
        }
        for index in real_indices
    )
    return pd.DataFrame(rows)


def make_feature_figure(features: pd.DataFrame) -> None:
    fraud = features[features["direction"].eq("fraud")].sort_values(
        "coefficient"
    )
    real = features[features["direction"].eq("real")].sort_values(
        "coefficient",
        ascending=False,
    )

    figure, axes = plt.subplots(1, 2, figsize=(12, 6))
    axes[0].barh(fraud["feature"], fraud["coefficient"], color="#c75b12")
    axes[0].set_title("Fraud-Associated Terms")
    axes[0].set_xlabel("Linear SVM coefficient")
    axes[0].grid(axis="x", alpha=0.25)

    axes[1].barh(real["feature"], real["coefficient"], color="#0b4f79")
    axes[1].set_title("Real-Associated Terms")
    axes[1].set_xlabel("Linear SVM coefficient")
    axes[1].grid(axis="x", alpha=0.25)

    figure.suptitle("Lexical Signals Learned by the Linear SVM")
    figure.tight_layout()
    figure.savefig(
        FIGURE_DIR / "top_features.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    data = pd.read_csv(DATA_PATH, dtype={"job_id": str})
    predictions = pd.read_csv(PREDICTIONS_PATH, dtype={"job_id": str})
    test = predictions[predictions["split"].eq("test")].copy()
    test = test.merge(
        data[["job_id", "text_all"]],
        on="job_id",
        how="left",
        validate="one_to_one",
    )
    if test["text_all"].isna().any():
        raise ValueError("Test predictions do not match the frozen data")

    test = test.sort_values("score", ascending=False).reset_index(drop=True)
    test["rank"] = np.arange(1, len(test) + 1)
    y_true = test["y_true"].to_numpy()
    scores = test["score"].to_numpy()
    positives = int(y_true.sum())

    budget_rows = [
        budget_metrics(y_true, scores, budget)
        for budget in REVIEW_BUDGETS
    ]
    budget_table = pd.DataFrame(budget_rows)
    budget_table.to_csv(
        OUTPUT_DIR / "test_review_budget.csv",
        index=False,
    )

    top_five = budget_table.iloc[0]
    confusion = {
        "tn": int(top_five["true_negatives"]),
        "fp": int(top_five["false_positives"]),
        "fn": int(top_five["false_negatives"]),
        "tp": int(top_five["true_positives"]),
    }
    pd.DataFrame(
        [
            [confusion["tn"], confusion["fp"]],
            [confusion["fn"], confusion["tp"]],
        ],
        index=["Actual 0", "Actual 1"],
        columns=["Predicted 0", "Predicted 1"],
    ).to_csv(OUTPUT_DIR / "test_confusion_matrix_5pct.csv")

    flagged_count = int(top_five["flagged_count"])
    error_mask = (
        test["rank"].le(flagged_count) & test["y_true"].eq(0)
    ) | (
        test["rank"].gt(flagged_count) & test["y_true"].eq(1)
    )
    errors = test.loc[error_mask, ["rank", "job_id", "y_true", "score", "text_all"]].copy()
    errors.insert(
        0,
        "case_type",
        np.where(errors["y_true"].eq(0), "false_positive", "false_negative"),
    )
    errors["excerpt"] = (
        errors["text_all"]
        .str.replace(r"\s+", " ", regex=True)
        .str.slice(0, 500)
    )
    errors.drop(columns="text_all").to_csv(
        OUTPUT_DIR / "test_error_cases.csv",
        index=False,
    )

    metrics = {
        "split": "test",
        "rows": int(len(test)),
        "positives": positives,
        "prevalence": float(y_true.mean()),
        "average_precision": float(average_precision_score(y_true, scores)),
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "review_budget": budget_rows,
        "confusion_matrix_5pct": confusion,
        "notes": [
            "Scores are decision-function values; only ranking is used.",
            "No 0.5 threshold is applied.",
            "The test split was not used to tune the model.",
        ],
    }
    (OUTPUT_DIR / "test_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    features = extract_top_features()
    features.to_csv(OUTPUT_DIR / "top_text_features.csv", index=False)
    make_pr_figure(y_true, scores, budget_table)
    make_feature_figure(features)

    print("Test metrics")
    print(f"PR-AUC: {metrics['average_precision']:.6f}")
    print(f"ROC-AUC: {metrics['roc_auc']:.6f}")
    print(budget_table.to_string(index=False))
    print(f"Outputs written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
