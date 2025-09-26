#!/usr/bin/env python3
"""
Gemini API Token Manager
用于管理Google Vertex AI访问令牌
"""

import requests
import time
import logging
from typing import Optional

class TokenManager:
    """访问令牌管理器"""

    def __init__(self, token_endpoint: str):
        self.token_endpoint = token_endpoint
        self.access_token = None
        self.token_expiry = 0
        self.logger = logging.getLogger(__name__)

    def get_access_token(self) -> Optional[str]:
        """获取有效的访问令牌"""
        # 如果令牌还没过期，直接返回
        current_time = time.time()
        if self.access_token and current_time < self.token_expiry:
            return self.access_token

        # 获取新令牌
        return self._refresh_token()

    def _refresh_token(self) -> Optional[str]:
        """刷新访问令牌"""
        try:
            self.logger.info("正在获取新的访问令牌...")

            response = requests.get(self.token_endpoint, timeout=10)

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')

                # 设置过期时间（提前5分钟过期以确保安全）
                expires_in = token_data.get('expires_in', 3600)  # 默认1小时
                self.token_expiry = time.time() + expires_in - 300

                self.logger.info(f"成功获取访问令牌，过期时间: {expires_in}秒")
                return self.access_token
            else:
                self.logger.error(f"获取令牌失败: HTTP {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"获取访问令牌异常: {e}")
            return None

    def is_token_valid(self) -> bool:
        """检查令牌是否有效"""
        return (self.access_token is not None and
                time.time() < self.token_expiry)