# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Video-subtitle-remover (VSR) 是一个基于AI技术的硬字幕去除软件。支持GUI和CLI两种界面，使用多种AI算法进行字幕检测和修复。

## 开发命令

### 运行应用

- **图形界面版本**: `python gui.py`
- **命令行版本**: `python ./backend/main.py`

### 环境配置

项目需要Python 3.12+，支持三种计算后端：

1. **CUDA (NVIDIA显卡)**:
   ```bash
   pip install paddlepaddle-gpu==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
   pip install torch==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cu118
   pip install -r requirements.txt
   ```

2. **DirectML (Windows下AMD/Intel显卡)**:
   ```bash
   pip install paddlepaddle==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
   pip install -r requirements.txt
   pip install torch_directml==0.2.5.dev240914
   ```

### Docker支持

项目为不同GPU架构提供Docker镜像：
- CUDA 11.8 (RTX 10/20/30系): `eritpchy/video-subtitle-remover:1.1.1-cuda11.8`
- CUDA 12.6 (RTX 40系): `eritpchy/video-subtitle-remover:1.1.1-cuda12.6`
- CUDA 12.8 (RTX 50系): `eritpchy/video-subtitle-remover:1.1.1-cuda12.8`
- DirectML (AMD/Intel): `eritpchy/video-subtitle-remover:1.1.1-directml`

## 架构概览

### 核心组件

1. **GUI界面** (`gui.py`): 基于PySimpleGUI的图形界面
2. **后端处理** (`backend/main.py`): 核心字幕检测和去除逻辑
3. **配置管理** (`backend/config.py`): 所有算法和参数的集中配置

### 关键模块

- **`backend/inpaint/`**: 包含三种修复算法:
  - `sttn_inpaint.py`: STTN算法（速度快，适合真人视频）
  - `lama_inpaint.py`: LAMA算法（图片效果最好，适合动画）
  - `video_inpaint.py`: ProPainter算法（显存需求高，适合高运动视频）

- **`backend/scenedetect/`**: 视频场景检测工具
- **`backend/tools/`**: 视频处理和训练的工具函数
- **`backend/ffmpeg/`**: 平台特定的FFmpeg二进制文件

### 算法选择

系统支持三种修复模式，在`backend/config.py`中配置：

- `InpaintMode.STTN`: 处理速度快，可跳过字幕检测，适合真人视频
- `InpaintMode.LAMA`: 静态内容质量最佳，不可跳过检测
- `InpaintMode.PROPAINTER`: 显存占用高，适合高运动场景

### 关键配置参数

`backend/config.py`中的重要设置：
- `MODE`: 算法选择
- `STTN_SKIP_DETECTION`: 跳过字幕检测以加快处理速度
- `STTN_NEIGHBOR_STRIDE`, `STTN_REFERENCE_LENGTH`: 质量与速度的权衡
- `PROPAINTER_MAX_LOAD_NUM`: 内存与质量的平衡
- `LAMA_SUPER_FAST`: LAMA算法的速度与质量权衡

### 测试

测试视频位于`test/`目录中，用于验证算法更改。

## 重要说明

- 项目自动处理模型文件的分割/合并（使用`filesplit`）
- 包含所有平台的FFmpeg二进制文件并自动配置
- 设备选择自动检测CUDA、DirectML或CPU回退
- 所有AI模型在启动时加载并缓存以提高性能