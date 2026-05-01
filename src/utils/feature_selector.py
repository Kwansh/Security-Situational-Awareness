"""
特征选择模块

基于统计方法的特征选择，支持 SelectKBest
"""

import numpy as np
from sklearn.feature_selection import SelectKBest, f_classif
from typing import Optional


class FeatureSelector:
    """
    特征选择器
    
    基于 ANOVA F 检验的特征选择方法
    """
    
    def __init__(self, k: int = 0):
        """
        初始化特征选择器
        
        Args:
            k: 选择的特征数量，<=0 表示选择全部特征
        """
        self.k = k
        self.selector: Optional[SelectKBest] = None
        self.selected_features: Optional[np.ndarray] = None
        self.use_identity = k <= 0

    def fit_transform(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """
        拟合并转换数据
        
        Args:
            X: 特征数组 (n_samples, n_features)
            y: 标签数组 (n_samples,)
            
        Returns:
            转换后的特征数组
        """
        if self.use_identity or self.k >= X.shape[1]:
            self.selected_features = np.arange(X.shape[1])
            self.selector = None
            return X
        self.selector = SelectKBest(score_func=f_classif, k=self.k)
        transformed = self.selector.fit_transform(X, y)
        self.selected_features = self.selector.get_support(indices=True)
        return transformed

    def transform(self, X: np.ndarray) -> np.ndarray:
        """
        转换数据
        
        Args:
            X: 特征数组 (n_samples, n_features)
            
        Returns:
            转换后的特征数组
        """
        if self.use_identity:
            return X
        if self.selector is None:
            raise ValueError("Selector is not fitted yet.")
        return self.selector.transform(X)
