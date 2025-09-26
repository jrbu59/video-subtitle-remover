#!/usr/bin/env python3
"""
增强版Gemini Client - 支持时间段字幕检测
"""

import os
import json
import base64
import requests
import logging
import cv2
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from backend.api.models.timed_subtitle import TimedSubtitleRegion, TimedSubtitleAnalysis
from backend.api.gemini.token_manager import TokenManager

logger = logging.getLogger(__name__)


class GeminiTimedClient:
    """增强版Gemini API客户端 - 支持时间段检测"""

    def __init__(self, token_manager: TokenManager, model_name: str = "gemini-1.5-pro-001"):
        self.token_manager = token_manager
        self.model_name = model_name
        self.api_endpoint = f"https://us-central1-aiplatform.googleapis.com/v1/projects/gemini-vertex-ai/locations/us-central1/publishers/google/models/{model_name}:streamGenerateContent"
        self.logger = logging.getLogger(__name__)

    def analyze_subtitle_with_time(self, video_path: str, sample_frames: int = 30) -> Optional[TimedSubtitleAnalysis]:
        """
        使用Gemini分析视频中的字幕，包含时间信息

        Args:
            video_path: 视频文件路径
            sample_frames: 采样帧数（增加到30帧以获得更好的时间覆盖）

        Returns:
            TimedSubtitleAnalysis: 带时间信息的字幕分析结果
        """
        try:
            self.logger.info(f"开始使用Gemini分析视频字幕（时间段模式）: {video_path}")

            # 提取视频关键帧及时间信息
            frames_with_time = self._extract_keyframes_with_time(video_path, sample_frames)
            if not frames_with_time:
                self.logger.error("无法提取视频帧")
                return None

            # 获取视频信息
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()

            # 构造增强提示词
            prompt = self._build_timed_subtitle_detection_prompt(frames_with_time, fps)

            # 发送请求到Gemini API
            response = self._send_gemini_request(prompt, [f[1] for f in frames_with_time])

            if response:
                # 解析响应
                return self._parse_timed_response(response, total_frames, fps)
            else:
                self.logger.error("Gemini API请求失败")
                return None

        except Exception as e:
            self.logger.error(f"Gemini时间段字幕分析异常: {e}")
            return None

    def _extract_keyframes_with_time(self, video_path: str, sample_frames: int) -> List[Tuple[int, np.ndarray]]:
        """提取视频关键帧及其帧号"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.logger.error("无法打开视频文件")
                return []

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            # 计算采样间隔，确保覆盖整个视频
            interval = max(1, total_frames // sample_frames)

            frames_with_time = []
            frame_indices = [i * interval for i in range(min(sample_frames, total_frames // interval))]

            for frame_no in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
                ret, frame = cap.read()
                if ret:
                    # 调整帧大小以减少数据量
                    height, width = frame.shape[:2]
                    if width > 1280:
                        ratio = 1280 / width
                        new_width = 1280
                        new_height = int(height * ratio)
                        frame = cv2.resize(frame, (new_width, new_height))
                    frames_with_time.append((frame_no, frame))

            cap.release()
            self.logger.info(f"成功提取 {len(frames_with_time)} 帧用于时间段分析")
            return frames_with_time

        except Exception as e:
            self.logger.error(f"提取视频帧异常: {e}")
            return []

    def _build_timed_subtitle_detection_prompt(self, frames_with_time: List[Tuple[int, np.ndarray]], fps: float) -> str:
        """构建时间段字幕检测提示词"""
        frame_info = []
        for i, (frame_no, _) in enumerate(frames_with_time):
            time_sec = frame_no / fps
            frame_info.append(f"Frame {i+1}: 帧号={frame_no}, 时间={time_sec:.2f}秒")

        frame_info_str = "\n".join(frame_info)

        return f"""
        请分析以下视频帧序列，检测其中的硬字幕（hard subtitle）信息，并标注每个字幕区域出现的时间段。

        视频帧信息：
        {frame_info_str}

        请按照以下格式返回JSON响应：
        {{
            "has_subtitles": boolean,           // 是否包含字幕
            "subtitle_type": "hard",            // 字幕类型（固定为"hard"）
            "timed_regions": [                  // 带时间信息的字幕区域列表
                {{
                    "frame_index": int,          // 在提供的帧序列中的索引(0-based)
                    "frame_no": int,             // 实际的视频帧号
                    "time_sec": float,           // 时间（秒）
                    "x": int,                    // 区域左上角x坐标
                    "y": int,                    // 区域左上角y坐标
                    "width": int,                // 区域宽度
                    "height": int,               // 区域高度
                    "confidence": float,         // 置信度(0-1)
                    "text_content": string,      // 识别的文本内容（如果能识别）
                    "is_subtitle": boolean       // 是否确定是字幕（而不是其他文字）
                }}
            ]
        }}

        要求：
        1. 仔细分析每一帧，识别字幕区域
        2. 记录字幕出现和消失的时间
        3. 区分字幕和其他屏幕文字（如UI元素、标题等）
        4. 字幕通常出现在底部或顶部，有固定位置
        5. 如果同一位置的字幕内容变化，记录为不同的区域
        6. 置信度应反映你对检测结果的确定程度
        7. 只返回is_subtitle为true的区域
        """

    def _encode_frame_to_base64(self, frame: np.ndarray) -> str:
        """将视频帧编码为base64"""
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buffer).decode('utf-8')

    def _send_gemini_request(self, prompt: str, frames: List[np.ndarray]) -> Optional[Dict[Any, Any]]:
        """发送请求到Gemini API"""
        try:
            # 获取访问令牌
            access_token = self.token_manager.get_access_token()
            if not access_token:
                self.logger.error("无法获取访问令牌")
                return None

            # 编码视频帧
            encoded_frames = [self._encode_frame_to_base64(frame) for frame in frames]

            # 构造请求体
            contents = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ]
            }

            # 添加视频帧
            for i, frame_data in enumerate(encoded_frames):
                contents["contents"][0]["parts"].append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": frame_data
                    }
                })

            # 发送请求
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            self.logger.info("正在发送请求到Gemini API（时间段模式）...")
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=contents,
                timeout=90  # 增加超时时间
            )

            if response.status_code == 200:
                self.logger.info("Gemini API请求成功")
                return response.json()
            else:
                self.logger.error(f"Gemini API请求失败: HTTP {response.status_code}, {response.text}")
                return None

        except Exception as e:
            self.logger.error(f"发送Gemini请求异常: {e}")
            return None

    def _parse_timed_response(self, response: Dict[Any, Any], total_frames: int, fps: float) -> TimedSubtitleAnalysis:
        """解析带时间信息的Gemini响应"""
        try:
            # 提取响应内容
            if isinstance(response, list) and len(response) > 0:
                candidates = response[0].get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        text_content = parts[0].get('text', '{}')
                        # 解析JSON
                        result = json.loads(text_content)

                        # 转换为TimedSubtitleRegion对象
                        timed_regions = []
                        for region_data in result.get('timed_regions', []):
                            if region_data.get('is_subtitle', True):  # 只处理确认是字幕的区域
                                frame_no = region_data['frame_no']

                                # 估算时间范围（假设字幕持续2-3秒）
                                duration_frames = int(fps * 2.5)  # 2.5秒
                                start_frame = max(0, frame_no - duration_frames // 2)
                                end_frame = min(total_frames - 1, frame_no + duration_frames // 2)

                                region = TimedSubtitleRegion(
                                    start_frame=start_frame,
                                    end_frame=end_frame,
                                    x=region_data['x'],
                                    y=region_data['y'],
                                    width=region_data['width'],
                                    height=region_data['height'],
                                    confidence=region_data['confidence'],
                                    text_content=region_data.get('text_content', '')
                                )
                                timed_regions.append(region)

                        analysis = TimedSubtitleAnalysis(
                            has_subtitles=result['has_subtitles'],
                            subtitle_type=result['subtitle_type'],
                            timed_regions=timed_regions,
                            total_frames=total_frames,
                            fps=fps
                        )

                        # 合并重叠的区域
                        analysis.merge_overlapping_regions()

                        self.logger.info(f"成功解析Gemini响应: {analysis.has_subtitles}, 时间段数: {len(timed_regions)}")
                        return analysis

            # 默认返回无字幕结果
            self.logger.warning("无法解析Gemini响应，返回默认结果")
            return TimedSubtitleAnalysis(
                has_subtitles=False,
                subtitle_type="hard",
                timed_regions=[],
                total_frames=total_frames,
                fps=fps
            )

        except Exception as e:
            self.logger.error(f"解析Gemini响应异常: {e}")
            # 返回默认结果
            return TimedSubtitleAnalysis(
                has_subtitles=False,
                subtitle_type="hard",
                timed_regions=[],
                total_frames=total_frames,
                fps=fps
            )