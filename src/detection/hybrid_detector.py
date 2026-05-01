"""Hybrid detector that fuses rule engine and ML detector outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from .ml_detector import MLDetector
from .rule_engine import RuleDetectionResult, RuleEngine


@dataclass
class FusionDetectionResult:
    is_attack: bool
    attack_type: str
    confidence: float
    rule_result: Optional[RuleDetectionResult] = None
    ml_result: Optional[Dict[str, Any]] = None
    fusion_strategy: str = "weighted"
    explanation: str = ""


class HybridDetector:
    """Support `rule_only`, `ml_only`, and `hybrid` detection modes."""

    ATTACK_TYPE_MAPPING = {
        "SYN_FLOOD": "SYN_FLOOD",
        "UDP_FLOOD": "UDP_FLOOD",
        "DNS_FLOOD": "DNS_FLOOD",
        "NTP_FLOOD": "NTP_FLOOD",
        "SQL_INJECTION": "SQL_INJECTION",
        "ANOMALY": "DDOS",
        "ANOMALY_DETECTION": "DDOS",
    }
    BENIGN_LABELS = {"normal", "benign", "0"}

    def __init__(
        self,
        rule_config: Optional[Dict[str, Any]] = None,
        model_path: Optional[str] = None,
        mode: str = "hybrid",
        fusion_strategy: str = "weighted",
        rule_weight: float = 0.4,
        ml_weight: float = 0.6,
        confidence_threshold: float = 0.5,
    ):
        self.mode = mode
        self.fusion_strategy = fusion_strategy
        self.rule_weight = float(rule_weight)
        self.ml_weight = float(ml_weight)
        self.confidence_threshold = float(confidence_threshold)

        self.rule_engine = RuleEngine(rule_config)
        self.ml_detector = MLDetector(model_path)
        if model_path:
            self.ml_detector.load_model(model_path)

    @classmethod
    def _is_attack_label(cls, label: str) -> bool:
        return str(label).strip().lower() not in cls.BENIGN_LABELS

    def _normalize_attack_type(self, attack_type: str) -> str:
        normalized = str(attack_type).strip().upper().replace("_DETECTION", "")
        return self.ATTACK_TYPE_MAPPING.get(normalized, normalized)

    def _extract_feature_values(self, features: Dict[str, Any]) -> Optional[np.ndarray]:
        if not features:
            return None

        if self.ml_detector.feature_columns:
            values: list[float] = []
            for col in self.ml_detector.feature_columns:
                value = features.get(col)
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    return None
            return np.asarray(values, dtype=float)

        standard_features = ["pkt_rate", "syn_rate", "udp_rate", "dns_rate", "ntp_rate", "avg_pkt_size"]
        collected: list[float] = []
        for feature_name in standard_features:
            if feature_name not in features:
                return None
            try:
                collected.append(float(features[feature_name]))
            except (TypeError, ValueError):
                return None
        return np.asarray(collected, dtype=float)

    def _weighted_fusion(self, rule_result: RuleDetectionResult, ml_result: Dict[str, Any]) -> FusionDetectionResult:
        rule_score = rule_result.confidence if rule_result.is_attack else 0.0
        ml_score = float(ml_result.get("confidence", 0.0)) if ml_result.get("is_attack") else 0.0

        weight_sum = max(self.rule_weight + self.ml_weight, 1e-6)
        fused_confidence = (self.rule_weight * rule_score + self.ml_weight * ml_score) / weight_sum

        rule_attack = rule_result.is_attack
        ml_attack = bool(ml_result.get("is_attack", False))
        if fused_confidence < self.confidence_threshold and not (rule_attack and ml_attack):
            return FusionDetectionResult(
                is_attack=False,
                attack_type="NORMAL",
                confidence=fused_confidence,
                rule_result=rule_result,
                ml_result=ml_result,
                fusion_strategy="weighted",
                explanation=self._generate_fusion_explanation(rule_result, ml_result, fused_confidence, False),
            )

        if rule_attack:
            attack_type = self._normalize_attack_type(rule_result.attack_type)
        elif ml_attack:
            attack_type = self._normalize_attack_type(str(ml_result.get("attack_type", "UNKNOWN")))
        else:
            attack_type = "NORMAL"

        is_attack = attack_type != "NORMAL"
        return FusionDetectionResult(
            is_attack=is_attack,
            attack_type=attack_type,
            confidence=fused_confidence,
            rule_result=rule_result,
            ml_result=ml_result,
            fusion_strategy="weighted",
            explanation=self._generate_fusion_explanation(rule_result, ml_result, fused_confidence, is_attack),
        )

    def _voting_fusion(self, rule_result: RuleDetectionResult, ml_result: Dict[str, Any]) -> FusionDetectionResult:
        rule_attack = rule_result.is_attack
        ml_attack = bool(ml_result.get("is_attack", False))
        votes = int(rule_attack) + int(ml_attack)

        if votes == 0:
            return FusionDetectionResult(
                is_attack=False,
                attack_type="NORMAL",
                confidence=(rule_result.confidence + float(ml_result.get("confidence", 0.0))) / 2,
                rule_result=rule_result,
                ml_result=ml_result,
                fusion_strategy="voting",
                explanation=self._generate_fusion_explanation(
                    rule_result,
                    ml_result,
                    (rule_result.confidence + float(ml_result.get("confidence", 0.0))) / 2,
                    False,
                ),
            )

        if rule_attack:
            attack_type = self._normalize_attack_type(rule_result.attack_type)
        else:
            attack_type = self._normalize_attack_type(str(ml_result.get("attack_type", "UNKNOWN")))

        confidence = max(rule_result.confidence, float(ml_result.get("confidence", 0.0)))
        return FusionDetectionResult(
            is_attack=True,
            attack_type=attack_type,
            confidence=confidence,
            rule_result=rule_result,
            ml_result=ml_result,
            fusion_strategy="voting",
            explanation=self._generate_fusion_explanation(rule_result, ml_result, confidence, True),
        )

    def _generate_fusion_explanation(
        self,
        rule_result: RuleDetectionResult,
        ml_result: Dict[str, Any],
        fused_confidence: float,
        is_attack: bool,
    ) -> str:
        lines: list[str] = []
        if rule_result.is_attack:
            lines.append(
                f"Rule engine: {self._normalize_attack_type(rule_result.attack_type)} "
                f"(confidence={rule_result.confidence:.2f})"
            )
            if rule_result.explanation:
                lines.append(rule_result.explanation)
        else:
            lines.append("Rule engine: NORMAL")

        if ml_result:
            lines.append(
                f"ML detector: {self._normalize_attack_type(str(ml_result.get('attack_type', 'NORMAL')))} "
                f"(confidence={float(ml_result.get('confidence', 0.0)):.2f})"
            )

        verdict = "ATTACK" if is_attack else "NORMAL"
        lines.append(f"Fusion verdict: {verdict} (confidence={fused_confidence:.2f}, strategy={self.fusion_strategy})")
        return "\n".join(lines)

    def detect(self, features: Dict[str, Any]) -> FusionDetectionResult:
        rule_result = self.rule_engine.detect(features)

        ml_result: Dict[str, Any] = {
            "prediction": 0,
            "attack_type": "NORMAL",
            "is_attack": False,
            "confidence": 0.0,
            "probabilities": None,
        }

        if self.mode != "rule_only" and self.ml_detector.is_loaded:
            feature_values = self._extract_feature_values(features)
            if feature_values is not None:
                try:
                    ml_result = self.ml_detector.predict(feature_values)
                    ml_result["attack_type"] = self._normalize_attack_type(str(ml_result.get("attack_type", "NORMAL")))
                    ml_result["is_attack"] = self._is_attack_label(str(ml_result["attack_type"]))
                except Exception as exc:
                    ml_result = {
                        "prediction": 0,
                        "attack_type": "NORMAL",
                        "is_attack": False,
                        "confidence": 0.0,
                        "error": str(exc),
                    }

        if self.mode == "rule_only":
            return FusionDetectionResult(
                is_attack=rule_result.is_attack,
                attack_type=self._normalize_attack_type(rule_result.attack_type),
                confidence=rule_result.confidence,
                rule_result=rule_result,
                ml_result=ml_result,
                fusion_strategy="rule_only",
                explanation=rule_result.explanation,
            )

        if self.mode == "ml_only":
            is_attack = bool(ml_result.get("is_attack", False))
            return FusionDetectionResult(
                is_attack=is_attack,
                attack_type=self._normalize_attack_type(str(ml_result.get("attack_type", "NORMAL"))),
                confidence=float(ml_result.get("confidence", 0.0)),
                rule_result=rule_result,
                ml_result=ml_result,
                fusion_strategy="ml_only",
                explanation=self._generate_fusion_explanation(
                    rule_result,
                    ml_result,
                    float(ml_result.get("confidence", 0.0)),
                    is_attack,
                ),
            )

        if self.fusion_strategy == "voting":
            return self._voting_fusion(rule_result, ml_result)
        return self._weighted_fusion(rule_result, ml_result)

    def detect_batch(self, features_list: List[Dict[str, Any]]) -> List[FusionDetectionResult]:
        return [self.detect(features) for features in features_list]

    def set_mode(self, mode: str) -> None:
        if mode not in {"ml_only", "rule_only", "hybrid"}:
            raise ValueError(f"Invalid mode: {mode}")
        self.mode = mode

    def set_fusion_strategy(self, strategy: str, rule_weight: float = 0.4, ml_weight: float = 0.6) -> None:
        if strategy not in {"weighted", "voting"}:
            raise ValueError(f"Invalid strategy: {strategy}")
        self.fusion_strategy = strategy
        self.rule_weight = float(rule_weight)
        self.ml_weight = float(ml_weight)
