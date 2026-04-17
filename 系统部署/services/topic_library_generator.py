"""
画像专属选题库生成服务 + GEO 六模式全绑定系统

核心原则：
- LLM 只负责生成：title、keywords、recommended_reason、scene_options、geo_mode、structure_rule
- 本地代码控制：GEO 模式枚举、三盘映射、阶段配比、分配逻辑、校验、兜底、缓存
- 每个选题强制归属一种 GEO 模式
- 按三盘比例分配 GEO 模式
- 后处理校验 GEO 模式合规性
"""

import json
import random
import logging
import uuid
import time
import threading
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from models.public_models import SavedPortrait, db

logger = logging.getLogger(__name__)

from services.template_config_service import template_config_service
from services.llm import get_llm_service


# =============================================================================
# GEO 六模式枚举库（100% 本地控制）
# =============================================================================

class GEOMode:
    """
    GEO 六模式枚举

    字段说明：
    - key: 英文标识
    - name: 中文名称
    - weight: 权重（按权重排序决定优先级）
    - title_rule: 标题生成规则（LLM 必须遵守）
    - structure_rule: 内容结构规则（LLM 必须遵守）
    - ban_patterns: 标题禁令正则列表
    - ban_phrases: 标题禁令词列表
    - compatible_types: 兼容的 type_key 列表
    """
    QA = 'qa'               # 问题-答案模式
    DEFINE = 'define'        # 定义-解释模式
    ARGUMENT = 'argument'    # 金句-论证模式
    FRAMEWORK = 'framework'  # 框架-工具模式
    LIST = 'list'            # 清单体
    HERO = 'hero'           # 英雄之旅


GEO_MODES = {
    # ── 1. 问题-答案模式（权重最高）─────────────────────────────────────────────
    GEOMode.QA: {
        'key': GEOMode.QA,
        'name': '问题-答案模式',
        'weight': 6,
        'title_rule': '标题必须是用户真实搜索的问题，格式：XX怎么办？/ XX怎么选？/ XX是什么？/ XX好不好？',
        'title_examples': [
            '桶装水有异味怎么办？',
            '酒店餐具破损怎么处理？',
            '高考志愿怎么填报最稳妥？',
            '豆芽批发怎么找靠谱供应商？',
        ],
        'structure_rule': '首段直接给答案，不需要铺垫。结构：答案开门见山 → 原因分析 → 具体方法 → 行动指引',
        'structure_template': '【开篇】直接给答案 | 【展开】原因拆解 | 【方法】具体步骤 | 【收尾】引导行动',
        'ban_patterns': [
            r'.*的正确认知',
            r'.*的底层逻辑',
            r'.*的真相',
            r'.*全面解析',
            r'.*完全指南',
            r'.*入门.*',
            r'春季.*|冬季.*|夏季.*',  # 季节拼接禁令
        ],
        'ban_phrases': ['正确认知', '底层逻辑', '真相', '全面解析', '完全指南', '原料', '供应链'],
        'compatible_types': ['pain_point', 'decision_encourage', 'cause', 'compare', 'pitfall', 'scene'],
    },

    # ── 2. 定义-解释模式 ───────────────────────────────────────────────────
    GEOMode.DEFINE: {
        'key': GEOMode.DEFINE,
        'name': '定义-解释模式',
        'weight': 5,
        'title_rule': '标题格式：什么是XX？/ XX是什么？/ 一文讲透XX / XX怎么选？',
        'title_examples': [
            '什么是真正的好桶装水？',
            '酒店陶瓷餐具修复是什么服务？',
            '高考志愿填报辅导怎么选？',
            '桶装水配送服务是什么？',
        ],
        'structure_rule': '结构：定义 → 比喻/类比 → 核心要素 → 案例说明',
        'structure_template': '【定义】XX是什么 | 【比喻】像YY一样 | 【要素】3个关键点 | 【案例】具体例子',
        'ban_patterns': [
            r'.*的正确认知',
            r'.*底层逻辑',
            r'.*真相',
            r'.*全面解析',
            r'春季.*|冬季.*|夏季.*',
        ],
        'ban_phrases': ['正确认知', '底层逻辑', '真相', '全面解析', '原料', '供应链'],
        'compatible_types': ['tutorial', 'upstream', 'cause', 'scene', 'region'],
    },

    # ── 3. 金句-论证模式 ─────────────────────────────────────────────────────
    GEOMode.ARGUMENT: {
        'key': GEOMode.ARGUMENT,
        'name': '金句-论证模式',
        'weight': 4,
        'title_rule': '标题格式：反常识金句开头，打破用户固有认知。格式：XX都错了！/ 别再XX了！/ 以为XX就行？',
        'title_examples': [
            '桶装水便宜就好？90%的人都选错了！',
            '别再被误导了！酒店餐具修复不是小事',
            '以为随便选就行？高考志愿填报3大误区',
            '酒店采购只看价格？难怪年年亏钱',
        ],
        'structure_rule': '结构：反常识金句 → 破（打破旧认知）→ 立（新认知） → 方案指引',
        'structure_template': '【金句】反常识开头 | 【破】打破旧认知 | 【立】建立新认知 | 【方案】具体行动',
        'ban_patterns': [
            r'.*的正确认知',
            r'.*底层逻辑',
            r'.*真相',
            r'.*全面解析',
            r'春季.*|冬季.*',
        ],
        'ban_phrases': ['正确认知', '底层逻辑', '真相', '全面解析', '原料', '供应链'],
        'compatible_types': ['rethink', 'pitfall', 'decision_encourage', 'compare'],
    },

    # ── 4. 框架-工具模式 ─────────────────────────────────────────────────────
    GEOMode.FRAMEWORK: {
        'key': GEOMode.FRAMEWORK,
        'name': '框架-工具模式',
        'weight': 3,
        'title_rule': '标题格式：框架名称 + 核心价值。格式：XX框架！3步搞定XX / XX工具，推荐收藏',
        'title_examples': [
            '酒店采购避坑框架！3步选出靠谱供应商',
            '高考志愿填报框架！一张表搞定所有选择',
            '桶装水选购框架！5分钟选出好水源',
            '餐厅食材采购框架！成本降低30%的秘密',
        ],
        'structure_rule': '结构：框架概述 → 工具/清单 → 操作步骤 → 自检清单',
        'structure_template': '【框架】是什么+解决什么问题 | 【工具】具体方法 | 【步骤】123操作 | 【自检】检查清单',
        'ban_patterns': [
            r'.*的正确认知',
            r'.*底层逻辑',
            r'.*全面解析',
            r'.*完全指南',
            r'春季.*|冬季.*',
        ],
        'ban_phrases': ['正确认知', '底层逻辑', '全面解析', '完全指南', '原料', '供应链'],
        'compatible_types': ['tutorial', 'upstream', 'skill', 'effect_proof', 'price'],
    },

    # ── 5. 清单体 ────────────────────────────────────────────────────────────
    GEOMode.LIST: {
        'key': GEOMode.LIST,
        'name': '清单体',
        'weight': 2,
        'title_rule': '标题格式：数字 + 结果导向。格式：X个XX / XX清单 / XX检查表 / XX指南',
        'title_examples': [
            '桶装水辨别指南！3步判断水质好坏',
            '酒店采购必看！5个坑千万别踩',
            '高考前必做清单！家长收藏',
            '桶装水配送协议检查清单',
        ],
        'structure_rule': '结构：数字开头 → 分点清单 → 每个要点一句话说明 → 总结收尾',
        'structure_template': '【数字】X个要点 | 【清单】逐条列出 | 【说明】每条一句话 | 【总结】核心建议',
        'ban_patterns': [
            r'.*的正确认知',
            r'.*底层逻辑',
            r'.*真相',
            r'春季.*|冬季.*',
        ],
        'ban_phrases': ['正确认知', '底层逻辑', '真相', '原料', '供应链'],
        'compatible_types': ['pitfall', 'skill', 'tutorial', 'upstream', 'effect_proof', 'price', 'seasonal', 'festival'],
    },

    # ── 6. 英雄之旅 ─────────────────────────────────────────────────────────
    GEOMode.HERO: {
        'key': GEOMode.HERO,
        'name': '英雄之旅',
        'weight': 1,
        'title_rule': '标题格式：真实案例故事开头。格式：XX的真实故事 / 一个XX的经历 / XX案例分享',
        'title_examples': [
            '一个酒店老板踩坑的真实故事',
            '客户退货3次才选对桶装水供应商',
            '高考志愿填报的真实案例分享',
            '餐饮老板选错豆芽供应商的血泪教训',
        ],
        'structure_rule': '结构：P（问题困境）→ C（冲突挑战）→ S（解决方案）→ R（结果启示）',
        'structure_template': '【P困境】用户遇到什么问题 | 【C冲突】核心矛盾是什么 | 【S方案】如何解决 | 【R启示】经验教训',
        'ban_patterns': [
            r'.*的正确认知',
            r'.*底层逻辑',
            r'.*全面解析',
        ],
        'ban_phrases': ['正确认知', '底层逻辑', '全面解析', '原料', '供应链'],
        'compatible_types': ['emotional', 'skill', 'scene', 'industry'],
    },
}

