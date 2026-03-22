"""
公开内容生成平台 - 频率限制服务

功能：
1. IP 级别限制（防止恶意刷接口）
2. 邮箱级别限制（防止注册滥用）
3. 用户级别限制（生成频率控制）

使用内存存储，适用于单机部署
分布式部署时建议使用 Redis
"""

import time
from typing import Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta
import threading


class RateLimitConfig:
    """频率限制配置"""

    # IP 级别限制
    IP_REGISTER = {'limit': 10, 'window': 3600}        # 每小时最多注册10次
    IP_LOGIN = {'limit': 20, 'window': 3600}           # 每小时最多登录20次
    IP_GENERAL = {'limit': 60, 'window': 60}           # 每分钟最多60次请求

    # 邮箱级别限制
    EMAIL_VERIFY_REQUEST = {'limit': 5, 'window': 3600}  # 每小时最多请求验证5次
    EMAIL_REGISTER = {'limit': 3, 'window': 86400}       # 每天最多注册3个账号

    # 用户级别限制（生成）
    USER_GENERATE = {'limit': 5, 'window': 60}          # 每分钟最多生成5次

    # 滑动窗口配置
    WINDOW_TYPE = 'sliding'  # 'fixed' or 'sliding'


class RateLimitRecord:
    """单条限制记录"""

    def __init__(self, key: str, limit: int, window: int):
        self.key = key
        self.limit = limit
        self.window = window
        self.requests = []  # 请求时间戳列表
        self.lock = threading.Lock()

    def is_allowed(self) -> bool:
        """检查是否允许请求"""
        with self.lock:
            now = time.time()
            window_start = now - self.window

            # 清理过期记录
            self.requests = [t for t in self.requests if t > window_start]

            # 检查是否超限
            if len(self.requests) >= self.limit:
                return False

            # 记录本次请求
            self.requests.append(now)
            return True

    def get_remaining(self) -> int:
        """获取剩余请求次数"""
        with self.lock:
            now = time.time()
            window_start = now - self.window
            self.requests = [t for t in self.requests if t > window_start]
            return max(0, self.limit - len(self.requests))

    def get_reset_time(self) -> Optional[float]:
        """获取限制重置时间"""
        with self.lock:
            if not self.requests:
                return None
            now = time.time()
            oldest_in_window = [t for t in self.requests if t > now - self.window]
            if not oldest_in_window:
                return None
            return min(oldest_in_window) + self.window


class RateLimiter:
    """频率限制器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._records = defaultdict(dict)
        self._cleanup_lock = threading.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 3600  # 每小时清理一次过期记录

    def _get_record(self, category: str, key: str, limit: int, window: int) -> RateLimitRecord:
        """获取或创建限制记录"""
        if category not in self._records:
            self._records[category] = {}

        if key not in self._records[category]:
            self._records[category][key] = RateLimitRecord(key, limit, window)

        return self._records[category][key]

    def check(self, category: str, key: str, limit: int, window: int) -> Tuple[bool, dict]:
        """
        检查请求是否允许

        Args:
            category: 限制类别（如 'ip_register', 'email_verify'）
            key: 限制键（如 IP 地址、邮箱）
            limit: 限制次数
            window: 时间窗口（秒）

        Returns:
            (is_allowed, info_dict)
            info_dict: {
                'remaining': 剩余次数,
                'reset_at': 重置时间戳,
                'retry_after': 距离下次可请求的秒数
            }
        """
        # 定期清理过期记录
        self._maybe_cleanup()

        record = self._get_record(category, key, limit, window)
        is_allowed = record.is_allowed()
        remaining = record.get_remaining()
        reset_time = record.get_reset_time()

        info = {
            'remaining': remaining,
            'reset_at': reset_time,
            'retry_after': 0 if is_allowed else (reset_time - time.time()) if reset_time else window
        }

        return is_allowed, info

    def get_status(self, category: str, key: str, limit: int, window: int) -> dict:
        """获取限制状态（不计入请求）"""
        record = self._get_record(category, key, limit, window)
        remaining = record.get_remaining()
        reset_time = record.get_reset_time()

        return {
            'remaining': remaining,
            'reset_at': reset_time,
            'limit': limit,
            'window': window
        }

    def reset(self, category: str, key: str) -> bool:
        """重置指定限制"""
        if category in self._records and key in self._records[category]:
            del self._records[category][key]
            return True
        return False

    def reset_category(self, category: str) -> int:
        """重置整个类别"""
        if category in self._records:
            count = len(self._records[category])
            del self._records[category]
            return count
        return 0

    def _maybe_cleanup(self):
        """定期清理过期记录"""
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            with self._cleanup_lock:
                if now - self._last_cleanup > self._cleanup_interval:
                    self._cleanup_expired()
                    self._last_cleanup = now

    def _cleanup_expired(self):
        """清理过期记录"""
        for category in list(self._records.keys()):
            for key in list(self._records[category].keys()):
                record = self._records[category][key]
                # 如果记录已完全过期，删除
                reset_time = record.get_reset_time()
                if reset_time is None or time.time() > reset_time + 3600:
                    del self._records[category][key]

            # 如果类别为空，删除
            if not self._records[category]:
                del self._records[category]


# 全局实例
rate_limiter = RateLimiter()


# =============================================================================
# 便捷函数
# =============================================================================

def check_ip_register(ip: str) -> Tuple[bool, dict]:
    """检查 IP 注册频率"""
    return rate_limiter.check(
        'ip_register', ip,
        RateLimitConfig.IP_REGISTER['limit'],
        RateLimitConfig.IP_REGISTER['window']
    )


def check_ip_login(ip: str) -> Tuple[bool, dict]:
    """检查 IP 登录频率"""
    return rate_limiter.check(
        'ip_login', ip,
        RateLimitConfig.IP_LOGIN['limit'],
        RateLimitConfig.IP_LOGIN['window']
    )


def check_email_verify(email: str) -> Tuple[bool, dict]:
    """检查邮箱验证请求频率"""
    return rate_limiter.check(
        'email_verify', email,
        RateLimitConfig.EMAIL_VERIFY_REQUEST['limit'],
        RateLimitConfig.EMAIL_VERIFY_REQUEST['window']
    )


def check_user_generate(user_id: int) -> Tuple[bool, dict]:
    """检查用户生成频率"""
    return rate_limiter.check(
        'user_generate', str(user_id),
        RateLimitConfig.USER_GENERATE['limit'],
        RateLimitConfig.USER_GENERATE['window']
    )


def check_general(ip: str) -> Tuple[bool, dict]:
    """检查通用请求频率"""
    return rate_limiter.check(
        'general', ip,
        RateLimitConfig.IP_GENERAL['limit'],
        RateLimitConfig.IP_GENERAL['window']
    )


def get_client_ip(request) -> str:
    """获取客户端 IP"""
    # 优先从 X-Forwarded-For 获取（反向代理场景）
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()

    # 其次从 X-Real-IP 获取
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip

    # 最后使用 remote_addr
    return request.remote_addr or '127.0.0.1'


def rate_limit_response(info: dict, message: str = "请求过于频繁，请稍后重试"):
    """生成频率限制响应"""
    from flask import jsonify
    retry_after = int(info.get('retry_after', 60))
    response = jsonify({
        'success': False,
        'error': 'rate_limit_exceeded',
        'message': message,
        'retry_after': retry_after
    })
    response.headers['Retry-After'] = str(retry_after)
    response.headers['X-RateLimit-Remaining'] = str(info.get('remaining', 0))
    response.headers['X-RateLimit-Reset'] = str(int(info.get('reset_at', time.time() + 60)))
    return response
