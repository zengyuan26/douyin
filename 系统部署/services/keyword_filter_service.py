# -*- coding: utf-8 -*-
"""
关键词筛选 / 问题引导词 - 从分析维度表读取并缓存
用于「识别问题」流程：关键词筛选维度生成种子词；问题引导词约束 LLM 推测搜索意图的问句形态。
"""

import time
from typing import List, Dict, Optional
from models.models import db, AnalysisDimension


# ── 提取产品名：从 business_desc 中抽核心产品词 ──────────────────────────────
def _extract_product_name(desc: str) -> str:
    """
    从业务描述中提取最核心的产品/服务名词。
    策略：优先取最后一个名词性片段（通常是最具体的产品名）。
    """
    import re
    d = (desc or '').strip()
    if not d:
        return '该产品'
    # 去掉常见前缀词
    for prefix in ('做', '卖', '提供', '经营', '销售', '定制', '提供', '从事', '我的业务是', '我的产品是', '业务：', '产品：', '我的业务是', '产品是'):
        if d.startswith(prefix):
            d = d[len(prefix):]
    # 取第一个逗号/顿号前的部分
    d = d.split('，')[0].split('、')[0].split('；')[0].split('\n')[0].strip()
    return d if d else '该产品'


class KeywordFilterService:
    """关键词筛选服务 - 带缓存的数据库读取"""

    _cache: Optional[List[Dict]] = None
    _cache_time: float = 0
    CACHE_TTL: int = 3600  # 缓存有效期：1小时

    @classmethod
    def _load_from_db(cls) -> List[Dict]:
        """从数据库加载关键词筛选维度"""
        dimensions = AnalysisDimension.query.filter_by(
            category='super_positioning',
            sub_category='keyword_filter',
            is_active=True
        ).order_by(
            AnalysisDimension.weight.desc()  # 按权重降序
        ).all()

        return [
            {
                'name': d.name,
                'code': d.code,
                'description': d.description,
                'content_template': d.content_template or '',
                'weight': d.weight or 1.0,
                'icon': d.icon,
            }
            for d in dimensions
        ]

    @classmethod
    def get_keyword_filter_tiers(cls) -> List[Dict]:
        """
        获取关键词筛选维度（带缓存）
        缓存过期后自动重新加载
        """
        now = time.time()

        # 检查缓存是否有效
        if cls._cache is not None and (now - cls._cache_time) < cls.CACHE_TTL:
            return cls._cache

        # 重新加载
        cls._cache = cls._load_from_db()
        cls._cache_time = now

        return cls._cache

    @classmethod
    def get_weighted_context(cls, business_desc: str = '') -> str:
        """
        获取加权后的关键词筛选上下文（产品动态版）

        从 business_desc 提取产品名，动态注入到 content_template 占位符中。
        不再依赖硬编码产品类型列表。
        """
        tiers = cls.get_keyword_filter_tiers()

        if not tiers:
            return ''

        product_name = _extract_product_name(business_desc)
        region = cls._extract_region_from_desc(business_desc)

        # 构建替换字典（全部基于 business_desc 动态生成，反映新三盘结构）
        replacements = {
            'EXAMPLE_PRODUCT':       product_name,
            # ── 前置观望搜前种草盘（50%）──
            'EXAMPLE_COMPARE':      f'「{product_name}」和竞品对比有什么区别/哪个好',
            'EXAMPLE_CAUSE':        f'「{product_name}」为什么会涨价/质量不稳定什么原因',
            'EXAMPLE_UPSTREAM':     f'「{product_name}」用什么原料/怎么选材最放心',
            'EXAMPLE_PITFALL':       f'「{product_name}」有哪些坑/怎么分辨优劣',
            'EXAMPLE_PRICE':        f'「{product_name}」价格行情/报价多少合理',
            'EXAMPLE_SCENE_PAIN':   f'「{product_name}」有质量问题商家推诿怎么办',
            'EXAMPLE_SCENE_PROBLEM': f'「{product_name}」使用中出现问题了怎么处理',
            # ── 刚需痛点盘（30%）──
            'EXAMPLE_DIRECT':       f'「{product_name}」哪里定制/怎么购买',
            'EXAMPLE_DECISION':     f'「{product_name}」供应商靠谱吗/会不会坑人',
            'EXAMPLE_REASSURE':     f'「{product_name}」售后怎么样/长期合作放心吗',
            # ── 使用配套搜后种草盘（20%）──
            'EXAMPLE_SKILL':       f'「{product_name}」使用后怎么保存/有什么技巧',
            'EXAMPLE_TOOLS':       f'「{product_name}」用什么工具/需要哪些耗材',
            # ── 地域/长尾 ──
            'EXAMPLE_REGION_SERVICE': f'成都武侯区「{product_name}」哪里有卖',
            'EXAMPLE_LONGTAIL':       f'婚宴/企业场景「{product_name}」定制哪家好',
            'EXAMPLE_REGION':         region,
        }

        # 计算总权重
        total_weight = sum(t.get('weight', 1.0) for t in tiers)

        # 构建上下文
        context_parts = []
        for tier in tiers:
            template = tier.get('content_template', '')
            # 动态替换占位符
            for placeholder, value in replacements.items():
                template = template.replace(f'{{{placeholder}}}', value)
            context_parts.append(template)

        return '\n\n'.join(context_parts)

    @classmethod
    def _extract_region_from_desc(cls, desc: str) -> str:
        """从业务描述中提取地域词（如果有）"""
        import re
        # 常见地域词
        regions = [
            '北京', '上海', '广州', '深圳', '成都', '杭州', '武汉', '南京',
            '西安', '重庆', '天津', '苏州', '长沙', '郑州', '东莞', '青岛',
            '沈阳', '宁波', '昆明', '大连', '厦门', '合肥', '福州', '济南',
            '佛山', '泉州', '南宁', '长春', '哈尔滨', '石家庄',
        ]
        d = desc or ''
        for region in regions:
            if region in d:
                idx = d.find(region)
                # 提取地域 + 可能的后缀
                seg = d[idx:]
                m = re.match(r'([^\s，、；。]{2,8})(?:市|区|县|省)?', seg)
                if m:
                    return m.group(1)
                return region
        return '本地'  # 未检测到地域时默认

    @classmethod
    def get_tier_by_name(cls, name: str) -> Optional[Dict]:
        """根据名称获取特定维度"""
        tiers = cls.get_keyword_filter_tiers()
        for tier in tiers:
            if tier['name'] == name:
                return tier
        return None

    @classmethod
    def clear_cache(cls):
        """清除缓存，强制重新加载"""
        cls._cache = None
        cls._cache_time = 0


