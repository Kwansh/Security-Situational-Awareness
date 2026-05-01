<<<<<<< HEAD
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
=======
﻿# 安全态势感知项目

一个基于 Python、scikit-learn 和 FastAPI 的 DDoS 流量识别项目。当前版本已经打通了从数据加载、预处理、特征选择、模型训练、模型保存，到 REST API / WebSocket 推理、批量预测与自动化测试的完整链路。

## 1. 项目背景

本项目面向网络安全场景中的 DDoS 攻击识别任务，目标是对网络流量特征进行分类，判断当前流量是否属于正常流量或某一类攻击流量，并提供可复现的训练流程和可直接调用的推理接口。

项目当前更偏向“可运行、可验证、可继续迭代”的工程版本，而不是只停留在论文式描述或演示代码层面。

## 2. 使用的数据集

当前仓库中的原始数据位于 `data/raw/`，主要使用的是 **CIC-DDoS2019** 风格的 CSV 流量特征数据。你当前目录下已经存在多类攻击样本，例如：

- `LDAP.csv`
- `MSSQL.csv`
- `NetBIOS.csv`
- `Portmap.csv`
- `Syn.csv`
- `UDP.csv`
- `UDPLag.csv`

这些 CSV 文件通常包含网络流的统计特征，例如：

- `Flow Duration`
- `Total Fwd Packets`
- `Total Backward Packets`
- `Flow Bytes/s`
- `Packet Length Mean`
- `SYN Flag Count`
- `ACK Flag Count`
- `Label`

其中 `Label` 列作为监督学习标签，其他数值型流量特征作为模型输入。

## 3. 当前实现了什么

### 3.1 数据处理

项目当前已经实现以下数据处理步骤：

- 递归读取 `data/raw/` 下的 CSV 文件
- 自动跳过锁文件等无效文件
- 清洗列名中的空格和格式问题
- 将 `inf/-inf` 转为缺失值
- 删除明显不适合直接建模的字段，如 IP、端口、时间戳、流 ID 等
- 将剩余字段尽量转换为数值型
- 用中位数填充缺失值
- 自动识别字符串标签并映射为整数类别
- 保存训练时实际使用的特征列名，保证推理阶段与训练阶段一致

### 3.2 特征工程

当前版本使用了基于 `SelectKBest + f_classif` 的过滤式特征选择方法：

- 先对特征做标准化
- 再进行单变量统计特征筛选
- 默认保留前 `30` 个最有区分度的特征
- 若特征数本来就少于 `k`，则自动保留全部

### 3.3 模型训练

当前训练流程在 `[scripts/train.py](F:/security-situational-awareness-ultimate/scripts/train.py)` 中实现，核心步骤如下：

1. 加载 CSV 数据
2. 进行预处理和标签编码
3. 划分训练集和测试集
4. 对训练集拟合标准化器
5. 在训练集上拟合特征选择器
6. 训练基础模型
7. 构建集成模型
8. 在测试集上评估 Accuracy / Precision / Recall / F1
9. 将模型和预处理组件统一保存为 artifact

当前基础模型包括：

- RandomForest
- XGBoost（如果环境中已安装）

当前集成方式支持：

- Voting
- Stacking

默认使用的训练脚本是：

```bash
python -m scripts.train --input data/raw --output data/models/model_artifacts.pkl
```

如果只想快速验证流程，可以限制只读取少量文件：

```bash
python -m scripts.train --input data/raw --output data/models/model_artifacts.pkl --max_files 1
```

### 3.4 模型产物管理

训练完成后，会保存统一模型产物文件：

- `data/models/model_artifacts.pkl`

其中包含：

- 训练好的集成模型
- 标准化器 `scaler`
- 特征选择器 `selector`
- 训练时使用的特征列名
- 标签映射关系
- 评估指标

相比把模型、缩放器、选择器分散保存在多个文件中，这种方式更方便部署和推理阶段统一加载。

### 3.5 API 推理服务

API 服务在 `[src/api/server.py](F:/security-situational-awareness-ultimate/src/api/server.py)` 中实现，当前已经支持：

- `GET /health`：检查服务与模型是否加载成功
- `GET /metadata`：查看特征列、标签映射、训练指标
- `POST /predict`：单条样本预测
- `POST /predict/batch`：上传 CSV 进行批量预测
- `WebSocket /ws`：实时推理

启动方式：

```bash
python run_api.py
```

启动后可以访问：

