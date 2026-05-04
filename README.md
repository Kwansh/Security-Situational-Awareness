# 网络安全态势感知系统

这是一个面向多智能体拆分的网络安全检测项目，当前已经按“被动检测”和“主动检测”分模块整理，并支持 `PCAP` 直接训练。

## 项目目标

- `1. 抓包 + pcap 解析 + 特征提取`
- `2. 被动攻击检测智能体`
- `3. 主动检测 / 扫描智能体`
- `4. RAG + LLM 语义分析智能体`
- `5. 前端展示界面`
- `6. 中枢 agent`

当前你主要负责：

- `2. 被动攻击检测`
- `3. 主动检测`

## 目录说明

```text
security-situational-awareness-ultimate/
├─ agents/
│  ├─ attack_detection_agent/     # 被动攻击检测 agent
│  ├─ active_detection_agent/     # 主动检测 agent
│  ├─ INTERFACE_CONTRACT.md       # 和同学1的对接接口说明
│  └─ README.md                   # 模块拆分说明
├─ scripts/
│  └─ train.py                    # 训练入口，支持 csv / pcap
├─ src/
│  ├─ api/server.py               # FastAPI 服务
│  ├─ data/pcap_dataset.py        # PCAP 直读训练数据加载
│  ├─ data/feature_extractor.py   # 特征提取
│  ├─ detection/                  # 现有被动检测核心逻辑
│  ├─ explainability/             # 攻击解释
│  ├─ models/                     # 模型训练与集成
│  └─ preprocess/                 # 数据预处理
├─ run_api.py                     # 启动 API 服务
├─ requirements.txt               # 依赖
└─ results/                       # 输出结果
```

## 模块对应功能

### 被动攻击检测

位置：

- `agents/attack_detection_agent/agent.py`
- `agents/attack_detection_agent/schemas.py`
- 现有检测核心在 `src/detection/`
- 现有解释模块在 `src/explainability/attack_explainer.py`

职责：

- 输入流量特征或 CIC 风格记录
- 输出攻击类型、置信度、规则证据和解释
- 适合做“被动检测”

### 主动检测

位置：

- `agents/active_detection_agent/agent.py`
- `agents/active_detection_agent/schemas.py`

职责：

- 输入目标 IP 和端口列表
- 做主动探测和扫描
- 输出 open port、风险等级、延迟和建议

### PCAP 直训

位置：

- `src/data/pcap_dataset.py`
- `scripts/train.py`

职责：

- 直接读取 `pcap`
- 生成训练所需的流特征 `DataFrame`
- 通过 `label_manifest` 对每个 pcap 做标签映射

说明：

- 现在推荐 `PCAP -> 直接训练`
- 不再要求先手工转成 CSV
- 仍然保留 CSV 模式，方便旧数据兼容

## 如何运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 训练模型

CSV 模式：

```bash
python scripts/train.py --input_format csv --data_dir data/raw --output_dir data/models
```

PCAP 直训模式：

```bash
python scripts/train.py --input_format pcap --data_dir data/raw/pcap --label_manifest data/raw/label_manifest.json --output_dir data/models
```

如果你的标签清单是 CSV，也支持：

```bash
python scripts/train.py --input_format pcap --data_dir data/raw/pcap --label_manifest data/raw/label_manifest.csv --output_dir data/models
```

训练产物规则：

- 每次训练都会生成一个时间戳文件，例如 `model_artifacts_20260424_153012_123456.pkl`
- 同时更新一个固定最新文件 `model_artifacts_latest.pkl`
- 这样既保留历史模型，也不会影响 API 默认加载最新版本
- 同时会写入 `data/models/model_registry.json`，记录每次训练的版本、路径和指标摘要

回滚命令：

```bash
python scripts/rollback_model.py --list
python scripts/rollback_model.py --steps 1
python scripts/rollback_model.py --target data/models/model_artifacts_20260424_153012_123456.pkl
```

- `--list` 会打印可回滚的历史版本
- `--steps 1` 表示回滚到上一个历史版本
- `--target` 可以直接指定某个历史模型文件

