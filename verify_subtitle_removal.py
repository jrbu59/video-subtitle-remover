#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证字幕去除效果的脚本
使用Gemini分析原视频和处理后视频，对比字幕去除效果
"""

import os
import sys
import logging
import cv2
import numpy as np
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入必要的模块
from backend.api.models.timed_subtitle import TimedSubtitleRegion, TimedSubtitleAnalysis
from backend.api.gemini.token_manager import TokenManager
from backend.api.gemini.gemini_timed_client import GeminiTimedClient
from backend.api.gemini.gemini_client import GeminiClient, SubtitleAnalysis, SubtitleRegion
from backend import config


def analyze_video_with_gemini(video_path: str, client_type="simple") -> dict:
    """
    使用Gemini分析视频中的字幕

    Args:
        video_path: 视频路径
        client_type: 客户端类型 ("simple" 或 "timed")
    """
    try:
        logger.info(f"使用Gemini分析视频: {video_path}")

        # 初始化token管理器
        token_endpoint = "http://api-ladder.ymt.io:8088/rpc/vertexai/accesstoken"
        token_manager = TokenManager(token_endpoint)

        if client_type == "timed":
            # 使用时间段客户端
            gemini_client = GeminiTimedClient(token_manager)
            analysis = gemini_client.analyze_subtitle_with_time(video_path, sample_frames=15)

            if analysis:
                return {
                    "success": True,
                    "has_subtitles": analysis.has_subtitles,
                    "subtitle_type": analysis.subtitle_type,
                    "regions_count": len(analysis.timed_regions),
                    "total_frames": analysis.total_frames,
                    "fps": analysis.fps,
                    "regions": [
                        {
                            "start_frame": r.start_frame,
                            "end_frame": r.end_frame,
                            "x": r.x, "y": r.y, "width": r.width, "height": r.height,
                            "confidence": r.confidence,
                            "text": r.text_content
                        } for r in analysis.timed_regions
                    ]
                }
        else:
            # 使用简单客户端
            gemini_client = GeminiClient(token_manager)
            analysis = gemini_client.analyze_subtitle_with_gemini(video_path, sample_frames=8)

            if analysis:
                return {
                    "success": True,
                    "has_subtitles": analysis.has_subtitles,
                    "subtitle_type": analysis.subtitle_type,
                    "regions_count": len(analysis.regions),
                    "regions": [
                        {
                            "x": r.x, "y": r.y, "width": r.width, "height": r.height,
                            "confidence": r.confidence,
                            "text": r.text_content
                        } for r in analysis.regions
                    ]
                }

        return {"success": False, "error": "Gemini API返回空结果"}

    except Exception as e:
        logger.error(f"Gemini分析异常: {e}")
        return {"success": False, "error": str(e)}


def create_mock_analysis_for_debugging(video_path: str) -> dict:
    """
    创建调试用的模拟分析结果
    """
    # 获取视频信息
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"success": False, "error": "无法打开视频"}

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cap.release()

    logger.info(f"视频信息: {width}x{height}, {total_frames}帧, {fps}fps")

    return {
        "success": True,
        "has_subtitles": True,
        "subtitle_type": "hard",
        "regions_count": 1,
        "regions": [
            {
                "x": int(width * 0.1),
                "y": int(height * 0.85),
                "width": int(width * 0.8),
                "height": int(height * 0.1),
                "confidence": 0.9,
                "text": "Mock subtitle region for debugging"
            }
        ]
    }


def extract_frames_for_comparison(video_path: str, frame_numbers: list) -> dict:
    """
    从视频中提取指定帧用于对比

    Args:
        video_path: 视频路径
        frame_numbers: 要提取的帧号列表
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {}

    frames = {}
    for frame_no in frame_numbers:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ret, frame = cap.read()
        if ret:
            frames[frame_no] = frame

    cap.release()
    return frames


def save_comparison_frames(original_frames: dict, processed_frames: dict, output_dir: str):
    """
    保存对比帧到文件
    """
    os.makedirs(output_dir, exist_ok=True)

    for frame_no in original_frames.keys():
        if frame_no in processed_frames:
            # 保存原始帧
            orig_path = os.path.join(output_dir, f"frame_{frame_no:04d}_original.jpg")
            cv2.imwrite(orig_path, original_frames[frame_no])

            # 保存处理后帧
            proc_path = os.path.join(output_dir, f"frame_{frame_no:04d}_processed.jpg")
            cv2.imwrite(proc_path, processed_frames[frame_no])

            # 创建对比图
            orig = original_frames[frame_no]
            proc = processed_frames[frame_no]

            # 计算差异
            diff = cv2.absdiff(orig, proc)

            # 并排显示
            comparison = np.hstack([orig, proc, diff])
            comp_path = os.path.join(output_dir, f"frame_{frame_no:04d}_comparison.jpg")
            cv2.imwrite(comp_path, comparison)

            logger.info(f"保存对比帧: {comp_path}")


