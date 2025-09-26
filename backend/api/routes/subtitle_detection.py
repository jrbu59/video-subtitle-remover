#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕检测相关API路由
"""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from backend.api.models.response import APIResponse, ErrorResponse
from backend.api.services.subtitle_detection_service import SubtitleDetectionService
from backend.api.services.task_service import TaskService

router = APIRouter()

@router.post("/detect-subtitles", summary="检测视频字幕")
async def detect_subtitles(
    task_id: str,
):
    """
    使用Gemini检测视频中的字幕区域

    ### 参数说明:
    - **task_id**: 上传任务的ID

    ### 返回:
    - 字幕检测结果
    """
    try:
        # 获取任务信息
        task = await TaskService.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 执行字幕检测
        detection_result = await SubtitleDetectionService.detect_subtitles(task_id)

        return APIResponse(
            success=True,
            message="字幕检测完成",
            data=detection_result
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"字幕检测失败: {str(e)}")

@router.get("/subtitle-analysis/{task_id}", summary="获取字幕分析结果")
async def get_subtitle_analysis(task_id: str):
    """
    获取指定任务的字幕分析结果

    ### 参数说明:
    - **task_id**: 任务ID

    ### 返回:
    - 字幕分析结果
    """
    try:
        task = await TaskService.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 获取字幕分析结果
        analysis_result = await SubtitleDetectionService.get_analysis_result(task_id)

        if analysis_result is None:
            raise HTTPException(status_code=404, detail="未找到字幕分析结果")

        return APIResponse(
            success=True,
            message="获取字幕分析结果成功",
            data=analysis_result
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取字幕分析结果失败: {str(e)}")