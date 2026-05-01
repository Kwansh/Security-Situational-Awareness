"""
数据预处理模块 - 融合项目 1 的鲁棒预处理能力

支持自动列清洗、类型编码、缺失值处理、标准化
"""

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
from sklearn.preprocessing import StandardScaler
from typing import Dict, Optional, Set

import pandas as pd

class DummyPreprocessor:
    """
    解耦后的预处理器类。
    职责：清理 CSV 中的标签列，确保输入 Scaler 的特征列对齐。
    """
    def transform_dataframe(self, df, fit=False):
        # 排除掉评估脚本中可能出现的所有标签列名
        exclude = ["Label", "label", "Class", "class", "Target", "target", "y", "Y"]
        cols = [c for c in df.columns if c not in exclude]
        # 返回只包含特征数据的 DataFrame，确保后续 Scaler 不会报错
        return df[cols]
    
class Preprocessor:
    """
    Prepare CIC-DDoS style data while retaining all usable features.
    
    数据预处理器，支持自动列清洗、类型编码、缺失值处理、标准化
    """

    def __init__(self, label_column: str = "Label"):
        """
        初始化预处理器
        
        Args:
            label_column: 标签列名
        """
        self.label_column = label_column
        self.scaler = StandardScaler()
        self.fitted = False
        self.label_mapping: Optional[Dict[str, int]] = None
        self.feature_columns: list = []
        self.categorical_encoders: Dict[str, Dict[str, int]] = {}
        self.numeric_fill_values: Dict[str, float] = {}
        self.datetime_columns: Set[str] = set()

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗数据
        
        Args:
            df: 原始 DataFrame
            
        Returns:
            清洗后的 DataFrame
        """
        cleaned = df.copy()
        
        # 清洗列名（去除空格）
        cleaned.columns = [str(column).strip() for column in cleaned.columns]
        
        # 替换 inf/-inf 为 NaN
        cleaned = cleaned.replace([np.inf, -np.inf], np.nan)
        
        return cleaned

    def _resolve_label_column(self, df: pd.DataFrame) -> str:
        """解析标签列名"""
        if self.label_column in df.columns:
            return self.label_column

        # 尝试模糊匹配
        normalized = {str(column).strip().lower(): column for column in df.columns}
        key = self.label_column.strip().lower()
        if key not in normalized:
            raise KeyError(f"Label column '{self.label_column}' was not found.")
        return normalized[key]

    def _encode_feature_column(
        self, 
        series: pd.Series, 
        column: str, 
        fit: bool = False
    ) -> pd.Series:
        """
        编码单个特征列
        
        Args:
            series: 特征列
            column: 列名
            fit: 是否拟合
            
        Returns:
            编码后的 Series
        """
        original = series.copy()
        normalized_name = column.strip().lower()

        # 检测时间列
        if fit and ("time" in normalized_name or "timestamp" in normalized_name):
            parsed = pd.to_datetime(original, errors="coerce")
            if parsed.notna().any():
                self.datetime_columns.add(column)
        
        # 处理时间列
        if column in self.datetime_columns:
            parsed = pd.to_datetime(original, errors="coerce")
            numeric = pd.Series(
                parsed.astype("int64"), 
                index=series.index, 
                dtype="float64"
            )
            numeric = numeric.where(parsed.notna(), np.nan)
            return numeric

        # 尝试数值转换
        numeric = pd.to_numeric(original, errors="coerce")
        if numeric.notna().sum() == len(original.dropna()):
            return numeric.astype("float64")

        # 类别编码
        values = original.fillna("__missing__").astype(str)
        if fit:
            categories = pd.Index(pd.unique(values))
            self.categorical_encoders[column] = {
                value: idx for idx, value in enumerate(categories)
            }
        
        mapping = self.categorical_encoders.get(column, {})
        return values.map(lambda value: mapping.get(value, -1)).astype("float64")

    def transform_dataframe(
        self, 
        df: pd.DataFrame, 
        fit: bool = False
    ) -> pd.DataFrame:
        """
        转换 DataFrame
        
        Args:
            df: 原始 DataFrame
            fit: 是否拟合
            
        Returns:
            转换后的 DataFrame
        """
        working = self.clean(df)
        
        # 处理标签列
        label_column = None
        try:
            label_column = self._resolve_label_column(working)
        except KeyError:
            label_column = None

        if label_column and label_column in working.columns:
            working = working.drop(columns=[label_column])

        # 删除未命名列
        unnamed_columns = [
            col for col in working.columns 
            if str(col).strip().startswith("Unnamed:")
        ]
        if unnamed_columns:
            working = working.drop(columns=unnamed_columns)

        # 确定特征列
        if fit:
            self.feature_columns = [str(column).strip() for column in working.columns]

        # 转换每列
        transformed = pd.DataFrame(index=working.index)
        for column in self.feature_columns:
            if column in working.columns:
                transformed[column] = self._encode_feature_column(
                    working[column], 
                    column, 
                    fit=fit
                )
            else:
                transformed[column] = np.nan

        # 填充缺失值
        if fit:
            self.numeric_fill_values = {}
            for column in transformed.columns:
                median = float(transformed[column].median()) if transformed[column].notna().any() else 0.0
                if np.isnan(median):
                    median = 0.0
                self.numeric_fill_values[column] = median
        
        for column in transformed.columns:
            fill_value = self.numeric_fill_values.get(column, 0.0)
            transformed[column] = transformed[column].fillna(fill_value)

        return transformed.astype("float64")

    def split(self, df: pd.DataFrame):
        """
        分割特征和标签
        
        Args:
            df: 原始 DataFrame
            
        Returns:
            (X, y) 特征和标签
        """
        label_column = self._resolve_label_column(df)
        y = df[label_column]
        
        X = self.transform_dataframe(df, fit=True)

        # 编码标签
        if not is_numeric_dtype(y):
            labels = sorted(y.dropna().astype(str).unique())
            self.label_mapping = {label: idx for idx, label in enumerate(labels)}
            y = y.astype(str).map(self.label_mapping)
        else:
            self.label_mapping = None
        
        return X, y.astype(int)

    def normalize(self, X: np.ndarray, fit: bool = True):
        """
        标准化
        
        Args:
            X: 特征数组
            fit: 是否拟合
            
        Returns:
            标准化后的数组
        """
        if fit:
            self.fitted = True
            return self.scaler.fit_transform(X)
        
        if not self.fitted:
            raise ValueError("Scaler is not fitted yet.")
        
        return self.scaler.transform(X)

    def get_feature_columns(self) -> list:
        """获取特征列名"""
        return self.feature_columns

    def get_label_mapping(self) -> Optional[Dict[str, int]]:
        """获取标签映射"""
        return self.label_mapping
