#!/usr/bin/env python3
"""
高级训练脚本 - 项目 1 的核心功能
支持 Stacking 集成、多模型对比、特征选择等高级功能。
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.model_artifacts import DEFAULT_ARTIFACT_NAME, save_artifacts
from scripts.train import build_training_pipeline


def main():
    parser = argparse.ArgumentParser(description="Train the advanced ensemble model.")
    parser.add_argument("--input", type=str, default="data/raw", help="Input data directory.")
    parser.add_argument("--output", type=str, default="", help="Artifact output path.")
    parser.add_argument("--k-features", dest="k_features", type=int, default=0, help="Number of selected features. Use 0 to keep all features.")
    parser.add_argument("--use-stacking", dest="use_stacking", action="store_true", help="Enable stacking.")
    parser.add_argument("--models", type=str, default="auto", help="Comma-separated base models: random_forest,xgboost,extra_trees,lightgbm,auto.")
    parser.add_argument("--test-size", dest="test_size", type=float, default=0.2, help="Validation split ratio.")
    parser.add_argument("--figures-dir", dest="figures_dir", type=str, default="results/figures", help="Directory to save evaluation figures.")
    parser.add_argument("--max-files", dest="max_files", type=int, default=None, help="Optional CSV file limit.")
    parser.add_argument("--max-rows-per-file", dest="max_rows_per_file", type=int, default=200000, help="Rows to load from each CSV file. Use 0 to load full files.")
    parser.add_argument("--chunk-size", dest="chunk_size", type=int, default=50000, help="Chunk size for large CSV reading.")
    parser.add_argument("--rf-estimators", dest="rf_estimators", type=int, default=200, help="RandomForest tree count.")
    parser.add_argument("--xgb-estimators", dest="xgb_estimators", type=int, default=200, help="XGBoost tree count.")
    parser.add_argument("--n-jobs", dest="n_jobs", type=int, default=1, help="Parallel jobs for base model training.")
    parser.add_argument("--quiet", action="store_true", help="Disable detailed progress logs.")
    args = parser.parse_args()

    result = build_training_pipeline(
        data_dir=args.input,
        k_features=args.k_features,
        use_stacking=args.use_stacking,
        test_size=args.test_size,
        max_files=args.max_files,
        max_rows_per_file=args.max_rows_per_file,
        chunk_size=args.chunk_size,
        rf_estimators=args.rf_estimators,
        xgb_estimators=args.xgb_estimators,
        n_jobs=args.n_jobs,
        model_names=args.models,
        verbose=not args.quiet,
        visualization_dir=args.figures_dir,
    )

    output_path = Path(args.output) if args.output else Path("data/models") / DEFAULT_ARTIFACT_NAME
    save_artifacts(
        output_path,
        model=result["ensemble"],
        scaler=result["preprocessor"].scaler,
        selector=result["selector"],
        feature_columns=result["feature_columns"],
        label_mapping=result["preprocessor"].label_mapping,
        metrics=result["metrics"],
        preprocessor=result["preprocessor"],
    )

    print(f"Saved advanced model artifacts to {output_path}")
    print(f"Rows loaded: {result['row_count']}")
    print(f"Raw features: {result['raw_feature_count']}")
    print(f"Selected features: {result['selected_feature_count']}")
    print(f"Accuracy: {result['metrics']['accuracy']:.4f}")
    print(f"F1: {result['metrics']['f1']:.4f}")
    print(f"Figures: {result['figures']}")


if __name__ == "__main__":
    main()
