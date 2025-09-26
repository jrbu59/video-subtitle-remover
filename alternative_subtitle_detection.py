#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
替代字幕检测方案 - 当Gemini API不可用时的解决方案
"""

import os
import sys
import cv2
import numpy as np
import logging
from typing import List, Tuple, Dict, Optional
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.api.models.timed_subtitle import TimedSubtitleRegion, TimedSubtitleAnalysis


class AlternativeSubtitleDetector:
    """替代字幕检测器"""

    def __init__(self, video_path: str):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)

        if not self.cap.isOpened():
            raise ValueError(f"无法打开视频: {video_path}")

        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"视频信息: {self.width}x{self.height}, {self.total_frames}帧, {self.fps:.1f}fps")

    def method1_ocr_based_detection(self, sample_frames: int = 20) -> TimedSubtitleAnalysis:
        """方法1: 基于OCR的字幕检测"""
        logger.info("方法1: 使用OCR检测字幕区域")

        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)
        except ImportError:
            logger.error("PaddleOCR未安装，跳过OCR方法")
            return self._create_empty_analysis()

        # 采样帧
        frame_interval = max(1, self.total_frames // sample_frames)
        detected_regions = []

        for i in range(0, min(sample_frames * frame_interval, self.total_frames), frame_interval):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = self.cap.read()

            if not ret:
                continue

            # OCR检测
            result = ocr.ocr(frame, cls=True)

            if result and result[0]:
                for detection in result[0]:
                    # 提取坐标和文本
                    coords = detection[0]
                    text = detection[1][0] if detection[1] else ""
                    confidence = detection[1][1] if detection[1] else 0.0

                    if confidence > 0.5 and len(text.strip()) > 2:  # 过滤低质量检测
                        # 计算边界框
                        x_coords = [coord[0] for coord in coords]
                        y_coords = [coord[1] for coord in coords]

                        x_min, x_max = int(min(x_coords)), int(max(x_coords))
                        y_min, y_max = int(min(y_coords)), int(max(y_coords))

                        # 检查是否在底部字幕区域（底部30%）
                        if y_min > self.height * 0.7:
                            detected_regions.append({
                                'frame_no': i,
                                'x': x_min,
                                'y': y_min,
                                'width': x_max - x_min,
                                'height': y_max - y_min,
                                'text': text,
                                'confidence': confidence
                            })

        return self._analyze_ocr_results(detected_regions)

    def method2_edge_detection(self, sample_frames: int = 30) -> TimedSubtitleAnalysis:
        """方法2: 基于边缘检测的字幕区域识别"""
        logger.info("方法2: 使用边缘检测识别字幕区域")

        frame_interval = max(1, self.total_frames // sample_frames)
        subtitle_regions = []

        for i in range(0, min(sample_frames * frame_interval, self.total_frames), frame_interval):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = self.cap.read()

            if not ret:
                continue

            # 只分析底部30%区域
            bottom_region = frame[int(self.height * 0.7):, :]

            # 转换为灰度图
            gray = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2GRAY)

            # 应用高斯模糊
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # 边缘检测
            edges = cv2.Canny(blurred, 50, 150)

            # 形态学操作连接文本
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 5))
            closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

            # 查找轮廓
            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                # 计算轮廓面积和边界框
                area = cv2.contourArea(contour)
                if area > 1000:  # 过滤小区域
                    x, y, w, h = cv2.boundingRect(contour)

                    # 调整坐标到原图
                    actual_y = y + int(self.height * 0.7)

                    # 检查宽高比（字幕通常比较宽）
                    aspect_ratio = w / h if h > 0 else 0
                    if aspect_ratio > 3 and w > self.width * 0.3:  # 宽度至少30%
                        subtitle_regions.append({
                            'frame_no': i,
                            'x': x,
                            'y': actual_y,
                            'width': w,
                            'height': h,
                            'area': area,
                            'aspect_ratio': aspect_ratio
                        })

        return self._analyze_edge_results(subtitle_regions)

    def method3_template_matching(self) -> TimedSubtitleAnalysis:
        """方法3: 基于模板匹配的检测（需要用户提供字幕样本）"""
        logger.info("方法3: 基于模板匹配检测字幕区域")

        # 这里可以实现基于已知字幕模板的匹配
        # 由于没有预定义模板，返回基于经验的固定区域

        return self._create_default_analysis()

    def method4_interactive_selection(self) -> TimedSubtitleAnalysis:
        """方法4: 交互式区域选择（用户手动标记）"""
        logger.info("方法4: 交互式区域选择")

        # 提取几个代表性帧让用户选择
        sample_frames = [
            int(self.total_frames * 0.1),  # 10%
            int(self.total_frames * 0.3),  # 30%
            int(self.total_frames * 0.7),  # 70%
            int(self.total_frames * 0.9),  # 90%
        ]

        print("\n请查看提取的样本帧，然后输入字幕区域坐标:")

        for i, frame_no in enumerate(sample_frames):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = self.cap.read()

            if ret:
                # 保存样本帧
                sample_path = f"sample_frame_{i+1}_{frame_no}.jpg"
                cv2.imwrite(sample_path, frame)
                print(f"样本帧 {i+1} 已保存: {sample_path} (第{frame_no}帧, {frame_no/self.fps:.1f}s)")

        print(f"\n视频尺寸: {self.width}x{self.height}")
        print("请查看样本帧，然后输入字幕区域坐标:")
        print("格式: x,y,width,height (例如: 100,1500,880,150)")

        # 在实际使用中可以添加交互输入
        # 这里提供默认值
        default_region = self._create_default_analysis()
        print("使用默认字幕区域...")

        return default_region

    def method5_motion_analysis(self, sample_frames: int = 50) -> TimedSubtitleAnalysis:
        """方法5: 基于运动分析的字幕检测"""
        logger.info("方法5: 基于运动分析检测字幕区域")

        frame_interval = max(1, self.total_frames // sample_frames)
        prev_frame = None
        subtitle_changes = []

        for i in range(0, min(sample_frames * frame_interval, self.total_frames), frame_interval):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = self.cap.read()

            if not ret:
                continue

            # 只分析底部区域
            bottom_region = frame[int(self.height * 0.75):, :]
            gray = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2GRAY)

            if prev_frame is not None:
                # 计算帧差
                diff = cv2.absdiff(prev_frame, gray)

                # 应用阈值
                _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

                # 计算变化区域
                change_ratio = np.sum(thresh > 0) / (thresh.shape[0] * thresh.shape[1])

                # 如果变化超过阈值，可能是字幕变化
                if change_ratio > 0.1:  # 10%变化
                    subtitle_changes.append({
                        'frame_no': i,
                        'change_ratio': change_ratio,
                        'prev_frame_no': i - frame_interval
                    })

            prev_frame = gray.copy()

        return self._analyze_motion_results(subtitle_changes)

    def _analyze_ocr_results(self, regions: List[Dict]) -> TimedSubtitleAnalysis:
        """分析OCR结果"""
        if not regions:
            return self._create_empty_analysis()

        # 聚类相似区域
        clustered_regions = self._cluster_regions(regions)

        timed_regions = []
        for cluster in clustered_regions:
            # 为每个聚类创建时间段
            frames = [r['frame_no'] for r in cluster]
            start_frame = min(frames)
            end_frame = max(frames)

            # 计算平均区域
            avg_x = int(np.mean([r['x'] for r in cluster]))
            avg_y = int(np.mean([r['y'] for r in cluster]))
            avg_w = int(np.mean([r['width'] for r in cluster]))
            avg_h = int(np.mean([r['height'] for r in cluster]))
            avg_conf = np.mean([r['confidence'] for r in cluster])

            # 扩展时间范围（假设字幕持续2-3秒）
            duration_frames = int(self.fps * 2.5)
            expanded_start = max(0, start_frame - duration_frames // 2)
            expanded_end = min(self.total_frames - 1, end_frame + duration_frames // 2)

            region = TimedSubtitleRegion(
                start_frame=expanded_start,
                end_frame=expanded_end,
                x=avg_x,
                y=avg_y,
                width=avg_w,
                height=avg_h,
                confidence=avg_conf,
                text_content=f"OCR检测区域 (帧{start_frame}-{end_frame})"
            )
            timed_regions.append(region)

        return TimedSubtitleAnalysis(
            has_subtitles=len(timed_regions) > 0,
            subtitle_type="hard",
            timed_regions=timed_regions,
            total_frames=self.total_frames,
            fps=self.fps
        )

    def _analyze_edge_results(self, regions: List[Dict]) -> TimedSubtitleAnalysis:
        """分析边缘检测结果"""
        if not regions:
            return self._create_empty_analysis()

        # 按时间分组
        time_groups = {}
        for region in regions:
            time_key = region['frame_no'] // int(self.fps * 2)  # 每2秒一组
            if time_key not in time_groups:
                time_groups[time_key] = []
            time_groups[time_key].append(region)

        timed_regions = []
        for time_key, group in time_groups.items():
            if len(group) >= 2:  # 至少要有2个检测点
                frames = [r['frame_no'] for r in group]
                start_frame = min(frames)
                end_frame = max(frames)

                # 计算统一区域
                min_x = min([r['x'] for r in group])
                max_x = max([r['x'] + r['width'] for r in group])
                min_y = min([r['y'] for r in group])
                max_y = max([r['y'] + r['height'] for r in group])

                # 扩展时间范围
                duration_frames = int(self.fps * 3)
                expanded_start = max(0, start_frame - duration_frames // 2)
                expanded_end = min(self.total_frames - 1, end_frame + duration_frames // 2)

                region = TimedSubtitleRegion(
                    start_frame=expanded_start,
                    end_frame=expanded_end,
                    x=min_x,
                    y=min_y,
                    width=max_x - min_x,
                    height=max_y - min_y,
                    confidence=0.7,
                    text_content=f"边缘检测区域 (帧{start_frame}-{end_frame})"
                )
                timed_regions.append(region)

        return TimedSubtitleAnalysis(
            has_subtitles=len(timed_regions) > 0,
            subtitle_type="hard",
            timed_regions=timed_regions,
            total_frames=self.total_frames,
            fps=self.fps
        )

    def _analyze_motion_results(self, changes: List[Dict]) -> TimedSubtitleAnalysis:
        """分析运动检测结果"""
        if not changes:
            return self._create_empty_analysis()

        # 检测字幕变化点
        subtitle_segments = []
        current_start = None

        for change in changes:
            if current_start is None:
                current_start = change['frame_no']

            # 检查是否是连续的字幕段
            if len(subtitle_segments) > 0:
                last_end = subtitle_segments[-1]['end']
                if change['frame_no'] - last_end > self.fps * 5:  # 间隔超过5秒
                    # 结束当前段，开始新段
                    if current_start is not None:
                        subtitle_segments.append({
                            'start': current_start,
                            'end': change['frame_no'],
                            'changes': 1
                        })
                        current_start = change['frame_no']

        # 处理最后一段
        if current_start is not None and changes:
            subtitle_segments.append({
                'start': current_start,
                'end': changes[-1]['frame_no'],
                'changes': len(changes)
            })

        # 创建时间段区域
        timed_regions = []
        for segment in subtitle_segments:
            if segment['changes'] >= 2:  # 至少2次变化
                region = TimedSubtitleRegion(
                    start_frame=segment['start'],
                    end_frame=segment['end'],
                    x=int(self.width * 0.1),
                    y=int(self.height * 0.8),
                    width=int(self.width * 0.8),
                    height=int(self.height * 0.15),
                    confidence=0.6,
                    text_content=f"运动检测区域 (帧{segment['start']}-{segment['end']})"
                )
                timed_regions.append(region)

        return TimedSubtitleAnalysis(
            has_subtitles=len(timed_regions) > 0,
            subtitle_type="hard",
            timed_regions=timed_regions,
            total_frames=self.total_frames,
            fps=self.fps
        )

    def _cluster_regions(self, regions: List[Dict], distance_threshold: int = 50) -> List[List[Dict]]:
        """聚类相似的字幕区域"""
        if not regions:
            return []

        clusters = []
        used = set()

        for i, region1 in enumerate(regions):
            if i in used:
                continue

            cluster = [region1]
            used.add(i)

            for j, region2 in enumerate(regions):
                if j in used:
                    continue

                # 计算区域相似度
                x_diff = abs(region1['x'] - region2['x'])
                y_diff = abs(region1['y'] - region2['y'])
                w_diff = abs(region1['width'] - region2['width'])
                h_diff = abs(region1['height'] - region2['height'])

                if (x_diff < distance_threshold and
                    y_diff < distance_threshold and
                    w_diff < distance_threshold and
                    h_diff < distance_threshold):
                    cluster.append(region2)
                    used.add(j)

            if len(cluster) > 0:
                clusters.append(cluster)

        return clusters

    def _create_default_analysis(self) -> TimedSubtitleAnalysis:
        """创建默认的字幕分析（基于常见字幕位置）"""
        # 创建两个时间段的默认字幕区域
        timed_regions = []

        # 第一段 (0-40%视频时长)
        if self.total_frames > 60:
            end_frame = min(int(self.total_frames * 0.4), self.total_frames - 1)
            region1 = TimedSubtitleRegion(
                start_frame=0,
                end_frame=end_frame,
                x=int(self.width * 0.05),
                y=int(self.height * 0.8),
                width=int(self.width * 0.9),
                height=int(self.height * 0.15),
                confidence=0.8,
                text_content="默认字幕区域1 (底部)"
            )
            timed_regions.append(region1)

        # 第二段 (60%-90%视频时长)
        if self.total_frames > 120:
            start_frame = int(self.total_frames * 0.6)
            end_frame = min(int(self.total_frames * 0.9), self.total_frames - 1)
            if start_frame < end_frame:
                region2 = TimedSubtitleRegion(
                    start_frame=start_frame,
                    end_frame=end_frame,
                    x=int(self.width * 0.05),
                    y=int(self.height * 0.8),
                    width=int(self.width * 0.9),
                    height=int(self.height * 0.15),
                    confidence=0.8,
                    text_content="默认字幕区域2 (底部)"
                )
                timed_regions.append(region2)

        return TimedSubtitleAnalysis(
            has_subtitles=len(timed_regions) > 0,
            subtitle_type="hard",
            timed_regions=timed_regions,
            total_frames=self.total_frames,
            fps=self.fps
        )

    def _create_empty_analysis(self) -> TimedSubtitleAnalysis:
        """创建空的分析结果"""
        return TimedSubtitleAnalysis(
            has_subtitles=False,
            subtitle_type="hard",
            timed_regions=[],
            total_frames=self.total_frames,
            fps=self.fps
        )

    def run_all_methods(self) -> Dict[str, TimedSubtitleAnalysis]:
        """运行所有检测方法"""
        results = {}

        print(f"\n{'='*60}")
        print("运行所有字幕检测方法")
        print(f"{'='*60}")

        try:
            results['ocr'] = self.method1_ocr_based_detection()
            print("✅ OCR检测完成")
        except Exception as e:
            logger.error(f"OCR检测失败: {e}")
            results['ocr'] = self._create_empty_analysis()

        try:
            results['edge'] = self.method2_edge_detection()
            print("✅ 边缘检测完成")
        except Exception as e:
            logger.error(f"边缘检测失败: {e}")
            results['edge'] = self._create_empty_analysis()

        try:
            results['motion'] = self.method5_motion_analysis()
            print("✅ 运动分析完成")
        except Exception as e:
            logger.error(f"运动分析失败: {e}")
            results['motion'] = self._create_empty_analysis()

        try:
            results['default'] = self._create_default_analysis()
            print("✅ 默认区域生成完成")
        except Exception as e:
            logger.error(f"默认区域生成失败: {e}")
            results['default'] = self._create_empty_analysis()

        return results

    def __del__(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()


def main():
    """测试替代检测方法"""
    video_path = "/home/jiarui/software/video-subtitle-remover/videos/test_video_with_subtitle.mp4"

    if not os.path.exists(video_path):
        print(f"测试视频不存在: {video_path}")
        return

    detector = AlternativeSubtitleDetector(video_path)
    results = detector.run_all_methods()

    print(f"\n{'='*60}")
    print("检测结果汇总")
    print(f"{'='*60}")

    for method, analysis in results.items():
        print(f"\n📋 {method.upper()} 方法:")
        print(f"   检测到字幕: {analysis.has_subtitles}")
        print(f"   时间段数量: {len(analysis.timed_regions)}")

        for i, region in enumerate(analysis.timed_regions):
            start_time = region.start_frame / analysis.fps
            end_time = region.end_frame / analysis.fps
            print(f"   区域{i+1}: {start_time:.1f}s-{end_time:.1f}s, "
                  f"位置({region.x},{region.y}) 大小{region.width}x{region.height}")

    # 推荐最佳方法
    best_method = None
    max_regions = 0

    for method, analysis in results.items():
        if analysis.has_subtitles and len(analysis.timed_regions) > max_regions:
            max_regions = len(analysis.timed_regions)
            best_method = method

    if best_method:
        print(f"\n🏆 推荐使用: {best_method.upper()} 方法 (检测到{max_regions}个时间段)")
    else:
        print(f"\n⚠️  所有方法都未检测到字幕，建议使用默认方法")


if __name__ == "__main__":
    main()