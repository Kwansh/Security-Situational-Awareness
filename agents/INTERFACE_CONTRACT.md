# Agent Interface Contract (Team Split)

This file defines the integration contract for:
- Agent 1: packet capture + pcap parsing + feature extraction
- Agent 2: passive attack detection (this repo module)
- Agent 3: active detection / scanning (this repo module)
- Hub Agent: orchestration

## 1) Responsibility Boundary

- Agent 2 (you): `agents/attack_detection_agent`
  - Passive detection only
  - Input: feature payload or CIC-style record payload
  - Output: attack verdict + explanation + rule evidence
- Agent 3 (you): `agents/active_detection_agent`
  - Active probing/scanning
  - Input: target hosts + port list
  - Output: open-port findings + risk summary

## 2) What You Need From Agent 1

Agent 1 can provide data through either of the following compatible interfaces:

### Interface A: `features` payload (recommended for online inference)

Required keys:
- `pkt_rate`
- `syn_rate`
- `udp_rate`
- `dns_rate`
- `ntp_rate`
- `avg_pkt_size`

Optional keys:
- `window_seconds`
- `payload` or `http_payload` (for SQL-injection rule evidence)
- `trace_id`
- `timestamp`

Example:

```json
{
  "source": "agent1_pcap_parser",
  "trace_id": "cap-20260423-001",
  "features": {
    "pkt_rate": 1240.0,
    "syn_rate": 730.0,
    "udp_rate": 42.0,
    "dns_rate": 15.0,
    "ntp_rate": 0.0,
    "avg_pkt_size": 318.4,
    "window_seconds": 1
  }
}
```

### Interface B: `record` payload (CIC row style, good for model training/inference reuse)

Required minimal keys for rule/metric compatibility:
- `Destination Port`
- `Source Port`
- `Protocol`
- `SYN Flag Count`
- `Packet Length Mean`

Strongly recommended keys:
- `Timestamp`
- `Flow Duration`
- `Flow Packets/s`
- `Label` (required for training dataset, optional for inference)

Example:

```json
{
  "source": "agent1_pcap_parser",
  "trace_id": "cap-20260423-002",
  "record": {
    "Timestamp": "2026-04-23 10:10:01",
    "Destination Port": 443,
    "Source Port": 51023,
    "Protocol": 6,
    "SYN Flag Count": 1,
    "Packet Length Mean": 512.0,
    "Flow Duration": 300000,
    "Flow Packets/s": 220.0
  }
}
```

## 3) File-Level Contract for Training Data (pcap -> csv)

If Agent 1 delivers CSV files for training:
- Encoding: UTF-8
- File extension: `.csv`
- Naming: `<capture_id>.csv` (same basename as pcap preferred)
- Minimum columns for training:
  - all model input columns produced by current preprocessing pipeline
  - label column `Label` (or a consistently mapped equivalent)

Recommended directory handoff:
- `data/raw/agent1_exports/`

## 4) Agent 2 Output Contract

`AttackDetectionAgent.run()` returns:
- `is_attack` (bool)
- `attack_type` (string)
- `confidence` (float)
- `severity` (string)
- `summary` (string)
- `recommendations` (list)
- `dynamic_metrics` (dict: pkt_len/syn_count/udp_count, etc.)
- `rule_evidence` (list of triggered rules)
- `raw_result` (full internal output for debugging)

## 5) Agent 3 Output Contract

`ActiveDetectionAgent.run()` returns:
- `summary`:
  - `target_count`
  - `port_count_per_target`
  - `total_probes`
  - `open_port_count`
  - `high_risk_open_port_count`
  - `error_count`
- `findings`: list of `{target, port, protocol, state, latency_ms, service, risk}`
- `recommendations`
- `errors`

## 6) Hub Agent Integration

Hub agent should call:
- `AttackDetectionAgent.run(...)` for passive data path
- `ActiveDetectionAgent.run(...)` for proactive scan path

and merge outputs by:
- `trace_id`
- `timestamp` window
- `source`

## 7) Important Note

Active detection must remain separate from passive detection in both:
- folder/module boundary
- runtime invocation path

Current split is implemented as:
- `agents/attack_detection_agent/`
- `agents/active_detection_agent/`

## 8) PCAP 训练标签清单

当 Agent 1 提供原始 `PCAP` 给训练流程时，需要额外给出标签清单，格式可以是 JSON 或 CSV。

### JSON 示例

```json
{
  "capture_001.pcap": "BENIGN",
  "capture_002.pcap": "SYN_FLOOD"
}
```

### CSV 示例

```csv
file,label
capture_001.pcap,BENIGN
capture_002.pcap,SYN_FLOOD
```

### 规则说明

- 一个 `PCAP` 文件只对应一个标签。
- `key` 可以写文件名、文件名去后缀，或者完整路径。
- 标签建议统一大写。
- 如果某个文件没有出现在清单里，训练时可能会回退为 `BENIGN`。

完整说明见：
- [docs/pcap_label_manifest_guide.md](../docs/pcap_label_manifest_guide.md)
