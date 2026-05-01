from sklearn.ensemble import RandomForestClassifier

try:
    import xgboost as xgb
except ImportError:  # pragma: no cover
    xgb = None


class ModelTrainer:
    """Train base models used by the ensemble."""

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.rf = None
        self.xgb = None

    def train_models(self, X_train, y_train):
        self.rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=20,
            class_weight="balanced",
            random_state=self.random_state,
            n_jobs=1,
        )
        self.rf.fit(X_train, y_train)

        if xgb is not None:
            self.xgb = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=self.random_state,
                eval_metric="mlogloss",
                n_jobs=1,
            )
            self.xgb.fit(X_train, y_train)

        return self
