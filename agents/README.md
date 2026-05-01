# Agents Split

This folder contains the multi-agent split implementation:

- `attack_detection_agent/`: passive detection wrapper (`run`, `run_batch`)
- `active_detection_agent/`: active scan/probe wrapper (`run`, `run_batch`)
- `INTERFACE_CONTRACT.md`: integration contract for team handoff
- `../docs/pcap_label_manifest_guide.md`: PCAP training label manifest spec

## Quick Usage

```python
from agents.attack_detection_agent import AttackDetectionAgent
from agents.active_detection_agent import ActiveDetectionAgent

attack_agent = AttackDetectionAgent()
active_agent = ActiveDetectionAgent()

passive_result = attack_agent.run(
    {
        "source": "agent1",
        "trace_id": "sample-001",
        "features": {
            "pkt_rate": 1200,
            "syn_rate": 700,
            "udp_rate": 30,
            "dns_rate": 10,
            "ntp_rate": 0,
            "avg_pkt_size": 320,
        },
    }
)

active_result = active_agent.run(
    {
        "trace_id": "sample-001",
        "targets": ["127.0.0.1"],
        "tcp_ports": [22, 80, 443],
    }
)
```
