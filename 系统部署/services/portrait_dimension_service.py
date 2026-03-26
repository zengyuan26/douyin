"""
画像维度服务

核心功能：
1. 存储完整：数据库存储完整维度信息（名称、描述、示例、映射等）
2. 输出精简：生成AI友好的精简提示词（逗号分隔字符串）
3. 维度映射：障碍→内容方向映射
4. 性能优化：维度缓存、按需查询

设计原则：
- 存储完整是为了管理界面展示和灵活配置
- 输出精简是为了节省Token、提升AI响应速度
- 按需读取是为了减少不必要的数据库查询
"""

from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging

from models.models import AnalysisDimension
from services.portrait_dimension_data import SUB_CATEGORY_LABELS

logger = logging.getLogger(__name__)

# ========== 缓存机制 ==========

# 维度缓存（启动时加载，定时刷新）
_dimension_cache: Dict[str, List[AnalysisDimension]] = {}
_cache_loaded_at = None


def _refresh_cache():
    """刷新维度缓存"""
    global _dimension_cache, _cache_loaded_at
    from datetime import datetime
    
    # 按子分类缓存启用的维度
    _dimension_cache = defaultdict(list)
    dims = AnalysisDimension.query.filter_by(
        category='super_positioning',
        is_active=True
    ).order_by(AnalysisDimension.sub_category, AnalysisDimension.id).all()
    
    for dim in dims:
        _dimension_cache[dim.sub_category].append(dim)
    
    _cache_loaded_at = datetime.utcnow()
    logger.info(f"[PortraitDimension] 缓存刷新，共 {len(dims)} 个画像维度")


def get_cached_dimensions(sub_category: str) -> List[AnalysisDimension]:
    """获取缓存的维度（按子分类）"""
    if not _dimension_cache:
        _refresh_cache()
    return _dimension_cache.get(sub_category, [])


def clear_cache():
    """清除缓存"""
    global _dimension_cache, _cache_loaded_at
    _dimension_cache = {}
    _cache_loaded_at = None


# ========== 精简输出方法 ==========

def get_dimensions_for_ai(sub_category: str) -> str:
    """
    获取指定子分类的维度名称（逗号分隔字符串）
    用于AI提示词
    
    Args:
        sub_category: 子分类名称，如 'conflict_type', 'transformation_barrier'
    
    Returns:
        逗号分隔的维度名称字符串，如 '缺失型,拥有型,冲突型'
    """
    dims = get_cached_dimensions(sub_category)
    return ",".join([d.name for d in dims if d.name])


def get_all_conflict_types_for_ai() -> str:
    """获取矛盾类型（AI用）"""
    return get_dimensions_for_ai('conflict_type')


def get_all_transformation_types_for_ai() -> str:
    """获取转变类型（AI用）"""
    return get_dimensions_for_ai('transformation_type')


def get_all_barriers_for_ai() -> str:
    """
    获取障碍维度（AI用，按来源分组）
    返回格式：
    内在:认知,资源,决策,心理,代理焦虑,拥有型
    他人:反对,口碑,分歧,社交压力,权威影响
    环境:渠道,时间,条件,沉没成本
    """
    dims = get_cached_dimensions('transformation_barrier')
    grouped = defaultdict(list)
    for d in dims:
        source = getattr(d, 'applicable_audience', '内在') or '内在'
        grouped[source].append(d.name)
    
    lines = []
    for source in ['内在', '他人', '环境']:
        if source in grouped:
            lines.append(f"{source}:{','.join(grouped[source])}")
    
    return "\n".join(lines)


def get_all_change_stages_for_ai() -> str:
    """获取转变阶段（AI用）"""
    return get_dimensions_for_ai('change_stage')


def get_all_buyer_relations_for_ai() -> str:
    """获取买用关系（AI用）"""
    return get_dimensions_for_ai('buyer_user_relationship')


def get_all_content_types_for_ai() -> str:
    """获取内容类型（AI用）"""
    return get_dimensions_for_ai('content_type')


def get_all_intent_stages_for_ai() -> str:
    """获取意图阶段（AI用）"""
    return get_dimensions_for_ai('intent_stage')