# GEO 权重排序（权重越高优先级越高）
GEO_WEIGHT_ORDER = sorted(GEO_MODES.keys(), key=lambda k: GEO_MODES[k]['weight'], reverse=True)

# type_key → 推荐 GEO 模式映射
TYPE_KEY_TO_GEO = {
    'compare':            [GEOMode.QA, GEOMode.ARGUMENT, GEOMode.DEFINE],
    'cause':             [GEOMode.QA, GEOMode.DEFINE, GEOMode.LIST],
    'upstream':          [GEOMode.DEFINE, GEOMode.FRAMEWORK, GEOMode.LIST],
    'pitfall':           [GEOMode.ARGUMENT, GEOMode.LIST, GEOMode.QA],
    'price':             [GEOMode.FRAMEWORK, GEOMode.LIST, GEOMode.DEFINE],
    'rethink':           [GEOMode.ARGUMENT, GEOMode.QA, GEOMode.HERO],
    'tutorial':          [GEOMode.DEFINE, GEOMode.FRAMEWORK, GEOMode.LIST],
    'scene':             [GEOMode.QA, GEOMode.HERO, GEOMode.DEFINE],
    'region':            [GEOMode.QA, GEOMode.DEFINE, GEOMode.LIST],
    'pain_point':        [GEOMode.QA, GEOMode.FRAMEWORK, GEOMode.LIST],
    'decision_encourage': [GEOMode.QA, GEOMode.ARGUMENT, GEOMode.FRAMEWORK],
    'effect_proof':      [GEOMode.FRAMEWORK, GEOMode.LIST, GEOMode.HERO],
    'skill':             [GEOMode.FRAMEWORK, GEOMode.LIST, GEOMode.HERO],
    'tools':             [GEOMode.LIST, GEOMode.FRAMEWORK, GEOMode.DEFINE],
    'industry':          [GEOMode.HERO, GEOMode.LIST, GEOMode.DEFINE],
    'seasonal':          [GEOMode.LIST, GEOMode.QA, GEOMode.DEFINE],
    'festival':          [GEOMode.LIST, GEOMode.QA, GEOMode.DEFINE],
    'emotional':         [GEOMode.HERO, GEOMode.ARGUMENT, GEOMode.QA],
}


