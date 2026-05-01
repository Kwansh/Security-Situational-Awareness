"""Client IP extraction and geolocation helpers."""

from __future__ import annotations

import ipaddress
import os
import threading
import time
from typing import Any, Dict, Iterable, Mapping, Optional

import httpx

_IPAPI_BASE = os.getenv("IP_GEO_API_BASE", "https://ipapi.co").rstrip("/")
_IPAPI_TIMEOUT = float(os.getenv("IP_GEO_API_TIMEOUT", "2.0"))
_GEO_CACHE_TTL_SECONDS = int(os.getenv("IP_GEO_CACHE_TTL_SECONDS", "21600"))
_IP_GEO_ENABLED = os.getenv("IP_GEO_ENABLED", "1").strip().lower() in {"1", "true", "yes"}
_GEO_PROVIDER = "ipapi.co"
_DEFAULT_HEADERS = {"User-Agent": "security-situational-awareness/geo-ip"}

_IP_HEADERS_ORDER = (
    "cf-connecting-ip",
    "true-client-ip",
    "x-forwarded-for",
    "x-real-ip",
    "x-client-ip",
    "x-original-forwarded-for",
    "forwarded",
)

_CACHE_LOCK = threading.RLock()
_GEO_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_ip(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = str(value).strip().strip('"').strip("'")
    if not candidate or candidate.lower() in {"unknown", "null", "none"}:
        return None

    # IPv4 with port (e.g. 203.0.113.5:1234)
    if candidate.count(":") == 1 and "." in candidate:
        candidate = candidate.split(":", 1)[0].strip()
    # Bracketed IPv6 with optional port (e.g. [2001:db8::1]:443)
    elif candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.find("]")]

    if "%" in candidate:
        candidate = candidate.split("%", 1)[0]

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _iter_forwarded_ips(value: str) -> Iterable[str]:
    # RFC 7239: Forwarded: for=192.0.2.60;proto=http;by=203.0.113.43
    for segment in value.split(","):
        for part in segment.split(";"):
            piece = part.strip()
            if not piece.lower().startswith("for="):
                continue
            raw = piece.split("=", 1)[1].strip().strip('"')
            yield raw


def _is_global_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


def extract_client_ip(headers: Mapping[str, str], fallback_host: Optional[str] = None) -> Optional[str]:
    lowered = {str(key).lower(): str(value) for key, value in headers.items()}
    for header in _IP_HEADERS_ORDER:
        raw = lowered.get(header)
        if not raw:
            continue
        if header == "x-forwarded-for":
            candidates = (part.strip() for part in raw.split(","))
        elif header == "forwarded":
            candidates = _iter_forwarded_ips(raw)
        else:
            candidates = (raw,)
        for candidate in candidates:
            normalized = _normalize_ip(candidate)
            if normalized:
                return normalized
    return _normalize_ip(fallback_host)


def _cache_get(ip: str) -> Optional[Dict[str, Any]]:
    with _CACHE_LOCK:
        cached = _GEO_CACHE.get(ip)
        if not cached:
            return None
        ts, payload = cached
        if time.time() - ts > _GEO_CACHE_TTL_SECONDS:
            _GEO_CACHE.pop(ip, None)
            return None
        return dict(payload)


def _cache_put(ip: str, payload: Dict[str, Any]) -> None:
    with _CACHE_LOCK:
        _GEO_CACHE[ip] = (time.time(), dict(payload))


def resolve_ip_geo(ip: Optional[str]) -> Dict[str, Any]:
    normalized_ip = _normalize_ip(ip)
    result: Dict[str, Any] = {
        "provider": _GEO_PROVIDER,
        "ip": normalized_ip or "",
        "resolved": False,
        "latitude": None,
        "longitude": None,
        "city": None,
        "region": None,
        "country": None,
        "country_code": None,
        "timezone": None,
    }

    if normalized_ip is None:
        result["reason"] = "missing_or_invalid_ip"
        return result
    if not _IP_GEO_ENABLED:
        result["reason"] = "geo_lookup_disabled"
        return result
    if not _is_global_ip(normalized_ip):
        result["reason"] = "non_public_ip"
        return result

    cached = _cache_get(normalized_ip)
    if cached is not None:
        return cached

    try:
        response = httpx.get(
            f"{_IPAPI_BASE}/{normalized_ip}/json/",
            timeout=_IPAPI_TIMEOUT,
            headers=_DEFAULT_HEADERS,
        )
    except Exception as exc:
        result["reason"] = f"lookup_failed:{exc.__class__.__name__}"
        return result

    if response.status_code != 200:
        result["reason"] = f"http_{response.status_code}"
        return result

    try:
        payload = response.json()
    except ValueError:
        result["reason"] = "invalid_json"
        return result

    if payload.get("error"):
        result["reason"] = str(payload.get("reason") or payload.get("message") or "provider_error")
        return result
    if payload.get("bogon"):
        result["reason"] = "bogon_ip"
        return result

    result.update(
        {
            "latitude": _as_float(payload.get("latitude")),
            "longitude": _as_float(payload.get("longitude")),
            "city": payload.get("city") or None,
            "region": payload.get("region") or None,
            "country": payload.get("country_name") or None,
            "country_code": payload.get("country_code") or None,
            "timezone": payload.get("timezone") or None,
        }
    )

    if result["latitude"] is None or result["longitude"] is None:
        result["reason"] = "coordinates_unavailable"
        return result

    result["resolved"] = True
    _cache_put(normalized_ip, result)
    return result

