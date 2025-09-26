#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试字幕区域标记问题的脚本
"""

import os
import sys
import cv2
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.api.models.timed_subtitle import TimedSubtitleRegion


def analyze_frame_differences(original_path: str, processed_path: str):
    """分析两帧之间的差异"""
    orig = cv2.imread(original_path)
    proc = cv2.imread(processed_path)

    if orig is None or proc is None:
        return None

    # 计算差异
    diff = cv2.absdiff(orig, proc)

    # 转换为灰度
    diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

    # 计算差异统计
    total_pixels = diff_gray.shape[0] * diff_gray.shape[1]
    changed_pixels = np.count_nonzero(diff_gray > 10)  # 阈值10
    change_ratio = changed_pixels / total_pixels

    return {
        "total_pixels": total_pixels,
        "changed_pixels": changed_pixels,
        "change_ratio": change_ratio,
        "max_diff": np.max(diff_gray),
        "mean_diff": np.mean(diff_gray)
    }


def draw_region_on_frame(frame, region_info, color=(0, 255, 0), thickness=3):
    """在帧上绘制字幕区域"""
    x, y, w, h = region_info["x"], region_info["y"], region_info["width"], region_info["height"]

    # 绘制矩形
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)

    # 添加文本标签
    label = f"Region: {w}x{h}"
    cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    return frame


def create_mock_regions_for_video(video_path: str):
    """为视频创建模拟的字幕区域（和测试脚本中一致）"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cap.release()

    regions = []

    # 第一段字幕 (0-40%视频时长)
    if total_frames > 30:
        end_frame = min(int(total_frames * 0.4), total_frames - 1)
        region1 = {
            "start_frame": 0,
            "end_frame": end_frame,
            "x": int(width * 0.1),
            "y": int(height * 0.85),
            "width": int(width * 0.8),
            "height": int(height * 0.1)
        }
        regions.append(region1)
        logger.info(f"模拟区域1: 帧 0-{end_frame}, 位置 ({region1['x']}, {region1['y']}) 大小 {region1['width']}x{region1['height']}")

    # 第二段字幕 (60%-90%视频时长)
    if total_frames > 60:
        start_frame = int(total_frames * 0.6)
        end_frame = min(int(total_frames * 0.9), total_frames - 1)
        if start_frame < end_frame:
            region2 = {
                "start_frame": start_frame,
                "end_frame": end_frame,
                "x": int(width * 0.1),
                "y": int(height * 0.85),
                "width": int(width * 0.8),
                "height": int(height * 0.1)
            }
            regions.append(region2)
            logger.info(f"模拟区域2: 帧 {start_frame}-{end_frame}, 位置 ({region2['x']}, {region2['y']}) 大小 {region2['width']}x{region2['height']}")

    return regions


def check_frame_in_subtitle_timespan(frame_no: int, regions: list) -> list:
    """检查帧是否在字幕时间段内"""
    active_regions = []
    for region in regions:
        if region["start_frame"] <= frame_no <= region["end_frame"]:
            active_regions.append(region)
    return active_regions


