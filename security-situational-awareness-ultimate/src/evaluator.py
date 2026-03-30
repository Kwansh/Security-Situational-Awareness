from sklearn.metrics import accuracy_score, classification_report, f1_score, precision_score, recall_score


class Evaluator:
    @staticmethod
    def evaluate(model, X_test, y_test):
        y_pred = model.predict(X_test)
        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, average="weighted", zero_division=0),
            "recall": recall_score(y_test, y_pred, average="weighted", zero_division=0),
            "f1": f1_score(y_test, y_pred, average="weighted", zero_division=0),
            "report": classification_report(y_test, y_pred, zero_division=0),
        }
        return metrics
