"""
市场洞察维度预筛选服务

功能：
1. 根据业务特征分析，筛选相关的市场洞察维度
2. 渲染维度内容模板，生成精简的LLM提示词
3. 按重要性排序，组装最终提示词

使用方式：
from services.market_insight_filter import MarketInsightFilter

filter = MarketInsightFilter()
relevant_dims = filter.filter_dimensions(business_info)
prompt = filter.build_prompt(business_info, relevant_dims)
"""

from typing import Dict, List, Optional, Any
from models.models import db, AnalysisDimension


class MarketInsightFilter:
    """市场洞察维度预筛选器"""

    def __init__(self):
        self.dimension_cache = None
        self.cache_loaded = False

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


# 全局单例
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


# ========== 常用触发条件模板 ==========

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


def get_default_dimensions() -> List[Dict]:
    """
    获取默认的市场洞察维度配置

    用于初始化数据库
    """
    return [
        {
            'name': '买用关系判断',
            'code': 'sup_mar_buy_user',
            'description': '判断购买方与使用方是否分离',
            'examples': '桶装水（企业付费→员工使用）| 奶粉（家长买→宝宝用）| 礼品（送礼人买→收礼人用）',
            'usage_tips': '涉及宝宝/老人/孩子/宠物 → 一定是买用分离',
            'trigger_conditions': {},  # 通用，所有业务都需要判断
            'content_template': '''【买用关系判断】
{description}
- 买即用：买的人=用的人（如桶装水配送、自用食品）
- 买用分离：买的人≠用的人（如奶粉是家长买给宝宝、礼品是送礼人买给收礼人）
涉及宝宝、老人、孩子、宠物等 → **一定是买用分离**。''',
            'importance': 5
        },
        {
            'name': 'B端C端判断',
            'code': 'sup_mar_b_c',
            'description': '判断是否存在企业客户（B端）和个人客户（C端）',
            'examples': '矿泉水定制（ToB+ToC）| 企业软件（纯ToB）| 家庭桶装水（纯ToC）',
            'usage_tips': '业务描述提到企业客户→B端存在；提到个人消费者→C端存在',
            'trigger_conditions': {'has_enterprise': True},  # 有企业客户时启用
            'content_template': '''【B端C端判断】
{description}
- 同时存在ToB和ToC：矿泉水定制、餐具修复、礼品定制等
- 纯ToC：桶装水（家庭自用）、食品（个人购买）
- 纯ToB：企业软件、办公设备、大宗原材料
请根据业务描述灵活判断，不要硬套规则。''',
            'importance': 4
        },
        {
            'name': '搜前阶段分析',
            'code': 'sup_mar_pre_search',
            'description': '用户还不知道用什么产品的阶段',
            'examples': '企业宣传用什么有档次？| 婚宴用什么水？| 送礼送什么好？',
            'usage_tips': '搜前用户搜的是问题词、痛点词',
            'trigger_conditions': {'search_stage': ['pre_search', 'all']},
            'content_template': '''【用户搜索阶段：搜前】
{description}
用户在有问题但不知道用什么产品时的搜索行为：

| 场景 | 搜索词类型 | 示例 |
|------|------------|------|
| 问题不明确 | 问题词 | "企业宣传用什么有档次？" |
| 场景不明确 | 痛点词 | "婚宴用水推荐" |
| 需求不明确 | 模糊需求词 | "送礼送什么好" |

搜前阶段关键词特点：
- 问题导向：不知道怎么选
- 场景模糊：不知道用什么产品
- 需要教育：让用户知道有什么选择''',
            'importance': 5
        },
        {
            'name': '搜中阶段分析',
            'code': 'sup_mar_mid_search',
            'description': '用户知道用什么，但不知道选哪个',
            'examples': '定制水哪家好？| 桶装水哪个牌子好？| 婚宴定制水多少钱？',
            'usage_tips': '搜中用户搜的是对比词、评测词',
            'trigger_conditions': {'search_stage': ['mid_search', 'all']},
            'content_template': '''【用户搜索阶段：搜中】
{description}
用户知道用什么产品，但在对比选择的搜索行为：

| 场景 | 搜索词类型 | 示例 |
|------|------------|------|
| 品牌对比 | 对比词 | "定制水哪家好？" |
| 价格对比 | 价格词 | "定制水多少钱？" |
| 质量评估 | 评测词 | "定制水质量怎么样？" |

搜中阶段关键词特点：
- 竞品对比：哪家好
- 价格敏感：多少钱
- 质量关注：怎么样''',
            'importance': 4
        },
        {
            'name': '搜后阶段分析',
            'code': 'sup_mar_post_search',
            'description': '用户确定要买，在找在哪里买',
            'examples': '定制水厂家联系方式 | 桶装水配送电话 | 婚宴定制水批发',
            'usage_tips': '搜后用户搜的是渠道词、品牌词',
            'trigger_conditions': {'search_stage': ['post_search', 'all']},
            'content_template': '''【用户搜索阶段：搜后】
{description}
用户确定要买，找购买渠道的搜索行为：

| 场景 | 搜索词类型 | 示例 |
|------|------------|------|
| 找供应商 | 渠道词 | "定制水厂家" |
| 找服务 | 联系方式 | "桶装水配送电话" |
| 找价格 | 批发词 | "定制水批发" |

搜后阶段关键词特点：
- 渠道明确：厂家、批发
- 联系方式：电话、地址
- 批量需求：批发、定制''',
            'importance': 3
        },
        {
            'name': '付费人顾虑',
            'code': 'sup_mar_buyer_concern',
            'description': '购买决策者的心理障碍和顾虑',
            'examples': '价格担忧 | 采购便利性 | 报销问题 | 决策风险',
            'usage_tips': '付费人关心：价格、成本、便利、风险',
            'trigger_conditions': {'has_enterprise': True},
            'content_template': '''【付费方顾虑】
{examples}
{usage_tips}

付费人（企业/老板/决策者）关心的问题：
- 价格担忧：值不值这个价？太贵了怎么办？
- 采购便利性：流程复不复杂？好不好协调？
- 报销/成本：发票能不能报？成本怎么算？
- 决策风险：万一效果不好怎么办？
- 配送服务：能不能按时到？服务稳不稳定？''',
            'importance': 4
        },
        {
            'name': '使用人痛点',
            'code': 'sup_mar_user_pain',
            'description': '实际使用者的体验问题和需求',
            'examples': '水质口感 | 配送方便 | 品质稳定 | 使用体验',
            'usage_tips': '使用人关心：体验、品质、方便',
            'trigger_conditions': {},
            'content_template': '''【使用人痛点】
{examples}
{usage_tips}

使用人（员工/客户/家庭成员）关心的问题：
- 体验感受：好不好喝？方不方便？
- 品质稳定：每次质量一样吗？
- 健康安全：卫不卫生？健不健康？
- 使用便利：好不好拿？好不好开？
- 外观形象：好不好看？有没有档次？''',
            'importance': 4
        },
        {
            'name': '蓝海长尾词',
            'code': 'sup_mar_blue_ocean',
            'description': '细分场景、精准需求、痛点解决方案类的蓝海关键词',
            'examples': '婚宴用水 | 凌晨配送 | 企业团建用水 | 火锅店供货',
            'usage_tips': '中国人口基数大，再小的需求也有很多人！',
            'trigger_conditions': {},
            'content_template': '''【蓝海长尾词挖掘】
{description}

核心思路：中国人口基数大，再小的需求也有很多人！围绕问题（不围绕产品）

关键词结构比例：
| 分类 | 占比 | 说明 |
|------|------|------|
| 付费人关键词 | 25% | 价格担忧、采购便利、配送问题 |
| 使用人关键词 | 20% | 体验、品质、健康担忧 |
| 蓝海长尾词 | 25% | 细分场景、精准需求、痛点解决 |
| 行业关联词 | 15% | 上下游、竞争格局、供应链 |
| 知识技能词 | 15% | 使用方法、保存技巧、选购指南 |

蓝海长尾词细分：
- 细分场景词（8%）：婚宴用水、凌晨配送、企业团建
- 精准需求词（6%）：精品礼盒装、净菜配送
- 痛点解决方案词（6%）：桶装水有味怎么办、豆芽怎么保存
- 长尾问题词（5%）：发豆芽要不要见光、桶装水多久换一次''',
            'importance': 5
        }
    ]
