#!/usr/bin/env python3
"""Rollback utility for model artifacts.

This script switches the fixed latest artifact back to an older timestamped
model without deleting any historical files.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import joblib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.model_artifacts import (
    DEFAULT_ARTIFACT_NAME,
    list_timestamped_artifacts,
    upsert_model_registry_entry,
)


def _resolve_path(base: Path, maybe_relative: str) -> Path:
    path = Path(maybe_relative)
    return path if path.is_absolute() else (base / path).resolve()


def _latest_path(models_dir: Path) -> Path:
    return models_dir / DEFAULT_ARTIFACT_NAME


def _backup_name(latest_path: Path) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return latest_path.with_name(f"{latest_path.stem}_rollback_{stamp}{latest_path.suffix}")


def _validate_artifact(path: Path) -> None:
    joblib.load(path)


def _print_versions(versions: list[Path]) -> None:
    payload = {
        "count": len(versions),
        "versions": [str(path.name) for path in versions],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def rollback_model(
    models_dir: Path,
    *,
    target: str | None = None,
    steps: int = 1,
    show_versions: bool = False,
) -> bool:
    base_name = Path(DEFAULT_ARTIFACT_NAME).stem.replace("_latest", "")
    versions = list_timestamped_artifacts(models_dir, base_name=base_name)

    if show_versions:
        _print_versions(versions)
        return True

    if target:
        target_path = _resolve_path(models_dir, target)
    else:
        if len(versions) <= steps:
            print("可回滚版本不足。请先训练出更多历史模型，或用 --target 指定具体版本。")
            return False
        target_path = versions[-(steps + 1)]

    if not target_path.exists():
        print(f"找不到目标模型文件: {target_path}")
        return False

    latest_path = _latest_path(models_dir)
    latest_path.parent.mkdir(parents=True, exist_ok=True)

    backup_path = None
    if latest_path.exists():
        backup_path = _backup_name(latest_path)
        shutil.copy2(latest_path, backup_path)

    try:
        shutil.copy2(target_path, latest_path)
        _validate_artifact(latest_path)
    except Exception as exc:
        print(f"回滚失败: {exc}")
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, latest_path)
            print(f"已恢复原 latest: {latest_path}")
        return False

    upsert_model_registry_entry(
        models_dir,
        artifact_path=target_path,
        latest_path=latest_path,
        status="current",
        metadata={
            "rollback_from": str(backup_path) if backup_path else None,
            "rollback_target": str(target_path),
        },
    )

    print("=" * 60)
    print("模型回滚完成")
    print("=" * 60)
    print(f"目标版本: {target_path}")
    print(f"当前 latest: {latest_path}")
    if backup_path:
        print(f"回滚前备份: {backup_path}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Rollback the latest model artifact to a previous version.")
    parser.add_argument(
        "--models-dir",
        type=str,
        default="data/models",
        help="Directory containing model artifacts.",
    )
    parser.add_argument(
        "--target",
        type=str,
        default="",
        help="Explicit target artifact filename or path to restore.",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=1,
        help="Rollback N versions back from the newest timestamped artifact.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print available timestamped versions and exit.",
    )
    args = parser.parse_args()

    models_dir = _resolve_path(PROJECT_ROOT, args.models_dir)
    success = rollback_model(
        models_dir,
        target=args.target or None,
        steps=max(1, args.steps),
        show_versions=args.list,
    )
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