def analyze_subtitle_regions():
    """分析字幕区域标记问题"""

    print(f"\n{'='*80}")
    print("字幕区域标记调试分析")
    print(f"{'='*80}")

    # 视频路径
    original_video = "/home/jiarui/software/video-subtitle-remover/videos/test_video_with_subtitle.mp4"
    processed_video = "/home/jiarui/software/video-subtitle-remover/videos/test_video_with_subtitle_no_subtitle_timed.mp4"

    # 获取模拟区域（和测试脚本中一致）
    regions = create_mock_regions_for_video(original_video)

    print(f"\n1. 字幕区域配置检查:")
    print(f"   共配置 {len(regions)} 个时间段")
    for i, region in enumerate(regions):
        start_time = region["start_frame"] / 30.0  # 假设30fps
        end_time = region["end_frame"] / 30.0
        print(f"   区域{i+1}: {start_time:.1f}s-{end_time:.1f}s, 位置({region['x']},{region['y']}) 大小{region['width']}x{region['height']}")

    # 分析对比帧
    comparison_dir = "frame_comparisons"
    frame_files = [f for f in os.listdir(comparison_dir) if f.endswith("_original.jpg")]
    frame_files.sort()

    print(f"\n2. 帧差异分析:")
    print(f"   {'帧号':<8} {'时间(s)':<8} {'是否应处理':<12} {'像素变化率':<12} {'平均差异':<12} {'最大差异':<8}")
    print("-" * 80)

    should_be_processed = 0
    actually_changed = 0

    for frame_file in frame_files:
        frame_no = int(frame_file.split("_")[1])
        time_sec = frame_no / 30.0

        # 检查是否应该被处理
        active_regions = check_frame_in_subtitle_timespan(frame_no, regions)
        should_process = len(active_regions) > 0

        if should_process:
            should_be_processed += 1

        # 分析实际差异
        original_path = os.path.join(comparison_dir, frame_file)
        processed_path = os.path.join(comparison_dir, frame_file.replace("_original.jpg", "_processed.jpg"))

        diff_stats = analyze_frame_differences(original_path, processed_path)

        if diff_stats:
            has_changes = diff_stats["change_ratio"] > 0.001  # 0.1%变化阈值
            if has_changes:
                actually_changed += 1

            status = "✓应处理" if should_process else "✗跳过"
            print(f"   {frame_no:<8} {time_sec:<8.1f} {status:<12} {diff_stats['change_ratio']:<12.3%} {diff_stats['mean_diff']:<12.1f} {diff_stats['max_diff']:<8}")
        else:
            status = "✓应处理" if should_process else "✗跳过"
            print(f"   {frame_no:<8} {time_sec:<8.1f} {status:<12} {'ERROR':<12} {'ERROR':<12} {'ERROR':<8}")

    print(f"\n3. 处理统计:")
    print(f"   应该被处理的帧: {should_be_processed}/{len(frame_files)}")
    print(f"   实际有变化的帧: {actually_changed}/{len(frame_files)}")

    if should_be_processed > 0 and actually_changed == 0:
        print("\n❌ 问题发现：应该处理的帧没有任何变化！")
        print("   可能原因:")
        print("   1. 字幕区域坐标错误，未覆盖实际字幕位置")
        print("   2. 时间段设置错误，处理的帧没有字幕")
        print("   3. VSR处理逻辑有问题，没有实际进行inpaint")

    elif should_be_processed > 0 and actually_changed < should_be_processed:
        print(f"\n⚠️  部分问题：{should_be_processed}帧应处理，但只有{actually_changed}帧有变化")

    elif should_be_processed == actually_changed and actually_changed > 0:
        print(f"\n✅ 处理正常：{should_be_processed}帧应处理，{actually_changed}帧实际有变化")
        print("   但字幕可能没有完全去除，需要检查区域坐标精度")

    # 创建带区域标记的对比图
    print(f"\n4. 创建带区域标记的调试图片:")
    debug_dir = "debug_regions"
    os.makedirs(debug_dir, exist_ok=True)

    for frame_file in frame_files[:3]:  # 只处理前3帧
        frame_no = int(frame_file.split("_")[1])
        active_regions = check_frame_in_subtitle_timespan(frame_no, regions)

        if active_regions:  # 只为应该处理的帧创建调试图
            original_path = os.path.join(comparison_dir, frame_file)
            frame = cv2.imread(original_path)

            if frame is not None:
                # 在帧上标记字幕区域
                for region in active_regions:
                    frame = draw_region_on_frame(frame, region, color=(0, 255, 0), thickness=3)

                # 保存调试图
                debug_path = os.path.join(debug_dir, f"debug_frame_{frame_no:04d}_with_regions.jpg")
                cv2.imwrite(debug_path, frame)
                print(f"   保存调试图: {debug_path}")


if __name__ == "__main__":
    analyze_subtitle_regions()