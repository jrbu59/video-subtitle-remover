#!/usr/bin/env python3
"""
相对坐标校正系统
解决Gemini绝对坐标与实际位置偏差问题
"""

import os
import sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import logging
import json

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from updated_token_manager import TokenManager
from updated_gemini_client import GeminiClient
from backend.inpaint.lama_inpaint import LamaInpaint
from backend import config

class RelativeCoordinateCorrector:
    """相对坐标校正器"""

    def __init__(self):
        self.correction_rules = {
            # 基于观察到的偏差模式定义校正规则
            "top_subtitle": {
                "y_offset": 270,  # 向下偏移270像素
                "x_offset": -70,  # 向左偏移70像素
                "width_scale": 1.07,  # 宽度增加7%
                "height_scale": 0.625,  # 高度减少37.5%
                "description": "顶部字幕校正规则"
            },
            "bottom_subtitle": {
                "y_offset": 0,
                "x_offset": 0,
                "width_scale": 1.0,
                "height_scale": 1.0,
                "description": "底部字幕通常比较准确"
            }
        }

    def detect_subtitle_position(self, region: dict, image_height: int) -> str:
        """检测字幕位置类型"""
        y = region.get('y', 0)
        height = region.get('height', 0)

        # 根据y坐标判断字幕位置
        if y + height < image_height * 0.4:
            return "top_subtitle"
        elif y > image_height * 0.7:
            return "bottom_subtitle"
        else:
            return "middle_subtitle"

    def apply_correction(self, region: dict, image_shape: tuple) -> dict:
        """应用相对坐标校正"""
        height, width = image_shape[:2]
        position_type = self.detect_subtitle_position(region, height)

        # 获取校正规则
        if position_type in self.correction_rules:
            rule = self.correction_rules[position_type]
        else:
            rule = self.correction_rules["top_subtitle"]  # 默认使用顶部规则

        # 应用校正
        corrected_region = region.copy()

        # 坐标校正
        corrected_region['x'] = max(0, region['x'] + rule['x_offset'])
        corrected_region['y'] = max(0, region['y'] + rule['y_offset'])

        # 尺寸校正
        corrected_region['width'] = int(region['width'] * rule['width_scale'])
        corrected_region['height'] = int(region['height'] * rule['height_scale'])

        # 边界检查
        corrected_region['x'] = min(corrected_region['x'], width - corrected_region['width'])
        corrected_region['y'] = min(corrected_region['y'], height - corrected_region['height'])
        corrected_region['width'] = min(corrected_region['width'], width - corrected_region['x'])
        corrected_region['height'] = min(corrected_region['height'], height - corrected_region['y'])

        # 添加校正信息
        corrected_region['correction_info'] = {
            'position_type': position_type,
            'rule_applied': rule['description'],
            'original_coords': (region['x'], region['y'], region['width'], region['height']),
            'corrected_coords': (corrected_region['x'], corrected_region['y'],
                               corrected_region['width'], corrected_region['height'])
        }

        logger.info(f"坐标校正: {position_type}")
        logger.info(f"  原始: ({region['x']}, {region['y']}) {region['width']}x{region['height']}")
        logger.info(f"  校正: ({corrected_region['x']}, {corrected_region['y']}) "
                   f"{corrected_region['width']}x{corrected_region['height']}")

        return corrected_region

