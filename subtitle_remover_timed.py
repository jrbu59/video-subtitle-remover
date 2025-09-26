#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版字幕去除器 - 支持时间段精确控制
"""

import os
import sys
import cv2
import logging
from typing import List, Dict, Optional, Tuple
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import SubtitleRemover, SubtitleDetect
from backend.api.models.timed_subtitle import TimedSubtitleRegion, TimedSubtitleAnalysis

logger = logging.getLogger(__name__)


class TimedSubtitleDetect(SubtitleDetect):
    """支持时间段的字幕检测器"""

    def __init__(self, video_path, timed_regions: List[TimedSubtitleRegion]):
        """
        初始化时间段字幕检测器

        Args:
            video_path: 视频路径
            timed_regions: 带时间信息的字幕区域列表
        """
        super().__init__(video_path, sub_area=None)
        self.timed_regions = timed_regions
        logger.info(f"初始化时间段字幕检测器，共 {len(self.timed_regions)} 个时间段")

    def find_subtitle_frame_no(self, sub_remover=None):
        """
        重写字幕检测方法，支持时间段模式
        """
        # 时间段模式：直接生成帧-区域映射
        logger.info("使用时间段模式生成字幕帧映射")
        subtitle_frame_no_box_dict = {}

        # 遍历所有时间段
        for timed_region in self.timed_regions:
            bbox = timed_region.get_bbox()
            xmin, xmax, ymin, ymax = bbox

            # 为时间段内的每一帧添加字幕区域
            for frame_no in range(timed_region.start_frame, timed_region.end_frame + 1):
                if frame_no not in subtitle_frame_no_box_dict:
                    subtitle_frame_no_box_dict[frame_no] = []
                subtitle_frame_no_box_dict[frame_no].append((xmin, xmax, ymin, ymax))

        logger.info(f"时间段模式：共 {len(subtitle_frame_no_box_dict)} 帧需要处理")
        return subtitle_frame_no_box_dict


class TimedSubtitleRemover(SubtitleRemover):
    """支持时间段的字幕去除器"""

    def __init__(self, video_path, sub_area=None, timed_regions: Optional[List[TimedSubtitleRegion]] = None):
        """
        初始化时间段字幕去除器

        Args:
            video_path: 视频文件路径
            sub_area: 传统的静态字幕区域（向后兼容）
            timed_regions: 带时间信息的字幕区域列表
        """
        # 先初始化父类
        super().__init__(video_path, sub_area)

        # 如果提供了时间段信息，替换检测器
        self.timed_regions = timed_regions or []
        if len(self.timed_regions) > 0:
            logger.info(f"使用时间段模式，共 {len(self.timed_regions)} 个时间段")
            # 替换字幕检测器为时间段版本
            self.sub_detector = TimedSubtitleDetect(video_path, self.timed_regions)


class TimedSubtitleAnalysisHelper:
    """时间段字幕分析辅助类"""

    @staticmethod
    def print_analysis_summary(timed_analysis: TimedSubtitleAnalysis):
        """打印分析摘要"""
        if not timed_analysis:
            print("无分析结果")
            return

        print(f"\n{'='*60}")
        print("字幕分析结果摘要")
        print(f"{'='*60}")
        print(f"是否包含字幕: {timed_analysis.has_subtitles}")
        print(f"字幕类型: {timed_analysis.subtitle_type}")
        print(f"视频总帧数: {timed_analysis.total_frames}")
        print(f"视频帧率: {timed_analysis.fps:.2f} fps")
        print(f"检测到的时间段数: {len(timed_analysis.timed_regions)}")

        if timed_analysis.timed_regions:
            print(f"\n时间段详情:")
            for i, region in enumerate(timed_analysis.timed_regions[:5]):  # 只显示前5个
                start_time = region.start_frame / timed_analysis.fps
                end_time = region.end_frame / timed_analysis.fps
                print(f"  {i+1}. 时间: {start_time:.2f}s - {end_time:.2f}s")
                print(f"     位置: ({region.x}, {region.y}) 大小: {region.width}x{region.height}")
                print(f"     置信度: {region.confidence:.2f}")
                if region.text_content:
                    print(f"     文本: {region.text_content[:50]}...")

            if len(timed_analysis.timed_regions) > 5:
                print(f"  ... 还有 {len(timed_analysis.timed_regions) - 5} 个时间段")

        print(f"{'='*60}\n")