#!/usr/bin/env python3
"""Training script for the security situational awareness model."""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.loader import DatasetLoader
from src.preprocess.preprocessor import Preprocessor
from src.models.trainer import ModelTrainer
from src.models.ensemble import EnsembleModel
from src.utils.evaluator import Evaluator
from src.utils.model_artifacts import (
    build_latest_artifact_name,
    build_timestamped_artifact_name,
    save_artifacts,
    upsert_model_registry_entry,
)


DEFAULT_MAX_ROWS_PER_FILE = 200000


def _stage_log(message: str) -> None:
    now = time.strftime("%H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def build_training_pipeline(
    data_dir: str,
    input_format: str = "csv",
    k_features: int = 0,
    use_stacking: bool = False,
    test_size: float = 0.2,
    random_state: int = 42,
    max_files: int | None = None,
    max_rows_per_file: int | None = DEFAULT_MAX_ROWS_PER_FILE,
    chunk_size: int = 50000,
    label_manifest: str | None = None,
    default_label: str = "BENIGN",
    rf_estimators: int = 200,
    xgb_estimators: int = 200,
    n_jobs: int = 1,
    model_names: str | None = None,
    verbose: bool = True,
    visualization_dir: str | None = None,
):
    if verbose:
        _stage_log(f"Stage 1/7 - Loading {input_format.upper()} data...")
    if input_format == "pcap":
        from src.data.pcap_dataset import load_label_mapping, load_pcaps_as_dataframe

        labels = load_label_mapping(label_manifest) if label_manifest else None
        if verbose and label_manifest:
            _stage_log(f"Using label manifest: {label_manifest}")
        df = load_pcaps_as_dataframe(
            data_dir=data_dir,
            max_files=max_files,
            label_mapping=labels,
            default_label=default_label,
        )
    else:
        loader = DatasetLoader(data_dir)
        df = loader.load_all(
            max_files=max_files,
            max_rows_per_file=max_rows_per_file,
            chunk_size=chunk_size,
            verbose=verbose,
        )
    if verbose:
        _stage_log(f"Data loaded: {len(df):,} rows, {df.shape[1]} columns")

    if verbose:
        _stage_log("Stage 2/7 - Preprocessing data...")
    preprocessor = Preprocessor()
    df = preprocessor.clean(df)
    X, y = preprocessor.split(df)
    if verbose:
        _stage_log(f"Preprocessing done: X={X.shape}, y={y.shape}")
        label_counts = y.value_counts().sort_index()
        _stage_log(
            "Label distribution: "
            + ", ".join([f"{int(k)}={int(v):,}" for k, v in label_counts.items()])
        )
    if y.nunique() < 2:
        raise ValueError(
            "Training requires at least 2 classes. "
            "For PCAP input, provide a label manifest so files/windows can be mapped to attack labels."
        )

    if verbose:
        _stage_log("Stage 3/7 - Splitting train/test sets...")
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y if y.nunique() > 1 else None,
    )
    if verbose:
        _stage_log(f"Split done: train={X_train.shape}, test={X_test.shape}")
        _stage_log(
            f"Train labels={int(y_train.nunique())}, Test labels={int(y_test.nunique())}"
        )

    if verbose:
        _stage_log("Stage 4/7 - Scaling features...")
    X_train_scaled = preprocessor.normalize(X_train.values, fit=True)
    X_test_scaled = preprocessor.normalize(X_test.values, fit=False)

    if verbose:
        _stage_log("Stage 5/7 - Feature selection...")
    from src.utils.feature_selector import FeatureSelector

    selector = FeatureSelector(k=k_features)
    X_train_selected = selector.fit_transform(X_train_scaled, y_train.values)
    X_test_selected = selector.transform(X_test_scaled)
    if verbose:
        _stage_log(
            f"Feature selection done: raw={X.shape[1]}, selected={X_train_selected.shape[1]}"
        )

    if verbose:
        _stage_log(
            f"Stage 6/7 - Training base models ({model_names or 'random_forest,xgboost'})..."
        )
    trainer = ModelTrainer(
        random_state=random_state,
        rf_estimators=rf_estimators,
        xgb_estimators=xgb_estimators,
        n_jobs=n_jobs,
        model_names=model_names,
    ).train_models(
        X_train_selected,
        y_train.values,
        log_fn=_stage_log if verbose else None,
    )

    base_models = dict(trainer.base_models)
    if not base_models:
        base_models = {}
        if trainer.rf is not None:
            base_models["random_forest"] = trainer.rf
        if trainer.xgb is not None:
            base_models["xgboost"] = trainer.xgb
        if trainer.extra_trees is not None:
            base_models["extra_trees"] = trainer.extra_trees
        if trainer.lightgbm is not None:
            base_models["lightgbm"] = trainer.lightgbm
    if not base_models:
        raise RuntimeError("No trained base models available for ensemble fitting.")

    if verbose:
        _stage_log(
            f"Stage 6/7 - Training ensemble model with {len(base_models)} base model(s)..."
        )
    ensemble = EnsembleModel(
        base_models,
        use_stacking=use_stacking,
    ).fit(X_train_selected, y_train.values, log_fn=_stage_log if verbose else None)

    if verbose:
        _stage_log("Stage 7/7 - Evaluating model...")
    metrics, y_pred = Evaluator.evaluate_with_predictions(ensemble, X_test_selected, y_test.values)
    class_names = None
    if preprocessor.label_mapping:
        reverse = {value: key for key, value in preprocessor.label_mapping.items()}
        class_names = [str(reverse.get(label, label)) for label in sorted(set(y_test.values) | set(y_pred))]
    figures = Evaluator.save_visualizations(
        y_true=y_test.values,
        y_pred=y_pred,
        metrics=metrics,
        output_dir=visualization_dir or "results/figures",
        class_names=class_names,
    )
    if verbose:
        _stage_log(
            f"Evaluation done: accuracy={metrics['accuracy']:.4f}, f1={metrics['f1']:.4f}"
        )
        _stage_log(f"Visualization saved: {figures}")

    return {
        "ensemble": ensemble,
        "preprocessor": preprocessor,
        "selector": selector,
        "metrics": metrics,
        "feature_columns": preprocessor.feature_columns,
        "selected_feature_count": int(X_train_selected.shape[1]),
        "raw_feature_count": int(X.shape[1]),
        "row_count": int(len(df)),
        "max_rows_per_file": max_rows_per_file,
        "figures": figures,
    }


