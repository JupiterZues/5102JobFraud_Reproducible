"""Bundle the trained TF-IDF + Linear SVM model into one offline HTML file."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

import joblib


APP_DIR = Path(__file__).resolve().parents[1]
ROOT = APP_DIR.parent
STANDALONE_DIR = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "02_modelling" / "models" / "selected_model.joblib"
THRESHOLD_PATH = APP_DIR / "thresholds.json"
SAMPLE_PATH = APP_DIR / "sample_jobs.csv"
HTML_SOURCE = APP_DIR / "static" / "index.html"
CSS_SOURCE = APP_DIR / "static" / "styles.css"
INFERENCE_SOURCE = STANDALONE_DIR / "inference.js"
UI_SOURCE = STANDALONE_DIR / "ui.js"
OUTPUT = ROOT / "JobGuard.html"


def build_model_payload() -> dict:
    pipeline = joblib.load(MODEL_PATH)
    vectorizer = pipeline.named_steps["tfidf"]
    classifier = pipeline.named_steps["classifier"]
    thresholds = json.loads(
        THRESHOLD_PATH.read_text(encoding="utf-8")
    )["validation_cutoffs"]

    return {
        "features": vectorizer.get_feature_names_out().tolist(),
        "idf": vectorizer.idf_.astype(float).tolist(),
        "coef": classifier.coef_.ravel().astype(float).tolist(),
        "intercept": float(classifier.intercept_[0]),
        "thresholds": thresholds,
        "score_range": {"min": -2.3, "max": 1.5},
        "sample_csv": SAMPLE_PATH.read_text(encoding="utf-8"),
    }


def build() -> Path:
    html_text = HTML_SOURCE.read_text(encoding="utf-8")
    css_text = CSS_SOURCE.read_text(encoding="utf-8")
    css_text = re.sub(r'@import url\([^;]+;\s*', '', css_text)
    inference_text = INFERENCE_SOURCE.read_text(encoding="utf-8")
    ui_text = UI_SOURCE.read_text(encoding="utf-8")
    model_payload = build_model_payload()

    html_text = html_text.replace(
        '<link rel="stylesheet" href="/assets/styles.css">',
        f"<style>\n{css_text}\n</style>",
    )
    html_text = re.sub(
        r'<a class="secondary-btn compact" href="/api/sample\.csv" '
        r'data-i18n="sample_download">.*?</a>',
        '<a id="sample-download" class="secondary-btn compact" '
        'href="#" data-i18n="sample_download">下载示例 CSV</a>',
        html_text,
        flags=re.DOTALL,
    )

    encoded_model = json.dumps(
        model_payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    runtime = (
        f"<script>\n"
        f"const JOBGUARD_MODEL = {encoded_model};\n"
        f"{inference_text}\n"
        f"{ui_text}\n"
        f"</script>"
    )
    html_text = html_text.replace(
        '<script src="/assets/app.js"></script>',
        runtime,
    )
    html_text = html_text.replace(
        "JobGuard | Fraud Review Assistant",
        "JobGuard | Offline Fraud Review Assistant",
    )

    OUTPUT.write_text(html_text, encoding="utf-8")
    return OUTPUT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-json",
        type=Path,
        help="Optional path for a model JSON file used by automated JS tests.",
    )
    args = parser.parse_args()

    if args.model_json:
        args.model_json.write_text(
            json.dumps(
                build_model_payload(),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

    output = build()
    print(output)
    print(f"Size: {output.stat().st_size / 1024 / 1024:.2f} MiB")


if __name__ == "__main__":
    main()
