#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API日志工具
统一的日志管理模块 - 双输出模式（文件+控制台）
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import json
import uuid

# 日志配置
class LogConfig:
    # 日志目录
    LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

    # 日志文件名
    ACCESS_LOG_FILE = "access.log"
    ERROR_LOG_FILE = "error.log"
    APPLICATION_LOG_FILE = "application.log"

    # 日志文件大小限制 (100MB)
    MAX_FILE_SIZE = 100 * 1024 * 1024

    # 保留的日志文件数量
    BACKUP_COUNT = 10

    # 日志级别
    LEVEL = logging.INFO

# 确保日志目录存在
os.makedirs(LogConfig.LOG_DIR, exist_ok=True)

# 全局logger字典，避免重复创建
_loggers = {}

def setup_dual_logger(name: str, log_file: str, level=logging.INFO, force_recreate=False) -> logging.Logger:
    """
    设置双输出日志记录器（文件+控制台）

    Args:
        name: logger名称
        log_file: 日志文件名
        level: 日志级别
        force_recreate: 是否强制重新创建

    Returns:
        配置好的logger实例
    """
    # 避免重复创建logger
    if not force_recreate and name in _loggers:
        return _loggers[name]

    # 创建logger
    logger = logging.getLogger(name)

    # 清除现有的handlers（避免重复添加）
    if logger.handlers:
        logger.handlers.clear()

    logger.setLevel(level)

    # 创建格式化器
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        '🔵 %(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    # 文件处理器（带轮转）
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(LogConfig.LOG_DIR, log_file),
            maxBytes=LogConfig.MAX_FILE_SIZE,
            backupCount=LogConfig.BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

        # 测试写入，确保文件可写
        test_msg = f"Logger '{name}' initialized at {datetime.now().isoformat()}"
        file_handler.emit(logging.LogRecord(
            name=name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=test_msg,
            args=(),
            exc_info=None
        ))

    except Exception as e:
        print(f"⚠️  Failed to create file handler for {log_file}: {e}")

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    # 缓存logger
    _loggers[name] = logger

    # 测试日志输出
    logger.info(f"✅ Logger '{name}' initialized successfully (File: {log_file})")

    return logger

# 创建不同用途的日志记录器
print("🔧 Initializing API loggers...")
access_logger = setup_dual_logger("api_access", LogConfig.ACCESS_LOG_FILE, logging.INFO)
error_logger = setup_dual_logger("api_error", LogConfig.ERROR_LOG_FILE, logging.ERROR)
app_logger = setup_dual_logger("api_app", LogConfig.APPLICATION_LOG_FILE, LogConfig.LEVEL)

class APILogger:
    """API日志记录器类 - 增强版双输出"""

    @staticmethod
    def generate_request_id() -> str:
        """生成唯一请求ID"""
        return str(uuid.uuid4())[:8]  # 缩短ID便于查看

    @staticmethod
    def log_request(request_id: str, method: str, url: str, client: str, headers: dict = None) -> None:
        """记录请求信息"""
        try:
            # 简化URL显示
            clean_url = url.replace('http://localhost:8002', '') if url.startswith('http://localhost:8002') else url

            # 控制台友好的格式
            console_msg = f"📨 [{request_id}] {method} {clean_url} from {client}"

            # 文件详细格式
            file_data = {
                "request_id": request_id,
                "type": "request",
                "timestamp": datetime.now().isoformat(),
                "method": method,
                "url": url,
                "client": client,
                "headers": dict(headers) if headers else {}
            }

            # 同时记录到文件和控制台
            access_logger.info(console_msg)
            # 将详细数据写入一个单独的行
            access_logger.debug(json.dumps(file_data, ensure_ascii=False))

        except Exception as e:
            error_logger.error(f"❌ 记录请求日志失败: {e}")

    @staticmethod
    def log_response(request_id: str, status_code: int, process_time: float, response_data: Any = None) -> None:
        """记录响应信息"""
        try:
            # 状态码emoji
            status_emoji = "✅" if status_code < 400 else "⚠️" if status_code < 500 else "❌"

            # 控制台友好的格式
            console_msg = f"📤 [{request_id}] {status_emoji} {status_code} ({process_time*1000:.1f}ms)"

            # 文件详细格式
            file_data = {
                "request_id": request_id,
                "type": "response",
                "timestamp": datetime.now().isoformat(),
                "status_code": status_code,
                "process_time_ms": round(process_time * 1000, 2),
                "response_size": len(str(response_data)) if response_data else 0
            }

            # 同时记录到文件和控制台
            access_logger.info(console_msg)
            access_logger.debug(json.dumps(file_data, ensure_ascii=False))

        except Exception as e:
            error_logger.error(f"❌ 记录响应日志失败: {e}")

    @staticmethod
    def log_info(message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录信息日志"""
        try:
            if extra:
                full_msg = f"{message} - {json.dumps(extra, ensure_ascii=False)}"
                app_logger.info(full_msg)
            else:
                app_logger.info(message)
        except Exception as e:
            print(f"❌ 日志记录失败: {e}")

    @staticmethod
    def log_error(message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录错误日志"""
        try:
            if extra:
                full_msg = f"{message} - {json.dumps(extra, ensure_ascii=False)}"
                error_logger.error(full_msg)
            else:
                error_logger.error(message)
        except Exception as e:
            print(f"❌ 错误日志记录失败: {e}")

    @staticmethod
    def log_debug(message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录调试日志"""
        try:
            if extra:
                full_msg = f"{message} - {json.dumps(extra, ensure_ascii=False)}"
                app_logger.debug(full_msg)
            else:
                app_logger.debug(message)
        except Exception as e:
            print(f"❌ 调试日志记录失败: {e}")

    @staticmethod
    def log_warning(message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录警告日志"""
        try:
            if extra:
                full_msg = f"{message} - {json.dumps(extra, ensure_ascii=False)}"
                app_logger.warning(full_msg)
            else:
                app_logger.warning(message)
        except Exception as e:
            print(f"❌ 警告日志记录失败: {e}")

# 导出常用函数
def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器"""
    return logging.getLogger(name)