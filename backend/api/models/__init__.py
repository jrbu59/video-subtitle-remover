#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API数据模型
"""

from .task import Task, TaskCreate, TaskResponse, TaskDetail, TaskList, TaskStatus, AlgorithmType
from .response import APIResponse, ErrorResponse, FileInfo, UploadResponse, DownloadInfo, StatusResponse

__all__ = [
    "Task", "TaskCreate", "TaskResponse", "TaskDetail", "TaskList", "TaskStatus", "AlgorithmType",
    "APIResponse", "ErrorResponse", "FileInfo", "UploadResponse", "DownloadInfo", "StatusResponse"
]