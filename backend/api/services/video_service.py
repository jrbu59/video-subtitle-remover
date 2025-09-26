#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频处理服务
"""

import os
import asyncio
import threading
from typing import Optional, Dict, Any
from fastapi import UploadFile

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import config
from backend.main import SubtitleRemover
from backend.api.models.task import TaskStatus
from backend.api.services.task_service import TaskService
from backend.api.services.storage import save_upload_file, get_upload_path, get_output_path
from backend.api.services.subtitle_detection_service import SubtitleDetectionService

# 导入日志工具
from backend.api.utils.logger import APILogger


class ProcessingSubtitleRemover(SubtitleRemover):
    """扩展的SubtitleRemover，支持进度回调"""

    def __init__(self, vd_path, sub_area=None, gui_mode=False, progress_callback=None):
        super().__init__(vd_path, sub_area, gui_mode)
        self.progress_callback = progress_callback
        self.task_id = None

    def set_task_id(self, task_id: str):
        """设置任务ID"""
        self.task_id = task_id

    def update_progress_callback(self, progress: float):
        """更新进度的回调"""
        if self.progress_callback and self.task_id:
            asyncio.create_task(self.progress_callback(self.task_id, progress))

    def update_progress(self, tbar, increment):
        """重写进度更新方法"""
        super().update_progress(tbar, increment)
        # 发送进度更新
        if hasattr(self, 'progress_total'):
            self.update_progress_callback(self.progress_total)


class VideoService:
    """视频处理服务"""

    _processing_tasks: Dict[str, threading.Thread] = {}
    _remover_instances: Dict[str, ProcessingSubtitleRemover] = {}

    @classmethod
    async def save_uploaded_file(cls, file: UploadFile, task_id: str) -> str:
        """保存上传的文件"""
        file_path = get_upload_path(task_id, file.filename)
        return await save_upload_file(file, file_path)

    @classmethod
    async def start_processing_task(cls, task_id: str, auto_detect_subtitles: bool = False):
        """启动视频处理任务"""
        task = await TaskService.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")

        # 如果需要自动检测字幕，则先进行字幕检测
        if auto_detect_subtitles:
            await TaskService.update_task_status(task_id, TaskStatus.DETECTING)
            detection_result = await SubtitleDetectionService.detect_subtitles(task_id)

            # 如果检测到字幕区域，则更新任务的字幕区域
            if detection_result and detection_result.get("has_subtitles", False):
                # 转换检测结果为字幕区域格式
                subtitle_regions = []
                for region in detection_result.get("regions", []):
                    # 转换为 [x1, y1, x2, y2] 格式
                    x1, y1 = region["x"], region["y"]
                    x2, y2 = region["x"] + region["width"], region["y"] + region["height"]
                    subtitle_regions.append([x1, y1, x2, y2])

                # 更新任务的字幕区域
                await TaskService.update_subtitle_regions(task_id, subtitle_regions)

        # 更新任务状态为处理中
        await TaskService.update_task_status(task_id, TaskStatus.PROCESSING)

        # 创建并启动处理线程
        thread = threading.Thread(target=cls._process_video_sync, args=(task_id,))
        thread.daemon = True
        cls._processing_tasks[task_id] = thread
        thread.start()

    @classmethod
    def _process_video_sync(cls, task_id: str):
        """同步视频处理方法（在线程中运行）"""
        try:
            # 获取任务信息
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            task = loop.run_until_complete(TaskService.get_task(task_id))
            if not task:
                return

            # 应用配置覆盖
            if task.config_override:
                cls._apply_config_override(task.config_override)

            # 设置算法模式
            if task.algorithm.value == "sttn":
                config.MODE = config.InpaintMode.STTN
            elif task.algorithm.value == "lama":
                config.MODE = config.InpaintMode.LAMA
            elif task.algorithm.value == "propainter":
                config.MODE = config.InpaintMode.PROPAINTER

            # 准备字幕区域 - 支持多个独立区域
            sub_area = None
            if task.subtitle_regions:
                APILogger.log_info(f"Processing {len(task.subtitle_regions)} subtitle regions: {task.subtitle_regions}")
                APILogger.log_debug(f"Raw subtitle_regions from task: {task.subtitle_regions}")
                APILogger.log_debug(f"Type of subtitle_regions: {type(task.subtitle_regions)}")

                # 转换字幕区域格式：从 [[x1,y1,x2,y2],...] 到 [(ymin, ymax, xmin, xmax),...]
                # 不再合并区域，而是保持多个独立区域
                if len(task.subtitle_regions) > 0:
                    all_areas = []
                    for i, region in enumerate(task.subtitle_regions):
                        APILogger.log_debug(f"Processing region {i}: {region}")
                        APILogger.log_debug(f"Type of region {i}: {type(region)}")
                        if len(region) == 4:
                            # 确保坐标值是整数类型
                            x1, y1, x2, y2 = [int(coord) for coord in region]
                            area = (min(y1, y2), max(y1, y2), min(x1, x2), max(x1, x2))
                            all_areas.append(area)
                            APILogger.log_info(f"Region {i}: [{x1},{y1},{x2},{y2}] -> ymin={area[0]}, ymax={area[1]}, xmin={area[2]}, xmax={area[3]}")
                        else:
                            APILogger.log_warning(f"Invalid region {i} format, expected 4 values but got {len(region)}")

                    if all_areas:
                        # 传递多个独立区域而不是合并
                        sub_area = all_areas  # 现在sub_area是一个区域列表
                        APILogger.log_info(f"✅ Will use {len(all_areas)} independent subtitle regions for precise detection")
                        for i, area in enumerate(all_areas):
                            APILogger.log_info(f"   Region {i+1}: ymin={area[0]}, ymax={area[1]}, xmin={area[2]}, xmax={area[3]}")
                    else:
                        APILogger.log_warning(f"No valid regions found in subtitle_regions")
                else:
                    APILogger.log_warning(f"Empty subtitle_regions list")
            else:
                APILogger.log_info(f"No subtitle_regions specified, will auto-detect subtitles")

            # 生成输出路径
            output_path = get_output_path(task_id, task.original_filename)
            output_filename = os.path.basename(output_path)

            # 创建字幕去除器
            async def progress_callback(task_id: str, progress: float):
                await TaskService.update_task_progress(task_id, progress)

            remover = ProcessingSubtitleRemover(
                task.file_path,
                sub_area=sub_area,
                gui_mode=False,
                progress_callback=progress_callback
            )
            remover.set_task_id(task_id)
            remover.video_out_name = output_path
            cls._remover_instances[task_id] = remover

            # 开始处理
            remover.run()

            # 检查输出文件是否生成
            if os.path.exists(output_path):
                # 处理成功
                loop.run_until_complete(TaskService.update_task_status(
                    task_id,
                    TaskStatus.COMPLETED,
                    progress=100.0,
                    output_path=output_path,
                    output_filename=output_filename
                ))
            else:
                # 处理失败
                loop.run_until_complete(TaskService.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    error_message="输出文件未生成"
                ))

        except Exception as e:
            # 处理失败
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(TaskService.update_task_status(
                task_id,
                TaskStatus.FAILED,
                error_message=str(e)
            ))
        finally:
            # 清理
            if task_id in cls._processing_tasks:
                del cls._processing_tasks[task_id]
            if task_id in cls._remover_instances:
                del cls._remover_instances[task_id]

    @classmethod
    def _apply_config_override(cls, config_override: Dict[str, Any]):
        """应用配置覆盖"""
        for key, value in config_override.items():
            if hasattr(config, key):
                setattr(config, key, value)
                APILogger.log_info(f"配置覆盖: {key} = {value}")

    @classmethod
    async def get_preview_info(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """获取处理预览信息"""
        remover = cls._remover_instances.get(task_id)
        if not remover:
            return None

        preview_info = {
            "has_preview": False,
            "frame_info": None
        }

        # 如果有预览帧，可以返回相关信息
        if hasattr(remover, 'preview_frame') and remover.preview_frame is not None:
            preview_info["has_preview"] = True
            preview_info["frame_info"] = {
                "width": remover.frame_width,
                "height": remover.frame_height,
                "fps": remover.fps,
                "total_frames": remover.frame_count
            }

        return preview_info

    @classmethod
    async def cancel_processing(cls, task_id: str) -> bool:
        """取消正在处理的任务"""
        # 获取处理线程
        thread = cls._processing_tasks.get(task_id)
        if thread and thread.is_alive():
            # 注意：Python的threading模块不支持强制终止线程
            # 这里只是标记任务为取消状态，实际的停止需要在处理逻辑中检查
            await TaskService.cancel_task(task_id)
            return True
        return False

    @classmethod
    def is_processing(cls, task_id: str) -> bool:
        """检查任务是否正在处理"""
        thread = cls._processing_tasks.get(task_id)
        return thread is not None and thread.is_alive()

    @classmethod
    def get_processing_count(cls) -> int:
        """获取正在处理的任务数量"""
        return len([t for t in cls._processing_tasks.values() if t.is_alive()])

    @classmethod
    async def get_supported_formats(cls) -> Dict[str, Any]:
        """获取支持的文件格式"""
        return {
            "video_formats": list(config.SUPPORTED_VIDEO_FORMATS),
            "image_formats": list(config.SUPPORTED_IMAGE_FORMATS),
            "max_file_size": config.MAX_FILE_SIZE,
            "max_file_size_mb": config.MAX_FILE_SIZE // (1024 * 1024)
        }

    @classmethod
    async def validate_algorithm_config(cls, algorithm: str, config_override: Optional[Dict[str, Any]] = None) -> bool:
        """验证算法配置的有效性"""
        try:
            # 基本算法验证
            if algorithm not in ["sttn", "lama", "propainter"]:
                return False

            # 配置参数验证
            if config_override:
                # 验证STTN相关参数
                if algorithm == "sttn":
                    if "STTN_MAX_LOAD_NUM" in config_override:
                        max_load = config_override["STTN_MAX_LOAD_NUM"]
                        stride = config_override.get("STTN_NEIGHBOR_STRIDE", config.STTN_NEIGHBOR_STRIDE)
                        length = config_override.get("STTN_REFERENCE_LENGTH", config.STTN_REFERENCE_LENGTH)
                        if max_load < stride * length:
                            return False

                # 验证ProPainter相关参数
                elif algorithm == "propainter":
                    if "PROPAINTER_MAX_LOAD_NUM" in config_override:
                        if config_override["PROPAINTER_MAX_LOAD_NUM"] < 1:
                            return False

            return True
        except Exception:
            return False