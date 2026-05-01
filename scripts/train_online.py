#!/usr/bin/env python3
"""Online training script with incremental buffering and hot-swap support."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.online_trainer import OnlineTrainer


def main() -> None:
    parser = argparse.ArgumentParser(description="Run online incremental training and hot-swap the model artifact.")
    parser.add_argument("--data_dir", type=str, default="data/raw", help="Directory containing incremental CSV data.")
    parser.add_argument("--artifact_path", type=str, default="data/models/model_artifacts.pkl", help="Target model artifact path.")
    parser.add_argument("--output_dir", type=str, default="data/models", help="Directory for metrics and reports.")
    parser.add_argument("--figures_dir", type=str, default="results/figures", help="Directory for evaluation figures.")
    parser.add_argument("--models", type=str, default="random_forest,xgboost", help="Comma-separated base models: random_forest,xgboost,extra_trees,lightgbm,auto.")
    parser.add_argument("--use_stacking", action="store_true", help="Enable stacking ensemble for the replacement model.")
    parser.add_argument("--test_size", type=float, default=0.2, help="Validation split ratio.")
    parser.add_argument("--window_rows", type=int, default=200000, help="Maximum rows to buffer for one online update.")
    parser.add_argument("--max_files", type=int, default=None, help="Optional CSV file limit.")
    parser.add_argument(
        "--max_rows_per_file",
        type=int,
        default=50000,
        help="Row limit per CSV file (default 50,000 for balanced multi-file buffering; set 0 to disable).",
    )
    parser.add_argument("--chunk_size", type=int, default=50000, help="Chunk size used while streaming CSV data.")
    parser.add_argument("--rf_estimators", type=int, default=200, help="RandomForest tree count.")
    parser.add_argument("--xgb_estimators", type=int, default=200, help="XGBoost tree count.")
    parser.add_argument("--n_jobs", type=int, default=1, help="Parallel jobs for model training.")
    parser.add_argument("--random_state", type=int, default=42, help="Random seed.")
    parser.add_argument("--backup", dest="backup_on_update", action="store_true", help="Create a backup before overwriting the current artifact.")
    parser.add_argument("--no-backup", dest="backup_on_update", action="store_false", help="Skip backup creation before overwrite.")
    parser.set_defaults(backup_on_update=True)
    parser.add_argument("--persist-buffer", dest="persist_buffer_snapshot", action="store_true", help="Persist buffered online window to output_dir/online_window_last.csv.")
    parser.add_argument("--no-persist-buffer", dest="persist_buffer_snapshot", action="store_false", help="Do not persist buffered online window snapshot.")
    parser.set_defaults(persist_buffer_snapshot=True)
    parser.add_argument("--quiet", action="store_true", help="Disable detailed progress logs.")
    args = parser.parse_args()

    trainer = OnlineTrainer(
        data_dir=args.data_dir,
        artifact_path=args.artifact_path,
        output_dir=args.output_dir,
        figures_dir=args.figures_dir,
        model_names=args.models,
        use_stacking=args.use_stacking,
        test_size=args.test_size,
        random_state=args.random_state,
        chunk_size=args.chunk_size,
        window_rows=args.window_rows,
        max_files=args.max_files,
        max_rows_per_file=args.max_rows_per_file,
        rf_estimators=args.rf_estimators,
        xgb_estimators=args.xgb_estimators,
        n_jobs=args.n_jobs,
        backup_on_update=args.backup_on_update,
        persist_buffer_snapshot=args.persist_buffer_snapshot,
        verbose=not args.quiet,
    )
    result = trainer.train()

    summary = {
        "artifact_path": str(result.artifact_path),
        "backup_path": str(result.backup_path) if result.backup_path else None,
        "row_count": result.row_count,
        "raw_feature_count": result.raw_feature_count,
        "selected_feature_count": result.selected_feature_count,
        "metrics": {
            "accuracy": result.metrics.get("accuracy"),
            "precision": result.metrics.get("precision"),
            "recall": result.metrics.get("recall"),
            "f1": result.metrics.get("f1"),
        },
        "figures": result.figures,
        "source_files": result.source_files,
        "buffer_path": result.buffer_path,
        "elapsed_seconds": round(result.elapsed_seconds, 2),
        "hot_reload_hint": "API watcher will reload automatically when run_api.py is active.",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
