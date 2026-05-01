"""Machine-learning detector with robust model loading and inference."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import joblib
import numpy as np


class MLDetector:
    """Wrapper around a trained classifier for attack detection."""

    BENIGN_LABELS = {"normal", "benign", "0"}

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path
        self.feature_columns: list[str] = []
        self.label_mapping: dict[str, int] = {}
        self.is_loaded = False

    def load_model(self, model_path: Optional[str] = None) -> bool:
        path = Path(model_path or self.model_path or "")
        if not str(path):
            raise ValueError("Model path not specified")
        if not path.exists():
            self.is_loaded = False
            return False

        try:
            loaded = joblib.load(path)
            if isinstance(loaded, dict):
                self.model = loaded.get("model") or loaded.get("ensemble") or loaded.get("classifier")
                self.feature_columns = list(loaded.get("feature_columns") or loaded.get("feature_names") or [])
                self.label_mapping = dict(loaded.get("label_mapping") or {})
            else:
                self.model = loaded
                self.feature_columns = []
                self.label_mapping = {}

            self.is_loaded = self.model is not None
            return self.is_loaded
        except Exception:
            self.model = None
            self.is_loaded = False
            return False

    @staticmethod
    def _to_2d(features: np.ndarray | Iterable[float]) -> np.ndarray:
        arr = np.asarray(features, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr

    def _predict_core(self, features: np.ndarray) -> tuple[np.ndarray, Optional[np.ndarray]]:
        if not self.is_loaded or self.model is None:
            raise RuntimeError("Model not loaded")

        predictions = np.asarray(self.model.predict(features))
        probabilities = None
        if hasattr(self.model, "predict_proba"):
            try:
                probabilities = np.asarray(self.model.predict_proba(features))
            except Exception:
                probabilities = None
        return predictions, probabilities

    def _decode_label(self, prediction: Any) -> str:
        if self.label_mapping:
            reverse_mapping = {int(v): str(k) for k, v in self.label_mapping.items()}
            try:
                return reverse_mapping.get(int(prediction), str(prediction))
            except (TypeError, ValueError):
                return str(prediction)
        return str(prediction)

    def predict(self, features: np.ndarray | Iterable[float]) -> Dict[str, Any]:
        features_2d = self._to_2d(features)
        predictions, probabilities = self._predict_core(features_2d)

        prediction = predictions[0]
        attack_type = self._decode_label(prediction)
        confidence = float(np.max(probabilities[0])) if probabilities is not None else 0.5

        return {
            "prediction": int(prediction) if str(prediction).isdigit() else prediction,
            "attack_type": attack_type,
            "is_attack": str(attack_type).strip().lower() not in self.BENIGN_LABELS,
            "confidence": confidence,
            "probabilities": probabilities[0].tolist() if probabilities is not None else None,
        }

    def predict_batch(self, features: np.ndarray | Iterable[Iterable[float]]) -> Dict[str, Any]:
        features_2d = self._to_2d(features)
        predictions, probabilities = self._predict_core(features_2d)

        attack_types = [self._decode_label(pred) for pred in predictions]
        confidences = (
            [float(np.max(row)) for row in probabilities]
            if probabilities is not None
            else [0.5] * len(predictions)
        )

        return {
            "predictions": [int(p) if str(p).isdigit() else p for p in predictions.tolist()],
            "attack_types": attack_types,
            "is_attacks": [str(a).strip().lower() not in self.BENIGN_LABELS for a in attack_types],
            "confidences": confidences,
            "probabilities": probabilities.tolist() if probabilities is not None else None,
        }

    def get_model_info(self) -> Dict[str, Any]:
        if not self.is_loaded:
            return {"loaded": False}

        return {
            "loaded": True,
            "model_type": type(self.model).__name__,
            "feature_columns": self.feature_columns,
            "label_mapping": self.label_mapping,
            "n_features": len(self.feature_columns) or None,
            "n_classes": len(self.label_mapping) or None,
        }
