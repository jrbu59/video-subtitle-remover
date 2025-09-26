#!/usr/bin/env python3
"""
调试坐标映射问题
分析Gemini检测坐标与实际字幕位置的对应关系
"""

import os
import sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from updated_token_manager import TokenManager
from updated_gemini_client import GeminiClient

def create_debug_visualization(image_path: str, detection_result: dict, output_path: str):
    """创建详细的调试可视化"""
    # 读取原图
    image = cv2.imread(image_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(image_rgb)
    draw = ImageDraw.Draw(pil_image)

    # 尝试加载字体
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    regions = detection_result.get('regions', [])
    colors = ['red', 'blue', 'green', 'orange', 'purple']

    for i, region in enumerate(regions):
        x = region.get('x', 0)
        y = region.get('y', 0)
        w = region.get('width', 0)
        h = region.get('height', 0)
        confidence = region.get('confidence', 0)
        text_content = region.get('text_content', 'Unknown')

        color = colors[i % len(colors)]

        # 绘制检测框
        draw.rectangle([x, y, x+w, y+h], outline=color, width=3)

        # 绘制坐标信息
        coord_text = f"({x},{y}) {w}x{h}"
        draw.text((x, y-40), coord_text, fill=color, font=small_font)

        # 绘制置信度和内容
        info_text = f"#{i+1}: {confidence:.2f} - {text_content}"
        draw.text((x, y-20), info_text, fill=color, font=small_font)

        # 绘制中心点
        center_x = x + w // 2
        center_y = y + h // 2
        draw.ellipse([center_x-3, center_y-3, center_x+3, center_y+3], fill=color)

    # 添加调试网格
    width, height = pil_image.size
    grid_size = 50

    # 绘制网格线
    for i in range(0, width, grid_size):
        draw.line([(i, 0), (i, height)], fill='lightgray', width=1)
    for j in range(0, height, grid_size):
        draw.line([(0, j), (width, j)], fill='lightgray', width=1)

    # 添加标尺
    for i in range(0, width, 100):
        draw.text((i, 5), str(i), fill='black', font=small_font)
    for j in range(0, height, 100):
        draw.text((5, j), str(j), fill='black', font=small_font)

    # 保存调试图
    pil_image.save(output_path)
    logger.info(f"调试可视化已保存: {output_path}")

def create_manual_mask_test(image_path: str, output_dir: str):
    """创建手动校正的掩码测试"""
    # 读取原图
    image = cv2.imread(image_path)
    height, width = image.shape[:2]

    # 基于观察，手动定义顶部字幕的准确位置
    # 从原图观察，顶部字幕大约在这个位置：
    manual_regions = [
        {
            "name": "top_subtitle_manual",
            "x": 160,  # 手动调整的x坐标
            "y": 205,  # 手动调整的y坐标
            "width": 580,  # 手动调整的宽度
            "height": 65,  # 手动调整的高度
            "note": "手动标注的顶部字幕位置"
        }
    ]

    for i, region in enumerate(manual_regions):
        # 创建掩码
        mask = np.zeros((height, width), dtype=np.uint8)

        x = region['x']
        y = region['y']
        w = region['width']
        h = region['height']

        # 填充掩码
        mask[y:y+h, x:x+w] = 255

        # 保存掩码
        mask_path = os.path.join(output_dir, f"manual_mask_{region['name']}.jpg")
        cv2.imwrite(mask_path, mask)
        logger.info(f"手动掩码已保存: {mask_path}")

        # 创建可视化
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        draw = ImageDraw.Draw(pil_image)

        # 绘制手动标注区域
        draw.rectangle([x, y, x+w, y+h], outline='yellow', width=4)
        draw.text((x, y-25), region['note'], fill='yellow')
        draw.text((x, y-10), f"({x},{y}) {w}x{h}", fill='yellow')

        viz_path = os.path.join(output_dir, f"manual_region_{region['name']}.jpg")
        pil_image.save(viz_path)
        logger.info(f"手动标注可视化: {viz_path}")

def main():
    """主调试函数"""
    logger.info("="*60)
    logger.info("坐标映射调试分析")
    logger.info("="*60)

    # 1. 初始化组件
    logger.info("1. 初始化Vertex AI组件...")
    try:
        token_manager = TokenManager()
        gemini_client = GeminiClient(token_manager)
        logger.info("✓ 组件初始化成功")
    except Exception as e:
        logger.error(f"✗ 组件初始化失败: {e}")
        return

    # 2. 检测字幕
    test_image = "/home/jiarui/software/video-subtitle-remover/images/test_image_with_subtitle.jpg"
    if not os.path.exists(test_image):
        logger.error(f"✗ 测试图片不存在: {test_image}")
        return

    logger.info("2. 重新检测字幕...")
    try:
        detection_result = gemini_client.analyze_image_subtitles(test_image)
        if not detection_result:
            logger.error("✗ 检测失败")
            return

        logger.info("✓ 检测结果:")
        for i, region in enumerate(detection_result.get('regions', [])):
            logger.info(f"  区域{i+1}: ({region['x']}, {region['y']}) "
                       f"{region['width']}x{region['height']} "
                       f"置信度:{region['confidence']} "
                       f"'{region['text_content']}'")

    except Exception as e:
        logger.error(f"✗ 检测失败: {e}")
        return

    # 3. 创建调试可视化
    output_dir = "./images"
    os.makedirs(output_dir, exist_ok=True)

    logger.info("3. 创建详细调试可视化...")
    debug_viz_path = os.path.join(output_dir, "debug_coordinate_mapping.jpg")
    create_debug_visualization(test_image, detection_result, debug_viz_path)

    # 4. 创建手动校正测试
    logger.info("4. 创建手动校正掩码测试...")
    create_manual_mask_test(test_image, output_dir)

    logger.info("="*60)
    logger.info("调试分析完成！请查看生成的文件进行对比分析。")
    logger.info("="*60)

if __name__ == "__main__":
    main()