def get_all_risk_dims_for_ai() -> str:
    """获取风险维度（AI用）"""
    return get_dimensions_for_ai('risk_dimension')


def get_all_cost_dims_for_ai() -> str:
    """获取成本维度（AI用）"""
    return get_dimensions_for_ai('cost_dimension')


def get_all_efficiency_dims_for_ai() -> str:
    """获取效率维度（AI用）"""
    return get_dimensions_for_ai('efficiency_dimension')


def get_all_emotional_dims_for_ai() -> str:
    """获取情感维度（AI用）"""
    return get_dimensions_for_ai('emotional_dimension')


def get_all_social_dims_for_ai() -> str:
    """获取社交维度（AI用）"""
    return get_dimensions_for_ai('social_dimension')


def get_dimension_weights_for_ai() -> str:
    """
    获取维度权重配置（AI用）
    返回格式：情感:10,效率:8,成本:7,风险:9,社交:8,认知:9,矛盾:8,障碍:9
    """
    from services.portrait_dimension_data import SUB_CATEGORY_WEIGHTS
    lines = [f"{SUB_CATEGORY_LABELS.get(k, k)}:{v}" for k, v in SUB_CATEGORY_WEIGHTS.items()]
    return ",".join(lines)


def get_dimension_weights_by_name(name: str) -> float:
    """
    根据维度名称获取权重（从数据库或默认配置）
    
    Args:
        name: 维度名称，如 '焦虑型', '认知'
    
    Returns:
        权重值（1.0-10.0），默认 1.0
    """
    # 先从缓存中查找
    for sub_cat, dims in _dimension_cache.items():
        for d in dims:
            if d.name == name and hasattr(d, 'weight') and d.weight:
                return float(d.weight)
    
    # 如果数据库中没有，返回子分类默认权重
    from services.portrait_dimension_data import SUB_CATEGORY_WEIGHTS
    # 遍历子分类尝试匹配
    for sub_cat, dims in _dimension_cache.items():
        for d in dims:
            if d.name == name:
                return SUB_CATEGORY_WEIGHTS.get(sub_cat, 1.0)
    
    return 1.0


def get_barrier_mapping_for_ai() -> Dict[str, str]:
    """
    获取障碍→内容方向映射（AI用）
    返回格式：{'认知': '科普/教程', '资源': '性价比/便捷方案', ...}

    prompt_template 字段存储内容方向
    """
    dims = get_cached_dimensions('transformation_barrier')
    mapping = {}
    for d in dims:
        if d.name and d.prompt_template:
            mapping[d.name] = d.prompt_template
    return mapping


def get_barrier_descriptions_for_ai() -> str:
    """
    获取障碍维度含义（精简描述，AI用）
    当需要理解某个障碍时查询，不需要全部输出
    """
    dims = get_cached_dimensions('transformation_barrier')
    lines = []
    for d in dims:
        if d.name and d.description:
            lines.append(f"{d.name}: {d.description}")
    return "\n".join(lines)


# ========== 完整上下文（管理界面用）==========

def get_full_dimension_context() -> Dict:
    """
    获取完整维度上下文（用于管理界面展示）
    返回按子分类分组的完整维度信息
    """
    result = {}
    sub_categories = [
        'conflict_type', 'transformation_type', 'transformation_barrier',
        'change_stage', 'buyer_user_relationship', 'content_type',
        'intent_stage', 'risk_dimension', 'cost_dimension',
        'efficiency_dimension', 'emotional_dimension', 'social_dimension'
    ]
    
    for sub_cat in sub_categories:
        dims = get_cached_dimensions(sub_cat)
        if dims:
            result[sub_cat] = {
                'label': sub_category_labels.get(sub_cat, sub_cat),
                'dimensions': [{
                    'id': d.id,
                    'name': d.name,
                    'description': d.description,
                    'examples': getattr(d, 'examples', ''),
                    'applicable_audience': getattr(d, 'applicable_audience', ''),
                    'prompt_template': getattr(d, 'prompt_template', ''),
                    'is_active': d.is_active
                } for d in dims]
            }
    
    return result


def get_dimension_by_name(sub_category: str, name: str) -> Optional[AnalysisDimension]:
    """根据子分类和名称获取维度"""
    dims = get_cached_dimensions(sub_category)
    for d in dims:
        if d.name == name:
            return d
    return None


