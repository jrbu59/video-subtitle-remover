#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
时间段字幕区域数据模型
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class TimedSubtitleRegion:
    """带时间戳的字幕区域"""
    start_frame: int      # 开始帧
    end_frame: int        # 结束帧
    x: int               # 区域左上角x坐标
    y: int               # 区域左上角y坐标
    width: int           # 区域宽度
    height: int          # 区域高度
    confidence: float    # 置信度(0-1)
    text_content: str = ""  # 识别的文本内容（如果能识别）

    def to_dict(self):
        """转换为字典"""
        return {
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": self.confidence,
            "text_content": self.text_content
        }

    def get_bbox(self) -> Tuple[int, int, int, int]:
        """获取边界框坐标 (xmin, xmax, ymin, ymax)"""
        return (self.x, self.x + self.width, self.y, self.y + self.height)

    def contains_frame(self, frame_no: int) -> bool:
        """检查指定帧是否在此时间段内"""
        return self.start_frame <= frame_no <= self.end_frame


@dataclass
class TimedSubtitleAnalysis:
    """带时间信息的字幕分析结果"""
    has_subtitles: bool
    subtitle_type: str  # 'hard' or 'soft'
    timed_regions: List[TimedSubtitleRegion]
    total_frames: int
    fps: float

    def get_regions_for_frame(self, frame_no: int) -> List[TimedSubtitleRegion]:
        """获取指定帧的所有字幕区域"""
        return [region for region in self.timed_regions if region.contains_frame(frame_no)]

    def get_unique_regions(self) -> List[Tuple[int, int, int, int]]:
        """获取所有唯一的区域坐标"""
        unique_regions = set()
        for region in self.timed_regions:
            unique_regions.add(region.get_bbox())
        return list(unique_regions)

    def merge_overlapping_regions(self, time_threshold: int = 10):
        """合并时间上重叠的相似区域

        Args:
            time_threshold: 时间间隔阈值（帧数）
        """
        if not self.timed_regions:
            return

        # 按开始帧排序
        sorted_regions = sorted(self.timed_regions, key=lambda r: r.start_frame)
        merged = []

        for region in sorted_regions:
            if not merged:
                merged.append(region)
                continue

            # 检查是否可以与最后一个区域合并
            last_region = merged[-1]

            # 检查空间位置是否相似（允许小偏差）
            x_diff = abs(region.x - last_region.x)
            y_diff = abs(region.y - last_region.y)
            w_diff = abs(region.width - last_region.width)
            h_diff = abs(region.height - last_region.height)

            # 检查时间是否接近
            time_gap = region.start_frame - last_region.end_frame

            if (x_diff <= 20 and y_diff <= 20 and
                w_diff <= 30 and h_diff <= 20 and
                time_gap <= time_threshold):
                # 合并区域
                last_region.end_frame = region.end_frame
                # 更新置信度为平均值
                last_region.confidence = (last_region.confidence + region.confidence) / 2
                # 合并文本内容
                if region.text_content and region.text_content not in last_region.text_content:
                    last_region.text_content += " | " + region.text_content
            else:
                merged.append(region)

        self.timed_regions = merged