# 前端接入说明

这份文档给前端同学看，目标是把当前已经新增和稳定下来的能力一次说清楚，方便你们直接接页面。

## 1. 当前新增功能

目前后端已经补齐了这些能力：

1. 被动攻击检测
- 单条预测
- 批量预测
- 解释说明

2. 主动检测 / 主动扫描
- 输入目标主机和端口列表
- 返回端口探测结果、风险等级和建议

3. 仪表盘数据接口
- 汇总统计
- 最近事件
- 增量事件流
- SSE 推送
- WebSocket 推送

4. 模型状态接口
- 健康检查
- 模型元数据
- 当前注册版本信息

## 2. 前端页面建议拆分

建议前端至少拆成这几个模块：

1. 首页 / 总览
- 展示总事件数、攻击数、正常数、攻击比例
- 展示攻击类型分布
- 展示来源分布
- 实时刷新事件列表

2. 被动检测页
- 支持手动输入特征
- 支持上传 CSV 批量检测
- 展示预测标签、置信度、解释、规则证据

3. 主动检测页
- 输入目标 IP 或域名
- 输入端口列表
- 一键发起扫描
- 展示 open / closed / error 结果

4. 模型状态页
- 展示当前模型是否加载成功
- 展示当前模型版本、特征数、标签映射
- 展示 registry 信息

## 3. 基础接口

### 3.1 健康检查

`GET /health`

用途：
- 看服务是否正常
- 看模型有没有加载
- 看当前注册版本信息

返回重点字段：
- `status`
- `model_loaded`
- `artifact_path`
- `feature_count`
- `registry_path`
- `registry_count`
- `active_model_path`

前端可用来做：
- 顶部状态灯
- “当前模型已加载”提示
- 模型版本显示

### 3.2 模型元数据

`GET /metadata`

用途：
- 查看模型特征列
- 查看标签映射
- 查看训练指标
- 查看 registry 快照

返回重点字段：
- `feature_columns`
- `label_mapping`
- `metrics`
- `artifact_metadata`
- `registry`

前端可用来做：
- 特征输入表单自动对齐
- 标签映射展示
- 模型版本信息面板

## 4. 被动检测接口

### 4.1 单条预测

`POST /predict`

请求体示例：

```json
{
  "source": "frontend_manual",
  "features": {
    "pkt_rate": 1200,
    "syn_rate": 700,
    "udp_rate": 30,
    "dns_rate": 10,
    "ntp_rate": 0,
    "avg_pkt_size": 320
  }
}
```

也支持 `record` 形式：

```json
{
  "source": "frontend_manual",
  "record": {
    "Destination Port": 443,
    "Source Port": 51023,
    "Protocol": 6,
    "SYN Flag Count": 1,
    "Packet Length Mean": 512
  }
}
```

返回重点字段：
- `prediction`
- `prediction_label`
- `attack_type`
- `confidence`
- `is_attack`
- `probabilities`
- `timestamp`
- `explanation`
- `event`

前端可用来做：
- 单条特征表单
- 检测结果卡片
- 置信度进度条
- 解释说明面板

### 4.2 批量预测

`POST /predict/batch`
或
`POST /batch`

请求方式：
- `multipart/form-data`
- 传一个 CSV 文件字段 `file`

返回重点字段：
- `total`
- `predictions`
- `dashboard_summary`
- `batch_alert`

前端可用来做：
- CSV 上传
- 批量结果表格
- 错误行提示

### 4.3 解释说明

`POST /api/explain`

请求体示例：

```json
{
  "features": {
    "pkt_rate": 1200,
    "syn_rate": 700,
    "udp_rate": 30,
    "dns_rate": 10,
    "ntp_rate": 0,
    "avg_pkt_size": 320
  }
}
```

返回重点字段：
- `is_attack`
- `attack_type`
- `confidence`
- `triggers`
- `explanation`

前端可用来做：
- “为什么判成攻击”说明区
- 规则命中列表

## 5. 主动检测接口

### 5.1 主动扫描

`POST /api/active-scan`

请求体示例：

