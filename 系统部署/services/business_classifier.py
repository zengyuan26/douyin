"""
业务特征识别服务

基于方案设计的信任来源决策树：
1. 是否有强品牌背书？ → 是 → 机构型
2. 是否高认知门槛业务？ → 是 → 知识型
3. 是否有故事/冲突可讲？ → 是 → 人设价值观型
4. 否则 → 产品型

输出：
- 信任来源类型
- 推荐选题类型
- 建议的均衡器配置
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TrustSourceType(Enum):
    """信任来源类型"""
    KNOWLEDGE = "knowledge"          # 知识型：专业内容建立信任
    PERSONA = "persona"             # 人设型：人设认同建立信任
    INSTITUTION = "institution"     # 机构型：品牌背书建立信任
    PRODUCT = "product"             # 产品型：产品本身建立信任


class BusinessType(Enum):
    """业务类型"""
    HIGH_COGNITION = "high_cognition"      # 高认知门槛（教育、医疗、法律、金融）
    LOW_COGNITION_STORY = "low_cognition_story"  # 低认知门槛+有故事（特产、食品、本地服务）
    BRAND_BACKED = "brand_backed"          # 强品牌背书（知名品牌、连锁企业）
    MIXED = "mixed"                        # 混合型


@dataclass
class ClassificationResult:
    """分类结果"""
    trust_source: TrustSourceType
    business_type: BusinessType
    confidence: float  # 置信度 0-1
    recommended_topic_types: List[str]
    recommended_balance_config: Dict[str, float]
    reasoning: str
    warnings: List[str]


# =============================================================================
# 业务特征关键词映射
# =============================================================================

# 高认知门槛行业关键词
HIGH_COGNITION_KEYWORDS = [
    "教育", "培训", "医疗", "健康", "法律", "金融", "投资", "理财",
    "保险", "法律咨询", "心理咨询", "留学", "移民", "考研", "公考",
    "考证", "职业技能", "企业管理", "法律服务", "医疗服务"
]

# 强品牌关键词
BRAND_KEYWORDS = [
    "品牌", "连锁", "上市", "集团", "知名", "老字号", "上市公司",
    "旗舰店", "专卖店", "全国连锁", "上市公司", "500强", "国企",
    "央企", "外资", "合资"
]

# 强品牌企业类型
BRAND_ORGANIZATION_TYPES = [
    "知名企业", "连锁企业", "上市公司", "国有企业", "外资企业",
    "合资企业", "品牌商", "品牌方", "旗舰店", "官方"
]

# 低认知门槛+有故事关键词
STORY_KEYWORDS = [
    # 特产/食品
    "特产", "零食", "水果", "农产品", "土特产", "山货", "手作", "手工",
    "自制", "家乡", "农村", "农场", "果园", "养殖场",
    # 本地服务
    "本地服务", "家政", "保洁", "维修", "装修", "摄影", "婚庆",
    "餐饮", "美食", "民宿", "农家乐", "采摘", "旅游",
    # 个人品牌
    "个人", "私人", "工作室", "达人", "博主", "创业者", "农人"
]

# 故事/冲突关键词
CONFLICT_KEYWORDS = [
    # 人物冲突
    "奇葩", "顾客", "客户", "同行", "竞争", "误解", "冲突", "故事",
    "经历", "亲身", "真实", "第一次", "没想到", "竟然",
    # 生产故事
    "制作", "生产", "加工", "种植", "养殖", "采摘", "凌晨",
    "坚持", "品质", "匠心", "祖传", "传承", "秘方"
]

# 产品型关键词
PRODUCT_KEYWORDS = [
    "产品", "商品", "物品", "单品", "标准化", "规格", "型号",
    "日用品", "快消品", "工业品", "原材料"
]


@dataclass
class BusinessFeatures:
    """业务特征"""
    name: str
    industry: str
    org_type: str
    tags: List[str]
    description: str
    has_story: bool
    has_brand: bool
    is_high_cognition: bool


class BusinessClassifier:
    """业务特征分类器"""

    def classify(self, portrait_data: Dict[str, Any]) -> ClassificationResult:
        """
        根据客户画像数据判断信任来源类型

        Args:
            portrait_data: 客户画像数据，包含：
                - name: 客户名称
                - industry: 行业
                - business_type: 业务类型描述
                - org_type: 机构类型
                - tags: 标签列表
                - description: 描述

        Returns:
            ClassificationResult: 分类结果
        """
        # 提取业务特征
        features = self._extract_features(portrait_data)

        # 决策树判断
        result = self._decision_tree(features)

        return result

    def _extract_features(self, data: Dict[str, Any]) -> BusinessFeatures:
        """提取业务特征"""
        name = data.get("name", "") or ""
        industry = data.get("industry", "") or ""
        business_type = data.get("business_type", "") or ""
        org_type = data.get("org_type", "") or ""
        tags = data.get("tags", []) or []
        description = data.get("description", "") or ""

        # 合并所有文本用于关键词匹配
        all_text = f"{name} {industry} {business_type} {org_type} {' '.join(tags)} {description}"

        # 判断特征
        has_brand = self._check_brand(all_text, org_type)
        is_high_cognition = self._check_high_cognition(all_text)
        has_story = self._check_has_story(all_text)

        return BusinessFeatures(
            name=name,
            industry=industry,
            org_type=org_type,
            tags=tags,
            description=description,
            has_story=has_story,
            has_brand=has_brand,
            is_high_cognition=is_high_cognition
        )

    def _check_brand(self, text: str, org_type: str) -> bool:
        """检查是否有强品牌背书"""
        # 机构类型直接判断
        for org in BRAND_ORGANIZATION_TYPES:
            if org in org_type:
                return True

        # 关键词判断
        for keyword in BRAND_KEYWORDS:
            if keyword in text:
                return True

        return False

    def _check_high_cognition(self, text: str) -> bool:
        """检查是否是高认知门槛业务"""
        for keyword in HIGH_COGNITION_KEYWORDS:
            if keyword in text:
                return True
        return False

    def _check_has_story(self, text: str) -> bool:
        """检查是否有故事/冲突可讲"""
        # 先检查故事关键词
        story_count = sum(1 for kw in STORY_KEYWORDS if kw in text)

        # 再检查冲突关键词
        conflict_count = sum(1 for kw in CONFLICT_KEYWORDS if kw in text)

        # 至少有一个故事关键词或多个冲突关键词
        return story_count >= 1 or conflict_count >= 3

    def _decision_tree(self, features: BusinessFeatures) -> ClassificationResult:
        """
        信任来源决策树

        决策逻辑：
        1. 是否有强品牌背书？ → 是 → 机构型
        2. 是否高认知门槛业务？ → 是 → 知识型
        3. 是否有故事/冲突可讲？ → 是 → 人设价值观型
        4. 否则 → 产品型
        """
        warnings = []
        reasoning_parts = []

        # 节点1: 品牌背书检查
        if features.has_brand:
            trust_source = TrustSourceType.INSTITUTION
            business_type = BusinessType.BRAND_BACKED
            confidence = 0.95
            reasoning_parts.append("检测到强品牌背书（机构型信任）")
            recommended_topics = ["机构产品类", "热点关联类", "案例分享类", "产品推荐类"]

            config = {
                "信息密度": 0.70,
                "问题悬念": 0.40,
                "情绪波动": 0.50,
                "互动频率": 0.50,
                "奖励分布": 0.50,
                "难度递进": 0.60
            }

        # 节点2: 高认知门槛检查
        elif features.is_high_cognition:
            trust_source = TrustSourceType.KNOWLEDGE
            business_type = BusinessType.HIGH_COGNITION
            confidence = 0.90
            reasoning_parts.append("高认知门槛业务（知识型信任）")
            recommended_topics = ["问题诊断类", "解决方案类", "知识科普类", "案例分享类"]

            config = {
                "信息密度": 0.80,
                "问题悬念": 0.50,
                "情绪波动": 0.40,
                "互动频率": 0.45,
                "奖励分布": 0.60,
                "难度递进": 0.75
            }

        # 节点3: 故事/冲突检查
        elif features.has_story:
            trust_source = TrustSourceType.PERSONA
            business_type = BusinessType.LOW_COGNITION_STORY
            confidence = 0.85
            reasoning_parts.append("低认知门槛但有故事可讲（人设型信任）")

            # 人设价值观类内容
            recommended_topics = ["人设价值观类", "人设故事类", "案例分享类", "产品推荐类"]

            config = {
                "信息密度": 0.20,
                "问题悬念": 0.70,
                "情绪波动": 0.75,
                "互动频率": 0.65,
                "奖励分布": 0.55,
                "难度递进": 0.65
            }

            warnings.append("人设型信任建议真人出镜")

        # 节点4: 产品型
        else:
            trust_source = TrustSourceType.PRODUCT
            business_type = BusinessType.MIXED
            confidence = 0.70
            reasoning_parts.append("无明显特征，使用产品型信任策略")

            recommended_topics = ["产品推荐类", "问题诊断类", "解决方案类"]

            config = {
                "信息密度": 0.60,
                "问题悬念": 0.45,
                "情绪波动": 0.55,
                "互动频率": 0.50,
                "奖励分布": 0.55,
                "难度递进": 0.50
            }

            warnings.append("建议补充业务描述以便更准确分类")

        # 构建理由
        reasoning = " → ".join(reasoning_parts)
        if features.name:
            reasoning = f"{features.name}: {reasoning}"

        return ClassificationResult(
            trust_source=trust_source,
            business_type=business_type,
            confidence=confidence,
            recommended_topic_types=recommended_topics,
            recommended_balance_config=config,
            reasoning=reasoning,
            warnings=warnings
        )

    def get_trust_source_label(self, trust_source: TrustSourceType) -> str:
        """获取信任来源标签"""
        labels = {
            TrustSourceType.KNOWLEDGE: "知识型",
            TrustSourceType.PERSONA: "人设型",
            TrustSourceType.INSTITUTION: "机构型",
            TrustSourceType.PRODUCT: "产品型"
        }
        return labels.get(trust_source, "未知")

    def get_business_type_label(self, business_type: BusinessType) -> str:
        """获取业务类型标签"""
        labels = {
            BusinessType.HIGH_COGNITION: "高认知门槛",
            BusinessType.LOW_COGNITION_STORY: "低认知门槛+有故事",
            BusinessType.BRAND_BACKED: "强品牌背书",
            BusinessType.MIXED: "混合型"
        }
        return labels.get(business_type, "未知")

    def get_topic_type_description(self, topic_type: str) -> Dict[str, Any]:
        """获取选题类型详细描述"""
        descriptions = {
            "问题诊断类": {
                "时长": "15-30秒",
                "信任来源": "知识型",
                "出镜": "均可",
                "核心逻辑": "知识驱动"
            },
            "解决方案类": {
                "时长": "30-60秒",
                "信任来源": "知识型",
                "出镜": "出镜更好",
                "核心逻辑": "知识驱动"
            },
            "案例分享类": {
                "时长": "60-90秒",
                "信任来源": "知识型+人设型",
                "出镜": "出镜更好",
                "核心逻辑": "知识驱动"
            },
            "产品推荐类": {
                "时长": "15-30秒",
                "信任来源": "知识型/机构型",
                "出镜": "出镜更好",
                "核心逻辑": "知识驱动"
            },
            "知识科普类": {
                "时长": "30-60秒",
                "信任来源": "知识型",
                "出镜": "均可",
                "核心逻辑": "知识驱动"
            },
            "热点关联类": {
                "时长": "15-30秒",
                "信任来源": "知识型",
                "出镜": "出镜更好",
                "核心逻辑": "知识驱动"
            },
            "人设故事类": {
                "时长": "60-90秒",
                "信任来源": "人设型",
                "出镜": "必须出镜",
                "核心逻辑": "知识+情感"
            },
            "人设价值观类": {
                "时长": "30-90秒",
                "信任来源": "人设型",
                "出镜": "必须出镜",
                "核心逻辑": "价值观驱动"
            },
            "机构产品类": {
                "时长": "15-60秒",
                "信任来源": "机构型",
                "出镜": "不需要出镜",
                "核心逻辑": "产品驱动"
            }
        }
        return descriptions.get(topic_type, {})


# =============================================================================
# 便捷函数
# =============================================================================

def classify_business(portrait_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    业务分类的便捷函数

    Args:
        portrait_data: 客户画像数据

    Returns:
        dict: 分类结果（字典格式）
    """
    classifier = BusinessClassifier()
    result = classifier.classify(portrait_data)

    return {
        "trust_source": result.trust_source.value,
        "trust_source_label": classifier.get_trust_source_label(result.trust_source),
        "business_type": result.business_type.value,
        "business_type_label": classifier.get_business_type_label(result.business_type),
        "confidence": round(result.confidence, 2),
        "recommended_topic_types": result.recommended_topic_types,
        "recommended_balance_config": result.recommended_balance_config,
        "reasoning": result.reasoning,
        "warnings": result.warnings
    }


def get_recommended_topics(trust_source: TrustSourceType) -> List[Dict[str, Any]]:
    """获取推荐的选题类型列表"""
    classifier = BusinessClassifier()

    topic_mapping = {
        TrustSourceType.KNOWLEDGE: ["问题诊断类", "解决方案类", "知识科普类", "案例分享类"],
        TrustSourceType.PERSONA: ["人设价值观类", "人设故事类", "案例分享类", "产品推荐类"],
        TrustSourceType.INSTITUTION: ["机构产品类", "热点关联类", "案例分享类", "产品推荐类"],
        TrustSourceType.PRODUCT: ["产品推荐类", "问题诊断类", "解决方案类"]
    }

    topics = topic_mapping.get(trust_source, [])

    result = []
    for topic in topics:
        desc = classifier.get_topic_type_description(topic)
        result.append({
            "type": topic,
            **desc
        })

    return result
