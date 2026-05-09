"""
选题体系

职责划分：
- 系统做：选题库管理、选题分类、热度计算、推荐排序
- LLM做：选题创意生成、选题扩展优化

选题类型：
- 问题诊断类、解决方案类、案例分享类、产品推荐类
- 知识科普类、热点关联类、人设故事类、人设价值观类
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import hashlib


class TopicType(Enum):
    """选题类型"""
    PROBLEM_DIAGNOSIS = "问题诊断类"
    SOLUTION = "解决方案类"
    CASE_SHARE = "案例分享类"
    PRODUCT_RECOMMEND = "产品推荐类"
    KNOWLEDGE = "知识科普类"
    HOT_TOPIC = "热点关联类"
    PERSONA_STORY = "人设故事类"
    PERSONA_VALUE = "人设价值观类"
    VIEWPOINT = "观点输出类"
    INSTITUTION_PRODUCT = "机构产品类"


class TopicStatus(Enum):
    """选题状态"""
    DRAFT = "草稿"
    APPROVED = "已审核"
    PUBLISHED = "已发布"
    ARCHIVED = "已归档"


@dataclass
class Topic:
    """选题"""
    id: str
    title: str
    topic_type: TopicType
    content_summary: str  # 内容概要
    target_keywords: List[str]  # 目标关键词
    status: TopicStatus
    hot_score: float = 0.0  # 热度分
    use_count: int = 0  # 使用次数
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "topic_type": self.topic_type.value,
            "content_summary": self.content_summary,
            "target_keywords": self.target_keywords,
            "status": self.status.value,
            "hot_score": self.hot_score,
            "use_count": self.use_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata
        }


@dataclass
class TopicRecommendation:
    """选题推荐结果"""
    topic: Topic
    match_score: float  # 匹配度
    reasons: List[str]  # 推荐理由
    balance_config: Dict[str, float]  # 推荐均衡器配置


class TopicLibrary:
    """
    选题库

    系统管理选题的存储、分类、检索
    """

    def __init__(self):
        self._topics: Dict[str, Topic] = {}
        self._index_by_type: Dict[TopicType, List[str]] = {}
        self._index_by_keyword: Dict[str, List[str]] = {}

    def add_topic(self, topic: Topic) -> str:
        """添加选题"""
        if not topic.id:
            topic.id = self._generate_id(topic.title)

        topic.created_at = datetime.now().isoformat()
        topic.updated_at = topic.created_at

        self._topics[topic.id] = topic
        self._index_by_type.setdefault(topic.topic_type, []).append(topic.id)
        self._index_by_keyword.setdefault("_all", []).append(topic.id)

        for keyword in topic.target_keywords:
            self._index_by_keyword.setdefault(keyword, []).append(topic.id)

        return topic.id

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        """获取选题"""
        return self._topics.get(topic_id)

    def list_topics(
        self,
        topic_type: Optional[TopicType] = None,
        status: Optional[TopicStatus] = None,
        limit: int = 20
    ) -> List[Topic]:
        """列出选题"""
        topics = list(self._topics.values())

        if topic_type:
            topics = [t for t in topics if t.topic_type == topic_type]

        if status:
            topics = [t for t in topics if t.status == status]

        # 按热度排序
        topics.sort(key=lambda t: t.hot_score, reverse=True)

        return topics[:limit]

    def search_topics(
        self,
        keyword: str,
        limit: int = 20
    ) -> List[Topic]:
        """搜索选题"""
        keyword = keyword.lower()
        results = []

        for topic in self._topics.values():
            if keyword in topic.title.lower():
                results.append(topic)
            elif keyword in topic.content_summary.lower():
                results.append(topic)
            elif any(keyword in kw.lower() for kw in topic.target_keywords):
                results.append(topic)

        results.sort(key=lambda t: t.hot_score, reverse=True)
        return results[:limit]

    def delete_topic(self, topic_id: str) -> bool:
        """删除选题"""
        topic = self._topics.get(topic_id)
        if not topic:
            return False

        del self._topics[topic_id]

        if topic.topic_type in self._index_by_type:
            self._index_by_type[topic.topic_type].remove(topic_id)

        for keyword in topic.target_keywords:
            if keyword in self._index_by_keyword:
                self._index_by_keyword[keyword].remove(topic_id)

        return True

    def update_topic(self, topic_id: str, updates: Dict[str, Any]) -> Optional[Topic]:
        """更新选题"""
        topic = self._topics.get(topic_id)
        if not topic:
            return None

        for key, value in updates.items():
            if hasattr(topic, key):
                setattr(topic, key, value)

        topic.updated_at = datetime.now().isoformat()
        return topic

    def increment_use_count(self, topic_id: str):
        """增加使用次数"""
        topic = self._topics.get(topic_id)
        if topic:
            topic.use_count += 1
            topic.updated_at = datetime.now().isoformat()

    def _generate_id(self, title: str) -> str:
        """生成选题ID"""
        content = f"{title}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


class TopicClassifier:
    """
    选题分类器

    系统根据客户画像和业务特征判断选题类型
    """

    # 选题类型与业务特征映射
    TYPE_MAPPING = {
        # 高认知门槛 -> 知识型选题
        "high_cognition": [
            TopicType.PROBLEM_DIAGNOSIS,
            TopicType.SOLUTION,
            TopicType.KNOWLEDGE,
            TopicType.CASE_SHARE
        ],
        # 低认知门槛+有故事 -> 人设型选题
        "low_cognition_story": [
            TopicType.PERSONA_VALUE,
            TopicType.PERSONA_STORY,
            TopicType.CASE_SHARE,
            TopicType.PRODUCT_RECOMMEND
        ],
        # 强品牌背书 -> 机构型选题
        "brand_backed": [
            TopicType.INSTITUTION_PRODUCT,
            TopicType.HOT_TOPIC,
            TopicType.CASE_SHARE,
            TopicType.PRODUCT_RECOMMEND
        ],
        # 混合型 -> 通用选题
        "mixed": [
            TopicType.SOLUTION,
            TopicType.PRODUCT_RECOMMEND,
            TopicType.VIEWPOINT
        ]
    }

    # 选题类型推荐配置
    TYPE_BALANCE_CONFIG = {
        TopicType.PROBLEM_DIAGNOSIS: {"信息密度": 0.6, "问题悬念": 0.7, "情绪波动": 0.6, "互动频率": 0.6, "奖励分布": 0.6, "难度递进": 0.5},
        TopicType.SOLUTION: {"信息密度": 0.75, "问题悬念": 0.5, "情绪波动": 0.5, "互动频率": 0.4, "奖励分布": 0.6, "难度递进": 0.7},
        TopicType.CASE_SHARE: {"信息密度": 0.5, "问题悬念": 0.65, "情绪波动": 0.7, "互动频率": 0.6, "奖励分布": 0.55, "难度递进": 0.6},
        TopicType.PRODUCT_RECOMMEND: {"信息密度": 0.55, "问题悬念": 0.5, "情绪波动": 0.65, "互动频率": 0.5, "奖励分布": 0.65, "难度递进": 0.45},
        TopicType.KNOWLEDGE: {"信息密度": 0.8, "问题悬念": 0.6, "情绪波动": 0.5, "互动频率": 0.45, "奖励分布": 0.6, "难度递进": 0.8},
        TopicType.HOT_TOPIC: {"信息密度": 0.5, "问题悬念": 0.8, "情绪波动": 0.7, "互动频率": 0.6, "奖励分布": 0.8, "难度递进": 0.5},
        TopicType.PERSONA_STORY: {"信息密度": 0.25, "问题悬念": 0.6, "情绪波动": 0.8, "互动频率": 0.65, "奖励分布": 0.55, "难度递进": 0.6},
        TopicType.PERSONA_VALUE: {"信息密度": 0.2, "问题悬念": 0.7, "情绪波动": 0.8, "互动频率": 0.7, "奖励分布": 0.55, "难度递进": 0.7},
        TopicType.VIEWPOINT: {"信息密度": 0.4, "问题悬念": 0.7, "情绪波动": 0.75, "互动频率": 0.6, "奖励分布": 0.6, "难度递进": 0.7},
        TopicType.INSTITUTION_PRODUCT: {"信息密度": 0.7, "问题悬念": 0.4, "情绪波动": 0.5, "互动频率": 0.5, "奖励分布": 0.5, "难度递进": 0.6},
    }

    def classify(self, business_type: str) -> List[TopicType]:
        """
        根据业务类型推荐选题类型

        Args:
            business_type: 业务类型标识

        Returns:
            List[TopicType]: 推荐的选题类型列表
        """
        topic_types = self.TYPE_MAPPING.get(business_type, self.TYPE_MAPPING["mixed"])
        return topic_types

    def get_recommended_balance(self, topic_type: TopicType) -> Dict[str, float]:
        """获取选题类型推荐的均衡器配置"""
        return self.TYPE_BALANCE_CONFIG.get(topic_type, {
            "信息密度": 0.6,
            "问题悬念": 0.5,
            "情绪波动": 0.6,
            "互动频率": 0.5,
            "奖励分布": 0.6,
            "难度递进": 0.6
        })

    def recommend_topics(
        self,
        topic_types: List[TopicType],
        library: TopicLibrary,
        limit: int = 5
    ) -> List[TopicRecommendation]:
        """
        推荐选题

        Args:
            topic_types: 选题类型列表
            library: 选题库
            limit: 返回数量

        Returns:
            List[TopicRecommendation]: 推荐的选题
        """
        recommendations = []

        for topic_type in topic_types:
            topics = library.list_topics(topic_type=topic_type, status=TopicStatus.APPROVED)

            for topic in topics[:limit]:
                balance_config = self.get_recommended_balance(topic.topic_type)

                recommendations.append(TopicRecommendation(
                    topic=topic,
                    match_score=self._calculate_match_score(topic, topic_type),
                    reasons=self._generate_reasons(topic, topic_type),
                    balance_config=balance_config
                ))

        # 按匹配度排序
        recommendations.sort(key=lambda r: r.match_score, reverse=True)
        return recommendations[:limit]

    def _calculate_match_score(self, topic: Topic, target_type: TopicType) -> float:
        """计算匹配度"""
        score = 0.0

        # 类型匹配
        if topic.topic_type == target_type:
            score += 0.4

        # 热度加成
        score += min(topic.hot_score / 100, 0.3)

        # 使用次数（不宜过度使用）
        if topic.use_count < 3:
            score += 0.2
        elif topic.use_count < 5:
            score += 0.1

        # 状态加成
        if topic.status == TopicStatus.APPROVED:
            score += 0.1

        return min(score, 1.0)

    def _generate_reasons(self, topic: Topic, target_type: TopicType) -> List[str]:
        """生成推荐理由"""
        reasons = []

        if topic.topic_type == target_type:
            reasons.append("选题类型匹配")

        if topic.hot_score > 50:
            reasons.append(f"热度较高({topic.hot_score:.0f})")

        if topic.use_count == 0:
            reasons.append("全新选题，避免重复")

        if topic.use_count > 0 and topic.use_count < 3:
            reasons.append(f"已使用{topic.use_count}次，效果待验证")

        return reasons


class TopicGenerator:
    """
    选题生成器

    调用LLM生成选题创意
    """

    def generate_topics(
        self,
        business_info: Dict[str, Any],
        count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        生成选题创意

        调用LLM生成，保留系统结构

        Args:
            business_info: 业务信息
            count: 生成数量

        Returns:
            List[Dict]: 选题列表
        """
        prompt = self._build_generation_prompt(business_info, count)

        # 这里应该调用LLM，实际返回结构化数据
        # 模拟LLM返回
        return self._mock_llm_response(business_info, count)

    def _build_generation_prompt(
        self,
        business_info: Dict[str, Any],
        count: int
    ) -> str:
        """构建生成提示词"""
        prompt = f"""你是一个短视频选题专家。请为以下业务生成选题创意。

【业务信息】
- 业务名称: {business_info.get('name', '')}
- 行业: {business_info.get('industry', '')}
- 业务类型: {business_info.get('business_type', '')}
- 目标用户: {business_info.get('target_audience', '')}
- 信任来源: {business_info.get('trust_source', '')}

请生成{count}个选题创意，每个选题包含：
1. 标题: 吸引人的标题
2. 选题类型: 从以下选择(问题诊断类/解决方案类/案例分享类/产品推荐类/知识科普类/热点关联类/人设故事类/人设价值观类/观点输出类/机构产品类)
3. 内容概要: 50字内的内容概要
4. 目标关键词: 3-5个SEO关键词
5. 推荐理由: 为什么这个选题好

请以JSON数组格式返回。
"""
        return prompt

    def _mock_llm_response(
        self,
        business_info: Dict[str, Any],
        count: int
    ) -> List[Dict[str, Any]]:
        """模拟LLM返回（实际项目中替换为真实LLM调用）"""
        # 实际使用时应该调用LLM API
        return [
            {
                "title": f"示例选题{i+1}：{business_info.get('name', '业务')}相关话题",
                "topic_type": "解决方案类",
                "content_summary": f"针对{business_info.get('target_audience', '目标用户')}的实用解决方案",
                "target_keywords": [business_info.get('industry', ''), "技巧", "方法"],
                "reason": "高实用性，适合目标用户"
            }
            for i in range(count)
        ]

    def expand_topic(
        self,
        topic: Topic,
        direction: str = "depth"
    ) -> Dict[str, Any]:
        """
        扩展选题

        Args:
            topic: 原始选题
            direction: 扩展方向 (depth-深度, breadth-广度, emotion-情感)

        Returns:
            Dict: 扩展后的选题
        """
        # 扩展提示词模板
        prompts = {
            "depth": f"将选题'{topic.title}'扩展为更深入的分析角度",
            "breadth": f"将选题'{topic.title}'扩展为更多相关话题",
            "emotion": f"将选题'{topic.title}'增加更多情感共鸣点"
        }

        # 实际应调用LLM
        return {
            "original": topic.to_dict(),
            "expanded_title": f"{topic.title}（扩展版）",
            "expansion_direction": direction,
            "prompt_used": prompts.get(direction, "")
        }


