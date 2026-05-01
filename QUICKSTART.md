# 网络安全态势感知系统 - 快速开始指南

## 5 分钟快速体验

### 1. 安装依赖

```bash
cd security-situational-awareness-ultimate
pip install -r requirements.txt
```

### 2. 准备测试数据

创建测试数据文件 `data/raw/test.csv`，包含以下列：
- Timestamp
- Destination Port
- Source Port
- Protocol
- SYN Flag Count
- Packet Length Mean
- Label

### 3. 训练模型

```bash
python scripts/train.py --input data/raw --output data/models/model_artifacts.pkl
```

### 4. 启动 API

```bash
python run_api.py
```

访问 http://localhost:8000/docs

### 5. 测试预测

```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "features": {
      "pkt_rate": 1000.0,
      "syn_rate": 500.0,
      "udp_rate": 200.0,
      "dns_rate": 50.0,
      "ntp_rate": 10.0,
      "avg_pkt_size": 500.0
    }
  }'
```

---

## 使用 Python SDK

```python
from src.detection.hybrid_detector import HybridDetector
from src.explainability.attack_explainer import AttackExplainer

# 创建检测器
detector = HybridDetector(
    model_path="data/models/model_artifacts.pkl",
    mode="hybrid",
)

# 创建解释器
explainer = AttackExplainer()

# 检测
features = {
    "pkt_rate": 10000.0,
    "syn_rate": 5000.0,
    "udp_rate": 200.0,
    "dns_rate": 50.0,
    "ntp_rate": 10.0,
    "avg_pkt_size": 50.0,
}

result = detector.detect(features)
print(f"🚨 检测到攻击：{result.attack_type}")
print(f"📊 置信度：{result.confidence:.2%}")

# 生成解释
explanation = explainer.explain(result, features)
print(f"\n📋 摘要：{explanation.summary}")
print(f"\n💡 建议:")
for rec in explanation.recommendations:
    print(f"  - {rec}")
```

---

## 常见问题

### Q: 模型加载失败？
A: 确保先运行训练脚本生成模型文件

### Q: 特征维度不匹配？
A: 使用 `mode="hybrid"` 可以自动适配不同特征集

### Q: 如何调整检测灵敏度？
A: 修改 `config/config.yaml` 中的 `rule_thresholds`

---

祝你使用愉快！🎉
