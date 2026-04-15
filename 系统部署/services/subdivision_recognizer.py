"""
细分赛道识别服务

功能：
1. 三层识别机制：市场分析输出 > 知识库匹配 > 探测询问
2. 打通市场分析和超级定位的数据流
3. 返回细分赛道及对应的问题类型

使用方式：
from services.subdivision_recognizer import SubdivisionRecognizer, recognize_subdivision

recognizer = SubdivisionRecognizer()

# 方式1：自动识别（优先市场分析，其次知识库，最后询问）
result = recognizer.recognize(
    business_desc="卖奶粉，宝宝拉肚子",
    industry="奶粉",
    market_analysis_report=None  # 可选，如果有市场分析报告
)

# 方式2：便捷函数
result = recognize_subdivision("卖奶粉", "奶粉")
"""

import re
import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

from services.industry_subdivision_knowledge import (
    INDUSTRY_SUBDIVISIONS,
    SubdivisionMatcher,
    SubdivisionMatch,
    BusinessType,
    ClientType,
    get_subdivisions,
    get_problems_for_subdivision,
    get_all_industries
)


class RecognitionStatus(Enum):
    """识别状态"""
    SUCCESS = "success"           # 成功识别
    NEED_CLARIFICATION = "need_clarification"  # 需要询问用户
    NO_MATCH = "no_match"         # 无法匹配


@dataclass
class RecognitionResult:
    """识别结果"""
    status: RecognitionStatus
    industry: str
    subdivision_id: str = ""           # 细分赛道ID
    subdivision_name: str = ""         # 细分赛道名称
    confidence: float = 0.0            # 置信度
    matched_keywords: List[str] = field(default_factory=list)  # 匹配的关键词
    problems: Dict[str, Any] = field(default_factory=dict)     # 问题类型
    business_type: str = ""            # 经营类型（消费品/本地服务/企业服务/个人品牌）
    client_type: str = ""              # 客户类型（C端/B端/混合）
    sales_range: str = ""              # 销售范围（本地/跨区域）
    needs_clarification: bool = False  # 是否需要询问
    clarification_question: str = ""   # 询问问题
    clarification_options: List[Dict] = field(default_factory=list)  # 询问选项
    source: str = "unknown"            # 数据来源：market_analysis / knowledge_base / detection


@dataclass
class BusinessFeatures:
    """业务特征"""
    business_type: str = ""      # 经营类型
    client_type: str = ""        # 客户类型
    sales_range: str = ""        # 销售范围
    has_baby: bool = False       # 涉及宝宝
    has_elderly: bool = False    # 涉及老人
    has_enterprise: bool = False # 有企业客户
    is_gift: bool = False        # 礼品场景
    is_pets: bool = False        # 宠物相关
    is_local: bool = False       # 本地业务
    is_cross_region: bool = False # 跨区域业务


