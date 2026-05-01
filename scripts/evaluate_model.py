#!/usr/bin/env python3
"""Evaluate a trained model on one CSV file or a directory of CSV files."""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from sklearn.exceptions import InconsistentVersionWarning
except Exception:  # pragma: no cover
    InconsistentVersionWarning = None

if InconsistentVersionWarning is not None:
    warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

from src.utils.model_artifacts import DEFAULT_ARTIFACT_NAME, LEGACY_ARTIFACT_NAME, load_artifacts


LABEL_CANDIDATES = (
    "Label",
    "label",
    "LABEL",
    "Class",
    "class",
    "Attack",
    "attack",
    "Target",
    "target",
    "y",
    "Y",
)


@dataclass
class RunningStats:
    """Incremental statistics for one dataset or file."""

    rows: int = 0
    correct: int = 0
    confidence_sum: float = 0.0
    confidence_min: float = math.inf
    confidence_max: float = -math.inf
    true_counts: Counter[str] = field(default_factory=Counter)
    pred_counts: Counter[str] = field(default_factory=Counter)
    confusion: DefaultDict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))

    def update(self, y_true: Sequence[str], y_pred: Sequence[str], confidence: Sequence[float]) -> None:
        if len(y_true) == 0:
            return

        true_arr = np.asarray(y_true, dtype=object)
        pred_arr = np.asarray(y_pred, dtype=object)
        conf_arr = np.asarray(confidence, dtype=float)

        self.rows += int(len(true_arr))
        self.correct += int(np.sum(true_arr == pred_arr))
        self.confidence_sum += float(conf_arr.sum())
        self.confidence_min = min(self.confidence_min, float(conf_arr.min()))
        self.confidence_max = max(self.confidence_max, float(conf_arr.max()))

        self.true_counts.update(pd.Series(true_arr).value_counts().to_dict())
        self.pred_counts.update(pd.Series(pred_arr).value_counts().to_dict())

        pair_counts = pd.DataFrame({"true": true_arr, "pred": pred_arr}).value_counts()
        for (true_label, pred_label), count in pair_counts.items():
            self.confusion[str(true_label)][str(pred_label)] += int(count)

    @property
    def mean_confidence(self) -> float:
        return float(self.confidence_sum / self.rows) if self.rows else 0.0

    @property
    def accuracy(self) -> float:
        return float(self.correct / self.rows) if self.rows else 0.0


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def _resolve_path(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def _discover_csv_files(root: Path) -> list[Path]:
    if root.is_file():
        if root.suffix.lower() != ".csv":
            raise ValueError(f"Input file must be a CSV file: {root}")
        return [root]

    if not root.exists():
        raise FileNotFoundError(f"Input path does not exist: {root}")

    files = sorted(
        path
        for path in root.rglob("*.csv")
        if path.is_file() and not path.name.startswith(".~lock.")
    )
    if not files:
        raise FileNotFoundError(f"No CSV files found under: {root}")
    return files


def _detect_label_column(columns: Iterable[str], explicit: Optional[str] = None) -> str:
    normalized = {str(column).strip().lower(): str(column) for column in columns}
    if explicit:
        key = explicit.strip().lower()
        if key not in normalized:
            raise KeyError(f"Label column '{explicit}' was not found.")
        return normalized[key]

    for candidate in LABEL_CANDIDATES:
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]

    raise KeyError(
        "Could not detect the label column. "
        f"Tried: {', '.join(LABEL_CANDIDATES)}"
    )


def _normalize_label(value: Any) -> Optional[str]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.upper()


def _canonicalize_prediction(value: Any, reverse_label_mapping: Dict[int, str]) -> str:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, (int, np.integer)):
        mapped = reverse_label_mapping.get(int(value))
        if mapped is not None:
            return str(mapped).strip().upper()
        return str(int(value))
    mapped = reverse_label_mapping.get(value)
    if mapped is not None:
        return str(mapped).strip().upper()
    text = str(value).strip()
    return text.upper() if text else ""


def _is_runnable_package(package: Dict[str, Any]) -> bool:
    return bool(package.get("model") is not None and package.get("preprocessor") is not None and package.get("scaler") is not None)


