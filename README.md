# DSAI5102 Job Fraud Detection: Reproducible Workpack

Technical code, frozen data, models, predictions, figures, and evaluation
outputs for:

**Alert-Budgeted Detection of Fraudulent Job Postings**

The final written report and slide deck are stored in `deliverables/`. The
remainder of the repository is organized as a reproducible three-stage
pipeline rather than by team-member labels.

## Directory structure

```text
DSAI5102_JobFraud_Reproducible_Workpack/
  README.md
  requirements.txt
  run_all.sh
  deliverables/
    Group17_Report.pdf
    Group17_Slides.pptx
    Group17_Slides.pdf
  docs/
    Project_Learning_Guide_CN.md
    Project_Learning_Guide_CN.docx
    Project_Learning_Guide_CN.pdf
  data/
    raw/
      fake_job_postings.csv
    intermediate/
      jobs_clean_v2.csv
    processed/
      jobs_clean.csv
  01_data_preparation/
    README.md
    data_preparation_v2.ipynb
    baseline_predictions_v2.csv
    figures/
  02_modelling/
    README.md
    scripts/
    models/
    predictions/
    outputs/
    reports/
  03_evaluation/
    README.md
    scripts/
    outputs/
  04_app/
    README.md
    app.py
    cli.py
    fraud_detector.py
    thresholds.json
    sample_jobs.csv
    tests/
```

## Final deliverables

- `deliverables/Group17_Report.pdf`
- `deliverables/Group17_Slides.pptx`
- `deliverables/Group17_Slides.pdf`

The report uses Times New Roman, three-line tables, continuous section flow,
black text, coloured figures, and page numbers only in the footer.

## Chinese learning guide

`docs/Project_Learning_Guide_CN.pdf` explains the project principles and
application in Chinese. It covers the business problem, data leakage, TF-IDF,
three model families, validation strategy, PR-AUC, fixed review budgets,
bootstrap intervals, error analysis, deployment recommendations, and the
reproduction workflow.

- Markdown source: `docs/Project_Learning_Guide_CN.md`
- Editable document: `docs/Project_Learning_Guide_CN.docx`
- PDF: `docs/Project_Learning_Guide_CN.pdf`

## Pipeline

### 1. Data preparation

`01_data_preparation/` preserves the original interactive data-preparation
workflow and its outputs:

- Raw EMSCAD data and text construction.
- v2 duplicate removal.
- Stratified 70%/15%/15% split.
- No-skill baseline and EDA.

The v2 intermediate dataset is stored at
`data/intermediate/jobs_clean_v2.csv`.

### 2. Final data and modelling

`02_modelling/` performs the final leakage check and all modelling:

- Canonical text deduplication.
- Final frozen split.
- TF-IDF Logistic Regression, Linear SVM, and Complement Naive Bayes.
- Validation-based model selection.
- Ablation and bootstrap uncertainty analysis.
- Serialized model and prediction files.

Use `data/processed/jobs_clean.csv` for modelling. It contains 15,716 records:
15,008 legitimate postings and 708 fraudulent postings.

| Split | Rows | Fraudulent |
|---|---:|---:|
| Train | 11,001 | 496 |
| Validation | 2,357 | 106 |
| Test | 2,358 | 106 |

The selected model is a Linear SVM with TF-IDF word unigrams and bigrams,
balanced class weights, and `C=1.0`. Its score is a decision value used for
ranking, not a probability.

| Result | Validation | Test |
|---|---:|---:|
| PR-AUC | 0.8960 | 0.9466 |
| ROC-AUC | 0.9852 | 0.9966 |
| Recall at 5% review | 0.8585 | 0.8868 |

The validation and test PR-AUC bootstrap intervals overlap, so the higher test
estimate should not be interpreted as a significant improvement.

### 3. Evaluation

`03_evaluation/` evaluates the frozen test predictions:

- PR-AUC and ROC-AUC.
- Precision, recall, F1, and confusion matrix at fixed review budgets.
- All false positives and false negatives at the 5% operating point.
- Top positive and negative Linear SVM coefficients.
- PR curve and feature-interpretation figures.

## Reproduce

Create the environment and run:

```bash
pip install -r requirements.txt
bash run_all.sh
```

The script regenerates:

1. Final cleaned data and baseline.
2. EDA figures.
3. Model comparison and predictions.
4. Validation figures.
5. Ablation and bootstrap analysis.
6. Test evaluation and figures.

The interactive v2 data-preparation notebook is retained for traceability but
is not run by `run_all.sh`, because it uses Colab file-upload commands.

The large raw, intermediate, and processed CSV files are not tracked by Git.
See `data/README.md` for the source and regeneration instructions.

## Key outputs

- `02_modelling/models/selected_model.joblib`
- `02_modelling/predictions/selected_model_predictions.csv`
- `02_modelling/reports/modeling_summary.md`
- `02_modelling/reports/model_comparison.csv`
- `02_modelling/reports/bootstrap_uncertainty.csv`
- `03_evaluation/outputs/test_metrics.json`
- `03_evaluation/outputs/test_review_budget.csv`
- `03_evaluation/outputs/test_error_cases.csv`
- `03_evaluation/outputs/figures/test_pr_curve.png`
- `03_evaluation/outputs/figures/top_features.png`

## Interactive demo

`04_app/` contains a small Streamlit application for single-posting and batch
CSV ranking. The app loads the frozen model and presents the score as a review
priority rather than a probability.

```bash
pip install -r 04_app/requirements.txt
streamlit run 04_app/app.py
```

The command-line interface is available at `04_app/cli.py`.

## Data source

The source dataset is the Employment Scam Aegean Dataset (EMSCAD), distributed
through Kaggle:

- https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction
- https://doi.org/10.3390/fi9010006
- Kaggle license metadata: CC0 1.0 Public Domain

The data contain historical English-language job postings from 2012-2014.
The model is an evaluation prototype and should be used only to assist human
review, not to automatically reject postings.
