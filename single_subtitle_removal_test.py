#!/usr/bin/env python3
"""
单个高置信度字幕去除测试
专门处理置信度最高的单个字幕区域，提高精确度
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

# 导入模块
from updated_token_manager import TokenManager
from updated_gemini_client import GeminiClient
from backend.inpaint.lama_inpaint import LamaInpaint
from backend import config

def get_highest_confidence_region(detection_result: dict) -> dict:
    """获取置信度最高的字幕区域"""
    regions = detection_result.get('regions', [])
    if not regions:
        return None

    # 按置信度排序，取最高的
    highest_region = max(regions, key=lambda r: r.get('confidence', 0))
    logger.info(f"选择最高置信度区域: {highest_region['text_content']} (置信度: {highest_region['confidence']})")
    return highest_region

def create_precise_mask(image_shape: tuple, region: dict) -> np.ndarray:
    """为单个区域创建精确掩码"""
    height, width = image_shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)

    x = region.get('x', 0)
    y = region.get('y', 0)
    w = region.get('width', 0)
    h = region.get('height', 0)

    # 更精细的扩展策略
    # 对于高置信度区域，使用更保守的扩展
    expansion_x = max(5, w // 20)  # 宽度的5%或至少5像素
    expansion_y = max(3, h // 10)  # 高度的10%或至少3像素

    # 应用扩展
    x_start = max(0, x - expansion_x)
    y_start = max(0, y - expansion_y)
    x_end = min(width, x + w + expansion_x)
    y_end = min(height, y + h + expansion_y)

    # 填充掩码
    mask[y_start:y_end, x_start:x_end] = 255

    logger.info(f"精确掩码区域: ({x_start}, {y_start}) -> ({x_end}, {y_end})")
    logger.info(f"掩码大小: {x_end - x_start}x{y_end - y_start}")
    logger.info(f"扩展量: x={expansion_x}, y={expansion_y}")

    return mask

def visualize_single_region(image_path: str, region: dict, output_path: str):
    """可视化单个字幕区域"""
    # 读取原图
    image = cv2.imread(image_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(image_rgb)
    draw = ImageDraw.Draw(pil_image)

    # 尝试加载字体
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    x = region.get('x', 0)
    y = region.get('y', 0)
    w = region.get('width', 0)
    h = region.get('height', 0)
    confidence = region.get('confidence', 0)
    text_content = region.get('text_content', 'Unknown')

    # 绘制原始检测框（红色）
    draw.rectangle([x, y, x+w, y+h], outline='red', width=4)

    # 计算扩展后的区域（绿色虚线）
    expansion_x = max(5, w // 20)
    expansion_y = max(3, h // 10)
    x_exp = max(0, x - expansion_x)
    y_exp = max(0, y - expansion_y)
    w_exp = min(pil_image.width - x_exp, w + 2 * expansion_x)
    h_exp = min(pil_image.height - y_exp, h + 2 * expansion_y)

    # 绘制扩展区域框（绿色）
    draw.rectangle([x_exp, y_exp, x_exp+w_exp, y_exp+h_exp], outline='green', width=2)

    # 绘制标签
    label = f"高置信度字幕: {confidence:.2f}"
    label_y = max(10, y - 50)
    draw.text((x, label_y), label, fill='red', font=font)

    # 绘制文本内容
    content_y = max(30, y - 25)
    draw.text((x, content_y), text_content, fill='blue', font=small_font)

    # 绘制处理信息
    info_y = y + h + 10
    draw.text((x, info_y), f"原始: {w}x{h}, 扩展: {w_exp}x{h_exp}", fill='black', font=small_font)

    # 保存可视化结果
    pil_image.save(output_path)
    logger.info(f"单区域可视化已保存: {output_path}")

def test_single_subtitle_removal():
    """测试单个字幕的精确去除"""
    logger.info("="*60)
    logger.info("单个高置信度字幕精确去除测试")
    logger.info("="*60)

    # 1. 初始化组件
    logger.info("1. 初始化Vertex AI组件...")
    try:
        token_manager = TokenManager()
        gemini_client = GeminiClient(token_manager)
        logger.info("✓ Vertex AI组件初始化成功")
    except Exception as e:
        logger.error(f"✗ 组件初始化失败: {e}")
        return

    # 2. 检查测试图片
    test_image = "/home/jiarui/software/video-subtitle-remover/images/test_image_with_subtitle.jpg"
    if not os.path.exists(test_image):
        logger.error(f"✗ 测试图片不存在: {test_image}")
        return

    logger.info(f"✓ 测试图片: {test_image}")

    # 3. 检测字幕
    logger.info("2. 检测字幕区域...")
    try:
        detection_result = gemini_client.analyze_image_subtitles(test_image)
        if not detection_result or not detection_result.get('has_subtitles', False):
            logger.error("✗ 未检测到字幕")
            return

        # 获取最高置信度区域
        highest_region = get_highest_confidence_region(detection_result)
        if not highest_region:
            logger.error("✗ 无法获取最高置信度区域")
            return

        logger.info(f"✓ 目标字幕: '{highest_region['text_content']}'")
        logger.info(f"  位置: ({highest_region['x']}, {highest_region['y']})")
        logger.info(f"  大小: {highest_region['width']}x{highest_region['height']}")
        logger.info(f"  置信度: {highest_region['confidence']}")

    except Exception as e:
        logger.error(f"✗ 字幕检测失败: {e}")
        return

    # 4. 创建输出目录
    output_dir = "./images"
    os.makedirs(output_dir, exist_ok=True)
    base_name = "single_subtitle_test"

    # 5. 可视化单个区域
    logger.info("3. 生成单区域可视化...")
    try:
        viz_path = os.path.join(output_dir, f"{base_name}_single_region.jpg")
        visualize_single_region(test_image, highest_region, viz_path)
        logger.info(f"✓ 单区域可视化: {viz_path}")
    except Exception as e:
        logger.error(f"✗ 可视化失败: {e}")
        return

    # 6. 加载LAMA模型
    logger.info("4. 加载LAMA模型...")
    try:
        lama_model = LamaInpaint(device=config.device)
        logger.info("✓ LAMA模型加载成功")
    except Exception as e:
        logger.error(f"✗ LAMA模型加载失败: {e}")
        return

    # 7. 创建精确掩码并去除字幕
    logger.info("5. 创建精确掩码并执行去字幕...")
    try:
        # 读取原图
        image = cv2.imread(test_image)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 创建精确掩码
        mask = create_precise_mask(image.shape, highest_region)

        # 保存掩码
        mask_path = os.path.join(output_dir, f"{base_name}_precise_mask.jpg")
        cv2.imwrite(mask_path, mask)
        logger.info(f"✓ 精确掩码已保存: {mask_path}")

        # 使用LAMA修复
        logger.info("正在使用LAMA进行精确修复...")
        result_image = lama_model(image_rgb, mask)

        # 保存结果
        result_path = os.path.join(output_dir, f"{base_name}_precise_result.jpg")
        result_bgr = cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR)
        cv2.imwrite(result_path, result_bgr)
        logger.info(f"✓ 精确去字幕结果: {result_path}")

    except Exception as e:
        logger.error(f"✗ 精确去字幕处理失败: {e}")
        return

    # 8. 保存处理信息
    logger.info("6. 保存处理信息...")
    info_data = {
        "target_region": highest_region,
        "processing_info": {
            "expansion_strategy": "conservative_percentage_based",
            "expansion_x": max(5, highest_region['width'] // 20),
            "expansion_y": max(3, highest_region['height'] // 10),
            "mask_area": f"{highest_region['width'] + 2*max(5, highest_region['width'] // 20)}x{highest_region['height'] + 2*max(3, highest_region['height'] // 10)}"
        }
    }

    info_path = os.path.join(output_dir, f"{base_name}_info.json")
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(info_data, f, indent=2, ensure_ascii=False)

    # 9. 输出最终总结
    logger.info("="*60)
    logger.info("单个字幕精确去除测试完成！")
    logger.info("="*60)
    logger.info("生成的文件:")
    logger.info(f"  原图: {test_image}")
    logger.info(f"  单区域可视化: {viz_path}")
    logger.info(f"  精确掩码: {mask_path}")
    logger.info(f"  精确去字幕结果: {result_path}")
    logger.info(f"  处理信息: {info_path}")
    logger.info("")
    logger.info(f"目标字幕: '{highest_region['text_content']}'")
    logger.info(f"置信度: {highest_region['confidence']}")
    logger.info("="*60)

if __name__ == "__main__":
    test_single_subtitle_removal()