"""Model artifact persistence helpers."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, Optional

import joblib


DEFAULT_ARTIFACT_NAME = "model_artifacts_latest.pkl"
LEGACY_ARTIFACT_NAME = "model_artifacts.pkl"
MODEL_REGISTRY_NAME = "model_registry.json"
ARTIFACT_VERSION = "4.1.0"


def build_timestamped_artifact_name(base_name: str = "model_artifacts", timestamp: str | None = None) -> str:
    """Build a stable timestamped artifact filename."""
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    return f"{base_name}_{stamp}.pkl"


def build_latest_artifact_name(base_name: str = "model_artifacts") -> str:
    """Return the fixed latest artifact filename."""
    return f"{base_name}_latest.pkl"


def get_model_registry_path(models_dir: str | Path) -> Path:
    """Return the registry path inside the model directory."""
    return Path(models_dir) / MODEL_REGISTRY_NAME


def is_timestamped_artifact_name(filename: str) -> bool:
    """Check whether a filename matches the timestamped artifact convention."""
    return bool(re.match(r"^.+_\d{8}_\d{6}(?:_\d{6})?\.pkl$", Path(filename).name))


def list_timestamped_artifacts(models_dir: str | Path, base_name: str = "model_artifacts") -> list[Path]:
    """List timestamped artifacts in chronological order."""
    root = Path(models_dir)
    if not root.exists():
        return []

    versions: list[Path] = []
    for path in root.glob(f"{base_name}_*.pkl"):
        if path.name in {build_latest_artifact_name(base_name), LEGACY_ARTIFACT_NAME}:
            continue
        if path.name.endswith("_backup.pkl") or "_backup_" in path.name:
            continue
        if is_timestamped_artifact_name(path.name):
            versions.append(path)

    return sorted(versions)


def load_model_registry(models_dir: str | Path) -> list[dict[str, Any]]:
    """Load the model registry if present."""
    registry_path = get_model_registry_path(models_dir)
    if not registry_path.exists():
        return []
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [entry for entry in payload if isinstance(entry, dict)]


def save_model_registry(models_dir: str | Path, entries: list[dict[str, Any]]) -> Path:
    """Persist the registry atomically."""
    registry_path = get_model_registry_path(models_dir)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, dir=str(registry_path.parent), suffix=".tmp", encoding="utf-8") as handle:
        tmp_path = Path(handle.name)
        handle.write(json.dumps(entries, ensure_ascii=False, indent=2))
    try:
        try:
            os.replace(tmp_path, registry_path)
        except PermissionError:
            registry_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    return registry_path


def upsert_model_registry_entry(
    models_dir: str | Path,
    *,
    artifact_path: str | Path,
    latest_path: str | Path,
    status: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Path:
    """Insert or update an artifact entry and mark it as current status."""
    artifact_str = str(artifact_path)
    latest_str = str(latest_path)
    entries = load_model_registry(models_dir)
    now = datetime.now(timezone.utc).isoformat()
    updated: list[dict[str, Any]] = []
    found = False

    for entry in entries:
        if str(entry.get("artifact_path")) == artifact_str:
            found = True
            merged = {
                **entry,
                "latest_path": latest_str,
                "status": status,
                "updated_at": now,
                "metadata": {**(entry.get("metadata") or {}), **(metadata or {})},
            }
            updated.append(merged)
        else:
            updated.append(entry)

    if not found:
        updated.append(
            {
                "artifact_path": artifact_str,
                "latest_path": latest_str,
                "status": status,
                "created_at": now,
                "updated_at": now,
                "metadata": metadata or {},
            }
        )

    if status == "current":
        for entry in updated:
            if str(entry.get("artifact_path")) != artifact_str:
                entry["status"] = entry.get("status") if entry.get("status") not in {None, "", "current"} else "archived"
                entry["updated_at"] = now

    return save_model_registry(models_dir, updated)


def _build_artifact_payload(
    *,
    model,
    scaler,
    selector,
    feature_columns,
    label_mapping,
    metrics,
    preprocessor=None,
    metadata: Optional[Dict[str, Any]] = None,
):
    return {
        "model": model,
        "scaler": scaler,
        "selector": selector,
        "feature_columns": list(feature_columns),
        "label_mapping": label_mapping or {},
        "metrics": metrics,
        "preprocessor": preprocessor,
        "metadata": {
            "version": ARTIFACT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        },
    }


def save_artifacts(
    output_path,
    *,
    model,
    scaler,
    selector,
    feature_columns,
    label_mapping,
    metrics,
    preprocessor=None,
    atomic: bool = True,
    backup_path: Optional[str | Path] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Save model artifacts with optional atomic replacement and backup."""
    artifact = _build_artifact_payload(
        model=model,
        scaler=scaler,
        selector=selector,
        feature_columns=feature_columns,
        label_mapping=label_mapping,
        metrics=metrics,
        preprocessor=preprocessor,
        metadata=metadata,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if backup_path is not None and output_path.exists():
        backup_path = Path(backup_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(joblib.load(output_path), backup_path)

    if atomic:
        with NamedTemporaryFile("wb", delete=False, dir=str(output_path.parent), suffix=".tmp") as handle:
            tmp_path = Path(handle.name)
        try:
            joblib.dump(artifact, tmp_path)
            try:
                os.replace(tmp_path, output_path)
            except PermissionError:
                # Some Windows sandboxes refuse atomic renames even when the
                # temp file lives beside the target. Fall back to a direct dump
                # so online training can still complete and hot swap safely.
                joblib.dump(artifact, output_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
    else:
        joblib.dump(artifact, output_path)
    return output_path


def load_artifacts(path):
    """Load model artifacts from disk."""
    return joblib.load(path)


def backup_artifact(path: str | Path, backup_path: Optional[str | Path] = None) -> Optional[Path]:
    """Create a backup copy of the artifact if it exists."""
    source = Path(path)
    if not source.exists():
        return None
    target = Path(backup_path) if backup_path else source.with_name(f"{source.stem}_backup{source.suffix}")
    target.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(joblib.load(source), target)
    return target


def load_metadata(path: str | Path) -> Dict[str, Any]:
    """Return metadata from an artifact if available."""
    artifact = joblib.load(path)
    if isinstance(artifact, dict):
        return artifact.get("metadata", {}) or {}
    return {}


def is_runnable_artifact(artifact: Any) -> bool:
    """Return True when an artifact contains the objects required for inference."""
    if not isinstance(artifact, dict):
        return False
    required = ("model", "preprocessor", "scaler")
    return all(artifact.get(key) is not None for key in required)
