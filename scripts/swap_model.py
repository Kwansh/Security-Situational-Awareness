#!/usr/bin/env python3
"""Model swapping utility for artifact replacement and rollback."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import joblib

from src.utils.model_artifacts import DEFAULT_ARTIFACT_NAME


def _resolve_path(base: Path, maybe_relative: str) -> Path:
    path = Path(maybe_relative)
    return path if path.is_absolute() else (base / path).resolve()


def replace_model(new_model_path: str, model_name: str = DEFAULT_ARTIFACT_NAME) -> bool:
    print("=" * 60)
    print("模型自动替换工具")
    print("=" * 60)

    project_root = Path(__file__).resolve().parents[1]
    new_model = _resolve_path(project_root, new_model_path)
    old_model = project_root / "data" / "models" / model_name
    backup_model = old_model.with_name(f"{old_model.stem}_backup{old_model.suffix}")

    print("\n[1/4] 检查新模型文件...")
    if not new_model.exists():
        print(f"错误：找不到新模型文件: {new_model}")
        return False

    print(f"找到新模型: {new_model}")
    print(f"文件大小: {new_model.stat().st_size / 1024 / 1024:.2f} MB")

    print("\n[2/4] 备份旧模型...")
    if old_model.exists():
        try:
            shutil.copy2(old_model, backup_model)
            print(f"旧模型已备份到: {backup_model}")
        except Exception as exc:
            print(f"备份失败: {exc}")
            return False
    else:
        print("旧模型不存在，跳过备份。")

    print("\n[3/4] 替换模型文件...")
    try:
        shutil.copy2(new_model, old_model)
        print(f"已复制: {new_model} -> {old_model}")
    except Exception as exc:
        print(f"复制失败: {exc}")
        return False

    print("\n[4/4] 验证新模型...")
    try:
        model_data = joblib.load(old_model)
        print("模型加载成功")
        if isinstance(model_data, dict):
            print(f"模型字典键: {list(model_data.keys())}")
        else:
            print(f"模型类型: {type(model_data).__name__}")
    except Exception as exc:
        print(f"模型验证失败: {exc}")
        if backup_model.exists():
            shutil.copy2(backup_model, old_model)
            print("已恢复旧模型。")
        return False

    print("\n" + "=" * 60)
    print("模型替换完成")
    print("=" * 60)
    print(f"新模型: {old_model}")
    print(f"备份文件: {backup_model}")
    print("下一步: python run_api.py --host 0.0.0.0 --port 8000")
    return True


def restore_model(model_name: str = DEFAULT_ARTIFACT_NAME) -> bool:
    print("=" * 60)
    print("模型恢复工具")
    print("=" * 60)

    project_root = Path(__file__).resolve().parents[1]
    backup_model = project_root / "data" / "models" / f"{Path(model_name).stem}_backup{Path(model_name).suffix}"
    old_model = project_root / "data" / "models" / model_name

    if not backup_model.exists():
        print("找不到备份文件。")
        return False

    try:
        shutil.copy2(backup_model, old_model)
        print("已恢复旧模型。")
        return True
    except Exception as exc:
        print(f"恢复失败: {exc}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="模型替换工具")
    parser.add_argument("--new-model", "-n", type=str, default="ddos_detect_model.pkl", help="新模型路径")
    parser.add_argument("--model-name", "-m", type=str, default=DEFAULT_ARTIFACT_NAME, help="目标模型文件名")
    parser.add_argument("--restore", "-r", action="store_true", help="恢复备份模型")
    args = parser.parse_args()

    if args.restore:
        restore_model(args.model_name)
    else:
        replace_model(args.new_model, args.model_name)


if __name__ == "__main__":
    main()