class SubdivisionRecognizer:
    """
    细分赛道识别器

    实现三层识别机制：
    1. 第一层：市场分析输出（优先）
    2. 第二层：知识库匹配（其次）
    3. 第三层：探测询问（兜底）
    """

    def __init__(self):
        self.matcher = SubdivisionMatcher()
        self._load_industry_knowledge()

    def _load_industry_knowledge(self):
        """加载行业知识库"""
        self.industry_knowledge = INDUSTRY_SUBDIVISIONS

    def recognize(
        self,
        business_desc: str,
        industry: str,
        market_analysis_report: Optional[Dict] = None,
        business_info: Optional[Dict] = None
    ) -> RecognitionResult:
        """
        识别细分赛道

        Args:
            business_desc: 业务描述
            industry: 行业名称
            market_analysis_report: 市场分析报告（可选）
            business_info: 业务信息（可选，包含更多特征）

        Returns:
            RecognitionResult: 识别结果
        """
        # 1. 分析业务特征
        features = self._analyze_features(business_desc, business_info or {})

        # 2. 尝试从市场分析报告获取细分赛道
        if market_analysis_report:
            result = self._recognize_from_market_analysis(market_analysis_report, industry)
            if result and result.status == RecognitionStatus.SUCCESS:
                result.source = "market_analysis"
                return result

        # 3. 从知识库匹配
        match_result = self.matcher.match(business_desc, industry)
        if not match_result.needs_clarification:
            return self._build_result_from_match(match_result, features, "knowledge_base")

        # 4. 用 LLM 生成细粒度探测问题
        matched_kw = match_result.matched_keywords if hasattr(match_result, 'matched_keywords') else []
        llm_result = self._generate_llm_clarification(
            business_desc, industry, features, matched_kw
        )
        if llm_result:
            return llm_result

        # 5. 降级：硬编码探测 + 返回询问
        self._detect_subdivision(business_desc, industry, features)
        return self._build_clarification_result(business_desc, industry, features, source="fallback")

    def recognize_multiple(
        self,
        business_desc: str,
        industry: str,
        market_analysis_report: Optional[Dict] = None
    ) -> List[RecognitionResult]:
        """
        识别多个细分赛道（用于混合型业务）

        Args:
            business_desc: 业务描述
            industry: 行业名称
            market_analysis_report: 市场分析报告

        Returns:
            List[RecognitionResult]: 识别结果列表
        """
        # 尝试多匹配
        matches = self.matcher.match_multiple(business_desc, industry)

        features = self._analyze_features(business_desc, {})

        results = []
        for match in matches:
            result = self._build_result_from_match(match, features, "knowledge_base")
            results.append(result)

        return results

    def _recognize_from_market_analysis(
        self,
        report: Dict,
        industry: str
    ) -> Optional[RecognitionResult]:
        """
        从市场分析报告中识别细分赛道

        报告格式：
        {
            "recommended_subdivision": "特殊配方奶粉_乳糖不耐受",
            "target_audience": "乳糖不耐受的宝宝",
            "blue_ocean_opportunity": {...},
            ...
        }
        """
        # 优先读取推荐的细分赛道
        recommended = report.get("recommended_subdivision", "")
        if recommended:
            # 在知识库中查找
            for ind_name, ind_data in self.industry_knowledge.items():
                if ind_name == industry:
                    subdivisions = ind_data.get("subdivisions", {})
                    if recommended in subdivisions:
                        sub_data = subdivisions[recommended]
                        return RecognitionResult(
                            status=RecognitionStatus.SUCCESS,
                            industry=industry,
                            subdivision_id=recommended,
                            subdivision_name=sub_data.get("name", recommended),
                            confidence=1.0,
                            problems=sub_data.get("problems", {}),
                            source="market_analysis"
                        )

        # 读取蓝海机会
        blue_ocean = report.get("blue_ocean_opportunity", {})
        if blue_ocean:
            subdivision = blue_ocean.get("subdivision", "")
            if subdivision:
                problems = blue_ocean.get("problems", {})
                return RecognitionResult(
                    status=RecognitionStatus.SUCCESS,
                    industry=industry,
                    subdivision_id=subdivision,
                    subdivision_name=subdivision,
                    confidence=0.9,
                    problems=problems,
                    source="market_analysis"
                )

        return None

    def _detect_subdivision(
        self,
        business_desc: str,
        industry: str,
        features: BusinessFeatures
    ) -> Optional[RecognitionResult]:
        """
        探测式识别

        通过分析业务描述中的模式，推断可能的细分赛道
        """
        desc_lower = business_desc.lower()

        # 检测本地服务特征
        local_keywords = ["上门", "到店", "本地", "附近", "同城"]
        if any(kw in desc_lower for kw in local_keywords):
            features.is_local = True

        # 检测跨区域特征
        cross_region_keywords = ["全国", "发货", "快递", "跨省", "网上", "电商"]
        if any(kw in desc_lower for kw in cross_region_keywords):
            features.is_cross_region = True

        # 检测B端特征
        enterprise_keywords = ["企业", "公司", "B端", "B2B", "定制", "批发"]
        if any(kw in desc_lower for kw in enterprise_keywords):
            features.has_enterprise = True
            features.client_type = "B端"

        # 检测C端特征
        personal_keywords = ["个人", "家庭", "C端", "B2C", "零售"]
        if any(kw in desc_lower for kw in personal_keywords):
            features.client_type = "C端"

        # 如果是律所，检测C端还是B端
        if industry == "律所":
            c_keywords = ["离婚", "劳动", "交通", "房产", "婚姻"]
            b_keywords = ["法律顾问", "合同", "股权", "知识产权", "企业"]
            c_score = sum(1 for kw in c_keywords if kw in desc_lower)
            b_score = sum(1 for kw in b_keywords if kw in desc_lower)

            if c_score > b_score:
                features.client_type = "C端"
            elif b_score > c_score:
                features.client_type = "B端"

        return None  # 探测式识别返回None，让后续流程处理

    def _generate_llm_clarification(
        self,
        business_desc: str,
        industry: str,
        features: BusinessFeatures,
        matched_keywords: Optional[List[str]] = None
    ) -> Optional[RecognitionResult]:
        """
        用 LLM 生成细粒度的探测问题

        当市场分析和知识库都无法直接确认细分赛道时，
        通过 LLM 分析业务描述，生成精准的探测问题来让用户选择。

        Returns:
            RecognitionResult（status=NEED_CLARIFICATION）或 None（LLM 调用失败时降级）
        """
        try:
            from services.llm import get_llm_service

            available_subdivisions = get_subdivisions(industry)
            if not available_subdivisions:
                logger.warning(
                    "[_generate_llm_clarification] 行业 '%s' 无细分赛道知识库，降级为硬编码探测",
                    industry
                )
                return None

            subdivisions_text = "\n".join(
                f"- {s['id']}：{s['name']}"
                + (f"（关键词：{', '.join(s.get('keywords', []))}）" if s.get('keywords') else "")
                for s in available_subdivisions
            )

            matched_kw_text = ", ".join(matched_keywords) if matched_keywords else "无"

            prompt = f"""你是一个业务分析助手。用户描述了自己的业务，你需要：

1. 分析该业务描述，判断它最可能属于哪个细分赛道
2. 如果有多个候选赛道，或者业务描述模糊，则生成1-2个精准的探测问题来区分
3. 探测问题要直接、具体，让用户能秒懂并快速作答

【业务描述】
{business_desc}

【行业】
{industry}

【已匹配的关键词】
{matched_kw_text}

【可选细分赛道】
{subdivisions_text}

请以 JSON 格式返回分析结果：
{{
  "best_subdivision_id": "最可能的赛道ID，若不确定则为空字符串",
  "best_subdivision_name": "最可能的赛道名称，若不确定则为空字符串",
  "confidence": 0.0到1.0之间的置信度，若不确定则低于0.6,
  "clarification_needed": true或false，是否需要探测问题,
  "clarification_question": "探测问题文本（若不需要探测则为空字符串）",
  "clarification_options": [
    {{"id": "赛道ID", "name": "赛道名称", "hint": "给用户的简短提示"}}
  ],
  "reasoning": "你的简短推理过程（1-2句话）"
}}

规则：
- 如果 confidence >= 0.7，直接返回 best_subdivision_id，不生成探测问题
- 如果 confidence < 0.7，必须生成 clarification_question 和至少2个选项
- 探测问题要站在用户角度，一眼看懂
- 只需要返回 JSON，不要有其他文字"""

            llm = get_llm_service()
            response = llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800
            )

            if not response:
                logger.warning("[_generate_llm_clarification] LLM 返回为空，降级为知识库探测")
                return None

            # 解析 JSON
            import json
            result_data = None
            for line in response.split('\n'):
                line = line.strip()
                if line.startswith('{') and not result_data:
                    try:
                        result_data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        # 尝试补全
                        pass
            if not result_data:
                # 尝试整体解析
                import re as re_module
                json_match = re_module.search(r'\{[\s\S]*\}', response)
                if json_match:
                    result_data = json.loads(json_match.group())

            if not result_data:
                logger.warning(
                    "[_generate_llm_clarification] JSON 解析失败，降级。原始响应：%s",
                    response[:200]
                )
                return None

            # 根据 LLM 结果构建返回值
            confidence = result_data.get("confidence", 0.0)
            best_id = result_data.get("best_subdivision_id", "")
            best_name = result_data.get("best_subdivision_name", "")
            clarification_needed = result_data.get("clarification_needed", False)
            clarification_question = result_data.get("clarification_question", "").strip()
            clarification_options = result_data.get("clarification_options", [])
            reasoning = result_data.get("reasoning", "")

            logger.info(
                "[_generate_llm_clarification] 行业=%s, 置信度=%.2f, 推理=%s",
                industry, confidence, reasoning[:100] if reasoning else ""
            )

            # 置信度高 → 直接返回识别结果
            if confidence >= 0.7 and best_id:
                # 在知识库中验证 best_id 是否有效
                valid_ids = {s['id'] for s in available_subdivisions}
                if best_id in valid_ids:
                    matched_sub = next(s for s in available_subdivisions if s['id'] == best_id)
                    return RecognitionResult(
                        status=RecognitionStatus.SUCCESS,
                        industry=industry,
                        subdivision_id=best_id,
                        subdivision_name=best_name or matched_sub.get('name', best_name),
                        confidence=confidence,
                        matched_keywords=matched_keywords or [],
                        problems=matched_sub.get('problems', {}),
                        business_type=self._infer_business_type(features),
                        client_type=self._infer_client_type_from_features(features),
                        sales_range=self._infer_sales_range(features),
                        needs_clarification=False,
                        source="llm_detection"
                    )
                else:
                    logger.warning(
                        "[_generate_llm_clarification] LLM 返回的赛道ID '%s' 不在知识库中，降级为探测",
                        best_id
                    )

            # 需要探测 → 返回带探测问题的结果
            if clarification_needed and clarification_options:
                # 如果 LLM 没有提供选项，降级用知识库选项
                if not clarification_options:
                    clarification_options = [
                        {"id": s['id'], "name": s['name'], "hint": ""}
                        for s in available_subdivisions[:5]
                    ]

                return RecognitionResult(
                    status=RecognitionStatus.NEED_CLARIFICATION,
                    industry=industry,
                    subdivision_id="",
                    subdivision_name="",
                    confidence=confidence,
                    matched_keywords=matched_keywords or [],
                    problems={},
                    business_type=self._infer_business_type(features),
                    client_type=self._infer_client_type_from_features(features),
                    sales_range=self._infer_sales_range(features),
                    needs_clarification=True,
                    clarification_question=clarification_question or (
                        f"根据您的描述「{business_desc}」，{industry}行业有多个细分方向，"
                        "请问您主要面向哪类客户？"
                    ),
                    clarification_options=clarification_options[:5],
                    source="llm_detection"
                )

            # 置信度低且无探测选项 → 返回通用询问
            return self._build_clarification_result(business_desc, industry, features, source="llm_fallback")

        except Exception as e:
            logger.warning("[_generate_llm_clarification] 异常: %s，降级为硬编码探测", e)
            return None

    def _build_result_from_match(
        self,
        match: SubdivisionMatch,
        features: BusinessFeatures,
        source: str
    ) -> RecognitionResult:
        """从匹配结果构建识别结果"""
        return RecognitionResult(
            status=RecognitionStatus.SUCCESS,
            industry=match.subdivision_id.split("_")[0] if "_" in match.subdivision_id else "",
            subdivision_id=match.subdivision_id,
            subdivision_name=match.subdivision_name,
            confidence=match.confidence,
            matched_keywords=match.matched_keywords,
            problems=match.problems,
            business_type=self._infer_business_type(features),
            client_type=self._infer_client_type(match, features),
            sales_range=self._infer_sales_range(features),
            needs_clarification=False,
            source=source
        )

    def _build_clarification_result(
        self,
        business_desc: str,
        industry: str,
        features: BusinessFeatures,
        source: str = "detection"
    ) -> RecognitionResult:
        """构建需要询问的识别结果"""
        subdivisions = get_subdivisions(industry)

        options = [
            {"id": sub["id"], "name": sub["name"]}
            for sub in subdivisions
        ]

        return RecognitionResult(
            status=RecognitionStatus.NEED_CLARIFICATION,
            industry=industry,
            subdivision_id="",
            subdivision_name="",
            confidence=0,
            problems={},
            business_type=self._infer_business_type(features),
            client_type=features.client_type,
            needs_clarification=True,
            clarification_question=f"根据您的描述'{business_desc}'，{industry}行业有多个细分方向，请选择您主要做的方向：",
            clarification_options=options,
            source=source
        )

    def _infer_client_type_from_features(self, features: BusinessFeatures) -> str:
        """从特征推断客户类型（不修改 features 本身）"""
        if features.client_type:
            return features.client_type
        if features.has_baby or features.has_elderly:
            return "C端"
        if features.has_enterprise:
            return "B端"
        return "C端"

    def _analyze_features(self, business_desc: str, business_info: Dict) -> BusinessFeatures:
        """分析业务特征"""
        features = BusinessFeatures()
        desc_lower = business_desc.lower() if business_desc else ''

        # 检测宝宝
        baby_keywords = ["宝宝", "婴儿", "奶粉", "纸尿裤", "奶瓶", "儿童", "孩子"]
        if any(kw in desc_lower for kw in baby_keywords):
            features.has_baby = True

        # 检测老人
        elderly_keywords = ["老人", "老年人", "养老", "爸妈", "中老年"]
        if any(kw in desc_lower for kw in elderly_keywords):
            features.has_elderly = True

        # 检测企业客户
        enterprise_keywords = ["企业", "公司", "酒店", "餐厅", "机构", "定制", "批发", "B端"]
        if any(kw in desc_lower for kw in enterprise_keywords):
            features.has_enterprise = True

        # 检测本地服务
        local_keywords = ["上门", "到店", "本地", "附近", "同城", "维修", "安装", "服务"]
        if any(kw in desc_lower for kw in local_keywords):
            features.is_local = True

        # 检测跨区域
        cross_region_keywords = ["全国", "发货", "快递", "跨省", "网上", "电商", "代购"]
        if any(kw in desc_lower for kw in cross_region_keywords):
            features.is_cross_region = True

        # 检测宠物
        pet_keywords = ["宠物", "猫", "狗", "鸟", "水族"]
        if any(kw in desc_lower for kw in pet_keywords):
            features.is_pets = True

        return features

    def _infer_business_type(self, features: BusinessFeatures) -> str:
        """推断经营类型"""
        # 根据关键词推断
        if features.is_local:
            return "本地服务"
        elif features.has_enterprise:
            return "企业服务"
        elif features.is_cross_region or features.has_baby or features.has_elderly:
            return "消费品"
        else:
            # 检查是否可能是个人品牌
            # 如果没有明显的消费品/服务特征，可能是内容创作
            return "个人品牌"  # 默认，可能是个人品牌

    def _infer_client_type(self, match: SubdivisionMatch, features: BusinessFeatures) -> str:
        """推断客户类型"""
        # 如果features已经有client_type，直接返回
        if features.client_type:
            return features.client_type

        # 从细分赛道推断
        subdivision_id = match.subdivision_id.lower()
        if "c端" in subdivision_id or "c端" in match.subdivision_name.lower():
            return "C端"
        elif "b端" in subdivision_id or "b端" in match.subdivision_name.lower():
            return "B端"

        # 根据特征推断
        if features.has_baby or features.has_elderly:
            return "C端"
        elif features.has_enterprise:
            return "B端"

        return "C端"  # 默认

    def _infer_sales_range(self, features: BusinessFeatures) -> str:
        """推断销售范围"""
        if features.is_local and not features.is_cross_region:
            return "本地"
        elif features.is_cross_region and not features.is_local:
            return "跨区域"
        elif features.is_local and features.is_cross_region:
            return "本地+跨区域"
        else:
            return "未知"

    def build_problems_prompt(
        self,
        result: RecognitionResult,
        include_header: bool = True
    ) -> str:
        """
        根据识别结果，构建问题识别Prompt

        Args:
            result: 识别结果
            include_header: 是否包含头部说明

        Returns:
            str: 构建好的Prompt
        """
        parts = []

        if include_header:
            parts.append("你是用户问题分析专家。请根据以下业务信息和问题类型模板，挖掘目标客户的问题。")
            parts.append("")

        # 业务基本信息
        parts.append("=== 业务信息 ===")
        parts.append(f"行业：{result.industry}")
        parts.append(f"细分赛道：{result.subdivision_name}")
        parts.append(f"经营类型：{result.business_type}")
        parts.append(f"客户类型：{result.client_type}")
        if result.sales_range:
            parts.append(f"销售范围：{result.sales_range}")

        if result.matched_keywords:
            parts.append(f"业务关键词：{', '.join(result.matched_keywords)}")

        parts.append("")

        # 问题类型模板
        if result.problems:
            parts.append("=== 问题类型模板 ===")
            parts.append(self._format_problems(result.problems))

        # 补充说明
        parts.append("")
        parts.append("=== 任务 ===")
        parts.append("请根据上述业务信息和问题类型模板，生成具体的问题场景和症状。")

        return "\n".join(parts)

    def _format_problems(self, problems: Dict) -> str:
        """格式化问题模板"""
        lines = []

        for category, items in problems.items():
            lines.append(f"\n【{category}】")
            if isinstance(items, dict):
                for sub_category, symptoms in items.items():
                    lines.append(f"  - {sub_category}：")
                    if isinstance(symptoms, list):
                        for symptom in symptoms:
                            lines.append(f"    • {symptom}")
                    else:
                        lines.append(f"    • {symptoms}")
            elif isinstance(items, list):
                for item in items:
                    lines.append(f"  • {item}")

        return "\n".join(lines)

    def get_available_subdivisions(self, industry: str) -> List[Dict]:
        """获取某个行业所有可用的细分赛道"""
        return get_subdivisions(industry)

    def get_problems_by_subdivision(
        self,
        industry: str,
        subdivision_id: str
    ) -> Dict:
        """获取某个细分赛道的问题类型"""
        return get_problems_for_subdivision(industry, subdivision_id)