- [http://localhost:8000/docs](http://localhost:8000/docs)
- [http://localhost:8000/health](http://localhost:8000/health)

### 3.6 批量预测脚本

批量预测脚本在 `[scripts/predict.py](F:/security-situational-awareness-ultimate/scripts/predict.py)` 中实现。

用法：

```bash
python -m scripts.predict --input your_test.csv --output results/predictions.csv --artifact data/models/model_artifacts.pkl
```

输出结果中会包含：

- `prediction`
- `prediction_label`
- `confidence`

### 3.7 自动化测试

当前已经补充并跑通两类测试：

- `[tests/test_pipeline.py](F:/security-situational-awareness-ultimate/tests/test_pipeline.py)`：验证训练流程和 artifact 保存
- `[tests/test_api.py](F:/security-situational-awareness-ultimate/tests/test_api.py)`：验证 API 模型加载与 `/predict` 接口

测试命令：

```bash
$env:PYTHONPATH = (Get-Location).Path
pytest tests/test_pipeline.py tests/test_api.py -p no:cacheprovider
```

在你当前环境里，这两项测试已经跑通。

## 4. 当前真实训练结果

你最近一次实际训练输出如下：

```json
{
  "accuracy": 0.9999692414710148,
  "precision": 0.9999692964062193,
  "recall": 0.9999692414710148,
  "f1": 0.9999692597484574
}
```

说明：

- 当前流程已经可以在你的数据上稳定完成训练
- 指标很高，说明数据本身区分度较强
- 但这不代表模型已经达到真实生产环境泛化上限
- 仍然需要结合交叉验证、独立测试集和类别分布分析进一步确认泛化能力

## 5. 你这次实际做了哪些操作

这次项目完善过程中，已经完成了以下工作：

- 修复了训练脚本中数据泄漏问题
- 统一了训练产物格式，改为 artifact 管理
- 修复了字符串标签无法正确编码的问题
- 修复了 API 与模型产物格式不一致的问题
- 补充了批量预测脚本
- 补充了自动化测试
- 修复了 FastAPI 新版本依赖下的兼容问题
- 让项目可以在你当前 Windows + PowerShell + `.venv` 环境中跑通

## 6. 项目目录说明

当前项目中比较关键的文件如下：

- `[scripts/train.py](F:/security-situational-awareness-ultimate/scripts/train.py)`：主训练脚本
- `[scripts/train_advanced.py](F:/security-situational-awareness-ultimate/scripts/train_advanced.py)`：高级训练入口
- `[scripts/predict.py](F:/security-situational-awareness-ultimate/scripts/predict.py)`：批量预测脚本
- `[src/preprocess.py](F:/security-situational-awareness-ultimate/src/preprocess.py)`：数据清洗与标签处理
- `[src/feature_selector.py](F:/security-situational-awareness-ultimate/src/feature_selector.py)`：特征筛选
- `[src/model_trainer.py](F:/security-situational-awareness-ultimate/src/model_trainer.py)`：基础模型训练
- `[src/ensemble_model.py](F:/security-situational-awareness-ultimate/src/ensemble_model.py)`：集成模型封装
- `[src/model_artifacts.py](F:/security-situational-awareness-ultimate/src/model_artifacts.py)`：模型产物保存与加载
- `[src/api/server.py](F:/security-situational-awareness-ultimate/src/api/server.py)`：推理 API
- `[run_api.py](F:/security-situational-awareness-ultimate/run_api.py)`：API 启动入口

## 7. 快速开始

### 7.1 安装依赖

```bash
pip install -r requirements.txt
pip install httpx python-multipart
```

### 7.2 运行测试

```bash
$env:PYTHONPATH = (Get-Location).Path
pytest tests/test_pipeline.py tests/test_api.py -p no:cacheprovider
```

### 7.3 训练模型

```bash
python -m scripts.train --input data/raw --output data/models/model_artifacts.pkl --max_files 1
```

### 7.4 启动 API

```bash
python run_api.py
```

### 7.5 调用单条预测接口

示例请求体：

```json
{
  "features": [2001, 6, 2, 4.0]
}
```

注意：

- 这里的 `features` 必须和训练时保留下来的特征数量一致
- 当前你的模型产物里可以通过 `/metadata` 查看需要的特征数量和列名
- 如果特征维度不一致，API 会返回 `422`

## 8. 已知限制

当前版本虽然已经能用，但仍存在一些现实限制：

- 还没有做交叉验证和更系统的实验记录
- 还没有加入模型版本号、训练时间、数据快照等更完整的元数据管理
- 还没有对类别不平衡做更深入处理
- 还没有接入真正的实时抓包或流式特征抽取模块
- 还没有完成生产级认证、限流、审计日志等安全能力
- README 之前提到的 Prometheus、Grafana、Optuna、规则引擎等能力，目前仓库中并未完整落地

## 9. 下一步改进方向

如果继续完善，这个项目最值得优先做的方向是：

### 方向 1：让训练更可靠

- 增加交叉验证
- 输出混淆矩阵和分类报告文件
- 保存每次训练的参数与结果日志
- 对不同攻击类别做单独评估

### 方向 2：让推理更实用

- 支持按列名自动对齐输入特征
- 对缺失列给出更友好的提示
- 增加 `/predict/proba` 或解释性接口
- 增加批量预测结果导出摘要

### 方向 3：让工程更完整

- 把训练参数放进 YAML 配置文件
- 增加结构化日志
- 增加模型版本管理
- 增加 Makefile 或一键脚本
- 增加 Docker 部署方案

### 方向 4：让安全场景更贴近真实环境

- 接入真实网络流量抓取
- 增加在线特征提取
- 对接告警系统
- 将预测结果接入态势感知看板

## 10. 总结

当前这个项目已经不是“只有文档看起来完整”的状态，而是已经具备以下可落地能力：

- 能基于 CIC-DDoS2019 风格数据进行训练
- 能保存统一 artifact 模型文件
- 能提供 REST API 和 WebSocket 推理
- 能做批量预测
- 能通过自动化测试验证主链路

如果后续继续打磨，它可以逐步升级为一个更完整的网络攻击检测与态势感知实验平台。
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
