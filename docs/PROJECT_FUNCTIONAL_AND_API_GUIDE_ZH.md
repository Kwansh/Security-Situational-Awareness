# 网络安全态势感知系统文档（按功能划分）

## 1. 项目定位

本项目是一个融合规则检测与机器学习检测的网络安全态势感知系统，核心能力包括：

- 离线训练与评估（多模型、集成学习）
- 在线增量训练与模型热更新
- 单条/批量/实时（WebSocket）攻击检测
- 攻击解释、事件日志、告警通知、Dashboard 统计
- 面向前端的标准 HTTP + WebSocket 接口

当前 API 主版本：`4.1.0`。

## 2. 核心目录（业务相关）

```text
config/                  # YAML 配置
src/
  api/                   # FastAPI 服务与路由
  data/                  # 数据加载与特征提取
  preprocess/            # 数据预处理
  detection/             # 规则/ML/融合检测
  models/                # 训练、集成、在线训练
  explainability/        # 攻击解释
  utils/                 # 配置、评估、日志、告警、模型产物
scripts/                 # 训练、预测、在线训练、模型替换等脚本
data/                    # 原始数据、模型产物
results/                 # 评估图、实时检测结果
run_api.py               # API 启动入口
```

## 3. 按功能模块说明

## 3.1 数据加载模块（`src/data/loader.py`）

类：`DatasetLoader`

主要能力：

- 递归加载 `data_dir` 下全部 CSV
- 支持 `max_files`、`max_rows_per_file`、`chunk_size` 限流，避免一次性爆内存
- 自动跳过异常行（`on_bad_lines="skip"`）
- 自动下采样数值类型（减小内存占用）

常用调用场景：

- 训练脚本 `scripts/train.py`、`scripts/train_advanced.py`
- 在线训练 `src/models/online_trainer.py`

## 3.2 特征提取模块（`src/data/feature_extractor.py`）

类：`FeatureExtractor`

支持三种模式：

- `standard`：提取 6 个标准统计特征
  - `pkt_rate`
  - `syn_rate`
  - `udp_rate`
  - `dns_rate`
  - `ntp_rate`
  - `avg_pkt_size`
- `full`：保留全部数值列（排除标识列/标签列）
- `hybrid`：标准特征 + 全量统计特征融合

典型用途：

- 特征离线抽取脚本：`scripts/extract_features.py`
- 模型训练前的特征工程

## 3.3 预处理模块（`src/preprocess/preprocessor.py`）

类：`Preprocessor`

主要能力：

- 清理列名、处理 `inf/-inf`
- 自动识别并编码类别特征
- 自动识别时间列并转数值
- 填充缺失值（按列中位数）
- 保存 `feature_columns`，保证训练/推理列对齐
- 标签编码（字符串标签 -> 整数）
- 标准化（`StandardScaler`）

在训练和 API 推理中都被复用，是输入一致性的关键模块。

## 3.4 规则检测模块（`src/detection/rule_engine.py`）

类：`RuleEngine`

支持检测：

- SYN Flood
- UDP Flood
- DNS Flood
- NTP Flood
- SQL Injection 关键词模式
- 高包速 + 小包长异常流量

输出结构：`RuleDetectionResult`，包含：

- 是否攻击 `is_attack`
- 攻击类型 `attack_type`
- 置信度 `confidence`
- 触发规则明细 `triggers`
- 解释文本 `explanation`

阈值由 `config/config.yaml` 的 `rule_thresholds` 控制。

## 3.5 机器学习检测模块（`src/detection/ml_detector.py`）

类：`MLDetector`

主要能力：

- 加载模型产物（支持裸模型和字典包）
- 单条/批量预测
- 概率输出（如果模型支持 `predict_proba`）
- 标签解码（根据 `label_mapping`）

判定“正常”标签集合：`normal/benign/0`。

## 3.6 融合检测模块（`src/detection/hybrid_detector.py`）

类：`HybridDetector`

支持模式：

- `rule_only`
- `ml_only`
- `hybrid`

融合策略：

- `weighted`（加权融合，默认）
- `voting`（投票融合）

返回 `FusionDetectionResult`，包含规则与模型双侧证据，适合后续解释展示。

## 3.7 可解释模块（`src/explainability/attack_explainer.py`）

类：`AttackExplainer`

输出结构：`AttackExplanation`，包含：

- 攻击类型、严重度
- 人类可读摘要（summary）
- 明细证据（details）
- 处置建议（recommendations）
- 技术细节（technical_details）

API `/predict` 和 `/api/explain` 都使用了该模块。

## 3.8 训练与评估模块

核心文件：

