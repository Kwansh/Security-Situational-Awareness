# 安全态势感知项目

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
