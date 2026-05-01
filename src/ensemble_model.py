import joblib
from sklearn.ensemble import StackingClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression


class EnsembleModel:
    """Wrap sklearn voting and stacking ensembles."""

    def __init__(self, base_models, voting: str = "soft", use_stacking: bool = False):
        self.base_models = base_models
        self.voting = voting
        self.use_stacking = use_stacking
        self.model = None

    def fit(self, X, y):
        estimators = [(name, model) for name, model in self.base_models.items() if model is not None]
        if not estimators:
            raise ValueError("At least one fitted base model is required.")

        if self.use_stacking:
            self.model = StackingClassifier(
                estimators=estimators,
                final_estimator=LogisticRegression(class_weight="balanced", max_iter=1000),
                stack_method="predict_proba",
                n_jobs=1,
            )
        else:
            self.model = VotingClassifier(
                estimators=estimators,
                voting=self.voting,
                n_jobs=1,
            )
        self.model.fit(X, y)
        return self

    def predict(self, X):
        if self.model is None:
            raise ValueError("Ensemble model is not fitted yet.")
        return self.model.predict(X)

    def predict_proba(self, X):
        if self.model is None:
            raise ValueError("Ensemble model is not fitted yet.")
        return self.model.predict_proba(X)

    def save(self, path):
        joblib.dump(self, path)

    @classmethod
    def load(cls, path):
        return joblib.load(path)
