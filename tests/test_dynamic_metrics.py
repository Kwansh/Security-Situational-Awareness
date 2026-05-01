"""Tests for dynamic metric extraction from CSV-like records."""

from src.api.server import _extract_dynamic_metrics


def test_extract_dynamic_metrics_from_common_aliases():
    row = {
        "avg_pkt_size": "512",
        "SYN Flag Count": "33",
        "udp_rate": 120,
    }
    metrics = _extract_dynamic_metrics(features=row, record=None)
    assert metrics["pkt_len"] == 512.0
    assert metrics["syn_count"] == 33.0
    assert metrics["udp_count"] == 120.0


def test_extract_dynamic_metrics_prefers_record_payload():
    features = {"avg_pkt_size": 999}
    record = {"packet_length_mean": 100, "syn_rate": 8, "udp_count": 12}
    metrics = _extract_dynamic_metrics(features=features, record=record)
    assert metrics == {"pkt_len": 100.0, "syn_count": 8.0, "udp_count": 12.0}


def test_extract_dynamic_metrics_derives_udp_per_minute_from_protocol_and_rate():
    row = {
        "Protocol": 17,
        "Flow Packets/s": 2.5,
        "Packet Length Mean": 400,
    }
    metrics = _extract_dynamic_metrics(features=row, record=None)
    assert metrics["pkt_len"] == 400.0
    assert metrics["udp_count"] == 150.0


def test_extract_dynamic_metrics_derives_syn_per_second_from_duration():
    row = {
        "SYN Flag Count": 3,
        "Flow Duration": 1_500_000,  # microseconds
        "Packet Length Mean": 500,
    }
    metrics = _extract_dynamic_metrics(features=row, record=None)
    assert metrics["pkt_len"] == 500.0
    assert metrics["syn_count"] == 2.0
    assert metrics["udp_count"] == 0.0


def test_extract_dynamic_metrics_falls_back_to_tcp_flow_rate_when_syn_flags_zero():
    row = {
        "Protocol": 6,
        "SYN Flag Count": 0,
        "Flow Packets/s": 123.45,
        "Packet Length Mean": 321,
    }
    metrics = _extract_dynamic_metrics(features=row, record=None)
    assert metrics["pkt_len"] == 321.0
    assert metrics["syn_count"] == 123.45
    assert metrics["udp_count"] == 0.0
