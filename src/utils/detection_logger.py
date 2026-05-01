"""Detection logging utilities."""

from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RESULTS_DIR = Path("results/realtime")
EVENTS_JSONL = RESULTS_DIR / "detections.jsonl"
RECENT_EVENTS_JSON = RESULTS_DIR / "latest_events.json"
SUMMARY_JSON = RESULTS_DIR / "summary.json"
TIMELINE_CSV = RESULTS_DIR / "attack_timeline.csv"
MAX_RECENT_EVENTS = int(os.getenv("MAX_RECENT_EVENTS", 1000000000))
BENIGN_LABELS = {"benign", "normal", "0"}
_CACHE_LOCK = threading.RLock()
_RECENT_EVENTS_CACHE: Optional[deque] = None
_SUMMARY_CACHE: Optional[Dict[str, Any]] = None


def ensure_results_dir() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _build_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    attack_total = sum(1 for event in events if event["is_attack"])
    benign_total = len(events) - attack_total
    label_counter = Counter(event["prediction_label"] for event in events)
    source_counter = Counter(event.get("source", "unknown") for event in events)
    return {
        "total_events": len(events),
        "attack_events": attack_total,
        "benign_events": benign_total,
        "attack_ratio": (attack_total / len(events)) if events else 0.0,
        "labels": dict(label_counter),
        "sources": dict(source_counter),
        "last_event": events[-1] if events else None,
    }


