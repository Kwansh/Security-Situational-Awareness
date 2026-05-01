<<<<<<< HEAD
﻿"""FastAPI service for security situational awareness detection."""

from __future__ import annotations

import asyncio
import io
import json
import math
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware   # ← 新增这一行
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator

from src.detection.rule_engine import RuleEngine
from src.explainability.attack_explainer import AttackExplainer
from src.api.routes import router as extra_router
from src.utils.alert import get_alert_manager, reload_alert_manager
from src.utils.ip_geo import extract_client_ip, resolve_ip_geo
from src.utils.detection_logger import (
    load_events_delta,
    load_recent_events,
    load_summary,
    log_detection,
    reset_detection_history,
)
from src.utils.model_artifacts import (
    DEFAULT_ARTIFACT_NAME,
    LEGACY_ARTIFACT_NAME,
    get_model_registry_path,
    load_artifacts,
    load_model_registry,
    is_runnable_artifact,
)


BENIGN_LABELS = {"normal", "benign", "0"}
UTC = timezone.utc
MAX_ABS_INPUT_VALUE = float(os.getenv("MAX_ABS_INPUT_VALUE", "1e12"))
ALLOW_RULE_ONLY_FALLBACK = os.getenv("ALLOW_RULE_ONLY_API", "0").strip() in {"1", "true", "yes"}
artifacts: Optional[dict] = None
artifacts_lock = threading.RLock()
artifact_mtime: Optional[float] = None
artifact_watch_stop = threading.Event()
artifact_watch_thread: Optional[threading.Thread] = None
rule_engine: RuleEngine = RuleEngine()
explainer: AttackExplainer = AttackExplainer()
alert_manager = get_alert_manager()

_DYNAMIC_METRIC_ALIASES: Dict[str, List[str]] = {
    "pkt_len": [
        "pkt_len",
        "packet_length",
        "packet_len",
        "avg_pkt_size",
        "avg_packet_size",
        "packet_length_mean",
        "packet length mean",
        "average packet size",
        "fwd packet length mean",
    ],
    "syn_count": [
        "syn_count",
        "syn_rate",
        "syn_packets_per_sec",
        "syn per sec",
        "syn flag count",
        "syn_flag_count",
        "synflagcount",
    ],
    "udp_count": [
        "udp_count",
        "udp_rate",
        "udp_packets_per_min",
        "udp per min",
        "udp packet count",
        "udp packets per min",
    ],
}


