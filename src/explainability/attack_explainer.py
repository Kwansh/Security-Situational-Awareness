"""Attack explanation module for readable detection evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class AttackExplanation:
    attack_type: str
    severity: str
    summary: str
    details: List[str]
    recommendations: List[str]
    technical_details: Optional[Dict[str, Any]] = None


class AttackExplainer:
    ATTACK_DESCRIPTIONS = {
        "SYN_FLOOD": {
            "name": "SYN Flood",
            "description": "大量SYN请求但不完成握手，耗尽服务连接资源。",
            "severity": "high",
            "recommendations": [
                "启用SYN Cookie并调整半连接队列。",
                "在边界设备配置SYN速率限制。",
                "对可疑源地址启用ACL或黑洞路由。",
            ],
        },
        "UDP_FLOOD": {
            "name": "UDP Flood",
            "description": "高强度UDP流量导致带宽或CPU资源被挤占。",
            "severity": "high",
            "recommendations": [
                "限制高风险UDP端口的速率。",
                "关闭非必要UDP服务。",
                "接入流量清洗能力。",
            ],
        },
        "DNS_FLOOD": {
            "name": "DNS Flood",
            "description": "针对DNS服务的大量查询压垮解析能力。",
            "severity": "high",
            "recommendations": [
                "启用DNS响应速率限制(RRL)。",
                "部署多节点DNS与缓存策略。",
                "对异常源IP实施限流和封禁。",
            ],
        },
        "NTP_FLOOD": {
            "name": "NTP Flood",
            "description": "利用NTP协议进行高流量放大或反射攻击。",
            "severity": "medium",
            "recommendations": [
                "限制NTP外部访问并关闭monlist等高风险能力。",
                "升级NTP服务并启用访问控制。",
                "过滤来源异常的NTP响应流量。",
            ],
        },
        "SQL_INJECTION": {
            "name": "SQL Injection",
            "description": "请求载荷疑似包含恶意SQL语句注入模式。",
            "severity": "critical",
            "recommendations": [
                "全面使用参数化查询。",
                "加强输入校验和输出转义。",
                "部署WAF并审计高风险接口。",
            ],
        },
        "DDOS": {
            "name": "DDoS",
            "description": "流量统计出现异常洪泛行为。",
            "severity": "high",
            "recommendations": [
                "启用弹性防护与自动扩容策略。",
                "配置全链路限流与熔断。",
                "建立应急响应预案和回放机制。",
            ],
        },
        "NORMAL": {
            "name": "Normal",
            "description": "未发现明确攻击证据。",
            "severity": "low",
            "recommendations": ["保持监控并定期更新检测规则与模型。"],
        },
    }

    def __init__(self, include_technical_details: bool = True):
        self.include_technical_details = include_technical_details

    def explain(self, detection_result: Any, features: Optional[Dict[str, Any]] = None) -> AttackExplanation:
        raw_attack_type = str(getattr(detection_result, "attack_type", "NORMAL")).upper()
        attack_type = raw_attack_type.replace("_DETECTION", "")
        attack_info = self.ATTACK_DESCRIPTIONS.get(attack_type, self.ATTACK_DESCRIPTIONS["NORMAL"])

        confidence = float(getattr(detection_result, "confidence", 0.0))
        if confidence >= 0.85:
            severity = "critical"
        elif confidence >= 0.65:
            severity = "high"
        elif confidence >= 0.45:
            severity = "medium"
        else:
            severity = attack_info["severity"]

        details = self._generate_details(detection_result, features)
        recommendations = list(attack_info["recommendations"])
        if confidence < 0.5 and attack_type != "NORMAL":
            recommendations.insert(0, "建议结合上下文流量进一步确认，降低误报风险。")

        technical_details = self._generate_technical_details(detection_result, features) if self.include_technical_details else None

        return AttackExplanation(
            attack_type=attack_info["name"],
            severity=severity,
            summary=self._generate_summary(attack_info["name"], attack_info["description"], confidence, attack_type),
            details=details,
            recommendations=recommendations,
            technical_details=technical_details,
        )

    @staticmethod
    def _generate_summary(attack_name: str, description: str, confidence: float, attack_type: str) -> str:
        if attack_type == "NORMAL":
            return "当前样本未命中攻击规则，模型也未给出攻击判定。"
        return f"检测到 {attack_name}，置信度 {confidence:.1%}。{description}"

    def _generate_details(self, detection_result: Any, features: Optional[Dict[str, Any]]) -> List[str]:
        details: List[str] = []

        rule_result = getattr(detection_result, "rule_result", None)
        if rule_result and getattr(rule_result, "triggers", None):
            details.append("规则触发证据:")
            for trigger in rule_result.triggers:
                details.append(f"- {trigger.rule_name}: {trigger.description} (severity={trigger.severity})")

        ml_result = getattr(detection_result, "ml_result", None)
        if isinstance(ml_result, dict) and ml_result:
            details.append(
                "模型判定: "
                f"{ml_result.get('attack_type', 'NORMAL')} "
                f"(confidence={float(ml_result.get('confidence', 0.0)):.2f})"
            )

        if features:
            monitored = ["pkt_rate", "syn_rate", "udp_rate", "dns_rate", "ntp_rate", "avg_pkt_size"]
            visible = [k for k in monitored if k in features]
            if visible:
                details.append("关键流量特征:")
                for key in visible:
                    details.append(f"- {key}={features[key]}")

        if not details:
            details.append("无额外可解释证据。")
        return details

    @staticmethod
    def _generate_technical_details(detection_result: Any, features: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        technical = {
            "is_attack": bool(getattr(detection_result, "is_attack", False)),
            "confidence": float(getattr(detection_result, "confidence", 0.0)),
            "fusion_strategy": getattr(detection_result, "fusion_strategy", "unknown"),
        }
        if features:
            technical["input_features"] = {
                key: value for key, value in features.items() if isinstance(value, (int, float, str))
            }
        return technical

    def format_report(self, explanation: AttackExplanation) -> str:
        lines = [
            "=" * 64,
            f"Security Detection Report: {explanation.attack_type}",
            "=" * 64,
            f"Severity: {explanation.severity.upper()}",
            "",
            f"Summary: {explanation.summary}",
            "",
            "Details:",
        ]
        lines.extend(explanation.details)
        lines.append("")
        lines.append("Recommendations:")
        for idx, recommendation in enumerate(explanation.recommendations, start=1):
            lines.append(f"{idx}. {recommendation}")
        if explanation.technical_details:
            lines.append("")
            lines.append(f"Technical: {explanation.technical_details}")
        lines.append("=" * 64)
        return "\n".join(lines)
