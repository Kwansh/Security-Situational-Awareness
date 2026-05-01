#!/bin/bash
# 安全态势感知系统 - 快速启动脚本 (Linux/macOS)

set -e

echo "========================================"
echo "  安全态势感知系统 - 融合版 v4.0"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：未找到 Python 3"
    exit 1
fi

echo "✅ Python 版本：$(python3 --version)"
echo ""

# 创建虚拟环境
if [ ! -d ".venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv .venv
fi

# 激活虚拟环境
echo "🔌 激活虚拟环境..."
source .venv/bin/activate

# 安装依赖
echo "📥 安装依赖（包括 XGBoost）..."
pip install -q -r requirements.txt

# 创建目录
echo "📁 创建数据目录..."
mkdir -p data/raw data/processed data/models results/figures

echo ""
echo "========================================"
echo "  ✅ 环境配置完成！"
echo "========================================"
echo ""
echo "📚 接下来可以执行："
echo ""
echo "  1️⃣  训练集成模型（推荐）"
echo "     python scripts/train_advanced.py --input data/raw --use-stacking"
echo ""
echo "  2️⃣  训练基础模型"
echo "     python scripts/train.py --input data/raw"
echo ""
echo "  3️⃣  运行预测"
echo "     python scripts/predict.py --input test.csv --output results/predictions.csv"
echo ""
echo "  4️⃣  启动 API 服务"
echo "     python run_api.py"
echo "     访问：http://localhost:8000/docs"
echo ""
echo "  5️⃣  运行测试"
echo "     pytest tests/ -v"
echo ""
echo "  6️⃣  查看文档"
echo "     cat README.md"
echo ""
echo "========================================"
