#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频处理相关API路由
"""

import os
import uuid
import aiofiles
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import config
from backend.api.models.response import APIResponse, UploadResponse, FileInfo, ErrorResponse
from backend.api.models.task import TaskCreate, TaskResponse, AlgorithmType
from backend.api.services.video_service import VideoService
from backend.api.services.task_service import TaskService
from backend.api.services.storage import validate_file, get_file_info

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, summary="上传视频文件")
async def upload_video(
    file: UploadFile = File(..., description="要处理的视频或图片文件"),
    algorithm: Optional[AlgorithmType] = Form(default=AlgorithmType.STTN, description="选择处理算法"),
    subtitle_regions: Optional[str] = Form(default=None, description="字幕区域JSON字符串，格式: [[x1,y1,x2,y2],...]"),
    config_override: Optional[str] = Form(default=None, description="配置覆盖JSON字符串"),
    auto_detect_subtitles: bool = Form(default=False, description="是否自动检测字幕区域（使用Gemini）")
):
    """
    上传视频文件进行字幕去除处理

    ### 参数说明:
    - **file**: 视频或图片文件
    - **algorithm**: 处理算法 (sttn/lama/propainter)
    - **subtitle_regions**: 指定字幕区域坐标 (可选)
    - **config_override**: 覆盖默认配置参数 (可选)
    - **auto_detect_subtitles**: 是否自动检测字幕区域（使用Gemini）

    ### 支持格式:
    - 视频: MP4, AVI, MOV, MKV, WMV, FLV, WebM, M4V
    - 图片: JPG, JPEG, PNG, BMP, TIFF, WebP

    ### 返回:
    - 任务ID和文件信息
    """
    try:
        # 验证文件
        validate_file(file)

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 保存上传的文件
        file_path = await VideoService.save_uploaded_file(file, task_id)

        # 获取文件信息
        file_info = await get_file_info(file_path, file.filename)

        # 解析额外参数
        import json
        parsed_regions = None
        parsed_config = None

        if subtitle_regions:
            try:
                parsed_regions = json.loads(subtitle_regions)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="字幕区域格式错误")

        if config_override:
            try:
                parsed_config = json.loads(config_override)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="配置覆盖格式错误")

        # 创建任务
        task_create = TaskCreate(
            algorithm=algorithm,
            subtitle_regions=parsed_regions,
            config_override=parsed_config,
            auto_detect_subtitles=auto_detect_subtitles
        )

        task = await TaskService.create_task(
            task_id=task_id,
            task_create=task_create,
            original_filename=file.filename,
            file_path=file_path,
            file_size=file_info.size,
            duration=file_info.duration
        )

        return UploadResponse(
            message="文件上传成功",
            task_id=task_id,
            file_info=file_info
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/process", response_model=TaskResponse, summary="开始处理任务")
async def start_processing(
    task_id: str = Form(..., description="任务ID"),
    start_immediately: bool = Form(default=True, description="是否立即开始处理"),
    auto_detect_subtitles: bool = Form(default=False, description="是否自动检测字幕区域（使用Gemini）")
):
    """
    开始视频字幕去除处理

    ### 参数说明:
    - **task_id**: 上传时返回的任务ID
    - **start_immediately**: 是否立即开始处理
    - **auto_detect_subtitles**: 是否自动检测字幕区域（使用Gemini）

    ### 返回:
    - 任务状态和消息
    """
    try:
        task = await TaskService.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        if start_immediately:
            # 启动后台处理任务，可能包含自动字幕检测
            auto_detect = auto_detect_subtitles or (hasattr(task, 'auto_detect_subtitles') and task.auto_detect_subtitles)
            await VideoService.start_processing_task(task_id, auto_detect_subtitles=auto_detect)

        return TaskResponse(
            task_id=task_id,
            status=task.status,
            message="任务已开始处理" if start_immediately else "任务已创建，等待处理"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理启动失败: {str(e)}")


@router.get("/download/{task_id}", summary="下载处理结果")
async def download_result(task_id: str):
    """
    下载处理完成的视频文件

    ### 参数说明:
    - **task_id**: 任务ID

    ### 返回:
    - 处理后的视频文件
    """
    try:
        task = await TaskService.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        if task.status.value != "completed":
            raise HTTPException(status_code=400, detail="任务尚未完成")

        if not task.output_path or not os.path.exists(task.output_path):
            raise HTTPException(status_code=404, detail="输出文件不存在")

        # 返回文件
        filename = task.output_filename or f"{task_id}_processed.mp4"
        return FileResponse(
            path=task.output_path,
            filename=filename,
            media_type='application/octet-stream'
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@router.get("/preview/{task_id}", summary="获取处理预览")
async def get_preview(task_id: str):
    """
    获取处理过程的预览信息

    ### 参数说明:
    - **task_id**: 任务ID

    ### 返回:
    - 预览信息和处理进度
    """
    try:
        task = await TaskService.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 获取预览信息（如果有的话）
        preview_info = await VideoService.get_preview_info(task_id)

        return APIResponse(
            success=True,
            message="预览信息获取成功",
            data={
                "task_id": task_id,
                "status": task.status.value,
                "progress": task.progress,
                "preview": preview_info
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取预览失败: {str(e)}")