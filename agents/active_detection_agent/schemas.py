"""Input/output schemas for active detection agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


UTC = timezone.utc


@dataclass
class ActiveScanInput:
    """Input payload for active probe scanning."""

    targets: List[str]
    tcp_ports: List[int] = field(
        default_factory=lambda: [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 3306, 3389, 6379, 8080]
    )
    timeout_ms: int = 400
    max_workers: int = 64
    source: str = "active_detection_agent"
    trace_id: Optional[str] = None

    def validate(self) -> None:
        if not self.targets:
            raise ValueError("`targets` must not be empty.")
        if self.timeout_ms <= 0:
            raise ValueError("`timeout_ms` must be > 0.")
        if self.max_workers <= 0:
            raise ValueError("`max_workers` must be > 0.")


@dataclass
class PortFinding:
    """Single port probe finding."""

    target: str
    port: int
    protocol: str
    state: str
    latency_ms: Optional[float]
    service: str
    risk: str


@dataclass
class ActiveScanOutput:
    """Standardized output for active scan results."""

    source: str
    trace_id: Optional[str]
    started_at: str
    finished_at: str
    duration_ms: int
    summary: Dict[str, int]
    findings: List[PortFinding]
    recommendations: List[str]
    errors: List[str]

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["findings"] = [asdict(item) for item in self.findings]
        return payload


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
