import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.models.online_trainer import OnlineTrainer
from src.utils.alert import AlertManager


class DummyChannel:
    channel_type = "dummy"

    def __init__(self, name="dummy"):
        self.name = name
        self.calls = []

    def send(self, payload):
        self.calls.append(payload)
        from src.utils.alert import AlertResult

        return AlertResult(channel=self.name, success=True)


def test_alert_manager_detection_and_batch():
    channel = DummyChannel()
    manager = AlertManager(
        enabled=True,
        trigger_on_detection=True,
        trigger_on_batch=True,
        retries=1,
        retry_delay_seconds=0,
        channels=[channel],
        templates={
            "detection": "{attack_type} {severity}",
            "batch": "{total_events} {attack_events}",
        },
    )
    event = {
        "timestamp": "2026-04-04T12:00:00+00:00",
        "prediction_label": "SYN_FLOOD",
        "confidence": 0.98,
        "is_attack": True,
        "severity": "critical",
        "source": "api",
        "input_kind": "features",
    }
    detection = manager.notify_detection(event=event, result={"attack_type": "SYN_FLOOD", "explanation": {"summary": "test"}})
    assert detection["sent"] is True
    assert channel.calls

    batch = manager.notify_batch(events=[event, {**event, "is_attack": False}], summary={"total_events": 2})
    assert batch["sent"] is True
    assert len(channel.calls) >= 2


def test_online_trainer_smoke(tmp_path):
    data_dir = tmp_path / "raw"
    data_dir.mkdir()
    df = pd.DataFrame(
        {
            "Timestamp": pd.date_range("2024-01-01", periods=120, freq="s"),
            "Destination Port": [80] * 120,
            "Source Port": list(range(1000, 1120)),
            "Protocol": [6] * 60 + [17] * 60,
            "SYN Flag Count": [1] * 60 + [0] * 60,
            "Packet Length Mean": [500.0] * 120,
            "Label": [0] * 60 + [1] * 60,
        }
    )
    (data_dir / "sample.csv").write_text(df.to_csv(index=False), encoding="utf-8")

    artifact_path = tmp_path / "models" / "model_artifacts.pkl"
    trainer = OnlineTrainer(
        data_dir=str(data_dir),
        artifact_path=str(artifact_path),
        output_dir=str(tmp_path / "models"),
        figures_dir=str(tmp_path / "figures"),
        window_rows=120,
        chunk_size=50,
        rf_estimators=10,
        xgb_estimators=10,
        verbose=False,
    )
    result = trainer.train()

    assert result.artifact_path.exists()
    assert result.row_count > 0
    assert artifact_path.exists()
    assert (tmp_path / "models" / "online_metrics.json").exists()
