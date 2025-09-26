#!/usr/bin/env python3
"""
精确坐标测量工具
通过网格和像素级测量来精确标注字幕位置
"""

import os
import sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.inpaint.lama_inpaint import LamaInpaint
from backend import config

def create_measurement_grid(image_path: str, output_path: str):
    """创建带测量网格的图片"""
    # 读取原图
    image = cv2.imread(image_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    height, width = image.shape[:2]

    pil_image = Image.fromarray(image_rgb)
    draw = ImageDraw.Draw(pil_image)

    # 字体
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # 绘制精细网格（每25像素一条线）
    grid_size = 25

    # 垂直线
    for x in range(0, width, grid_size):
        # 主要网格线（每100像素）用粗线
        line_width = 2 if x % 100 == 0 else 1
        color = 'yellow' if x % 100 == 0 else 'lightgray'
        draw.line([(x, 0), (x, height)], fill=color, width=line_width)

        # 标注坐标（每100像素）
        if x % 100 == 0:
            draw.text((x+2, 5), str(x), fill='yellow', font=small_font)

    # 水平线
    for y in range(0, height, grid_size):
        line_width = 2 if y % 100 == 0 else 1
        color = 'yellow' if y % 100 == 0 else 'lightgray'
        draw.line([(0, y), (width, y)], fill=color, width=line_width)

        # 标注坐标（每100像素）
        if y % 100 == 0:
            draw.text((5, y+2), str(y), fill='yellow', font=small_font)

    # 添加图片信息
    info_text = f"图片尺寸: {width}x{height}"
    draw.text((10, height-30), info_text, fill='white', font=font)

    # 保存网格图
    pil_image.save(output_path)
    logger.info(f"测量网格图已保存: {output_path}")
    return width, height

def test_multiple_coordinates():
    """测试多个可能的坐标位置"""
    test_image = "/home/jiarui/software/video-subtitle-remover/images/test_image_with_subtitle.jpg"

    if not os.path.exists(test_image):
        logger.error("测试图片不存在")
        return

    # 创建测量网格
    output_dir = "./images"
    os.makedirs(output_dir, exist_ok=True)

    grid_path = os.path.join(output_dir, "measurement_grid.jpg")
    width, height = create_measurement_grid(test_image, grid_path)

    # 基于网格观察，定义多个测试坐标
    # 通过仔细观察字幕"配料表只有黑醋和水"的实际位置
    test_coordinates = [
        {
            "name": "test_1_conservative",
            "x": 140,
            "y": 435,
            "width": 600,
            "height": 60,
            "description": "保守估计，稍微偏左和偏上"
        },
        {
            "name": "test_2_centered",
            "x": 160,
            "y": 440,
            "width": 580,
            "height": 55,
            "description": "居中估计"
        },
        {
            "name": "test_3_wider",
            "x": 120,
            "y": 430,
            "width": 640,
            "height": 65,
            "description": "更宽的覆盖范围"
        },
        {
            "name": "test_4_precise",
            "x": 135,
            "y": 438,
            "width": 610,
            "height": 58,
            "description": "精确测量（基于网格观察）"
        }
    ]

    # 读取原图
    image = cv2.imread(test_image)

    for i, coord in enumerate(test_coordinates):
        logger.info(f"\n测试坐标 {i+1}: {coord['description']}")
        logger.info(f"坐标: ({coord['x']}, {coord['y']}) {coord['width']}x{coord['height']}")

        # 创建可视化
        create_coordinate_test_visualization(test_image, coord,
                                           os.path.join(output_dir, f"coordinate_test_{coord['name']}.jpg"))

        # 创建掩码
        mask = create_test_mask(image.shape, coord)
        mask_path = os.path.join(output_dir, f"mask_{coord['name']}.jpg")
        cv2.imwrite(mask_path, mask)

        # 使用LAMA测试
        test_lama_removal(test_image, mask,
                         os.path.join(output_dir, f"lama_result_{coord['name']}.jpg"))

def create_coordinate_test_visualization(image_path: str, coord: dict, output_path: str):
    """创建坐标测试可视化"""
    # 读取原图
    image = cv2.imread(image_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(image_rgb)
    draw = ImageDraw.Draw(pil_image)

    # 字体
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except:
        font = ImageFont.load_default()

    x, y, w, h = coord['x'], coord['y'], coord['width'], coord['height']

    # 绘制测试框（橙色）
    draw.rectangle([x, y, x+w, y+h], outline='orange', width=4)

    # 绘制中心点
    center_x, center_y = x + w//2, y + h//2
    draw.ellipse([center_x-3, center_y-3, center_x+3, center_y+3], fill='orange')

    # 绘制角点标记
    corner_size = 10
    draw.rectangle([x-corner_size//2, y-corner_size//2, x+corner_size//2, y+corner_size//2], fill='red')
    draw.rectangle([x+w-corner_size//2, y-corner_size//2, x+w+corner_size//2, y+corner_size//2], fill='red')
    draw.rectangle([x-corner_size//2, y+h-corner_size//2, x+corner_size//2, y+h+corner_size//2], fill='red')
    draw.rectangle([x+w-corner_size//2, y+h-corner_size//2, x+w+corner_size//2, y+h+corner_size//2], fill='red')

    # 添加标注
    draw.text((x, y-25), f"{coord['name']}: ({x},{y}) {w}x{h}", fill='orange', font=font)
    draw.text((x, y+h+5), coord['description'], fill='orange', font=font)

    # 保存
    pil_image.save(output_path)
    logger.info(f"坐标测试可视化: {output_path}")

def create_test_mask(image_shape: tuple, coord: dict) -> np.ndarray:
    """创建测试掩码"""
    height, width = image_shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)

    x, y, w, h = coord['x'], coord['y'], coord['width'], coord['height']

    # 边界检查
    x = max(0, x)
    y = max(0, y)
    w = min(w, width - x)
    h = min(h, height - y)

    mask[y:y+h, x:x+w] = 255
    return mask

def test_lama_removal(image_path: str, mask: np.ndarray, output_path: str):
    """测试LAMA去字幕效果"""
    try:
        # 读取图片
        image = cv2.imread(image_path)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # LAMA修复
        lama_model = LamaInpaint(device=config.device)
        result = lama_model(image_rgb, mask)

        # 保存结果
        result_bgr = cv2.cvtColor(result, cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, result_bgr)
        logger.info(f"LAMA测试结果: {output_path}")

    except Exception as e:
        logger.error(f"LAMA测试失败: {e}")

def find_optimal_coordinates():
    """通过视觉分析找到最优坐标"""

    # 基于对原图的仔细观察，我认为最精确的坐标应该是：
    # 字幕"配料表只有黑醋和水"从网格观察：
    # - 左边界大约在x=135-140左右
    # - 右边界大约在x=745-750左右，所以宽度约610-615
    # - 上边界大约在y=435-440左右
    # - 下边界大约在y=495-500左右，所以高度约60-65

    optimal_coords = {
        "name": "optimal_final",
        "x": 135,
        "y": 438,
        "width": 615,
        "height": 62,
        "description": "基于网格精确观察的最优坐标"
    }

    return optimal_coords

def main():
    """主函数"""
    logger.info("="*60)
    logger.info("精确坐标测量和验证")
    logger.info("="*60)

    # 1. 测试多个坐标
    logger.info("1. 测试多个候选坐标...")
    test_multiple_coordinates()

    # 2. 应用最优坐标
    logger.info("2. 应用最优坐标...")
    optimal = find_optimal_coordinates()

    test_image = "/home/jiarui/software/video-subtitle-remover/images/test_image_with_subtitle.jpg"
    output_dir = "./images"

    # 创建最优坐标的可视化和测试
    create_coordinate_test_visualization(test_image, optimal,
                                       os.path.join(output_dir, "optimal_coordinate_test.jpg"))

    image = cv2.imread(test_image)
    optimal_mask = create_test_mask(image.shape, optimal)
    cv2.imwrite(os.path.join(output_dir, "optimal_mask.jpg"), optimal_mask)

    test_lama_removal(test_image, optimal_mask,
                     os.path.join(output_dir, "optimal_lama_result.jpg"))

    # 保存最优坐标信息
    optimal_info = {
        "optimal_coordinates": optimal,
        "measurement_method": "grid_based_visual_analysis",
        "notes": "基于25像素网格进行精确视觉测量"
    }

    with open(os.path.join(output_dir, "optimal_coordinates_info.json"), 'w', encoding='utf-8') as f:
        import json
        json.dump(optimal_info, f, indent=2, ensure_ascii=False)

    logger.info("="*60)
    logger.info("精确坐标测量完成！")
    logger.info(f"最优坐标: ({optimal['x']}, {optimal['y']}) {optimal['width']}x{optimal['height']}")
    logger.info("="*60)

if __name__ == "__main__":
    main()