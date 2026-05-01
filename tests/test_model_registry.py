"""Tests for model registry helpers."""

from __future__ import annotations

from pathlib import Path

from src.utils.model_artifacts import (
    build_timestamped_artifact_name,
    list_timestamped_artifacts,
    load_model_registry,
    upsert_model_registry_entry,
)


def test_registry_upsert_and_activation(tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    first = models_dir / build_timestamped_artifact_name("model_artifacts", "20260424_153012_123456")
    second = models_dir / build_timestamped_artifact_name("model_artifacts", "20260424_153112_123456")
    latest = models_dir / "model_artifacts_latest.pkl"

    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    latest.write_text("latest", encoding="utf-8")

    upsert_model_registry_entry(
        models_dir,
        artifact_path=first,
        latest_path=latest,
        status="current",
        metadata={"epoch": 1},
    )
    upsert_model_registry_entry(
        models_dir,
        artifact_path=second,
        latest_path=latest,
        status="current",
        metadata={"epoch": 2},
    )

    registry = load_model_registry(models_dir)
    assert len(registry) == 2
    assert registry[-1]["artifact_path"] == str(second)
    assert registry[-1]["status"] == "current"
    assert registry[0]["status"] == "archived"
    assert registry[-1]["metadata"]["epoch"] == 2

    versions = list_timestamped_artifacts(models_dir)
    assert [path.name for path in versions] == [first.name, second.name]
