# 安全态势感知融合项目 - 增强说明

## 项目版本演进

### v1.0
- 规则引擎检测
- 6 维标准特征
- 基础 ML 模型
- 命令行脚本

### v2.0
- FastAPI 服务
- 自动化测试
- 模型产物管理
- 批量预测

### 过渡阶段
- 混合检测器
- 统一配置
- 完整文档

### v4.1
- 增强集成模型：RF + XGB + LGB + ET
- Stacking 集成策略
- 特征重要性分析
- 高级训练脚本
- 在线学习与热加载
- 告警系统集成
- 完整测试套件
- 详细文档

## 核心改进

### 1. 增强集成模型
- 支持 4 种基础模型：RandomForest、XGBoost、LightGBM、ExtraTrees
- Stacking 集成策略（推荐）
- 可配置各模型参数
- 特征重要性分析

### 2. 在线学习
- `train_online.py` 支持流式缓冲训练
- 后台重训 + 原子覆盖 + API 热加载
- 支持备份回滚

### 3. 告警系统
- `src/utils/alert.py` 提供统一告警接口
- 支持 Webhook、企业微信机器人、SMTP 邮件、短信适配器
- 支持模板、重试、配置开关

### 4. 完整测试覆盖
- API 测试
- 数据管道测试
- 规则引擎测试
- 集成测试
- 在线学习与告警单测

## 使用建议

### 快速原型
```bash
python scripts/train.py --data_dir data/raw --test_size 0.2
```

### 生产训练
```bash
python scripts/train_advanced.py --input data/raw --models auto --use-stacking
```

### 在线更新
```bash
python scripts/train_online.py --data_dir data/raw --artifact_path data/models/model_artifacts.pkl
```

### API 服务
```bash
python run_api.py --host 0.0.0.0 --port 8000
```

## 版本信息

**版本**: 4.1.0  
**最后更新**: 2026-04-04
