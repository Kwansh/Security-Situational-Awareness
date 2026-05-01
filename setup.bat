@echo off
<<<<<<< HEAD
chcp 65001 >nul
=======
chcp 437
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
set PYTHONPATH=%cd%
setlocal enabledelayedexpansion

echo ========================================
<<<<<<< HEAD
echo 安全态势感知系统 - 融合版 v4.0
=======
echo Security Situational Awareness - Setup
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
echo ========================================

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    exit /b 1
)

python --version

if not exist ".venv" (
    python -m venv .venv
)

call .venv\Scripts\activate.bat

pip install -q -r requirements.txt

if not exist "data\raw" mkdir data\raw
if not exist "data\processed" mkdir data\processed
if not exist "data\models" mkdir data\models
if not exist "results\figures" mkdir results\figures

echo ========================================
<<<<<<< HEAD
echo ✅ 环境配置完成
echo ========================================

echo.
echo 📚 接下来可以执行：
echo.
echo   1️⃣  训练集成模型（推荐）
echo      python scripts\train_advanced.py --input data\raw --use-stacking
echo.
echo   2️⃣  训练基础模型
echo      python scripts\train.py --input data\raw
echo.
echo   3️⃣  运行预测
echo      python scripts\predict.py --input test.csv --output results\predictions.csv
echo.
echo   4️⃣  启动 API 服务
echo      python run_api.py
echo      访问：http://localhost:8000/docs
echo.
echo   5️⃣  运行测试
echo      pytest tests\ -v
echo.
echo   6️⃣  查看文档
echo      type README.md
echo.
=======
echo Setup completed
echo ========================================

echo 1. Train advanced model
echo python -m scripts.train_advanced --input data/raw --output data/models/ensemble_model.pkl --use-stacking

echo 2. Train basic model
echo python -m scripts.train --input data/raw --output data/models/ddos_model.pkl

echo 3. Predict
echo python -m scripts.predict --input test.csv --output results.csv

echo 4. Start API
echo python -m api.server

echo 5. Test
echo pytest tests/ -v --cov=src

echo 6. Read README
echo type README.md

>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
echo ========================================
pause
