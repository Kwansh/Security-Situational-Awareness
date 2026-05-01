<<<<<<< HEAD
﻿"""Ensemble model module."""

from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional

import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, StackingClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.utils.validation import check_is_fitted

try:
    import xgboost as xgb

    HAS_XGB = True
except Exception:  # pragma: no cover
    HAS_XGB = False

try:
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
    """Soft voting without re-fitting already fitted base estimators."""

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
                if hasattr(estimator, "classes_"):
                    est_classes = np.asarray(estimator.classes_)
                    aligned = np.zeros((len(X), len(self.classes_)), dtype=float)
                    for idx, cls in enumerate(est_classes):
                        target_idx = np.where(self.classes_ == cls)[0]
                        if len(target_idx) > 0:
                            aligned[:, target_idx[0]] = prob[:, idx]
                    probs.append(aligned)
                else:
                    probs.append(prob)
            else:
                pred = estimator.predict(X)
                aligned = np.zeros((len(X), len(self.classes_)), dtype=float)
                for i, cls in enumerate(self.classes_):
                    aligned[:, i] = (pred == cls).astype(float)
                probs.append(aligned)

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
        if not self.is_fitted:
            raise ValueError("Model is not fitted yet.")
        return self.ensemble_model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Model is not fitted yet.")
        if hasattr(self.ensemble_model, "predict_proba"):
            return self.ensemble_model.predict_proba(X)
        predictions = self.predict(X)
        classes = np.unique(predictions)
        proba = np.zeros((len(predictions), len(classes)), dtype=float)
        class_to_idx = {c: i for i, c in enumerate(classes)}
        for row, pred in enumerate(predictions):
            proba[row, class_to_idx[pred]] = 1.0
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
        steps_start = time.time()

        for name, estimator in self.base_models.items():
            completed_steps += 1
            step_start = time.time()
            self._log(
                log_fn,
                (
                    f"Ensemble step {completed_steps}/{total_steps}: fitting base '{name}' "
                    f"{_progress_bar(completed_steps / total_steps)}"
                ),
            )
            if not _is_estimator_fitted(estimator):
                estimator.fit(X, y)
            estimators.append((name, estimator))
            step_elapsed = time.time() - step_start
            overall_progress = completed_steps / total_steps
            elapsed = time.time() - steps_start
            eta_seconds = (elapsed / overall_progress - elapsed) if overall_progress > 0 else 0.0
            self._log(
                log_fn,
                (
                    f"Ensemble base '{name}' done in {step_elapsed:.1f}s | "
                    f"overall {overall_progress * 100:5.1f}% ETA {_format_eta(eta_seconds)}"
                ),
            )

        if self.use_stacking and len(estimators) > 1:
            completed_steps += 1
            self._log(
                log_fn,
                (
                    f"Ensemble step {completed_steps}/{total_steps}: fitting stacking meta-model "
                    f"{_progress_bar(completed_steps / total_steps)}"
                ),
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
                (
                    f"Ensemble step {completed_steps}/{total_steps}: building soft-voting model "
                    f"{_progress_bar(completed_steps / total_steps)}"
                ),
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
=======
"""
集成学习模型模块
支持 Voting、Stacking 等多种集成策略
增强版：支持 RF + XGB + LightGBM + ExtraTrees 的 Stacking 集成
"""

from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import numpy as np
import joblib
from sklearn.ensemble import (
    RandomForestClassifier, 
    GradientBoostingClassifier,
    VotingClassifier,
    StackingClassifier,
    ExtraTreesClassifier
)
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
import warnings
warnings.filterwarnings('ignore')

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    warnings.warn("XGBoost 未安装，将使用备用模型")

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False
    warnings.warn("LightGBM 未安装，将跳过该模型")

from src.utils.logger import get_logger

logger = get_logger(__name__)


class EnsembleClassifier:
    """集成分类器 - 多模型融合提升性能（支持 RF + XGB + LGB + ET）"""
    
    def __init__(
        self,
        models: List[str] = None,
        voting: str = 'soft',
        use_stacking: bool = True,
        n_jobs: int = -1,
        # 可单独调整各模型参数
        rf_params: Dict = None,
        xgb_params: Dict = None,
        lgb_params: Dict = None,
        et_params: Dict = None,
        meta_params: Dict = None
    ):
        """
        初始化集成分类器
        
        Args:
            models: 模型列表，默认 ['random_forest', 'xgboost', 'lightgbm', 'extra_trees']
            voting: 投票策略（仅在 use_stacking=False 时生效）'soft' 或 'hard'
            use_stacking: 是否使用 Stacking 集成（推荐 True）
            n_jobs: 并行作业数
            rf_params: 随机森林参数字典
            xgb_params: XGBoost 参数字典
            lgb_params: LightGBM 参数字典
            et_params: ExtraTrees 参数字典
            meta_params: 元学习器参数字典
        """
        if models is None:
            self.model_names = ['random_forest', 'xgboost', 'lightgbm', 'extra_trees']
        else:
            self.model_names = models
        
        # 过滤掉不可用的模型
        if 'xgboost' in self.model_names and not HAS_XGB:
            logger.warning("XGBoost 不可用，从模型列表中移除")
            self.model_names.remove('xgboost')
        if 'lightgbm' in self.model_names and not HAS_LGB:
            logger.warning("LightGBM 不可用，从模型列表中移除")
            self.model_names.remove('lightgbm')
        
        self.voting = voting
        self.use_stacking = use_stacking
        self.n_jobs = n_jobs
        
        # 保存模型参数
        self.rf_params = rf_params or {}
        self.xgb_params = xgb_params or {}
        self.lgb_params = lgb_params or {}
        self.et_params = et_params or {}
        self.meta_params = meta_params or {}
        
        self.base_models = {}
        self.ensemble_model = None
        self.meta_model = None
        self.is_fitted = False
        
        logger.info("集成分类器初始化完成", extra={
            "models": self.model_names,
            "voting": self.voting,
            "use_stacking": self.use_stacking,
            "n_models": len(self.model_names)
        })
    
    def _create_base_model(self, name: str):
        """创建基础模型，参数采用 CIC-DDoS2019 优化配置"""
        
        if name == 'random_forest':
            # 推荐参数：n_estimators=300, max_depth=20
            params = {
                'n_estimators': 300,
                'max_depth': 20,
                'min_samples_split': 2,
                'min_samples_leaf': 1,
                'class_weight': 'balanced',
                'random_state': 42,
                'n_jobs': self.n_jobs
            }
            params.update(self.rf_params)
            return RandomForestClassifier(**params)
        
        elif name == 'xgboost':
            if not HAS_XGB:
                raise RuntimeError("XGBoost 未安装")
            params = {
                'n_estimators': 300,
                'max_depth': 10,
                'learning_rate': 0.05,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42,
                'use_label_encoder': False,
                'eval_metric': 'mlogloss',
                'n_jobs': self.n_jobs
            }
            params.update(self.xgb_params)
            return xgb.XGBClassifier(**params)
        
        elif name == 'lightgbm':
            if not HAS_LGB:
                raise RuntimeError("LightGBM 未安装")
            params = {
                'n_estimators': 300,
                'learning_rate': 0.05,
                'max_depth': 10,
                'num_leaves': 31,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'class_weight': 'balanced',
                'random_state': 42,
                'n_jobs': self.n_jobs,
                'verbose': -1
            }
            params.update(self.lgb_params)
            return lgb.LGBMClassifier(**params)
        
        elif name == 'extra_trees':
            params = {
                'n_estimators': 300,
                'max_depth': 20,
                'min_samples_split': 2,
                'min_samples_leaf': 1,
                'class_weight': 'balanced',
                'random_state': 42,
                'n_jobs': self.n_jobs,
                'bootstrap': False  # ExtraTrees 默认不 bootstrap
            }
            params.update(self.et_params)
            return ExtraTreesClassifier(**params)
        
        elif name == 'gradient_boosting':
            # 保留作为备选
            return GradientBoostingClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )
        
        elif name == 'knn':
            return KNeighborsClassifier(
                n_neighbors=5,
                weights='distance',
                n_jobs=self.n_jobs
            )
        
        else:
            raise ValueError(f"不支持的模型：{name}")
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> 'EnsembleClassifier':
        """
        训练集成模型
        
        Args:
            X: 特征矩阵 (n_samples, n_features)
            y: 标签向量 (n_samples,)
        
        Returns:
            self
        """
        logger.info("开始训练集成模型", extra={
            "data_shape": X.shape,
            "n_models": len(self.model_names),
            "use_stacking": self.use_stacking
        })
        
        # 训练基础模型
        for name in self.model_names:
            logger.info(f"训练基础模型：{name}")
            model = self._create_base_model(name)
            model.fit(X, y)
            self.base_models[name] = model
        
        # 创建集成模型
        if self.use_stacking:
            # Stacking 集成：使用所有基模型，元学习器为逻辑回归
            estimators = [(name, self.base_models[name]) for name in self.model_names]
            meta_params_default = {
                'class_weight': 'balanced',
                'max_iter': 1000,
                'n_jobs': self.n_jobs,
                'random_state': 42
            }
            meta_params_default.update(self.meta_params)
            self.meta_model = LogisticRegression(**meta_params_default)
            
            self.ensemble_model = StackingClassifier(
                estimators=estimators,
                final_estimator=self.meta_model,
                stack_method='predict_proba',  # 使用概率作为输入特征
                n_jobs=self.n_jobs,
                passthrough=False  # 不传递原始特征
            )
        else:
            # Voting 集成（软投票或硬投票）
            estimators = [(name, self.base_models[name]) for name in self.model_names]
            self.ensemble_model = VotingClassifier(
                estimators=estimators,
                voting=self.voting,
                n_jobs=self.n_jobs
            )
        
        # 训练集成模型
        logger.info("训练集成模型（Stacking）")
        self.ensemble_model.fit(X, y)
        self.is_fitted = True
        
        logger.info("集成模型训练完成")
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测"""
        if not self.is_fitted:
            raise ValueError("模型未训练，请先调用 fit()")
        return self.ensemble_model.predict(X)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """预测概率"""
        if not self.is_fitted:
            raise ValueError("模型未训练，请先调用 fit()")
        
        if hasattr(self.ensemble_model, 'predict_proba'):
            return self.ensemble_model.predict_proba(X)
        else:
            # 对于不支持 predict_proba 的模型，使用预测结果
            pred = self.predict(X)
            n_classes = len(np.unique(pred))
            proba = np.zeros((len(X), n_classes))
            for i, p in enumerate(pred):
                proba[i, p] = 1.0
            return proba
    
    def evaluate(
        self, 
        X: np.ndarray, 
        y: np.ndarray
    ) -> Dict[str, float]:
        """
        评估模型性能
        
        Args:
            X: 特征矩阵
            y: 真实标签
        
        Returns:
            评估指标字典
        """
        y_pred = self.predict(X)
        
        metrics = {
            'accuracy': float(accuracy_score(y, y_pred)),
            'precision': float(precision_score(y, y_pred, average='weighted', zero_division=0)),
            'recall': float(recall_score(y, y_pred, average='weighted', zero_division=0)),
            'f1_weighted': float(f1_score(y, y_pred, average='weighted', zero_division=0))
        }
        
        logger.info("模型评估完成", extra=metrics)
        return metrics
    
    def get_feature_importance(self, feature_names: List[str] = None) -> Dict[str, float]:
        """
        获取特征重要性（平均所有树模型）
        
        Returns:
            特征重要性的字典
        """
        importance_dict = {}
        n_tree_models = 0
        
        for name, model in self.base_models.items():
            # 支持所有具有 feature_importances_ 的树模型
            if hasattr(model, 'feature_importances_'):
                imp_array = model.feature_importances_
                if feature_names:
                    for fname, imp in zip(feature_names, imp_array):
                        importance_dict[fname] = importance_dict.get(fname, 0) + imp
                else:
                    for i, imp in enumerate(imp_array):
                        key = f"feature_{i}"
                        importance_dict[key] = importance_dict.get(key, 0) + imp
                n_tree_models += 1
        
        # 平均
        if n_tree_models > 0:
            for key in importance_dict:
                importance_dict[key] /= n_tree_models
        
        # 排序
        sorted_importance = dict(
            sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
        )
        
        return sorted_importance
    
    def save(self, save_path: str, feature_names: List[str] = None, 
             label_mapping: Dict = None, metrics: Dict = None):
        """
        保存模型
        
        Args:
            save_path: 保存路径
            feature_names: 特征名称
            label_mapping: 标签映射
            metrics: 评估指标
        """
        model_data = {
            'ensemble_model': self.ensemble_model,
            'base_models': self.base_models,
            'meta_model': self.meta_model,
            'model_names': self.model_names,
            'voting': self.voting,
            'use_stacking': self.use_stacking,
            'feature_names': feature_names,
            'label_mapping': label_mapping,
            'metrics': metrics,
            'version': '4.0.0'  # 升级版本号
        }
        
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model_data, save_path)
        
        logger.info(f"模型已保存：{save_path}")
    
    @classmethod
    def load(cls, load_path: str) -> 'EnsembleClassifier':
        """
        加载模型
        
        Args:
            load_path: 模型文件路径
        
        Returns:
            加载的集成分类器实例
        """
        logger.info(f"加载模型：{load_path}")
        model_data = joblib.load(load_path)
        
        instance = cls(
            models=model_data['model_names'],
            voting=model_data['voting'],
            use_stacking=model_data['use_stacking']
        )
        instance.ensemble_model = model_data['ensemble_model']
        instance.base_models = model_data['base_models']
        instance.meta_model = model_data['meta_model']
        instance.is_fitted = True
        
        logger.info("模型加载成功", extra={"version": model_data.get('version', 'unknown')})
        return instance
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