class TopicLibraryGenerator:
    """
    选题库生成器 + GEO 六模式全绑定

    核心原则：
    - LLM 只生成内容：title、keywords、recommended_reason、scene_options、geo_mode、structure_rule
    - 所有规则由本地控制：GEO 模式枚举、三盘映射、阶段配比、分配逻辑、校验、兜底
    """

    # =============================================================================
    # 本地静态规则 - LLM 不参与计算
    # =============================================================================

    # 选题分类（严格对应三大需求底盘）
    TOPIC_TYPES = [
        # ① 前置观望搜前种草盘（50%，种草型）
        {'name': '对比选型类',     'key': 'compare',             'base': '前置观望种草盘',     'direction': '种草型', 'priority': 'P0'},
        {'name': '原因分析类',     'key': 'cause',               'base': '前置观望种草盘',     'direction': '种草型', 'priority': 'P1'},
        {'name': '上游科普类',     'key': 'upstream',             'base': '前置观望种草盘',     'direction': '种草型', 'priority': 'P1'},
        {'name': '避坑指南类',     'key': 'pitfall',             'base': '前置观望种草盘',     'direction': '种草型', 'priority': 'P1'},
        {'name': '行情价格类',     'key': 'price',               'base': '前置观望种草盘',     'direction': '种草型', 'priority': 'P2'},
        {'name': '认知颠覆类',     'key': 'rethink',             'base': '前置观望种草盘',     'direction': '种草型', 'priority': 'P2'},
        {'name': '知识教程类',     'key': 'tutorial',             'base': '前置观望种草盘',     'direction': '种草型', 'priority': 'P1'},
        {'name': '场景细分类',     'key': 'scene',               'base': '前置观望种草盘',     'direction': '种草型', 'priority': 'P2'},
        {'name': '地域精准类',     'key': 'region',              'base': '前置观望种草盘',     'direction': '种草型', 'priority': 'P3'},

        # ② 刚需痛点盘（30%，转化型）
        {'name': '痛点解决类',     'key': 'pain_point',          'base': '刚需痛点盘',         'direction': '转化型', 'priority': 'P0'},
        {'name': '决策安心类',     'key': 'decision_encourage',   'base': '刚需痛点盘',         'direction': '转化型', 'priority': 'P0'},
        {'name': '效果验证类',     'key': 'effect_proof',        'base': '刚需痛点盘',         'direction': '转化型', 'priority': 'P1'},

        # ③ 使用配套搜后种草盘（20%，种草型）
        {'name': '实操技巧类',     'key': 'skill',               'base': '使用配套搜后种草盘', 'direction': '种草型', 'priority': 'P1'},
        {'name': '工具耗材类',     'key': 'tools',              'base': '使用配套搜后种草盘', 'direction': '种草型', 'priority': 'P2'},
        {'name': '行业关联系列类', 'key': 'industry',            'base': '使用配套搜后种草盘', 'direction': '种草型', 'priority': 'P2'},
        {'name': '季节营销类',     'key': 'seasonal',            'base': '使用配套搜后种草盘', 'direction': '种草型', 'priority': 'P2'},
        {'name': '节日营销类',     'key': 'festival',            'base': '使用配套搜后种草盘', 'direction': '种草型', 'priority': 'P1'},
        {'name': '情感故事类',     'key': 'emotional',           'base': '使用配套搜后种草盘', 'direction': '种草型', 'priority': 'P3'},
    ]

    TYPE_KEY_MAP = {t['key']: t for t in TOPIC_TYPES}

    # 三套选题配比（内容阶段联动）- 本地控制
    STAGE_RATIO_MAP = {
        '起号阶段': {
            '前置观望种草盘':      0.90,
            '刚需痛点盘':          0.00,
            '使用配套搜后种草盘':   0.10,
            'description': '90%前置种草 + 0%刚需转化 + 10%使用配套',
        },
        '成长阶段': {
            '前置观望种草盘':      0.60,
            '刚需痛点盘':          0.15,
            '使用配套搜后种草盘':   0.25,
            'description': '60%前置种草 + 15%刚需转化 + 25%使用配套',
        },
        '成熟阶段': {
            '前置观望种草盘':      0.30,
            '刚需痛点盘':          0.50,
            '使用配套搜后种草盘':   0.20,
            'description': '30%前置种草 + 50%刚需转化 + 20%使用配套',
        },
    }

    # 底盘 → type_key 列表的本地映射
    BASE_TO_TYPES = {
        '前置观望种草盘':     [t['key'] for t in TOPIC_TYPES if t['base'] == '前置观望种草盘'],
        '刚需痛点盘':         [t['key'] for t in TOPIC_TYPES if t['base'] == '刚需痛点盘'],
        '使用配套搜后种草盘':  [t['key'] for t in TOPIC_TYPES if t['base'] == '使用配套搜后种草盘'],
    }

    # =============================================================================
    # 画像维度 → 选题类型映射（本地控制）
    # =============================================================================

    # 画像维度特征词（用于检测画像包含哪些维度）
    PORTRAIT_DIMENSION_KEYWORDS = {
        'identity': {
            'keywords': ['人群', '身份', '宝爸', '宝妈', '家长', '老人', '儿童', '学生', '孕妈', '产妇', '中老年', '新手', '过敏'],
            'dimension_name': '人群身份',
        },
        'pain_point': {
            'keywords': ['痛点', '问题', '困扰', '烦恼', '难受', '不适', '担心', '焦虑', '害怕', '不会', '不懂', '拉肚子', '便秘', '上火'],
            'dimension_name': '痛点需求',
        },
        'concern': {
            'keywords': ['顾虑', '担心', '害怕', '顾虑', '疑虑', '怕', '担忧', '不确定', '安全', '质量', '真假', '成分', '价格贵'],
            'dimension_name': '购买顾虑',
        },
        'scenario': {
            'keywords': ['场景', '时候', '情况', '高铁', '旅行', '旅游', '上班', '上学', '早餐', '睡前', '断奶', '辅食', '术后', '产后'],
            'dimension_name': '使用场景',
        },
    }

    # 画像维度 → 三盘优先映射
    DIMENSION_BASE_PRIORITY = {
        'identity': {
            'primary_base': '前置观望种草盘',
            'secondary_bases': ['使用配套搜后种草盘'],
            'preferred_type_keys': ['compare', 'tutorial', 'cause', 'upstream', 'scene'],
            'dimension_weight': 0.8,
        },
        'pain_point': {
            'primary_base': '刚需痛点盘',
            'secondary_bases': ['前置观望种草盘'],
            'preferred_type_keys': ['pain_point', 'decision_encourage', 'effect_proof', 'pitfall'],
            'dimension_weight': 0.9,
        },
        'concern': {
            'primary_base': '刚需痛点盘',
            'secondary_bases': ['前置观望种草盘'],
            'preferred_type_keys': ['decision_encourage', 'rethink', 'pitfall', 'cause'],
            'dimension_weight': 0.85,
        },
        'scenario': {
            'primary_base': '使用配套搜后种草盘',
            'secondary_bases': ['前置观望种草盘'],
            'preferred_type_keys': ['skill', 'seasonal', 'festival', 'scene', 'emotional'],
            'dimension_weight': 0.75,
        },
    }

    # =============================================================================
    # GEO 模式核心规则（100% 本地控制）
    # =============================================================================

    # 三盘 ↔ GEO 模式映射（固定比例）
    BASE_GEO_RATIO = {
        # 三盘内各 GEO 模式的固定比例（总和为 1.0）
        '前置观望种草盘': {
            GEOMode.QA:       0.30,   # 问题-答案模式（高权重，最常见）
            GEOMode.DEFINE:   0.25,   # 定义-解释模式
            GEOMode.LIST:     0.25,   # 清单体（种草型内容最适配）
            GEOMode.ARGUMENT: 0.10,   # 金句-论证模式
            GEOMode.FRAMEWORK: 0.07,  # 框架-工具模式
            GEOMode.HERO:     0.03,   # 英雄之旅（较少使用）
        },
        '刚需痛点盘': {
            GEOMode.QA:       0.35,   # 问题-答案模式（最适合转化）
            GEOMode.ARGUMENT: 0.25,   # 金句-论证模式（打消顾虑）
            GEOMode.FRAMEWORK: 0.25,  # 框架-工具模式（给出具体方案）
            GEOMode.DEFINE:   0.08,   # 定义-解释模式
            GEOMode.LIST:     0.05,   # 清单体
            GEOMode.HERO:     0.02,   # 英雄之旅
        },
        '使用配套搜后种草盘': {
            GEOMode.LIST:     0.35,   # 清单体（实用干货，易传播）
            GEOMode.HERO:     0.30,   # 英雄之旅（情感故事，易转发）
            GEOMode.FRAMEWORK: 0.20,  # 框架-工具模式
            GEOMode.QA:       0.08,   # 问题-答案模式
            GEOMode.DEFINE:   0.05,   # 定义-解释模式
            GEOMode.ARGUMENT: 0.02,   # 金句-论证模式
        },
    }

    # 账号阶段 ↔ GEO 模式配比（影响整体 GEO 分布）
    STAGE_GEO_RATIO_MAP = {
        '起号阶段': {
            # 起号阶段：重种草，轻转化，多用清单/QA/DEFINE
            GEOMode.QA:        0.30,
            GEOMode.DEFINE:    0.25,
            GEOMode.LIST:      0.25,
            GEOMode.ARGUMENT:  0.10,
            GEOMode.FRAMEWORK: 0.07,
            GEOMode.HERO:      0.03,
        },
        '成长阶段': {
            # 成长阶段：平衡种草和转化
            GEOMode.QA:        0.28,
            GEOMode.DEFINE:    0.18,
            GEOMode.LIST:      0.20,
            GEOMode.ARGUMENT:  0.15,
            GEOMode.FRAMEWORK: 0.12,
            GEOMode.HERO:      0.07,
        },
        '成熟阶段': {
            # 成熟阶段：重转化，多用 FRAMEWORK/ARGUMENT/QA
            GEOMode.QA:        0.30,
            GEOMode.ARGUMENT:  0.25,
            GEOMode.FRAMEWORK: 0.20,
            GEOMode.DEFINE:    0.12,
            GEOMode.LIST:      0.08,
            GEOMode.HERO:      0.05,
        },
    }

    # 缓存有效期（小时）
    CACHE_TTL_HOURS = {
        'basic': 24,
        'professional': 168,
        'enterprise': 720,
    }

    # 防抖锁
    _generation_locks: Dict[str, float] = {}
    _locks_lock = threading.Lock()

    # LLM 并发控制
    _semaphore = threading.Semaphore(3)

    def __init__(self):
        self.llm = get_llm_service()

    # ===========================================================================
    # 公开接口
    # ===========================================================================

    def generate(
        self,
        portrait_data: Dict,
        business_info: Dict,
        keyword_library: Dict = None,
        plan_type: str = 'professional',
        use_template: bool = True,
        topic_count: int = 20,
        portrait_id: Optional[int] = None,
        content_stage: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        生成选题库（简化版）

        核心流程：
        1. 缓存检查 → 直接返回
        2. 防抖检查（5分钟）
        3. 调用 LLM → 生成选题（只返回核心字段）
        4. 本地分配 type_key（三盘比例）
        5. 兜底补全

        注意：geo_mode 和 scene_options 在内容生成时动态确定
        """
        try:
            # ── 1. 缓存检查 ──────────────────────────────
            if portrait_id:
                portrait = SavedPortrait.query.get(portrait_id)
                if portrait and not portrait.topic_library_expired:
                    logger.info("[TopicLibraryGenerator] 命中缓存，跳过生成 portrait_id=%s", portrait_id)
                    return {
                        'success': True,
                        'topic_library': portrait.topic_library,
                        'tokens_used': 0,
                        '_meta': {'from_cache': True},
                    }
                if portrait and not content_stage:
                    content_stage = portrait.content_stage or '成长阶段'

            # ── 2. 防抖检查（5分钟） ────────────────────
            if portrait_id and user_id:
                lock_key = f"{user_id}:{portrait_id}"
                with self._locks_lock:
                    last_time = self._generation_locks.get(lock_key, 0)
                    if time.time() - last_time < 300:
                        logger.info("[TopicLibraryGenerator] 防抖命中 portrait_id=%s", portrait_id)
                        return {
                            'success': False,
                            'error': '选题库正在生成中或刚刚生成完成，请5分钟后再试',
                            '_meta': {'from_debounce': True},
                        }
                    self._generation_locks[lock_key] = time.time()

            # ── 3. 防御性检查 ───────────────────────────
            if not isinstance(portrait_data, dict):
                portrait_data = {}
            if not isinstance(business_info, dict):
                business_info = {}

            # ── 4. 获取阶段配置 ─────────────────────────
            stage = content_stage or '成长阶段'
            stage_config = self.STAGE_RATIO_MAP.get(stage, self.STAGE_RATIO_MAP['成长阶段']).copy()
            logger.info("[TopicLibraryGenerator] 阶段: %s | 三盘: %s",
                        stage, stage_config['description'])

            # ── 4.1 画像维度分析 → 调整三盘配比 ───────────
            portrait_dimensions = self._analyze_portrait_dimensions(portrait_data)
            if portrait_dimensions:
                stage_config = self._adjust_base_ratio_by_portrait(
                    portrait_data, portrait_dimensions, stage_config, topic_count
                )
                logger.info("[TopicLibraryGenerator] 画像维度: %s | 调整后三盘: %s",
                           portrait_dimensions, stage_config.get('_adjusted_description', ''))

            # ── 5. 构建上下文 ───────────────────────────
            context = self._build_context(portrait_data, business_info, keyword_library)

            # ── 6. 构建 LLM 提示词 ───────────────────
            prompt = self._build_llm_prompt(context, topic_count, stage)
            system_msg = self._build_system_prompt()
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ]

            # ── 7. 调用 LLM（带并发控制） ──────────────
            with self._semaphore:
                logger.info("[TopicLibraryGenerator] 画像: 身份=%s, 痛点=%s",
                            context.get('目标客户身份', ''), context.get('核心痛点', ''))
                response = self.llm.chat(messages)
                logger.info("[TopicLibraryGenerator] LLM响应长度=%d", len(response))

            # ── 8. 7层降级 JSON 解析 ───────────────────
            parsed_topics = self._parse_response_7layer(response)
            logger.info("[TopicLibraryGenerator] 解析得到 %d 条", len(parsed_topics))

            # ── 9. 本地分配 type_key（三盘比例 + 画像维度） ────────
            typed_topics = self._assign_type_keys(
                parsed_topics, stage_config, topic_count, portrait_dimensions
            )

            # ── 10. 兜底补全 ────────────────────────────
            filled_topics = self._fill_missing_topics(
                typed_topics, topic_count, portrait_data, stage_config, business_info
            )

            # ── 11. 组装最终结构 ───────────────────────
            # 排除非底盘字段
            result_base_ratio = {
                k: v for k, v in stage_config.items()
                if k in ('前置观望种草盘', '刚需痛点盘', '使用配套搜后种草盘')
            }
            result = {
                'topics': filled_topics,
                'by_type': self._count_by_type(filled_topics),
                'priorities': self._count_by_priority(filled_topics),
                'stage': stage,
                'base_ratio': result_base_ratio,
                'generated_at': datetime.utcnow().isoformat(),
                '_portrait_dimensions': portrait_dimensions,
            }

            return {
                'success': True,
                'topic_library': result,
                'tokens_used': self._estimate_tokens(prompt, response),
                '_meta': {
                    'plan_type': plan_type,
                    'used_template': use_template,
                    'based_on_keywords': bool(keyword_library),
                    'content_stage': stage,
                }
            }

        except Exception as e:
            import sys, traceback
            print(f"[DEBUG TopicLibraryGenerator] === EXCEPTION ===", file=sys.stderr)
            print(f"[DEBUG] type: {type(e).__name__}, msg: {str(e)[:500]}", file=sys.stderr)
            print(f"[DEBUG] traceback:\n{traceback.format_exc()}", file=sys.stderr)
            print(f"[DEBUG] === END ===", file=sys.stderr)
            error_str = str(e)
            if len(error_str) > 300:
                error_str = error_str[:300] + '...'
            logger.error("[TopicLibraryGenerator] Error: " + error_str)
            return {'success': False, 'error': error_str}

    # ===========================================================================
    # GEO 模式分配（核心规则，全部本地计算）
    # ===========================================================================

    def _assign_geo_modes(
        self,
        topics: List[Dict],
        stage_config: Dict,
        stage_geo_config: Dict,
        topic_count: int,
    ) -> List[Dict]:
        """
        本地按三盘比例 + 阶段配比分配 GEO 模式

        分配策略：
        1. 先按三盘内 GEO 比例分配
        2. 再参考账号阶段 GEO 配比微调
        3. 确保每个选题的 GEO 与 type_key 兼容
        """
        if not topics:
            return topics

        # 计算各底盘应分配的选题数
        base_counts = {}
        for base_name, ratio in stage_config.items():
            if base_name == 'description':
                continue
            count = int(round(ratio * topic_count))
            base_counts[base_name] = count

        # 调整总数
        total_assigned = sum(base_counts.values())
        if total_assigned != topic_count:
            diff = topic_count - total_assigned
            base_counts['前置观望种草盘'] = base_counts.get('前置观望种草盘', 0) + diff

        logger.info("[TopicLibraryGenerator] GEO分配 - 三盘数量: %s", base_counts)

        # 按底盘分配 GEO 模式
        result = []
        base_assigned = {base: 0 for base in base_counts}

        for topic in topics:
            if len(result) >= topic_count:
                break

            base = topic.get('base', '前置观望种草盘')
            type_key = topic.get('type_key', '')

            # 获取该底盘的 GEO 比例
            base_geo_ratios = self.BASE_GEO_RATIO.get(base, {})

            # 根据 type_key 获取兼容的 GEO 模式
            compatible_geos = TYPE_KEY_TO_GEO.get(type_key, list(GEO_MODES.keys()))

            # 按比例随机选择 GEO 模式
            chosen_geo = self._select_geo_by_ratio(base_geo_ratios, compatible_geos, stage_geo_config)

            # 获取 GEO 详细信息
            geo_info = GEO_MODES.get(chosen_geo, GEO_MODES[GEOMode.QA])

            topic['geo_mode'] = chosen_geo
            topic['geo_mode_name'] = geo_info['name']
            topic['title_rule'] = geo_info['title_rule']
            topic['structure_rule'] = geo_info['structure_rule']
            topic['weight'] = geo_info['weight']

            result.append(topic)

        return result

    def _select_geo_by_ratio(
        self,
        base_geo_ratios: Dict[str, float],
        compatible_geos: List[str],
        stage_geo_config: Dict[str, float],
    ) -> str:
        """
        按比例随机选择 GEO 模式

        策略：
        1. 优先从兼容的 GEO 模式中选择
        2. 结合底盘比例（70%权重）和阶段比例（30%权重）计算最终概率
        """
        # 构建候选池，每个 GEO 的最终概率
        candidates = {}
        for geo_key, base_ratio in base_geo_ratios.items():
            if geo_key not in compatible_geos:
                continue
            stage_ratio = stage_geo_config.get(geo_key, 0.1)
            # 混合比例：底盘70% + 阶段30%
            final_ratio = base_ratio * 0.7 + stage_ratio * 0.3
            candidates[geo_key] = final_ratio

        if not candidates:
            # 兜底：返回权重最高的兼容模式
            for geo in compatible_geos:
                if geo in GEO_MODES:
                    return geo
            return GEOMode.QA

        # 按概率随机选择
        geo_keys = list(candidates.keys())
        ratios = list(candidates.values())
        total = sum(ratios)
        probs = [r / total for r in ratios]

        return random.choices(geo_keys, weights=probs, k=1)[0]

    # ===========================================================================
    # 后处理 GEO 校验
    # ===========================================================================

    def _validate_and_fix_geo(
        self,
        topics: List[Dict],
        stage_geo_config: Dict[str, float],
    ) -> List[Dict]:
        """
        后处理 GEO 校验（100% 本地）

        校验规则：
        1. 检查是否有 geo_mode，缺失则自动补为 qa（最高权重）
        2. 检查标题是否符合 title_rule（禁令正则），违规则自动修正
        3. 检查 structure_rule 是否匹配 GEO 模式，不匹配则覆盖
        4. 注入完整的 GEO 规则（title_rule、structure_rule）
        """
        validated = []

        for topic in topics:
            if not isinstance(topic, dict):
                continue

            # ── 1. 校验 geo_mode ────────────────────
            geo_mode = topic.get('geo_mode', '')
            if not geo_mode or geo_mode not in GEO_MODES:
                # 自动补为 qa（最高权重模式）
                geo_mode = GEOMode.QA
                topic['geo_mode'] = geo_mode

            geo_info = GEO_MODES.get(geo_mode, GEO_MODES[GEOMode.QA])
            topic['geo_mode_name'] = geo_info['name']
            topic['weight'] = geo_info['weight']

            # ── 2. 校验标题禁令 ──────────────────────
            title = topic.get('title', '')
            if title:
                ban_triggered = False
                for pattern in geo_info['ban_patterns']:
                    if re.search(pattern, title):
                        ban_triggered = True
                        break
                for phrase in geo_info['ban_phrases']:
                    if phrase in title:
                        ban_triggered = True
                        break

                if ban_triggered:
                    # 自动修正标题（按 GEO 模式重新生成）
                    topic['title'] = self._fix_title_by_geo(title, geo_mode, topic)
                    logger.info("[TopicLibraryGenerator] 标题违禁已修正: %s → %s", title[:20], topic['title'][:20])

            # ── 3. 注入 GEO 规则 ─────────────────────
            topic['title_rule'] = geo_info['title_rule']
            topic['structure_rule'] = geo_info['structure_rule']

            # ── 4. 注入 GEO 结构模板 ──────────────────
            topic['structure_template'] = geo_info.get('structure_template', '')

            validated.append(topic)

        return validated

    def _fix_title_by_geo(self, title: str, geo_mode: str, topic: Dict) -> str:
        """
        按 GEO 模式修正违禁标题

        策略：从标题中提取核心关键词，按 GEO 模式的标题规则重新组装
        """
        geo_info = GEO_MODES.get(geo_mode, GEO_MODES[GEOMode.QA])
        type_key = topic.get('type_key', '')
        pain_point = topic.get('title', '')[:20]  # 用原标题作为痛点参考

        # 从原标题提取关键词（去除违禁词）
        import re
        keywords = re.findall(r'[\u4e00-\u9fa5]{2,8}', title)
        keywords = [k for k in keywords if k not in geo_info['ban_phrases']]
        core = keywords[0] if keywords else pain_point

        # 按 GEO 模式生成新标题
        if geo_mode == GEOMode.QA:
            return self._clean_title(f'{core}怎么办？教你一招搞定')
        elif geo_mode == GEOMode.DEFINE:
            return self._clean_title(f'什么是{core}？一文讲透')
        elif geo_mode == GEOMode.ARGUMENT:
            return self._clean_title(f'别再误解了！{core}其实没那么复杂')
        elif geo_mode == GEOMode.FRAMEWORK:
            return self._clean_title(f'{core}处理框架！3步搞定')
        elif geo_mode == GEOMode.LIST:
            return self._clean_title(f'{core}处理清单！5个要点收藏')
        elif geo_mode == GEOMode.HERO:
            return self._clean_title(f'一个真实案例看懂{core}')
        else:
            return self._clean_title(f'{core}怎么处理？')

    # ===========================================================================
    # 按 GEO 权重重排优先级
    # ===========================================================================

    def _rerank_by_geo_weight(self, topics: List[Dict]) -> List[Dict]:
        """
        按 GEO 权重重排优先级

        规则：按 GEO 权重排序（qa>list>define>framework>argument>hero）
        同权重内保持原有优先级顺序
        """
        if not topics:
            return topics

        # GEO 权重顺序
        geo_weight_order = GEO_WEIGHT_ORDER  # 已按权重降序排列

        # 优先级映射
        priority_order = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}

        def sort_key(topic):
            geo = topic.get('geo_mode', '')
            geo_idx = geo_weight_order.index(geo) if geo in geo_weight_order else len(geo_weight_order)
            priority = priority_order.get(topic.get('priority', 'P2'), 2)
            return (geo_idx, priority)

        return sorted(topics, key=sort_key)

    # ===========================================================================
    # LLM 提示词构建
    # ===========================================================================

    def _build_system_prompt(self) -> str:
        """构建 System Prompt"""
        return f"""你是一位抖音爆款选题策划专家。

【核心要求】
1. 选题必须围绕用户真实搜索需求，不能是业务介绍
2. 标题必须是用户真实搜索的问题格式
3. 关键词必须从用户视角出发，反映用户的搜索习惯

【绝对禁止】
- 禁止："XX的正确认知"、"XX的底层逻辑"、"XX的真相"
- 禁止："XX全面解析"、"XX完全指南"
- 禁止：季节拼接（春季XX、冬季XX → 改为具体问题描述）
- 禁止：原料/供应链（非制造业禁止出现）
- 禁止：业务描述开头拼接（如"高考志愿填报辅导XXX"）

【JSON格式约束】
1. 所有字符串值必须使用英文双引号 "
2. keywords 数组内的每个关键词也必须用英文双引号包裹
3. 输出必须是可直接被 Python json.loads() 解析的有效 JSON"""

    def _build_llm_prompt(
        self,
        context: Dict,
        topic_count: int = 20,
        stage: str = '成长阶段',
    ) -> str:
        """
        构建 User Prompt（选题库生成）

        只生成选题核心信息，其他字段由本地计算或内容生成时动态确定：
        - geo_mode → 内容生成时根据 type_key 映射
        - scene_options → 内容生成时根据 title + portrait_data 动态构建
        """
        return f"""你是一位抖音爆款选题策划专家。

请为以下业务生成{topic_count}个选题，严格按三盘分配：

=== 三盘分配比例（强制）===
① 前置观望种草盘（50%）：对比选型类、原因分析类、避坑指南类、行情价格类、认知颠覆类
② 刚需痛点盘（30%）：痛点解决类、决策安心类
③ 使用配套搜后种草盘（20%）：实操技巧类、季节营销类、节日营销类

=== 账号阶段：{stage} ===
起号阶段：重种草，刚需盘占比低
成长阶段：平衡种草和转化
成熟阶段：重转化，刚需盘占比高

=== 业务信息（必须严格围绕这些信息生成选题）===
行业：{context['行业']}
业务：{context['业务描述']}
客户：{context['目标客户']}
痛点：{context['核心痛点']}
顾虑：{context['核心顾虑']}

=== 画像视角约束 ===
画像摘要：{context['portrait_summary'] or '（无）'}
用户视角：{context['用户视角描述'] or '（无）'}
买单方视角：{context['买单方视角描述'] or '（无）'}

=== 实时上下文 ===
当前季节：{context['当前季节']}（{context['月份名称']}）
当前节日：{context['当前节日']}

=== 关键词库（选题必须围绕这些关键词）===
{context.get('关键词库', '（无关键词库数据）')}

=== 选题格式禁令（严格遵守）===
1. ❌ "XX的正确认知" → ✅ "XX怎么办？"
2. ❌ "XX的底层逻辑" → ✅ "什么是XX？"
3. ❌ "XX的真相" → ✅ "别再误解了！XX"
4. ❌ "XX全面解析" → ✅ "XX清单！3个要点"
5. ❌ "春季XX/冬季XX" → ✅ "高考出分前家长要做什么"
6. ❌ "XX原料/供应链"（非制造业禁止）

=== LLM 输出字段（只生成这4个核心字段）===
1. **title**：选题标题（必须包含业务关键词，必须是用户真实搜索的问题）
2. **keywords**：关键词列表（必须包含业务相关词）
3. **recommended_reason**：推荐理由（为什么这个选题好）
4. **type_key**：选题类型键（从以下列表选择1个）：
   - compare：对比选型类
   - cause：原因分析类
   - pitfall：避坑指南类
   - price：行情价格类
   - rethink：认知颠覆类
   - pain_point：痛点解决类
   - decision_encourage：决策安心类
   - skill：实操技巧类
   - seasonal：季节营销类
   - festival：节日营销类

=== JSON输出格式（严格JSON，不要markdown代码块）===
```json
[
  {{
    "title": "选题标题（必须包含业务关键词）",
    "keywords": ["关键词1", "关键词2"],
    "recommended_reason": "推荐理由",
    "type_key": "pain_point"
  }},
  ...共{topic_count}条
]
```

请严格按上述JSON格式输出，直接返回JSON数组，不要有其他文字说明："""

    # ===========================================================================
    # 本地上下文构建
    # ===========================================================================

    def _build_context(
        self,
        portrait_data: Dict,
        business_info: Dict,
        keyword_library: Dict = None,
    ) -> Dict:
        """构建模板变量上下文（本地计算）"""
        if not isinstance(portrait_data, dict):
            portrait_data = {}
        if not isinstance(business_info, dict):
            business_info = {}
        if not isinstance(keyword_library, dict):
            keyword_library = None

        identity_tags = portrait_data.get('identity_tags', {})
        user_persp = portrait_data.get('user_perspective', {})
        buyer_persp = portrait_data.get('buyer_perspective', {})

        identity = portrait_data.get('identity', '')
        if not identity:
            identity = identity_tags.get('user', '') or identity_tags.get('buyer', '')

        pain_point = portrait_data.get('pain_point', '')
        if not pain_point:
            pain_point = user_persp.get('problem', '')
            if not pain_point:
                summary = portrait_data.get('portrait_summary', '')
                if summary and '，' in summary:
                    pain_point = summary.split('，')[0]

        concern = portrait_data.get('concern', '')
        if not concern:
            concern = buyer_persp.get('obstacles', '')
            if not concern:
                concern = buyer_persp.get('psychology', '')

        scenario = portrait_data.get('scenario', '')
        if not scenario:
            scenario = user_persp.get('current_state', '')

        portrait_summary = portrait_data.get('portrait_summary', '')
        user_perspective_text = portrait_data.get('user_perspective', {}).get('problem', '')
        buyer_perspective_text = (
            portrait_data.get('buyer_perspective', {}).get('obstacles', '') or
            portrait_data.get('buyer_perspective', {}).get('psychology', '')
        )
        user_current_state = user_persp.get('current_state', '')

        keywords_text = ''
        if keyword_library:
            all_kw = []
            for cat in keyword_library.get('categories', []):
                if isinstance(cat, dict):
                    kws = cat.get('keywords', [])
                    if isinstance(kws, list):
                        all_kw.extend(kws[:5])
            keywords_text = ', '.join(all_kw[:50])

        realtime = {}
        try:
            realtime = template_config_service.get_realtime_context()
        except Exception:
            pass

        return {
            '目标客户身份': self._escape(identity),
            '核心痛点': self._escape(pain_point),
            '核心顾虑': self._escape(concern),
            '使用场景': self._escape(scenario),
            'portrait_summary': self._escape(portrait_summary),
            '用户视角描述': self._escape(user_perspective_text),
            '买单方视角描述': self._escape(buyer_perspective_text),
            '用户当前状态': self._escape(user_current_state),
            '业务描述': self._escape(business_info.get('business_description', '')),
            '行业': self._escape(business_info.get('industry', '')),
            '产品': self._escape(', '.join(business_info.get('products', []))),
            '地域': self._escape(business_info.get('region', '')),
            '目标客户': self._escape(business_info.get('target_customer', '')),
            '当前季节': self._escape(realtime.get('当前季节', '')),
            '月份名称': self._escape(realtime.get('月份名称', '')),
            '季节消费特点': self._escape(realtime.get('季节消费特点', '')),
            '当前节日': self._escape(realtime.get('当前节日', '无')),
            '关键词库': self._escape(keywords_text),
        }

    # ===========================================================================
    # 画像维度分析（本地计算）
    # ===========================================================================

    def _analyze_portrait_dimensions(self, portrait_data: Dict) -> Dict[str, float]:
        """
        分析画像数据包含哪些维度及其强度

        Returns:
            Dict: {dimension: score}，如 {'identity': 0.8, 'pain_point': 0.6}
        """
        if not portrait_data:
            return {}

        dimensions = {}

        # 提取画像中的关键文本（用于关键词匹配）
        portrait_text = ' '.join([
            str(portrait_data.get('identity', '') or ''),
            str(portrait_data.get('pain_point', '') or ''),
            str(portrait_data.get('concern', '') or ''),
            str(portrait_data.get('scenario', '') or ''),
            str(portrait_data.get('portrait_summary', '') or ''),
            # 包含子字段
            str(portrait_data.get('user_perspective', {}).get('problem', '') or ''),
            str(portrait_data.get('buyer_perspective', {}).get('obstacles', '') or ''),
            str(portrait_data.get('buyer_perspective', {}).get('psychology', '') or ''),
        ]).lower()

        # 检测每个维度
        for dim_key, dim_config in self.PORTRAIT_DIMENSION_KEYWORDS.items():
            score = 0.0
            for keyword in dim_config['keywords']:
                if keyword.lower() in portrait_text:
                    score += 0.3
            # 直接字段存在时加分
            if portrait_data.get(dim_key):
                score += 0.4
            # 子字段检查
            if dim_key == 'identity' and portrait_data.get('identity_tags'):
                score += 0.3
            if dim_key == 'concern' and portrait_data.get('barriers'):
                score += 0.3

            if score > 0:
                dimensions[dim_key] = min(score, 1.0)

        return dimensions

    def _adjust_base_ratio_by_portrait(
        self,
        portrait_data: Dict,
        portrait_dimensions: Dict[str, float],
        stage_config: Dict,
        topic_count: int,
    ) -> Dict:
        """
        根据画像维度调整三盘配比

        策略：
        1. 分析画像的主要维度特征
        2. 根据维度强度调整三盘比例
        3. 优先维度获得更多选题配额
        """
        if not portrait_dimensions:
            stage_config['_adjusted_description'] = stage_config.get('description', '')
            return stage_config

        # 找出最强维度
        strongest_dim = max(portrait_dimensions.items(), key=lambda x: x[1])
        dim_key = strongest_dim[0]
        dim_score = strongest_dim[1]

        # 复制配置，避免修改原始数据
        adjusted = stage_config.copy()

        # 获取维度配置
        dim_config = self.DIMENSION_BASE_PRIORITY.get(dim_key, {})

        if not dim_config:
            return adjusted

        # 根据维度强度和账号阶段调整配比
        primary_base = dim_config['primary_base']
        secondary_base = dim_config['secondary_bases'][0] if dim_config['secondary_bases'] else '前置观望种草盘'

        # 获取当前阶段的基础配比
        base_ratio = {
            k: v for k, v in adjusted.items()
            if k not in ('description', '_adjusted_description')
        }

        # 根据维度强度调整
        adjustment_factor = dim_score * 0.3  # 最大调整30%

        if dim_key == 'pain_point':
            # 痛点维度：增加刚需痛点盘
            base_ratio['刚需痛点盘'] = min(0.50, base_ratio.get('刚需痛点盘', 0.15) + adjustment_factor)
            base_ratio['前置观望种草盘'] = max(0.30, base_ratio.get('前置观望种草盘', 0.60) - adjustment_factor * 0.5)
            base_ratio['使用配套搜后种草盘'] = max(0.15, base_ratio.get('使用配套搜后种草盘', 0.25) - adjustment_factor * 0.5)

        elif dim_key == 'concern':
            # 顾忌维度：增加刚需痛点盘（决策安心类）
            base_ratio['刚需痛点盘'] = min(0.45, base_ratio.get('刚需痛点盘', 0.15) + adjustment_factor)
            base_ratio['前置观望种草盘'] = max(0.35, base_ratio.get('前置观望种草盘', 0.60) - adjustment_factor * 0.3)
            base_ratio['使用配套搜后种草盘'] = base_ratio.get('使用配套搜后种草盘', 0.25)

        elif dim_key == 'identity':
            # 人群维度：增加前置观望种草盘（对比选型、知识教程）
            base_ratio['前置观望种草盘'] = min(0.80, base_ratio.get('前置观望种草盘', 0.60) + adjustment_factor)
            base_ratio['刚需痛点盘'] = max(0.05, base_ratio.get('刚需痛点盘', 0.15) - adjustment_factor * 0.3)
            base_ratio['使用配套搜后种草盘'] = base_ratio.get('使用配套搜后种草盘', 0.25)

        elif dim_key == 'scenario':
            # 场景维度：增加使用配套搜后种草盘
            base_ratio['使用配套搜后种草盘'] = min(0.50, base_ratio.get('使用配套搜后种草盘', 0.25) + adjustment_factor)
            base_ratio['前置观望种草盘'] = max(0.30, base_ratio.get('前置观望种草盘', 0.60) - adjustment_factor * 0.5)
            base_ratio['刚需痛点盘'] = base_ratio.get('刚需痛点盘', 0.15)

        # 归一化，确保总和为1
        total = sum(base_ratio.values())
        if total > 0 and abs(total - 1.0) > 0.01:
            for k in base_ratio:
                base_ratio[k] = base_ratio[k] / total

        # 更新配置
        adjusted.update(base_ratio)
        adjusted['_adjusted_description'] = (
            f"画像维度调整({dim_config['dimension_name']}={dim_score:.1f}): "
            f"前置={base_ratio.get('前置观望种草盘', 0):.0%}, "
            f"刚需={base_ratio.get('刚需痛点盘', 0):.0%}, "
            f"配套={base_ratio.get('使用配套搜后种草盘', 0):.0%}"
        )
        adjusted['_portrait_dimension'] = dim_key
        adjusted['_dimension_score'] = dim_score

        return adjusted

    def _get_preferred_type_keys_by_dimension(self, portrait_dimensions: Dict[str, float]) -> List[str]:
        """
        根据画像维度获取优先的type_key列表
        """
        preferred_keys = []

        # 按维度权重排序
        sorted_dims = sorted(
            portrait_dimensions.items(),
            key=lambda x: self.DIMENSION_BASE_PRIORITY.get(x[0], {}).get('dimension_weight', 0) * x[1],
            reverse=True
        )

        for dim_key, score in sorted_dims:
            dim_config = self.DIMENSION_BASE_PRIORITY.get(dim_key, {})
            preferred_keys.extend(dim_config.get('preferred_type_keys', []))

        # 去重但保留顺序
        seen = set()
        unique_keys = []
        for key in preferred_keys:
            if key not in seen:
                seen.add(key)
                unique_keys.append(key)

        return unique_keys

    # ===========================================================================
    # type_key 分配（本地计算）
    # ===========================================================================

    def _assign_type_keys(
        self,
        topics: List[Dict],
        stage_config: Dict,
        topic_count: int = 20,
        portrait_dimensions: Dict = None,
    ) -> List[Dict]:
        """本地按三盘比例分配 type_key"""
        if not topics:
            return topics

        base_keys = {
            '前置观望种草盘':     [t['key'] for t in self.TOPIC_TYPES if t['base'] == '前置观望种草盘'],
            '刚需痛点盘':         [t['key'] for t in self.TOPIC_TYPES if t['base'] == '刚需痛点盘'],
            '使用配套搜后种草盘':  [t['key'] for t in self.TOPIC_TYPES if t['base'] == '使用配套搜后种草盘'],
        }

        # 获取调整后的三盘配比（排除非底盘字段）
        base_ratio = {
            k: v for k, v in stage_config.items()
            if k in base_keys
        }

        base_counts = {}
        for base_name, ratio in base_ratio.items():
            count = int(round(ratio * topic_count))
            base_counts[base_name] = count

        total_assigned = sum(base_counts.values())
        if total_assigned != topic_count:
            base_counts['前置观望种草盘'] = base_counts.get('前置观望种草盘', 0) + (topic_count - total_assigned)

        result = []
        base_assignments = {base: 0 for base in base_counts}
        used_keys = set()

        # 获取画像维度优先的type_key
        preferred_keys_by_dim = []
        if portrait_dimensions:
            preferred_keys_by_dim = self._get_preferred_type_keys_by_dimension(portrait_dimensions)

        for topic in topics:
            if len(result) >= topic_count:
                break

            assigned = False
            for base_name, count in base_counts.items():
                if base_assignments[base_name] >= count:
                    continue

                # 优先从画像维度推荐的type_key中选择
                available_keys = [k for k in base_keys[base_name] if k not in used_keys]

                # 如果有画像维度推荐的key，优先使用
                if preferred_keys_by_dim:
                    dim_preferred = [k for k in preferred_keys_by_dim if k in available_keys]
                    if dim_preferred:
                        available_keys = dim_preferred

                if not available_keys:
                    available_keys = base_keys[base_name]

                chosen_key = random.choice(available_keys)
                type_info = self.TYPE_KEY_MAP[chosen_key]

                topic['type_key'] = chosen_key
                topic['type_name'] = type_info['name']
                topic['priority'] = type_info['priority']
                topic['base'] = type_info['base']
                topic['content_direction'] = type_info['direction']
                topic['source'] = self._get_source_by_type(chosen_key)
                topic['id'] = str(uuid.uuid4())
                topic['generation_count'] = 0
                topic['created_at'] = datetime.utcnow().isoformat()
                topic['title'] = self._clean_title(topic.get('title', ''))

                result.append(topic)
                base_assignments[base_name] += 1
                used_keys.add(chosen_key)
                assigned = True
                break

            if not assigned:
                chosen_key = random.choice(base_keys['前置观望种草盘'])
                type_info = self.TYPE_KEY_MAP[chosen_key]
                topic['type_key'] = chosen_key
                topic['type_name'] = type_info['name']
                topic['priority'] = type_info['priority']
                topic['base'] = type_info['base']
                topic['content_direction'] = type_info['direction']
                topic['source'] = self._get_source_by_type(chosen_key)
                topic['id'] = str(uuid.uuid4())
                topic['generation_count'] = 0
                topic['created_at'] = datetime.utcnow().isoformat()
                topic['title'] = self._clean_title(topic.get('title', ''))
                result.append(topic)

        return result

    def _get_source_by_type(self, type_key: str) -> str:
        """根据 type_key 返回来源说明"""
        source_map = {
            'compare':            '对比选型系列',
            'cause':             '原因分析系列',
            'upstream':          '上游科普系列',
            'pitfall':           '避坑指南系列',
            'price':             '行情价格系列',
            'rethink':           '认知颠覆系列',
            'tutorial':          '知识教程系列',
            'scene':             '场景细分系列',
            'region':            '地域精准系列',
            'pain_point':         '刚需痛点盘',
            'decision_encourage':  '刚需痛点盘',
            'effect_proof':      '刚需痛点盘',
            'skill':             '使用配套盘',
            'tools':             '使用配套盘',
            'industry':          '使用配套盘',
            'seasonal':          '使用配套盘',
            'festival':          '使用配套盘',
            'emotional':          '使用配套盘',
        }
        return source_map.get(type_key, '选题推荐')

    # ===========================================================================
    # 7层降级 JSON 解析
    # ===========================================================================

    def _parse_response_7layer(self, response: str) -> List[Dict]:
        """7层降级 JSON 解析"""
        import json as _json

        try:
            clean = response.strip()
            if clean.startswith('```json'):
                clean = clean[7:]
            elif clean.startswith('```'):
                clean = clean[3:]
            if clean.endswith('```'):
                clean = clean[:-3]
            clean = clean.strip()

            # 第1层：直接解析
            try:
                result = _json.loads(clean)
                if isinstance(result, list) and len(result) > 0:
                    logger.info("[TopicLibraryGenerator] ✓ 第1层直接解析，得到 %d 条", len(result))
                    return [self._normalize_llm_item(t) for t in result if isinstance(t, dict)]
            except _json.JSONDecodeError:
                pass

            # 第2层：修复JSON后解析
            fixed = self._fix_json_errors(clean)
            try:
                result = _json.loads(fixed)
                if isinstance(result, list) and len(result) > 0:
                    logger.info("[TopicLibraryGenerator] ✓ 第2层修复后成功，得到 %d 条", len(result))
                    return [self._normalize_llm_item(t) for t in result if isinstance(t, dict)]
            except _json.JSONDecodeError:
                pass

            # 第3层：找第一个完整JSON对象
            start = clean.find('{')
            if start != -1:
                for end in range(len(clean), start, -1):
                    candidate = clean[start:end].replace('{{', '{').replace('}}', '}')
                    try:
                        result = _json.loads(candidate)
                        if isinstance(result, list) and len(result) > 0:
                            logger.info("[TopicLibraryGenerator] ✓ 第3层找到数组，得到 %d 条", len(result))
                            return [self._normalize_llm_item(t) for t in result if isinstance(t, dict)]
                    except _json.JSONDecodeError:
                        continue

            # 第4层：提取topics数组
            topics_match = re.search(r'"topics"\s*:\s*\[([\s\S]*)\]', clean)
            if topics_match:
                inner = topics_match.group(1)
                bracket_count = 1
                for i, c in enumerate(inner):
                    if c == '[':
                        bracket_count += 1
                    elif c == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            inner = '[' + inner[:i+1]
                            break
                if inner.endswith(']'):
                    try:
                        topics = _json.loads(inner)
                        logger.info("[TopicLibraryGenerator] ✓ 第4层提取topics数组，得到 %d 条", len(topics))
                        return [self._normalize_llm_item(t) for t in topics if isinstance(t, dict)]
                    except _json.JSONDecodeError:
                        pass

            # 第5层：提取裸数组
            array_match = re.search(r'\[\s*\{', clean)
            if array_match:
                start_pos = array_match.start()
                for end_pos in range(len(clean), start_pos, -1):
                    test_str = clean[start_pos:end_pos]
                    try:
                        parsed = _json.loads(test_str)
                        if isinstance(parsed, list) and len(parsed) > 0:
                            logger.info("[TopicLibraryGenerator] ✓ 第5层提取裸数组，得到 %d 条", len(parsed))
                            return [self._normalize_llm_item(t) for t in parsed if isinstance(t, dict)]
                    except _json.JSONDecodeError:
                        continue

            # 第6层：逐个提取JSON对象
            topics = []
            bracket_depth = 0
            in_json = False
            json_start = -1
            for i, c in enumerate(clean):
                if c == '{':
                    if not in_json:
                        json_start = i
                        in_json = True
                    bracket_depth += 1
                elif c == '}':
                    bracket_depth -= 1
                    if in_json and bracket_depth == 0:
                        json_str = clean[json_start:i+1]
                        try:
                            obj = _json.loads(json_str)
                            if isinstance(obj, dict) and ('title' in obj or '标题' in obj):
                                topics.append(obj)
                        except _json.JSONDecodeError:
                            pass
                        in_json = False
                        json_start = -1
            if topics:
                logger.info("[TopicLibraryGenerator] ✓ 第6层逐个提取，得到 %d 条", len(topics))
                return [self._normalize_llm_item(t) for t in topics]

            # 第7层：从后向前提取
            topics = self._extract_valid_topics_backward(clean)
            if topics:
                logger.info("[TopicLibraryGenerator] ✓ 第7层从后向前提取，得到 %d 条", len(topics))
                return [self._normalize_llm_item(t) for t in topics]

            logger.warning("[TopicLibraryGenerator] 7层解析全部失败，使用兜底选题")
            return self._get_fallback_topics(20)

        except Exception as e:
            logger.warning("[TopicLibraryGenerator] 解析异常: %s", str(e)[:200])
            return self._get_fallback_topics(20)

    def _normalize_llm_item(self, item: Dict) -> Dict:
        """
        规范化LLM返回的单条选题

        只保留 LLM 返回的核心字段，其他字段由本地计算：
        - geo_mode → _assign_geo_modes 时计算
        - scene_options → 内容生成时动态构建
        - type_key → LLM返回或本地分配
        """
        return {
            'title': item.get('title') or item.get('标题') or '',
            'keywords': item.get('keywords') or item.get('关键词') or [],
            'recommended_reason': item.get('recommended_reason') or item.get('推荐理由') or '',
            'type_key': item.get('type_key') or item.get('type') or '',
        }

    def _fix_json_errors(self, json_str: str) -> str:
        """修复常见JSON格式错误"""
        # 去除markdown代码块
        json_str = json_str.strip()
        if json_str.startswith('```json'):
            json_str = json_str[7:]
        elif json_str.startswith('```'):
            json_str = json_str[3:]
        if json_str.endswith('```'):
            json_str = json_str[:-3]
        json_str = json_str.strip()

        # 修复中文引号
        def replace_curly_quotes(text):
            result = []
            i = 0
            in_string = False
            while i < len(text):
                c = text[i]
                if c == '"' and (i == 0 or text[i-1] != '\\'):
                    in_string = not in_string
                    result.append(c)
                elif not in_string and c in '\u2018\u2019\u201b':
                    result.append('"')
                elif not in_string and c in '\u201c\u201d\u201f':
                    result.append('"')
                else:
                    result.append(c)
                i += 1
            return ''.join(result)
        json_str = replace_curly_quotes(json_str)

        # 修复ASCII单引号
        json_str = re.sub(r'("(?:[^"\\]|\\.)*)\'(?=[,\s\r\n\]}])', r'\1"', json_str)

        # 逐行检查引号配对
        lines = json_str.split('\n')
        fixed_lines = []
        for line in lines:
            quote_count = 0
            escape = False
            for ch in line:
                if escape:
                    escape = False
                    continue
                if ch == '\\':
                    escape = True
                    continue
                if ch == '"':
                    quote_count += 1
            if quote_count % 2 == 1:
                line = line.rstrip() + '"'
            fixed_lines.append(line)
        json_str = '\n'.join(fixed_lines)

        # 去除注释
        lines = json_str.split('\n')
        cleaned_lines = []
        for line in lines:
            if '//' in line:
                in_string = False
                escape = False
                for i, c in enumerate(line):
                    if escape:
                        escape = False
                        continue
                    if c == '\\':
                        escape = True
                        continue
                    if c == '"':
                        in_string = not in_string
                if not in_string:
                    line = line[:line.index('//')]
            cleaned_lines.append(line)
        json_str = '\n'.join(cleaned_lines)

        # 修复末尾逗号
        json_str = re.sub(r',(\s*[\]}])', r'\1', json_str)

        # 移除不可见字符
        json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', json_str)

        # 从最后一个有效位置截断
        last_valid_pos = -1
        for i in range(len(json_str) - 1, -1, -1):
            c = json_str[i]
            if c in '}':
                try:
                    _json.loads(json_str[:i+1])
                    last_valid_pos = i + 1
                    break
                except _json.JSONDecodeError:
                    continue
            elif c == ']':
                try:
                    _json.loads(json_str[:i+1])
                    last_valid_pos = i + 1
                    break
                except _json.JSONDecodeError:
                    continue
        if last_valid_pos > 0 and last_valid_pos < len(json_str):
            json_str = json_str[:last_valid_pos]

        return json_str

    def _extract_valid_topics_backward(self, text: str) -> list:
        """从后向前查找有效topic对象"""
        topics = []
        n = len(text)
        import json as _json
        for start in range(n - 2, -1, -1):
            if text[start] != '{':
                continue
            candidate = text[start:]
            if not candidate.strip().startswith('{'):
                continue
            try:
                obj = _json.loads(candidate)
                if isinstance(obj, dict) and ('title' in obj or '标题' in obj):
                    topics.insert(0, obj)
            except _json.JSONDecodeError:
                continue
        return topics

    # ===========================================================================
    # 兜底补全
    # ===========================================================================

    def _fill_missing_topics(
        self,
        topics: List[Dict],
        topic_count: int,
        portrait_data: Dict,
        stage_config: Dict,
        business_info: Dict = None,
    ) -> List[Dict]:
        """选题数量不足时本地补全

        注意：geo_mode 和 scene_options 在内容生成时动态确定，不在此处处理
        """
        if len(topics) >= topic_count:
            return topics[:topic_count]

        missing = topic_count - len(topics)
        logger.info("[TopicLibraryGenerator] 选题不足，补充 %d 条兜底", missing)

        identity = portrait_data.get('identity', '') or portrait_data.get('目标客户身份', '')
        pain_point = portrait_data.get('pain_point', '') or portrait_data.get('核心痛点', '')
        concern = portrait_data.get('concern', '') or portrait_data.get('核心顾虑', '')

        # 从业务信息中获取业务描述
        business_desc = ''
        if business_info:
            business_desc = business_info.get('business_description', '') or business_info.get('业务描述', '')
        if not business_desc:
            business_desc = portrait_data.get('业务描述', '') or portrait_data.get('business_description', '')

        existing_keys = {t.get('type_key') for t in topics if isinstance(t, dict)}

        # 兜底选题类型（按三盘比例）
        fallback_types = [
            ('cause',             '前置观望种草盘'),
            ('compare',           '前置观望种草盘'),
            ('pitfall',           '前置观望种草盘'),
            ('pain_point',        '刚需痛点盘'),
            ('decision_encourage', '刚需痛点盘'),
            ('skill',             '使用配套搜后种草盘'),
            ('seasonal',          '使用配套搜后种草盘'),
            ('rethink',           '前置观望种草盘'),
            ('tutorial',          '前置观望种草盘'),
            ('effect_proof',      '刚需痛点盘'),
        ]

        for type_key, base in fallback_types:
            if len(topics) >= topic_count:
                break
            if type_key in existing_keys:
                continue

            type_info = self.TYPE_KEY_MAP.get(type_key, {})
            if not type_info:
                continue

            # 生成兜底标题
            core = pain_point or identity or business_desc or '相关内容'
            title = f'{core}怎么办？'

            topics.append({
                'id': str(uuid.uuid4()),
                'title': self._clean_title(title),
                'type_key': type_key,
                'type_name': type_info.get('name', type_key),
                'priority': type_info.get('priority', 'P2'),
                'base': type_info.get('base', ''),
                'content_direction': type_info.get('direction', '种草型'),
                'source': self._get_source_by_type(type_key),
                'keywords': [],
                'recommended_reason': f'基于画像「{pain_point or identity}」生成',
                'generation_count': 0,
                'created_at': datetime.utcnow().isoformat(),
            })
            existing_keys.add(type_key)

        return topics

    # ===========================================================================
    # 存储接口
    # ===========================================================================

    def save_to_portrait(
        self,
        portrait_id: int,
        topic_library: Dict,
        user_id: int,
        plan_type: str = 'professional',
    ) -> bool:
        """保存选题库到画像记录"""
        portrait = SavedPortrait.query.get(portrait_id)
        if not portrait:
            return False

        ttl_hours = self.CACHE_TTL_HOURS.get(plan_type, 24)

        portrait.topic_library = topic_library
        portrait.topic_updated_at = datetime.utcnow()
        portrait.topic_update_count = (portrait.topic_update_count or 0) + 1
        portrait.topic_cache_expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

        db.session.commit()
        return True

    def get_from_portrait(self, portrait_id: int) -> Optional[Dict]:
        """从画像获取已保存的选题库"""
        portrait = SavedPortrait.query.get(portrait_id)
        if not portrait:
            return None
        if portrait.topic_library_expired:
            return None
        return portrait.topic_library

    def select_topics(
        self,
        topic_library: Dict,
        count: int = 5,
        topic_type: str = None,
        keyword_hint: str = None,
    ) -> List[Dict]:
        """从选题库中选择选题"""
        topics = topic_library.get('topics', [])
        if not topics:
            return []

        if keyword_hint and keyword_hint.strip():
            keyword = keyword_hint.strip().lower()
            topics = [
                t for t in topics
                if keyword in (t.get('title', '') + ' '.join(t.get('keywords', []))).lower()
            ]

        if topic_type:
            topics = [t for t in topics if t.get('type_key') == topic_type]

        # 按 GEO 权重排序
        geo_weight_order = GEO_WEIGHT_ORDER
        priority_order = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}

        def sort_key(t):
            geo = t.get('geo_mode', '')
            geo_idx = geo_weight_order.index(geo) if geo in geo_weight_order else len(geo_weight_order)
            priority = priority_order.get(t.get('priority', 'P2'), 2)
            return (geo_idx, priority)

        topics = sorted(topics, key=sort_key)
        random.shuffle(topics)
        return topics[:count]

    # ===========================================================================
    # 工具方法
    # ===========================================================================

    def _escape(self, s: str) -> str:
        if not isinstance(s, str):
            return ''
        return s.replace('{', '{{').replace('}', '}}')

    def _clean_title(self, title: str) -> str:
        if not title:
            return ''
        title = title.replace('"', ' ').replace("'", ' ').strip()
        title = re.sub(r'\s+', ' ', title)
        title = re.sub(r'([。！？])\1+', r'\1', title)
        title = re.sub(r'的怎么办', '怎么办', title)
        title = re.sub(r'怎么办怎么办', '怎么办', title)
        if len(title) > 35:
            title = title[:34] + '…'
        return title

    def _count_by_type(self, topics: List[Dict]) -> Dict:
        counts = {}
        for t in topics:
            if not isinstance(t, dict):
                continue
            key = t.get('type_key', 'unknown')
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _count_by_geo(self, topics: List[Dict]) -> Dict:
        counts = {}
        for t in topics:
            if not isinstance(t, dict):
                continue
            key = t.get('geo_mode', 'unknown')
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _count_by_priority(self, topics: List[Dict]) -> Dict:
        counts = {'P0': 0, 'P1': 0, 'P2': 0, 'P3': 0}
        for t in topics:
            if not isinstance(t, dict):
                continue
            p = t.get('priority', 'P2')
            if p in counts:
                counts[p] += 1
        return counts

    def _get_fallback_topics(self, count: int) -> List[Dict]:
        """纯兜底选题（7层解析全部失败时使用）"""
        topics = []
        for i in range(count):
            geo_key = GEO_WEIGHT_ORDER[i % len(GEO_WEIGHT_ORDER)]
            geo_info = GEO_MODES[geo_key]
            type_key = list(self.TYPE_KEY_MAP.keys())[i % len(self.TYPE_KEY_MAP)]
            type_info = self.TYPE_KEY_MAP[type_key]
            title = self._generate_fallback_title(geo_key, '相关内容', '', '')

            topics.append({
                'id': str(uuid.uuid4()),
                'title': self._clean_title(title),
                'type_key': type_key,
                'type_name': type_info['name'],
                'priority': type_info['priority'],
                'base': type_info['base'],
                'content_direction': type_info['direction'],
                'source': self._get_source_by_type(type_key),
                'keywords': [],
                'recommended_reason': '兜底选题',
                'generation_count': 0,
                'created_at': datetime.utcnow().isoformat(),
                'scene_options': [],
                'geo_mode': geo_key,
                'geo_mode_name': geo_info['name'],
                'title_rule': geo_info['title_rule'],
                'structure_rule': geo_info['structure_rule'],
                'weight': geo_info['weight'],
            })
        return topics

    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """估算token消耗"""
        return int((len(prompt) / 2) + (len(response) / 2))


# 全局实例
topic_library_generator = TopicLibraryGenerator()
