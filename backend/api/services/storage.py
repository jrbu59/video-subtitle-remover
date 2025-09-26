#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件存储管理服务
"""

import os
import cv2
import aiofiles
from typing import Optional
from fastapi import UploadFile, HTTPException

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import config
from backend.api.models.response import FileInfo


def ensure_directories():
    """确保必要的目录存在"""
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)


def validate_file(file: UploadFile):
    """验证上传的文件"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 检查文件扩展名
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in config.SUPPORTED_VIDEO_FORMATS and file_ext not in config.SUPPORTED_IMAGE_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}. "
                   f"支持的格式: {', '.join(config.SUPPORTED_VIDEO_FORMATS | config.SUPPORTED_IMAGE_FORMATS)}"
        )

    # 检查文件大小
    if hasattr(file, 'size') and file.size and file.size > config.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大. 最大支持: {config.MAX_FILE_SIZE // (1024*1024)}MB"
        )


async def get_file_info(file_path: str, original_filename: str) -> FileInfo:
    """获取文件信息"""
    try:
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        file_ext = os.path.splitext(original_filename)[1].lower()

        duration = None
        resolution = None

        # 如果是视频文件，获取视频信息
        if file_ext in config.SUPPORTED_VIDEO_FORMATS:
            try:
                cap = cv2.VideoCapture(file_path)
                if cap.isOpened():
                    # 获取视频时长
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    if fps > 0:
                        duration = frame_count / fps

                    # 获取分辨率
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    resolution = f"{width}x{height}"

                cap.release()
            except Exception as e:
                print(f"获取视频信息失败: {e}")

        # 如果是图片文件，获取图片信息
        elif file_ext in config.SUPPORTED_IMAGE_FORMATS:
            try:
                img = cv2.imread(file_path)
                if img is not None:
                    height, width = img.shape[:2]
                    resolution = f"{width}x{height}"
            except Exception as e:
                print(f"获取图片信息失败: {e}")

        return FileInfo(
            filename=original_filename,
            size=file_size,
            format=file_ext,
            duration=duration,
            resolution=resolution
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件信息失败: {str(e)}")


def get_upload_path(task_id: str, original_filename: str) -> str:
    """生成上传文件路径"""
    file_ext = os.path.splitext(original_filename)[1]
    filename = f"{task_id}{file_ext}"
    return os.path.join(config.UPLOAD_DIR, filename)


def get_output_path(task_id: str, original_filename: str) -> str:
    """生成输出文件路径"""
    name, ext = os.path.splitext(original_filename)

    # 对于图片，保持原扩展名；对于视频，统一使用.mp4
    if ext.lower() in config.SUPPORTED_IMAGE_FORMATS:
        output_ext = ext
    else:
        output_ext = '.mp4'

    filename = f"{task_id}_no_sub{output_ext}"
    return os.path.join(config.OUTPUT_DIR, filename)


async def save_upload_file(file: UploadFile, file_path: str) -> str:
    """保存上传的文件"""
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        return file_path
    except Exception as e:
        # 如果保存失败，清理部分文件
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")


def delete_file(file_path: str) -> bool:
    """删除文件"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception as e:
        print(f"删除文件失败 {file_path}: {e}")
        return False


def cleanup_task_files(task_id: str, file_path: Optional[str] = None, output_path: Optional[str] = None):
    """清理任务相关的所有文件"""
    deleted_files = []

    # 删除上传文件
    if file_path and os.path.exists(file_path):
        if delete_file(file_path):
            deleted_files.append(file_path)

    # 删除输出文件
    if output_path and os.path.exists(output_path):
        if delete_file(output_path):
            deleted_files.append(output_path)

    # 删除可能的临时文件
    for directory in [config.UPLOAD_DIR, config.OUTPUT_DIR]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if task_id in filename:
                    file_path = os.path.join(directory, filename)
                    if delete_file(file_path):
                        deleted_files.append(file_path)

    return deleted_files


def get_directory_size(directory: str) -> int:
    """获取目录总大小"""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
    except Exception as e:
        print(f"计算目录大小失败 {directory}: {e}")
    return total_size


def get_storage_info():
    """获取存储信息"""
    return {
        "upload_dir": {
            "path": config.UPLOAD_DIR,
            "size": get_directory_size(config.UPLOAD_DIR),
            "exists": os.path.exists(config.UPLOAD_DIR)
        },
        "output_dir": {
            "path": config.OUTPUT_DIR,
            "size": get_directory_size(config.OUTPUT_DIR),
            "exists": os.path.exists(config.OUTPUT_DIR)
        },
        "max_file_size": config.MAX_FILE_SIZE,
        "retention_hours": config.FILE_RETENTION_HOURS
    }