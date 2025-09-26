#!/usr/bin/env python3
"""
完整的Vertex AI Gemini字幕检测和LAMA去除测试
包含可视化检测结果功能
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

def visualize_detection(image_path: str, gemini_result: dict, output_path: str):
    """可视化Gemini检测结果"""
    # 读取原图
    image = cv2.imread(image_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(image_rgb)
    draw = ImageDraw.Draw(pil_image)

    regions = gemini_result.get('regions', [])

    # 尝试加载字体
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        font = ImageFont.load_default()

    for i, region in enumerate(regions):
        x = region.get('x', 0)
        y = region.get('y', 0)
        w = region.get('width', 0)
        h = region.get('height', 0)
        confidence = region.get('confidence', 0)
        text_content = region.get('text_content', 'Unknown')

        # 绘制检测框
        draw.rectangle([x, y, x+w, y+h], outline='red', width=3)

        # 绘制标签
        label = f"区域{i+1}: {confidence:.2f}"
        label_y = max(10, y - 25)
        draw.text((x, label_y), label, fill='red', font=font)

        # 绘制文本内容
        if text_content and text_content != 'Unknown':
            content_y = max(30, y - 5)
            # 限制文本长度以避免显示过长
            display_text = text_content[:15] + ('...' if len(text_content) > 15 else '')
            draw.text((x, content_y), display_text, fill='blue', font=font)

    # 保存可视化结果
    pil_image.save(output_path)
    logger.info(f"检测可视化已保存: {output_path}")

def create_mask_from_regions(image_shape: tuple, regions: list) -> np.ndarray:
    """根据检测区域创建掩码"""
    height, width = image_shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)

    expansion = 10  # 扩展像素，确保完全覆盖字幕

    for i, region in enumerate(regions):
        x = region.get('x', 0)
        y = region.get('y', 0)
        w = region.get('width', 0)
        h = region.get('height', 0)

        # 扩展区域
        x = max(0, x - expansion)
        y = max(0, y - expansion)
        w = min(width - x, w + 2 * expansion)
        h = min(height - y, h + 2 * expansion)

        # 填充掩码
        mask[y:y+h, x:x+w] = 255
        logger.info(f"掩码区域{i+1}: ({x}, {y}) {w}x{h}")

    return mask

def main():
    """主测试函数"""
    logger.info("="*60)
    logger.info("Vertex AI Gemini + LAMA 字幕去除完整测试")
    logger.info("="*60)

    # 1. 初始化组件
    logger.info("1. 初始化组件...")
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

    # 3. 使用Gemini检测字幕
    logger.info("2. 使用Vertex AI Gemini检测字幕...")
    try:
        detection_result = gemini_client.analyze_image_subtitles(test_image)

        if not detection_result:
            logger.error("✗ Gemini检测失败")
            return

        if not detection_result.get('has_subtitles', False):
            logger.warning("✗ 未检测到字幕")
            return

        regions = detection_result.get('regions', [])
        logger.info(f"✓ 检测到 {len(regions)} 个字幕区域")

        # 打印检测详情
        for i, region in enumerate(regions):
            logger.info(f"  区域{i+1}: ({region.get('x')}, {region.get('y')}) "
                       f"{region.get('width')}x{region.get('height')} "
                       f"置信度:{region.get('confidence'):.2f} "
                       f"内容:'{region.get('text_content')}'")

    except Exception as e:
        logger.error(f"✗ 字幕检测异常: {e}")
        return

    # 4. 创建输出目录
    output_dir = "./images"
    os.makedirs(output_dir, exist_ok=True)
    base_name = "test_complete_vertex_ai"

    # 5. 可视化检测结果
    logger.info("3. 生成检测可视化...")
    try:
        detection_viz_path = os.path.join(output_dir, f"{base_name}_detection.jpg")
        visualize_detection(test_image, detection_result, detection_viz_path)
        logger.info(f"✓ 检测可视化: {detection_viz_path}")
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

    # 7. 创建掩码并去除字幕
    logger.info("5. 创建掩码并执行去字幕...")
    try:
        # 读取原图
        image = cv2.imread(test_image)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 创建掩码
        mask = create_mask_from_regions(image.shape, regions)

        # 保存掩码
        mask_path = os.path.join(output_dir, f"{base_name}_mask.jpg")
        cv2.imwrite(mask_path, mask)
        logger.info(f"✓ 掩码已保存: {mask_path}")

        # 使用LAMA修复
        logger.info("正在使用LAMA算法修复...")
        result_image = lama_model(image_rgb, mask)

        # 保存结果
        result_path = os.path.join(output_dir, f"{base_name}_result.jpg")
        result_bgr = cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR)
        cv2.imwrite(result_path, result_bgr)
        logger.info(f"✓ 去字幕结果: {result_path}")

    except Exception as e:
        logger.error(f"✗ 去字幕处理失败: {e}")
        return

    # 8. 输出最终总结
    logger.info("="*60)
    logger.info("测试完成！生成的文件:")
    logger.info(f"  原图: {test_image}")
    logger.info(f"  检测可视化: {detection_viz_path}")
    logger.info(f"  处理掩码: {mask_path}")
    logger.info(f"  去字幕结果: {result_path}")
    logger.info("="*60)

    # 9. 保存检测结果到JSON
    json_path = os.path.join(output_dir, f"{base_name}_detection.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(detection_result, f, indent=2, ensure_ascii=False)
    logger.info(f"  检测数据: {json_path}")

    logger.info("Vertex AI Gemini + LAMA 测试成功完成！")

if __name__ == "__main__":
    main()