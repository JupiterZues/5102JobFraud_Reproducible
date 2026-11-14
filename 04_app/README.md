# Job Fraud Review Assistant

A bilingual HTML/CSS/JavaScript application backed by FastAPI. It loads the
frozen Linear SVM model and ranks job postings for human review.

## Features

- Score one job posting from five text fields.
- Show a review priority based on validation-set top-k cutoffs.
- Upload a batch CSV and download ranked results.
- Command-line scoring for one text or a CSV.
- Switch the complete interface between Chinese and English.

The score is a ranking value, not a calibrated probability.

## Run the web app

From the repository root:

```bash
pip install -r 04_app/requirements.txt
bash 04_app/run_web.sh
```

Then open `http://localhost:8501`.

## Run the CLI

One posting:

```bash
python 04_app/cli.py text \
  --title "Data Entry Clerk" \
  --description "Work from home. Apply using below link."
```

Batch CSV:

```bash
python 04_app/cli.py csv \
  --input 04_app/sample_jobs.csv \
  --output 04_app/sample_jobs_ranked.csv
```

## Input schema

CSV columns may include:

- `job_id`
- `title`
- `company_profile`
- `description`
- `requirements`
- `benefits`

At least one text field must be non-empty.

## Output

The ranked result adds:

- `review_rank`
- `risk_score`
- `priority`

`priority` is one of:

- `High - top 5%`
- `Medium - top 10%`
- `Low - top 20%`
- `Routine review`

The cutoffs in `thresholds.json` come from the validation split and are only a
reference for this dataset. Re-estimate them on current platform data before
deployment.

## Important limitations

- Never automatically reject a posting from the model score alone.
- EMSCAD is historical English-language data from 2012-2014.
- The SVM score is not a probability.
- Human review and an appeal process are required.