def main():
    parser = argparse.ArgumentParser(description="Train the DDoS detection model.")
    parser.add_argument(
        "--data_dir",
        "--input",
        dest="data_dir",
        type=str,
        default="data/raw",
        help="Input data directory.",
    )
    parser.add_argument(
        "--input_format",
        type=str,
        default="csv",
        choices=["csv", "pcap"],
        help="Input format: csv or pcap.",
    )
    parser.add_argument(
        "--output_dir", type=str, default="data/models", help="Output directory."
    )
    parser.add_argument(
        "--output_path",
        "--output",
        dest="output_path",
        type=str,
        default="",
        help="Artifact output path.",
    )
    parser.add_argument(
        "--k_features",
        type=int,
        default=0,
        help="Number of selected features. Use 0 to keep all features.",
    )
    parser.add_argument(
        "--use_stacking", action="store_true", help="Enable stacking ensemble."
    )
    parser.add_argument(
        "--models",
        type=str,
        default="random_forest,xgboost",
        help="Comma-separated base models: random_forest,xgboost,extra_trees,lightgbm,auto.",
    )
    parser.add_argument(
        "--test_size", type=float, default=0.2, help="Validation split ratio."
    )
    parser.add_argument(
        "--figures_dir", type=str, default="results/figures", help="Directory to save evaluation figures."
    )
    parser.add_argument(
        "--random_state", type=int, default=42, help="Random seed."
    )
    parser.add_argument(
        "--max_files", type=int, default=None, help="Optional CSV file limit."
    )
    parser.add_argument(
        "--max_rows_per_file",
        type=int,
        default=DEFAULT_MAX_ROWS_PER_FILE,
        help="Rows to load from each CSV file.",
    )
    parser.add_argument(
        "--chunk_size", type=int, default=50000, help="Chunk size for large CSV reading."
    )
    parser.add_argument(
        "--label_manifest",
        type=str,
        default="",
        help="Optional filename-to-label mapping for PCAP training (.json or .csv).",
    )
    parser.add_argument(
        "--default_label",
        type=str,
        default="BENIGN",
        help="Fallback label for PCAP files when mapping is missing.",
    )
    parser.add_argument("--rf_estimators", type=int, default=200, help="RandomForest tree count.")
    parser.add_argument("--xgb_estimators", type=int, default=200, help="XGBoost tree count.")
    parser.add_argument("--n_jobs", type=int, default=1, help="Parallel jobs for base model training.")
    parser.add_argument(
        "--quiet", action="store_true", help="Disable detailed progress logs."
    )
    args = parser.parse_args()
    if not (0.05 <= args.test_size <= 0.5):
        raise ValueError("--test_size must be between 0.05 and 0.5")

    start_time = time.time()
    result = build_training_pipeline(
        data_dir=args.data_dir,
        input_format=args.input_format,
        k_features=args.k_features,
        use_stacking=args.use_stacking,
        test_size=args.test_size,
        random_state=args.random_state,
        max_files=args.max_files,
        max_rows_per_file=args.max_rows_per_file,
        chunk_size=args.chunk_size,
        label_manifest=args.label_manifest or None,
        default_label=args.default_label,
        rf_estimators=args.rf_estimators,
        xgb_estimators=args.xgb_estimators,
        n_jobs=args.n_jobs,
        model_names=args.models,
        verbose=not args.quiet,
        visualization_dir=args.figures_dir,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    latest_artifact_path = Path(args.output_path) if args.output_path else output_dir / build_latest_artifact_name()
    timestamped_artifact_path = latest_artifact_path.with_name(
        build_timestamped_artifact_name(latest_artifact_path.stem.replace("_latest", ""))
    )
    save_artifacts(
        timestamped_artifact_path,
        model=result["ensemble"],
        scaler=result["preprocessor"].scaler,
        selector=result["selector"],
        feature_columns=result["feature_columns"],
        label_mapping=result["preprocessor"].label_mapping,
        metrics=result["metrics"],
        preprocessor=result["preprocessor"],
    )
    shutil.copy2(timestamped_artifact_path, latest_artifact_path)
    upsert_model_registry_entry(
        output_dir,
        artifact_path=timestamped_artifact_path,
        latest_path=latest_artifact_path,
        status="current",
        metadata={
            "input_format": args.input_format,
            "data_dir": args.data_dir,
            "label_manifest": args.label_manifest or None,
            "default_label": args.default_label,
            "row_count": result["row_count"],
            "raw_feature_count": result["raw_feature_count"],
            "selected_feature_count": result["selected_feature_count"],
            "metrics": {key: value for key, value in result["metrics"].items() if key != "report"},
        },
    )

    metrics_path = output_dir / "metrics.json"
    metrics_to_store = {
        key: value for key, value in result["metrics"].items() if key != "report"
    }
    metrics_to_store["raw_feature_count"] = result["raw_feature_count"]
    metrics_to_store["selected_feature_count"] = result["selected_feature_count"]
    metrics_to_store["row_count"] = result["row_count"]
    metrics_to_store["figures"] = result["figures"]
    metrics_path.write_text(json.dumps(metrics_to_store, indent=2), encoding="utf-8")

    print(f"Saved timestamped model artifacts to {timestamped_artifact_path}")
    print(f"Updated latest model artifact at {latest_artifact_path}")
    print(json.dumps(metrics_to_store, indent=2))
    print(f"Total elapsed time: {time.time() - start_time:.1f}s")


if __name__ == "__main__":
    main()
