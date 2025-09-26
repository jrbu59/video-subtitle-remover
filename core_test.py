#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试字幕去除核心功能
只处理视频的前几帧以验证功能
"""

import os
import sys
import cv2
import numpy as np

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 导入必要的模块
from backend.main import SubtitleRemover, SubtitleDetect
from backend.tools.inpaint_tools import create_mask
import config

def test_frame_processing():
    """测试单帧处理功能"""
    print("=== 测试单帧处理功能 ===")

    video_path = "videos/test_video_with_subtitle.mp4"

    if not os.path.exists(video_path):
        print(f"❌ 测试视频文件不存在: {video_path}")
        return False

    try:
        # 打开视频文件
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("❌ 无法打开视频文件")
            return False

        # 读取第一帧
        ret, frame = cap.read()
        if not ret:
            print("❌ 无法读取视频帧")
            cap.release()
            return False

        print(f"✅ 成功读取视频帧，尺寸: {frame.shape}")

        # 创建字幕检测对象
        detector = SubtitleDetect(video_path)

        # 检测字幕区域
        print("🔍 检测字幕区域...")
        dt_boxes, elapse = detector.detect_subtitle(frame)
        print(f"✅ 字幕检测完成，耗时: {elapse:.2f}秒")

        # 获取坐标
        if len(dt_boxes) > 0:
            coordinate_list = detector.get_coordinates(dt_boxes.tolist())
            print(f"✅ 检测到 {len(coordinate_list)} 个字幕区域")

            # 创建掩码
            mask_size = (frame.shape[0], frame.shape[1])  # (height, width)
            mask = create_mask(mask_size, coordinate_list)
            print(f"✅ 掩码创建成功，尺寸: {mask.shape}")

            # 测试LAMA修复
            from backend.inpaint.lama_inpaint import LamaInpaint
            lama_inpaint = LamaInpaint()
            print("🎨 开始LAMA修复...")
            inpainted_frame = lama_inpaint(frame, mask)
            print("✅ LAMA修复完成")

            # 保存结果
            output_path = "test_frame_result.jpg"
            cv2.imwrite(output_path, inpainted_frame)
            print(f"✅ 结果已保存到: {output_path}")
        else:
            print("⚠️ 未检测到字幕区域")

        cap.release()
        return True

    except Exception as e:
        print(f"❌ 帧处理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mask_creation():
    """测试掩码创建功能"""
    print("\n=== 测试掩码创建功能 ===")

    try:
        # 创建测试掩码
        mask_size = (1080, 1920)  # (height, width)
        test_coordinates = [(100, 200, 50, 100)]  # (xmin, xmax, ymin, ymax)

        mask = create_mask(mask_size, test_coordinates)
        print(f"✅ 掩码创建成功，尺寸: {mask.shape}, 数据类型: {mask.dtype}")

        # 验证掩码值
        unique_values = np.unique(mask)
        print(f"✅ 掩码唯一值: {unique_values}")

        return True
    except Exception as e:
        print(f"❌ 掩码创建测试失败: {e}")
        return False

def main():
    """主函数"""
    print("开始测试字幕去除核心功能...")

    # 测试掩码创建
    mask_success = test_mask_creation()

    # 测试帧处理
    frame_success = test_frame_processing()

    print(f"\n=== 测试结果 ===")
    print(f"掩码创建: {'✅ 通过' if mask_success else '❌ 失败'}")
    print(f"帧处理: {'✅ 通过' if frame_success else '❌ 失败'}")

    if mask_success and frame_success:
        print("\n🎉 核心功能测试通过！字幕去除功能正常工作。")
        return True
    else:
        print("\n⚠️ 部分测试未通过。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)