#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复字幕区域坐标问题
"""

import os
import sys
import cv2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.api.models.timed_subtitle import TimedSubtitleRegion, TimedSubtitleAnalysis
from subtitle_remover_timed import TimedSubtitleRemover, TimedSubtitleAnalysisHelper


def get_video_info(video_path: str):
    """获取视频详细信息"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    }
    cap.release()
    return info


def create_corrected_subtitle_analysis(video_path: str) -> TimedSubtitleAnalysis:
    """创建修正后的字幕分析结果"""

    video_info = get_video_info(video_path)
    if not video_info:
        raise ValueError("无法获取视频信息")

    logger.info(f"视频尺寸: {video_info['width']}x{video_info['height']}")
    logger.info(f"视频信息: {video_info['total_frames']}帧, {video_info['fps']:.2f}fps")

    # 创建正确的字幕区域坐标
    width = video_info["width"]
    height = video_info["height"]
    total_frames = video_info["total_frames"]
    fps = video_info["fps"]

    # 字幕通常在底部，使用合理的坐标
    subtitle_y = int(height * 0.8)  # 从底部20%开始
    subtitle_height = int(height * 0.15)  # 高度15%
    subtitle_x = int(width * 0.05)  # 左边距5%
    subtitle_width = int(width * 0.9)  # 宽度90%

    logger.info(f"修正后的字幕区域: x={subtitle_x}, y={subtitle_y}, w={subtitle_width}, h={subtitle_height}")

    timed_regions = []

    # 第一段字幕 (0-40%视频时长)
    if total_frames > 30:
        end_frame = min(int(total_frames * 0.4), total_frames - 1)
        region1 = TimedSubtitleRegion(
            start_frame=0,
            end_frame=end_frame,
            x=subtitle_x,
            y=subtitle_y,
            width=subtitle_width,
            height=subtitle_height,
            confidence=0.95,
            text_content="修正后的字幕区域1"
        )
        timed_regions.append(region1)
        logger.info(f"区域1: 帧 {region1.start_frame}-{region1.end_frame} (0-{end_frame/fps:.1f}s)")

    # 第二段字幕 (60%-90%视频时长)
    if total_frames > 60:
        start_frame = int(total_frames * 0.6)
        end_frame = min(int(total_frames * 0.9), total_frames - 1)
        if start_frame < end_frame:
            region2 = TimedSubtitleRegion(
                start_frame=start_frame,
                end_frame=end_frame,
                x=subtitle_x,
                y=subtitle_y,
                width=subtitle_width,
                height=subtitle_height,
                confidence=0.92,
                text_content="修正后的字幕区域2"
            )
            timed_regions.append(region2)
            logger.info(f"区域2: 帧 {region2.start_frame}-{region2.end_frame} ({start_frame/fps:.1f}s-{end_frame/fps:.1f}s)")

    # 创建分析结果
    analysis = TimedSubtitleAnalysis(
        has_subtitles=len(timed_regions) > 0,
        subtitle_type="hard",
        timed_regions=timed_regions,
        total_frames=total_frames,
        fps=fps
    )

    return analysis


def create_debug_frames_with_regions(video_path: str, analysis: TimedSubtitleAnalysis, output_dir: str):
    """创建带字幕区域标记的调试帧"""
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return

    # 提取一些关键帧
    key_frames = [10, 50, 100, 150, 200, 250]

    for frame_no in key_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ret, frame = cap.read()

        if ret:
            # 获取当前帧的字幕区域
            active_regions = analysis.get_regions_for_frame(frame_no)

            # 在帧上绘制区域
            for region in active_regions:
                x, y, w, h = region.x, region.y, region.width, region.height

                # 绘制矩形框
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)

                # 添加标签
                label = f"Subtitle Region ({w}x{h})"
                cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            # 保存标记后的帧
            time_sec = frame_no / analysis.fps
            should_process = len(active_regions) > 0
            status = "PROCESS" if should_process else "SKIP"

            output_path = os.path.join(output_dir, f"corrected_frame_{frame_no:04d}_{status}_{time_sec:.1f}s.jpg")
            cv2.imwrite(output_path, frame)
            logger.info(f"保存调试帧: {output_path}")

    cap.release()


def test_corrected_subtitle_removal():
    """测试修正后的字幕去除"""

    print(f"\n{'='*80}")
    print("修正坐标后的字幕去除测试")
    print(f"{'='*80}\n")

    # 视频路径
    input_video = "/home/jiarui/software/video-subtitle-remover/videos/test_video_with_subtitle.mp4"

    # 获取视频信息
    video_info = get_video_info(input_video)
    print(f"视频信息: {video_info['width']}x{video_info['height']}, {video_info['total_frames']}帧")

    # 创建修正后的分析结果
    logger.info("创建修正后的字幕区域...")
    corrected_analysis = create_corrected_subtitle_analysis(input_video)

    # 打印分析结果
    TimedSubtitleAnalysisHelper.print_analysis_summary(corrected_analysis)

    # 创建调试帧
    debug_dir = "corrected_regions_debug"
    create_debug_frames_with_regions(input_video, corrected_analysis, debug_dir)
    print(f"\n📸 修正后的区域调试图已保存到: {debug_dir}/")
    print("    请检查绿色框是否正确覆盖字幕位置\n")

    # 自动继续处理（去掉交互）
    print("自动继续处理视频...")
    if True:
        logger.info("开始使用修正后的坐标处理视频...")

        # 准备输出路径
        output_path = "/home/jiarui/software/video-subtitle-remover/videos/test_video_corrected_regions.mp4"

        # 创建字幕去除器
        remover = TimedSubtitleRemover(
            video_path=input_video,
            sub_area=None,
            timed_regions=corrected_analysis.timed_regions
        )

        # 设置输出路径并运行
        remover.video_out_name = output_path
        logger.info(f"输出文件: {output_path}")

        try:
            remover.run()
            logger.info(f"✅ 字幕去除完成！输出文件: {output_path}")

            # 创建处理后的对比帧
            comparison_dir = "corrected_comparison"
            os.makedirs(comparison_dir, exist_ok=True)

            # 提取对比帧
            cap_orig = cv2.VideoCapture(input_video)
            cap_proc = cv2.VideoCapture(output_path)

            key_frames = [10, 50, 100, 200, 250]
            for frame_no in key_frames:
                # 原始帧
                cap_orig.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
                ret1, orig_frame = cap_orig.read()

                # 处理后帧
                cap_proc.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
                ret2, proc_frame = cap_proc.read()

                if ret1 and ret2:
                    # 创建对比图
                    comparison = cv2.hconcat([orig_frame, proc_frame])

                    # 添加标签
                    cv2.putText(comparison, "ORIGINAL", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)
                    cv2.putText(comparison, "PROCESSED", (orig_frame.shape[1] + 50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)

                    comp_path = os.path.join(comparison_dir, f"corrected_comparison_frame_{frame_no:04d}.jpg")
                    cv2.imwrite(comp_path, comparison)

            cap_orig.release()
            cap_proc.release()

            print(f"\n✅ 处理完成！请检查以下文件:")
            print(f"   输出视频: {output_path}")
            print(f"   对比图片: {comparison_dir}/")

        except Exception as e:
            logger.error(f"处理失败: {e}")
    else:
        print("取消处理，请手动调整区域坐标")


if __name__ == "__main__":
    test_corrected_subtitle_removal()