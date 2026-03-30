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