```json
{
  "targets": ["127.0.0.1"],
  "tcp_ports": [22, 80, 443],
  "timeout_ms": 400,
  "max_workers": 64,
  "source": "frontend_active_scan",
  "trace_id": "scan-001"
}
```

返回重点字段：
- `summary`
- `findings`
- `recommendations`
- `errors`
- `source`
- `trace_id`
- `started_at`
- `finished_at`
- `duration_ms`

其中 `summary` 通常包括：
- `target_count`
- `port_count_per_target`
- `total_probes`
- `open_port_count`
- `high_risk_open_port_count`
- `error_count`

`findings` 里每条结果通常包含：
- `target`
- `port`
- `protocol`
- `state`
- `latency_ms`
- `service`
- `risk`

前端可用来做：
- 扫描表单
- 扫描结果表
- 风险汇总卡片
- 建议面板

## 6. 仪表盘接口

### 6.1 总览统计

`GET /dashboard/summary`

用途：
- 获取总事件统计
- 获取攻击类型分布
- 获取来源分布

前端可直接做：
- 首页总览卡片
- 条形图
- 饼图

### 6.2 最近事件

`GET /dashboard/events?limit=100`

用途：
- 获取最近事件列表

前端可做：
- 事件表格
- 时间轴列表

### 6.3 增量事件

`GET /dashboard/events/delta?limit=100&cursor=...`

用途：
- 拉增量事件
- 适合轮询刷新

返回重点字段：
- `events`
- `count`
- `cursor`
- `summary`

前端可做：
- 每隔几百毫秒刷新一次
- 不必每次拉全量

### 6.4 SSE 推送

`GET /stream/events`

用途：
- 服务端推送事件
- 更适合实时看板

前端可做：
- `EventSource` 接入
- 实时滚动更新

### 6.5 WebSocket 推送

`WS /ws`
`WS /ws/stream`

用途：
- 实时事件流
- 交互式预测

前端可做：
- WebSocket 实时监控面板
- 实时推送预测结果

## 7. 管理接口

### 7.1 重新加载模型

`POST /admin/reload-model`

用途：
- 模型文件更新后，手动让服务重新加载

前端一般不需要放给普通用户
- 更适合管理员页

### 7.2 重置事件

`POST /admin/reset-events`

用途：
- 清空事件历史

前端一般也只给管理员使用

## 8. 前端对接建议

### 8.1 单条检测建议

如果页面上是手填表单，建议直接调用：
- `POST /predict`

然后把这些字段展示出来：
- `prediction_label`
- `confidence`
- `is_attack`
- `explanation.summary`
- `explanation.recommendations`

### 8.2 批量检测建议

如果页面支持 CSV 上传，建议：
- 上传后先走 `POST /predict/batch`
- 再把 `predictions` 渲染成表格

### 8.3 主动扫描建议

如果页面支持“目标 IP + 端口列表”输入，建议：
- 点击按钮直接调 `POST /api/active-scan`
- 扫描完成后展示 summary 和 findings

### 8.4 仪表盘建议

首页建议优先接：
- `GET /dashboard/summary`
- `GET /dashboard/events/delta`

如果想做更实时：
- SSE 优先
- WebSocket 其次

## 9. 兼容和注意事项

1. 目前前后端默认可以跨域
- 后端已经配了 CORS

2. 被动检测和主动检测是两个不同模块
- 被动检测走 `/predict`
- 主动检测走 `/api/active-scan`

3. `confidence` 不是“绝对可信度”
- 更适合展示为“模型置信度”

4. 批量接口要求 CSV 格式正确
- 如果列名和模型特征不对齐，会返回错误行

5. 主动扫描只能在授权环境使用
- 前端最好加提示文案

## 10. 推荐最小接入顺序

如果你们想最快接起来，建议按这个顺序做：

1. `GET /health`
2. `GET /metadata`
3. `POST /predict`
4. `POST /api/explain`
5. `POST /api/active-scan`
6. `GET /dashboard/summary`
7. `GET /dashboard/events/delta`

这样就能先把主流程跑通，再做实时化和美化。

