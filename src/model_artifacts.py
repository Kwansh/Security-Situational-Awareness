<<<<<<< HEAD
﻿"""Compatibility wrapper for model artifact utilities."""

from src.utils.model_artifacts import *  # noqa: F401,F403
=======
﻿from pathlib import Path

import joblib


DEFAULT_ARTIFACT_NAME = "model_artifacts.pkl"


def save_artifacts(
    output_path,
    *,
    model,
    scaler,
    selector,
    feature_columns,
    label_mapping,
    metrics,
):
    artifact = {
        "model": model,
        "scaler": scaler,
        "selector": selector,
        "feature_columns": list(feature_columns),
        "label_mapping": label_mapping or {},
        "metrics": metrics,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output_path)
    return output_path


def load_artifacts(path):
    return joblib.load(path)
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
