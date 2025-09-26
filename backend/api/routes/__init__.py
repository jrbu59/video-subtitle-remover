#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API路由模块
"""

from .video import router as video_router
from .task import router as task_router

__all__ = ["video_router", "task_router"]