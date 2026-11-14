# Model Selection Summary

## Scope

Three transparent TF-IDF models were compared on the same frozen data split:

- Logistic Regression with balanced class weights.
- Linear SVM with balanced class weights.
- Complement Naive Bayes.

All TF-IDF preprocessing was fitted within each training fold. Hyperparameters
were selected using three-fold stratified cross-validation on the training
split. The validation split was used once to compare the selected candidate
from each model family. The test split was used only to generate predictions
after model selection and was not used for tuning.

## TF-IDF configuration

- Word unigrams and bigrams.
- `min_df=3`.
- `max_df=0.95`.
- Up to 60,000 features.
- Sublinear term frequency scaling.
- Unicode accent stripping and lowercasing.

## Validation results

| Model | Selected parameter | CV AP | Validation AP | Validation ROC-AUC |
|---|---|---:|---:|---:|
| Linear SVM | `C=1.0` | 0.8608 ± 0.0075 | **0.8960** | **0.9852** |
| Logistic Regression | `C=10.0` | 0.8600 ± 0.0075 | 0.8893 | 0.9847 |
| Complement Naive Bayes | `alpha=0.1` | 0.7319 ± 0.0063 | 0.7788 | 0.9649 |

The no-skill baseline has validation AP **0.04497** and ROC-AUC **0.500**.
All three text models substantially outperform it.

## Selected model

**Linear SVM with `C=1.0` and balanced class weights.**

Selection rule: highest validation Average Precision, which directly evaluates
ranking quality for the rare fraudulent class.

## Validation review-budget results

| Model | Reviewed share | Postings reviewed | Frauds found | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Linear SVM | 5% | 118 | 91 | 0.771 | 0.858 |
| Linear SVM | 10% | 236 | 99 | 0.419 | 0.934 |
| Linear SVM | 20% | 472 | 102 | 0.216 | 0.962 |

Reviewing the top 5% of validation postings catches about 85.8% of fraudulent
postings. Reviewing the top 10% catches about 93.4%. Precision falls as the
review budget expands because fraudulent postings are rare.

## Outputs for the evaluation owner

- `predictions/selected_model_predictions.csv`: selected-model validation and
  test scores.
- `predictions/model_predictions.csv`: validation and test scores for all three
  models.
- `reports/model_comparison.csv`: cross-validation and validation metrics.
- `reports/validation_review_budget.csv`: validation precision/recall at 5%,
  10%, and 20% review budgets.
- `models/selected_model.joblib`: serialized selected pipeline.

The final test metrics should be computed once by the evaluation owner from
`selected_model_predictions.csv`. The test split must not be used to revise the
model after its metrics are observed.

## TF-IDF ablation

The selected Linear SVM configuration was held fixed while comparing unigram
and unigram-plus-bigram features on the training and validation splits.

| Configuration | Vocabulary | CV AP | Validation AP | Validation ROC-AUC | Recall @ 5% |
|---|---:|---:|---:|---:|---:|
| Unigram | 25,805 | 0.8370 ± 0.0115 | 0.8822 | 0.9771 | 0.8396 |
| Unigram + bigram | 60,000 | 0.8608 ± 0.0075 | **0.8960** | **0.9852** | **0.8585** |

Adding bigrams improves validation AP by 0.0137 and top-5% recall by 1.89
percentage points. The test split was not used for this ablation.

## Bootstrap uncertainty

Confidence intervals use 2,000 bootstrap resamples with seed 42.

| Split | Metric | Estimate | 95% interval |
|---|---|---:|---:|
| Validation | PR-AUC | 0.8960 | 0.8471-0.9405 |
| Validation | ROC-AUC | 0.9852 | 0.9747-0.9933 |
| Validation | Recall @ 5% | 0.8585 | 0.7903-0.9256 |
| Test | PR-AUC | 0.9466 | 0.9154-0.9713 |
| Test | ROC-AUC | 0.9966 | 0.9945-0.9983 |
| Test | Recall @ 5% | 0.8868 | 0.8291-0.9634 |

The validation and test PR-AUC intervals overlap. The higher test estimate
should therefore be treated as sampling variation, not evidence that the model
became better after selection.

## Limitations

- The SVM score is a ranking score, not a calibrated probability.
- The data use word-level TF-IDF and do not capture all semantic similarity.
- Model selection uses one validation split; three-fold cross-validation
  provides a stability check but not a complete uncertainty analysis.
- The historical EMSCAD data may not represent current job-posting behaviour.
