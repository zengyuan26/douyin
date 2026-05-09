"""
搜索触发决策器

判断何时触发搜索增强
"""

import logging
from typing import Optional

from services.search.config import SearchConfig

logger = logging.getLogger(__name__)


class SearchTriggerDecider:
    """
    搜索触发决策器

    根据多种因素判断是否触发搜索增强
    """

    def __init__(self, config: Optional[SearchConfig] = None):
        """
        初始化决策器

        Args:
            config: 搜索配置
        """
        self.config = config or SearchConfig()

    def should_search(
        self,
        topic: str,
        topic_type: str = "",
        duration: int = 60,
        style: str = "",
        force: bool = False,
    ) -> bool:
        """
        判断是否应该触发搜索

        Args:
            topic: 选题主题
            topic_type: 话题类型
            duration: 视频时长（秒）
            style: 风格要求
            force: 强制触发（忽略条件）

        Returns:
            是否应该触发搜索
        """
        # 1. 检查总开关
        if not self.config.enabled:
            logger.debug("搜索功能未启用")
            return False

        # 2. 强制触发
        if force:
            logger.info(f"强制触发搜索: topic={topic}")
            return True

        # 3. 时长判断
        if duration < self.config.min_duration_for_search:
            logger.debug(f"视频时长{duration}秒 < {self.config.min_duration_for_search}秒，跳过")
            return False

        # 4. 话题类型判断
        if self._should_skip_topic_type(topic_type, duration):
            logger.debug(f"话题类型{topic_type}不触发搜索")
            return False

        # 5. 主题关键词判断
        if self._should_skip_topic(topic):
            logger.debug(f"主题过于简单，跳过搜索")
            return False

        return True

    def _should_skip_topic_type(self, topic_type: str, duration: int) -> bool:
        """
        判断话题类型是否应该跳过搜索

        Args:
            topic_type: 话题类型
            duration: 视频时长

        Returns:
            是否跳过
        """
        # 不搜索的类型
        no_search_types = ["情感共鸣", "简单分享", "日常记录"]

        if topic_type in no_search_types:
            return True

        # 短时长情感类不搜索
        if topic_type == "情感共鸣" and duration < 90:
            return True

        return False

    def _should_skip_topic(self, topic: str) -> bool:
        """
        判断主题是否过于简单

        Args:
            topic: 选题主题

        Returns:
            是否跳过
        """
        # 纯情感词/日常词（这些不需要引用）
        skip_keywords = [
            "开心", "难过", "想你了", "晚安", "早安",
            "今天", "明天", "周末", "放假", "累", "困",
            "饿", "热", "冷", "忙", "烦", "爽", "耶",
            "唉", "哦", "嗯", "好", "差", "棒"
        ]

        # 纯情感/日常词直接跳过（不区分长度）
        if topic in skip_keywords:
            return True

        return False

    def get_search_hint(
        self,
        topic: str,
        topic_type: str = "",
    ) -> Optional[str]:
        """
        获取搜索提示

        当不适合搜索时，给出原因提示

        Args:
            topic: 选题主题
            topic_type: 话题类型

        Returns:
            提示信息或 None
        """
        if not self.config.enabled:
            return "搜索功能未启用"

        # 纯情感词
        skip_keywords = ["开心", "难过", "晚安", "早安", "累", "困", "饿"]
        if topic in skip_keywords:
            return "情感类话题无需引用资料"

        if topic_type in ["情感共鸣", "简单分享"]:
            return "情感类内容不适合添加引用"

        return None
