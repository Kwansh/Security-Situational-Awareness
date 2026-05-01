"""Unified alerting framework for attack notifications."""

from __future__ import annotations

import json
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib import error as urllib_error
from urllib import request as urllib_request

from src.utils.config import load_config


@dataclass
class AlertResult:
    channel: str
    success: bool
    attempts: int = 0
    error: Optional[str] = None
    response: Optional[str] = None


class AlertChannel:
    """Base class for all alert channels."""

    channel_type = "base"

    def __init__(self, name: Optional[str] = None, enabled: bool = True, retries: int = 3, timeout: int = 10):
        self.name = name or self.channel_type
        self.enabled = enabled
        self.retries = max(1, int(retries))
        self.timeout = max(1, int(timeout))

    def send(self, payload: Dict[str, Any]) -> AlertResult:
        raise NotImplementedError


class WebhookAlertChannel(AlertChannel):
    channel_type = "webhook"

    def __init__(self, url: str, method: str = "POST", headers: Optional[Dict[str, str]] = None, **kwargs):
        super().__init__(**kwargs)
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}

    def send(self, payload: Dict[str, Any]) -> AlertResult:
        if not self.enabled:
            return AlertResult(channel=self.name, success=False, error="channel_disabled")

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib_request.Request(self.url, data=body, method=self.method)
        req.add_header("Content-Type", "application/json; charset=utf-8")
        for key, value in self.headers.items():
            req.add_header(str(key), str(value))

        try:
            with urllib_request.urlopen(req, timeout=self.timeout) as resp:
                response_text = resp.read().decode("utf-8", errors="ignore")
                return AlertResult(channel=self.name, success=True, response=response_text)
        except Exception as exc:  # pragma: no cover - network dependent
            return AlertResult(channel=self.name, success=False, error=str(exc))


