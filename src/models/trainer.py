"""Model training module with visible progress for large datasets."""

from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_class_weight

try:
    import xgboost as xgb

    XGBOOST_AVAILABLE = True
except ImportError:  # pragma: no cover
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb

    LIGHTGBM_AVAILABLE = True
except ImportError:  # pragma: no cover
    LIGHTGBM_AVAILABLE = False


LogFn = Optional[Callable[[str], None]]


class EncodedLabelClassifier(BaseEstimator, ClassifierMixin):
    """Estimator wrapper that remaps labels to contiguous ints for training."""

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


class ModelTrainer:
    """Train multiple base models with visible progress logs."""

    MODEL_ALIASES = {
        "rf": "random_forest",
        "random_forest": "random_forest",
        "randomforest": "random_forest",
        "random forest": "random_forest",
        "xgb": "xgboost",
        "xgboost": "xgboost",
        "xg boost": "xgboost",
        "et": "extra_trees",
        "extra_trees": "extra_trees",
        "extratrees": "extra_trees",
        "extra trees": "extra_trees",
        "lgb": "lightgbm",
        "lgbm": "lightgbm",
        "lightgbm": "lightgbm",
        "light gbm": "lightgbm",
        "auto": "auto",
    }
    DEFAULT_MODELS = ("random_forest", "xgboost")
    AUTO_MODELS = ("random_forest", "xgboost", "extra_trees", "lightgbm")

    def __init__(
        self,
        random_state: int = 42,
        rf_estimators: int = 200,
        xgb_estimators: int = 200,
        rf_progress_step: int = 25,
        n_jobs: int = 1,
        model_names: Optional[Sequence[str] | str] = None,
    ):
        self.random_state = random_state
        self.rf_estimators = int(max(10, rf_estimators))
        self.xgb_estimators = int(max(10, xgb_estimators))
        self.lightgbm_estimators = int(max(10, xgb_estimators))
        self.rf_progress_step = int(max(5, rf_progress_step))
        self.n_jobs = int(n_jobs)
        self.model_names = self._normalize_model_names(model_names)

        self.rf: Optional[RandomForestClassifier] = None
        self.xgb = None
        self.extra_trees: Optional[ExtraTreesClassifier] = None
        self.lightgbm = None
        self.base_models: Dict[str, object] = {}

    @classmethod
    def _normalize_model_names(
        cls, model_names: Optional[Sequence[str] | str]
    ) -> List[str]:
        if model_names is None:
            requested: List[str] = list(cls.DEFAULT_MODELS)
        elif isinstance(model_names, str):
            requested = [part.strip() for part in model_names.split(",")]
        else:
            requested = [str(item).strip() for item in model_names]

        normalized: List[str] = []
        for item in requested:
            if not item:
                continue
            canonical = cls.MODEL_ALIASES.get(item.lower(), item.lower())
            if canonical == "auto":
                for auto_name in cls.AUTO_MODELS:
                    if auto_name not in normalized:
                        normalized.append(auto_name)
                continue
            if canonical not in normalized:
                normalized.append(canonical)

        return normalized or list(cls.DEFAULT_MODELS)

    @staticmethod
    def _log(log_fn: LogFn, message: str) -> None:
        if log_fn is not None:
            log_fn(message)

    @staticmethod
    def _format_eta(seconds: float) -> str:
        total = max(0, int(seconds))
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @staticmethod
    def _progress_bar(progress: float, width: int = 24) -> str:
        progress = min(max(progress, 0.0), 1.0)
        filled = int(round(progress * width))
        return "[" + "#" * filled + "-" * (width - filled) + "]"

    def _build_class_weight(self, y_train) -> Optional[Dict[int, float]]:
        classes = np.unique(y_train)
        if len(classes) > 1:
            weights = compute_class_weight(class_weight="balanced", classes=classes, y=y_train)
            return {int(c): float(w) for c, w in zip(classes, weights)}
        return None

    def _train_incremental_tree_model(
        self,
        estimator,
        total_estimators: int,
        X_train,
        y_train,
        log_fn: LogFn,
        label: str,
    ):
        start = time.time()
        current = min(self.rf_progress_step, total_estimators)
        estimator.set_params(n_estimators=current, warm_start=True)
        estimator.fit(X_train, y_train)
        progress = current / total_estimators
        elapsed = time.time() - start
        eta_seconds = (elapsed / progress - elapsed) if progress > 0 else 0.0
        self._log(
            log_fn,
            (
                f"{label} progress: {self._progress_bar(progress)} {progress * 100:5.1f}% "
                f"({current}/{total_estimators} trees) ETA {self._format_eta(eta_seconds)}"
            ),
        )

        while current < total_estimators:
            current = min(current + self.rf_progress_step, total_estimators)
            estimator.set_params(n_estimators=current)
            estimator.fit(X_train, y_train)
            progress = current / total_estimators
            elapsed = time.time() - start
            eta_seconds = (elapsed / progress - elapsed) if progress > 0 else 0.0
            self._log(
                log_fn,
                (
                    f"{label} progress: {self._progress_bar(progress)} {progress * 100:5.1f}% "
                    f"({current}/{total_estimators} trees) ETA {self._format_eta(eta_seconds)}"
                ),
            )

        estimator.set_params(warm_start=False)
        self._log(log_fn, f"{label} training done in {time.time() - start:.1f}s")
        return estimator

    def _train_rf_with_progress(self, X_train, y_train, log_fn: LogFn = None) -> RandomForestClassifier:
        class_weight = self._build_class_weight(y_train)

        rf = RandomForestClassifier(
            n_estimators=min(self.rf_progress_step, self.rf_estimators),
            max_depth=20,
            class_weight=class_weight,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
        )
        try:
            return self._train_incremental_tree_model(rf, self.rf_estimators, X_train, y_train, log_fn, "RF")
        except PermissionError:
            self._log(log_fn, "RF parallel training hit PermissionError, retrying with n_jobs=1.")
            rf = RandomForestClassifier(
                n_estimators=min(self.rf_progress_step, self.rf_estimators),
                max_depth=20,
                class_weight=class_weight,
                random_state=self.random_state,
                n_jobs=1,
            )
            return self._train_incremental_tree_model(rf, self.rf_estimators, X_train, y_train, log_fn, "RF")

    def _train_extra_trees_with_progress(self, X_train, y_train, log_fn: LogFn = None) -> ExtraTreesClassifier:
        class_weight = self._build_class_weight(y_train)

        extra_trees = ExtraTreesClassifier(
            n_estimators=min(self.rf_progress_step, self.rf_estimators),
            max_depth=20,
            class_weight=class_weight,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
        )
        try:
            return self._train_incremental_tree_model(
                extra_trees,
                self.rf_estimators,
                X_train,
                y_train,
                log_fn,
                "ET",
            )
        except PermissionError:
            self._log(log_fn, "ET parallel training hit PermissionError, retrying with n_jobs=1.")
            extra_trees = ExtraTreesClassifier(
                n_estimators=min(self.rf_progress_step, self.rf_estimators),
                max_depth=20,
                class_weight=class_weight,
                random_state=self.random_state,
                n_jobs=1,
            )
            return self._train_incremental_tree_model(
                extra_trees,
                self.rf_estimators,
                X_train,
                y_train,
                log_fn,
                "ET",
            )

    def _train_xgb_with_progress(self, X_train, y_train, log_fn: LogFn = None):
        if not XGBOOST_AVAILABLE:
            self._log(log_fn, "XGBoost is not installed, skipping XGB model.")
            return None
        raw_classes = np.unique(y_train)
        if len(raw_classes) < 2:
            self._log(log_fn, "Only one class detected in training data, skipping XGB model.")
            return None

        start = time.time()
        self._log(log_fn, "XGB progress: starting...")
        self._log(log_fn, f"XGB detected {len(raw_classes)} class(es): {raw_classes.tolist()[:10]}")

        n_classes = int(len(raw_classes))

        trainer = self
        total_rounds = self.xgb_estimators

        class XGBProgressCallback(xgb.callback.TrainingCallback):
            def __init__(self, total_rounds: int, log_every: int = 10):
                self.total_rounds = max(1, int(total_rounds))
                self.log_every = max(1, int(log_every))
                self.start_time = time.time()

            def after_iteration(self, model, epoch: int, evals_log) -> bool:
                done = epoch + 1
                if done == 1 or done == self.total_rounds or done % self.log_every == 0:
                    progress = done / self.total_rounds
                    elapsed = time.time() - self.start_time
                    eta_seconds = (elapsed / progress - elapsed) if progress > 0 else 0.0
                    trainer._log(
                        log_fn,
                        (
                            f"XGB progress: {trainer._progress_bar(progress)} {progress * 100:5.1f}% "
                            f"({done}/{self.total_rounds} rounds) ETA {trainer._format_eta(eta_seconds)}"
                        ),
                    )
                return False

        callbacks = [XGBProgressCallback(total_rounds=total_rounds, log_every=10)]
        xgb_params = {
            "n_estimators": self.xgb_estimators,
            "max_depth": 8,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": self.random_state,
            "n_jobs": self.n_jobs,
            "tree_method": "hist",
            "verbosity": 0,
        }
        if n_classes <= 2:
            xgb_params["objective"] = "binary:logistic"
            xgb_params["eval_metric"] = "logloss"
        else:
            xgb_params["objective"] = "multi:softprob"
            xgb_params["num_class"] = int(n_classes)
            xgb_params["eval_metric"] = "mlogloss"

        base_model = xgb.XGBClassifier(
            **xgb_params,
        )
        model = EncodedLabelClassifier(base_model)

        try:
            model.fit(
                X_train,
                y_train,
                eval_set=[(X_train, y_train)],
                verbose=False,
                callbacks=callbacks,
            )
        except TypeError:
            self._log(
                log_fn,
                "XGB callback API is not supported by current xgboost version, falling back to built-in verbose logs.",
            )
            verbose_step = max(1, self.xgb_estimators // 10)
            model.fit(
                X_train,
                y_train,
                eval_set=[(X_train, y_train)],
                verbose=verbose_step,
            )
            self._log(
                log_fn,
                f"XGB progress: {self._progress_bar(1.0)} 100.0% ({self.xgb_estimators}/{self.xgb_estimators} rounds) ETA 00:00:00",
            )
        self._log(log_fn, f"XGB training done in {time.time() - start:.1f}s")
        return model

    def _train_lightgbm_with_progress(self, X_train, y_train, log_fn: LogFn = None):
        if not LIGHTGBM_AVAILABLE:
            self._log(log_fn, "LightGBM is not installed, skipping LGBM model.")
            return None
        if len(np.unique(y_train)) < 2:
            self._log(log_fn, "Only one class detected in training data, skipping LGBM model.")
            return None

        start = time.time()
        self._log(log_fn, "LGB progress: starting...")
        total_rounds = self.lightgbm_estimators

        class LGBProgressCallback:
            order = 10
            before_iteration = False

            def __init__(self, total_rounds: int, log_every: int = 10):
                self.total_rounds = max(1, int(total_rounds))
                self.log_every = max(1, int(log_every))
                self.start_time = time.time()

            def __call__(self, env):
                done = int(env.iteration) + 1
                if done == 1 or done == self.total_rounds or done % self.log_every == 0:
                    progress = done / self.total_rounds
                    elapsed = time.time() - self.start_time
                    eta_seconds = (elapsed / progress - elapsed) if progress > 0 else 0.0
                    ModelTrainer._log(
                        log_fn,
                        (
                            f"LGB progress: {ModelTrainer._progress_bar(progress)} {progress * 100:5.1f}% "
                            f"({done}/{self.total_rounds} rounds) ETA {ModelTrainer._format_eta(eta_seconds)}"
                        ),
                    )

        callbacks = [LGBProgressCallback(total_rounds=total_rounds, log_every=10)]
        classes = np.unique(y_train)
        lgb_params = {
            "n_estimators": self.lightgbm_estimators,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": self.random_state,
            "n_jobs": self.n_jobs,
            "verbosity": -1,
        }
        if len(classes) > 2:
            lgb_params["objective"] = "multiclass"
            lgb_params["num_class"] = len(classes)
        model = lgb.LGBMClassifier(**lgb_params)

        try:
            model.fit(X_train, y_train, callbacks=callbacks)
        except TypeError:
            self._log(
                log_fn,
                "LightGBM callback API is not supported by current lightgbm version, falling back to plain fit.",
            )
            model.fit(X_train, y_train)
            self._log(
                log_fn,
                f"LGB progress: {self._progress_bar(1.0)} 100.0% ({self.lightgbm_estimators}/{self.lightgbm_estimators} rounds) ETA 00:00:00",
            )
        self._log(log_fn, f"LGB training done in {time.time() - start:.1f}s")
        return model

    def train_models(self, X_train, y_train, log_fn: LogFn = None):
        self.base_models = {}
        for model_name in self.model_names:
            try:
                if model_name == "random_forest":
                    self._log(log_fn, "Training RandomForest base model...")
                    self.rf = self._train_rf_with_progress(X_train, y_train, log_fn=log_fn)
                    self.base_models["random_forest"] = self.rf
                elif model_name == "extra_trees":
                    self._log(log_fn, "Training ExtraTrees base model...")
                    self.extra_trees = self._train_extra_trees_with_progress(X_train, y_train, log_fn=log_fn)
                    self.base_models["extra_trees"] = self.extra_trees
                elif model_name == "xgboost":
                    self._log(log_fn, "Training XGBoost base model...")
                    self.xgb = self._train_xgb_with_progress(X_train, y_train, log_fn=log_fn)
                    if self.xgb is not None:
                        self.base_models["xgboost"] = self.xgb
                elif model_name == "lightgbm":
                    self._log(log_fn, "Training LightGBM base model...")
                    self.lightgbm = self._train_lightgbm_with_progress(X_train, y_train, log_fn=log_fn)
                    if self.lightgbm is not None:
                        self.base_models["lightgbm"] = self.lightgbm
                else:
                    self._log(log_fn, f"Unsupported model name '{model_name}', skipping.")
            except Exception as exc:
                self._log(log_fn, f"{model_name} training failed, skipping this model: {exc}")

        if not self.base_models:
            raise RuntimeError("No base models were trained successfully.")
        return self
