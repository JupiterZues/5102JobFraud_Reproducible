"""Create validation-only model comparison figures."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve


MODULE_DIR = Path(__file__).resolve().parents[1]
PREDICTIONS_PATH = MODULE_DIR / "predictions" / "model_predictions.csv"
BUDGET_PATH = MODULE_DIR / "reports" / "validation_review_budget.csv"
FIGURE_DIR = MODULE_DIR / "reports" / "figures"

MODEL_LABELS = {
    "linear_svm": "Linear SVM",
    "logistic_regression": "Logistic Regression",
    "complement_nb": "Complement NB",
}

MODEL_COLORS = {
    "linear_svm": "#1f77b4",
    "logistic_regression": "#2ca02c",
    "complement_nb": "#ff7f0e",
}


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    predictions = pd.read_csv(PREDICTIONS_PATH, dtype={"job_id": str})
    validation = predictions[predictions["split"].eq("validation")]

    figure, axis = plt.subplots(figsize=(8, 6))
    for model_name, part in validation.groupby("model"):
        precision, recall, _ = precision_recall_curve(
            part["y_true"],
            part["score"],
        )
        ap = average_precision_score(part["y_true"], part["score"])
        axis.plot(
            recall,
            precision,
            linewidth=2,
            label=f"{MODEL_LABELS[model_name]} (AP={ap:.3f})",
            color=MODEL_COLORS[model_name],
        )

    prevalence = validation["y_true"].mean()
    axis.axhline(
        prevalence,
        color="black",
        linestyle="--",
        linewidth=1.5,
        label=f"No-skill baseline ({prevalence:.3f})",
    )
    axis.set_title("Validation Precision-Recall Curves")
    axis.set_xlabel("Recall")
    axis.set_ylabel("Precision")
    axis.set_xlim(0, 1.01)
    axis.set_ylim(0, 1.01)
    axis.grid(alpha=0.25)
    axis.legend(loc="lower left")
    figure.tight_layout()
    figure.savefig(
        FIGURE_DIR / "validation_pr_curves.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)

    budget = pd.read_csv(BUDGET_PATH)
    budget["review_percentage"] = budget["review_budget"] * 100
    figure, axis = plt.subplots(figsize=(8, 5))
    for model_name, part in budget.groupby("model"):
        axis.plot(
            part["review_percentage"],
            part["recall"],
            marker="o",
            linewidth=2,
            label=MODEL_LABELS[model_name],
            color=MODEL_COLORS[model_name],
        )
    axis.set_title("Fraud Recall under a Fixed Manual-Review Budget")
    axis.set_xlabel("Share of postings manually reviewed (%)")
    axis.set_ylabel("Fraudulent postings detected (Recall)")
    axis.set_xticks([5, 10, 20])
    axis.set_ylim(0, 1.02)
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(
        FIGURE_DIR / "validation_review_budget.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)

    print(f"Model figures written to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
