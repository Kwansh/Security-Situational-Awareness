<<<<<<< HEAD
﻿"""API endpoint smoke tests."""

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api import server as api_server
import src.api.routes as api_routes
from src.api.server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "model_loaded" in data


class TestMetadataEndpoint:
    def test_metadata(self, client):
        response = client.get("/metadata")
        assert response.status_code in [200, 503]


class TestPredictEndpoint:
    def test_predict_missing_model(self, client):
        payload = {
            "features": {
                "pkt_rate": 1000.0,
                "syn_rate": 500.0,
                "udp_rate": 200.0,
                "dns_rate": 50.0,
                "ntp_rate": 10.0,
                "avg_pkt_size": 500.0,
            }
        }
        response = client.post("/predict", json=payload)
        assert response.status_code in [200, 422, 503]

    def test_predict_invalid_features(self, client):
        payload = {"features": []}
        response = client.post("/predict", json=payload)
        assert response.status_code in [422, 503]

    def test_predict_infinite_values_no_500(self, client):
        payload = {
            "record": {
                "Flow Bytes/s": "Infinity",
                "Flow Packets/s": "1e309",
                "Destination Port": 80,
                "Protocol": 6,
            },
            "source": "test",
        }
        response = client.post("/predict", json=payload)
        assert response.status_code in [200, 422, 503]

    def test_predict_attach_client_ip_and_geo(self, client, monkeypatch):
        monkeypatch.setattr(
            api_server,
            "_predict_single",
            lambda features, record: {
                "prediction": 1,
                "prediction_label": "SYN_FLOOD",
                "confidence": 0.99,
                "is_attack": True,
                "attack_type": "SYN_FLOOD",
                "timestamp": "2026-04-06T00:00:00+00:00",
                "explanation": {},
            },
        )
        monkeypatch.setattr(
            api_server,
            "resolve_ip_geo",
            lambda ip: {
                "provider": "ipapi.co",
                "ip": ip or "",
                "resolved": True,
                "latitude": 37.386,
                "longitude": -122.0838,
                "city": "Mountain View",
                "region": "California",
                "country": "United States",
                "country_code": "US",
                "timezone": "America/Los_Angeles",
            },
        )
        monkeypatch.setattr(
            api_server,
            "log_detection",
            lambda result, **kwargs: {"result_prediction": result["prediction"], **kwargs},
        )

        response = client.post(
            "/predict",
            json={"features": {"pkt_rate": 1.0}, "source": "test"},
            headers={"X-Forwarded-For": "8.8.8.8"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event"]["client_ip"] == "8.8.8.8"
        assert data["event"]["geo"]["resolved"] is True
        assert data["event"]["geo"]["city"] == "Mountain View"

    def test_predict_returns_dynamic_metrics_from_record(self, client, monkeypatch):
        monkeypatch.setattr(
            api_server,
            "_predict_single",
            lambda features, record: {
                "prediction": 1,
                "prediction_label": "SYN_FLOOD",
                "confidence": 0.91,
                "is_attack": True,
                "attack_type": "SYN_FLOOD",
                "timestamp": "2026-04-07T00:00:00+00:00",
                "explanation": {},
            },
        )
        monkeypatch.setattr(
            api_server,
            "resolve_ip_geo",
            lambda ip: {
                "provider": "ipapi.co",
                "ip": ip or "",
                "resolved": False,
                "latitude": None,
                "longitude": None,
                "city": None,
                "region": None,
                "country": None,
                "country_code": None,
                "timezone": None,
            },
        )
        monkeypatch.setattr(
            api_server,
            "log_detection",
            lambda result, **kwargs: {
                "result_prediction": result["prediction"],
                "pkt_len": kwargs["dynamic_metrics"]["pkt_len"],
                "syn_count": kwargs["dynamic_metrics"]["syn_count"],
                "udp_count": kwargs["dynamic_metrics"]["udp_count"],
            },
        )

        response = client.post(
            "/predict",
            json={
                "record": {
                    "Packet Length Mean": "680",
                    "SYN Flag Count": 17,
                    "udp_rate": "95",
                },
                "source": "test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pkt_len"] == 680.0
        assert data["syn_count"] == 17.0
        assert data["udp_count"] == 95.0
        assert data["event"]["pkt_len"] == 680.0
        assert data["event"]["syn_count"] == 17.0
        assert data["event"]["udp_count"] == 95.0


class TestDashboardEndpoints:
    def test_dashboard_summary(self, client):
        response = client.get("/dashboard/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total_events" in data or isinstance(data, dict)

    def test_dashboard_events(self, client):
        response = client.get("/dashboard/events?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "count" in data

    def test_dashboard_events_delta(self, client):
        # First fetch gets cursor.
        response = client.get("/dashboard/events/delta?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "cursor" in data
        assert "summary" in data

        # Second fetch with cursor is still valid and should return JSON shape.
        cursor = data.get("cursor", "")
        response2 = client.get(f"/dashboard/events/delta?limit=10&cursor={cursor}")
        assert response2.status_code == 200
        data2 = response2.json()
        assert "events" in data2
        assert "cursor" in data2
        assert "summary" in data2

    def test_ws_stream(self, client):
        with client.websocket_connect("/ws/stream?interval_ms=50&limit=5") as websocket:
            payload = websocket.receive_json()
            assert "type" in payload

    def test_ws_stream_mode_on_ws_endpoint(self, client):
        with client.websocket_connect("/ws?stream=1&interval_ms=50&limit=5") as websocket:
            payload = websocket.receive_json()
            assert "type" in payload


class TestAdminEndpoints:
    def test_reload_model(self, client):
        response = client.post("/admin/reload-model")
        assert response.status_code == 200
        data = response.json()
        assert "reloaded" in data
        assert "model_loaded" in data

    def test_reset_events(self, client):
        response = client.post("/admin/reset-events?archive=false")
        assert response.status_code == 200
        data = response.json()
        assert data.get("reset") is True
        assert "summary" in data


class TestActiveScanEndpoint:
    def test_active_scan(self, client, monkeypatch):
        monkeypatch.setattr(
            api_routes._active_agent,
            "run",
            lambda payload: type(
                "Result",
                (),
                {
                    "to_dict": lambda self: {
                        "source": payload.get("source", "api_active_scan"),
                        "trace_id": payload.get("trace_id"),
                        "started_at": "2026-04-23T00:00:00+00:00",
                        "finished_at": "2026-04-23T00:00:00+00:00",
                        "duration_ms": 1,
                        "summary": {
                            "target_count": len(payload.get("targets", [])),
                            "port_count_per_target": len(payload.get("tcp_ports", [])),
                            "total_probes": 0,
                            "open_port_count": 0,
                            "high_risk_open_port_count": 0,
                            "error_count": 0,
                        },
                        "findings": [],
                        "recommendations": ["No open ports detected."],
                        "errors": [],
                    }
                },
            )(),
        )

        response = client.post(
            "/api/active-scan",
            json={
                "targets": ["127.0.0.1"],
                "tcp_ports": [22, 80],
                "trace_id": "scan-001",
                "source": "test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["trace_id"] == "scan-001"
        assert "summary" in data
        assert "findings" in data


class TestRootEndpoint:
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
=======
﻿import importlib
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
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
