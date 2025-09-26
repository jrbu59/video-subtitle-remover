"""
Gemini API客户端模块 - 基于Vertex AI的图片字幕检测
"""

import requests
import json
import logging
import time
import base64
import cv2
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class GeminiClient:
    """Vertex AI Gemini客户端 - 专门用于图片字幕检测"""

    def __init__(self, token_manager, project_id: str = "curious-skyline-408708",
                 location: str = "us-central1", model_name: str = "gemini-1.5-pro"):
        self.token_manager = token_manager
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        self.base_url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}"

        logger.info(f"初始化GeminiClient: {project_id}/{location}/{model_name}")

    def _make_api_call(self, endpoint: str, data: dict, max_retries: int = 3) -> dict:
        """带重试的API调用"""
        for attempt in range(max_retries):
            try:
                # 获取当前有效令牌
                token = self.token_manager.get_token()

                headers = {
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                }

                url = f"{self.base_url}/{endpoint}"
                logger.info(f"调用API: {url}")

                response = requests.post(url, headers=headers, json=data, timeout=60)

                if response.status_code == 401:
                    # 令牌无效，强制刷新后重试
                    logger.warning("令牌认证失败，强制刷新令牌")
                    self.token_manager.force_refresh()
                    continue

                elif response.status_code == 429:
                    # 限流，等待后重试
                    wait_time = min(2 ** attempt * 5, 60)
                    logger.warning(f"API限流，等待 {wait_time} 秒后重试")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.RequestException as e:
                logger.warning(f"API调用失败 (尝试 {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    wait_time = min(2 ** attempt, 30)
                    time.sleep(wait_time)
                else:
                    raise Exception(f"API调用失败: {e}")

    def analyze_image_subtitles(self, image_path: str) -> Optional[Dict]:
        """
        分析单张图片中的字幕区域

        Args:
            image_path: 图片文件路径

        Returns:
            字幕分析结果
        """
        try:
            logger.info(f"开始分析图片字幕: {image_path}")

            # 编码图片
            image_data = self._encode_image_to_base64(image_path)
            if not image_data:
                return None

            # 构造请求数据
            request_data = self._build_subtitle_detection_request(image_data)

            # 调用API
            endpoint = f"publishers/google/models/{self.model_name}:generateContent"
            response = self._make_api_call(endpoint, request_data)

            # 解析响应
            return self._parse_gemini_response(response)

        except Exception as e:
            logger.error(f"图片字幕分析异常: {e}")
            return None

    def _encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """将图片编码为base64"""
        try:
            # 读取图片
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"无法读取图片: {image_path}")
                return None

            # 调整图片大小以减少数据量（如果太大）
            height, width = image.shape[:2]
            if width > 1280:
                ratio = 1280 / width
                new_width = 1280
                new_height = int(height * ratio)
                image = cv2.resize(image, (new_width, new_height))
                logger.info(f"图片已调整大小: {width}x{height} -> {new_width}x{new_height}")

            # 编码为JPEG格式
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not _:
                logger.error("图片编码失败")
                return None

            # 转换为base64
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            logger.info(f"图片编码完成，数据大小: {len(image_base64)} 字符")
            return image_base64

        except Exception as e:
            logger.error(f"图片编码异常: {e}")
            return None

    def _build_subtitle_detection_request(self, image_data: str) -> dict:
        """构建字幕检测请求"""
        prompt = """
请仔细分析这张图片，检测其中的字幕文本区域。请注意以下要求：

1. 只检测硬字幕（直接渲染在图片上的文本）
2. 不要检测图片中商品包装上的文字或其他非字幕文本
3. 字幕通常位于图片的顶部或底部，具有较为规整的矩形背景或边框
4. 请准确定位每个字幕区域的边界框坐标

请严格按照以下JSON格式返回结果：

{
    "has_subtitles": boolean,           // 是否包含字幕
    "subtitle_type": "hard",            // 字幕类型（固定为"hard"）
    "dominant_position": "bottom",      // 主要字幕位置（"top"/"bottom"/"middle"）
    "regions": [                        // 字幕区域列表
        {
            "x": int,                   // 区域左上角x坐标（像素）
            "y": int,                   // 区域左上角y坐标（像素）
            "width": int,               // 区域宽度（像素）
            "height": int,              // 区域高度（像素）
            "confidence": float,        // 置信度(0-1)
            "text_content": string      // 识别的文本内容
        }
    ]
}

要求：
- 如果没有检测到字幕，返回 {"has_subtitles": false, "subtitle_type": "hard", "dominant_position": "unknown", "regions": []}
- 尽可能准确地定位字幕区域的边界框
- 置信度应反映你对检测结果的确定程度
- 只检测明显的字幕文本，不要包含商品包装上的文字

请只返回JSON格式的结果，不要包含其他解释文字。
"""

        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_data
                            }
                        }
                    ]
                }
            ],
            "generation_config": {
                "temperature": 0.1,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
                "response_mime_type": "text/plain"
            }
        }

    def _parse_gemini_response(self, response: Dict) -> Optional[Dict]:
        """解析Gemini响应"""
        try:
            # 提取响应内容
            candidates = response.get('candidates', [])
            if not candidates:
                logger.error("响应中没有candidates")
                return None

            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            if not parts:
                logger.error("响应中没有parts")
                return None

            text_content = parts[0].get('text', '')
            if not text_content:
                logger.error("响应中没有文本内容")
                return None

            logger.info(f"Gemini响应内容: {text_content}")

            # 解析JSON响应
            try:
                # 清理响应文本（移除可能的markdown代码块标记）
                clean_text = text_content.strip()
                if clean_text.startswith('```json'):
                    clean_text = clean_text[7:]
                elif clean_text.startswith('```'):
                    clean_text = clean_text[3:]

                if clean_text.endswith('```'):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()

                result = json.loads(clean_text)
                logger.info(f"成功解析Gemini响应: 检测到字幕={result.get('has_subtitles', False)}, 区域数={len(result.get('regions', []))}")
                return result

            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}")
                logger.error(f"原始响应: {text_content}")
                return None

        except Exception as e:
            logger.error(f"解析Gemini响应异常: {e}")
            return None