"""Additional API routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from agents.active_detection_agent import ActiveDetectionAgent
from src.detection.rule_engine import RuleEngine
from src.explainability.attack_explainer import AttackExplainer

router = APIRouter()
_rule_engine = RuleEngine()
_explainer = AttackExplainer()
_active_agent = ActiveDetectionAgent()


class ActiveScanRequest(BaseModel):
    """Input payload for the active scan endpoint."""

    targets: list[str]
    tcp_ports: list[int] = Field(
        default_factory=lambda: [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 3306, 3389, 6379, 8080]
    )
    timeout_ms: int = Field(default=400, ge=1, le=60000)
    max_workers: int = Field(default=64, ge=1, le=256)
    source: str = Field(default="api_active_scan", max_length=64)
    trace_id: str | None = None


@router.post("/explain")
async def explain_prediction(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an explanation using rule-based evidence."""
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, dict):
        features = payload if isinstance(payload, dict) else {}

    result = _rule_engine.detect(features)
    explained = _explainer.explain(result, features)
    return {
        "is_attack": result.is_attack,
        "attack_type": result.attack_type,
        "confidence": result.confidence,
        "triggers": [
            {
                "rule_name": trigger.rule_name,
                "severity": trigger.severity,
                "threshold": trigger.threshold,
                "actual_value": trigger.actual_value,
                "description": trigger.description,
            }
            for trigger in result.triggers
        ],
        "explanation": {
            "attack_type": explained.attack_type,
            "severity": explained.severity,
            "summary": explained.summary,
            "details": explained.details,
            "recommendations": explained.recommendations,
            "technical_details": explained.technical_details,
        },
    }


@router.post("/active-scan")
async def active_scan(payload: ActiveScanRequest) -> Dict[str, Any]:
    """Run an authorized active probe scan and return structured findings."""
    result = _active_agent.run(payload.model_dump())
    return result.to_dict()
