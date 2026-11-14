"""Create the frozen modelling data and no-skill baseline for the mini project."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split


RANDOM_STATE = 42
MODULE_DIR = Path(__file__).resolve().parents[1]
ROOT = MODULE_DIR.parent
RAW_PATH = ROOT / "data" / "raw" / "fake_job_postings.csv"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = MODULE_DIR / "outputs"
CLEAN_PATH = PROCESSED_DIR / "jobs_clean.csv"
PREDICTIONS_PATH = OUTPUT_DIR / "baseline_predictions.csv"
MANIFEST_PATH = OUTPUT_DIR / "data_manifest.json"
VALIDATION_PATH = OUTPUT_DIR / "data_validation.json"

TEXT_COLUMNS = [
    "title",
    "company_profile",
    "description",
    "requirements",
    "benefits",
]

METADATA_COLUMNS = [
    "employment_type",
    "required_experience",
    "required_education",
    "industry",
    "function",
]

URL_PATTERN = re.compile(r"(?i)(?:https?://|www\.)\S+")
EMBEDDED_URL_HASH_PATTERN = re.compile(r"(?i)#?url_[0-9a-f]+#?")
HEX_HASH_PATTERN = re.compile(
    r"(?i)\b(?:"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}"
    r"|[0-9a-f]{16,}"
    r")\b"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_text_key(text: str) -> str:
    """Normalize formatting variants while retaining the original text separately."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = URL_PATTERN.sub(" ", text)
    text = EMBEDDED_URL_HASH_PATTERN.sub(" ", text)
    text = HEX_HASH_PATTERN.sub(" ", text)
    text = "".join(character if character.isalnum() else " " for character in text)
    return " ".join(text.split())


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    frame = pd.read_csv(RAW_PATH, dtype={"job_id": str})
    raw_rows = len(frame)

    required = {"fraudulent", *TEXT_COLUMNS}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if frame["fraudulent"].isna().any():
        raise ValueError("fraudulent contains missing values")
    frame["fraudulent"] = frame["fraudulent"].astype(int)
    if not set(frame["fraudulent"].unique()).issubset({0, 1}):
        raise ValueError("fraudulent must contain only 0 and 1")

    if "job_id" not in frame.columns:
        frame["job_id"] = range(1, len(frame) + 1)
    frame["job_id"] = frame["job_id"].astype(str)
    if frame["job_id"].isna().any() or frame["job_id"].duplicated().any():
        raise ValueError("job_id must be present and unique")

    frame["text_all"] = (
        frame[TEXT_COLUMNS]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    empty_text = int(frame["text_all"].eq("").sum())
    frame = frame[frame["text_all"].ne("")].copy()

    exact_duplicate_rows = int(
        frame.duplicated(subset=["text_all", "fraudulent"]).sum()
    )
    frame = frame.drop_duplicates(
        subset=["text_all", "fraudulent"],
        keep="first",
    ).copy()

    frame["_text_key"] = frame["text_all"].map(canonical_text_key)
    if frame["_text_key"].eq("").any():
        raise ValueError("Canonical text key contains empty values")
    if (frame.groupby("_text_key")["fraudulent"].nunique() > 1).any():
        raise ValueError("A canonical text key has conflicting labels")

    normalized_duplicate_rows = int(
        frame.duplicated(subset=["_text_key", "fraudulent"]).sum()
    )
    frame = frame.drop_duplicates(
        subset=["_text_key", "fraudulent"],
        keep="first",
    ).reset_index(drop=True)

    train_index, remaining_index = train_test_split(
        frame.index,
        test_size=0.30,
        stratify=frame["fraudulent"],
        random_state=RANDOM_STATE,
    )
    validation_index, test_index = train_test_split(
        remaining_index,
        test_size=0.50,
        stratify=frame.loc[remaining_index, "fraudulent"],
        random_state=RANDOM_STATE,
    )

    frame["split"] = ""
    frame.loc[train_index, "split"] = "train"
    frame.loc[validation_index, "split"] = "validation"
    frame.loc[test_index, "split"] = "test"

    if set(frame["split"].unique()) != {"train", "validation", "test"}:
        raise ValueError("Unexpected split labels")

    split_sets = {
        name: set(part["job_id"])
        for name, part in frame.groupby("split", sort=False)
    }
    for left, right in [
        ("train", "validation"),
        ("train", "test"),
        ("validation", "test"),
    ]:
        if split_sets[left] & split_sets[right]:
            raise ValueError(f"job_id overlap between {left} and {right}")

    key_sets = {
        name: set(part["_text_key"])
        for name, part in frame.groupby("split", sort=False)
    }
    for left, right in [
        ("train", "validation"),
        ("train", "test"),
        ("validation", "test"),
    ]:
        if key_sets[left] & key_sets[right]:
            raise ValueError(f"canonical text overlap between {left} and {right}")

    metadata_columns = [column for column in METADATA_COLUMNS if column in frame]
    output_columns = [
        "job_id",
        "text_all",
        "fraudulent",
        "split",
        *metadata_columns,
    ]
    clean = frame[output_columns].copy()
    clean.to_csv(CLEAN_PATH, index=False, encoding="utf-8")

    train = clean[clean["split"].eq("train")]
    baseline = DummyClassifier(strategy="prior", random_state=RANDOM_STATE)
    baseline.fit(train[["text_all"]], train["fraudulent"])

    prediction_parts = []
    baseline_metrics: dict[str, dict[str, float | int]] = {}
    for split_name in ["validation", "test"]:
        part = clean[clean["split"].eq(split_name)]
        score = baseline.predict_proba(part[["text_all"]])[:, 1]
        prediction_parts.append(
            pd.DataFrame(
                {
                    "job_id": part["job_id"].to_numpy(),
                    "split": split_name,
                    "y_true": part["fraudulent"].to_numpy(),
                    "baseline_score": score,
                }
            )
        )
        baseline_metrics[split_name] = {
            "rows": int(len(part)),
            "positives": int(part["fraudulent"].sum()),
            "average_precision": float(
                average_precision_score(part["fraudulent"], score)
            ),
            "roc_auc": float(roc_auc_score(part["fraudulent"], score)),
        }

    predictions = pd.concat(prediction_parts, ignore_index=True)
    predictions.to_csv(PREDICTIONS_PATH, index=False, encoding="utf-8")

    split_summary = (
        clean.groupby("split")["fraudulent"]
        .agg(rows="size", positives="sum", positive_rate="mean")
        .reindex(["train", "validation", "test"])
        .reset_index()
        .to_dict(orient="records")
    )
    for row in split_summary:
        row["rows"] = int(row["rows"])
        row["positives"] = int(row["positives"])
        row["positive_rate"] = float(row["positive_rate"])

    validation = {
        "rows": int(len(clean)),
        "job_id_unique": bool(clean["job_id"].is_unique),
        "labels": sorted(int(value) for value in clean["fraudulent"].unique()),
        "empty_text_rows": int(clean["text_all"].eq("").sum()),
        "split_labels": sorted(clean["split"].unique().tolist()),
        "split_job_id_overlap": {
            pair: len(split_sets[pair.split("-")[0]] & split_sets[pair.split("-")[1]])
            for pair in ["train-validation", "train-test", "validation-test"]
        },
        "split_canonical_key_overlap": {
            pair: len(key_sets[pair.split("-")[0]] & key_sets[pair.split("-")[1]])
            for pair in ["train-validation", "train-test", "validation-test"]
        },
        "duplicate_canonical_text_rows_within_clean": int(
            clean.assign(
                key=clean["text_all"].map(canonical_text_key)
            ).duplicated(subset=["key", "fraudulent"]).sum()
        ),
        "split_summary": split_summary,
        "baseline_metrics": baseline_metrics,
        "passed": True,
    }
    VALIDATION_PATH.write_text(
        json.dumps(validation, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    raw_class_counts = Counter(frame["fraudulent"].tolist())
    final_class_counts = Counter(clean["fraudulent"].tolist())
    manifest = {
        "version": "final-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_state": RANDOM_STATE,
        "source_dataset": "EMSCAD via Kaggle Real / Fake Job Posting Prediction",
        "source_url": (
            "https://www.kaggle.com/datasets/"
            "shivamb/real-or-fake-fake-jobposting-prediction"
        ),
        "original_paper_doi": "10.3390/fi9010006",
        "license": "CC0: Public Domain (Kaggle dataset metadata)",
        "cleaning": {
            "raw_rows": raw_rows,
            "removed_empty_text": empty_text,
            "removed_exact_duplicates": exact_duplicate_rows,
            "removed_canonical_duplicates": normalized_duplicate_rows,
            "final_rows": int(len(clean)),
            "final_class_counts": {
                str(label): int(count)
                for label, count in sorted(final_class_counts.items())
            },
        },
        "files": {
            "raw": {
                "path": str(RAW_PATH.relative_to(ROOT)),
                "sha256": sha256(RAW_PATH),
            },
            "clean": {
                "path": str(CLEAN_PATH.relative_to(ROOT)),
                "sha256": sha256(CLEAN_PATH),
            },
            "baseline_predictions": {
                "path": str(PREDICTIONS_PATH.relative_to(ROOT)),
                "sha256": sha256(PREDICTIONS_PATH),
            },
        },
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Frozen rows: {len(clean):,}")
    print(f"Removed exact duplicates: {exact_duplicate_rows:,}")
    print(f"Removed canonical duplicates: {normalized_duplicate_rows:,}")
    print(f"Final class counts: {dict(sorted(final_class_counts.items()))}")
    print(pd.DataFrame(split_summary).to_string(index=False))
    print(f"Clean data: {CLEAN_PATH}")
    print(f"Baseline predictions: {PREDICTIONS_PATH}")
    print(f"Validation report: {VALIDATION_PATH}")


if __name__ == "__main__":
    main()
