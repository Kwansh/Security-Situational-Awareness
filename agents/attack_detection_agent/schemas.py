"""Input/output schemas for attack detection agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


UTC = timezone.utc


@dataclass
class AttackDetectionInput:
    """Unified input payload for passive attack detection."""

    source: str = "agent_hub"
    trace_id: Optional[str] = None
    features: Optional[List[float] | Dict[str, Any]] = None
    record: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def validate(self) -> None:
        if self.features is None and self.record is None:
            raise ValueError("Provide either `features` or `record`.")


@dataclass
class RuleEvidence:
    """Structured rule trigger evidence."""

    rule_name: str
    severity: str
    threshold: float
    actual_value: float
    description: str


@dataclass
class AttackDetectionOutput:
    """Standardized output from attack detection agent."""

    source: str
    trace_id: Optional[str]
    timestamp: str
    is_attack: bool
    attack_type: str
    confidence: float
    severity: str
    summary: str
    recommendations: List[str]
    dynamic_metrics: Dict[str, float]
    rule_evidence: List[RuleEvidence]
    raw_result: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["rule_evidence"] = [asdict(item) for item in self.rule_evidence]
        return payload