class WeComRobotChannel(WebhookAlertChannel):
    channel_type = "wecom"

    def build_request_body(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        content = payload.get("message") or payload.get("text") or json.dumps(payload, ensure_ascii=False, indent=2)
        return {
            "msgtype": "markdown",
            "markdown": {"content": content},
        }

    def send(self, payload: Dict[str, Any]) -> AlertResult:
        return super().send(self.build_request_body(payload))


class SmsAlertChannel(WebhookAlertChannel):
    channel_type = "sms"

    def build_request_body(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        message = payload.get("message") or payload.get("text") or "Security alert"
        return {
            "type": "sms",
            "message": message,
            "payload": payload,
        }

    def send(self, payload: Dict[str, Any]) -> AlertResult:
        return super().send(self.build_request_body(payload))


class EmailAlertChannel(AlertChannel):
    channel_type = "email"

    def __init__(
        self,
        host: str,
        port: int,
        from_addr: str,
        to_addrs: Sequence[str],
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        use_ssl: bool = False,
        subject_prefix: str = "[Security Alert]",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.host = host
        self.port = int(port)
        self.from_addr = from_addr
        self.to_addrs = list(to_addrs)
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.subject_prefix = subject_prefix

    def send(self, payload: Dict[str, Any]) -> AlertResult:
        if not self.enabled:
            return AlertResult(channel=self.name, success=False, error="channel_disabled")
        if not self.to_addrs:
            return AlertResult(channel=self.name, success=False, error="missing_recipients")

        message = EmailMessage()
        message["From"] = self.from_addr
        message["To"] = ", ".join(self.to_addrs)
        message["Subject"] = f"{self.subject_prefix} {payload.get('title', payload.get('attack_type', 'Alert'))}"
        message.set_content(payload.get("message") or json.dumps(payload, ensure_ascii=False, indent=2))

        smtp_cls = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP
        try:
            with smtp_cls(self.host, self.port, timeout=self.timeout) as client:
                if self.use_tls and not self.use_ssl:
                    client.starttls(context=ssl.create_default_context())
                if self.username:
                    client.login(self.username, self.password)
                client.send_message(message)
            return AlertResult(channel=self.name, success=True)
        except Exception as exc:  # pragma: no cover - network dependent
            return AlertResult(channel=self.name, success=False, error=str(exc))


@dataclass
class AlertManager:
    enabled: bool = False
    trigger_on_detection: bool = True
    trigger_on_batch: bool = True
    retries: int = 3
    retry_delay_seconds: float = 2.0
    timeout_seconds: int = 10
    templates: Dict[str, str] = field(default_factory=dict)
    channels: List[AlertChannel] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: Optional[Dict[str, Any]] = None) -> "AlertManager":
        cfg = config or load_config()
        alerting = cfg.get("alerting") or {}
        templates = (alerting.get("templates") or {}).copy()
        channels: List[AlertChannel] = []

        for channel_cfg in alerting.get("channels", []) or []:
            if not isinstance(channel_cfg, dict):
                continue
            if not channel_cfg.get("enabled", False):
                continue
            channel_type = str(channel_cfg.get("type", "")).lower().strip()
            timeout = int(channel_cfg.get("timeout_seconds", alerting.get("timeout_seconds", 10)))
            retries = int(channel_cfg.get("retries", alerting.get("retries", 3)))
            common = {
                "enabled": True,
                "retries": retries,
                "timeout": timeout,
                "name": channel_cfg.get("name"),
            }
            if channel_type == "webhook":
                channels.append(
                    WebhookAlertChannel(
                        url=str(channel_cfg.get("url", "")).strip(),
                        method=str(channel_cfg.get("method", "POST")),
                        headers=channel_cfg.get("headers") or {},
                        **common,
                    )
                )
            elif channel_type in {"wecom", "wechat", "wecom_robot"}:
                channels.append(
                    WeComRobotChannel(
                        url=str(channel_cfg.get("url", "")).strip(),
                        method=str(channel_cfg.get("method", "POST")),
                        headers=channel_cfg.get("headers") or {},
                        **common,
                    )
                )
            elif channel_type == "email":
                channels.append(
                    EmailAlertChannel(
                        host=str(channel_cfg.get("host", "")),
                        port=int(channel_cfg.get("port", 25)),
                        from_addr=str(channel_cfg.get("from_addr", channel_cfg.get("username", ""))),
                        to_addrs=channel_cfg.get("to_addrs") or [],
                        username=str(channel_cfg.get("username", "")),
                        password=str(channel_cfg.get("password", "")),
                        use_tls=bool(channel_cfg.get("use_tls", True)),
                        use_ssl=bool(channel_cfg.get("use_ssl", False)),
                        subject_prefix=str(channel_cfg.get("subject_prefix", "[Security Alert]")),
                        **common,
                    )
                )
            elif channel_type == "sms":
                channels.append(
                    SmsAlertChannel(
                        url=str(channel_cfg.get("endpoint", channel_cfg.get("url", ""))).strip(),
                        method=str(channel_cfg.get("method", "POST")),
                        headers=channel_cfg.get("headers") or {},
                        **common,
                    )
                )

        return cls(
            enabled=bool(alerting.get("enabled", False)),
            trigger_on_detection=bool(alerting.get("trigger_on_detection", True)),
            trigger_on_batch=bool(alerting.get("trigger_on_batch", True)),
            retries=int(alerting.get("retries", 3)),
            retry_delay_seconds=float(alerting.get("retry_delay_seconds", 2.0)),
            timeout_seconds=int(alerting.get("timeout_seconds", 10)),
            templates=templates,
            channels=channels,
        )

    @staticmethod
    def _safe_format(template: str, context: Dict[str, Any]) -> str:
        class _SafeDict(dict):
            def __missing__(self, key):
                return ""

        return template.format_map(_SafeDict(context))

    def _dispatch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled or not self.channels:
            return {
                "enabled": False,
                "sent": False,
                "channels": [],
                "reason": "alerting_disabled_or_no_channels",
            }

        results: List[AlertResult] = []
        for channel in self.channels:
            attempt_result = self._send_with_retry(channel, payload)
            results.append(attempt_result)

        sent = any(result.success for result in results)
        return {
            "enabled": True,
            "sent": sent,
            "channels": [
                {
                    "channel": result.channel,
                    "success": result.success,
                    "attempts": result.attempts,
                    "error": result.error,
                    "response": result.response,
                }
                for result in results
            ],
        }

    def _send_with_retry(self, channel: AlertChannel, payload: Dict[str, Any]) -> AlertResult:
        last_result = AlertResult(channel=channel.name, success=False, attempts=0)
        for attempt in range(1, max(1, self.retries) + 1):
            result = channel.send(payload)
            result.attempts = attempt
            last_result = result
            if result.success:
                return result
            if attempt < self.retries:
                time.sleep(max(0.0, self.retry_delay_seconds))
        return last_result

    def notify_detection(
        self,
        *,
        event: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        source: str = "api",
        input_kind: str = "features",
    ) -> Dict[str, Any]:
        if not self.trigger_on_detection:
            return {"enabled": False, "sent": False, "reason": "detection_alerting_disabled"}

        context = self._build_detection_context(event=event, result=result, source=source, input_kind=input_kind)
        message = self._safe_format(self.templates.get("detection", "{attack_type}"), context)
        payload = {
            "type": "detection",
            "title": f"{context['attack_type']} 告警",
            "message": message,
            "text": message,
            "event": event,
            "result": result or {},
            "context": context,
        }
        return self._dispatch(payload)

    def notify_batch(
        self,
        *,
        events: Sequence[Dict[str, Any]],
        summary: Optional[Dict[str, Any]] = None,
        source: str = "batch",
    ) -> Dict[str, Any]:
        if not self.trigger_on_batch:
            return {"enabled": False, "sent": False, "reason": "batch_alerting_disabled"}

        summary = summary or {}
        attack_events = [event for event in events if event.get("is_attack")]
        if not attack_events:
            return {"enabled": False, "sent": False, "reason": "no_attack_events"}
        context = {
            "timestamp": events[-1].get("timestamp") if events else "",
            "total_events": len(events),
            "attack_events": len(attack_events),
            "benign_events": len(events) - len(attack_events),
            "attack_ratio": (len(attack_events) / len(events)) if events else 0.0,
            "source": source,
            "summary": summary,
        }
        message = self._safe_format(self.templates.get("batch", "{total_events}"), context)
        payload = {
            "type": "batch",
            "title": "批量告警",
            "message": message,
            "text": message,
            "events": list(events),
            "summary": summary,
            "context": context,
        }
        return self._dispatch(payload)

    @staticmethod
    def _build_detection_context(
        *,
        event: Dict[str, Any],
        result: Optional[Dict[str, Any]],
        source: str,
        input_kind: str,
    ) -> Dict[str, Any]:
        result = result or {}
        explanation = result.get("explanation") or {}
        summary = explanation.get("summary") or result.get("summary") or "检测到疑似攻击流量"
        return {
            "timestamp": event.get("timestamp", ""),
            "attack_type": str(result.get("attack_type") or event.get("prediction_label") or "UNKNOWN"),
            "severity": event.get("severity", "low"),
            "confidence": float(event.get("confidence", 0.0)),
            "source": source,
            "input_kind": input_kind,
            "summary": summary,
            "details": explanation.get("details") or "",
            "recommendations": explanation.get("recommendations") or [],
            "prediction_label": event.get("prediction_label", ""),
            "is_attack": event.get("is_attack", False),
        }


_ALERT_MANAGER: Optional[AlertManager] = None


def get_alert_manager(reload: bool = False) -> AlertManager:
    global _ALERT_MANAGER
    if reload or _ALERT_MANAGER is None:
        _ALERT_MANAGER = AlertManager.from_config()
    return _ALERT_MANAGER


def reload_alert_manager() -> AlertManager:
    return get_alert_manager(reload=True)