class RelativeCoordinateGeminiClient(GeminiClient):
    """支持相对坐标的Gemini客户端"""

    def _build_subtitle_detection_request(self, image_data: str) -> dict:
        """构建支持相对坐标的字幕检测请求"""
        prompt = """
请仔细分析这张图片，检测其中的字幕文本区域。

重要要求：
1. 只检测硬字幕（直接渲染在图片上的文本）
2. 不要检测图片中商品包装上的文字或其他非字幕文本
3. 字幕通常位于图片的顶部或底部，具有较为规整的矩形背景或边框
4. 请提供精确的边界框坐标，确保完全覆盖字幕文本
5. 坐标系统：以图片左上角为原点(0,0)，x轴向右，y轴向下

请严格按照以下JSON格式返回结果：

{
    "has_subtitles": boolean,           // 是否包含字幕
    "subtitle_type": "hard",            // 字幕类型（固定为"hard"）
    "dominant_position": "bottom",      // 主要字幕位置（"top"/"bottom"/"middle"）
    "image_info": {                     // 图片信息
        "estimated_width": int,         // 估计的图片宽度
        "estimated_height": int         // 估计的图片高度
    },
    "regions": [                        // 字幕区域列表
        {
            "x": int,                   // 区域左上角x坐标（像素）
            "y": int,                   // 区域左上角y坐标（像素）
            "width": int,               // 区域宽度（像素）
            "height": int,              // 区域高度（像素）
            "confidence": float,        // 置信度(0-1)
            "text_content": string,     // 识别的文本内容
            "relative_position": {      // 相对位置信息
                "x_percent": float,     // x坐标相对于图片宽度的百分比
                "y_percent": float,     // y坐标相对于图片高度的百分比
                "width_percent": float, // 宽度相对于图片宽度的百分比
                "height_percent": float // 高度相对于图片高度的百分比
            }
        }
    ]
}

要求：
- 如果没有检测到字幕，返回 {"has_subtitles": false, "subtitle_type": "hard", "dominant_position": "unknown", "regions": []}
- 尽可能准确地定位字幕区域的边界框
- 置信度应反映你对检测结果的确定程度
- 只检测明显的字幕文本，不要包含商品包装上的文字
- 提供相对位置百分比，便于坐标校正

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
                "max_output_tokens": 3072,
                "response_mime_type": "text/plain"
            }
        }

def test_relative_coordinate_correction():
    """测试相对坐标校正系统"""
    logger.info("="*60)
    logger.info("相对坐标校正系统测试")
    logger.info("="*60)

    # 1. 初始化组件
    logger.info("1. 初始化组件...")
    try:
        token_manager = TokenManager()
        gemini_client = RelativeCoordinateGeminiClient(token_manager)
        corrector = RelativeCoordinateCorrector()
        logger.info("✓ 组件初始化成功")
    except Exception as e:
        logger.error(f"✗ 组件初始化失败: {e}")
        return

    # 2. 检测字幕
    test_image = "/home/jiarui/software/video-subtitle-remover/images/test_image_with_subtitle.jpg"
    if not os.path.exists(test_image):
        logger.error(f"✗ 测试图片不存在: {test_image}")
        return

    logger.info("2. 使用增强Gemini检测字幕...")
    try:
        detection_result = gemini_client.analyze_image_subtitles(test_image)
        if not detection_result or not detection_result.get('has_subtitles', False):
            logger.error("✗ 未检测到字幕")
            return

        regions = detection_result.get('regions', [])
        logger.info(f"✓ 检测到 {len(regions)} 个字幕区域")

    except Exception as e:
        logger.error(f"✗ 字幕检测失败: {e}")
        return

    # 3. 读取图片获取实际尺寸
    image = cv2.imread(test_image)
    actual_height, actual_width = image.shape[:2]
    logger.info(f"实际图片尺寸: {actual_width}x{actual_height}")

    # 4. 应用坐标校正
    logger.info("3. 应用相对坐标校正...")
    corrected_regions = []
    for i, region in enumerate(regions):
        logger.info(f"\n处理区域 {i+1}: {region.get('text_content', 'Unknown')}")
        corrected_region = corrector.apply_correction(region, image.shape)
        corrected_regions.append(corrected_region)

    # 5. 创建对比可视化
    logger.info("4. 创建校正对比可视化...")
    output_dir = "./images"
    os.makedirs(output_dir, exist_ok=True)

    # 可视化原始检测结果
    create_comparison_visualization(test_image, regions, corrected_regions,
                                  os.path.join(output_dir, "coordinate_correction_comparison.jpg"))

    # 6. 测试最高置信度区域的去字幕效果
    if corrected_regions:
        highest_region = max(corrected_regions, key=lambda r: r.get('confidence', 0))
        logger.info("5. 测试校正后的去字幕效果...")

        test_lama_with_corrected_coordinates(test_image, highest_region, output_dir)

    # 7. 保存校正信息
    correction_info = {
        "original_detection": detection_result,
        "corrected_regions": corrected_regions,
        "correction_summary": {
            "total_regions": len(regions),
            "image_size": {"width": actual_width, "height": actual_height},
            "correction_rules_applied": [r.get('correction_info', {}).get('rule_applied') for r in corrected_regions]
        }
    }

    info_path = os.path.join(output_dir, "coordinate_correction_info.json")
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(correction_info, f, indent=2, ensure_ascii=False)

    logger.info("="*60)
    logger.info("相对坐标校正测试完成！")
    logger.info("="*60)

def create_comparison_visualization(image_path: str, original_regions: list,
                                  corrected_regions: list, output_path: str):
    """创建原始vs校正后的对比可视化"""
    # 读取原图
    image = cv2.imread(image_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(image_rgb)
    draw = ImageDraw.Draw(pil_image)

    # 字体
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # 绘制原始检测结果（红色）
    for i, region in enumerate(original_regions):
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        draw.rectangle([x, y, x+w, y+h], outline='red', width=3)
        draw.text((x, y-40), f"原始{i+1}: {region.get('confidence', 0):.2f}", fill='red', font=small_font)
        draw.text((x, y-25), region.get('text_content', 'Unknown')[:15], fill='red', font=small_font)

    # 绘制校正后结果（绿色）
    for i, region in enumerate(corrected_regions):
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        draw.rectangle([x, y, x+w, y+h], outline='lime', width=3)
        draw.text((x, y+h+5), f"校正{i+1}: {region.get('confidence', 0):.2f}", fill='lime', font=small_font)

        # 显示校正信息
        correction_info = region.get('correction_info', {})
        if correction_info:
            orig_coords = correction_info.get('original_coords', (0,0,0,0))
            offset_info = f"偏移: ({x-orig_coords[0]}, {y-orig_coords[1]})"
            draw.text((x, y+h+20), offset_info, fill='lime', font=small_font)

    # 添加图例
    legend_y = 50
    draw.text((10, legend_y), "红色框: Gemini原始检测", fill='red', font=font)
    draw.text((10, legend_y+25), "绿色框: 相对坐标校正后", fill='lime', font=font)

    # 保存对比图
    pil_image.save(output_path)
    logger.info(f"校正对比可视化已保存: {output_path}")

def test_lama_with_corrected_coordinates(image_path: str, corrected_region: dict, output_dir: str):
    """使用校正后的坐标测试LAMA去字幕"""
    try:
        # 读取原图
        image = cv2.imread(image_path)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        height, width = image.shape[:2]

        # 创建掩码
        mask = np.zeros((height, width), dtype=np.uint8)
        x = corrected_region['x']
        y = corrected_region['y']
        w = corrected_region['width']
        h = corrected_region['height']

        # 小幅扩展
        expansion = 5
        x = max(0, x - expansion)
        y = max(0, y - expansion)
        w = min(width - x, w + 2 * expansion)
        h = min(height - y, h + 2 * expansion)

        mask[y:y+h, x:x+w] = 255

        # 保存校正掩码
        mask_path = os.path.join(output_dir, "corrected_coordinate_mask.jpg")
        cv2.imwrite(mask_path, mask)
        logger.info(f"校正坐标掩码: {mask_path}")

        # 使用LAMA修复
        lama_model = LamaInpaint(device=config.device)
        result_image = lama_model(image_rgb, mask)

        # 保存结果
        result_path = os.path.join(output_dir, "corrected_coordinate_lama_result.jpg")
        result_bgr = cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR)
        cv2.imwrite(result_path, result_bgr)
        logger.info(f"校正坐标LAMA结果: {result_path}")

    except Exception as e:
        logger.error(f"LAMA测试失败: {e}")

if __name__ == "__main__":
    test_relative_coordinate_correction()