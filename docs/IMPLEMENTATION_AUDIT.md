# 文档驱动实现审计报告

本文档用于对照 `docs/` 中的功能目标，记录当前项目的实现状态。

## 已实现清单

- 规则引擎：SYN Flood、UDP Flood、DNS Flood、NTP Flood、SQL 注入等规则检测已实现。
- 机器学习检测器：模型加载、推理、概率输出、异常/攻击分类已实现。
- 混合检测器：规则结果与 ML 结果融合已实现。
- 特征提取：`standard`、`full`、`hybrid` 三种模式已实现。
- 数据预处理：清洗、编码、缺失值处理、标准化、标签映射已实现。
- API 服务：`/predict`、`/batch`、`/predict/batch`、`/ws`、`/dashboard`、`/dashboard/summary`、`/dashboard/events`、`/metadata`、`/health`、`/admin/reload-model`、`/api/explain` 已实现。
- 可解释性：攻击解释模块可输出可读检测依据、处置建议和技术细节。
- 训练脚本：`scripts/train.py`、`scripts/train_advanced.py`、`scripts/train_online.py` 可直接运行，支持大 CSV 分块读取、在线缓冲与进度日志。
- 训练评估：训练完成后自动输出 accuracy、precision、recall、F1，并生成混淆矩阵与指标图。
- 模型产物：`model_artifacts.pkl`、`metrics.json`、`online_metrics.json`、可视化结果输出已实现。
- WebSocket 实时检测：已实现。
- Dashboard 前端：已实现，浏览器访问 `/` 或 `/dashboard` 可查看。
- 在线学习：已实现，支持流式缓冲、后台重训、备份覆盖和热加载。
- 告警系统：已实现，支持 Webhook、企业微信机器人、SMTP 邮件、短信适配器。
- Docker 部署：`Dockerfile`、`docker-compose.yml` 已补齐。

## 未实现清单

- 在线学习中的真正 `partial_fit` 级别增量算法仍未引入，因为当前主模型以树模型为主，采用的是生产上更稳妥的后台重训方案。
- 短信通道当前提供通用适配器接口，若接入具体短信服务商仍需配置对应 endpoint 或 SDK 网关。

## 部分实现 / 存在偏差清单

- LightGBM：代码已集成，若环境缺少依赖会自动跳过，不会中断训练。
- 文档版本描述：已统一对齐到 4.1.0，增强说明仅保留非规范性的版本演进概览，不影响当前实现与接口定义。

## 可直接执行的命令

```bash
python scripts/train.py --data_dir data/raw --test_size 0.2 --chunk_size 50000
python scripts/train_advanced.py --input data/raw --models auto --use-stacking
python scripts/train_online.py --data_dir data/raw --artifact_path data/models/model_artifacts.pkl
python run_api.py --host 0.0.0.0 --port 8000
```

## 备注

- 当前项目已具备真实落地所需的核心检测链路与生产增强能力。
- 如果要进一步向“生产级”靠拢，建议优先补齐：认证鉴权、限流、告警去重策略和在线学习的真正增量算法。
