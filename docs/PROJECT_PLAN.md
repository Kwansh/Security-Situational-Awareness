# 项目计划

## Phase 1: 基础功能 ✅
- [x] 数据加载
- [x] 特征提取
- [x] 数据预处理
- [x] 规则引擎
- [x] ML 检测器
- [x] 混合检测器
- [x] 攻击解释器
- [x] 模型训练
- [x] 集成模型
- [x] API 服务

## Phase 2: 融合功能 ✅
- [x] 混合检测器
- [x] API 服务
- [x] 攻击解释
- [x] 配置文件
- [x] 测试套件

## Phase 3: 生产增强 ✅
- [x] WebSocket 实时检测
- [x] 可视化 Dashboard
- [x] 在线学习
- [x] Docker 部署
- [x] 告警系统集成

---

**当前版本**: 4.1.0  
**完成度**: 100% 核心功能 + 生产增强能力

**真实状态说明**:
- 训练链路支持 `random_forest`、`xgboost`、`extra_trees`、`lightgbm` 的可选组合；默认保持 RF + XGBoost 的快速路径。
- API 支持 `/predict`、`/batch`、`/predict/batch`、`/ws`、`/dashboard`、`/dashboard/summary`、`/dashboard/events`、`/metadata`、`/health`、`/admin/reload-model`、`/api/explain`。
- 在线学习采用“流式缓冲 + 后台重训 + 原子覆盖 + API 热加载”的无中断方案。
- 告警系统支持 Webhook、企业微信机器人、SMTP 邮件、短信适配器，并与检测日志联动。
- Dockerfile 与 docker-compose 已补齐并与 run_api 启动参数对齐。
