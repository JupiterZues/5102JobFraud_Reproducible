# Evaluation

This folder reproduces the final test evaluation from the frozen Linear SVM
predictions.

## Files

- `scripts/evaluate_selected_model.py`: recomputes all evaluation outputs.
- `outputs/test_metrics.json`: PR-AUC, ROC-AUC, and review-budget metrics.
- `outputs/test_review_budget.csv`: 5%, 10%, and 20% review budgets.
- `outputs/test_confusion_matrix_5pct.csv`: confusion matrix at 5% capacity.
- `outputs/test_error_cases.csv`: all 24 false positives and 12 false
  negatives at the 5% operating point.
- `outputs/top_text_features.csv`: strongest positive and negative SVM
  coefficients.
- `outputs/figures/test_pr_curve.png`: test precision-recall curve.
- `outputs/figures/top_features.png`: lexical feature interpretation.

## Reproduce

From the root of this reproducible workpack:

```bash
python 03_evaluation/scripts/evaluate_selected_model.py
```

The script reads the frozen test predictions and must not be used to retrain or
reselect the model.

## Final test results

- Test postings: 2,358.
- Fraudulent postings: 106.
- PR-AUC: 0.9466.
- ROC-AUC: 0.9966.
- Top 5% reviewed: 118 postings, 94 fraudulent, recall 88.7%, precision 79.7%.
- Top 10% reviewed: 236 postings, 105 fraudulent, recall 99.1%, precision 44.5%.
- Top 20% reviewed: 472 postings, all 106 fraudulent, precision 22.5%.

The SVM score is a ranking value, not a calibrated probability.
