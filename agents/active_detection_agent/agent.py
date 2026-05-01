"""Active scan agent for network probing."""

from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Tuple

from agents.active_detection_agent.schemas import ActiveScanInput, ActiveScanOutput, PortFinding, utc_now_iso


class ActiveDetectionAgent:
    """Perform lightweight active probing for target hosts and TCP ports."""

    HIGH_RISK_PORTS: Dict[int, str] = {
        21: "FTP",
        23: "Telnet",
        25: "SMTP",
        135: "RPC",
        139: "NetBIOS",
        445: "SMB",
        3306: "MySQL",
        3389: "RDP",
        6379: "Redis",
    }

    SERVICE_HINTS: Dict[int, str] = {
        21: "ftp",
        22: "ssh",
        23: "telnet",
        25: "smtp",
        53: "dns",
        80: "http",
        110: "pop3",
        135: "rpc",
        139: "netbios",
        143: "imap",
        443: "https",
        445: "smb",
        3306: "mysql",
        3389: "rdp",
        6379: "redis",
        8080: "http-alt",
    }

    @staticmethod
    def _coerce_payload(payload: ActiveScanInput | Dict[str, object]) -> ActiveScanInput:
        if isinstance(payload, ActiveScanInput):
            payload.validate()
            return payload
        if not isinstance(payload, dict):
            raise TypeError("payload must be ActiveScanInput or dict")

        data = ActiveScanInput(
            targets=[str(item) for item in payload.get("targets", [])],
            tcp_ports=[int(item) for item in payload.get("tcp_ports", [])]
            if payload.get("tcp_ports")
            else ActiveScanInput(targets=["127.0.0.1"]).tcp_ports,
            timeout_ms=int(payload.get("timeout_ms", 400)),
            max_workers=int(payload.get("max_workers", 64)),
            source=str(payload.get("source", "active_detection_agent")),
            trace_id=payload.get("trace_id"),
        )
        data.validate()
        return data

    @staticmethod
    def _probe_tcp(target: str, port: int, timeout_sec: float) -> Tuple[str, int, str, float | None]:
        started = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_sec)
        try:
            code = sock.connect_ex((target, port))
            latency_ms = (time.perf_counter() - started) * 1000.0
            if code == 0:
                return target, port, "open", latency_ms
            return target, port, "closed", latency_ms
        except OSError:
            return target, port, "error", None
        finally:
            sock.close()

    @classmethod
    def _risk_for(cls, port: int, state: str) -> str:
        if state != "open":
            return "low"
        return "high" if port in cls.HIGH_RISK_PORTS else "medium"

    @classmethod
    def _recommendations(cls, findings: List[PortFinding], errors: List[str]) -> List[str]:
        recommendations: List[str] = []
        open_ports = [item for item in findings if item.state == "open"]
        risky = [item for item in open_ports if item.port in cls.HIGH_RISK_PORTS]

        if risky:
            recommendations.append("Limit exposure of high-risk ports with ACL, firewall, or zero-trust policy.")
            recommendations.append("Enable MFA and strong auth for management services (SSH/RDP/DB).")
        elif open_ports:
            recommendations.append("Review open ports and close services not required by business.")
        else:
            recommendations.append("No open ports detected in current scan scope; keep periodic active checks.")

        if errors:
            recommendations.append("Some targets returned probe errors; retry with approved network path and timeout.")
        return recommendations

    def run(self, payload: ActiveScanInput | Dict[str, object]) -> ActiveScanOutput:
        request = self._coerce_payload(payload)
        started_at = utc_now_iso()
        started_perf = time.perf_counter()

        findings: List[PortFinding] = []
        errors: List[str] = []
        timeout_sec = request.timeout_ms / 1000.0

        tasks = [(target, int(port)) for target in request.targets for port in request.tcp_ports]
        worker_count = min(max(1, request.max_workers), max(1, len(tasks)))

        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            futures = {
                pool.submit(self._probe_tcp, target, port, timeout_sec): (target, port)
                for target, port in tasks
            }
            for future in as_completed(futures):
                target, port = futures[future]
                try:
                    host, scanned_port, state, latency = future.result()
                    findings.append(
                        PortFinding(
                            target=host,
                            port=scanned_port,
                            protocol="tcp",
                            state=state,
                            latency_ms=round(latency, 2) if latency is not None else None,
                            service=self.SERVICE_HINTS.get(scanned_port, "unknown"),
                            risk=self._risk_for(scanned_port, state),
                        )
                    )
                except Exception as exc:  # pragma: no cover
                    errors.append(f"{target}:{port} probe failed: {exc}")

        findings.sort(key=lambda item: (item.target, item.port))
        open_ports = [item for item in findings if item.state == "open"]
        high_risk_open_ports = [item for item in open_ports if item.port in self.HIGH_RISK_PORTS]

        finished_at = utc_now_iso()
        duration_ms = int((time.perf_counter() - started_perf) * 1000)

        summary = {
            "target_count": len(request.targets),
            "port_count_per_target": len(request.tcp_ports),
            "total_probes": len(tasks),
            "open_port_count": len(open_ports),
            "high_risk_open_port_count": len(high_risk_open_ports),
            "error_count": len(errors),
        }

        return ActiveScanOutput(
            source=request.source,
            trace_id=request.trace_id,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            summary=summary,
            findings=findings,
            recommendations=self._recommendations(findings, errors),
            errors=errors,
        )

    def run_batch(self, payloads: Iterable[ActiveScanInput | Dict[str, object]]) -> List[ActiveScanOutput]:
        return [self.run(item) for item in payloads]
