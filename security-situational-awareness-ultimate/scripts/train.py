import argparse
import json
from pathlib import Path

from sklearn.model_selection import train_test_split

from src.data_loader import DatasetLoader
from src.ensemble_model import EnsembleModel
from src.evaluator import Evaluator
from src.feature_selector import FeatureSelector
from src.model_artifacts import DEFAULT_ARTIFACT_NAME, save_artifacts
from src.model_trainer import ModelTrainer
from src.preprocess import Preprocessor


def build_training_pipeline(
    data_dir: str,
    k_features: int = 30,
    use_stacking: bool = False,
    test_size: float = 0.2,
    random_state: int = 42,
    max_files: int | None = None,
):
    loader = DatasetLoader(data_dir)
    df = loader.load_all(max_files=max_files)

    preprocessor = Preprocessor()
    df = preprocessor.clean(df)
    X, y = preprocessor.split(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y if y.nunique() > 1 else None,
    )

    X_train_scaled = preprocessor.normalize(X_train.values, fit=True)
    X_test_scaled = preprocessor.normalize(X_test.values, fit=False)

    selector = FeatureSelector(k=k_features)
    X_train_selected = selector.fit_transform(X_train_scaled, y_train.values)
    X_test_selected = selector.transform(X_test_scaled)

    trainer = ModelTrainer(random_state=random_state).train_models(X_train_selected, y_train.values)
    ensemble = EnsembleModel(
        {"rf": trainer.rf, "xgb": trainer.xgb},
        use_stacking=use_stacking,
    ).fit(X_train_selected, y_train.values)

    metrics = Evaluator.evaluate(ensemble, X_test_selected, y_test.values)
    return {
        "ensemble": ensemble,
        "preprocessor": preprocessor,
        "selector": selector,
        "metrics": metrics,
        "feature_columns": preprocessor.feature_columns,
    }


def main():
    parser = argparse.ArgumentParser(description="Train the DDoS detection model.")
    parser.add_argument("--data_dir", "--input", dest="data_dir", type=str, default="data/raw", help="Input data directory.")
    parser.add_argument("--output_dir", type=str, default="data/models", help="Output directory.")
    parser.add_argument("--output_path", "--output", dest="output_path", type=str, default="", help="Artifact output path.")
    parser.add_argument("--k_features", type=int, default=30, help="Number of selected features.")
    parser.add_argument("--use_stacking", action="store_true", help="Enable stacking ensemble.")
    parser.add_argument("--test_size", type=float, default=0.2, help="Validation split ratio.")
    parser.add_argument("--random_state", type=int, default=42, help="Random seed.")
    parser.add_argument("--max_files", type=int, default=None, help="Optional CSV file limit.")
    args = parser.parse_args()

    result = build_training_pipeline(
        data_dir=args.data_dir,
        k_features=args.k_features,
        use_stacking=args.use_stacking,
        test_size=args.test_size,
        random_state=args.random_state,
        max_files=args.max_files,
    )

    output_dir = Path(args.output_dir)
    artifact_path = Path(args.output_path) if args.output_path else output_dir / DEFAULT_ARTIFACT_NAME
    save_artifacts(
        artifact_path,
        model=result["ensemble"],
        scaler=result["preprocessor"].scaler,
        selector=result["selector"],
        feature_columns=result["feature_columns"],
        label_mapping=result["preprocessor"].label_mapping,
        metrics=result["metrics"],
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics.json"
    metrics_to_store = {key: value for key, value in result["metrics"].items() if key != "report"}
    metrics_path.write_text(json.dumps(metrics_to_store, indent=2), encoding="utf-8")

    print(f"Saved model artifacts to {artifact_path}")
    print(json.dumps(metrics_to_store, indent=2))


if __name__ == "__main__":
    main()