def _load_package_with_fallback(requested_path: Path, allow_fallback: bool = True) -> tuple[Dict[str, Any], Path, list[str]]:
    notices: list[str] = []
    package = load_artifacts(requested_path)
    if _is_runnable_package(package):
        return package, requested_path, notices

    if not allow_fallback:
        raise ValueError(
            f"Artifact at {requested_path} does not contain a runnable model. "
            f"Available keys: {sorted(package.keys()) if isinstance(package, dict) else type(package)}"
        )

    fallback_path = requested_path.with_name(LEGACY_ARTIFACT_NAME)
    if fallback_path.exists() and fallback_path != requested_path:
        fallback = load_artifacts(fallback_path)
        if _is_runnable_package(fallback):
            notices.append(
                f"Requested artifact '{requested_path.name}' is not a runnable model; "
                f"using fallback '{fallback_path.name}' instead."
            )
            return fallback, fallback_path, notices

    raise ValueError(
        f"Artifact at {requested_path} does not contain a runnable model and no fallback model was found. "
        f"Available keys: {sorted(package.keys()) if isinstance(package, dict) else type(package)}"
    )


def _transform_chunk(package: Dict[str, Any], chunk: pd.DataFrame) -> np.ndarray:
    import numpy as np
    
    preprocessor = package["preprocessor"]
    scaler = package["scaler"]
    selector = package.get("selector")

    # 1. 过一遍模型原有的预处理器
    feature_frame = preprocessor.transform_dataframe(chunk, fit=False)
    
    # ========================================================
    # 救命代码 V2：精准对齐模型的 78 个特征！
    # ========================================================
    # 尝试从模型中读取它真正需要的列名名单 (Scikit-Learn 标准特性)
    if hasattr(scaler, "feature_names_in_"):
        expected_features = scaler.feature_names_in_
        
        # 防御性编程：如果 CSV 刚好缺失了模型需要的某列，补 0 防止崩溃
        for col in expected_features:
            if col not in feature_frame.columns:
                feature_frame[col] = 0.0
                
        # 严格按照名单和顺序，只提取这 78 个特征！多余的全部抛弃！
        numeric_frame = feature_frame[expected_features].copy()
    else:
        # 如果模型比较老没有保存名单，退化为保留纯数字并硬截断前 78 列
        numeric_frame = feature_frame.select_dtypes(include=[np.number]).copy()
        n_features = getattr(scaler, "n_features_in_", 78)
        if numeric_frame.shape[1] > n_features:
            numeric_frame = numeric_frame.iloc[:, :n_features]
            
    # 顺手清理无穷大 (Infinity) 和缺失值 (NaN)
    numeric_frame.replace([np.inf, -np.inf], np.nan, inplace=True)
    numeric_frame.fillna(0, inplace=True) 
    # ========================================================

    # 2. 把纯净且数量完美对齐的 78 个特征喂给 scaler
    scaled = scaler.transform(numeric_frame.values)
    
    if selector is None:
        return scaled
    if getattr(selector, "use_identity", False):
        return scaled
    return selector.transform(scaled)