def get_barrier_examples(name: str) -> str:
    """获取障碍的典型表现示例"""
    dim = get_dimension_by_name('transformation_barrier', name)
    return getattr(dim, 'examples', '') or ''


def get_barrier_description(name: str) -> str:
    """获取障碍的定义描述"""
    dim = get_dimension_by_name('transformation_barrier', name)
    return getattr(dim, 'description', '') or ''


def get_content_direction(barrier_name: str) -> str:
    """获取障碍对应的内容方向"""
    dim = get_dimension_by_name('transformation_barrier', barrier_name)
    return getattr(dim, 'prompt_template', '') or ''


# ========== AI提示词构建 ==========

def build_portrait_generation_context() -> Dict[str, str]:
    """
    构建画像生成的完整AI提示词上下文（精简版）
    返回包含所有维度信息的字典
    """
    return {
        '矛盾类型': get_all_conflict_types_for_ai(),
        '转变类型': get_all_transformation_types_for_ai(),
        '障碍维度': get_all_barriers_for_ai(),
        '障碍含义': get_barrier_descriptions_for_ai(),
        '转变阶段': get_all_change_stages_for_ai(),
        '买用关系': get_all_buyer_relations_for_ai(),
        '风险维度': get_all_risk_dims_for_ai(),
        '成本维度': get_all_cost_dims_for_ai(),
        '效率维度': get_all_efficiency_dims_for_ai(),
        '情感维度': get_all_emotional_dims_for_ai(),
        '社交维度': get_all_social_dims_for_ai(),
        '内容类型': get_all_content_types_for_ai(),
        '内容方向映射': get_barrier_mapping_for_ai()
    }


# ========== 画像生成模板 ==========

PORTRAIT_GENERATION_PROMPT_TEMPLATE = """你是精准营销专家。基于业务信息，生成精准人群画像。

## 业务信息
{business_info}

## 问题卡片
- 使用人：{user_identity}
- 付费人：{buyer_identity}
- 买用关系：{buyer_user_relationship}
- 具体问题：{specific_problem}

## 维度选项（请根据业务选择适用项）

### 矛盾类型
{conflict_types}
例：拥有型 表示"有资源但不知道怎么用"（如：1000万粉丝不知道怎么变现）

### 障碍维度（影响转变的因素）
{barrier_dimensions}
格式：来源:障碍名
例：内在:认知 表示"不知道正确方法"的内在障碍

### 障碍含义（按需查询）
{barrier_descriptions}
当需要理解某个障碍时查询，不需要全部输出

### 障碍→内容方向映射
{barrier_mapping}
例：认知→科普/教程 表示认知障碍用科普/教程内容解决

### 转变类型
{transformation_types}
例：旧→新 表示从旧奶粉转到新奶粉

### 转变阶段
{change_stages}
转变前=还没开始考虑,转变中=正在执行,转变后=已完成

### 买用关系
{buyer_relations}
保护型=为他人购买(宝妈给宝宝),孝心型=晚辈给长辈

### 情感维度
{emotional_dims}
焦虑型=担心害怕,内疚型=觉得亏欠想补偿,成就型=想要更好

### 社交维度
{social_dims}
同类人背书=和我一样的人说好,专家背书=权威人士说好

### 风险维度
{risk_dims}
风险厌恶程度,财务/健康/机会风险类型

### 成本维度
{cost_dims}
极度价格敏感=只买最便宜,性价比导向=买对不买贵,首次购买谨慎=怕被坑

### 效率维度
{efficiency_dims}
极高时间敏感=要最快方案,愿意投入时间=学习型用户

## 输出要求

请生成画像时：
1. 选择1-2个主要矛盾类型
2. 选择1-3个主要障碍（过多会让画像模糊）
3. 选择对应的内容方向
4. 画像名称格式：【使用人状态】+【付费人核心障碍】+【付费人身份】

## 输出格式
{{
  "name": "【宝宝转奶】不知道怎么转+老公说不用+焦虑宝妈",
  "conflict_type": "替代型",
  "transformation": {{
    "type": "旧→新",
    "user_current": "宝宝在喝旧奶粉",
    "user_target": "顺利接受新奶粉"
  }},
  "barriers": ["认知", "他人-反对"],
  "emotional": ["焦虑型"],
  "content_directions": ["科普", "权威背书"],
  "keywords": ["转奶方法", "奶粉推荐"]
}}
"""


