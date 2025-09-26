#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Subtitle Remover API Server
基于FastAPI的视频字幕去除服务
"""

import os
import sys
import uvicorn
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 导入日志工具（必须在路径设置之后）
from backend.api.utils.logger import APILogger

import config
from backend.api.routes.video import router as video_router
from backend.api.routes.task import router as task_router
from backend.api.routes.subtitle_detection import router as subtitle_detection_router
from backend.api.services.storage import ensure_directories


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    APILogger.log_info(f"🚀 Video Subtitle Remover API Server v{config.VERSION} starting...")
    APILogger.log_info(f"📍 Upload directory: {config.UPLOAD_DIR}")
    APILogger.log_info(f"📍 Output directory: {config.OUTPUT_DIR}")

    # 确保存储目录存在
    ensure_directories()

    # 显示可用的算法
    APILogger.log_info("🎯 Available algorithms:")
    APILogger.log_info(f"   - STTN: {'✅ Enabled' if config.MODE == config.InpaintMode.STTN else '⚪ Available'}")
    APILogger.log_info(f"   - LAMA: {'✅ Enabled' if config.MODE == config.InpaintMode.LAMA else '⚪ Available'}")
    APILogger.log_info(f"   - ProPainter: {'✅ Enabled' if config.MODE == config.InpaintMode.PROPAINTER else '⚪ Available'}")

    # 显示设备信息
    if config.USE_DML:
        APILogger.log_info("🖥️  Using DirectML acceleration")
    elif hasattr(config, 'device') and 'cuda' in str(config.device):
        APILogger.log_info("🎮 Using CUDA acceleration")
    else:
        APILogger.log_info("💻 Using CPU processing")

    yield

    # 关闭时执行
    APILogger.log_info("👋 Video Subtitle Remover API Server shutting down...")


# 创建FastAPI应用实例
app = FastAPI(
    title="Video Subtitle Remover API",
    description="""
    ## 视频字幕去除API服务

    基于AI技术的硬字幕去除服务，支持多种算法和处理模式。

    ### 🎯 支持的算法

    - **STTN**: 适合真人视频，处理速度快，可跳过字幕检测
    - **LAMA**: 适合动画视频，静态内容效果最佳
    - **ProPainter**: 适合高运动场景，显存需求较高

    ### 📁 支持的格式

    **视频格式**: MP4, AVI, MOV, MKV, WMV, FLV, WebM, M4V

    **图片格式**: JPG, JPEG, PNG, BMP, TIFF, WebP

    ### 🚀 使用流程

    1. **上传文件**: POST `/api/upload`
    2. **开始处理**: POST `/api/process`
    3. **查询状态**: GET `/api/task/{task_id}`
    4. **下载结果**: GET `/api/download/{task_id}`

    ### 🔧 配置参数

    可通过 `config_override` 参数覆盖默认配置，支持的参数包括：
    - `STTN_SKIP_DETECTION`: 跳过字幕检测（仅STTN算法）
    - `STTN_NEIGHBOR_STRIDE`: 相邻帧步长
    - `STTN_REFERENCE_LENGTH`: 参考帧数量
    - `LAMA_SUPER_FAST`: 极速模式
    - 更多参数请参考配置文档
    """,
    version=config.VERSION,
    docs_url="/docs",          # Swagger UI 文档地址
    redoc_url="/redoc",        # ReDoc 文档地址
    openapi_url="/openapi.json", # OpenAPI schema地址
    contact={
        "name": "Video Subtitle Remover",
        "url": "https://github.com/YaoFANGUK/video-subtitle-remover",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan
)

# 添加日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    request_id = APILogger.generate_request_id()

    # 记录请求
    APILogger.log_request(
        request_id=request_id,
        method=request.method,
        url=str(request.url),
        client=request.client.host if request.client else "unknown",
        headers=request.headers
    )

    try:
        response = await call_next(request)
        process_time = time.time() - start_time

        # 记录响应
        APILogger.log_response(
            request_id=request_id,
            status_code=response.status_code,
            process_time=process_time
        )

        # 添加请求ID到响应头
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        process_time = time.time() - start_time
        APILogger.log_response(
            request_id=request_id,
            status_code=500,
            process_time=process_time,
            response_data=str(e)
        )
        raise e

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(video_router, prefix="/api", tags=["视频处理"])
app.include_router(task_router, prefix="/api", tags=["任务管理"])
app.include_router(subtitle_detection_router, prefix="/api", tags=["字幕检测"])

# 静态文件服务（用于下载处理后的文件）
if os.path.exists(config.OUTPUT_DIR):
    app.mount("/files", StaticFiles(directory=config.OUTPUT_DIR), name="files")


@app.get("/", include_in_schema=False)
async def root():
    """根路径重定向到API文档"""
    return RedirectResponse(url="/docs")


@app.get("/api/health", tags=["系统状态"])
async def health_check():
    """
    健康检查接口

    返回服务状态和系统信息
    """
    import torch
    import platform

    return {
        "status": "healthy",
        "version": config.VERSION,
        "system": {
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "torch_version": torch.__version__,
        },
        "config": {
            "default_algorithm": config.MODE.value,
            "use_dml": config.USE_DML,
            "cuda_available": torch.cuda.is_available(),
            "max_file_size_mb": config.MAX_FILE_SIZE // (1024 * 1024),
            "file_retention_hours": config.FILE_RETENTION_HOURS,
        },
        "storage": {
            "upload_dir": config.UPLOAD_DIR,
            "output_dir": config.OUTPUT_DIR,
        }
    }


@app.get("/api/algorithms", tags=["系统状态"])
async def get_algorithms():
    """
    获取可用算法列表

    返回所有支持的算法及其描述
    """
    return {
        "algorithms": [
            {
                "name": "sttn",
                "display_name": "STTN",
                "description": "适合真人视频，处理速度快，可跳过字幕检测",
                "features": ["高速处理", "可跳过检测", "真人视频优化"],
                "default": config.MODE == config.InpaintMode.STTN
            },
            {
                "name": "lama",
                "display_name": "LAMA",
                "description": "适合动画视频，静态内容效果最佳",
                "features": ["高质量修复", "动画优化", "静态内容"],
                "default": config.MODE == config.InpaintMode.LAMA
            },
            {
                "name": "propainter",
                "display_name": "ProPainter",
                "description": "适合高运动场景，显存需求较高",
                "features": ["高运动场景", "高质量", "大显存需求"],
                "default": config.MODE == config.InpaintMode.PROPAINTER
            }
        ],
        "default_algorithm": config.MODE.value
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False,  # 生产环境应设为False
        access_log=True
    )