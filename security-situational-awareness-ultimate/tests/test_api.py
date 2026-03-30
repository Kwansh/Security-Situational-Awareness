import importlib
from pathlib import Path

from fastapi.testclient import TestClient

from scripts.train import build_training_pipeline
from src.model_artifacts import save_artifacts


def make_dataset_frame():
    import pandas as pd

    rows = []
    for index in range(30):
        label = "BENIGN" if index % 2 == 0 else "Syn"
        rows.append(
            {
                "Flow ID": f"flow-{index}",
                "Source IP": "192.168.0.1",
                "Destination IP": "10.0.0.1",
                "Timestamp": "2018-11-03 11:36:28",
                "Flow Duration": 2000 + index,
                "Total Fwd Packets": 5 + index,
                "Total Backward Packets": 1 + (index % 4),
                "Flow Bytes/s": 3.0 + index,
                "Label": label,
            }
        )
    return pd.DataFrame(rows)


def make_workspace(root: Path, name: str) -> Path:
    workspace = root / ".test_runs" / name
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def test_predict_endpoint(monkeypatch):
    tmp_path = make_workspace(Path.cwd(), "api")
    data_dir = tmp_path / "raw"
    data_dir.mkdir(exist_ok=True)
    make_dataset_frame().to_csv(data_dir / "sample.csv", index=False)

    result = build_training_pipeline(str(data_dir), k_features=3, use_stacking=False, test_size=0.2)
    artifact_path = tmp_path / "model_artifacts.pkl"
    save_artifacts(
        artifact_path,
        model=result["ensemble"],
        scaler=result["preprocessor"].scaler,
        selector=result["selector"],
        feature_columns=result["feature_columns"],
        label_mapping=result["preprocessor"].label_mapping,
        metrics=result["metrics"],
    )

    monkeypatch.setenv("MODEL_ARTIFACT_PATH", str(artifact_path))
    module = importlib.import_module("src.api.server")
    module = importlib.reload(module)

    with TestClient(module.app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["model_loaded"] is True

        response = client.post("/predict", json={"features": [2001, 6, 2, 4.0]})
        assert response.status_code == 200
        payload = response.json()
        assert "prediction" in payload
        assert "confidence" in payload
