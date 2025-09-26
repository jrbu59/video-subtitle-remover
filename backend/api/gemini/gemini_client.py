#!/usr/bin/env python3
"""
Gemini Client for subtitle detection
基于Google Vertex AI Gemini模型的字幕检测客户端
"""

import os
import json
import base64
import requests
import logging
import cv2
import numpy as np
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from .token_manager import TokenManager

logger = logging.getLogger(__name__)

@dataclass
class SubtitleRegion:
    """字幕区域信息"""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    text_content: str

@dataclass
class SubtitleAnalysis:
    """字幕分析结果"""
    has_subtitles: bool
    subtitle_type: str  # 'hard' or 'soft'
    dominant_position: str  # 'top', 'bottom', 'middle'
    regions: List[SubtitleRegion]

class GeminiClient:
    """Gemini API客户端"""

    def __init__(self, token_manager: TokenManager, model_name: str = "gemini-1.5-pro-001"):
        self.token_manager = token_manager
        self.model_name = model_name
        self.api_endpoint = f"https://us-central1-aiplatform.googleapis.com/v1/projects/gemini-vertex-ai/locations/us-central1/publishers/google/models/{model_name}:streamGenerateContent"
        self.logger = logging.getLogger(__name__)

    def analyze_subtitle_with_gemini(self, video_path: str, sample_frames: int = 8) -> Optional[SubtitleAnalysis]:
        """
        使用Gemini分析视频中的字幕

        Args:
            video_path: 视频文件路径
            sample_frames: 采样帧数

        Returns:
            SubtitleAnalysis: 字幕分析结果
        """
        try:
            self.logger.info(f"开始使用Gemini分析视频字幕: {video_path}")

            # 提取视频关键帧
            frames = self._extract_keyframes(video_path, sample_frames)
            if not frames:
                self.logger.error("无法提取视频帧")
                return None

            # 构造提示词
            prompt = self._build_subtitle_detection_prompt()

            # 发送请求到Gemini API
            response = self._send_gemini_request(prompt, frames)

            if response:
                # 解析响应
                return self._parse_gemini_response(response)
            else:
                self.logger.error("Gemini API请求失败")
                return None

        except Exception as e:
            self.logger.error(f"Gemini字幕分析异常: {e}")
            return None

    def _extract_keyframes(self, video_path: str, sample_frames: int) -> List[np.ndarray]:
        """提取视频关键帧"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.logger.error("无法打开视频文件")
                return []

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            # 计算采样间隔
            interval = max(1, total_frames // sample_frames)

            frames = []
            frame_indices = [i * interval for i in range(sample_frames)]

            for i in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if ret:
                    # 调整帧大小以减少数据量
                    height, width = frame.shape[:2]
                    if width > 1280:
                        ratio = 1280 / width
                        new_width = 1280
                        new_height = int(height * ratio)
                        frame = cv2.resize(frame, (new_width, new_height))
                    frames.append(frame)

            cap.release()
            self.logger.info(f"成功提取 {len(frames)} 帧用于分析")
            return frames

        except Exception as e:
            self.logger.error(f"提取视频帧异常: {e}")
            return []

    def _build_subtitle_detection_prompt(self) -> str:
        """构建字幕检测提示词"""
        return """
        请分析以下视频帧，检测其中的硬字幕（hard subtitle）信息。

        请按照以下格式返回JSON响应：
        {
            "has_subtitles": boolean,           // 是否包含字幕
            "subtitle_type": "hard",            // 字幕类型（固定为"hard"）
            "dominant_position": "bottom",      // 主要字幕位置（"top"/"bottom"/"middle"）
            "regions": [                        // 字幕区域列表
                {
                    "x": int,                   // 区域左上角x坐标
                    "y": int,                   // 区域左上角y坐标
                    "width": int,               // 区域宽度
                    "height": int,              // 区域高度
                    "confidence": float,        // 置信度(0-1)
                    "text_content": string      // 识别的文本内容（如果能识别）
                }
            ]
        }

        要求：
        1. 只检测硬字幕（直接渲染在视频画面上的字幕）
        2. 不要检测软字幕（可选的字幕轨道）
        3. 如果没有检测到字幕，返回 {"has_subtitles": false, "subtitle_type": "hard", "dominant_position": "unknown", "regions": []}
        4. 尽可能准确地定位字幕区域
        5. 置信度应反映你对检测结果的确定程度
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

            self.logger.info("正在发送请求到Gemini API...")
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=contents,
                timeout=60
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

    def _parse_gemini_response(self, response: Dict[Any, Any]) -> SubtitleAnalysis:
        """解析Gemini响应"""
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

                        # 转换为SubtitleAnalysis对象
                        regions = []
                        for region_data in result.get('regions', []):
                            region = SubtitleRegion(
                                x=region_data['x'],
                                y=region_data['y'],
                                width=region_data['width'],
                                height=region_data['height'],
                                confidence=region_data['confidence'],
                                text_content=region_data.get('text_content', '')
                            )
                            regions.append(region)

                        analysis = SubtitleAnalysis(
                            has_subtitles=result['has_subtitles'],
                            subtitle_type=result['subtitle_type'],
                            dominant_position=result['dominant_position'],
                            regions=regions
                        )

                        self.logger.info(f"成功解析Gemini响应: {analysis.has_subtitles}, 区域数: {len(regions)}")
                        return analysis

            # 默认返回无字幕结果
            self.logger.warning("无法解析Gemini响应，返回默认结果")
            return SubtitleAnalysis(
                has_subtitles=False,
                subtitle_type="hard",
                dominant_position="unknown",
                regions=[]
            )

        except Exception as e:
            self.logger.error(f"解析Gemini响应异常: {e}")
            # 返回默认结果
            return SubtitleAnalysis(
                has_subtitles=False,
                subtitle_type="hard",
                dominant_position="unknown",
                regions=[]
            )