"""
专家评审模块 - 5维评审体系

提供完整的内容质量评审功能，包括：
- psychology_compliance: 心理合规
- emotion_resonance: 情绪共鸣
- trust_building: 信任建立
- value_delivery: 价值传递
- action_guide: 行动引导

使用方法：
    from services.expert_reviewer import ExpertReviewer, REVIEW_DIMENSIONS

    reviewer = ExpertReviewer(llm_service)
    result = reviewer.review_content(content_data)
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from services.llm import get_llm_service

logger = logging.getLogger(__name__)

# =============================================================================
# 评审维度配置
# =============================================================================

# 5维评审体系
REVIEW_DIMENSIONS = {
    "psychology_compliance": {
        "name": "心理合规",
        "name_en": "Psychology Compliance",
        "weight": 0.20,
        "description": "内容是否遵守心理营销规范，不利用焦虑/恐惧进行过度营销",
        "keywords": ["焦虑营销", "恐惧诉求", "虚假紧迫感", "心理操控"],
        "checklist": [
            "是否过度渲染焦虑或恐惧",
            "是否制造虚假的紧迫感",
            "是否使用心理操控手段",
            "是否违反广告法规定",
        ],
        "prompt_template": "请评估以下内容的心理合规性：\n\n{content}\n\n重点检查：\n1. 是否过度渲染焦虑或恐惧\n2. 是否制造虚假紧迫感\n3. 是否使用心理操控手段\n4. 是否违反广告法规定\n\n请用JSON格式输出：\n{{\n  \"dimension\": \"psychology_compliance\",\n  \"score\": 0-100的分数,\n  \"issues\": [\"问题1\", \"问题2\"],\n  \"suggestions\": [\"改进建议1\", \"改进建议2\"],\n  \"is_pass\": true/false\n}}",
    },
    "emotion_resonance": {
        "name": "情绪共鸣",
        "name_en": "Emotion Resonance",
        "weight": 0.20,
        "description": "内容是否能引发目标用户的情感共鸣",
        "keywords": ["共情", "代入感", "情感连接", "触动"],
        "checklist": [
            "是否能引发目标用户的情感共鸣",
            "是否有足够的代入感",
            "是否能触动用户情绪",
            "情绪表达是否自然真实",
        ],
        "prompt_template": "请评估以下内容的情绪共鸣能力：\n\n{content}\n\n目标用户画像：\n{portrait}\n\n重点检查：\n1. 是否能引发目标用户的情感共鸣\n2. 是否有足够的代入感\n3. 是否能触动用户情绪\n4. 情绪表达是否自然真实\n\n请用JSON格式输出：\n{{\n  \"dimension\": \"emotion_resonance\",\n  \"score\": 0-100的分数,\n  \"issues\": [\"问题1\", \"问题2\"],\n  \"suggestions\": [\"改进建议1\", \"改进建议2\"],\n  \"is_pass\": true/false\n}}",
    },
    "trust_building": {
        "name": "信任建立",
        "name_en": "Trust Building",
        "weight": 0.25,
        "description": "内容是否能建立用户对品牌/产品的信任",
        "keywords": ["信任", "权威", "真实", "可信"],
        "checklist": [
            "是否有足够的信任证据",
            "是否引用权威数据或来源",
            "案例是否真实可信",
            "是否有品牌背书",
        ],
        "prompt_template": "请评估以下内容的信任建立能力：\n\n{content}\n\n重点检查：\n1. 是否有足够的信任证据\n2. 是否引用权威数据或来源\n3. 案例是否真实可信\n4. 是否有品牌背书\n\n请用JSON格式输出：\n{{\n  \"dimension\": \"trust_building\",\n  \"score\": 0-100的分数,\n  \"issues\": [\"问题1\", \"问题2\"],\n  \"suggestions\": [\"改进建议1\", \"改进建议2\"],\n  \"is_pass\": true/false\n}}",
    },
    "value_delivery": {
        "name": "价值传递",
        "name_en": "Value Delivery",
        "weight": 0.25,
        "description": "内容是否清晰传递了产品/服务的核心价值",
        "keywords": ["价值", "干货", "实用", "可操作"],
        "checklist": [
            "是否清晰传达了核心价值",
            "是否有足够的干货内容",
            "内容是否实用可操作",
            "信息是否易于理解",
        ],
        "prompt_template": "请评估以下内容的价值传递能力：\n\n{content}\n\n重点检查：\n1. 是否清晰传达了核心价值\n2. 是否有足够的干货内容\n3. 内容是否实用可操作\n4. 信息是否易于理解\n\n请用JSON格式输出：\n{{\n  \"dimension\": \"value_delivery\",\n  \"score\": 0-100的分数,\n  \"issues\": [\"问题1\", \"问题2\"],\n  \"suggestions\": [\"改进建议1\", \"改进建议2\"],\n  \"is_pass\": true/false\n}}",
    },
    "action_guide": {
        "name": "行动引导",
        "name_en": "Action Guide",
        "weight": 0.10,
        "description": "内容是否有明确的行动号召，引导用户下一步",
        "keywords": ["CTA", "行动", "转化", "引导"],
        "checklist": [
            "是否有明确的行动号召",
            "CTA是否清晰具体",
            "是否有降低行动门槛的措施",
            "引导是否自然不生硬",
        ],
        "prompt_template": "请评估以下内容的行动引导能力：\n\n{content}\n\n重点检查：\n1. 是否有明确的行动号召\n2. CTA是否清晰具体\n3. 是否有降低行动门槛的措施\n4. 引导是否自然不生硬\n\n请用JSON格式输出：\n{{\n  \"dimension\": \"action_guide\",\n  \"score\": 0-100的分数,\n  \"issues\": [\"问题1\", \"问题2\"],\n  \"suggestions\": [\"改进建议1\", \"改进建议2\"],\n  \"is_pass\": true/false\n}}",
    },
}

# 评审结果等级
REVIEW_GRADES = {
    "excellent": {
        "range": (90, 100),
        "label": "优秀",
        "color": "#22C55E",
        "description": "内容质量优秀，可以直接发布",
    },
    "good": {
        "range": (75, 89),
        "label": "良好",
        "color": "#3B82F6",
        "description": "内容质量良好，有少量优化空间",
    },
    "pass": {
        "range": (60, 74),
        "label": "合格",
        "color": "#F59E0B",
        "description": "内容质量合格，需要适当优化",
    },
    "fail": {
        "range": (0, 59),
        "label": "不合格",
        "color": "#EF4444",
        "description": "内容质量不合格，需要重新创作",
    },
}


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class DimensionResult:
    """单个维度的评审结果"""
    dimension_key: str
    dimension_name: str
    score: int
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    is_pass: bool = True

    def to_dict(self) -> dict:
        return {
            "dimension_key": self.dimension_key,
            "dimension_name": self.dimension_name,
            "score": self.score,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "is_pass": self.is_pass,
        }


@dataclass
class ReviewResult:
    """完整评审结果"""
    success: bool = False
    overall_score: int = 0
    grade: str = ""
    grade_label: str = ""
    dimension_results: List[DimensionResult] = field(default_factory=list)
    weighted_scores: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    is_pass: bool = False
    pass_dimensions: int = 0
    total_dimensions: int = 5
    raw_output: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "overall_score": self.overall_score,
            "grade": self.grade,
            "grade_label": self.grade_label,
            "dimension_results": [d.to_dict() for d in self.dimension_results],
            "weighted_scores": self.weighted_scores,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "is_pass": self.is_pass,
            "pass_dimensions": self.pass_dimensions,
            "total_dimensions": self.total_dimensions,
        }


# =============================================================================
# 专家评审器
# =============================================================================

class ExpertReviewer:
    """
    内容专家评审器

    基于5维评审体系对内容进行质量评估。

    使用方法：
        from services.expert_reviewer import ExpertReviewer

        reviewer = ExpertReviewer()
        result = reviewer.review_content(
            content="图文内容...",
            portrait={"identity": "目标用户画像..."},
        )
    """

    def __init__(self, llm_service=None):
        self.llm = llm_service or get_llm_service()

    def review_content(
        self,
        content: str,
        portrait: Dict[str, Any] = None,
        dimensions: List[str] = None,
        min_pass_score: int = 60,
    ) -> ReviewResult:
        """
        评审内容质量

        Args:
            content: 待评审的内容（可以是完整内容或单帧内容）
            portrait: 用户画像（用于情绪共鸣评估）
            dimensions: 需要评审的维度列表，默认评审全部5个维度
            min_pass_score: 通过最低分数

        Returns:
            ReviewResult: 评审结果
        """
        result = ReviewResult()

        if not content:
            result.issues.append("内容为空")
            return result

        # 确定需要评审的维度
        if dimensions is None:
            dimensions = list(REVIEW_DIMENSIONS.keys())

        try:
            dimension_results = []
            weighted_scores = {}
            all_issues = []
            all_suggestions = []

            for dim_key in dimensions:
                if dim_key not in REVIEW_DIMENSIONS:
                    logger.warning(f"[ExpertReviewer] 未知维度: {dim_key}")
                    continue

                dim_config = REVIEW_DIMENSIONS[dim_key]

                # 构建prompt
                prompt = dim_config["prompt_template"]
                prompt = prompt.replace("{content}", content)

                if portrait:
                    prompt = prompt.replace("{portrait}", str(portrait))

                # 调用LLM
                messages = [{"role": "user", "content": prompt}]
                response = self.llm.chat(messages, temperature=0.3)

                if not response:
                    logger.warning(f"[ExpertReviewer] 维度 {dim_key} 评审返回为空")
                    continue

                # 解析结果
                dim_result = self._parse_dimension_result(dim_key, dim_config, response)
                dimension_results.append(dim_result)

                # 累加加权分数
                weighted_score = dim_result.score * dim_config["weight"]
                weighted_scores[dim_key] = weighted_score

                # 收集问题和建议
                all_issues.extend(dim_result.issues)
                all_suggestions.extend(dim_result.suggestions)

            # 计算总分
            total_weighted_score = sum(weighted_scores.values())
            overall_score = int(round(total_weighted_score))

            # 确定等级
            grade, grade_label = self._get_grade(overall_score)

            # 判断是否通过
            pass_dimensions = sum(1 for d in dimension_results if d.is_pass)
            is_pass = (
                overall_score >= min_pass_score and
                pass_dimensions >= len(dimension_results) * 0.6
            )

            # 构建结果
            result.success = True
            result.overall_score = overall_score
            result.grade = grade
            result.grade_label = grade_label
            result.dimension_results = dimension_results
            result.weighted_scores = weighted_scores
            result.issues = list(dict.fromkeys(all_issues))  # 去重
            result.suggestions = list(dict.fromkeys(all_suggestions))  # 去重
            result.is_pass = is_pass
            result.pass_dimensions = pass_dimensions
            result.total_dimensions = len(dimension_results)

        except Exception as e:
            logger.error(f"[ExpertReviewer] 评审异常: {e}")
            result.issues.append(f"评审异常: {str(e)}")

        return result

    def review_dimensions_parallel(
        self,
        content: str,
        portrait: Dict[str, Any] = None,
    ) -> Dict[str, DimensionResult]:
        """
        并行评审所有维度（更高效）

        Args:
            content: 待评审的内容
            portrait: 用户画像

        Returns:
            Dict[str, DimensionResult]: 各维度评审结果
        """
        results = {}

        for dim_key, dim_config in REVIEW_DIMENSIONS.items():
            prompt = dim_config["prompt_template"]
            prompt = prompt.replace("{content}", content)

            if portrait:
                prompt = prompt.replace("{portrait}", str(portrait))

            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages, temperature=0.3)

            if response:
                results[dim_key] = self._parse_dimension_result(dim_key, dim_config, response)
            else:
                results[dim_key] = DimensionResult(
                    dimension_key=dim_key,
                    dimension_name=dim_config["name"],
                    score=0,
                    issues=["LLM调用失败"],
                    suggestions=[],
                    is_pass=False,
                )

        return results

    def _parse_dimension_result(
        self,
        dim_key: str,
        dim_config: Dict,
        response: str,
    ) -> DimensionResult:
        """解析单个维度的评审结果"""
        import json
        import re

        # 尝试解析JSON
        try:
            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)

            score = data.get("score", 0)
            issues = data.get("issues", [])
            suggestions = data.get("suggestions", [])
            is_pass = data.get("is_pass", score >= 60)

            if isinstance(issues, str):
                issues = [issues]
            if isinstance(suggestions, str):
                suggestions = [suggestions]

            return DimensionResult(
                dimension_key=dim_key,
                dimension_name=dim_config["name"],
                score=score,
                issues=issues,
                suggestions=suggestions,
                is_pass=is_pass,
            )

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"[ExpertReviewer] 解析维度结果失败: {e}")

            # 尝试从文本中提取信息
            score = 50
            issues = []
            suggestions = []

            if "焦虑" in response or "恐惧" in response:
                issues.append("可能存在心理合规问题")
            if "不足" in response or "缺失" in response:
                issues.append("内容存在不足")
            if "建议" in response:
                suggestions.append("根据评审反馈优化内容")

            return DimensionResult(
                dimension_key=dim_key,
                dimension_name=dim_config["name"],
                score=score,
                issues=issues,
                suggestions=suggestions,
                is_pass=score >= 60,
            )

    def _get_grade(self, score: int) -> tuple:
        """根据分数获取等级"""
        for grade_key, grade_config in REVIEW_GRADES.items():
            min_score, max_score = grade_config["range"]
            if min_score <= score <= max_score:
                return grade_key, grade_config["label"]
        return "fail", "不合格"


# =============================================================================
# 便捷函数
# =============================================================================

def review_content(
    content: str,
    portrait: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    便捷函数：快速评审内容

    使用方法：
        from services.expert_reviewer import review_content

        result = review_content("图文内容...")
        if result["is_pass"]:
            print("内容通过评审")
    """
    reviewer = ExpertReviewer()
    result = reviewer.review_content(content, portrait)
    return result.to_dict()


def get_dimension_info(dimension_key: str = None) -> Dict[str, Any]:
    """
    获取维度信息

    Args:
        dimension_key: 维度键，为None时返回所有维度

    Returns:
        维度配置信息
    """
    if dimension_key:
        return REVIEW_DIMENSIONS.get(dimension_key, {})
    return REVIEW_DIMENSIONS
