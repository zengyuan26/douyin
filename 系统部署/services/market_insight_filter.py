"""
市场洞察维度预筛选服务

功能：
1. 根据业务特征分析，筛选相关的市场洞察维度
2. 渲染维度内容模板，生成精简的LLM提示词
3. 按重要性排序，组装最终提示词
4. 【新增】集成细分赛道识别，打通市场分析和超级定位

使用方式：
from services.market_insight_filter import MarketInsightFilter

filter = MarketInsightFilter()
relevant_dims = filter.filter_dimensions(business_info)
prompt = filter.build_prompt(business_info, relevant_dims)

# 【新增】细分赛道识别
result = filter.recognize_subdivision(business_info)
"""

from typing import Dict, List, Optional, Any
from models.models import db, AnalysisDimension

# 导入细分赛道识别模块
try:
    from services.subdivision_recognizer import (
        SubdivisionRecognizer,
        RecognitionResult,
        RecognitionStatus,
        recognize_subdivision as _recognize_sub
    )
    SUBDIVISION_ENABLED = True
except ImportError:
    SUBDIVISION_ENABLED = False
    RecognitionResult = None
    RecognitionStatus = None
    _recognize_sub = None


class MarketInsightFilter:
    """市场洞察维度预筛选器"""

    def __init__(self):
        self.dimension_cache = None
        self.cache_loaded = False
        self.subdivision_recognizer = None
        if SUBDIVISION_ENABLED:
            self.subdivision_recognizer = SubdivisionRecognizer()

    def load_dimensions(self, force_reload: bool = False) -> List[Dict]:
        """加载所有市场洞察维度"""
        if self.cache_loaded and not force_reload:
            return self.dimension_cache

        dims = AnalysisDimension.query.filter_by(
            category='super_positioning',
            sub_category='market_insight',
            is_active=True
        ).all()

        self.dimension_cache = [
            {
                'id': d.id,
                'name': d.name,
                'code': d.code,
                'description': d.description or '',
                'examples': getattr(d, 'examples', None) or '',
                'usage_tips': getattr(d, 'usage_tips', None) or '',
                'applicable_audience': getattr(d, 'applicable_audience', None) or '',
                'trigger_conditions': getattr(d, 'trigger_conditions', None) or {},
                'content_template': getattr(d, 'content_template', None) or '',
                'importance': getattr(d, 'importance', 1) or 1
            }
            for d in dims
        ]
        self.cache_loaded = True
        return self.dimension_cache

    def analyze_business_features(self, business_info: Dict) -> Dict:
        """
        分析业务特征，返回触发条件匹配所需的信息

        Args:
            business_info: 业务信息字典，包含：
                - business_type: 业务类型 (service/product/both)
                - description: 业务描述
                - business_range: 经营范围
                - keywords: 关键词列表
                - target_users: 目标用户
                等

        Returns:
            业务特征字典
        """
        features = {
            'business_type': business_info.get('business_type', '').lower(),
            'description': business_info.get('description', ''),
            'keywords': business_info.get('keywords', []),
            'has_baby': False,
            'has_elderly': False,
            'has_enterprise': False,
            'is_gift': False,
            'is_pets': False,
            'search_stage': 'all'
        }

        # 从业务描述和关键词中分析特征
        desc_lower = features['description'].lower()
        keywords_str = ' '.join(features.get('keywords', [])).lower()

        # 检测涉及宝宝
        baby_keywords = ['宝宝', '婴儿', '奶粉', '纸尿裤', '奶瓶', '婴儿车', '辅食', '尿不湿', 'Baby', 'Infant', ' toddler']
        if any(kw in desc_lower or kw in keywords_str for kw in baby_keywords):
            features['has_baby'] = True

        # 检测涉及老人
        elderly_keywords = ['老人', '老年人', '养老', '轮椅', '拐杖', '助听器', '老花镜', '保健品', 'Elderly', ' senior']
        if any(kw in desc_lower or kw in keywords_str for kw in elderly_keywords):
            features['has_elderly'] = True

        # 检测企业客户
        enterprise_keywords = ['企业', '公司', '酒店', '餐厅', '酒楼', '医院', '学校', '机构', '酒店', '婚庆', '会议', '团建', '定制', '批发', 'B端', 'B2B', '企业定制']
        if any(kw in desc_lower or kw in keywords_str for kw in enterprise_keywords):
            features['has_enterprise'] = True

        # 检测礼品场景
        gift_keywords = ['礼品', '礼物', '送礼', '伴手礼', '定制水', '定制礼品', '企业礼品', '员工福利', 'Gift', 'gift']
        if any(kw in desc_lower or kw in keywords_str for kw in gift_keywords):
            features['is_gift'] = True

        # 检测宠物
        pet_keywords = ['宠物', '猫', '狗', '狗粮', '猫粮', '宠物用品', 'Pet', 'pet', 'dog', 'cat']
        if any(kw in desc_lower or kw in keywords_str for kw in pet_keywords):
            features['is_pets'] = True

        return features

    def matches_trigger(self, trigger: Dict, features: Dict) -> bool:
        """
        判断维度是否匹配业务特征

        Args:
            trigger: 维度的触发条件
            features: 业务特征

        Returns:
            是否匹配
        """
        # 如果没有触发条件，默认匹配
        if not trigger:
            return True

        # 检查业务类型
        if 'business_types' in trigger and trigger['business_types']:
            if features.get('business_type') not in trigger['business_types']:
                return False

        # 检查特殊人群
        if trigger.get('has_baby') and not features.get('has_baby'):
            return False
        if trigger.get('has_elderly') and not features.get('has_elderly'):
            return False
        if trigger.get('has_enterprise') and not features.get('has_enterprise'):
            return False
        if trigger.get('is_gift') and not features.get('is_gift'):
            return False
        if trigger.get('is_pets') and not features.get('is_pets'):
            return False

        return True

    def render_template(self, dimension: Dict, features: Dict) -> str:
        """
        渲染维度内容模板

        Args:
            dimension: 维度数据
            features: 业务特征

        Returns:
            渲染后的内容
        """
        # 如果有自定义模板，使用自定义模板
        template = dimension.get('content_template', '').strip()
        if template:
            # 替换变量
            replacements = {
                '{examples}': dimension.get('examples', ''),
                '{usage_tips}': dimension.get('usage_tips', ''),
                '{description}': dimension.get('description', ''),
                '{name}': dimension.get('name', ''),
            }
            for key, value in replacements.items():
                template = template.replace(key, value)
            return template

        # 否则使用默认格式
        parts = []

        # 维度名称
        parts.append(f"【{dimension['name']}】")

        # 描述
        if dimension.get('description'):
            parts.append(dimension['description'])

        # 示例
        examples = dimension.get('examples', '').strip()
        if examples:
            parts.append(f"示例：{examples}")

        # 区分技巧
        tips = dimension.get('usage_tips', '').strip()
        if tips:
            parts.append(f"区分技巧：{tips}")

        return '\n'.join(parts)

    def filter_dimensions(self, business_info: Dict, force_reload: bool = False) -> List[Dict]:
        """
        根据业务信息筛选相关维度

        Args:
            business_info: 业务信息
            force_reload: 是否强制重新加载维度

        Returns:
            筛选并渲染后的维度列表
        """
        # 1. 加载维度
        dimensions = self.load_dimensions(force_reload)

        # 2. 分析业务特征
        features = self.analyze_business_features(business_info)

        # 3. 筛选匹配的维度
        relevant = []
        for dim in dimensions:
            if self.matches_trigger(dim.get('trigger_conditions', {}), features):
                # 渲染内容
                rendered_content = self.render_template(dim, features)
                relevant.append({
                    'id': dim['id'],
                    'name': dim['name'],
                    'code': dim['code'],
                    'importance': dim.get('importance', 1),
                    'content': rendered_content,
                    'examples': dim.get('examples', ''),
                    'usage_tips': dim.get('usage_tips', ''),
                })

        # 4. 按重要性排序
        relevant.sort(key=lambda x: x.get('importance', 1), reverse=True)

        return relevant

    def build_prompt(self, business_info: Dict, dimensions: List[Dict],
                     include_header: bool = True) -> str:
        """
        构建发送给LLM的提示词

        Args:
            business_info: 业务信息
            dimensions: 筛选后的维度列表
            include_header: 是否包含头部说明

        Returns:
            提示词字符串
        """
        parts = []

        # 头部说明
        if include_header:
            parts.append("你是用户问题分析专家。请根据以下规则和业务信息，挖掘目标客户的问题。")
            parts.append("")

        # 相关维度内容
        if dimensions:
            parts.append("=== 分析规则 ===")
            for dim in dimensions:
                parts.append(f"\n{dim['content']}")

        # 业务信息
        parts.append("\n=== 业务信息 ===")
        parts.append(f"业务描述：{business_info.get('description', '')}")
        parts.append(f"业务类型：{business_info.get('business_type', '')}")
        parts.append(f"经营范围：{business_info.get('business_range', '')}")

        # 关键词
        keywords = business_info.get('keywords', [])
        if keywords:
            parts.append(f"关键词：{', '.join(keywords)}")

        return '\n'.join(parts)

    def get_dimension_summary(self, dimensions: List[Dict]) -> str:
        """
        获取维度摘要（用于日志/调试）

        Args:
            dimensions: 筛选后的维度列表

        Returns:
            摘要字符串
        """
        if not dimensions:
            return "无相关维度"

        names = [d['name'] for d in dimensions]
        return f"已筛选 {len(dimensions)} 个维度: {', '.join(names)}"

    # ============================================================
    # 【新增】细分赛道识别方法
    # ============================================================

    def recognize_subdivision(self, business_info: Dict,
                             market_analysis_report: Optional[Dict] = None) -> Optional['RecognitionResult']:
        """
        【新增】识别细分赛道

        Args:
            business_info: 业务信息，包含：
                - description: 业务描述
                - industry: 行业名称
                - keywords: 关键词列表
            market_analysis_report: 市场分析报告（可选）

        Returns:
            RecognitionResult: 识别结果
        """
        if not SUBDIVISION_ENABLED or not self.subdivision_recognizer:
            return None

        business_desc = business_info.get('description', '')
        industry = business_info.get('industry', '')

        if not business_desc or not industry:
            return None

        return self.subdivision_recognizer.recognize(
            business_desc=business_desc,
            industry=industry,
            market_analysis_report=market_analysis_report,
            business_info=business_info
        )

    def build_prompt_with_subdivision(self, business_info: Dict,
                                      market_analysis_report: Optional[Dict] = None) -> Dict:
        """
        【新增】构建包含细分赛道的完整Prompt

        Args:
            business_info: 业务信息
            market_analysis_report: 市场分析报告

        Returns:
            Dict: {
                'prompt': str,  # 完整Prompt
                'subdivision_result': RecognitionResult,  # 细分赛道识别结果
                'dimensions': List[Dict],  # 筛选的维度
                'needs_clarification': bool,  # 是否需要询问
                'clarification_question': str,  # 询问问题
                'clarification_options': List[Dict]  # 询问选项
            }
        """
        result = {
            'prompt': '',
            'subdivision_result': None,
            'dimensions': [],
            'needs_clarification': False,
            'clarification_question': '',
            'clarification_options': []
        }

        # 1. 识别细分赛道
        subdivision_result = self.recognize_subdivision(business_info, market_analysis_report)
        result['subdivision_result'] = subdivision_result

        # 2. 如果需要询问，返回询问信息
        if subdivision_result and subdivision_result.needs_clarification:
            result['needs_clarification'] = True
            result['clarification_question'] = subdivision_result.clarification_question
            result['clarification_options'] = subdivision_result.clarification_options
            return result

        # 3. 筛选维度
        dimensions = self.filter_dimensions(business_info)
        result['dimensions'] = dimensions

        # 4. 构建Prompt
        parts = []

        # 头部说明
        parts.append("你是用户问题分析专家。请根据以下规则和业务信息，挖掘目标客户的问题。")
        parts.append("")

        # 【新增】细分赛道信息
        if subdivision_result:
            parts.append("=== 细分赛道信息 ===")
            parts.append(f"行业：{subdivision_result.industry}")
            parts.append(f"细分赛道：{subdivision_result.subdivision_name}")
            parts.append(f"经营类型：{subdivision_result.business_type}")
            parts.append(f"客户类型：{subdivision_result.client_type}")
            if subdivision_result.sales_range:
                parts.append(f"销售范围：{subdivision_result.sales_range}")
            if subdivision_result.matched_keywords:
                parts.append(f"匹配关键词：{', '.join(subdivision_result.matched_keywords)}")
            parts.append("")

        # 相关维度内容
        if dimensions:
            parts.append("=== 分析规则 ===")
            for dim in dimensions:
                parts.append(f"\n{dim['content']}")

        # 业务信息
        parts.append("\n=== 业务信息 ===")
        parts.append(f"业务描述：{business_info.get('description', '')}")
        parts.append(f"业务类型：{business_info.get('business_type', '')}")
        parts.append(f"经营范围：{business_info.get('business_range', '')}")

        # 关键词
        keywords = business_info.get('keywords', [])
        if keywords:
            parts.append(f"关键词：{', '.join(keywords)}")

        result['prompt'] = '\n'.join(parts)
        return result

    def get_problems_from_subdivision(self, subdivision_result: 'RecognitionResult') -> Dict:
        """
        【新增】从细分赛道识别结果获取问题类型

        Args:
            subdivision_result: 细分赛道识别结果

        Returns:
            Dict: 问题类型字典
        """
        if not subdivision_result or not subdivision_result.problems:
            return {}

        return subdivision_result.problems


