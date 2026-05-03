from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional

import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.utils.validation import check_is_fitted

try:  # pragma: no cover
    import xgboost as xgb

    HAS_XGB = True
except Exception:  # pragma: no cover
    HAS_XGB = False

try:  # pragma: no cover
    import lightgbm as lgb

    HAS_LGB = True
except Exception:  # pragma: no cover
    HAS_LGB = False


LogFn = Optional[Callable[[str], None]]


def _format_eta(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _progress_bar(progress: float, width: int = 24) -> str:
    progress = min(max(progress, 0.0), 1.0)
    filled = int(round(progress * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _is_estimator_fitted(estimator) -> bool:
    try:
        check_is_fitted(estimator)
        return True
    except Exception:
        return False


class SoftVotingModel:
    """Soft voting without refitting already fitted base estimators."""

    def __init__(self, estimators: List[tuple[str, object]]):
        self.estimators = estimators
        self.classes_: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray, y: np.ndarray):
        self.classes_ = np.unique(y)
        for _, estimator in self.estimators:
            if not _is_estimator_fitted(estimator):
                estimator.fit(X, y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.classes_ is None:
            raise ValueError("SoftVotingModel is not fitted")

        probs = []
        for _, estimator in self.estimators:
            if hasattr(estimator, "predict_proba"):
                prob = estimator.predict_proba(X)
                est_classes = np.asarray(getattr(estimator, "classes_", self.classes_))
                aligned = np.zeros((len(X), len(self.classes_)), dtype=float)
                for idx, cls in enumerate(est_classes):
                    target_idx = np.where(self.classes_ == cls)[0]
                    if len(target_idx) > 0 and idx < prob.shape[1]:
                        aligned[:, target_idx[0]] = prob[:, idx]
                probs.append(aligned)
            else:
                pred = estimator.predict(X)
                aligned = np.zeros((len(X), len(self.classes_)), dtype=float)
                for i, cls in enumerate(self.classes_):
                    aligned[:, i] = (pred == cls).astype(float)
                probs.append(aligned)

        if not probs:
            raise ValueError("SoftVotingModel has no estimators")
        return np.mean(probs, axis=0)

    def predict(self, X: np.ndarray) -> np.ndarray:
        proba = self.predict_proba(X)
        idx = np.argmax(proba, axis=1)
        return self.classes_[idx]


class EnsembleClassifier:
    """General ensemble classifier supporting voting and stacking."""

    MODEL_ALIASES = {
        "rf": "random_forest",
        "random_forest": "random_forest",
        "randomforest": "random_forest",
        "xgb": "xgboost",
        "xgboost": "xgboost",
        "et": "extra_trees",
        "extra_trees": "extra_trees",
        "extratrees": "extra_trees",
        "lgb": "lightgbm",
        "lgbm": "lightgbm",
        "lightgbm": "lightgbm",
        "auto": "auto",
    }
    AUTO_MODELS = ("random_forest", "xgboost", "extra_trees", "lightgbm")

    def __init__(
        self,
        models: Optional[List[str]] = None,
        voting: str = "soft",
        use_stacking: bool = True,
        n_jobs: int = 1,
        random_state: int = 42,
    ):
        self.model_names = models or ["random_forest", "xgboost"]
        self.model_names = self._normalize_model_names(self.model_names)
        if "xgboost" in self.model_names and not HAS_XGB:
            self.model_names = [name for name in self.model_names if name != "xgboost"]
        if "lightgbm" in self.model_names and not HAS_LGB:
            self.model_names = [name for name in self.model_names if name != "lightgbm"]
        if not self.model_names:
            self.model_names = ["random_forest"]

        self.voting = voting
        self.use_stacking = use_stacking
        self.n_jobs = n_jobs
        self.random_state = random_state

        self.base_models: Dict[str, object] = {}
        self.ensemble_model = None
        self.is_fitted = False

    @classmethod
    def _normalize_model_names(cls, model_names: List[str] | str) -> List[str]:
        if isinstance(model_names, str):
            items = [part.strip() for part in model_names.split(",")]
        else:
            items = [str(item).strip() for item in model_names]
        normalized: List[str] = []
        for item in items:
            canonical = cls.MODEL_ALIASES.get(str(item).strip().lower(), str(item).strip().lower())
            if canonical == "auto":
                for auto_name in cls.AUTO_MODELS:
                    if auto_name not in normalized:
                        normalized.append(auto_name)
                continue
            if canonical and canonical not in normalized:
                normalized.append(canonical)
        return normalized or ["random_forest"]

    def _build_model(self, name: str):
        if name == "random_forest":
            return RandomForestClassifier(
                n_estimators=200,
                max_depth=20,
                class_weight="balanced",
                random_state=self.random_state,
                n_jobs=self.n_jobs,
            )
        if name == "extra_trees":
            return ExtraTreesClassifier(
                n_estimators=200,
                max_depth=20,
                class_weight="balanced",
                random_state=self.random_state,
                n_jobs=self.n_jobs,
            )
        if name == "xgboost" and HAS_XGB:
            return xgb.XGBClassifier(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                eval_metric="mlogloss",
                random_state=self.random_state,
                n_jobs=self.n_jobs,
            )
        if name == "lightgbm" and HAS_LGB:
            return lgb.LGBMClassifier(
                n_estimators=200,
                learning_rate=0.05,
                num_leaves=31,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=self.random_state,
                n_jobs=self.n_jobs,
                verbosity=-1,
            )
        raise ValueError(f"Unsupported model: {name}")

    def fit(self, X: np.ndarray, y: np.ndarray):
        self.base_models = {}
        estimators = []
        for name in self.model_names:
            model = self._build_model(name)
            model.fit(X, y)
            self.base_models[name] = model
            estimators.append((name, model))

        if self.use_stacking and len(estimators) > 1:
            meta = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=self.random_state)
            self.ensemble_model = StackingClassifier(
                estimators=estimators,
                final_estimator=meta,
                stack_method="predict_proba",
                n_jobs=self.n_jobs,
            )
            self.ensemble_model.fit(X, y)
        else:
            self.ensemble_model = SoftVotingModel(estimators).fit(X, y)

        self.is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.ensemble_model is None:
            raise ValueError("EnsembleClassifier is not fitted")
        return self.ensemble_model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.ensemble_model is None:
            raise ValueError("EnsembleClassifier is not fitted")
        if hasattr(self.ensemble_model, "predict_proba"):
            return self.ensemble_model.predict_proba(X)
        pred = self.predict(X)
        classes = np.unique(pred)
        proba = np.zeros((len(pred), len(classes)), dtype=float)
        for i, value in enumerate(pred):
            proba[i, int(value)] = 1.0
        return proba

    def save(
        self,
        save_path: str,
        feature_names: Optional[List[str]] = None,
        label_mapping: Optional[Dict] = None,
        metrics: Optional[Dict] = None,
    ):
        payload = {
            "ensemble_model": self.ensemble_model,
            "base_models": self.base_models,
            "model_names": self.model_names,
            "voting": self.voting,
            "use_stacking": self.use_stacking,
            "feature_names": feature_names,
            "label_mapping": label_mapping,
            "metrics": metrics,
            "version": "4.1.0",
        }
        joblib.dump(payload, save_path)

    @classmethod
    def load(cls, load_path: str) -> "EnsembleClassifier":
        payload = joblib.load(load_path)
        instance = cls(
            models=payload.get("model_names"),
            voting=payload.get("voting", "soft"),
            use_stacking=payload.get("use_stacking", True),
        )
        instance.ensemble_model = payload.get("ensemble_model")
        instance.base_models = payload.get("base_models", {})
        instance.is_fitted = instance.ensemble_model is not None
        return instance


class EnsembleModel:
    """Compatibility wrapper used by training scripts/tests."""

    def __init__(self, base_models: Dict[str, object], use_stacking: bool = False):
        if not base_models:
            raise ValueError("base_models cannot be empty")
        self.base_models = dict(base_models)
        self.use_stacking = use_stacking
        self.model = None

    @staticmethod
    def _log(log_fn: LogFn, message: str) -> None:
        if log_fn is not None:
            log_fn(message)

    def fit(self, X: np.ndarray, y: np.ndarray, log_fn: LogFn = None):
        estimators = []
        total_steps = len(self.base_models) + 1
        completed_steps = 0
        started = time.time()

        for name, estimator in self.base_models.items():
            completed_steps += 1
            self._log(
                log_fn,
                f"Ensemble step {completed_steps}/{total_steps}: fitting base '{name}' {_progress_bar(completed_steps / total_steps)}",
            )
            if not _is_estimator_fitted(estimator):
                estimator.fit(X, y)
            estimators.append((name, estimator))

            elapsed = time.time() - started
            progress = completed_steps / total_steps
            eta_seconds = (elapsed / progress - elapsed) if progress > 0 else 0.0
            self._log(
                log_fn,
                f"Ensemble base '{name}' done | overall {progress * 100:5.1f}% ETA {_format_eta(eta_seconds)}",
            )

        if self.use_stacking and len(estimators) > 1:
            completed_steps += 1
            self._log(
                log_fn,
                f"Ensemble step {completed_steps}/{total_steps}: fitting stacking meta-model {_progress_bar(completed_steps / total_steps)}",
            )
            self.model = StackingClassifier(
                estimators=estimators,
                final_estimator=LogisticRegression(max_iter=1000, class_weight="balanced"),
                stack_method="predict_proba",
                n_jobs=1,
            )
            self.model.fit(X, y)
        else:
            completed_steps += 1
            self._log(
                log_fn,
                f"Ensemble step {completed_steps}/{total_steps}: building soft-voting model {_progress_bar(completed_steps / total_steps)}",
            )
            self.model = SoftVotingModel(estimators).fit(X, y)

        self._log(log_fn, "Ensemble fit completed.")
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise ValueError("EnsembleModel is not fitted")
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise ValueError("EnsembleModel is not fitted")
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)
        pred = self.predict(X)
        n_classes = len(np.unique(pred))
        out = np.zeros((len(pred), n_classes), dtype=float)
        for i, p in enumerate(pred):
            out[i, int(p)] = 1.0
        return out
