#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能字幕检测 - 集成多种检测方法的完整解决方案
"""

import os
import sys
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.api.models.timed_subtitle import TimedSubtitleAnalysis
from backend.api.gemini.token_manager import TokenManager
from backend.api.gemini.gemini_timed_client import GeminiTimedClient
from alternative_subtitle_detection import AlternativeSubtitleDetector
from subtitle_remover_timed import TimedSubtitleRemover, TimedSubtitleAnalysisHelper


class SmartSubtitleDetector:
    """智能字幕检测器 - 自动选择最佳检测方法"""

    def __init__(self, video_path: str, gemini_token_endpoint: Optional[str] = None):
        self.video_path = video_path
        self.gemini_token_endpoint = gemini_token_endpoint or "http://api-ladder.ymt.io:8088/rpc/vertexai/accesstoken"

    def detect_subtitles(self, prefer_gemini: bool = True) -> TimedSubtitleAnalysis:
        """
        智能检测字幕区域

        Args:
            prefer_gemini: 是否优先尝试Gemini API

        Returns:
            TimedSubtitleAnalysis: 字幕分析结果
        """
        logger.info("🔍 开始智能字幕检测...")

        # 方法1: 尝试Gemini API (如果启用)
        if prefer_gemini:
            gemini_result = self._try_gemini_detection()
            if gemini_result and gemini_result.has_subtitles:
                logger.info("✅ Gemini检测成功")
                return gemini_result
            else:
                logger.warning("⚠️ Gemini检测失败或无字幕，尝试备用方法")

        # 方法2: 使用替代检测方法
        logger.info("🔄 使用备用检测方法...")
        alternative_detector = AlternativeSubtitleDetector(self.video_path)
        results = alternative_detector.run_all_methods()

        # 选择最佳结果
        best_result = self._select_best_result(results)

        if best_result and best_result.has_subtitles:
            logger.info("✅ 备用方法检测成功")
            return best_result
        else:
            logger.warning("⚠️ 所有方法都未检测到字幕，使用默认区域")
            return self._create_fallback_result()

    def _try_gemini_detection(self) -> Optional[TimedSubtitleAnalysis]:
        """尝试Gemini检测"""
        try:
            token_manager = TokenManager(self.gemini_token_endpoint)
            gemini_client = GeminiTimedClient(token_manager)

            analysis = gemini_client.analyze_subtitle_with_time(
                self.video_path,
                sample_frames=20
            )

            return analysis

        except Exception as e:
            logger.error(f"Gemini检测异常: {e}")
            return None

    def _select_best_result(self, results: dict) -> Optional[TimedSubtitleAnalysis]:
        """选择最佳检测结果"""

        # 优先级排序: OCR > 边缘检测 > 运动分析 > 默认
        priority_order = ['ocr', 'edge', 'motion', 'default']

        for method in priority_order:
            if method in results:
                analysis = results[method]
                if analysis.has_subtitles and len(analysis.timed_regions) > 0:
                    logger.info(f"选择 {method.upper()} 方法的结果")
                    return analysis

        return None

    def _create_fallback_result(self) -> TimedSubtitleAnalysis:
        """创建回退结果"""
        alternative_detector = AlternativeSubtitleDetector(self.video_path)
        return alternative_detector._create_default_analysis()


def test_smart_detection_and_removal():
    """测试智能检测和字幕去除"""

    print(f"\n{'='*80}")
    print("智能字幕检测和去除测试")
    print(f"{'='*80}")

    video_path = "/home/jiarui/software/video-subtitle-remover/videos/test_video_with_subtitle.mp4"

    if not os.path.exists(video_path):
        print(f"❌ 测试视频不存在: {video_path}")
        return

    # 步骤1: 智能检测
    detector = SmartSubtitleDetector(video_path)

    print("1. 尝试Gemini检测...")
    analysis = detector.detect_subtitles(prefer_gemini=True)

    print("2. 检测结果:")
    TimedSubtitleAnalysisHelper.print_analysis_summary(analysis)

    if not analysis.has_subtitles:
        print("❌ 未检测到字幕，退出")
        return

    # 步骤2: 字幕去除
    print("3. 开始字幕去除...")
    output_path = "/home/jiarui/software/video-subtitle-remover/videos/test_video_smart_detection.mp4"

    try:
        remover = TimedSubtitleRemover(
            video_path=video_path,
            sub_area=None,
            timed_regions=analysis.timed_regions
        )

        remover.video_out_name = output_path
        logger.info(f"输出文件: {output_path}")

        remover.run()

        print(f"✅ 字幕去除完成！")
        print(f"📁 输出视频: {output_path}")

        # 统计信息
        total_processed_frames = sum(
            (region.end_frame - region.start_frame + 1)
            for region in analysis.timed_regions
        )

        print(f"\n📊 处理统计:")
        print(f"   检测方法: 智能检测 (Gemini + OCR备用)")
        print(f"   时间段数: {len(analysis.timed_regions)}")
        print(f"   处理帧数: {total_processed_frames}/{analysis.total_frames}")
        print(f"   处理比例: {total_processed_frames/analysis.total_frames*100:.1f}%")

    except Exception as e:
        logger.error(f"❌ 字幕去除失败: {e}")


def main():
    """主函数"""
    test_smart_detection_and_removal()


if __name__ == "__main__":
    main()