- `src/models/trainer.py`：多模型训练（RF/XGBoost/ExtraTrees/LightGBM）
- `src/models/ensemble.py`：软投票/Stacking 集成
- `src/utils/feature_selector.py`：`SelectKBest` 特征筛选
- `src/utils/evaluator.py`：指标与图表输出（混淆矩阵、指标柱图等）

离线训练入口：

- `scripts/train.py`（主训练脚本）
- `scripts/train_advanced.py`（高级训练包装）

训练结果产物：

- `data/models/model_artifacts.pkl`
- `data/models/metrics.json`
- `results/figures/*.png`

## 3.9 在线训练与热更新模块

核心文件：`src/models/online_trainer.py` + `scripts/train_online.py`

流程：

1. 从增量 CSV 缓冲窗口数据
2. 复用离线训练管线训练新模型
3. 原子方式替换 `model_artifacts.pkl`
4. 保存 `online_metrics.json` 与可视化图

API 服务侧默认有模型文件 watcher，会轮询自动加载新产物。

## 3.10 事件日志与告警模块

核心文件：

- `src/utils/detection_logger.py`
- `src/utils/alert.py`

事件日志落盘位置：

- `results/realtime/detections.jsonl`
- `results/realtime/latest_events.json`
- `results/realtime/summary.json`
- `results/realtime/attack_timeline.csv`

告警支持：

- webhook
- 企业微信机器人
- email
- sms（通过 webhook 接口）

开关与模板在 `config/config.yaml` 的 `alerting` 下配置。

## 3.11 API 模块（`src/api/server.py`）

### 3.11.1 服务职责

- 对外提供检测接口（HTTP + WS）
- 提供 Dashboard 数据接口
- 提供管理接口（热重载、事件清理）
- 接入解释模块、日志模块、告警模块

### 3.11.2 运行方式

```bash
python run_api.py --host 0.0.0.0 --port 8000
```

启动后：

- Swagger: `http://localhost:8000/docs`
- Dashboard: `http://localhost:8000/`
- 健康检查: `http://localhost:8000/health`

---

## 4. API 使用说明（重点）

Base URL：`http://localhost:8000`

## 4.1 健康与模型信息

1. `GET /health`
- 用途：检查服务和模型加载状态
- 典型返回字段：
  - `status`: `ok` 或 `rule_only`
  - `model_loaded`: 是否加载模型
  - `feature_count`: 特征数

2. `GET /metadata`
- 用途：给前端动态获取模型元数据（特征列、标签映射、指标）
- 注意：模型未加载时返回 `503`

## 4.2 预测接口

1. `POST /predict`
- 用途：单条检测
- 请求体二选一：
  - `features`：数组或对象
  - `record`：原始流量记录对象（推荐，服务端会走 `preprocessor`）
- 可选字段：
  - `source`：来源标识（默认 `api`）

请求示例（record）：

```json
{
  "record": {
    "Flow Duration": 1200,
    "Total Fwd Packets": 20,
    "Total Backward Packets": 10,
    "Flow Bytes/s": 9000.5,
    "Protocol": 6
  },
  "source": "frontend_form"
}
```

典型响应字段：

- `prediction`
- `prediction_label`
- `attack_type`
- `confidence`
- `is_attack`
- `probabilities`
- `explanation`（summary/details/recommendations）
- `event`（写入日志后的事件对象）

2. `POST /predict/batch`（别名：`POST /batch`）
- 用途：CSV 批量检测
- 请求格式：`multipart/form-data`
  - `file`: CSV 文件（必填）
  - `source`: 来源（可选，query 参数）
- 返回：
  - `predictions`（逐行结果）
  - `dashboard_summary`
  - `batch_alert`

## 4.3 Dashboard 与事件

1. `GET /dashboard/summary`
- 返回累计统计：总数、攻击数、攻击占比、标签分布、来源分布

2. `GET /dashboard/events?limit=100`
- 返回最近事件列表，适合前端表格轮询

3. `GET /dashboard`
- `Accept: text/html` 时返回内置 Dashboard 页面
- 默认 JSON 返回 `{summary, events, count}`

## 4.4 实时接口（WebSocket）

`WS /ws`

发送消息格式：

```json
{
  "record": {
    "Flow Duration": 1200,
    "Protocol": 6
  },
  "source": "frontend_ws"
}
```

服务端回推：

- 检测结果
- `event`
- `dashboard_summary`

出错时返回：

```json
{
  "error": "..."
}
```

## 4.5 管理接口

1. `POST /admin/reload-model`
- 强制重新加载模型产物

2. `POST /admin/reset-events?archive=true`
- 清空实时事件历史
- `archive=true` 时会先归档旧文件

## 4.6 解释接口（扩展路由）

