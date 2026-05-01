"""Evaluation utilities with optional visualization output."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


class Evaluator:
    """Model evaluation metrics and figure export helpers."""

    @staticmethod
    def evaluate(model: Any, X_test, y_test) -> Dict[str, float]:
        y_pred = model.predict(X_test)
        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
            "f1": float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
            "report": classification_report(y_test, y_pred, zero_division=0),
        }
        return metrics

    @staticmethod
    def evaluate_with_predictions(model: Any, X_test, y_test):
        y_pred = model.predict(X_test)
        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
            "f1": float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
            "report": classification_report(y_test, y_pred, zero_division=0),
        }
        return metrics, y_pred

    @staticmethod
    def save_visualizations(
        y_true: Iterable,
        y_pred: Iterable,
        metrics: Dict[str, float],
        output_dir: str | Path,
        class_names: Optional[list[str]] = None,
    ) -> Dict[str, str]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        y_true_arr = np.asarray(list(y_true))
        y_pred_arr = np.asarray(list(y_pred))
        labels = sorted(set(y_true_arr.tolist()) | set(y_pred_arr.tolist()))

        if class_names is None:
            class_names = [str(label) for label in labels]

        # Confusion matrix figure
        cm = confusion_matrix(y_true_arr, y_pred_arr, labels=labels)
        fig_cm = output_path / "confusion_matrix.png"
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=class_names, yticklabels=class_names)
        plt.title("Confusion Matrix")
        plt.xlabel("Predicted")
        plt.ylabel("True")
        plt.tight_layout()
        plt.savefig(fig_cm, dpi=150)
        plt.close()

        # Normalized confusion matrix figure
        fig_cm_norm = output_path / "confusion_matrix_normalized.png"
        cm_float = cm.astype(float)
        row_sum = cm_float.sum(axis=1, keepdims=True)
        cm_norm = np.divide(cm_float, row_sum, out=np.zeros_like(cm_float), where=row_sum != 0)
        plt.figure(figsize=(8, 6))
        sns.heatmap(
            cm_norm,
            annot=True,
            fmt=".2f",
            cmap="YlGnBu",
            xticklabels=class_names,
            yticklabels=class_names,
            vmin=0.0,
            vmax=1.0,
        )
        plt.title("Normalized Confusion Matrix")
        plt.xlabel("Predicted")
        plt.ylabel("True")
        plt.tight_layout()
        plt.savefig(fig_cm_norm, dpi=150)
        plt.close()

        # Metrics bar figure
        fig_metrics = output_path / "metrics_bar.png"
        metric_names = ["accuracy", "precision", "recall", "f1"]
        values = [float(metrics.get(name, 0.0)) for name in metric_names]
        plt.figure(figsize=(8, 5))
        bars = plt.bar(metric_names, values, color=["#2E86AB", "#A23B72", "#F18F01", "#5FAD56"])
        plt.ylim(0, 1.0)
        plt.title("Model Metrics")
        plt.ylabel("Score")
        for bar, val in zip(bars, values):
            plt.text(bar.get_x() + bar.get_width() / 2, min(0.98, val + 0.02), f"{val:.3f}", ha="center", va="bottom")
        plt.tight_layout()
        plt.savefig(fig_metrics, dpi=150)
        plt.close()

        # Class distribution comparison
        fig_distribution = output_path / "class_distribution.png"
        true_counts = [int(np.sum(y_true_arr == label)) for label in labels]
        pred_counts = [int(np.sum(y_pred_arr == label)) for label in labels]
        positions = np.arange(len(labels))
        width = 0.36
        plt.figure(figsize=(10, 5))
        plt.bar(positions - width / 2, true_counts, width=width, label="True", color="#2563eb")
        plt.bar(positions + width / 2, pred_counts, width=width, label="Pred", color="#f97316")
        plt.xticks(positions, class_names, rotation=30, ha="right")
        plt.ylabel("Count")
        plt.title("Class Distribution (True vs Predicted)")
        plt.legend()
        plt.tight_layout()
        plt.savefig(fig_distribution, dpi=150)
        plt.close()

        return {
            "confusion_matrix": str(fig_cm),
            "confusion_matrix_normalized": str(fig_cm_norm),
            "metrics_bar": str(fig_metrics),
            "class_distribution": str(fig_distribution),
        }
