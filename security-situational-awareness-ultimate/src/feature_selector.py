import numpy as np
from sklearn.feature_selection import SelectKBest, f_classif


class FeatureSelector:
    """Feature selection based on ANOVA F score."""

    def __init__(self, k: int = 30):
        self.k = k
        self.selector: SelectKBest | None = None
        self.selected_features: np.ndarray | None = None

    def fit_transform(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        effective_k = "all" if self.k <= 0 or self.k >= X.shape[1] else self.k
        self.selector = SelectKBest(score_func=f_classif, k=effective_k)
        transformed = self.selector.fit_transform(X, y)
        self.selected_features = self.selector.get_support(indices=True)
        return transformed

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.selector is None:
            raise ValueError("Selector is not fitted yet.")
        return self.selector.transform(X)