# ============================================================
# 全局单例
# ============================================================

_market_insight_filter = None


def get_market_insight_filter() -> MarketInsightFilter:
    """获取全局单例"""
    global _market_insight_filter
    if _market_insight_filter is None:
        _market_insight_filter = MarketInsightFilter()
    return _market_insight_filter


def filter_relevant_dimensions(business_info: Dict) -> List[Dict]:
    """
    便捷函数：根据业务信息筛选相关维度

    用法：
        dimensions = filter_relevant_dimensions({
            'business_type': 'product',
            'description': '婴儿奶粉代购',
            'keywords': ['奶粉', '婴儿', '代购']
        })
    """
    return get_market_insight_filter().filter_dimensions(business_info)


def build_llm_prompt(business_info: Dict, include_rules: bool = True) -> str:
    """
    便捷函数：构建完整的LLM提示词

    用法：
        prompt = build_llm_prompt({
            'business_type': 'product',
            'description': '婴儿奶粉代购',
        })
    """
    filter_instance = get_market_insight_filter()
    dimensions = filter_instance.filter_dimensions(business_info)

    if not include_rules:
        # 只返回基础提示词
        return f"""你是用户问题分析专家。请根据以下业务信息，挖掘目标客户的问题。

=== 业务信息 ===
业务描述：{business_info.get('description', '')}
业务类型：{business_info.get('business_type', '')}
经营范围：{business_info.get('business_range', '')}
"""

    return filter_instance.build_prompt(business_info, dimensions)


