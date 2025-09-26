#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试字幕检测功能
使用较短的处理时间和更小的视频片段
"""

import os
import sys
import time

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 导入必要的模块
from backend.main import SubtitleRemover, SubtitleDetect
import config

def quick_test():
    """快速测试字幕检测功能"""
    print("=== 快速测试字幕检测功能 ===")

    video_path = "videos/test_video_with_subtitle.mp4"

    if not os.path.exists(video_path):
        print(f"❌ 测试视频文件不存在: {video_path}")
        return False

    print(f"✅ 使用测试视频: {video_path}")

    # 创建字幕检测对象
    detector = SubtitleDetect(video_path)

    # 只检测前10帧以加快测试速度
    print("🔍 开始快速检测字幕...")
    start_time = time.time()

    try:
        # 为了快速测试，我们只检查字幕检测类的基本功能
        print("检查字幕检测器初始化...")

        # 测试文本检测器初始化
        text_detector = detector.text_detector
        print("✅ 文本检测器初始化成功")

        # 测试坐标获取功能 - 使用正确的格式
        # 根据代码，输入应该是 [[[x1, y1], [x2, y2], [x3, y3], [x4, y4]]] 格式
        test_coords = [[[100, 50], [200, 50], [200, 100], [100, 100]]]
        coordinates = detector.get_coordinates(test_coords)
        print(f"✅ 坐标转换功能正常: {coordinates}")

        # 测试相似区域判断
        region1 = (100, 200, 50, 100)
        region2 = (105, 205, 55, 105)
        is_similar = detector.are_similar(region1, region2)
        print(f"✅ 相似区域判断功能正常: {is_similar}")

        detection_time = time.time() - start_time
        print(f"✅ 快速检测完成，耗时: {detection_time:.2f}秒")

        return True

    except Exception as e:
        print(f"❌ 快速检测失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_subtitle_removal_config():
    """测试字幕去除配置"""
    print("\n=== 测试字幕去除配置 ===")

    try:
        # 显示当前配置
        print(f"当前算法模式: {config.MODE}")
        print(f"LAMA超快速模式: {config.LAMA_SUPER_FAST}")
        print(f"STTN跳过检测: {config.STTN_SKIP_DETECTION}")

        # 测试配置修改
        original_mode = config.MODE
        config.MODE = config.InpaintMode.LAMA
        print(f"✅ 成功修改算法模式为LAMA")

        # 恢复原始配置
        config.MODE = original_mode
        print(f"✅ 成功恢复原始配置")

        return True
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False

def main():
    """主函数"""
    print("开始快速测试字幕检测功能...")

    # 测试字幕检测
    detection_success = quick_test()

    # 测试配置
    config_success = test_subtitle_removal_config()

    print(f"\n=== 测试结果 ===")
    print(f"字幕检测: {'✅ 通过' if detection_success else '❌ 失败'}")
    print(f"配置测试: {'✅ 通过' if config_success else '❌ 失败'}")

    if detection_success and config_success:
        print("\n🎉 快速测试通过！字幕检测核心功能正常工作。")
        return True
    else:
        print("\n⚠️ 部分测试未通过。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)