class TopicHotCalculator:
    """
    选题热度计算器

    系统计算选题热度，影响推荐排序
    """

    def __init__(self):
        self.weights = {
            "trend_score": 0.3,      # 趋势得分
            "search_volume": 0.25,   # 搜索量
            "competition": 0.2,      # 竞争度（越低越高）
            "seasonal": 0.15,        # 季节性
            "freshness": 0.1         # 新鲜度
        }

    def calculate(
        self,
        topic: Topic,
        trend_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        计算热度分

        Args:
            topic: 选题
            trend_data: 趋势数据

        Returns:
            float: 热度分 0-100
        """
        score = 0.0

        # 趋势得分
        if trend_data:
            score += self.weights["trend_score"] * trend_data.get("trend_score", 50)

        # 搜索量得分
        if trend_data:
            search_volume = trend_data.get("search_volume", 0)
            search_score = min(search_volume / 1000, 100)
            score += self.weights["search_volume"] * search_score

        # 竞争度得分（反向）
        if trend_data:
            competition = trend_data.get("competition", 50)
            comp_score = 100 - competition
            score += self.weights["competition"] * comp_score

        # 季节性得分
        seasonal_score = self._calculate_seasonal_score(topic)
        score += self.weights["seasonal"] * seasonal_score

        # 新鲜度得分
        freshness_score = self._calculate_freshness_score(topic)
        score += self.weights["freshness"] * freshness_score

        return min(score, 100)

    def _calculate_seasonal_score(self, topic: Topic) -> float:
        """计算季节性得分"""
        # 简单实现，实际应该根据关键词和时间判断
        return 50.0

    def _calculate_freshness_score(self, topic: Topic) -> float:
        """计算新鲜度得分"""
        if topic.use_count == 0:
            return 100.0
        elif topic.use_count < 3:
            return 80.0
        elif topic.use_count < 5:
            return 60.0
        else:
            return max(100 - topic.use_count * 10, 20.0)


# =============================================================================
# 便捷函数
# =============================================================================

def create_topic(
    title: str,
    topic_type: str,
    content_summary: str,
    keywords: List[str]
) -> Dict[str, Any]:
    """创建选题"""
    library = TopicLibrary()

    topic = Topic(
        id="",
        title=title,
        topic_type=TopicType(topic_type),
        content_summary=content_summary,
        target_keywords=keywords,
        status=TopicStatus.DRAFT
    )

    topic_id = library.add_topic(topic)
    return library.get_topic(topic_id).to_dict()


def list_topics(
    topic_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """列出选题"""
    library = TopicLibrary()

    tt = TopicType(topic_type) if topic_type else None
    st = TopicStatus(status) if status else None

    topics = library.list_topics(topic_type=tt, status=st, limit=limit)
    return [t.to_dict() for t in topics]


def search_topics(keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
    """搜索选题"""
    library = TopicLibrary()
    topics = library.search_topics(keyword, limit)
    return [t.to_dict() for t in topics]


def recommend_topics(
    business_type: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """推荐选题"""
    library = TopicLibrary()
    classifier = TopicClassifier()

    topic_types = classifier.classify(business_type)
    recommendations = classifier.recommend_topics(topic_types, library, limit)

    return [
        {
            "topic": r.topic.to_dict(),
            "match_score": r.match_score,
            "reasons": r.reasons,
            "balance_config": r.balance_config
        }
        for r in recommendations
    ]
