#!/usr/bin/env python3
"""
最终版本：使用Vertex AI Gemini检测字幕区域并用LAMA算法去除的完整测试脚本
基于提供的API调用方式实现
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

# 导入项目模块
from backend.inpaint.lama_inpaint import LamaInpaint
from backend import config
from updated_token_manager import TokenManager
from updated_gemini_client import GeminiClient

class VertexAISubtitleRemover:
    """基于Vertex AI Gemini检测和LAMA修复的字幕去除器"""

    def __init__(self, token_api_url: str = "http://api-ladder.ymt.io:8088/rpc/vertexai/accesstoken"):
        """
        初始化去除器

        Args:
            token_api_url: Token API的URL地址
        """
        self.device = config.device
        self.lama_model = None

        # 初始化Gemini组件
        logger.info("初始化Vertex AI Gemini组件...")
        self.token_manager = TokenManager(token_api_url)
        self.gemini_client = GeminiClient(self.token_manager)

        logger.info("Vertex AI字幕去除器初始化完成")

    def load_lama_model(self):
        """加载LAMA模型"""
        if self.lama_model is None:
            logger.info("正在加载LAMA模型...")
            try:
                self.lama_model = LamaInpaint(device=self.device)
                logger.info("LAMA模型加载完成")
            except Exception as e:
                logger.error(f"LAMA模型加载失败: {e}")
                raise

    def detect_subtitles(self, image_path: str):
        """使用Vertex AI Gemini检测字幕区域"""
        logger.info("开始使用Vertex AI Gemini检测字幕区域...")

        try:
            # 检查令牌状态
            token_info = self.token_manager.get_token_info()
            logger.info(f"令牌状态: {token_info}")

            # 调用Gemini分析
            result = self.gemini_client.analyze_image_subtitles(image_path)

            if result and result.get('has_subtitles', False):
                regions = result.get('regions', [])
                logger.info(f"Vertex AI Gemini检测到 {len(regions)} 个字幕区域")
                return result
            else:
                logger.info("Vertex AI Gemini未检测到字幕区域")
                return None

        except Exception as e:
            logger.error(f"字幕检测失败: {e}")
            return None

    def create_mask_from_gemini_regions(self, image_shape: tuple, gemini_result: dict) -> np.ndarray:
        """根据Gemini检测结果创建掩码"""
        height, width = image_shape[:2]
        mask = np.zeros((height, width), dtype=np.uint8)

        regions = gemini_result.get('regions', [])
        expansion = config.SUBTITLE_AREA_DEVIATION_PIXEL

        for region in regions:
            x = region.get('x', 0)
            y = region.get('y', 0)
            w = region.get('width', 0)
            h = region.get('height', 0)

            # 扩展区域以确保完全覆盖字幕
            x = max(0, x - expansion)
            y = max(0, y - expansion)
            w = min(width - x, w + 2 * expansion)
            h = min(height - y, h + 2 * expansion)

            # 填充掩码
            mask[y:y+h, x:x+w] = 255
            logger.info(f"掩码区域: ({x}, {y}) {w}x{h}")

        return mask

    def visualize_detection(self, image_path: str, gemini_result: dict, output_path: str):
        """可视化Gemini检测结果"""
        # 读取原图
        image = cv2.imread(image_path)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        draw = ImageDraw.Draw(pil_image)

        regions = gemini_result.get('regions', [])

        # 尝试加载字体，如果失败则使用默认字体
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
                draw.text((x, content_y), text_content[:20], fill='blue', font=font)

        # 保存可视化结果
        pil_image.save(output_path)
        logger.info(f"检测可视化结果已保存: {output_path}")

    def remove_subtitles(self, image_path: str, gemini_result: dict, output_path: str):
        """使用LAMA算法去除字幕"""
        self.load_lama_model()

        # 读取原图
        image = cv2.imread(image_path)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 根据Gemini结果创建掩码
        mask = self.create_mask_from_gemini_regions(image.shape, gemini_result)

        # 保存掩码用于调试
        mask_path = output_path.replace('.jpg', '_mask.jpg')
        cv2.imwrite(mask_path, mask)
        logger.info(f"掩码已保存: {mask_path}")

        # 使用LAMA进行修复
        logger.info("正在使用LAMA算法去除字幕...")
        result = self.lama_model(image_rgb, mask)

        # 转换回BGR并保存
        result_bgr = cv2.cvtColor(result, cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, result_bgr)
        logger.info(f"去字幕结果已保存: {output_path}")

        return result_bgr

    def process_image(self, image_path: str, output_dir: str = './images'):
        """处理单张图片的完整流程"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        base_name = os.path.splitext(os.path.basename(image_path))[0]

        logger.info(f"开始处理图片: {image_path}")

        # 1. 使用Vertex AI Gemini检测字幕区域
        logger.info("步骤1: 使用Vertex AI Gemini检测字幕区域")
        gemini_result = self.detect_subtitles(image_path)

        if not gemini_result or not gemini_result.get('has_subtitles', False):
            logger.warning("未检测到字幕，处理结束")
            return

        # 2. 可视化检测结果
        logger.info("步骤2: 可视化检测结果")
        detection_output = os.path.join(output_dir, f"{base_name}_vertex_ai_detection.jpg")
        self.visualize_detection(image_path, gemini_result, detection_output)

        # 3. 使用LAMA去除字幕
        logger.info("步骤3: 使用LAMA去除字幕")
        removal_output = os.path.join(output_dir, f"{base_name}_vertex_ai_removed.jpg")
        self.remove_subtitles(image_path, gemini_result, removal_output)

        # 4. 输出结果总结
        logger.info("\n" + "="*60)
        logger.info("Vertex AI Gemini + LAMA 字幕去除处理完成")
        logger.info("="*60)
        logger.info(f"原图: {image_path}")
        logger.info(f"Vertex AI检测可视化: {detection_output}")
        logger.info(f"LAMA去字幕结果: {removal_output}")

        regions = gemini_result.get('regions', [])
        logger.info(f"检测到的字幕区域数量: {len(regions)}")

        for i, region in enumerate(regions):
            logger.info(f"区域 {i+1}:")
            logger.info(f"  位置: ({region.get('x', 0)}, {region.get('y', 0)})")
            logger.info(f"  大小: {region.get('width', 0)}x{region.get('height', 0)}")
            logger.info(f"  置信度: {region.get('confidence', 0):.2f}")
            logger.info(f"  文本内容: {region.get('text_content', 'Unknown')}")

        logger.info("="*60)

def test_token_connection():
    """测试令牌连接"""
    try:
        logger.info("测试令牌API连接...")
        token_manager = TokenManager()
        token = token_manager.get_token()
        if token:
            logger.info("令牌获取成功！")
            logger.info(f"令牌信息: {token_manager.get_token_info()}")
            return True
        else:
            logger.error("令牌获取失败")
            return False
    except Exception as e:
        logger.error(f"令牌连接测试失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("="*60)
    logger.info("Vertex AI Gemini + LAMA 字幕去除测试")
    logger.info("="*60)

    # 1. 测试令牌连接
    if not test_token_connection():
        logger.error("令牌API连接失败，请检查网络连接和API服务状态")
        return

    # 2. 检查测试图片
    test_image = "/home/jiarui/software/video-subtitle-remover/images/test_image_with_subtitle.jpg"
    if not os.path.exists(test_image):
        logger.error(f"测试图片不存在: {test_image}")
        return

    try:
        # 3. 创建处理器
        logger.info("初始化Vertex AI字幕去除器...")
        remover = VertexAISubtitleRemover()

        # 4. 处理图片
        remover.process_image(test_image)

        logger.info("测试完成！")

    except Exception as e:
        logger.error(f"处理异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()