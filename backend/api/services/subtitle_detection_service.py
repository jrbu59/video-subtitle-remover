#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕检测服务
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from typing import Optional, Dict, Any
from backend.api.gemini import TokenManager, GeminiClient
from backend.api.services.task_service import TaskService
from backend.api.models.task import TaskStatus
from backend.api.utils.logger import APILogger

class SubtitleDetectionService:
    """字幕检测服务"""

    # Gemini API令牌端点（需要根据实际配置修改）
    GEMINI_TOKEN_ENDPOINT = "http://api-ladder.ymt.io:8088/rpc/vertexai/accesstoken"

    @classmethod
    async def detect_subtitles(cls, task_id: str) -> Dict[str, Any]:
        """
        使用Gemini检测视频中的字幕

        Args:
            task_id: 任务ID

        Returns:
            字幕检测结果
        """
        try:
            # 获取任务信息
            task = await TaskService.get_task(task_id)
            if not task:
                raise ValueError("任务不存在")

            # 更新任务状态为检测中
            await TaskService.update_task_status(task_id, TaskStatus.DETECTING)

            # 初始化Gemini客户端
            token_manager = TokenManager(cls.GEMINI_TOKEN_ENDPOINT)
            gemini_client = GeminiClient(token_manager)

            # 执行字幕检测
            APILogger.log_info(f"开始检测任务 {task_id} 的字幕区域")
            subtitle_analysis = gemini_client.analyze_subtitle_with_gemini(
                task.file_path,
                sample_frames=8
            )

            # 准备返回结果
            if subtitle_analysis:
                result = {
                    "has_subtitles": subtitle_analysis.has_subtitles,
                    "subtitle_type": subtitle_analysis.subtitle_type,
                    "dominant_position": subtitle_analysis.dominant_position,
                    "regions": []
                }

                # 转换区域格式
                for region in subtitle_analysis.regions:
                    result["regions"].append({
                        "x": region.x,
                        "y": region.y,
                        "width": region.width,
                        "height": region.height,
                        "confidence": region.confidence,
                        "text_content": region.text_content
                    })

                # 保存分析结果到任务
                await cls._save_analysis_result(task_id, result)

                # 更新任务状态
                await TaskService.update_task_status(task_id, TaskStatus.PENDING)

                APILogger.log_info(f"任务 {task_id} 字幕检测完成: {subtitle_analysis.has_subtitles}")
                return result
            else:
                # 检测失败
                await TaskService.update_task_status(task_id, TaskStatus.FAILED, error_message="字幕检测失败")
                APILogger.log_error(f"任务 {task_id} 字幕检测失败")
                return {
                    "has_subtitles": False,
                    "subtitle_type": "hard",
                    "dominant_position": "unknown",
                    "regions": [],
                    "error": "字幕检测失败"
                }

        except Exception as e:
            # 检测异常
            await TaskService.update_task_status(task_id, TaskStatus.FAILED, error_message=str(e))
            APILogger.log_error(f"任务 {task_id} 字幕检测异常: {str(e)}")
            return {
                "has_subtitles": False,
                "subtitle_type": "hard",
                "dominant_position": "unknown",
                "regions": [],
                "error": str(e)
            }

    @classmethod
    async def _save_analysis_result(cls, task_id: str, analysis_result: Dict[str, Any]):
        """保存分析结果到任务"""
        try:
            # 这里可以将分析结果保存到任务的元数据中
            # 或者保存到单独的存储中
            APILogger.log_debug(f"保存任务 {task_id} 的分析结果")
            # 实现保存逻辑（例如更新数据库或文件）
        except Exception as e:
            APILogger.log_error(f"保存分析结果失败: {str(e)}")

    @classmethod
    async def get_analysis_result(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取字幕分析结果

        Args:
            task_id: 任务ID

        Returns:
            字幕分析结果
        """
        try:
            # 获取任务信息
            task = await TaskService.get_task(task_id)
            if not task:
                return None

            # 这里应该从存储中获取分析结果
            # 目前返回一个示例结果
            result = {
                "has_subtitles": True,
                "subtitle_type": "hard",
                "dominant_position": "bottom",
                "regions": [
                    {
                        "x": 100,
                        "y": 800,
                        "width": 800,
                        "height": 100,
                        "confidence": 0.95,
                        "text_content": "示例字幕文本"
                    }
                ]
            }

            return result
        except Exception as e:
            APILogger.log_error(f"获取分析结果失败: {str(e)}")
            return None

    @classmethod
    async def is_detection_needed(cls, task_id: str) -> bool:
        """
        判断是否需要进行字幕检测

        Args:
            task_id: 任务ID

        Returns:
            是否需要检测
        """
        try:
            task = await TaskService.get_task(task_id)
            if not task:
                return False

            # 如果任务没有指定字幕区域，则需要检测
            return task.subtitle_regions is None or len(task.subtitle_regions) == 0
        except Exception:
            return True