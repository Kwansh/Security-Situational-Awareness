import argparse
import json
from pathlib import Path

import pandas as pd

from src.model_artifacts import load_artifacts
from src.preprocess import Preprocessor


def main():
    parser = argparse.ArgumentParser(description="Run batch predictions from a CSV file.")
    parser.add_argument("--input", required=True, help="Input CSV file.")
    parser.add_argument("--output", required=True, help="Output CSV file.")
    parser.add_argument("--artifact", default="data/models/model_artifacts.pkl", help="Artifact path.")
    args = parser.parse_args()

    artifacts = load_artifacts(args.artifact)
    df = pd.read_csv(args.input, low_memory=False)

    preprocessor = Preprocessor()
    df = preprocessor.clean(df)
    feature_frame = df.copy()
    if "Label" in feature_frame.columns:
        feature_frame = feature_frame.drop(columns=["Label"])

    available_columns = [column for column in artifacts["feature_columns"] if column in feature_frame.columns]
    missing_columns = sorted(set(artifacts["feature_columns"]) - set(available_columns))
    if missing_columns:
        raise ValueError(f"Missing required feature columns: {missing_columns[:10]}")

    feature_frame = feature_frame[artifacts["feature_columns"]]
    for column in feature_frame.columns:
        feature_frame[column] = pd.to_numeric(feature_frame[column], errors="coerce")
    feature_frame = feature_frame.fillna(feature_frame.median(numeric_only=True)).fillna(0.0)

    scaled = artifacts["scaler"].transform(feature_frame.values)
    selected = artifacts["selector"].transform(scaled)
    predictions = artifacts["model"].predict(selected)
    probabilities = artifacts["model"].predict_proba(selected).max(axis=1)

    reverse_mapping = {value: key for key, value in artifacts.get("label_mapping", {}).items()}
    result = feature_frame.copy()
    result["prediction"] = predictions
    result["prediction_label"] = [reverse_mapping.get(int(pred), str(int(pred))) for pred in predictions]
    result["confidence"] = probabilities

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)

    print(json.dumps({"rows": len(result), "output": str(output_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