`POST /api/explain`

用途：仅基于规则引擎生成解释结果（无需模型预测）。

---

## 5. 给前端怎么接（实战）

## 5.1 推荐对接方式

前端建议同时接三类接口：

- 表单/单条分析：`POST /predict`
- 文件分析：`POST /predict/batch`
- 实时流：`WS /ws`

统计展示建议：

- 每 2~5 秒轮询 `GET /dashboard/summary` 和 `GET /dashboard/events`

## 5.2 TypeScript 类型建议

```ts
export interface PredictResponse {
  prediction: number;
  prediction_label: string;
  attack_type: string;
  confidence: number;
  is_attack: boolean;
  probabilities: number[] | null;
  explanation: {
    attack_type: string;
    severity: string;
    summary: string;
    details: string[];
    recommendations: string[];
    technical_details?: Record<string, unknown>;
  };
  event: {
    timestamp: string;
    prediction: number;
    prediction_label: string;
    confidence: number;
    is_attack: boolean;
    severity: string;
    source: string;
    input_kind: string;
  };
}
```

## 5.3 HTTP 调用示例（前端）

```ts
export async function predictByRecord(record: Record<string, unknown>) {
  const resp = await fetch("http://localhost:8000/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ record, source: "web_frontend" }),
  });
  if (!resp.ok) throw new Error(`predict failed: ${resp.status}`);
  return resp.json();
}
```

## 5.4 批量上传示例

```ts
export async function batchPredict(file: File) {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch("http://localhost:8000/predict/batch?source=web_upload", {
    method: "POST",
    body: form,
  });
  if (!resp.ok) throw new Error(`batch failed: ${resp.status}`);
  return resp.json();
}
```

## 5.5 WebSocket 示例

```ts
const ws = new WebSocket("ws://localhost:8000/ws");

ws.onopen = () => {
  ws.send(
    JSON.stringify({
      record: { "Flow Duration": 1200, Protocol: 6 },
      source: "websocket_panel",
    })
  );
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data.error 存在时做错误提示
  // 正常时更新实时卡片和表格
};
```

## 5.6 前端展示字段建议

高优先字段：

- `attack_type`
- `confidence`
- `is_attack`
- `explanation.summary`
- `explanation.recommendations`

运营统计字段：

- `dashboard_summary.attack_ratio`
- `dashboard_summary.labels`
- `dashboard_summary.sources`

## 5.7 联调注意事项（非常重要）

1. 模型未加载时，`/predict` 可能返回 `503`。
- 先检查 `/health` 的 `model_loaded`。

2. 跨域（CORS）默认未显式配置。
- 前后端跨域部署时，建议：
  - 同域反向代理（推荐），或
  - 在 API 中增加 `CORSMiddleware`。

3. 输入字段不完整会返回 `422`。
- 推荐前端优先传 `record` 原始列，让服务端统一预处理。

4. 批量接口是 `multipart/form-data`，不是 JSON。

---

## 6. 典型业务流程

## 6.1 离线训练到上线

1. 准备 CSV 到 `data/raw`
2. 执行训练脚本生成 `model_artifacts.pkl`
3. 启动 API（`run_api.py`）
4. 前端接 `/predict`、`/dashboard/*`、`/ws`

## 6.2 在线更新

1. 运行 `scripts/train_online.py`
2. 新模型原子替换
3. API watcher 自动发现并加载
4. 前端无感继续调用

---

## 7. 常用脚本速查

```bash
# 离线训练
python scripts/train.py --data_dir data/raw --output_dir data/models

# 高级训练
python scripts/train_advanced.py --input data/raw --models auto --use-stacking

# 在线训练+热替换
python scripts/train_online.py --data_dir data/raw --artifact_path data/models/model_artifacts.pkl

# 批量预测
python scripts/predict.py --input data/raw/sample.csv --output results/predictions.csv

# 回放数据到 API，制造实时事件
python scripts/replay_events.py --input data/raw --api-base http://127.0.0.1:8000 --max-rows 2000

# 手工替换模型
python scripts/swap_model.py --new-model data/models/new_model.pkl
```

---

## 8. 测试说明

测试目录：`tests/`

覆盖方向：

- API 冒烟测试（`test_api.py`）
- 规则引擎测试（`test_rules.py`）
- 训练流水线测试（`test_pipeline.py`）
- 在线训练/告警测试（`test_online_features.py`）

执行方式：

```bash
pytest -q
```

---

## 9. 部署说明（简版）

Docker 启动：

```bash
docker compose up --build -d
```

容器健康检查地址：

- `http://localhost:8000/health`

镜像默认挂载：

- `./data -> /app/data`
- `./results -> /app/results`

