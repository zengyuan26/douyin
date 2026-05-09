#!/usr/bin/env python3
"""
B端/C端分类服务

功能：
1. 识别B端(企业客户)和C端(家庭/个人客户)
2. 为画像补充B端C端相关信息
3. 按B端C端分组画像

基于 Skill 文档 geo-seo 的B端C端对比矩阵：
| 对比项 | B端(企业) | C端(家庭) |
|--------|-----------|-----------|
| 购买动机 | 经营需求、品牌展示 | 日常需求、生活必需 |
| 决策人 | 多人决策（老板+财务+采购） | 个人决策或家庭决策 |
| 核心痛点 | 报销、门槛、配送 | 品质、价格、服务 |
| 搜索特点 | 专业、长尾、具体 | 通俗、广泛、口语化 |
| 内容需求 | 解决方案、案例证明 | 使用指南、性价比 |
| 转化方式 | 私信+电话+面谈 | 私信+下单 |
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.portrait_generator import Portrait


@dataclass
class ClientTypeProfile:
    """B端/C端客户画像"""
    client_type: str                # B端(企业)/C端(家庭)
    decision_makers: List[str]      # 决策人
    core_needs: List[str]           # 核心需求
    conversion_cycle: str           # 转化周期
    keywords_type: List[str]        # 关键词类型
    content_type: List[str]         # 内容类型
    purchase_motive: str            # 购买动机
    search_characteristics: str     # 搜索特点
    typical_pain_points: List[str]  # 典型痛点
    typical_barriers: List[str]     # 典型顾虑


# B端C端定义
CLIENT_TYPE_PROFILES = {
    'B端': ClientTypeProfile(
        client_type='B端',
        decision_makers=['老板', '行政', '采购', '财务', '负责人', '经理'],
        core_needs=['性价比', '可报销', '门槛低', '服务好', '品牌展示', '稳定供应'],
        conversion_cycle='3-7天（较长）',
        keywords_type=['解决方案型', '价格型', '对比型', '专业型'],
        content_type=['解决方案', '案例证明', '企业服务', '合作案例', '报价方案'],
        purchase_motive='经营需求、品牌展示、招待客户、员工福利',
        search_characteristics='专业、长尾、具体、问题导向',
        typical_pain_points=[
            '报销流程复杂',
            '起订量门槛高',
            '配送不及时',
            '品牌形象不匹配',
        ],
        typical_barriers=[
            '价格不够优惠',
            '不能开票',
            '服务响应慢',
            '门槛太高',
        ],
    ),
    'C端': ClientTypeProfile(
        client_type='C端',
        decision_makers=['家庭主妇', '上班族', '老年人', '个人', '丈夫', '妻子'],
        core_needs=['品质保障', '价格实惠', '方便配送', '口感好', '新鲜'],
        conversion_cycle='当天或几分钟（短）',
        keywords_type=['品质型', '实用性', '口碑型', '性价比型'],
        content_type=['使用指南', '性价比', '口碑推荐', '选购攻略', '真实评测'],
        purchase_motive='日常需求、生活必需、家庭使用、馈赠亲友',
        search_characteristics='通俗、广泛、口语化、问题导向',
        typical_pain_points=[
            '价格太贵',
            '品质不稳定',
            '配送不方便',
            '不知道选哪个',
        ],
        typical_barriers=[
            '价格顾虑',
            '品质担忧',
            '服务不确定',
            '选择困难',
        ],
    ),
}


class ClientTypeClassifier:
    """
    B端C端分类器

    根据画像特征自动识别：
    - B端：企业购买，用于经营/招待/福利
    - C端：家庭/个人购买，用于日常使用
    """

    # B端关键词
    B_KEYWORDS = [
        '企业', '公司', '老板', '行政', '采购', '财务', '负责人', '经理',
        '员工', '福利', '招待', '送礼', '品牌展示', '团购', '批量', '定制',
        '单位', '机关', '酒店', '餐厅', '饭店', '宾馆', '会所',
        '开业', '年会', '活动', '会议', '培训', '团建',
        '商务', '业务', '经营', '采购', '供应', '合作',
    ]

    # C端关键词
    C_KEYWORDS = [
        '家庭', '个人', '自己', '孩子', '老公', '老婆', '父母', '老人',
        '日常', '自用', '平时', '送给朋友', '走亲戚', '串门',
        '家里', '家里用', '给孩子', '给父母', '给长辈',
        '自己吃', '家人', '一家', '老公孩子', '一家三口',
    ]

    def __init__(self):
        """初始化分类器"""
        pass

    def classify_portrait(
        self,
        portrait: Dict[str, Any],
    ) -> str:
        """
        根据画像特征判断B端/C端

        Args:
            portrait: 画像字典

        Returns:
            B端/C端
        """
        # 收集所有文本特征
        text_features = self._collect_text_features(portrait)

        # 计算B端匹配度
        b_score = sum(1 for kw in self.B_KEYWORDS if kw in text_features)

        # 计算C端匹配度
        c_score = sum(1 for kw in self.C_KEYWORDS if kw in text_features)

        # 决策
        if b_score > c_score:
            return 'B端'
        elif c_score > b_score:
            return 'C端'
        else:
            return 'C端'  # 默认为C端

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

        # portrait_summary
        features.append(portrait.get('portrait_summary', ''))

        # 合并为文本
        return ' '.join(features).lower()

    def enrich_portrait_with_client_type(
        self,
        portrait: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        为画像补充B端C端分类信息

        Args:
            portrait: 画像字典

        Returns:
            增强后的画像字典
        """
        client_type = self.classify_portrait(portrait)
        profile = CLIENT_TYPE_PROFILES.get(client_type)

        if profile:
            portrait['client_type'] = client_type
            portrait['decision_makers'] = profile.decision_makers
            portrait['core_needs'] = profile.core_needs
            portrait['conversion_cycle'] = profile.conversion_cycle
            portrait['keywords_type'] = profile.keywords_type
            portrait['content_type'] = profile.content_type
            portrait['purchase_motive'] = profile.purchase_motive
            portrait['search_characteristics'] = profile.search_characteristics
            portrait['client_typical_pain_points'] = profile.typical_pain_points
            portrait['client_typical_barriers'] = profile.typical_barriers

        return portrait

    def enrich_portraits(
        self,
        portraits: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        批量为画像补充B端C端信息

        Args:
            portraits: 画像列表

        Returns:
            增强后的画像列表
        """
        return [self.enrich_portrait_with_client_type(p) for p in portraits]


def group_portraits_by_client_type(
    portraits: List[Any],
) -> Dict[str, List[Any]]:
    """
    按B端/C端分组画像

    Args:
        portraits: Portrait对象或字典列表

    Returns:
        {
            'B端': [portrait1, portrait2, ...],
            'C端': [portrait3, portrait4, ...],
            '未分类': [...],
        }
    """
    grouped = {
        'B端': [],
        'C端': [],
        '未分类': [],
    }

    for portrait in portraits:
        # 支持 Portrait 对象或字典
        if hasattr(portrait, 'client_type'):
            client_type = portrait.client_type
        elif isinstance(portrait, dict):
            client_type = portrait.get('client_type', '')
        else:
            client_type = ''

        # 映射到分组
        if client_type in grouped:
            grouped[client_type].append(portrait)
        else:
            grouped['未分类'].append(portrait)

    # 清理空分组
    return {k: v for k, v in grouped.items() if v}


# 全局分类器单例
_classifier = None


def get_client_type_classifier() -> ClientTypeClassifier:
    """获取全局分类器单例"""
    global _classifier
    if _classifier is None:
        _classifier = ClientTypeClassifier()
    return _classifier
