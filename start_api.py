#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API服务启动脚本
"""

import os
import sys
import uvicorn

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入配置
import backend.config as config

if __name__ == "__main__":
    uvicorn.run(
        "backend.api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False,
        access_log=True
    )