def generate_portrait_prompt(
    business_info: str,
    user_identity: str,
    buyer_identity: str,
    buyer_user_relationship: str,
    specific_problem: str
) -> str:
    """
    生成画像生成的AI提示词
    
    Args:
        business_info: 业务信息描述
        user_identity: 使用人身份
        buyer_identity: 付费人身份
        buyer_user_relationship: 买用关系描述
        specific_problem: 具体问题描述
    
    Returns:
        格式化后的AI提示词
    """
    context = build_portrait_generation_context()
    barrier_mapping_str = "\n".join([
        f"{k}→{v}" for k, v in context['内容方向映射'].items()
    ])
    
    return PORTRAIT_GENERATION_PROMPT_TEMPLATE.format(
        business_info=business_info,
        user_identity=user_identity,
        buyer_identity=buyer_identity,
        buyer_user_relationship=buyer_user_relationship,
        specific_problem=specific_problem,
        conflict_types=context['矛盾类型'],
        barrier_dimensions=context['障碍维度'],
        barrier_descriptions=context['障碍含义'],
        barrier_mapping=barrier_mapping_str,
        transformation_types=context['转变类型'],
        change_stages=context['转变阶段'],
        buyer_relations=context['买用关系'],
        emotional_dims=context['情感维度'],
        social_dims=context['社交维度'],
        risk_dims=context['风险维度'],
        cost_dims=context['成本维度'],
        efficiency_dims=context['效率维度']
    )


# ========== 画像命名模板 ==========

PORTRAIT_NAME_TEMPLATES = {
    'basic': '【{user_state}】{barrier}+{buyer_identity}',
    'with_emotion': '【{user_state}】{barrier}+{emotion}+{buyer_identity}',
    'with_conflict': '【{conflict_type}】{user_state}+{barrier}+{buyer_identity}'
}


def generate_portrait_name(
    user_state: str,
    barrier: str,
    buyer_identity: str,
    conflict_type: str = None,
    emotion: str = None,
    template_key: str = 'basic'
) -> str:
    """
    生成画像名称
    
    Args:
        user_state: 使用人状态
        barrier: 核心障碍
        buyer_identity: 付费人身份
        conflict_type: 矛盾类型（可选）
        emotion: 情感类型（可选）
        template_key: 模板类型
    
    Returns:
        画像名称，如：【宝宝转奶】不知道怎么转+焦虑宝妈
    """
    template = PORTRAIT_NAME_TEMPLATES.get(template_key, PORTRAIT_NAME_TEMPLATES['basic'])
    
    if template_key == 'with_conflict':
        return template.format(
            conflict_type=conflict_type or '',
            user_state=user_state,
            barrier=barrier,
            buyer_identity=buyer_identity
        )
    elif template_key == 'with_emotion':
        return template.format(
            user_state=user_state,
            barrier=barrier,
            emotion=emotion or '',
            buyer_identity=buyer_identity
        )
    else:
        return template.format(
            user_state=user_state,
            barrier=barrier,
            buyer_identity=buyer_identity
        )


# ========== 维度统计 ==========

def get_dimension_stats() -> Dict:
    """获取维度统计信息"""
    if not _dimension_cache:
        _refresh_cache()
    
    stats = {}
    for sub_cat, dims in _dimension_cache.items():
        stats[sub_cat] = {
            'total': len(dims),
            'active': len([d for d in dims if d.is_active])
        }
    
    return {
        'total_dimensions': sum(s['total'] for s in stats.values()),
        'active_dimensions': sum(s['active'] for s in stats.values()),
        'by_category': stats,
        'cache_loaded_at': _cache_loaded_at.isoformat() if _cache_loaded_at else None
    }


# ========== 初始化 ==========

def init_cache():
    """初始化缓存"""
    _refresh_cache()
    logger.info("[PortraitDimension] 维度服务初始化完成")
