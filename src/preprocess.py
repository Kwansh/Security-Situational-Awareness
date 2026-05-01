import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
from sklearn.preprocessing import StandardScaler


class Preprocessor:
    """Clean raw CIC-DDoS style data and prepare numeric model inputs."""

    DEFAULT_DROP_COLUMNS = {
        "Flow ID",
        "Source IP",
        "Source Port",
        "Destination IP",
        "Destination Port",
        "Protocol",
        "Timestamp",
        "SimillarHTTP",
        "Inbound",
    }

    def __init__(self, label_column: str = "Label"):
        self.label_column = label_column
        self.scaler = StandardScaler()
        self.fitted = False
        self.label_mapping = None
        self.feature_columns: list[str] = []

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = df.copy()
        cleaned.columns = [str(column).strip() for column in cleaned.columns]
        cleaned = cleaned.replace([np.inf, -np.inf], np.nan)
        return cleaned

    def _resolve_label_column(self, df: pd.DataFrame) -> str:
        if self.label_column in df.columns:
            return self.label_column

        normalized = {str(column).strip().lower(): column for column in df.columns}
        key = self.label_column.strip().lower()
        if key not in normalized:
            raise KeyError(f"Label column '{self.label_column}' was not found.")
        return normalized[key]

    def split(self, df: pd.DataFrame):
        label_column = self._resolve_label_column(df)
        working = df.copy()
        y = working[label_column]
        X = working.drop(columns=[label_column])

        drop_columns = []
        for column in X.columns:
            normalized = str(column).strip()
            if normalized.startswith("Unnamed:"):
                drop_columns.append(column)
            elif normalized in self.DEFAULT_DROP_COLUMNS:
                drop_columns.append(column)
        if drop_columns:
            X = X.drop(columns=drop_columns)

        for column in X.columns:
            X[column] = pd.to_numeric(X[column], errors="coerce")

        X = X.dropna(axis=1, how="all")
        X = X.fillna(X.median(numeric_only=True)).fillna(0.0)
        self.feature_columns = list(X.columns)

        if not is_numeric_dtype(y):
            labels = sorted(y.dropna().astype(str).unique())
            self.label_mapping = {label: idx for idx, label in enumerate(labels)}
            y = y.astype(str).map(self.label_mapping)
        else:
            self.label_mapping = None
        return X, y.astype(int)

    def normalize(self, X: np.ndarray, fit: bool = True):
        if fit:
            self.fitted = True
            return self.scaler.fit_transform(X)
        if not self.fitted:
            raise ValueError("Scaler is not fitted yet.")
        return self.scaler.transform(X)
