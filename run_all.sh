#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

python 02_modelling/scripts/prepare_final_data.py
python 02_modelling/scripts/make_eda.py
python 02_modelling/scripts/train_models.py
python 02_modelling/scripts/make_model_figures.py
python 02_modelling/scripts/run_ablation_and_uncertainty.py
python 03_evaluation/scripts/evaluate_selected_model.py
