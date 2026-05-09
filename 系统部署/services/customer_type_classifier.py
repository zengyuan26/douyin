#!/usr/bin/env python3
"""
三类客户分类服务

功能：
1. 识别本地居民/返乡人/在外本地人三类客户群体
2. 为画像补充客户类型相关信息
3. 按客户类型分组画像

基于 Skill 文档 geo-seo 的三类核心客户群体模型：
| 人群 | 画像 | 消费场景 | 核心需求 | 内容方向 |
|------|------|----------|----------|----------|
| 本地居民 | 本地常住人口 | 自家消费、到店购买 | 实惠、方便、新鲜 | 性价比、便利性 |
| 返乡人 | 春节从外地返乡 | 送礼、带特产回城 | 品质、包装、便携 | 送礼攻略、品质推荐 |
| 在外本地人 | 在外地工作的本地人 | 思念家乡味、复购 | 正宗、情怀、邮寄 | 乡愁内容、品牌故事 |
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.portrait_generator import Portrait


@dataclass
class CustomerTypeProfile:
    """三类客户群体画像"""
    customer_type: str               # 本地居民/返乡人/在外本地人
    consumption_scenario: str        # 消费场景
    core_needs: List[str]           # 核心需求
    content_direction: List[str]     # 内容方向
    typical_pain_points: List[str]  # 典型痛点
    typical_barriers: List[str]      # 典型顾虑
    search_keywords_type: List[str] # 典型搜索词类型


# 三类客户定义
CUSTOMER_TYPE_PROFILES = {
    '本地居民': CustomerTypeProfile(
        customer_type='本地居民',
        consumption_scenario='自家消费、到店购买',
        core_needs=['实惠', '方便', '新鲜', '性价比', '便利性'],
        content_direction=['性价比评测', '便利性推荐', '新鲜度对比', '选购指南'],
        typical_pain_points=[
            '价格太贵不划算',
            '不够新鲜',
            '购买不方便',
            '不知道哪家好',
            '品质不稳定',
        ],
        typical_barriers=[
            '价格顾虑',
            '品质担忧',
            '便利性不足',
            '选择困难',
        ],
        search_keywords_type=[
            '哪家便宜',
            '哪里有卖',
            '怎么选',
            '好不好',
        ],
    ),
    '返乡人': CustomerTypeProfile(
        customer_type='返乡人',
        consumption_scenario='送礼、带特产回城',
        core_needs=['品质', '包装', '便携', '面子', '档次'],
        content_direction=['送礼攻略', '品质推荐', '包装评测', '便携指南', '品牌推荐'],
        typical_pain_points=[
            '不知道带什么回去',
            '包装不够好看',
            '不方便携带',
            '品质参差不齐',
            '不知道去哪买正宗',
        ],
        typical_barriers=[
            '包装顾虑',
            '便携性顾虑',
            '品质担忧',
            '选择困难',
        ],
        search_keywords_type=[
            '送礼送什么',
            '带什么回家',
            '包装好看',
            '哪里买正宗',
        ],
    ),
    '在外本地人': CustomerTypeProfile(
        customer_type='在外本地人',
        consumption_scenario='思念家乡味、复购、邮寄',
        core_needs=['正宗', '情怀', '邮寄', '家乡味', '回忆'],
        content_direction=['乡愁内容', '品牌故事', '复购攻略', '邮寄指南', '正宗对比'],
        typical_pain_points=[
            '在外地买不到正宗口味',
            '邮寄不方便',
            '怀念家乡味道',
            '不知道哪里能买到',
            '品质不稳定',
        ],
        typical_barriers=[
            '正宗性担忧',
            '邮寄便利性',
            '价格偏高',
            '品质不确定',
        ],
        search_keywords_type=[
            '哪里买正宗',
            '可以邮寄吗',
            '怀念',
            '家乡味',
        ],
    ),
}


class CustomerTypeClassifier:
    """
    三类客户分类器

    根据画像特征自动识别：
    - 本地居民：本地常住人口，自家消费
    - 返乡人：春节从外地返乡，送礼带特产
    - 在外本地人：在外地工作，思念家乡味
    """

    # 分类关键词映射
    KEYWORD_MAPPING = {
        '返乡人': [
            '送礼', '带回', '回城', '春节', '过年', '父母', '长辈', '老家',
            '家乡', '特产', '探望', '团圆', '假期', '休假', '回家',
        ],
        '在外本地人': [
            '在外', '外地', '工作', '想念', '家乡', '邮寄', '寄', '快递',
            '正宗', '怀念', '复购', '思念', '漂泊', '打拼', '异乡',
            '小时候', '回忆', '小时候的味道', '小时候的味道',
        ],
        '本地居民': [
            '自家', '自己吃', '家庭', '家里', '平时', '日常', '常吃',
            '楼下', '附近', '菜市场', '超市', '实惠', '方便',
        ],
    }

    def __init__(self):
        """初始化分类器"""
        pass

    def classify_portrait(
        self,
        portrait: Dict[str, Any],
    ) -> str:
        """
        根据画像特征判断客户类型

        Args:
            portrait: 画像字典

        Returns:
            客户类型: 本地居民/返乡人/在外本地人
        """
        # 收集所有文本特征
        text_features = self._collect_text_features(portrait)

        # 计算每种类型的匹配度
        scores = {}
        for customer_type, keywords in self.KEYWORD_MAPPING.items():
            score = sum(1 for kw in keywords if kw in text_features)
            scores[customer_type] = score

        # 返回得分最高的类型
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        else:
            return '本地居民'  # 默认为本地居民

    def _collect_text_features(self, portrait: Dict[str, Any]) -> str:
        """收集画像的文本特征"""
        features = []

        # identity
        features.append(portrait.get('identity', ''))

        # identity_description
        features.append(portrait.get('identity_description', ''))

        # pain_points
        pain_points = portrait.get('pain_points', [])
        if isinstance(pain_points, list):
            features.extend(pain_points)
        else:
            features.append(str(pain_points))

        # barriers
        barriers = portrait.get('barriers', [])
        if isinstance(barriers, list):
            features.extend(barriers)
        else:
            features.append(str(barriers))

        # search_keywords
        search_keywords = portrait.get('search_keywords', [])
        if isinstance(search_keywords, list):
            features.extend(search_keywords)
        else:
            features.append(str(search_keywords))

        # portrait_summary
        features.append(portrait.get('portrait_summary', ''))

        # 合并为文本
        return ' '.join(features).lower()

    def enrich_portrait_with_customer_type(
        self,
        portrait: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        为画像补充三类客户分类信息

        Args:
            portrait: 画像字典

        Returns:
            增强后的画像字典
        """
        customer_type = self.classify_portrait(portrait)
        profile = CUSTOMER_TYPE_PROFILES.get(customer_type)

        if profile:
            portrait['customer_type'] = customer_type
            portrait['customer_subtype'] = profile.consumption_scenario
            portrait['customer_core_needs'] = profile.core_needs
            portrait['customer_content_direction'] = profile.content_direction
            portrait['customer_typical_pain_points'] = profile.typical_pain_points
            portrait['customer_typical_barriers'] = profile.typical_barriers

        return portrait

    def enrich_portraits(
        self,
        portraits: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        批量为画像补充客户类型信息

        Args:
            portraits: 画像列表

        Returns:
            增强后的画像列表
        """
        return [self.enrich_portrait_with_customer_type(p) for p in portraits]


def group_portraits_by_customer_type(
    portraits: List[Any],
) -> Dict[str, List[Any]]:
    """
    按三类客户分组画像

    Args:
        portraits: Portrait对象或字典列表

    Returns:
        {
            '本地居民': [portrait1, portrait2, ...],
            '返乡人': [portrait3, portrait4, ...],
            '在外本地人': [portrait5, portrait6, ...],
            '未分类': [...],
        }
    """
    grouped = {
        '本地居民': [],
        '返乡人': [],
        '在外本地人': [],
        '未分类': [],
    }

    for portrait in portraits:
        # 支持 Portrait 对象或字典
        if hasattr(portrait, 'customer_type'):
            customer_type = portrait.customer_type
        elif isinstance(portrait, dict):
            customer_type = portrait.get('customer_type', '')
        else:
            customer_type = ''

        # 映射到分组
        if customer_type in grouped:
            grouped[customer_type].append(portrait)
        else:
            grouped['未分类'].append(portrait)

    # 清理空分组
    return {k: v for k, v in grouped.items() if v}


# 全局分类器单例
_classifier = None


def get_customer_type_classifier() -> CustomerTypeClassifier:
    """获取全局分类器单例"""
    global _classifier
    if _classifier is None:
        _classifier = CustomerTypeClassifier()
    return _classifier
