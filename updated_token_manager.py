"""
令牌管理模块 - 基于提供的API示例
"""

import requests
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

class TokenError(Exception):
    """令牌相关异常"""
    pass

class TokenManager:
    """动态令牌管理器"""

    def __init__(self, token_api_url: str = "http://api-ladder.ymt.io:8088/rpc/vertexai/accesstoken",
                 token_duration: int = 3600, refresh_buffer: int = 300):
        self.token_api_url = token_api_url
        self.token_duration = token_duration  # 令牌有效期（秒）
        self.refresh_buffer = refresh_buffer  # 提前刷新时间（秒）

        self.current_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None

        logger.info(f"初始化TokenManager，API URL: {token_api_url}")

    def get_token(self) -> str:
        """获取有效的访问令牌"""
        if self._is_token_expired():
            logger.info("令牌已过期或不存在，开始刷新")
            self._refresh_token()
        return self.current_token

    def _is_token_expired(self) -> bool:
        """检查令牌是否过期"""
        if not self.current_token or not self.token_expiry:
            return True
        return datetime.now() >= self.token_expiry

    def _refresh_token(self, max_retries: int = 3):
        """刷新访问令牌"""
        for attempt in range(max_retries):
            try:
                logger.info(f"正在获取访问令牌 (尝试 {attempt + 1}/{max_retries})")

                response = requests.post(
                    self.token_api_url,
                    timeout=120,
                    headers={'Content-Type': 'application/json'}
                )
                response.raise_for_status()

                # 获取令牌并设置过期时间
                token = response.text.strip()
                if not token:
                    raise TokenError("获取到空的令牌")

                self.current_token = token
                # 提前刷新以避免在使用时过期
                self.token_expiry = datetime.now() + timedelta(
                    seconds=self.token_duration - self.refresh_buffer
                )

                logger.info(f"令牌获取成功，有效期至: {self.token_expiry}")
                return

            except requests.RequestException as e:
                logger.warning(f"获取令牌失败 (尝试 {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    # 指数退避重试
                    wait_time = min(2 ** attempt, 60)
                    logger.info(f"等待 {wait_time} 秒后重试")
                    time.sleep(wait_time)
                else:
                    raise TokenError(f"获取访问令牌失败，已重试 {max_retries} 次: {e}")

    def force_refresh(self):
        """强制刷新令牌"""
        logger.info("强制刷新令牌")
        self.current_token = None
        self.token_expiry = None
        self.get_token()

    def get_token_info(self) -> dict:
        """获取令牌信息"""
        return {
            'has_token': self.current_token is not None,
            'expiry_time': self.token_expiry.isoformat() if self.token_expiry else None,
            'is_expired': self._is_token_expired(),
            'time_to_expiry': (self.token_expiry - datetime.now()).total_seconds()
                             if self.token_expiry else None
        }