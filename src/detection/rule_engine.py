"""Rule-based detection engine for common network attacks."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RuleTrigger:
    """A single rule trigger record."""

    rule_name: str
    threshold: float
    actual_value: float
    severity: str
    description: str


@dataclass
class RuleDetectionResult:
    """Final result of rule-based detection."""

    is_attack: bool
    attack_type: str
    confidence: float
    triggers: List[RuleTrigger] = field(default_factory=list)
    explanation: str = ""


class RuleEngine:
    """Detect SYN/UDP/DNS/NTP flood and SQL injection patterns."""

    DEFAULT_THRESHOLDS = {
        "syn_flood_per_sec": 500.0,
        "udp_flood_per_min": 10000.0,
        "dns_flood_per_sec": 2000.0,
        "ntp_flood_per_min": 5000.0,
        "sql_injection_min_matches": 2.0,
        "pkt_anomaly_per_sec": 10000.0,
    }

    SQL_INJECTION_KEYWORDS = [
        "union",
        "select",
        "or 1=1",
        "drop",
        "insert",
        "update",
        "delete",
        "--",
        ";",
        "/*",
        "*/",
        "xp_cmdshell",
        "information_schema",
    ]

    _SEVERITY_SCORES = {"low": 1, "medium": 2, "high": 3, "critical": 4}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.thresholds = dict(self.DEFAULT_THRESHOLDS)
        if config and isinstance(config, dict):
            self.thresholds.update(config.get("rule_thresholds", {}))
        self.sql_keywords = (
            list(config.get("sql_injection_keywords", self.SQL_INJECTION_KEYWORDS))
            if isinstance(config, dict)
            else list(self.SQL_INJECTION_KEYWORDS)
        )

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def detect_syn_flood(self, features: Dict[str, Any]) -> Optional[RuleTrigger]:
        syn_rate = self._to_float(features.get("syn_rate"), 0.0)
        threshold = self._to_float(self.thresholds.get("syn_flood_per_sec"), 500.0)
        if syn_rate < threshold:
            return None
        severity = "critical" if syn_rate >= threshold * 2 else "high"
        return RuleTrigger(
            rule_name="SYN_FLOOD_DETECTION",
            threshold=threshold,
            actual_value=syn_rate,
            severity=severity,
            description=f"SYN rate {syn_rate:.0f}/s exceeds threshold {threshold:.0f}/s.",
        )

    def detect_udp_flood(self, features: Dict[str, Any]) -> Optional[RuleTrigger]:
        udp_rate_raw = self._to_float(features.get("udp_rate"), 0.0)
        threshold_per_min = self._to_float(self.thresholds.get("udp_flood_per_min"), 10000.0)
        rate_unit = str(features.get("udp_rate_unit", "per_min")).lower()
        if rate_unit in {"per_sec", "sec", "s"}:
            window_seconds = max(self._to_float(features.get("window_seconds"), 1.0), 0.001)
            udp_per_min = udp_rate_raw * (60.0 / window_seconds)
        else:
            udp_per_min = udp_rate_raw
        if udp_per_min < threshold_per_min:
            return None
        severity = "critical" if udp_per_min >= threshold_per_min * 2 else "high"
        return RuleTrigger(
            rule_name="UDP_FLOOD_DETECTION",
            threshold=threshold_per_min,
            actual_value=udp_per_min,
            severity=severity,
            description=(
                f"UDP rate normalized to {udp_per_min:.0f}/min exceeds "
                f"threshold {threshold_per_min:.0f}/min."
            ),
        )

    def detect_dns_flood(self, features: Dict[str, Any]) -> Optional[RuleTrigger]:
        dns_rate = self._to_float(features.get("dns_rate"), 0.0)
        threshold = self._to_float(self.thresholds.get("dns_flood_per_sec"), 2000.0)
        if dns_rate < threshold:
            return None
        severity = "critical" if dns_rate >= threshold * 2 else "high"
        return RuleTrigger(
            rule_name="DNS_FLOOD_DETECTION",
            threshold=threshold,
            actual_value=dns_rate,
            severity=severity,
            description=f"DNS query rate {dns_rate:.0f}/s exceeds threshold {threshold:.0f}/s.",
        )

    def detect_ntp_flood(self, features: Dict[str, Any]) -> Optional[RuleTrigger]:
        ntp_rate_raw = self._to_float(features.get("ntp_rate"), 0.0)
        threshold_per_min = self._to_float(self.thresholds.get("ntp_flood_per_min"), 5000.0)
        rate_unit = str(features.get("ntp_rate_unit", "per_min")).lower()
        if rate_unit in {"per_sec", "sec", "s"}:
            window_seconds = max(self._to_float(features.get("window_seconds"), 1.0), 0.001)
            ntp_per_min = ntp_rate_raw * (60.0 / window_seconds)
        else:
            ntp_per_min = ntp_rate_raw
        if ntp_per_min < threshold_per_min:
            return None
        severity = "critical" if ntp_per_min >= threshold_per_min * 2 else "high"
        return RuleTrigger(
            rule_name="NTP_FLOOD_DETECTION",
            threshold=threshold_per_min,
            actual_value=ntp_per_min,
            severity=severity,
            description=(
                f"NTP query rate normalized to {ntp_per_min:.0f}/min exceeds "
                f"threshold {threshold_per_min:.0f}/min."
            ),
        )

    def detect_sql_injection(self, features: Dict[str, Any]) -> Optional[RuleTrigger]:
        payload = features.get("payload")
        if payload is None:
            payload = features.get("http_payload")
        if payload is None:
            return None
        payload_text = str(payload).lower()
        matches = sum(1 for keyword in self.sql_keywords if keyword in payload_text)
        threshold = self._to_float(self.thresholds.get("sql_injection_min_matches"), 2.0)
        if matches < threshold:
            return None
        severity = "critical" if matches >= threshold * 2 else "high"
        return RuleTrigger(
            rule_name="SQL_INJECTION_DETECTION",
            threshold=threshold,
            actual_value=float(matches),
            severity=severity,
            description=f"SQL injection indicators matched {matches} times (threshold {threshold:.0f}).",
        )

    def detect_anomaly(self, features: Dict[str, Any]) -> Optional[RuleTrigger]:
        pkt_rate = self._to_float(features.get("pkt_rate"), 0.0)
        avg_pkt_size = self._to_float(features.get("avg_pkt_size"), 0.0)
        threshold = self._to_float(self.thresholds.get("pkt_anomaly_per_sec"), 10000.0)
        if pkt_rate <= threshold:
            return None
        # High packet rate with tiny average packet size is a common flood signal.
        if avg_pkt_size < 100:
            severity = "high" if pkt_rate < threshold * 2 else "critical"
            return RuleTrigger(
                rule_name="ANOMALY_DETECTION",
                threshold=threshold,
                actual_value=pkt_rate,
                severity=severity,
                description=(
                    f"Abnormal traffic pattern detected: pkt_rate={pkt_rate:.0f}/s, "
                    f"avg_pkt_size={avg_pkt_size:.0f} bytes."
                ),
            )
        return None

    def detect(self, features: Dict[str, Any]) -> RuleDetectionResult:
        detectors = [
            self.detect_syn_flood,
            self.detect_udp_flood,
            self.detect_dns_flood,
            self.detect_ntp_flood,
            self.detect_sql_injection,
            self.detect_anomaly,
        ]
        triggers: List[RuleTrigger] = []
        for detector in detectors:
            trigger = detector(features)
            if trigger is not None:
                triggers.append(trigger)

        if not triggers:
            return RuleDetectionResult(
                is_attack=False,
                attack_type="NORMAL",
                confidence=0.0,
                triggers=[],
                explanation="No rule-based attack evidence was found.",
            )

        max_trigger = max(triggers, key=lambda t: self._SEVERITY_SCORES.get(t.severity, 0))
        confidence = min(
            1.0,
            0.2 * len(triggers) + 0.15 * self._SEVERITY_SCORES.get(max_trigger.severity, 1),
        )
        attack_type = max_trigger.rule_name.replace("_DETECTION", "")
        return RuleDetectionResult(
            is_attack=True,
            attack_type=attack_type,
            confidence=confidence,
            triggers=triggers,
            explanation=self._generate_explanation(triggers),
        )

    @staticmethod
    def _generate_explanation(triggers: List[RuleTrigger]) -> str:
        if not triggers:
            return "No rule was triggered."
        lines = ["Rule evidence:"]
        for trigger in triggers:
            lines.append(f"- {trigger.description} (severity={trigger.severity})")
        return "\n".join(lines)

    def detect_batch(self, features_list: List[Dict[str, Any]]) -> List[RuleDetectionResult]:
        return [self.detect(features) for features in features_list]
