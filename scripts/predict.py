#!/usr/bin/env python3
"""Batch prediction script for CSV files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.alert import get_alert_manager
from src.utils.detection_logger import is_attack_label, load_summary, log_detection
from src.utils.model_artifacts import DEFAULT_ARTIFACT_NAME, load_artifacts


def _load_prediction_artifacts(artifact_path: str | Path) -> dict:
    artifacts = load_artifacts(artifact_path)
    preprocessor = artifacts.get("preprocessor")
    if preprocessor is None:
        raise ValueError("Artifact does not contain a preprocessor.")
    for key in ("scaler", "selector", "model"):
        if artifacts.get(key) is None:
            raise ValueError(f"Artifact does not contain required key: {key}")
    return artifacts


def _reverse_label_mapping(label_mapping: dict) -> dict[int, str]:
    reverse: dict[int, str] = {}
    for key, value in (label_mapping or {}).items():
        try:
            reverse[int(value)] = str(key)
        except (TypeError, ValueError):
            continue
    return reverse


def main() -> None:
    parser = argparse.ArgumentParser(description="Run batch predictions from a CSV file.")
    parser.add_argument("--input", required=True, help="Input CSV file.")
    parser.add_argument("--output", required=True, help="Output CSV file.")
    parser.add_argument(
        "--artifact",
        default=f"data/models/{DEFAULT_ARTIFACT_NAME}",
        help="Model artifact path.",
    )
    parser.add_argument("--source", default="batch_predict", help="Detection source tag.")
    args = parser.parse_args()

    artifacts = _load_prediction_artifacts(args.artifact)
    preprocessor = artifacts["preprocessor"]

    df = pd.read_csv(args.input, low_memory=False)
    df = preprocessor.clean(df)
    feature_frame = preprocessor.transform_dataframe(df, fit=False)

    scaled = artifacts["scaler"].transform(feature_frame.values)
    selected = artifacts["selector"].transform(scaled)
    predictions = artifacts["model"].predict(selected)
    if hasattr(artifacts["model"], "predict_proba"):
        probabilities = artifacts["model"].predict_proba(selected).max(axis=1)
    else:
        probabilities = pd.Series([0.5] * len(predictions), dtype=float).to_numpy()

    reverse_mapping = _reverse_label_mapping(artifacts.get("label_mapping", {}))
    result = feature_frame.copy()
    result["prediction"] = predictions
    result["prediction_label"] = [
        reverse_mapping.get(int(pred), str(int(pred))) for pred in predictions
    ]
    result["confidence"] = probabilities
    result["is_attack"] = result["prediction_label"].map(is_attack_label)

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
        batch_alert = alert_manager.notify_batch(
            events=event_records,
            summary=load_summary(),
            source=args.source,
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)

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