def main():
    """主函数"""
    # 视频路径
    original_video = "/home/jiarui/software/video-subtitle-remover/videos/test_video_with_subtitle.mp4"
    processed_video = "/home/jiarui/software/video-subtitle-remover/videos/test_video_with_subtitle_no_subtitle_timed.mp4"

    # 检查文件是否存在
    if not os.path.exists(original_video):
        logger.error(f"原始视频不存在: {original_video}")
        return

    if not os.path.exists(processed_video):
        logger.error(f"处理后视频不存在: {processed_video}")
        return

    print(f"\n{'='*80}")
    print("字幕去除效果验证")
    print(f"{'='*80}")
    print(f"原始视频: {original_video}")
    print(f"处理后视频: {processed_video}")
    print(f"{'='*80}\n")

    # 分析原始视频
    logger.info("1. 分析原始视频...")
    use_real_gemini = True  # 设置为True使用真实Gemini API，False使用模拟数据

    if use_real_gemini:
        original_analysis = analyze_video_with_gemini(original_video, "simple")
    else:
        logger.info("使用模拟数据进行分析")
        original_analysis = create_mock_analysis_for_debugging(original_video)

    print("原始视频分析结果:")
    print(f"  成功: {original_analysis.get('success', False)}")
    if original_analysis.get('success'):
        print(f"  包含字幕: {original_analysis.get('has_subtitles', False)}")
        print(f"  字幕区域数: {original_analysis.get('regions_count', 0)}")
        for i, region in enumerate(original_analysis.get('regions', [])):
            print(f"    区域{i+1}: ({region['x']}, {region['y']}) {region['width']}x{region['height']} 置信度:{region['confidence']:.2f}")
    else:
        print(f"  错误: {original_analysis.get('error', '未知错误')}")

    # 分析处理后视频
    logger.info("2. 分析处理后视频...")
    if use_real_gemini:
        processed_analysis = analyze_video_with_gemini(processed_video, "simple")
    else:
        processed_analysis = create_mock_analysis_for_debugging(processed_video)

    print("\n处理后视频分析结果:")
    print(f"  成功: {processed_analysis.get('success', False)}")
    if processed_analysis.get('success'):
        print(f"  包含字幕: {processed_analysis.get('has_subtitles', False)}")
        print(f"  字幕区域数: {processed_analysis.get('regions_count', 0)}")
        for i, region in enumerate(processed_analysis.get('regions', [])):
            print(f"    区域{i+1}: ({region['x']}, {region['y']}) {region['width']}x{region['height']} 置信度:{region['confidence']:.2f}")
    else:
        print(f"  错误: {processed_analysis.get('error', '未知错误')}")

    # 对比结果
    print(f"\n{'='*80}")
    print("对比分析")
    print(f"{'='*80}")

    if original_analysis.get('success') and processed_analysis.get('success'):
        orig_has_subs = original_analysis.get('has_subtitles', False)
        proc_has_subs = processed_analysis.get('has_subtitles', False)

        if orig_has_subs and not proc_has_subs:
            print("✅ 字幕去除成功！原视频有字幕，处理后视频无字幕")
        elif orig_has_subs and proc_has_subs:
            orig_count = original_analysis.get('regions_count', 0)
            proc_count = processed_analysis.get('regions_count', 0)

            if proc_count < orig_count:
                print(f"⚠️  部分字幕去除：原视频{orig_count}个区域，处理后{proc_count}个区域")
            else:
                print("❌ 字幕去除失败！处理后视频仍有相同数量的字幕区域")
        elif not orig_has_subs and not proc_has_subs:
            print("ℹ️  两个视频都没有检测到字幕")
        else:
            print("🤔 异常情况：原视频无字幕但处理后有字幕")

    # 提取关键帧进行视觉对比
    logger.info("3. 提取关键帧进行视觉对比...")
    key_frames = [10, 50, 100, 150, 200, 250]  # 提取一些关键帧

    original_frames = extract_frames_for_comparison(original_video, key_frames)
    processed_frames = extract_frames_for_comparison(processed_video, key_frames)

    if original_frames and processed_frames:
        comparison_dir = "frame_comparisons"
        save_comparison_frames(original_frames, processed_frames, comparison_dir)
        print(f"\n📸 关键帧对比图已保存到: {comparison_dir}/")
        print("    可以查看 *_comparison.jpg 文件来直观对比效果")

    # 给出调试建议
    print(f"\n{'='*80}")
    print("调试建议")
    print(f"{'='*80}")

    if not use_real_gemini:
        print("1. 当前使用模拟数据，建议启用真实Gemini API验证")
        print("   将脚本中 use_real_gemini 设置为 True")

    print("2. 检查字幕区域坐标是否正确:")
    if original_analysis.get('success') and original_analysis.get('regions'):
        region = original_analysis['regions'][0]
        print(f"   检测到的区域: x={region['x']}, y={region['y']}, w={region['width']}, h={region['height']}")
        print("   确认这个区域是否覆盖了实际的字幕位置")

    print("3. 检查时间段设置:")
    print("   确认模拟的时间段(0-4s, 6-9s)是否与实际字幕出现时间一致")

    print("4. 查看frame_comparisons目录中的对比图:")
    print("   - *_original.jpg: 原始帧")
    print("   - *_processed.jpg: 处理后帧")
    print("   - *_comparison.jpg: 并排对比图")


if __name__ == "__main__":
    main()