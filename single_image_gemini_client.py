#!/usr/bin/env python3
"""
单张图片的Gemini字幕检测客户端
用于测试单张图片的字幕区域检测
"""

import os
import json
import base64
import requests
import cv2
import numpy as np
from PIL import Image, ImageDraw
from typing import Optional, List, Dict, Any
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SingleImageGeminiClient:
    """单张图片的Gemini API客户端"""

    def __init__(self, api_key: str = None, model_name: str = "gemini-1.5-pro"):
        """
        初始化客户端

        Args:
            api_key: Gemini API密钥
            model_name: 模型名称
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self.model_name = model_name

        if not self.api_key:
            raise ValueError("请设置GEMINI_API_KEY环境变量或传入api_key参数")

        # 使用Google AI Studio API端点
        self.api_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

        logger.info(f"初始化Gemini客户端，模型: {model_name}")

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

            if not os.path.exists(image_path):
                logger.error(f"图片文件不存在: {image_path}")
                return None

            # 读取并编码图片
            image_data = self._encode_image_to_base64(image_path)
            if not image_data:
                return None

            # 构造提示词
            prompt = self._build_subtitle_detection_prompt()

            # 发送请求到Gemini API
            response = self._send_gemini_request(prompt, image_data, image_path)

            if response:
                return self._parse_gemini_response(response)
            else:
                logger.error("Gemini API请求失败")
                return None

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

    def _build_subtitle_detection_prompt(self) -> str:
        """构建字幕检测提示词"""
        return """
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

    def _send_gemini_request(self, prompt: str, image_data: str, image_path: str) -> Optional[Dict]:
        """发送请求到Gemini API"""
        try:
            # 构造请求体
            request_body = {
                "contents": [
                    {
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
                "generationConfig": {
                    "temperature": 0.1,  # 降低随机性，提高一致性
                    "topK": 1,
                    "topP": 1,
                    "maxOutputTokens": 2048
                }
            }

            # 设置请求头
            headers = {
                "Content-Type": "application/json"
            }

            # 构造完整的URL，包含API密钥
            url = f"{self.api_endpoint}?key={self.api_key}"

            logger.info("正在发送请求到Gemini API...")

            # 发送请求
            response = requests.post(
                url,
                headers=headers,
                json=request_body,
                timeout=30
            )

            if response.status_code == 200:
                logger.info("Gemini API请求成功")
                return response.json()
            else:
                logger.error(f"Gemini API请求失败: HTTP {response.status_code}")
                logger.error(f"响应内容: {response.text}")
                return None

        except Exception as e:
            logger.error(f"发送Gemini请求异常: {e}")
            return None

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

# 测试函数
def test_single_image_detection():
    """测试单张图片字幕检测"""

    # 检查API密钥
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logger.error("请设置GEMINI_API_KEY环境变量")
        logger.info("您可以通过以下方式设置:")
        logger.info("export GEMINI_API_KEY='your_api_key_here'")
        return

    # 测试图片路径
    test_image = "/home/jiarui/software/video-subtitle-remover/images/test_image_with_subtitle.jpg"

    if not os.path.exists(test_image):
        logger.error(f"测试图片不存在: {test_image}")
        return

    try:
        # 创建客户端
        client = SingleImageGeminiClient(api_key=api_key)

        # 分析图片
        result = client.analyze_image_subtitles(test_image)

        if result:
            logger.info("\n=== 字幕检测结果 ===")
            logger.info(f"是否有字幕: {result.get('has_subtitles', False)}")
            logger.info(f"字幕类型: {result.get('subtitle_type', 'unknown')}")
            logger.info(f"主要位置: {result.get('dominant_position', 'unknown')}")

            regions = result.get('regions', [])
            logger.info(f"检测到的字幕区域数量: {len(regions)}")

            for i, region in enumerate(regions):
                logger.info(f"区域 {i+1}:")
                logger.info(f"  位置: ({region.get('x', 0)}, {region.get('y', 0)})")
                logger.info(f"  大小: {region.get('width', 0)}x{region.get('height', 0)}")
                logger.info(f"  置信度: {region.get('confidence', 0):.2f}")
                logger.info(f"  文本内容: {region.get('text_content', 'unknown')}")

            return result
        else:
            logger.error("字幕检测失败")
            return None

    except Exception as e:
        logger.error(f"测试异常: {e}")
        return None

if __name__ == "__main__":
    test_single_image_detection()