def get_keyword_filter_service() -> KeywordFilterService:
    """获取服务实例（静态方法，直接调用类方法）"""
    return KeywordFilterService


class QuestionGuideService:
    """问题引导词维度（超级定位 / question_guide）—— 带缓存"""

    _cache: Optional[List[Dict]] = None
    _cache_time: float = 0
    CACHE_TTL: int = 3600

    @classmethod
    def _load_from_db(cls) -> List[Dict]:
        dimensions = AnalysisDimension.query.filter_by(
            category='super_positioning',
            sub_category='question_guide',
            is_active=True,
        ).order_by(AnalysisDimension.weight.desc()).all()

        return [
            {
                'name': d.name,
                'code': d.code,
                'description': d.description,
                'content_template': d.content_template or '',
                'weight': d.weight or 1.0,
                'icon': d.icon,
            }
            for d in dimensions
        ]

    @classmethod
    def get_dimensions(cls) -> List[Dict]:
        now = time.time()
        if cls._cache is not None and (now - cls._cache_time) < cls.CACHE_TTL:
            return cls._cache
        cls._cache = cls._load_from_db()
        cls._cache_time = now
        return cls._cache

    @classmethod
    def get_weighted_context(cls, business_desc: str = '') -> str:
        """
        获取问题引导词上下文（兼容旧调用，business_desc 暂不影响）
        """
        tiers = cls.get_dimensions()
        if not tiers:
            return ''
        return '\n\n'.join(t['content_template'] for t in tiers if t.get('content_template'))

    @classmethod
    def clear_cache(cls):
        cls._cache = None
        cls._cache_time = 0
