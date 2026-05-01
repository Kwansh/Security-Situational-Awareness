"""Passive attack detection agent wrapper."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException

from agents.attack_detection_agent.schemas import AttackDetectionInput, AttackDetectionOutput, RuleEvidence
from src.api import server as detection_api


class AttackDetectionAgent:
    """Wrap existing passive detection pipeline with unified IO interface."""

    def __init__(
        self,
        artifact_path: Optional[str] = None,
        allow_rule_only_fallback: bool = True,
    ):
        if artifact_path:
            os.environ["MODEL_ARTIFACT_PATH"] = artifact_path
        self.allow_rule_only_fallback = allow_rule_only_fallback
        self.model_loaded = detection_api.load_models(force=True)

    @staticmethod
    def _coerce_payload(payload: AttackDetectionInput | Dict[str, Any]) -> AttackDetectionInput:
        if isinstance(payload, AttackDetectionInput):
            payload.validate()
            return payload

        if not isinstance(payload, dict):
            raise TypeError("payload must be AttackDetectionInput or dict")

        data = AttackDetectionInput(
            source=str(payload.get("source", "agent_hub")),
            trace_id=payload.get("trace_id"),
            features=payload.get("features"),
            record=payload.get("record"),
            metadata=dict(payload.get("metadata") or {}),
            timestamp=str(payload.get("timestamp") or AttackDetectionInput().timestamp),
        )
        data.validate()
        return data

    @staticmethod
    def _collect_rule_evidence(raw_result: Dict[str, Any]) -> List[RuleEvidence]:
        rule_result = raw_result.get("rule_result")
        if not rule_result:
            return []

        triggers = getattr(rule_result, "triggers", []) or []
        evidence: List[RuleEvidence] = []
        for trigger in triggers:
            evidence.append(
                RuleEvidence(
                    rule_name=str(getattr(trigger, "rule_name", "")),
                    severity=str(getattr(trigger, "severity", "unknown")),
                    threshold=float(getattr(trigger, "threshold", 0.0)),
                    actual_value=float(getattr(trigger, "actual_value", 0.0)),
                    description=str(getattr(trigger, "description", "")),
                )
            )
        return evidence

    def _predict_with_fallback(self, payload: AttackDetectionInput) -> Dict[str, Any]:
        try:
            return detection_api._predict_single(payload.features, payload.record)
        except HTTPException as exc:
            if not self.allow_rule_only_fallback or exc.status_code != 503:
                raise

            feature_dict: Dict[str, Any] = {}
            if isinstance(payload.record, dict):
                feature_dict = payload.record
            elif isinstance(payload.features, dict):
                feature_dict = payload.features
            else:
                raise

            result = detection_api._rule_only_predict(feature_dict)
            result["explanation"] = detection_api._build_explanation(result, feature_dict)
            return result

    def run(self, payload: AttackDetectionInput | Dict[str, Any]) -> AttackDetectionOutput:
        request = self._coerce_payload(payload)
        raw_result = self._predict_with_fallback(request)

        dynamic_metrics = detection_api._extract_dynamic_metrics(request.features, request.record)
        metric_values = {k: float(v) for k, v in dynamic_metrics.items() if isinstance(v, (int, float))}
        explanation = raw_result.get("explanation") if isinstance(raw_result.get("explanation"), dict) else {}

        output = AttackDetectionOutput(
            source=request.source,
            trace_id=request.trace_id,
            timestamp=str(raw_result.get("timestamp") or request.timestamp),
            is_attack=bool(raw_result.get("is_attack", False)),
            attack_type=str(raw_result.get("attack_type", "NORMAL")),
            confidence=float(raw_result.get("confidence", 0.0)),
            severity=str(explanation.get("severity", "low")),
            summary=str(explanation.get("summary", "")),
            recommendations=[str(item) for item in explanation.get("recommendations", [])],
            dynamic_metrics=metric_values,
            rule_evidence=self._collect_rule_evidence(raw_result),
            raw_result=raw_result,
        )
        return output

    def run_batch(self, payloads: Iterable[AttackDetectionInput | Dict[str, Any]]) -> List[AttackDetectionOutput]:
        return [self.run(item) for item in payloads]
