"""Unit tests for client IP and geo resolution helpers."""

from __future__ import annotations

from src.utils import ip_geo


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_extract_client_ip_prefers_forwarded_header():
    headers = {
        "X-Forwarded-For": "8.8.8.8, 10.0.0.3",
        "X-Real-IP": "1.1.1.1",
    }
    assert ip_geo.extract_client_ip(headers) == "8.8.8.8"


def test_extract_client_ip_fallback_to_host():
    assert ip_geo.extract_client_ip({}, fallback_host="127.0.0.1") == "127.0.0.1"


def test_resolve_ip_geo_private_ip_skips_lookup(monkeypatch):
    called = {"count": 0}

    def _never_called(*args, **kwargs):
        called["count"] += 1
        raise AssertionError("httpx.get should not be called for non-public IP")

    monkeypatch.setattr(ip_geo, "_IP_GEO_ENABLED", True)
    monkeypatch.setattr(ip_geo.httpx, "get", _never_called)

    result = ip_geo.resolve_ip_geo("127.0.0.1")
    assert result["resolved"] is False
    assert result["reason"] == "non_public_ip"
    assert called["count"] == 0


def test_resolve_ip_geo_public_ip_and_cache(monkeypatch):
    with ip_geo._CACHE_LOCK:
        ip_geo._GEO_CACHE.clear()

    called = {"count": 0}

    def _fake_get(*args, **kwargs):
        called["count"] += 1
        return _FakeResponse(
            200,
            {
                "latitude": 37.386,
                "longitude": -122.0838,
                "city": "Mountain View",
                "region": "California",
                "country_name": "United States",
                "country_code": "US",
                "timezone": "America/Los_Angeles",
            },
        )

    monkeypatch.setattr(ip_geo, "_IP_GEO_ENABLED", True)
    monkeypatch.setattr(ip_geo.httpx, "get", _fake_get)

    first = ip_geo.resolve_ip_geo("8.8.8.8")
    second = ip_geo.resolve_ip_geo("8.8.8.8")

    assert first["resolved"] is True
    assert first["city"] == "Mountain View"
    assert second["resolved"] is True
    assert called["count"] == 1
