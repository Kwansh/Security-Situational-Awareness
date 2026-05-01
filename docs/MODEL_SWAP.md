# 模型替换指南

## 自动替换

```bash
python scripts/swap_model.py --new-model /path/to/new_model.pkl
```

## 手动替换

1. 备份旧模型
2. 复制新模型到 data/models/
3. 验证模型加载

## 恢复旧模型

```bash
python scripts/swap_model.py --restore
```

## 验证模型

```bash
python3 -c "import joblib; model = joblib.load('data/models/model_artifacts.pkl'); print('✅ 模型加载成功！')"
```
