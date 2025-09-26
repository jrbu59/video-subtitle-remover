# Gemini图片字幕检测和去除测试指南

## 概述

本测试实现了使用Gemini AI检测单张图片中的字幕区域，然后使用LAMA算法去除字幕的完整流程。这是为了验证Gemini检测的准确性，为后续视频处理做准备。

## 文件说明

### 核心文件

1. **single_image_gemini_client.py** - Gemini API客户端
   - 专门用于单张图片的字幕检测
   - 使用Google AI Studio API端点
   - 支持精确的字幕区域坐标检测

2. **test_image_subtitle_removal_with_gemini.py** - 完整测试脚本
   - 集成Gemini检测和LAMA去字幕功能
   - 提供可视化检测结果
   - 输出详细的处理报告

### 测试图片

- **测试图片**: `/home/jiarui/software/video-subtitle-remover/images/test_image_with_subtitle.jpg`
- 包含顶部和底部的中文字幕文本

## 使用步骤

### 1. 环境准备

确保已安装所有依赖：
```bash
pip install -r requirements.txt
```

### 2. 配置Gemini API密钥

获取Google AI Studio API密钥并设置环境变量：
```bash
export GEMINI_API_KEY='your_api_key_here'
```

### 3. 运行测试

```bash
python test_image_subtitle_removal_with_gemini.py
```

## 输出结果

测试脚本将生成以下文件：

1. **{图片名}_gemini_detection.jpg** - Gemini检测结果可视化
   - 红色框标记检测到的字幕区域
   - 显示置信度和识别的文本内容

2. **{图片名}_lama_removed.jpg** - LAMA去字幕结果
   - 使用LAMA算法修复的最终图片

3. **{图片名}_lama_removed_mask.jpg** - 处理掩码
   - 显示实际处理的区域

## 核心特性

### Gemini检测功能

- **精确定位**: 提供字幕区域的像素级坐标
- **文本识别**: 识别字幕内容
- **置信度评估**: 提供检测结果的可信度
- **智能过滤**: 区分字幕文本和其他文字（如商品包装文字）

### LAMA修复功能

- **高质量修复**: 使用预训练的LAMA模型
- **区域扩展**: 自动扩展掩码区域避免残留边缘
- **设备优化**: 支持CUDA/DirectML/CPU多种后端

## 测试验证要点

1. **检测准确性**: 验证Gemini是否准确识别了字幕区域
2. **区域定位**: 检查边界框是否完全覆盖字幕
3. **修复质量**: 评估LAMA算法的修复效果
4. **背景一致性**: 确保修复区域与周围背景自然融合

## 性能参数

- **图片预处理**: 自动调整大小至1280px宽度以优化API调用
- **掩码扩展**: 默认扩展8像素（可在config.py中调整）
- **LAMA质量**: 使用高质量模式（LAMA_SUPER_FAST=False）

## 故障排除

### 常见问题

1. **API密钥错误**: 确保GEMINI_API_KEY设置正确
2. **网络连接**: 确保能访问Google AI Studio API
3. **模型加载**: 首次运行会自动下载和合并模型文件
4. **内存不足**: 降低图片分辨率或使用CPU模式

### 日志信息

脚本提供详细的日志输出，包括：
- Gemini API调用状态
- 检测结果详情
- LAMA模型加载进度
- 文件保存路径

## 下一步规划

成功验证单张图片的处理效果后，可以：

1. **扩展到视频处理**: 将Gemini检测集成到视频处理流程
2. **批量处理**: 支持批量图片处理
3. **参数优化**: 根据测试结果调整检测和修复参数
4. **性能优化**: 缓存Gemini结果，减少重复调用

## 技术细节

- **Gemini模型**: gemini-1.5-pro
- **检测精度**: 像素级边界框
- **修复算法**: LAMA (Large Mask Inpainting)
- **支持格式**: JPG, PNG等常见图片格式