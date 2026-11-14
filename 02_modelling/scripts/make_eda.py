"""Generate EDA figures from the frozen job-posting dataset."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODULE_DIR = Path(__file__).resolve().parents[1]
ROOT = MODULE_DIR.parent
CLEAN_PATH = ROOT / "data" / "processed" / "jobs_clean.csv"
RAW_PATH = ROOT / "data" / "raw" / "fake_job_postings.csv"
FIGURE_DIR = MODULE_DIR / "outputs" / "figures"


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    clean = pd.read_csv(CLEAN_PATH, dtype={"job_id": str})
    raw = pd.read_csv(RAW_PATH, dtype={"job_id": str})

    counts = clean["fraudulent"].value_counts().reindex([0, 1], fill_value=0)
    figure, axis = plt.subplots(figsize=(7, 5))
    bars = axis.bar(
        ["Real", "Fake"],
        counts.to_numpy(),
        color=["steelblue", "darkorange"],
    )
    for bar, value in zip(bars, counts):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:,}\n({value / len(clean):.2%})",
            ha="center",
            va="bottom",
        )
    axis.set_title("Class Distribution of Job Postings")
    axis.set_xlabel("Job Posting Type")
    axis.set_ylabel("Number of Job Postings")
    axis.set_ylim(0, counts.max() * 1.18)
    figure.tight_layout()
    figure.savefig(
        FIGURE_DIR / "eda_class_balance.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)

    missing_rate = raw.isna().mean().sort_values() * 100
    figure, axis = plt.subplots(figsize=(9, 6))
    axis.barh(
        missing_rate.index,
        missing_rate.to_numpy(),
        color="steelblue",
    )
    axis.set_title("Missing Values in the Original Dataset")
    axis.set_xlabel("Missing Rate (%)")
    axis.set_ylabel("Feature")
    axis.set_xlim(0, 100)
    figure.tight_layout()
    figure.savefig(
        FIGURE_DIR / "eda_missing_values.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)

    lengths = clean["text_all"].str.split().str.len()
    upper = lengths.quantile(0.99)
    bins = np.linspace(0, upper, 51)
    figure, axis = plt.subplots(figsize=(9, 5))
    axis.hist(
        lengths[clean["fraudulent"].eq(0)],
        bins=bins,
        density=True,
        alpha=0.6,
        label="Real",
        color="steelblue",
    )
    axis.hist(
        lengths[clean["fraudulent"].eq(1)],
        bins=bins,
        density=True,
        alpha=0.6,
        label="Fake",
        color="darkorange",
    )
    axis.set_title("Text Length Distribution by Job Type")
    axis.set_xlabel("Number of Words")
    axis.set_ylabel("Density")
    axis.set_xlim(0, upper)
    axis.legend()
    figure.tight_layout()
    figure.savefig(
        FIGURE_DIR / "eda_text_length.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)

    print(f"EDA figures written to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
