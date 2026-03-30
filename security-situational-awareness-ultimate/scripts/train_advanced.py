import argparse
from pathlib import Path

from src.model_artifacts import DEFAULT_ARTIFACT_NAME, save_artifacts
from scripts.train import build_training_pipeline


def main():
    parser = argparse.ArgumentParser(description="Train the advanced ensemble model.")
    parser.add_argument("--input", type=str, default="data/raw", help="Input data directory.")
    parser.add_argument("--output", type=str, default="", help="Artifact output path.")
    parser.add_argument("--k-features", dest="k_features", type=int, default=30, help="Number of selected features.")
    parser.add_argument("--use-stacking", dest="use_stacking", action="store_true", help="Enable stacking.")
    parser.add_argument("--test-size", dest="test_size", type=float, default=0.2, help="Validation split ratio.")
    parser.add_argument("--max-files", dest="max_files", type=int, default=None, help="Optional CSV file limit.")
    args = parser.parse_args()

    result = build_training_pipeline(
        data_dir=args.input,
        k_features=args.k_features,
        use_stacking=args.use_stacking,
        test_size=args.test_size,
        max_files=args.max_files,
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
    )

    print(f"Saved advanced model artifacts to {output_path}")
    print(f"Accuracy: {result['metrics']['accuracy']:.4f}")
    print(f"F1: {result['metrics']['f1']:.4f}")


if __name__ == "__main__":
    main()