# ============================================================
# 全局单例
# ============================================================

_recognizer = None


def get_recognizer() -> SubdivisionRecognizer:
    """获取全局单例"""
    global _recognizer
    if _recognizer is None:
        _recognizer = SubdivisionRecognizer()
    return _recognizer


def recognize_subdivision(
    business_desc: str,
    industry: str,
    market_analysis_report: Optional[Dict] = None
) -> RecognitionResult:
    """
    便捷函数：识别细分赛道

    使用方式：
        result = recognize_subdivision("卖奶粉", "奶粉")
    """
    return get_recognizer().recognize(
        business_desc=business_desc,
        industry=industry,
        market_analysis_report=market_analysis_report
    )


def recognize_multiple_subdivisions(
    business_desc: str,
    industry: str
) -> List[RecognitionResult]:
    """
    便捷函数：识别多个细分赛道（混合型业务）

    使用方式：
        results = recognize_multiple_subdivisions("卖奶粉", "奶粉")
    """
    return get_recognizer().recognize_multiple(
        business_desc=business_desc,
        industry=industry
    )


def build_problems_prompt(result: RecognitionResult) -> str:
    """
    便捷函数：构建问题识别Prompt

    使用方式：
        prompt = build_problems_prompt(result)
    """
    return get_recognizer().build_problems_prompt(result)
