<<<<<<< HEAD
﻿#!/usr/bin/env python3
"""Batch prediction script for the security situational awareness project."""

from __future__ import annotations

import argparse
import json
import sys
=======
﻿import argparse
import json
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
from pathlib import Path

import pandas as pd

<<<<<<< HEAD
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.alert import get_alert_manager
from src.utils.detection_logger import load_summary, log_detection
from src.utils.model_artifacts import DEFAULT_ARTIFACT_NAME, load_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Run batch predictions from a CSV file.")
    parser.add_argument("--input", required=True, help="Input CSV file.")
    parser.add_argument("--output", required=True, help="Output CSV file.")
    parser.add_argument("--artifact", default=f"data/models/{DEFAULT_ARTIFACT_NAME}", help="Artifact path.")
    parser.add_argument("--source", default="batch_predict", help="Detection source tag.")
    args = parser.parse_args()

    artifacts = load_artifacts(args.artifact)
    preprocessor = artifacts.get("preprocessor")
    if preprocessor is None:
        raise ValueError("Artifact does not contain the preprocessor. Please retrain the model.")

    df = pd.read_csv(args.input, low_memory=False)
    feature_frame = preprocessor.transform_dataframe(df, fit=False)
=======
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
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39

    scaled = artifacts["scaler"].transform(feature_frame.values)
    selected = artifacts["selector"].transform(scaled)
    predictions = artifacts["model"].predict(selected)
    probabilities = artifacts["model"].predict_proba(selected).max(axis=1)

    reverse_mapping = {value: key for key, value in artifacts.get("label_mapping", {}).items()}
    result = feature_frame.copy()
    result["prediction"] = predictions
    result["prediction_label"] = [reverse_mapping.get(int(pred), str(int(pred))) for pred in predictions]
    result["confidence"] = probabilities
<<<<<<< HEAD
    result["is_attack"] = result["prediction_label"].astype(str).str.lower().ne("benign")

    event_records = []
    for idx, row in result.iterrows():
        event = log_detection(
            {
                "prediction": int(row["prediction"]),
                "prediction_label": row["prediction_label"],
                "confidence": float(row["confidence"]),
                "timestamp": pd.Timestamp.utcnow().isoformat(),
            },
            source=args.source,
            input_kind="csv",
            alert=False,
        )
        event["index"] = int(idx)
        event_records.append(event)

    alert_manager = get_alert_manager()
    batch_alert = None
    if event_records:
        batch_alert = alert_manager.notify_batch(events=event_records, summary=load_summary(), source=args.source)
=======
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)

<<<<<<< HEAD
    print(
        json.dumps(
            {
                "rows": len(result),
                "output": str(output_path),
                "summary": load_summary(),
                "batch_alert": batch_alert,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
=======
    print(json.dumps({"rows": len(result), "output": str(output_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