def _ensure_cache_loaded() -> None:
    global _RECENT_EVENTS_CACHE, _SUMMARY_CACHE
    with _CACHE_LOCK:
        if _RECENT_EVENTS_CACHE is not None and _SUMMARY_CACHE is not None:
            return

        if RECENT_EVENTS_JSON.exists():
            try:
                data = json.loads(RECENT_EVENTS_JSON.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    data = []
            except json.JSONDecodeError:
                data = []
        else:
            data = []

        _RECENT_EVENTS_CACHE = deque(data[-MAX_RECENT_EVENTS:], maxlen=MAX_RECENT_EVENTS)
        _SUMMARY_CACHE = _build_summary(list(_RECENT_EVENTS_CACHE))


def is_attack_label(label: str) -> bool:
    return str(label).strip().lower() not in BENIGN_LABELS


def confidence_to_severity(confidence: float, attack: bool) -> str:
    if not attack:
        return "info"
    if confidence >= 0.95:
        return "critical"
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"


def load_recent_events(limit: int = MAX_RECENT_EVENTS) -> List[Dict[str, Any]]:
    _ensure_cache_loaded()
    with _CACHE_LOCK:
        cached = list(_RECENT_EVENTS_CACHE or [])
    return cached[-limit:]


def _event_cursor(event: Dict[str, Any]) -> str:
    return f"{event.get('timestamp', '')}|{event.get('event_uid', '')}"


def load_events_delta(cursor: Optional[str], limit: int = MAX_RECENT_EVENTS) -> Dict[str, Any]:
    """Return events newer than a cursor token: '<iso_timestamp>|<event_uid>'."""
    events = load_recent_events(limit=MAX_RECENT_EVENTS)
    if not cursor:
        sliced = events[-limit:]
        next_cursor = _event_cursor(sliced[-1]) if sliced else ""
        return {"events": sliced, "cursor": next_cursor}

    since_ts, _, since_uid = str(cursor).partition("|")
    out: List[Dict[str, Any]] = []
    for event in events:
        ts = str(event.get("timestamp", ""))
        uid = str(event.get("event_uid", ""))
        if ts > since_ts or (ts == since_ts and uid > since_uid):
            out.append(event)
    if len(out) > limit:
        out = out[-limit:]
    next_cursor = _event_cursor(out[-1]) if out else cursor
    return {"events": out, "cursor": next_cursor}


def write_recent_events(events: List[Dict[str, Any]]) -> None:
    global _RECENT_EVENTS_CACHE
    with _CACHE_LOCK:
        _RECENT_EVENTS_CACHE = deque(events[-MAX_RECENT_EVENTS:], maxlen=MAX_RECENT_EVENTS)
        RECENT_EVENTS_JSON.write_text(
            json.dumps(list(_RECENT_EVENTS_CACHE), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def write_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    global _SUMMARY_CACHE
    summary = _build_summary(events)
    with _CACHE_LOCK:
        _SUMMARY_CACHE = summary
        SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def append_timeline_row(event: Dict[str, Any]) -> None:
    header = "timestamp,prediction_label,confidence,is_attack,severity,source\n"
    row = (
        f"{event['timestamp']},{event['prediction_label']},"
        f"{event['confidence']:.6f},{int(event['is_attack'])},"
        f"{event['severity']},{event.get('source', 'unknown')}\n"
    )
    if not TIMELINE_CSV.exists():
        TIMELINE_CSV.write_text(header + row, encoding="utf-8")
    else:
        with TIMELINE_CSV.open("a", encoding="utf-8") as handle:
            handle.write(row)


def _send_alert_if_enabled(event: Dict[str, Any], result: Dict[str, Any], source: str, input_kind: str):
    try:
        from src.utils.alert import get_alert_manager
    except Exception as exc:  # pragma: no cover
        return {"enabled": False, "sent": False, "error": str(exc)}

    manager = get_alert_manager()
    if not manager.enabled:
        return {"enabled": False, "sent": False, "reason": "alerting_disabled"}
    try:
        return manager.notify_detection(event=event, result=result, source=source, input_kind=input_kind)
    except Exception as exc:  # pragma: no cover
        return {"enabled": True, "sent": False, "error": str(exc)}


def log_detection(
    result: Dict[str, Any],
    *,
    source: str = "api",
    input_kind: str = "features",
    alert: bool = True,
    client_ip: Optional[str] = None,
    geo: Optional[Dict[str, Any]] = None,
    dynamic_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist a detection event and optionally trigger alerts."""
    global _RECENT_EVENTS_CACHE
    ensure_results_dir()

    label = str(result.get("prediction_label", result.get("prediction", "unknown")))
    attack = is_attack_label(label)
    event = {
        "event_uid": uuid.uuid4().hex[:16],
        "timestamp": result["timestamp"],
        "prediction": int(result["prediction"]),
        "prediction_label": label,
        "confidence": float(result["confidence"]),
        "is_attack": attack,
        "severity": confidence_to_severity(float(result["confidence"]), attack),
        "source": source,
        "input_kind": input_kind,
    }
    if client_ip:
        event["client_ip"] = str(client_ip)
    if geo is not None:
        event["geo"] = geo
    if dynamic_metrics is not None:
        for key in ("pkt_len", "syn_count", "udp_count"):
            if key in dynamic_metrics:
                event[key] = dynamic_metrics.get(key)

    with EVENTS_JSONL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    _ensure_cache_loaded()
    with _CACHE_LOCK:
        if _RECENT_EVENTS_CACHE is None:
            _RECENT_EVENTS_CACHE = deque(maxlen=MAX_RECENT_EVENTS)
        _RECENT_EVENTS_CACHE.append(event)
        recent_events_list = list(_RECENT_EVENTS_CACHE)
        RECENT_EVENTS_JSON.write_text(
            json.dumps(recent_events_list, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    write_summary(recent_events_list)
    append_timeline_row(event)

    if alert and attack:
        event["alert"] = _send_alert_if_enabled(event, result, source, input_kind)
    else:
        event["alert"] = {"enabled": False, "sent": False}

    return event


def load_summary() -> Dict[str, Any]:
    _ensure_cache_loaded()
    with _CACHE_LOCK:
        if _SUMMARY_CACHE is not None:
            return dict(_SUMMARY_CACHE)

    if not SUMMARY_JSON.exists():
        return _build_summary([])
    return json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))


def reset_detection_history(archive: bool = True) -> Dict[str, Any]:
    """Reset realtime detection files, optionally archiving existing records."""
    global _RECENT_EVENTS_CACHE, _SUMMARY_CACHE
    ensure_results_dir()

    files = [EVENTS_JSONL, RECENT_EVENTS_JSON, SUMMARY_JSON, TIMELINE_CSV]
    archived_files: List[str] = []
    removed_files: List[str] = []
    clear_errors: List[str] = []
    archive_dir: Optional[Path] = None

    if archive:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_dir = RESULTS_DIR / "archive" / timestamp
        archive_dir.mkdir(parents=True, exist_ok=True)

    for src in files:
        if not src.exists() or not archive or archive_dir is None:
            continue
        try:
            target = archive_dir / src.name
            shutil.copy2(str(src), str(target))
            archived_files.append(str(target))
        except OSError as exc:
            clear_errors.append(f"archive_failed:{src}:{exc}")

    try:
        EVENTS_JSONL.write_text("", encoding="utf-8")
        removed_files.append(str(EVENTS_JSONL))
    except OSError as exc:
        clear_errors.append(f"clear_failed:{EVENTS_JSONL}:{exc}")

    try:
        write_recent_events([])
        removed_files.append(str(RECENT_EVENTS_JSON))
    except OSError as exc:
        clear_errors.append(f"clear_failed:{RECENT_EVENTS_JSON}:{exc}")

    try:
        TIMELINE_CSV.write_text("timestamp,prediction_label,confidence,is_attack,severity,source\n", encoding="utf-8")
        removed_files.append(str(TIMELINE_CSV))
    except OSError as exc:
        clear_errors.append(f"clear_failed:{TIMELINE_CSV}:{exc}")

    try:
        summary = write_summary([])
        removed_files.append(str(SUMMARY_JSON))
    except OSError as exc:
        clear_errors.append(f"clear_failed:{SUMMARY_JSON}:{exc}")
        summary = load_summary()

    with _CACHE_LOCK:
        _RECENT_EVENTS_CACHE = deque([], maxlen=MAX_RECENT_EVENTS)
        _SUMMARY_CACHE = _build_summary([])

    return {
        "reset": True,
        "archive_enabled": bool(archive),
        "archive_dir": str(archive_dir) if archive_dir else None,
        "archived_files": archived_files,
        "removed_files": removed_files,
        "clear_errors": clear_errors,
        "summary": summary,
    }
