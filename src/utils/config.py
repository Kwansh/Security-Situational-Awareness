"""Configuration utilities for the project."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge dictionaries without mutating inputs."""
    merged: Dict[str, Any] = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def get_default_config() -> Dict[str, Any]:
    """Return a safe default configuration."""
    return {
        "paths": {
            "data_dir": "data",
            "raw_dir": "data/raw",
            "processed_dir": "data/processed",
            "models_dir": "data/models",
            "results_dir": "results",
            "figures_dir": "results/figures",
        },
        "rule_thresholds": {
            "syn_flood_per_sec": 500,
            "udp_flood_per_min": 10000,
            "dns_flood_per_sec": 2000,
            "ntp_flood_per_min": 5000,
            "sql_injection_min_matches": 2,
        },
        "detection": {
            "mode": "hybrid",
            "fusion_strategy": "weighted",
            "rule_weight": 0.4,
            "ml_weight": 0.6,
            "confidence_threshold": 0.5,
        },
        "model_config": {
            "random_forest": {"n_estimators": 100, "max_depth": 10},
            "xgboost": {"n_estimators": 100, "max_depth": 6},
        },
        "ensemble_config": {
            "enabled": True,
            "method": "voting",
            "models": ["random_forest", "xgboost"],
            "voting": "soft",
        },
        "training": {
            "test_size": 0.2,
            "validation_size": 0.2,
            "random_state": 42,
            "scale_features": True,
            "max_rows_per_file": 200000,
            "max_files": None,
        },
        "online_learning": {
            "enabled": False,
            "stream_chunk_size": 50000,
            "buffer_rows": 200000,
            "hot_reload": True,
            "backup_on_update": True,
        },
        "alerting": {
            "enabled": False,
            "trigger_on_detection": True,
            "trigger_on_batch": True,
            "retries": 3,
            "retry_delay_seconds": 2,
            "timeout_seconds": 10,
            "templates": {
                "detection": (
                    "[安全告警]\n"
                    "时间: {timestamp}\n"
                    "攻击类型: {attack_type}\n"
                    "严重度: {severity}\n"
                    "置信度: {confidence:.4f}\n"
                    "来源: {source}\n"
                    "输入类型: {input_kind}\n"
                    "摘要: {summary}\n"
                ),
                "batch": (
                    "[批量告警]\n"
                    "时间: {timestamp}\n"
                    "总事件: {total_events}\n"
                    "攻击事件: {attack_events}\n"
                    "正常事件: {benign_events}\n"
                    "攻击比例: {attack_ratio:.2%}\n"
                ),
            },
            "channels": [],
        },
        "system": {
            "name": "网络安全态势感知系统",
            "version": "4.1.0",
            "description": "基于规则引擎和机器学习的网络攻击检测与态势感知系统",
        },
    }


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """Load a YAML config file and merge it with defaults."""
    path = Path(config_path)
    if not path.exists():
        return get_default_config()

    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return _deep_merge(get_default_config(), loaded)


def save_config(config: Dict[str, Any], config_path: str = "config/config.yaml") -> None:
    """Persist configuration to disk."""
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(config, handle, allow_unicode=True, default_flow_style=False, sort_keys=False)