验证旧模型/外来模型：

```bash
python scripts/evaluate_model.py --input your_labeled_test.csv --artifact data/models/model_artifacts_latest.pkl --output-dir results/eval
```

- `--input` 必须是带标签的测试集
- `--artifact` 可以替换成别人给你的 `pkl` 路径
- 输出会包含 accuracy / precision / recall / f1、混淆矩阵和预测明细

PCAP 文件说明：

- 现在支持 `.pcap`、`.pcapng`、`.cap` 和无后缀的原始抓包文件
- 但训练时仍然需要 `label_manifest`，因为模型必须知道每个文件对应什么标签

如果你想看当前模型账本，也可以通过：

- `GET /health`
- `GET /metadata`

它们会返回 registry 路径、当前 active 模型和历史条数。

### 3. 启动 API 服务

```bash
python run_api.py --host 0.0.0.0 --port 8000
```

浏览器打开：

- `http://localhost:8000/`
- `http://localhost:8000/docs`

## API 接口

### 检查类接口

- `GET /health`
  - 检查服务是否正常
  - 返回模型是否加载
- `GET /metadata`
  - 查看模型元信息
  - 包括特征列和标签映射

### 预测类接口

- `POST /predict`
  - 单条预测
  - 支持 `features` 或 `record`
- `POST /predict/batch`
  - 批量预测
  - 适合上传 CSV 文件
- `POST /batch`
  - `predict/batch` 的别名

### 可解释接口

- `POST /api/explain`
  - 输出攻击解释
  - 返回规则证据、风险摘要、建议

### 主动检测接口

- `POST /api/active-scan`
  - 对目标主机做主动探测
  - 返回端口状态、风险等级、延迟和建议

### 仪表盘接口

- `GET /dashboard`
- `GET /dashboard/summary`
- `GET /dashboard/events`
- `GET /dashboard/events/delta`
- `GET /stream/events`
- `WS /ws`
- `WS /ws/stream`

### 管理接口

- `POST /admin/reload-model`
  - 重新加载模型产物
- `POST /admin/reset-events`
  - 清空历史事件

## Agent 接口

### 被动攻击检测 Agent

调用：

```python
from agents.attack_detection_agent import AttackDetectionAgent

agent = AttackDetectionAgent()
result = agent.run({
    "source": "agent1",
    "trace_id": "demo-001",
    "features": {
        "pkt_rate": 1200,
        "syn_rate": 700,
        "udp_rate": 30,
        "dns_rate": 10,
        "ntp_rate": 0,
        "avg_pkt_size": 320
    }
})
```

输出：

- `is_attack`
- `attack_type`
- `confidence`
- `severity`
- `summary`
- `recommendations`
- `dynamic_metrics`
- `rule_evidence`

### 主动检测 Agent

调用：

```python
from agents.active_detection_agent import ActiveDetectionAgent

agent = ActiveDetectionAgent()
result = agent.run({
    "trace_id": "scan-001",
    "targets": ["127.0.0.1"],
    "tcp_ports": [22, 80, 443]
})
```

输出：

- `summary`
- `findings`
- `recommendations`
- `errors`

## 和同学1的对接建议

推荐同学1提供两类输入：

### 训练数据

- `pcap` 文件
- `label_manifest.json` 或 `label_manifest.csv`

### 在线检测

- 已提取好的 `features`
- 或者 `record` 形式的 CIC 行数据

推荐对接文档：

- [agents/INTERFACE_CONTRACT.md](agents/INTERFACE_CONTRACT.md)

## 依赖补充

PCAP 直训新增依赖：

- `dpkt`

## 当前状态

- 主 README 已更新为模块总说明
- 被动检测和主动检测已经分开目录
- 训练入口支持 `csv` / `pcap`
- PCAP 直读训练已接入标签清单机制
- 训练产物已改为“时间戳历史文件 + latest 最新文件”
- 已新增回滚脚本，支持查看历史版本和回滚到指定模型
- 已新增 `model_registry.json`，记录训练与回滚后的当前激活版本
