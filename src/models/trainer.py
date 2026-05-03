from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder


class EncodedLabelClassifier(BaseEstimator, ClassifierMixin):
    """Compatibility wrapper that encodes labels before fitting."""

    def __init__(self, estimator):
        self.estimator = estimator

    def fit(self, X, y, **fit_params):
        y_arr = np.asarray(y)
        self.label_encoder_ = LabelEncoder()
        y_encoded = self.label_encoder_.fit_transform(y_arr)
        self.classes_ = np.asarray(self.label_encoder_.classes_)
        self.estimator_ = clone(self.estimator)

        params = dict(fit_params)
        eval_set = params.get("eval_set")
        if eval_set:
            encoded_eval = []
            for X_eval, y_eval in eval_set:
                y_eval_arr = np.asarray(y_eval)
                y_eval_encoded = self.label_encoder_.transform(y_eval_arr)
                encoded_eval.append((X_eval, y_eval_encoded))
            params["eval_set"] = encoded_eval

        self.estimator_.fit(X, y_encoded, **params)
        return self

    def predict(self, X):
        encoded_pred = np.asarray(self.estimator_.predict(X)).astype(int)
        encoded_pred = np.clip(encoded_pred, 0, max(0, len(self.classes_) - 1))
        return self.label_encoder_.inverse_transform(encoded_pred)

    def predict_proba(self, X):
        proba = np.asarray(self.estimator_.predict_proba(X))
        if proba.ndim == 1:
            proba = np.column_stack([1.0 - proba, proba])

        expected = len(self.classes_)
        if proba.shape[1] == expected:
            return proba

        aligned = np.zeros((proba.shape[0], expected), dtype=float)
        width = min(expected, proba.shape[1])
        aligned[:, :width] = proba[:, :width]
        denom = aligned.sum(axis=1, keepdims=True)
        return np.divide(aligned, denom, out=np.zeros_like(aligned), where=denom != 0)

    def __getattr__(self, name):
        if name.endswith("_") and "estimator_" in self.__dict__:
            return getattr(self.estimator_, name)
        raise AttributeError(name)


@dataclass
class TrainingResult:
    rf: Any = None
    xgb: Any = None
    lgb: Any = None
    et: Any = None
    metrics: Optional[Dict[str, float]] = None


class ModelTrainer:
    """Minimal trainer compatibility layer."""

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.rf = None
        self.xgb = None
        self.lgb = None
        self.et = None

    def train_models(self, X: np.ndarray, y: np.ndarray) -> TrainingResult:
        self.rf = RandomForestClassifier(n_estimators=100, random_state=self.random_state)
        self.rf.fit(X, y)
        return TrainingResult(rf=self.rf, metrics={"accuracy": float(self.rf.score(X, y))})