def _predict_chunk(package: Dict[str, Any], chunk: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    selected = _transform_chunk(package, chunk)
    model = package["model"]
    predicted = model.predict(selected)
    if hasattr(model, "predict_proba"):
        confidence = np.max(model.predict_proba(selected), axis=1)
    else:
        confidence = np.ones(len(predicted), dtype=float)
    return np.asarray(predicted), np.asarray(confidence, dtype=float)


def _build_label_order(package: Dict[str, Any], stats: RunningStats, per_file_stats: Dict[str, RunningStats]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    label_mapping = package.get("label_mapping") or {}
    if isinstance(label_mapping, dict):
        try:
            model_labels = [str(label).strip().upper() for label, _ in sorted(label_mapping.items(), key=lambda item: int(item[1]))]
        except Exception:
            model_labels = [str(label).strip().upper() for label in label_mapping.keys()]
        for label in model_labels:
            if label and label not in seen:
                ordered.append(label)
                seen.add(label)

    for source in [stats.true_counts, stats.pred_counts]:
        for label in source.keys():
            label = str(label).strip().upper()
            if label and label not in seen:
                ordered.append(label)
                seen.add(label)

    for file_stats in per_file_stats.values():
        for source in [file_stats.true_counts, file_stats.pred_counts]:
            for label in source.keys():
                label = str(label).strip().upper()
                if label and label not in seen:
                    ordered.append(label)
                    seen.add(label)

    return ordered


def _confusion_matrix_from_counts(confusion: Dict[str, Counter[str]], labels: Sequence[str]) -> np.ndarray:
    matrix = np.zeros((len(labels), len(labels)), dtype=np.int64)
    index = {label: idx for idx, label in enumerate(labels)}
    for true_label, pred_counts in confusion.items():
        if true_label not in index:
            continue
        row = index[true_label]
        for pred_label, count in pred_counts.items():
            if pred_label not in index:
                continue
            matrix[row, index[pred_label]] += int(count)
    return matrix


def _compute_metrics(matrix: np.ndarray, labels: Sequence[str]) -> Dict[str, Any]:
    total = int(matrix.sum())
    if total == 0:
        return {
            "accuracy": 0.0,
            "precision_weighted": 0.0,
            "recall_weighted": 0.0,
            "f1_weighted": 0.0,
            "precision_macro": 0.0,
            "recall_macro": 0.0,
            "f1_macro": 0.0,
            "balanced_accuracy": 0.0,
            "support": 0,
            "per_class": {},
        }

    tp = np.diag(matrix).astype(float)
    support = matrix.sum(axis=1).astype(float)
    predicted = matrix.sum(axis=0).astype(float)

    precision = np.divide(tp, predicted, out=np.zeros_like(tp), where=predicted != 0)
    recall = np.divide(tp, support, out=np.zeros_like(tp), where=support != 0)
    f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros_like(tp), where=(precision + recall) != 0)

    weighted_precision = float(np.sum(precision * support) / total)
    weighted_recall = float(np.sum(recall * support) / total)
    weighted_f1 = float(np.sum(f1 * support) / total)
    macro_precision = float(np.mean(precision)) if len(precision) else 0.0
    macro_recall = float(np.mean(recall)) if len(recall) else 0.0
    macro_f1 = float(np.mean(f1)) if len(f1) else 0.0
    accuracy = float(tp.sum() / total)
    balanced_accuracy = macro_recall

    per_class = {
        label: {
            "precision": float(precision[idx]),
            "recall": float(recall[idx]),
            "f1": float(f1[idx]),
            "support": int(support[idx]),
            "predicted": int(predicted[idx]),
            "true_positive": int(tp[idx]),
        }
        for idx, label in enumerate(labels)
    }

    return {
        "accuracy": accuracy,
        "precision_weighted": weighted_precision,
        "recall_weighted": weighted_recall,
        "f1_weighted": weighted_f1,
        "precision_macro": macro_precision,
        "recall_macro": macro_recall,
        "f1_macro": macro_f1,
        "balanced_accuracy": balanced_accuracy,
        "support": total,
        "per_class": per_class,
    }


def _save_heatmap(matrix: np.ndarray, labels: Sequence[str], path: Path, title: str, fmt: str = "d") -> None:
    plt.figure(figsize=(max(8, len(labels) * 1.1), max(6, len(labels) * 0.9)))
    sns.heatmap(matrix, annot=True, fmt=fmt, cmap="Blues", xticklabels=labels, yticklabels=labels, cbar=True)
    plt.title(title)
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def _save_metrics_bar(metrics: Dict[str, Any], path: Path) -> None:
    names = ["accuracy", "precision_weighted", "recall_weighted", "f1_weighted"]
    values = [float(metrics.get(name, 0.0)) for name in names]
    plt.figure(figsize=(9, 5))
    bars = plt.bar(names, values, color=["#2563eb", "#7c3aed", "#f97316", "#16a34a"])
    plt.ylim(0, 1.0)
    plt.ylabel("Score")
    plt.title("Overall Model Metrics")
    for bar, value in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width() / 2, min(0.98, value + 0.02), f"{value:.4f}", ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def _save_distribution_chart(true_counts: Counter[str], pred_counts: Counter[str], labels: Sequence[str], path: Path) -> None:
    true_values = [int(true_counts.get(label, 0)) for label in labels]
    pred_values = [int(pred_counts.get(label, 0)) for label in labels]
    positions = np.arange(len(labels))
    width = 0.38
    plt.figure(figsize=(max(10, len(labels) * 1.1), 5))
    plt.bar(positions - width / 2, true_values, width=width, label="True", color="#2563eb")
    plt.bar(positions + width / 2, pred_values, width=width, label="Predicted", color="#f97316")
    plt.xticks(positions, labels, rotation=30, ha="right")
    plt.ylabel("Count")
    plt.title("Class Distribution: True vs Predicted")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def _evaluate_files(
    package: Dict[str, Any],
    files: Sequence[Path],
    *,
    chunk_size: int,
    label_column: Optional[str],
) -> tuple[RunningStats, Dict[str, RunningStats], list[dict[str, Any]], list[str]]:
    overall = RunningStats()
    per_file: Dict[str, RunningStats] = {}
    notices: list[str] = []
    observed_labels: set[str] = set()

    for file_index, csv_path in enumerate(files, start=1):
        file_stats = RunningStats()
        per_file[csv_path.name] = file_stats
        print(f"[{file_index}/{len(files)}] Evaluating {csv_path.name}", flush=True)

        for chunk in pd.read_csv(csv_path, low_memory=False, chunksize=chunk_size, on_bad_lines="skip"):
            resolved_label_col = _detect_label_column(chunk.columns, explicit=label_column)
            labels = chunk[resolved_label_col]
            valid_mask = labels.notna()
            if not valid_mask.any():
                continue

            chunk = chunk.loc[valid_mask].copy()
            labels = labels.loc[valid_mask]
            y_true = [value for value in (_normalize_label(item) for item in labels.tolist()) if value]
            if not y_true:
                continue

            try:
                y_pred_idx, confidence = _predict_chunk(package, chunk)
            except Exception as exc:
                raise RuntimeError(f"Failed to predict on {csv_path.name}: {exc}") from exc

            reverse_mapping = {int(value): str(key).strip().upper() for key, value in (package.get("label_mapping") or {}).items()}
            y_pred = [_canonicalize_prediction(item, reverse_mapping) for item in y_pred_idx.tolist()]

            if len(y_pred) != len(y_true):
                raise RuntimeError(
                    f"Prediction row count mismatch in {csv_path.name}: "
                    f"true={len(y_true)} pred={len(y_pred)}"
                )

            observed_labels.update(y_true)
            observed_labels.update(label for label in y_pred if label)

            overall.update(y_true, y_pred, confidence)
            file_stats.update(y_true, y_pred, confidence)

    per_file_metrics: list[dict[str, Any]] = []
    for file_name, stats in per_file.items():
        labels = sorted(set(stats.true_counts.keys()) | set(stats.pred_counts.keys()), key=str)
        matrix = _confusion_matrix_from_counts(stats.confusion, labels)
        metrics = _compute_metrics(matrix, labels)
        per_file_metrics.append(
            {
                "file": file_name,
                "rows": stats.rows,
                "accuracy": metrics["accuracy"],
                "precision_weighted": metrics["precision_weighted"],
                "recall_weighted": metrics["recall_weighted"],
                "f1_weighted": metrics["f1_weighted"],
                "mean_confidence": stats.mean_confidence,
                "min_confidence": 0.0 if math.isinf(stats.confidence_min) else float(stats.confidence_min),
                "max_confidence": 0.0 if math.isinf(stats.confidence_max) else float(stats.confidence_max),
                "true_classes": len(stats.true_counts),
                "pred_classes": len(stats.pred_counts),
            }
        )

    return overall, per_file, per_file_metrics, sorted(observed_labels)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained model across one CSV or a CSV directory.")
    parser.add_argument(
        "--input",
        default="data/raw",
        help="CSV file or directory containing CSV files.",
    )
    parser.add_argument(
        "--artifact",
        default=f"data/models/{DEFAULT_ARTIFACT_NAME}",
        help="Model artifact path.",
    )
    parser.add_argument(
        "--output_dir",
        default="results/eval",
        help="Directory where evaluation outputs will be written.",
    )
    parser.add_argument(
        "--chunk_size",
        type=int,
        default=50000,
        help="Chunk size for streaming large CSV files.",
    )
    parser.add_argument(
        "--label_column",
        default="",
        help="Optional explicit label column name. If omitted, auto-detection is used.",
    )
    parser.add_argument(
        "--no_fallback",
        action="store_true",
        help="Do not fall back to the legacy model_artifacts.pkl if the requested artifact is not runnable.",
    )
    args = parser.parse_args()

    input_path = _resolve_path(PROJECT_ROOT, args.input)
    artifact_path = _resolve_path(PROJECT_ROOT, args.artifact)
    output_root = _resolve_path(PROJECT_ROOT, args.output_dir)
    output_run = output_root / f"eval_{_now_stamp()}"
    output_run.mkdir(parents=True, exist_ok=True)

    csv_files = _discover_csv_files(input_path)
    print(f"Discovered {len(csv_files)} CSV file(s).", flush=True)

    package, resolved_artifact_path, notices = _load_package_with_fallback(
        artifact_path,
        allow_fallback=not args.no_fallback,
    )

    for notice in notices:
        print(f"NOTICE: {notice}", flush=True)

    label_mapping = package.get("label_mapping") or {}
    if isinstance(label_mapping, dict) and label_mapping:
        print(f"Model label mapping: {label_mapping}", flush=True)

    overall_stats, per_file_stats, per_file_metrics, observed_labels = _evaluate_files(
        package,
        csv_files,
        chunk_size=max(1000, int(args.chunk_size)),
        label_column=args.label_column or None,
    )

    labels = _build_label_order(package, overall_stats, per_file_stats)
    if not labels:
        labels = observed_labels
    if not labels:
        raise RuntimeError("No labels were observed during evaluation.")

    overall_matrix = _confusion_matrix_from_counts(overall_stats.confusion, labels)
    overall_metrics = _compute_metrics(overall_matrix, labels)

    confidence_summary = {
        "mean": overall_stats.mean_confidence,
        "min": 0.0 if math.isinf(overall_stats.confidence_min) else float(overall_stats.confidence_min),
        "max": 0.0 if math.isinf(overall_stats.confidence_max) else float(overall_stats.confidence_max),
        "rows": overall_stats.rows,
    }

    summary_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "requested_artifact": str(artifact_path),
        "resolved_artifact": str(resolved_artifact_path),
        "input_path": str(input_path),
        "csv_files": [str(path) for path in csv_files],
        "file_count": len(csv_files),
        "row_count": overall_stats.rows,
        "labels": labels,
        "confidence": confidence_summary,
        "overall_metrics": overall_metrics,
    }

    per_file_df = pd.DataFrame(per_file_metrics).sort_values(["accuracy", "rows", "file"], ascending=[False, False, True])
    per_file_csv = output_run / "per_file_metrics.csv"
    per_file_df.to_csv(per_file_csv, index=False)

    metrics_json = output_run / "evaluation_summary.json"
    metrics_json.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    matrix_df = pd.DataFrame(overall_matrix, index=labels, columns=labels)
    matrix_df.to_csv(output_run / "confusion_matrix.csv", encoding="utf-8")

    row_sums = overall_matrix.sum(axis=1, keepdims=True)
    normalized = np.divide(overall_matrix.astype(float), row_sums, out=np.zeros_like(overall_matrix, dtype=float), where=row_sums != 0)
    pd.DataFrame(normalized, index=labels, columns=labels).to_csv(output_run / "confusion_matrix_normalized.csv", encoding="utf-8")

    _save_heatmap(overall_matrix, labels, output_run / "confusion_matrix.png", "Confusion Matrix")
    _save_heatmap(normalized, labels, output_run / "confusion_matrix_normalized.png", "Normalized Confusion Matrix", fmt=".2f")
    _save_metrics_bar(overall_metrics, output_run / "metrics_bar.png")
    _save_distribution_chart(overall_stats.true_counts, overall_stats.pred_counts, labels, output_run / "class_distribution.png")

    print("=" * 72, flush=True)
    print(f"Evaluation complete. Outputs written to: {output_run}", flush=True)
    print(
        json.dumps(
            {
                "accuracy": overall_metrics["accuracy"],
                "precision_weighted": overall_metrics["precision_weighted"],
                "recall_weighted": overall_metrics["recall_weighted"],
                "f1_weighted": overall_metrics["f1_weighted"],
                "balanced_accuracy": overall_metrics["balanced_accuracy"],
                "mean_confidence": confidence_summary["mean"],
                "rows": overall_stats.rows,
                "files": len(csv_files),
                "artifact": str(resolved_artifact_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
