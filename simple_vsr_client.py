#!/usr/bin/env python3
"""
简化版Gemini+VSR去字幕客户端
移除了本地Gemini检测逻辑，完全依赖服务端处理
"""

import os
import sys
import json
import logging
import requests
import time
from datetime import datetime
from typing import Optional

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

class SimpleVSRProcessor:
    """简化版VSR处理客户端"""

    def __init__(self, vsr_base_url: str = "http://192.168.0.108:8002"):
        self.vsr_base_url = vsr_base_url
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)

    def check_vsr_health(self):
        """检查VSR服务状态"""
        try:
            self.logger.info(f"正在检查VSR服务健康状态: {self.vsr_base_url}")
            response = self.session.get(f"{self.vsr_base_url}/api/health", timeout=10)

            self.logger.info(f"HTTP状态码: {response.status_code}")

            if response.status_code == 200:
                try:
                    health_data = response.json()
                    self.logger.info(f"健康检查成功，服务版本: {health_data.get('version', 'Unknown')}")
                    return True, health_data
                except Exception as json_error:
                    error_msg = f"JSON解析失败: {json_error}"
                    self.logger.error(error_msg)
                    return False, error_msg
            else:
                error_msg = f"HTTP错误 {response.status_code}: {response.text}"
                self.logger.error(error_msg)
                return False, error_msg

        except requests.exceptions.ConnectionError as e:
            error_msg = f"连接错误: {e}"
            self.logger.error(error_msg)
            return False, error_msg
        except requests.exceptions.Timeout as e:
            error_msg = f"请求超时: {e}"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"未知错误: {e}"
            self.logger.error(error_msg)
            return False, error_msg

    def process_with_vsr(self, video_path: str, algorithm: str = "sttn", auto_detect_subtitles: bool = True):
        """使用VSR处理字幕去除（包含服务端字幕检测）"""
        self.logger.info(f"\n🚀 开始VSR字幕去除处理")
        self.logger.info("-" * 50)

        # 检查VSR服务
        is_healthy, health_info = self.check_vsr_health()
        if not is_healthy:
            self.logger.error(f"VSR服务不可用: {health_info}")
            return False, None

        self.logger.info(f"VSR服务状态正常")

        try:
            # 上传视频
            self.logger.info(f"上传视频: {os.path.basename(video_path)}")

            with open(video_path, 'rb') as f:
                files = {'file': (os.path.basename(video_path), f, 'video/mp4')}

                # 准备表单数据
                data = {
                    'algorithm': algorithm,
                    'auto_detect_subtitles': 'true' if auto_detect_subtitles else 'false'
                }

                response = self.session.post(
                    f"{self.vsr_base_url}/api/upload",
                    files=files,
                    data=data,
                    timeout=60
                )

                if response.status_code != 200:
                    self.logger.error(f"上传失败: {response.text}")
                    return False, None

                upload_result = response.json()
                task_id = upload_result['task_id']
                self.logger.info(f"上传成功，任务ID: {task_id}")

            # 开始处理
            self.logger.info("开始处理...")
            process_data = {
                'task_id': task_id,
                'start_immediately': 'true',
                'auto_detect_subtitles': 'true' if auto_detect_subtitles else 'false'
            }

            response = self.session.post(
                f"{self.vsr_base_url}/api/process",
                data=process_data,
                timeout=30
            )

            if response.status_code != 200:
                self.logger.error(f"开始处理失败: {response.text}")
                return False, None

            # 等待处理完成
            self.logger.info("等待处理完成...")

            while True:
                response = self.session.get(f"{self.vsr_base_url}/api/task/{task_id}", timeout=10)
                if response.status_code != 200:
                    self.logger.error(f"获取状态失败: {response.text}")
                    return False, None

                status_info = response.json()
                status = status_info['status']
                progress = status_info.get('progress', 0)

                self.logger.info(f"状态: {status}, 进度: {progress:.1f}%")

                if status == 'completed':
                    self.logger.info("✅ 处理完成!")

                    # 生成输出文件名
                    base_name = os.path.splitext(video_path)[0]
                    output_path = f"{base_name}_vsr_processed.mp4"

                    # 下载结果
                    self.logger.info(f"下载结果到: {output_path}")
                    response = self.session.get(f"{self.vsr_base_url}/api/download/{task_id}", timeout=300)

                    if response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            f.write(response.content)

                        # 文件大小对比
                        original_size = os.path.getsize(video_path)
                        processed_size = os.path.getsize(output_path)

                        self.logger.info(f"文件大小对比:")
                        self.logger.info(f"  原始文件: {original_size / 1024 / 1024:.2f} MB")
                        self.logger.info(f"  处理后: {processed_size / 1024 / 1024:.2f} MB")

                        return True, output_path
                    else:
                        self.logger.error(f"下载失败: {response.text}")
                        return False, None

                elif status == 'failed':
                    error_msg = status_info.get('error_message', '未知错误')
                    self.logger.error(f"❌ 处理失败: {error_msg}")
                    return False, None

                elif status in ['pending', 'processing', 'detecting']:
                    time.sleep(5)
                else:
                    self.logger.warning(f"未知状态: {status}")
                    time.sleep(5)

        except Exception as e:
            self.logger.error(f"VSR处理异常: {e}")
            return False, None

    def process_video(self, video_path: str, algorithm: str = "sttn", output_path: Optional[str] = None):
        """完整的视频去字幕流程"""
        if not os.path.exists(video_path):
            self.logger.error(f"视频文件不存在: {video_path}")
            return False, None

        self.logger.info("=" * 80)
        self.logger.info("🎬 VSR 字幕去除开始")
        self.logger.info("=" * 80)
        self.logger.info(f"输入视频: {video_path}")
        self.logger.info(f"文件大小: {os.path.getsize(video_path) / 1024 / 1024:.2f} MB")
        self.logger.info(f"使用算法: {algorithm}")

        start_time = datetime.now()

        try:
            # VSR处理（包含服务端字幕检测）
            success, result_path = self.process_with_vsr(video_path, algorithm, auto_detect_subtitles=True)

            # 处理完成
            processing_time = (datetime.now() - start_time).total_seconds()

            self.logger.info("\n" + "=" * 80)
            if success:
                self.logger.info("🎉 字幕去除成功完成！")
                self.logger.info(f"输出文件: {result_path}")
                self.logger.info(f"处理耗时: {processing_time:.1f}秒")

                # 如果指定了输出路径，移动文件
                if output_path and output_path != result_path:
                    import shutil
                    shutil.move(result_path, output_path)
                    self.logger.info(f"文件已移动到: {output_path}")
                    return True, output_path

                return True, result_path
            else:
                self.logger.info("❌ 字幕去除失败")
                self.logger.info(f"处理耗时: {processing_time:.1f}秒")
                return False, None

        except Exception as e:
            self.logger.error(f"处理异常: {e}")
            return False, None

        finally:
            self.logger.info("=" * 80)

def main():
    """主函数 - 命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(description="简化版VSR字幕去除工具")
    parser.add_argument("video_path", help="输入视频文件路径")
    parser.add_argument("-o", "--output", help="输出文件路径（可选）")
    parser.add_argument("-a", "--algorithm", default="sttn", choices=["sttn", "lama", "propainter"],
                       help="VSR算法选择 (默认: sttn)")
    parser.add_argument("--vsr-url", default="http://192.168.0.108:8002",
                       help="VSR服务地址 (默认: http://192.168.0.108:8002)")

    args = parser.parse_args()

    setup_logging()

    processor = SimpleVSRProcessor(args.vsr_url)
    success, output_path = processor.process_video(args.video_path, args.algorithm, args.output)

    if success:
        print(f"\n✅ 成功！输出文件: {output_path}")
        exit(0)
    else:
        print("\n❌ 处理失败")
        exit(1)

if __name__ == "__main__":
    main()