# ============================================================
# 【新增】细分赛道识别便捷函数
# ============================================================

def recognize_subdivision(business_info: Dict,
                          market_analysis_report: Optional[Dict] = None) -> Optional['RecognitionResult']:
    """
    【新增】便捷函数：识别细分赛道

    使用方式：
        result = recognize_subdivision({
            'description': '卖奶粉',
            'industry': '奶粉'
        })
    """
    if not SUBDIVISION_ENABLED or _recognize_sub is None:
        return None
    return get_market_insight_filter().recognize_subdivision(business_info, market_analysis_report)


def build_prompt_with_subdivision(business_info: Dict,
                                   market_analysis_report: Optional[Dict] = None) -> Dict:
    """
    【新增】便捷函数：构建包含细分赛道的完整Prompt

    使用方式：
        result = build_prompt_with_subdivision({
            'description': '卖奶粉',
            'industry': '奶粉',
            'keywords': ['奶粉', '婴儿']
        })

    返回：
        {
            'prompt': '完整Prompt字符串',
            'subdivision_result': RecognitionResult,
            'dimensions': [...],
            'needs_clarification': False,
            'clarification_question': '',
            'clarification_options': [...]
        }
    """
    return get_market_insight_filter().build_prompt_with_subdivision(
        business_info, market_analysis_report
    )


# ============================================================
# 常用触发条件模板
# ============================================================

TRIGGER_TEMPLATES = {
    'has_baby': {
        'has_baby': True,
        'description': '涉及宝宝/婴儿（如奶粉、纸尿裤、婴儿用品）'
    },
    'has_elderly': {
        'has_elderly': True,
        'description': '涉及老人（如保健品、医疗器械、养老服务）'
    },
    'has_enterprise': {
        'has_enterprise': True,
        'description': '有企业客户（如定制、批发、B端服务）'
    },
    'is_gift': {
        'is_gift': True,
        'description': '礼品场景（如定制礼品、企业礼品、伴手礼）'
    },
    'is_pets': {
        'is_pets': True,
        'description': '涉及宠物（如宠物食品、宠物用品）'
    },
    'all': {
        'description': '通用（所有业务都适用）'
    }
}
