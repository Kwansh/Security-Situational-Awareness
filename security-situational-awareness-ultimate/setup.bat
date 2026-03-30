@echo off
chcp 437
set PYTHONPATH=%cd%
setlocal enabledelayedexpansion

echo ========================================
echo Security Situational Awareness - Setup
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

echo ========================================
pause
