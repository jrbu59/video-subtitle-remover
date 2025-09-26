#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务管理服务
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# 导入日志工具
from backend.api.utils.logger import APILogger

import config
from backend.api.models.task import Task, TaskCreate, TaskStatus, AlgorithmType
from backend.api.services.storage import cleanup_task_files


class TaskService:
    """任务管理服务"""

    # 内存中的任务存储（生产环境应使用数据库）
    _tasks: Dict[str, Task] = {}
    _task_lock = asyncio.Lock()

    @classmethod
    async def create_task(
        cls,
        task_id: str,
        task_create: TaskCreate,
        original_filename: str,
        file_path: str,
        file_size: Optional[int] = None,
        duration: Optional[float] = None
    ) -> Task:
        """创建新任务"""
        async with cls._task_lock:
            task = Task(
                id=task_id,
                algorithm=task_create.algorithm,
                original_filename=original_filename,
                file_path=file_path,
                subtitle_regions=task_create.subtitle_regions,
                config_override=task_create.config_override,
                auto_detect_subtitles=task_create.auto_detect_subtitles,
                file_size=file_size,
                duration=duration
            )
            cls._tasks[task_id] = task
            return task

    @classmethod
    async def get_task(cls, task_id: str) -> Optional[Task]:
        """获取任务"""
        return cls._tasks.get(task_id)

    @classmethod
    async def update_task_status(
        cls,
        task_id: str,
        status: TaskStatus,
        progress: Optional[float] = None,
        error_message: Optional[str] = None,
        output_path: Optional[str] = None,
        output_filename: Optional[str] = None
    ) -> Optional[Task]:
        """更新任务状态"""
        async with cls._task_lock:
            task = cls._tasks.get(task_id)
            if not task:
                return None

            task.status = status
            if progress is not None:
                task.progress = progress
            if error_message is not None:
                task.error_message = error_message
            if output_path is not None:
                task.output_path = output_path
            if output_filename is not None:
                task.output_filename = output_filename

            # 更新时间戳
            if status == TaskStatus.PROCESSING and not task.started_at:
                task.started_at = datetime.now()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task.completed_at = datetime.now()

            return task

    @classmethod
    async def update_subtitle_regions(cls, task_id: str, subtitle_regions: list) -> Optional[Task]:
        """更新任务的字幕区域"""
        async with cls._task_lock:
            task = cls._tasks.get(task_id)
            if not task:
                return None

            task.subtitle_regions = subtitle_regions
            return task

    @classmethod
    async def get_task_list(
        cls,
        status: Optional[TaskStatus] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "created_at",
        order: str = "desc"
    ) -> Tuple[List[Task], int]:
        """获取任务列表"""
        # 筛选任务
        tasks = list(cls._tasks.values())
        if status:
            tasks = [task for task in tasks if task.status == status]

        # 排序
        reverse = order == "desc"
        if order_by == "created_at":
            tasks.sort(key=lambda x: x.created_at, reverse=reverse)
        elif order_by == "progress":
            tasks.sort(key=lambda x: x.progress, reverse=reverse)
        elif order_by == "status":
            tasks.sort(key=lambda x: x.status.value, reverse=reverse)

        # 分页
        total = len(tasks)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_tasks = tasks[start:end]

        return paginated_tasks, total

    @classmethod
    async def delete_task(cls, task_id: str) -> bool:
        """删除任务"""
        async with cls._task_lock:
            task = cls._tasks.get(task_id)
            if not task:
                return False

            # 清理相关文件
            cleanup_task_files(task_id, task.file_path, task.output_path)

            # 从内存中删除
            del cls._tasks[task_id]
            return True

    @classmethod
    async def cancel_task(cls, task_id: str) -> bool:
        """取消任务"""
        # 注意：这里只是更新状态，实际的任务取消需要在处理逻辑中实现
        task = await cls.update_task_status(
            task_id,
            TaskStatus.FAILED,
            error_message="任务已被用户取消"
        )
        return task is not None

    @classmethod
    async def cleanup_expired_tasks(cls) -> Dict[str, Any]:
        """清理过期任务"""
        async with cls._task_lock:
            current_time = datetime.now()
            expired_threshold = current_time - timedelta(hours=config.FILE_RETENTION_HOURS)

            expired_tasks = []
            for task_id, task in list(cls._tasks.items()):
                # 清理超过保留时间的已完成或失败任务
                if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] and
                    task.completed_at and task.completed_at < expired_threshold):
                    expired_tasks.append(task_id)

            # 删除过期任务
            deleted_count = 0
            deleted_files = []
            for task_id in expired_tasks:
                task = cls._tasks[task_id]
                files = cleanup_task_files(task_id, task.file_path, task.output_path)
                deleted_files.extend(files)
                del cls._tasks[task_id]
                deleted_count += 1

            return {
                "deleted_tasks": deleted_count,
                "deleted_files": len(deleted_files),
                "file_list": deleted_files
            }

    @classmethod
    async def get_task_statistics(cls) -> Dict[str, Any]:
        """获取任务统计"""
        stats = {
            "total": len(cls._tasks),
            "pending": 0,
            "detecting": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "by_algorithm": {
                "sttn": 0,
                "lama": 0,
                "propainter": 0
            }
        }

        for task in cls._tasks.values():
            # 按状态统计
            stats[task.status.value] += 1
            # 按算法统计
            stats["by_algorithm"][task.algorithm.value] += 1

        return stats

    @classmethod
    async def get_processing_tasks(cls) -> List[Task]:
        """获取正在处理的任务"""
        return [task for task in cls._tasks.values() if task.status == TaskStatus.PROCESSING]

    @classmethod
    async def save_tasks_to_file(cls, file_path: str):
        """将任务保存到文件（可选的持久化）"""
        try:
            tasks_data = {}
            for task_id, task in cls._tasks.items():
                # 将Task对象转换为字典
                task_dict = task.dict()
                # 处理datetime序列化
                for field in ['created_at', 'started_at', 'completed_at']:
                    if task_dict.get(field):
                        task_dict[field] = task_dict[field].isoformat()
                tasks_data[task_id] = task_dict

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            APILogger.log_error(f"保存任务到文件失败: {e}")

    @classmethod
    async def load_tasks_from_file(cls, file_path: str):
        """从文件加载任务（可选的持久化）"""
        try:
            if not os.path.exists(file_path):
                return

            with open(file_path, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)

            async with cls._task_lock:
                for task_id, task_dict in tasks_data.items():
                    # 处理datetime反序列化
                    for field in ['created_at', 'started_at', 'completed_at']:
                        if task_dict.get(field):
                            task_dict[field] = datetime.fromisoformat(task_dict[field])

                    # 创建Task对象
                    task = Task(**task_dict)
                    cls._tasks[task_id] = task

        except Exception as e:
            APILogger.log_error(f"从文件加载任务失败: {e}")

    @classmethod
    def get_task_count(cls) -> int:
        """获取任务总数"""
        return len(cls._tasks)

    @classmethod
    async def update_task_progress(cls, task_id: str, progress: float) -> Optional[Task]:
        """更新任务进度"""
        return await cls.update_task_status(task_id, TaskStatus.PROCESSING, progress=progress)