# API 前端对接手册（可直接落地）

本文专门面向前端同学，说明如何快速接入本项目 API。

## 1. 联调前准备

1. 启动 API

```bash
python run_api.py --host 0.0.0.0 --port 8000
```

2. 验证服务可用

```bash
curl http://localhost:8000/health
```

3. 打开文档

- Swagger: `http://localhost:8000/docs`
- Dashboard: `http://localhost:8000/`

## 2. 推荐前端接入架构

使用三条链路组合：

- 交互分析：`POST /predict`
- 文件分析：`POST /predict/batch`
- 实时更新：`WS /ws`

统计看板用轮询：

- `GET /dashboard/summary`
- `GET /dashboard/events`

## 3. 接口总览（前端最常用）

| 接口 | 方法 | 说明 |
|---|---|---|
| `/health` | GET | 服务/模型健康检查 |
| `/metadata` | GET | 特征列、标签映射、指标 |
| `/predict` | POST | 单条检测（features 或 record） |
| `/predict/batch` | POST | CSV 批量检测 |
| `/dashboard/summary` | GET | 统计摘要 |
| `/dashboard/events` | GET | 最近事件 |
| `/ws` | WebSocket | 实时检测 |
| `/api/explain` | POST | 规则解释（无模型推理） |

## 4. 前端类型定义（TypeScript）

```ts
export type Dict = Record<string, unknown>;

export interface PredictRequest {
  features?: number[] | Dict;
  record?: Dict;
  source?: string;
}

export interface PredictResponse {
  prediction: number;
  prediction_label: string;
  attack_type: string;
  confidence: number;
  is_attack: boolean;
  probabilities: number[] | null;
  timestamp: string;
  explanation: {
    attack_type: string;
    severity: string;
    summary: string;
    details: string[];
    recommendations: string[];
    technical_details?: Dict;
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
    alert?: Dict;
  };
}

export interface DashboardSummary {
  total_events: number;
  attack_events: number;
  benign_events: number;
  attack_ratio: number;
  labels: Record<string, number>;
  sources: Record<string, number>;
  last_event: Dict | null;
}
```

## 5. 统一请求封装（fetch）

```ts
const API_BASE = "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, init);
  if (!resp.ok) {
    let detail = "";
    try {
      const json = await resp.json();
      detail = json?.detail ? ` - ${json.detail}` : "";
    } catch {}
    throw new Error(`HTTP ${resp.status}${detail}`);
  }
  return resp.json() as Promise<T>;
}
```

## 6. 单条检测接入

```ts
export function predictOne(payload: PredictRequest) {
  return request<PredictResponse>("/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, source: payload.source ?? "frontend" }),
  });
}
```

建议优先传 `record`（原始字段），由服务端统一预处理，前端更稳定。

## 7. 批量检测接入

```ts
export async function predictBatch(file: File, source = "frontend_batch") {
  const form = new FormData();
  form.append("file", file);
  return request<{
    total: number;
    predictions: Dict[];
    dashboard_summary: DashboardSummary;
    batch_alert: Dict | null;
  }>(`/predict/batch?source=${encodeURIComponent(source)}`, {
    method: "POST",
    body: form,
  });
}
```

## 8. Dashboard 轮询接入

```ts
export function getSummary() {
  return request<DashboardSummary>("/dashboard/summary");
}

export function getEvents(limit = 100) {
  return request<{ events: Dict[]; count: number }>(`/dashboard/events?limit=${limit}`);
}

export function startPolling(onTick: (data: { summary: DashboardSummary; events: Dict[] }) => void) {
  const timer = setInterval(async () => {
    const [summary, eventsResp] = await Promise.all([getSummary(), getEvents(50)]);
    onTick({ summary, events: eventsResp.events });
  }, 3000);
  return () => clearInterval(timer);
}
```

## 9. WebSocket 实时接入

```ts
type WsMessage = PredictResponse & { dashboard_summary?: DashboardSummary; error?: string };

export function createRealtimeSocket(onMessage: (msg: WsMessage) => void) {
  const ws = new WebSocket("ws://localhost:8000/ws");

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data) as WsMessage;
    onMessage(data);
  };

  function sendRecord(record: Dict, source = "frontend_ws") {
    ws.send(JSON.stringify({ record, source }));
  }

  function sendFeatures(features: Dict | number[], source = "frontend_ws") {
    ws.send(JSON.stringify({ features, source }));
  }

  return { ws, sendRecord, sendFeatures };
}
```

## 10. 错误处理策略（前端必做）

1. `503 Model artifacts are not loaded`
- 页面提示“模型未加载”
- 引导运维检查 `/health` 与模型文件

2. `422` 参数错误
- 提示“输入格式错误”
- 展示后端 `detail` 原文，便于排查字段

3. WebSocket 返回 `{ error: "..." }`
- 不要断开连接，展示错误后允许用户继续发送

## 11. 跨域与网关建议

当前 API 未显式配置 `CORSMiddleware`。

建议选其一：

1. 前后端同域部署（Nginx 反向代理，推荐）
2. 在后端增加 CORS 白名单配置

开发阶段可用前端 dev server 代理（`/api` -> `http://localhost:8000`）。

## 12. 最小可用联调顺序

1. 调 `/health`，确认服务可用
2. 调 `/predict`，验证单条结果
3. 调 `/dashboard/summary`，确认统计更新
4. 接入 `/predict/batch` 文件上传
5. 最后接入 `WS /ws` 做实时能力

这样能最快形成可演示闭环。

