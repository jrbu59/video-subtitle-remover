#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终验证字幕去除效果
"""

import os
import cv2
import numpy as np

def analyze_subtitle_removal_effect():
    """分析字幕去除效果"""

    print(f"\n{'='*80}")
    print("最终验证：字幕去除效果分析")
    print(f"{'='*80}")

    # 视频路径
    original_video = "/home/jiarui/software/video-subtitle-remover/videos/test_video_with_subtitle.mp4"
    first_attempt = "/home/jiarui/software/video-subtitle-remover/videos/test_video_with_subtitle_no_subtitle_timed.mp4"
    corrected_attempt = "/home/jiarui/software/video-subtitle-remover/videos/test_video_corrected_regions.mp4"

    # 测试帧
    test_frames = [10, 50, 100, 200, 250]

    print(f"对比视频:")
    print(f"1. 原始视频: test_video_with_subtitle.mp4")
    print(f"2. 首次处理: test_video_with_subtitle_no_subtitle_timed.mp4")
    print(f"3. 修正处理: test_video_corrected_regions.mp4")
    print(f"\n分析帧: {test_frames}")
    print(f"{'='*80}")

    for frame_no in test_frames:
        print(f"\n📋 帧 {frame_no} (时间: {frame_no/30:.1f}s):")

        # 读取三个版本的帧
        cap_orig = cv2.VideoCapture(original_video)
        cap_first = cv2.VideoCapture(first_attempt)
        cap_corrected = cv2.VideoCapture(corrected_attempt)

        cap_orig.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        cap_first.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        cap_corrected.set(cv2.CAP_PROP_POS_FRAMES, frame_no)

        ret1, orig = cap_orig.read()
        ret2, first = cap_first.read()
        ret3, corrected = cap_corrected.read()

        if ret1 and ret2 and ret3:
            # 计算差异
            diff_first = cv2.absdiff(orig, first)
            diff_corrected = cv2.absdiff(orig, corrected)

            # 转换为灰度并计算统计
            diff_first_gray = cv2.cvtColor(diff_first, cv2.COLOR_BGR2GRAY)
            diff_corrected_gray = cv2.cvtColor(diff_corrected, cv2.COLOR_BGR2GRAY)

            # 计算变化像素
            changed_first = np.count_nonzero(diff_first_gray > 10)
            changed_corrected = np.count_nonzero(diff_corrected_gray > 10)

            total_pixels = diff_first_gray.shape[0] * diff_first_gray.shape[1]
            ratio_first = changed_first / total_pixels * 100
            ratio_corrected = changed_corrected / total_pixels * 100

            # 分析字幕区域（底部20%）
            height = orig.shape[0]
            subtitle_region = orig[int(height*0.8):, :]
            subtitle_first = first[int(height*0.8):, :]
            subtitle_corrected = corrected[int(height*0.8):, :]

            subtitle_diff_first = cv2.absdiff(subtitle_region, subtitle_first)
            subtitle_diff_corrected = cv2.absdiff(subtitle_region, subtitle_corrected)

            subtitle_diff_first_gray = cv2.cvtColor(subtitle_diff_first, cv2.COLOR_BGR2GRAY)
            subtitle_diff_corrected_gray = cv2.cvtColor(subtitle_diff_corrected, cv2.COLOR_BGR2GRAY)

            subtitle_changed_first = np.count_nonzero(subtitle_diff_first_gray > 10)
            subtitle_changed_corrected = np.count_nonzero(subtitle_diff_corrected_gray > 10)

            subtitle_pixels = subtitle_diff_first_gray.shape[0] * subtitle_diff_first_gray.shape[1]
            subtitle_ratio_first = subtitle_changed_first / subtitle_pixels * 100 if subtitle_pixels > 0 else 0
            subtitle_ratio_corrected = subtitle_changed_corrected / subtitle_pixels * 100 if subtitle_pixels > 0 else 0

            print(f"   全帧变化:")
            print(f"     首次处理: {ratio_first:.2f}% ({changed_first}/{total_pixels})")
            print(f"     修正处理: {ratio_corrected:.2f}% ({changed_corrected}/{total_pixels})")

            print(f"   字幕区域变化 (底部20%):")
            print(f"     首次处理: {subtitle_ratio_first:.2f}% ({subtitle_changed_first}/{subtitle_pixels})")
            print(f"     修正处理: {subtitle_ratio_corrected:.2f}% ({subtitle_changed_corrected}/{subtitle_pixels})")

            # 判断哪个效果更好
            if subtitle_ratio_corrected > subtitle_ratio_first * 2:
                print(f"   ✅ 修正处理效果更好 (字幕区域变化更大)")
            elif subtitle_ratio_first > subtitle_ratio_corrected * 2:
                print(f"   ⚠️  首次处理效果更好 (字幕区域变化更大)")
            else:
                print(f"   🤔 两次处理效果相近")

            # 保存三方对比图
            comparison_dir = "final_comparison"
            os.makedirs(comparison_dir, exist_ok=True)

            # 创建三方对比
            comparison = np.hstack([orig, first, corrected])

            # 添加标签
            label_height = 60
            labeled_comparison = np.zeros((comparison.shape[0] + label_height, comparison.shape[1], 3), dtype=np.uint8)
            labeled_comparison[label_height:, :] = comparison

            # 添加文字标签
            cv2.putText(labeled_comparison, "ORIGINAL", (50, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
            cv2.putText(labeled_comparison, "FIRST ATTEMPT", (orig.shape[1] + 50, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 2)
            cv2.putText(labeled_comparison, "CORRECTED", (orig.shape[1] + first.shape[1] + 50, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2)

            comp_path = os.path.join(comparison_dir, f"final_comparison_frame_{frame_no:04d}.jpg")
            cv2.imwrite(comp_path, labeled_comparison)

        cap_orig.release()
        cap_first.release()
        cap_corrected.release()

    print(f"\n{'='*80}")
    print("总结")
    print(f"{'='*80}")
    print("1. 检查 final_comparison/ 目录中的对比图片")
    print("2. 每张图显示：原始 | 首次处理 | 修正处理")
    print("3. 重点观察字幕区域（底部）的变化效果")
    print("4. 如果修正处理的字幕区域变化明显更大，说明修正成功")

    # 检查原视频分辨率信息
    cap = cv2.VideoCapture(original_video)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    print(f"\n视频分辨率: {width}x{height}")
    print(f"字幕区域估计: 底部20% (Y坐标 {int(height*0.8)} - {height})")

    # 对比区域坐标
    print(f"\n区域坐标对比:")
    print(f"首次处理 (错误): (108, 1632) - 超出视频高度!")
    print(f"修正处理 (正确): (54, {int(height*0.8)}) - 在视频范围内")

    print(f"\n📸 三方对比图已保存到: final_comparison/")
    print("请查看对比图片确认字幕去除效果")


if __name__ == "__main__":
    analyze_subtitle_removal_effect()