def _dashboard_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>网络安全态势感知系统</title>
  <style>
    body { font-family: "Microsoft YaHei", Arial, sans-serif; margin: 0; background: #f4f7fb; color: #0f172a; }
    .wrap { max-width: 1100px; margin: 24px auto; padding: 0 16px; }
    .title { font-size: 24px; font-weight: 700; margin-bottom: 12px; }
    .row { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 16px; }
    .card { background: #fff; border-radius: 10px; padding: 14px; box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08); }
    .label { font-size: 12px; color: #475569; }
    .value { font-size: 22px; font-weight: 700; margin-top: 6px; }
    table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08); }
    th, td { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px; }
    th { background: #0f172a; color: #fff; text-align: left; }
    .links { margin-bottom: 14px; font-size: 13px; }
    .links a { margin-right: 12px; color: #1d4ed8; text-decoration: none; }
    .chart-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; margin-bottom: 16px; }
    .chart-card { background: #fff; border-radius: 10px; padding: 14px; box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08); }
    .chart-title { font-size: 14px; font-weight: 700; margin-bottom: 10px; color: #0f172a; }
    .bar-list { display: flex; flex-direction: column; gap: 8px; }
    .bar-item { display: grid; grid-template-columns: 140px 1fr 56px; gap: 8px; align-items: center; font-size: 12px; }
    .bar-track { background: #e2e8f0; border-radius: 999px; height: 10px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #1d4ed8, #0ea5e9); }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="title">网络安全态势感知系统 Dashboard</div>
    <div class="links">
      <a href="/docs" target="_blank">API 文档</a>
      <a href="/health" target="_blank">健康检查</a>
      <a href="/metadata" target="_blank">模型元数据</a>
    </div>
    <div class="row">
      <div class="card"><div class="label">总事件</div><div class="value" id="total_events">-</div></div>
      <div class="card"><div class="label">攻击事件</div><div class="value" id="attack_events">-</div></div>
      <div class="card"><div class="label">正常事件</div><div class="value" id="benign_events">-</div></div>
      <div class="card"><div class="label">攻击比例</div><div class="value" id="attack_ratio">-</div></div>
    </div>
    <div class="chart-grid">
      <div class="chart-card">
        <div class="chart-title">攻击类型分布</div>
        <div class="bar-list" id="label_bars"></div>
      </div>
      <div class="chart-card">
        <div class="chart-title">来源分布</div>
        <div class="bar-list" id="source_bars"></div>
      </div>
    </div>
    <table>
      <thead>
        <tr><th>时间</th><th>标签</th><th>置信度</th><th>是否攻击</th><th>严重度</th><th>来源</th></tr>
      </thead>
      <tbody id="events_body"></tbody>
    </table>
  </div>
  <script>
    function renderBarList(targetId, statsObj) {
      const root = document.getElementById(targetId);
      root.innerHTML = '';
      const entries = Object.entries(statsObj || {}).sort((a, b) => b[1] - a[1]).slice(0, 8);
      if (!entries.length) {
        root.innerHTML = '<div style="font-size:12px;color:#64748b;">暂无数据</div>';
        return;
      }
      const maxVal = Math.max(...entries.map(([, v]) => Number(v) || 0), 1);
      entries.forEach(([name, value]) => {
        const row = document.createElement('div');
        row.className = 'bar-item';
        const width = Math.max(2, Math.round(((Number(value) || 0) / maxVal) * 100));
        row.innerHTML = `
          <div title="${name}">${name}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
          <div style="text-align:right;">${value}</div>
        `;
        root.appendChild(row);
      });
    }

    function prependRows(newEvents) {
      const body = document.getElementById('events_body');
      const frag = document.createDocumentFragment();
      (newEvents || []).forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${item.timestamp || ''}</td><td>${item.prediction_label || ''}</td><td>${(item.confidence ?? 0).toFixed(4)}</td><td>${item.is_attack ? '是' : '否'}</td><td>${item.severity || ''}</td><td>${item.source || ''}</td>`;
        frag.appendChild(tr);
      });
      body.insertBefore(frag, body.firstChild);
      while (body.children.length > 200) {
        body.removeChild(body.lastChild);
      }
    }

    function renderSummary(summary) {
      document.getElementById('total_events').textContent = summary.total_events ?? 0;
      document.getElementById('attack_events').textContent = summary.attack_events ?? 0;
      document.getElementById('benign_events').textContent = summary.benign_events ?? 0;
      document.getElementById('attack_ratio').textContent = ((summary.attack_ratio ?? 0) * 100).toFixed(2) + '%';
      renderBarList('label_bars', summary.labels || {});
      renderBarList('source_bars', summary.sources || {});
    }

    let cursor = null;
    async function bootstrap() {
      const [summaryResp, deltaResp] = await Promise.all([
        fetch('/dashboard/summary'),
        fetch('/dashboard/events/delta?limit=50')
      ]);
      const summary = await summaryResp.json();
      const delta = await deltaResp.json();
      renderSummary(summary);
      prependRows((delta.events || []).slice().reverse());
      cursor = delta.cursor || null;
    }

    async function pullDelta() {
      const q = cursor ? `?limit=50&cursor=${encodeURIComponent(cursor)}` : '?limit=50';
      const resp = await fetch('/dashboard/events/delta' + q);
      const data = await resp.json();
      if (data.summary) renderSummary(data.summary);
      if ((data.events || []).length) prependRows((data.events || []).slice().reverse());
      cursor = data.cursor || cursor;
    }

    bootstrap().then(() => {
      setInterval(pullDelta, 500);
    });
  </script>
</body>
</html>"""


class PredictionRequest(BaseModel):
    """Input payload for `/predict` endpoint."""

    features: Optional[List[float] | Dict[str, Any]] = None
    record: Optional[Dict[str, Any]] = None
    source: str = Field(default="api", max_length=64)

    @model_validator(mode="after")
    def check_payload(self):
        if self.features is None and self.record is None:
            raise ValueError("Provide either `features` or `record`.")
        return self


def _artifact_is_runnable(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return is_runnable_artifact(load_artifacts(path))
    except Exception:
        return False


def get_artifact_path() -> Path:
    env_path = os.getenv("MODEL_ARTIFACT_PATH")
    if env_path:
        return Path(env_path)

    latest = Path(f"data/models/{DEFAULT_ARTIFACT_NAME}")
    typo_latest = Path("data/models/model_artifacts_lastest.pkl")
    legacy = Path(f"data/models/{LEGACY_ARTIFACT_NAME}")
    if _artifact_is_runnable(latest):
        return latest
    if _artifact_is_runnable(typo_latest):
        return typo_latest
    if _artifact_is_runnable(legacy):
        return legacy
    if latest.exists():
        return latest
    if typo_latest.exists():
        return typo_latest
    return legacy


def _artifact_snapshot() -> Optional[dict]:
    with artifacts_lock:
        return artifacts


def _registry_snapshot() -> Dict[str, Any]:
    artifact_path = get_artifact_path()
    registry = load_model_registry(artifact_path.parent)
    active_entry = None
    for entry in reversed(registry):
        if entry.get("status") == "current":
            active_entry = entry
            break
    return {
        "registry_path": str(get_model_registry_path(artifact_path.parent)),
        "entry_count": len(registry),
        "active_entry": active_entry,
    }


def _reverse_label_mapping(artifact_bundle: Optional[dict] = None) -> Dict[int, str]:
    bundle = artifact_bundle or _artifact_snapshot()
    if not bundle:
        return {}
    mapping = bundle.get("label_mapping") or {}
    reverse = {}
    for key, value in mapping.items():
        try:
            reverse[int(value)] = str(key)
        except (TypeError, ValueError):
            continue
    return reverse


def _is_attack_label(label: str) -> bool:
    return str(label).strip().lower() not in BENIGN_LABELS


def _coerce_float_dict(data: Dict[str, Any]) -> Dict[str, float]:
    numeric: Dict[str, float] = {}
    for key, value in data.items():
        try:
            numeric[key] = float(value)
        except (TypeError, ValueError):
            continue
    return numeric


def _normalize_metric_key(key: str) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _to_float_or_none(value: Any) -> Optional[float]:
    try:
        if value is None or str(value).strip() == "":
            return None
        parsed = float(value)
        if not math.isfinite(parsed):
            return None
        return parsed
    except (TypeError, ValueError):
        return None


def _extract_dynamic_metrics(
    features: Optional[List[float] | Dict[str, Any]],
    record: Optional[Dict[str, Any]],
) -> Dict[str, Optional[float]]:
    source: Dict[str, Any] = {}
    if isinstance(record, dict):
        source = record
    elif isinstance(features, dict):
        source = features

    normalized_map: Dict[str, Any] = {_normalize_metric_key(k): v for k, v in source.items()}
    metrics: Dict[str, Optional[float]] = {"pkt_len": 0.0, "syn_count": 0.0, "udp_count": 0.0}

    for canonical, aliases in _DYNAMIC_METRIC_ALIASES.items():
        for alias in aliases:
            value = normalized_map.get(_normalize_metric_key(alias))
            parsed = _to_float_or_none(value)
            if parsed is not None:
                metrics[canonical] = parsed
                break

    flow_packets_per_sec = _to_float_or_none(normalized_map.get(_normalize_metric_key("Flow Packets/s")))
    flow_duration_micro = _to_float_or_none(normalized_map.get(_normalize_metric_key("Flow Duration")))
    syn_flag_count = _to_float_or_none(normalized_map.get(_normalize_metric_key("SYN Flag Count")))
    protocol = _to_float_or_none(normalized_map.get(_normalize_metric_key("Protocol")))
    explicit_syn_rate = None
    for syn_rate_alias in ("syn_rate", "syn_packets_per_sec", "syn per sec"):
        explicit_syn_rate = _to_float_or_none(normalized_map.get(_normalize_metric_key(syn_rate_alias)))
        if explicit_syn_rate is not None:
            break

    # Derive SYN packets per second from CIC-style CSV when explicit syn_rate is missing.
    if explicit_syn_rate is None and syn_flag_count is not None:
        derived_syn = None
        if flow_duration_micro and flow_duration_micro > 0:
            derived_syn = syn_flag_count / (flow_duration_micro / 1_000_000.0)
        elif flow_packets_per_sec is not None:
            derived_syn = syn_flag_count * flow_packets_per_sec
        else:
            derived_syn = syn_flag_count
        if derived_syn is not None and math.isfinite(derived_syn):
            metrics["syn_count"] = max(0.0, float(derived_syn))

    # Practical fallback: many CIC rows have SYN Flag Count=0 almost always.
    # For TCP traffic, fall back to Flow Packets/s so frontend still gets
    # a dynamic "syn-like" rate from CSV instead of a constant zero.
    if (
        explicit_syn_rate is None
        and (metrics["syn_count"] is None or metrics["syn_count"] <= 0.0)
        and protocol == 6.0
        and flow_packets_per_sec is not None
    ):
        metrics["syn_count"] = max(0.0, float(flow_packets_per_sec))

    # Derive UDP packets per minute from protocol + flow packet rate.
    if metrics["udp_count"] in (None, 0.0):
        if protocol == 17.0 and flow_packets_per_sec is not None:
            metrics["udp_count"] = max(0.0, float(flow_packets_per_sec))

    return metrics


def _sanitize_input_array(feature_array: np.ndarray) -> np.ndarray:
    arr = np.asarray(feature_array, dtype=np.float64).reshape(1, -1)
    # Replace NaN/Inf and clamp extreme outliers before scaler.
    arr = np.nan_to_num(arr, nan=0.0, posinf=MAX_ABS_INPUT_VALUE, neginf=-MAX_ABS_INPUT_VALUE)
    arr = np.clip(arr, -MAX_ABS_INPUT_VALUE, MAX_ABS_INPUT_VALUE)
    return arr


def _extract_array_from_features(features: List[float] | Dict[str, Any], artifact_bundle: Optional[dict] = None) -> np.ndarray:
    bundle = artifact_bundle or _artifact_snapshot()
    if bundle is None:
        raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")

    feature_columns = list(bundle.get("feature_columns") or [])
    preprocessor = bundle.get("preprocessor")

    if isinstance(features, list):
        arr = np.asarray(features, dtype=float).reshape(1, -1)
        if feature_columns and arr.shape[1] != len(feature_columns):
            raise HTTPException(
                status_code=422,
                detail=f"Expected {len(feature_columns)} raw features, got {arr.shape[1]}",
            )
        return _sanitize_input_array(arr)

    if not isinstance(features, dict):
        raise HTTPException(status_code=422, detail="`features` must be a list or object.")

    if feature_columns and all(col in features for col in feature_columns):
        try:
            arr = np.asarray([[float(features[col]) for col in feature_columns]], dtype=float)
            return _sanitize_input_array(arr)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid feature value: {exc}") from exc

    if preprocessor is None:
        raise HTTPException(
            status_code=422,
            detail="Feature object does not match model columns and no preprocessor is available.",
        )

    transformed = preprocessor.transform_dataframe(pd.DataFrame([features]), fit=False)
    return _sanitize_input_array(transformed.values)


def _extract_array_from_record(record: Dict[str, Any], artifact_bundle: Optional[dict] = None) -> np.ndarray:
    bundle = artifact_bundle or _artifact_snapshot()
    if bundle is None:
        raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")
    preprocessor = bundle.get("preprocessor")
    if preprocessor is None:
        raise HTTPException(status_code=503, detail="Model artifact does not include preprocessor.")
    transformed = preprocessor.transform_dataframe(pd.DataFrame([record]), fit=False)
    return _sanitize_input_array(transformed.values)


def _preprocess_array(feature_array: np.ndarray, artifact_bundle: Optional[dict] = None) -> np.ndarray:
    bundle = artifact_bundle or _artifact_snapshot()
    if bundle is None:
        raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")

    try:
        scaled = bundle["scaler"].transform(feature_array)
    except ValueError:
        # Retry once with stricter sanitization to avoid 500 on bad rows.
        safe = _sanitize_input_array(feature_array)
        try:
            scaled = bundle["scaler"].transform(safe)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid numeric range in input features: {exc}",
            ) from exc

    selected = bundle["selector"].transform(scaled)
    return selected


def _predict_array(selected_array: np.ndarray, artifact_bundle: Optional[dict] = None) -> Dict[str, Any]:
    bundle = artifact_bundle or _artifact_snapshot()
    if bundle is None:
        raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")

    prediction = bundle["model"].predict(selected_array)
    if hasattr(bundle["model"], "predict_proba"):
        probabilities = bundle["model"].predict_proba(selected_array)
        confidence = float(np.max(probabilities[0]))
    else:
        probabilities = None
        confidence = 0.5

    predicted_int = int(prediction[0])
    label = _reverse_label_mapping(bundle).get(predicted_int, str(predicted_int))
    return {
        "prediction": predicted_int,
        "prediction_label": label,
        "attack_type": str(label).upper(),
        "confidence": confidence,
        "is_attack": _is_attack_label(label),
        "probabilities": probabilities[0].tolist() if probabilities is not None else None,
=======
﻿import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.model_artifacts import DEFAULT_ARTIFACT_NAME, load_artifacts
from src.preprocess import Preprocessor

artifacts = None


class PredictionRequest(BaseModel):
    features: list[float]


def get_artifact_path() -> Path:
    return Path(os.getenv("MODEL_ARTIFACT_PATH", f"data/models/{DEFAULT_ARTIFACT_NAME}"))


def reverse_label_mapping():
    if not artifacts:
        return {}
    mapping = artifacts.get("label_mapping") or {}
    return {value: key for key, value in mapping.items()}


def predict_array(feature_array: np.ndarray):
    if artifacts is None:
        raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")

    expected_features = len(artifacts["feature_columns"])
    if feature_array.shape[1] != expected_features:
        raise HTTPException(
            status_code=422,
            detail=f"Expected {expected_features} features, got {feature_array.shape[1]}.",
        )

    scaled = artifacts["scaler"].transform(feature_array)
    selected = artifacts["selector"].transform(scaled)
    prediction = artifacts["model"].predict(selected)
    probabilities = artifacts["model"].predict_proba(selected)[0]
    confidence = float(np.max(probabilities))
    label = reverse_label_mapping().get(int(prediction[0]), str(int(prediction[0])))

    return {
        "prediction": int(prediction[0]),
        "prediction_label": label,
        "confidence": confidence,
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
        "timestamp": datetime.now(UTC).isoformat(),
    }


<<<<<<< HEAD
def _rule_only_predict(feature_dict: Dict[str, Any]) -> Dict[str, Any]:
    result = rule_engine.detect(feature_dict)
    label = result.attack_type if result.is_attack else "NORMAL"
    return {
        "prediction": 1 if result.is_attack else 0,
        "prediction_label": label,
        "attack_type": label,
        "confidence": float(result.confidence),
        "is_attack": bool(result.is_attack),
        "probabilities": None,
        "timestamp": datetime.now(UTC).isoformat(),
        "rule_result": result,
    }


def _build_explanation(prediction: Dict[str, Any], feature_dict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    pseudo_result = SimpleNamespace(
        attack_type=prediction.get("attack_type", "NORMAL"),
        is_attack=prediction.get("is_attack", False),
        confidence=float(prediction.get("confidence", 0.0)),
        rule_result=prediction.get("rule_result"),
        ml_result={
            "attack_type": prediction.get("attack_type", "NORMAL"),
            "confidence": prediction.get("confidence", 0.0),
        },
        fusion_strategy="api",
    )
    explained = explainer.explain(pseudo_result, features=feature_dict)
    return {
        "attack_type": explained.attack_type,
        "severity": explained.severity,
        "summary": explained.summary,
        "details": explained.details,
        "recommendations": explained.recommendations,
        "technical_details": explained.technical_details,
    }


def _build_request_geo_context(request: Request) -> Dict[str, Any]:
    client_ip = extract_client_ip(
        headers=request.headers,
        fallback_host=request.client.host if request.client is not None else None,
    )
    return {"client_ip": client_ip, "geo": resolve_ip_geo(client_ip)}


def _build_websocket_geo_context(websocket: WebSocket) -> Dict[str, Any]:
    client_ip = extract_client_ip(
        headers=websocket.headers,
        fallback_host=websocket.client.host if websocket.client is not None else None,
    )
    return {"client_ip": client_ip, "geo": resolve_ip_geo(client_ip)}


def _predict_single(features: Optional[List[float] | Dict[str, Any]], record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    artifact_bundle = _artifact_snapshot()
    feature_dict: Optional[Dict[str, Any]] = None

    if record is not None:
        feature_dict = _coerce_float_dict(record)
        if artifact_bundle is not None:
            arr = _extract_array_from_record(record, artifact_bundle)
            selected = _preprocess_array(arr, artifact_bundle)
            result = _predict_array(selected, artifact_bundle)
        elif ALLOW_RULE_ONLY_FALLBACK:
            result = _rule_only_predict(record)
        else:
            raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")
    elif features is not None:
        if isinstance(features, dict):
            feature_dict = _coerce_float_dict(features)
        if artifact_bundle is not None:
            arr = _extract_array_from_features(features, artifact_bundle)
            selected = _preprocess_array(arr, artifact_bundle)
            result = _predict_array(selected, artifact_bundle)
        elif isinstance(features, dict) and ALLOW_RULE_ONLY_FALLBACK:
            result = _rule_only_predict(features)
        else:
            raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")
    else:
        raise HTTPException(status_code=422, detail="Provide either `features` or `record`.")

    # Always attach rule evidence when available.
    if feature_dict:
        rule_result = rule_engine.detect(feature_dict)
        result["rule_result"] = rule_result

    result["explanation"] = _build_explanation(result, feature_dict)
    return result


def _read_artifact_mtime(path: Path) -> Optional[float]:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return None


def load_models(force: bool = False) -> bool:
    global artifacts, artifact_mtime
    path = get_artifact_path()
    current_mtime = _read_artifact_mtime(path)
    if not force and artifact_mtime is not None and current_mtime is not None and current_mtime <= artifact_mtime:
        return False

    if not path.exists():
        return False

    try:
        loaded_artifacts = load_artifacts(path)
    except Exception:
        return False

    if not is_runnable_artifact(loaded_artifacts):
        typo_latest = Path("data/models/model_artifacts_lastest.pkl")
        legacy = Path(f"data/models/{LEGACY_ARTIFACT_NAME}")
        if typo_latest != path and typo_latest.exists():
            try:
                typo_artifacts = load_artifacts(typo_latest)
                if is_runnable_artifact(typo_artifacts):
                    loaded_artifacts = typo_artifacts
                    path = typo_latest
                    current_mtime = _read_artifact_mtime(path)
            except Exception:
                pass
        if not is_runnable_artifact(loaded_artifacts) and legacy != path and legacy.exists():
            try:
                legacy_artifacts = load_artifacts(legacy)
                if is_runnable_artifact(legacy_artifacts):
                    loaded_artifacts = legacy_artifacts
                    path = legacy
                    current_mtime = _read_artifact_mtime(path)
            except Exception:
                pass
        if not is_runnable_artifact(loaded_artifacts):
            return False

    with artifacts_lock:
        artifacts = loaded_artifacts
        artifact_mtime = current_mtime
    return True


def reload_model_artifacts() -> Dict[str, Any]:
    changed = load_models(force=True)
    return {
        "reloaded": changed,
        "model_loaded": artifacts is not None,
        "artifact_path": str(get_artifact_path()),
        "artifact_mtime": artifact_mtime,
    }


def _artifact_watch_loop(poll_interval: float = 5.0) -> None:
    while not artifact_watch_stop.wait(max(1.0, poll_interval)):
        try:
            load_models(force=False)
        except Exception:
            continue


@asynccontextmanager
async def lifespan(_: FastAPI):
    global artifact_watch_thread, alert_manager
    load_models(force=True)
    alert_manager = reload_alert_manager()
    artifact_watch_stop.clear()
    artifact_watch_thread = threading.Thread(
        target=_artifact_watch_loop,
        kwargs={"poll_interval": float(os.getenv("MODEL_WATCH_INTERVAL", "5"))},
        daemon=True,
        name="artifact-watchdog",
    )
    artifact_watch_thread.start()
    yield
    artifact_watch_stop.set()
    if artifact_watch_thread is not None and artifact_watch_thread.is_alive():
        artifact_watch_thread.join(timeout=2.0)

# ==================== CORS 配置（新增） ====================
# 开发阶段推荐允许所有来源，生产环境建议改成具体域名
origins = [
    "*",                    # 开发时用 "*" 最方便（允许任意前端）
    # "http://localhost:3000",      # 如果前端是 React/Vue 等本地开发
    # "http://127.0.0.1:8080",
    # "https://你的前端域名.com",   # 生产时改为具体地址
]

app = FastAPI(
    title="网络安全态势感知系统 API",
    description="融合规则检测、模型推理和可解释输出的攻击检测服务",
    version="4.1.0",
    lifespan=lifespan,
)
# 添加 CORS 中间件（必须在 include_router 和定义路由之前）
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           # 允许的源
    allow_credentials=True,          # 允许携带 cookies / Authorization 等凭证
    allow_methods=["*"],             # 允许所有 HTTP 方法（GET, POST, OPTIONS 等）
    allow_headers=["*"],             # 允许所有请求头
    expose_headers=["*"],            # 可选：允许前端访问自定义响应头
    allow_origin_regex=".*",   # 👈 只加这一行
    max_age=3600,                    # 可选：预检请求缓存 1 小时
)
app.include_router(extra_router, prefix="/api", tags=["explain"])


# @app.get("/")
# def root(request: Request) -> Any:
#     accept = request.headers.get("accept", "")
#     if "text/html" in accept:
#         return HTMLResponse(_dashboard_html())
#     bundle = _artifact_snapshot()
#     return {
#         "name": "网络安全态势感知系统",
#         "version": "4.1.0",
#         "model_loaded": bundle is not None,
#         "artifact_path": str(get_artifact_path()),
#         "dashboard_ui": "/",
#     }
# 强制返回HTML，带正确响应头，浏览器100%识别
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return HTMLResponse(
        content=_dashboard_html(),
        media_type="text/html; charset=utf-8"
    )

@app.get("/health", tags=["health"])
def health() -> Dict[str, Any]:
    bundle = _artifact_snapshot()
    registry = _registry_snapshot()
    return {
        "status": "ok" if bundle else "rule_only",
        "model_loaded": bundle is not None,
        "artifact_path": str(get_artifact_path()),
        "feature_count": len(bundle.get("feature_columns", [])) if bundle else 0,
        "artifact_mtime": artifact_mtime,
        "watcher_enabled": True,
        "registry_path": registry["registry_path"],
        "registry_count": registry["entry_count"],
        "active_model_path": registry["active_entry"].get("artifact_path") if registry["active_entry"] else None,
    }


@app.get("/metadata", tags=["model"])
def metadata() -> Dict[str, Any]:
    bundle = _artifact_snapshot()
    if bundle is None:
        raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")
    registry = _registry_snapshot()
    return {
        "feature_columns": bundle.get("feature_columns", []),
        "label_mapping": bundle.get("label_mapping", {}),
        "metrics": {k: v for k, v in (bundle.get("metrics") or {}).items() if k != "report"},
        "artifact_metadata": bundle.get("metadata", {}),
        "registry": registry,
    }


@app.post("/admin/reload-model", tags=["admin"])
def admin_reload_model() -> Dict[str, Any]:
    return reload_model_artifacts()


@app.post("/admin/reset-events", tags=["admin"])
def admin_reset_events(archive: bool = Query(default=True)) -> Dict[str, Any]:
    return reset_detection_history(archive=archive)


@app.get("/dashboard", tags=["dashboard"])
def dashboard(request: Request, limit: int = Query(default=50, ge=1, le=1000000000)) -> Any:
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return HTMLResponse(_dashboard_html())
    events = load_recent_events(limit=limit)
    return {"summary": load_summary(), "events": events, "count": len(events)}


@app.get("/dashboard/summary", tags=["dashboard"])
def dashboard_summary() -> Dict[str, Any]:
    return load_summary()


@app.get("/dashboard/events", tags=["dashboard"])
def dashboard_events(limit: int = Query(default=100, ge=1, le=1000000000)) -> Dict[str, Any]:
    events = load_recent_events(limit=limit)
    return {"events": events, "count": len(events)}


@app.get("/dashboard/events/delta", tags=["dashboard"])
def dashboard_events_delta(
    cursor: Optional[str] = Query(default=None, description="Cursor token: '<timestamp>|<event_uid>'"),
    limit: int = Query(default=100, ge=1, le=1000000000),
) -> Dict[str, Any]:
    payload = load_events_delta(cursor=cursor, limit=limit)
    return {
        "events": payload["events"],
        "count": len(payload["events"]),
        "cursor": payload["cursor"],
        "summary": load_summary(),
    }


@app.get("/stream/events", tags=["dashboard"])
async def stream_events(
    cursor: Optional[str] = Query(default=None, description="Cursor token from /dashboard/events/delta"),
    limit: int = Query(default=100, ge=1, le=1000000000),
    interval_ms: int = Query(default=200, ge=50, le=5000),
    heartbeat_ms: int = Query(default=2000, ge=500, le=10000),
) -> StreamingResponse:
    def _to_sse_data(payload: Dict[str, Any]) -> str:
        # Use default=str so unexpected objects never crash the stream loop.
        return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

    async def _event_generator():
        local_cursor = cursor
        heartbeat_every = max(0.5, heartbeat_ms / 1000.0)
        last_heartbeat = time.monotonic()
        while True:
            try:
                payload = load_events_delta(cursor=local_cursor, limit=limit)
                events = payload.get("events", [])
                local_cursor = payload.get("cursor", local_cursor)

                if events:
                    message = {
                        "type": "delta",
                        "events": events,
                        "cursor": local_cursor,
                        "summary": load_summary(),
                    }
                    yield _to_sse_data(message)
                    last_heartbeat = time.monotonic()
                elif time.monotonic() - last_heartbeat >= heartbeat_every:
                    # Use a normal data frame heartbeat for broader frontend compatibility.
                    yield _to_sse_data({"type": "ping", "cursor": local_cursor})
                    last_heartbeat = time.monotonic()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover
                # Keep SSE channel alive on transient serializer/data errors.
                yield _to_sse_data({"type": "error", "message": str(exc)})

            await asyncio.sleep(max(0.05, interval_ms / 1000.0))

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Type": "text/event-stream; charset=utf-8",
    }
    return StreamingResponse(_event_generator(), headers=headers)


@app.websocket("/ws/stream")
async def websocket_stream(
    websocket: WebSocket,
):
    await websocket.accept()
    cursor: Optional[str] = None
    interval = max(0.05, float(websocket.query_params.get("interval_ms", "200")) / 1000.0)
    limit = int(websocket.query_params.get("limit", "100"))
    limit = min(max(limit, 1), 1000000000)

    try:
        while True:
            payload = load_events_delta(cursor=cursor, limit=limit)
            events = payload.get("events", [])
            cursor = payload.get("cursor", cursor)
            if events:
                await websocket.send_json(
                    {
                        "type": "delta",
                        "events": events,
                        "cursor": cursor,
                        "summary": load_summary(),
                    }
                )
            else:
                await websocket.send_json({"type": "ping", "cursor": cursor})
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        return


@app.post("/predict", tags=["predict"])
def predict(request: PredictionRequest, raw_request: Request) -> Dict[str, Any]:
    geo_context = _build_request_geo_context(raw_request)
    dynamic_metrics = _extract_dynamic_metrics(request.features, request.record)
    result = _predict_single(request.features, request.record)
    result.update(dynamic_metrics)
    event = log_detection(
        result,
        source=request.source,
        input_kind="record" if request.record is not None else "features",
        client_ip=geo_context["client_ip"],
        geo=geo_context["geo"],
        dynamic_metrics=dynamic_metrics,
    )
    return {**result, "event": event}


@app.post("/predict/batch", tags=["predict"])
@app.post("/batch", tags=["predict"])
async def batch_predict(raw_request: Request, file: UploadFile = File(...), source: str = "batch_upload") -> Dict[str, Any]:
    geo_context = _build_request_geo_context(raw_request)
    content = await file.read()
    try:
        frame = pd.read_csv(io.BytesIO(content), low_memory=False)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"CSV parsing failed: {exc}") from exc

    rows: List[Dict[str, Any]] = []
    event_records: List[Dict[str, Any]] = []
    for index, row in frame.iterrows():
        row_dict = row.to_dict()
        try:
            result = _predict_single(features=row_dict, record=None)
            dynamic_metrics = _extract_dynamic_metrics(features=row_dict, record=None)
            result.update(dynamic_metrics)
            result["index"] = int(index)
            event = log_detection(
                result,
                source=source,
                input_kind="csv_row",
                alert=False,
                client_ip=geo_context["client_ip"],
                geo=geo_context["geo"],
                dynamic_metrics=dynamic_metrics,
            )
            result["event"] = event
            event_records.append(event)
            rows.append(result)
        except HTTPException as exc:
            rows.append({"index": int(index), "error": exc.detail})

    batch_alert = None
    if event_records:
        batch_alert = alert_manager.notify_batch(events=event_records, summary=load_summary(), source=source)
        if isinstance(batch_alert, dict):
            batch_alert["source"] = source

    return {
        "total": len(rows),
        "predictions": rows,
        "dashboard_summary": load_summary(),
        "batch_alert": batch_alert,
    }
=======
def load_models():
    global artifacts
    artifact_path = get_artifact_path()
    if artifact_path.exists():
        artifacts = load_artifacts(artifact_path)
    else:
        artifacts = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_models()
    yield


app = FastAPI(title="DDoS Detection API", version="2.0", lifespan=lifespan)


@app.get("/health")
def health():
    feature_count = len(artifacts["feature_columns"]) if artifacts else 0
    return {
        "status": "ok" if artifacts else "missing_model",
        "model_loaded": artifacts is not None,
        "artifact_path": str(get_artifact_path()),
        "feature_count": feature_count,
    }


@app.get("/metadata")
def metadata():
    if artifacts is None:
        raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")
    return {
        "feature_columns": artifacts["feature_columns"],
        "label_mapping": artifacts.get("label_mapping", {}),
        "metrics": {key: value for key, value in artifacts.get("metrics", {}).items() if key != "report"},
    }


@app.post("/predict")
def predict(request: PredictionRequest):
    feature_array = np.asarray(request.features, dtype=float).reshape(1, -1)
    return predict_array(feature_array)


@app.post("/predict/batch")
async def predict_batch(file: UploadFile = File(...)):
    if artifacts is None:
        raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")

    content = await file.read()
    df = pd.read_csv(pd.io.common.BytesIO(content), low_memory=False)
    preprocessor = Preprocessor()
    df = preprocessor.clean(df)

    missing_columns = sorted(set(artifacts["feature_columns"]) - set(df.columns))
    if missing_columns:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required feature columns: {missing_columns[:10]}",
        )

    feature_frame = df[artifacts["feature_columns"]].copy()
    for column in feature_frame.columns:
        feature_frame[column] = pd.to_numeric(feature_frame[column], errors="coerce")
    feature_frame = feature_frame.fillna(feature_frame.median(numeric_only=True)).fillna(0.0)

    scaled = artifacts["scaler"].transform(feature_frame.values)
    selected = artifacts["selector"].transform(scaled)
    predictions = artifacts["model"].predict(selected)
    probabilities = artifacts["model"].predict_proba(selected).max(axis=1)
    label_map = reverse_label_mapping()

    results = []
    for index, (prediction, confidence) in enumerate(zip(predictions, probabilities)):
        results.append(
            {
                "index": index,
                "prediction": int(prediction),
                "prediction_label": label_map.get(int(prediction), str(int(prediction))),
                "confidence": float(confidence),
            }
        )

    return {"total": len(results), "predictions": results}
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
<<<<<<< HEAD
    geo_context = _build_websocket_geo_context(websocket)
    stream_mode = str(websocket.query_params.get("stream", "0")).strip().lower() in {"1", "true", "yes"}
    poll_interval = max(0.05, float(websocket.query_params.get("interval_ms", "500")) / 1000.0)
    limit = int(websocket.query_params.get("limit", "1000000000"))
    limit = min(max(limit, 1), 1000000000)
    cursor: Optional[str] = None
    try:
        while True:
            if stream_mode:
                payload = load_events_delta(cursor=cursor, limit=limit)
                events = payload.get("events", [])
                cursor = payload.get("cursor", cursor)
                if events:
                    await websocket.send_json(
                        {
                            "type": "delta",
                            "events": events,
                            "cursor": cursor,
                            "summary": load_summary(),
                        }
                    )
                else:
                    await websocket.send_json({"type": "ping", "cursor": cursor})
                await asyncio.sleep(poll_interval)
                continue

            try:
                payload = await asyncio.wait_for(websocket.receive_json(), timeout=15.0)
            except TimeoutError:
                await websocket.send_json({"type": "ping", "summary": load_summary()})
                continue

            source = str(payload.get("source", "websocket"))
            try:
                result = _predict_single(payload.get("features"), payload.get("record"))
                dynamic_metrics = _extract_dynamic_metrics(payload.get("features"), payload.get("record"))
                result.update(dynamic_metrics)
                event = log_detection(
                    result,
                    source=source,
                    input_kind="record" if payload.get("record") is not None else "features",
                    client_ip=geo_context["client_ip"],
                    geo=geo_context["geo"],
                    dynamic_metrics=dynamic_metrics,
                )
                await websocket.send_json({**result, "event": event, "dashboard_summary": load_summary()})
            except HTTPException as exc:
                await websocket.send_json({"error": exc.detail})
            except Exception as exc:  # pragma: no cover
                await websocket.send_json({"error": f"Unexpected server error: {exc}"})
    except WebSocketDisconnect:
        return
=======
    try:
        while True:
            payload = await websocket.receive_json()
            features = payload.get("features")
            if features is None:
                await websocket.send_json({"error": "Missing features"})
                continue
            try:
                feature_array = np.asarray(features, dtype=float).reshape(1, -1)
                await websocket.send_json(predict_array(feature_array))
            except HTTPException as exc:
                await websocket.send_json({"error": exc.detail})
    except WebSocketDisconnect:
        return
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
