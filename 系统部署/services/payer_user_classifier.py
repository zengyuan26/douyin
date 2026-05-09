#!/usr/bin/env python3
"""
付费人/使用人分类服务

功能：
1. 区分付费人和使用人
2. 识别付费人和使用人分离的场景
3. 为画像补充付费人/使用人信息

基于 Skill 文档 geo-seo 的付费人vs使用人对比：
| 角色 | 定义 | 关注点 | 示例 |
|------|------|--------|------|
| 付费人 | 出钱购买的人 | 价值、成本、效果 | 老板、老公、父母 |
| 使用人 | 实际使用的人 | 体验、品质、方便 | 员工、孩子、老婆 |

典型分离场景：
- 桶装水企业采购：付费人(行政)关心价格，使用人(员工)关心水质
- 定制水送礼：付费人(送礼人)关心面子，使用人(收礼人)可能不使用
- 婴儿用水：付费人(父母)关心安全，价格，使用人(婴儿)关心口感、营养
- 员工福利：付费人(企业/老板)关心成本，使用人(员工)关心品质、喜好
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.portrait_generator import Portrait


@dataclass
class PayerUserProfile:
    """付费人/使用人分离画像"""
    payer_role: str                 # 付费人角色
    payer_concerns: List[str]       # 付费人关注点
    user_role: str                  # 使用人角色
    user_concerns: List[str]        # 使用人关注点
    separation_cases: List[str]     # 分离典型场景
    is_separated: bool              # 是否分离


# 付费人/使用人分离模式定义
PAYER_USER_PROFILES = {
    '企业采购': PayerUserProfile(
        payer_role='企业老板/行政/采购',
        payer_concerns=['价格', '成本', '品牌', '可报销', '门槛', '配送', '服务'],
        user_role='企业员工',
        user_concerns=['水质', '口感', '方便', '健康', '温度'],
        separation_cases=['桶装水企业采购', '定制水企业招待', '员工饮用水'],
        is_separated=True,
    ),
    '家庭送礼': PayerUserProfile(
        payer_role='送礼人',
        payer_concerns=['面子', '档次', '包装', '价格', '体面', '好看'],
        user_role='收礼人',
        user_concerns=['品质', '口感', '实用性', '品牌'],
        separation_cases=['定制水送礼', '礼盒套装', '节日礼品'],
        is_separated=True,
    ),
    '家庭为孩子': PayerUserProfile(
        payer_role='父母',
        payer_concerns=['安全', '价格', '营养', '健康', '品质'],
        user_role='孩子',
        user_concerns=['口感', '味道', '颜色', '趣味性'],
        separation_cases=['婴儿用水', '儿童食品', '学生用品'],
        is_separated=True,
    ),
    '家庭自用': PayerUserProfile(
        payer_role='家庭决策人',
        payer_concerns=['价格', '性价比', '品质', '健康', '方便'],
        user_role='家庭成员',
        user_concerns=['口感', '方便', '健康', '新鲜'],
        separation_cases=['日常饮用', '家庭桶装水', '家常菜食材'],
        is_separated=False,
    ),
}


class PayerUserClassifier:
    """
    付费人/使用人分类器

    根据画像特征自动识别：
    - 付费人和使用人是否分离
    - 分离场景下的角色定位
    - 各方关注点
    """

    # 分离场景关键词
    SEPARATION_KEYWORDS = {
        '企业采购': ['企业', '员工', '老板', '行政', '采购', '福利', '招待'],
        '家庭送礼': ['送礼', '收礼', '礼品', '礼盒', '节日', '探望', '长辈'],
        '家庭为孩子': ['孩子', '婴儿', '儿童', '宝宝', '学生', '小孩', '小孩'],
    }

    # 付费人关注点
    PAYER_CONCERNS = {
        '成本价值': ['价格', '成本', '性价比', '贵不贵', '值不值', '优惠', '打折'],
        '功能效果': ['效果', '有用吗', '管用吗', '作用', '功效'],
        '便利性': ['方便', '快捷', '省事', '简单', '配送', '送货'],
        '形象面子': ['面子', '档次', '好看', '体面', '品牌', '有面子'],
        '安全合规': ['安全', '正规', '正规', '靠谱', '放心', '合规'],
    }

    # 使用人关注点
    USER_CONCERNS = {
        '体验口感': ['口感', '味道', '好不好吃', '香不香', '鲜不鲜'],
        '品质质量': ['品质', '质量', '正宗', '地道', '好不好'],
        '方便使用': ['方便', '简单', '容易', '省事', '快捷'],
        '健康安全': ['健康', '营养', '安全', '卫生', '干净'],
        '情感诉求': ['怀念', '回忆', '小时候', '家乡', '思念'],
    }

    def __init__(self):
        """初始化分类器"""
        pass

    def classify_payer_user(
        self,
        portrait: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        区分付费人和使用人

        Args:
            portrait: 画像字典

        Returns:
            {
                'payer_role': '付费人角色',
                'payer_concerns': ['关注点1', ...],
                'user_role': '使用人角色',
                'user_concerns': ['关注点1', ...],
                'is_separated': True/False,
                'separation_type': '企业采购/家庭送礼/...',
            }
        """
        # 收集所有文本特征
        text_features = self._collect_text_features(portrait)

        # 判断分离类型
        separation_type = self._detect_separation_type(text_features)

        # 获取分离模式
        profile = PAYER_USER_PROFILES.get(separation_type)

        # 分析付费人关注点
        payer_concerns = self._extract_concerns(text_features, self.PAYER_CONCERNS)

        # 分析使用人关注点
        user_concerns = self._extract_concerns(text_features, self.USER_CONCERNS)

        return {
            'payer_role': profile.payer_role if profile else '购买决策人',
            'payer_concerns': payer_concerns or (profile.payer_concerns if profile else []),
            'user_role': profile.user_role if profile else '使用者',
            'user_concerns': user_concerns or (profile.user_concerns if profile else []),
            'is_separated': profile.is_separated if profile else False,
            'separation_type': separation_type,
        }

    def _detect_separation_type(self, text_features: str) -> str:
        """检测分离类型"""
        scores = {}
        for sep_type, keywords in self.SEPARATION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_features)
            scores[sep_type] = score

        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        else:
            return '家庭自用'

    def _extract_concerns(
        self,
        text_features: str,
        concern_mapping: Dict[str, List[str]],
    ) -> List[str]:
        """提取关注点"""
        found_concerns = []
        for concern_type, keywords in concern_mapping.items():
            if any(kw in text_features for kw in keywords):
                found_concerns.append(concern_type)
        return found_concerns

    def _collect_text_features(self, portrait: Dict[str, Any]) -> str:
        """收集画像的文本特征"""
        features = []

        # identity
        features.append(portrait.get('identity', ''))

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

    def enrich_portrait_with_payer_user(
        self,
        portrait: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        为画像补充付费人/使用人信息

        Args:
            portrait: 画像字典

        Returns:
            增强后的画像字典
        """
        payer_user_info = self.classify_payer_user(portrait)

        portrait['payer_info'] = {
            'role': payer_user_info['payer_role'],
            'concerns': payer_user_info['payer_concerns'],
        }
        portrait['user_info'] = {
            'role': payer_user_info['user_role'],
            'concerns': payer_user_info['user_concerns'],
        }
        portrait['is_payer_user_separated'] = payer_user_info['is_separated']
        portrait['payer_user_separation_type'] = payer_user_info['separation_type']

        return portrait

    def enrich_portraits(
        self,
        portraits: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        批量为画像补充付费人/使用人信息

        Args:
            portraits: 画像列表

        Returns:
            增强后的画像列表
        """
        return [self.enrich_portrait_with_payer_user(p) for p in portraits]


def group_portraits_by_payer_user_separation(
    portraits: List[Any],
) -> Dict[str, List[Any]]:
    """
    按付费人/使用人是否分离分组画像

    Args:
        portraits: Portrait对象或字典列表

    Returns:
        {
            '分离': [portrait1, portrait2, ...],
            '未分离': [portrait3, portrait4, ...],
            '未分类': [...],
        }
    """
    grouped = {
        '分离': [],
        '未分离': [],
        '未分类': [],
    }

    for portrait in portraits:
        # 支持 Portrait 对象或字典
        if hasattr(portrait, 'is_payer_user_separated'):
            is_separated = portrait.is_payer_user_separated
        elif isinstance(portrait, dict):
            is_separated = portrait.get('is_payer_user_separated', None)
        else:
            is_separated = None

        # 映射到分组
        if is_separated is True:
            grouped['分离'].append(portrait)
        elif is_separated is False:
            grouped['未分离'].append(portrait)
        else:
            grouped['未分类'].append(portrait)

    # 清理空分组
    return {k: v for k, v in grouped.items() if v}


# 全局分类器单例
_classifier = None


def get_payer_user_classifier() -> PayerUserClassifier:
    """获取全局分类器单例"""
    global _classifier
    if _classifier is None:
        _classifier = PayerUserClassifier()
    return _classifier
