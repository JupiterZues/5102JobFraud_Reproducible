# Data Files

Large CSV files are intentionally not tracked in Git.

Expected local layout:

```text
data/
  raw/
    fake_job_postings.csv
  intermediate/
    jobs_clean_v2.csv
  processed/
    jobs_clean.csv
```

The raw dataset is the Employment Scam Aegean Dataset (EMSCAD), available from:

https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction

After placing the raw file at `data/raw/fake_job_postings.csv`, run:

```bash
python 02_modelling/scripts/prepare_final_data.py
```

This regenerates the final processed data, baseline predictions, validation
report, and manifest. The expected file hashes are recorded in
`02_modelling/outputs/data_manifest.json`.
