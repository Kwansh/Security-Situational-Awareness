"""
日志工具模块

提供统一的日志配置和记录功能
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "security-awareness",
    level: str = "INFO",
    log_file: Optional[str] = None,
    console_output: bool = True,
) -> logging.Logger:
    """
    设置日志器
    
    Args:
        name: 日志器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径
        console_output: 是否输出到控制台
        
    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有处理器
    logger.handlers = []
    
    # 日志格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # 控制台处理器
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# 创建默认日志器
default_logger = setup_logger()


def get_logger(name: str = __name__) -> logging.Logger:
    """
    获取日志器
    
    Args:
        name: 日志器名称
        
    Returns:
        Logger 实例
    """
    return logging.getLogger(name)
