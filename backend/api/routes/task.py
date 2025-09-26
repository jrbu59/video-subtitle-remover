#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务管理相关API路由
"""

import os
import sys
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from backend.api.models.response import APIResponse
from backend.api.models.task import TaskDetail, TaskList, TaskStatus
from backend.api.services.task_service import TaskService

router = APIRouter()


@router.get("/task/{task_id}", response_model=TaskDetail, summary="查询任务状态")
async def get_task_status(task_id: str):
    """
    查询指定任务的详细状态

    ### 参数说明:
    - **task_id**: 任务ID

    ### 返回:
    - 任务详细信息，包括状态、进度、错误信息等
    """
    try:
        task = await TaskService.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 构建下载链接
        download_url = None
        if task.status.value == "completed" and task.output_path:
            download_url = f"/api/download/{task_id}"

        return TaskDetail(
            id=task.id,
            status=task.status,
            progress=task.progress,
            algorithm=task.algorithm,
            original_filename=task.original_filename,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            error_message=task.error_message,
            subtitle_regions=task.subtitle_regions,
            file_size=task.file_size,
            duration=task.duration,
            download_url=download_url
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询任务失败: {str(e)}")


@router.get("/tasks", response_model=TaskList, summary="获取任务列表")
async def get_task_list(
    status: Optional[TaskStatus] = Query(default=None, description="按状态筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页大小"),
    order_by: str = Query(default="created_at", description="排序字段"),
    order: str = Query(default="desc", regex="^(asc|desc)$", description="排序方向")
):
    """
    获取任务列表

    ### 参数说明:
    - **status**: 按状态筛选 (pending/processing/completed/failed)
    - **page**: 页码
    - **page_size**: 每页大小 (1-100)
    - **order_by**: 排序字段
    - **order**: 排序方向 (asc/desc)

    ### 返回:
    - 分页的任务列表
    """
    try:
        tasks, total = await TaskService.get_task_list(
            status=status,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order=order
        )

        # 转换为TaskDetail列表
        task_details = []
        for task in tasks:
            download_url = None
            if task.status.value == "completed" and task.output_path:
                download_url = f"/api/download/{task.id}"

            task_details.append(TaskDetail(
                id=task.id,
                status=task.status,
                progress=task.progress,
                algorithm=task.algorithm,
                original_filename=task.original_filename,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
                error_message=task.error_message,
                subtitle_regions=task.subtitle_regions,
                file_size=task.file_size,
                duration=task.duration,
                download_url=download_url
            ))

        return TaskList(
            tasks=task_details,
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")


@router.delete("/task/{task_id}", response_model=APIResponse, summary="删除任务")
async def delete_task(task_id: str):
    """
    删除指定任务及其相关文件

    ### 参数说明:
    - **task_id**: 任务ID

    ### 返回:
    - 删除结果
    """
    try:
        task = await TaskService.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 如果任务正在处理中，不允许删除
        if task.status.value == "processing":
            raise HTTPException(status_code=400, detail="任务正在处理中，无法删除")

        # 删除任务和相关文件
        await TaskService.delete_task(task_id)

        return APIResponse(
            success=True,
            message="任务删除成功",
            data={"task_id": task_id}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")


@router.post("/task/{task_id}/cancel", response_model=APIResponse, summary="取消任务")
async def cancel_task(task_id: str):
    """
    取消正在处理的任务

    ### 参数说明:
    - **task_id**: 任务ID

    ### 返回:
    - 取消结果
    """
    try:
        task = await TaskService.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        if task.status.value != "processing":
            raise HTTPException(status_code=400, detail="只能取消正在处理的任务")

        # 取消任务
        await TaskService.cancel_task(task_id)

        return APIResponse(
            success=True,
            message="任务取消成功",
            data={"task_id": task_id}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")


@router.post("/tasks/cleanup", response_model=APIResponse, summary="清理过期任务")
async def cleanup_expired_tasks():
    """
    清理过期的任务和文件

    ### 返回:
    - 清理结果统计
    """
    try:
        result = await TaskService.cleanup_expired_tasks()

        return APIResponse(
            success=True,
            message="清理完成",
            data=result
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.get("/tasks/stats", response_model=APIResponse, summary="获取任务统计")
async def get_task_statistics():
    """
    获取任务统计信息

    ### 返回:
    - 各状态任务数量统计
    """
    try:
        stats = await TaskService.get_task_statistics()

        return APIResponse(
            success=True,
            message="统计信息获取成功",
            data=stats
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")