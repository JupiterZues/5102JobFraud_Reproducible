# Final Data and Modelling

Run scripts from the workpack root in this order:

```bash
python 02_modelling/scripts/prepare_final_data.py
python 02_modelling/scripts/make_eda.py
python 02_modelling/scripts/train_models.py
python 02_modelling/scripts/make_model_figures.py
python 02_modelling/scripts/run_ablation_and_uncertainty.py
```

## Data flow

1. `prepare_final_data.py`
   - Reads `data/raw/fake_job_postings.csv`.
   - Reconstructs `text_all`.
   - Removes exact and canonical duplicate postings.
   - Creates the final stratified split.
   - Writes `data/processed/jobs_clean.csv`.
   - Writes a no-skill baseline and data-validation files.

2. `train_models.py`
   - Fits TF-IDF inside every cross-validation fold.
   - Compares Logistic Regression, Linear SVM, and Complement Naive Bayes.
   - Selects a model using validation Average Precision.
   - Writes predictions for validation and test without re-tuning on test.

3. `make_model_figures.py`
   - Produces validation PR curves and review-budget figures.

4. `run_ablation_and_uncertainty.py`
   - Compares unigram and unigram-plus-bigram TF-IDF.
   - Computes bootstrap confidence intervals for validation and test metrics.

## Main outputs

- `models/selected_model.joblib`
- `predictions/model_predictions.csv`
- `predictions/selected_model_predictions.csv`
- `outputs/jobs_clean.csv`
- `outputs/data_validation.json`
- `outputs/data_manifest.json`
- `reports/model_comparison.csv`
- `reports/validation_review_budget.csv`
- `reports/modeling_summary.md`

## Model-selection rules

- Fit all learned components on training data only.
- Select the model and hyperparameters using validation data.
- Do not tune or select an operating point on the test split.
- Treat SVM scores as ranking values, not calibrated probabilities.
