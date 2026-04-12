"""
公开内容生成平台 - 内容生成服务

功能：
1. 基于模板和关键词生成内容
2. AI增强（可选）
3. 生成标题方案
4. 生成标签方案
5. 生成图文内容
"""

import time
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from models.public_models import (
    PublicUser, PublicGeneration, PublicLLMCallLog
)
from models.models import db, AnalysisDimension
from services.public_template_matcher import template_matcher
from services.public_quota_manager import quota_manager

import logging
logger = logging.getLogger(__name__)



# =============================================================================
# 经营类型枚举映射（前后端通用）
# =============================================================================
BUSINESS_TYPE_MAP = {
    "product": "消费品",
    "local_service": "本地服务",
    "personal": "个人账号/IP",
    "enterprise": "企业服务"
}

BUSINESS_TYPE_REVERSE = {
    "消费品": "product",
    "本地服务": "local_service",
    "个人账号/IP": "personal",
    "企业服务": "enterprise"
}


# =============================================================================
# GEO 战略类型映射（经营类型作为顶层战略开关）
# =============================================================================
GEO_STRATEGY_MAP = {
    # 消费品 → 走解决方案化升级
    "product": {
        "strategy_name": "消费品解决方案化",
        "core_psychology": "效果焦虑、安全顾虑、适配担忧、性价比判断",
        "problem_focus": ["功效", "安全", "适配", "体验", "价格"],
        "trust_types": ["实测对比", "用户口碑", "成分说明", "避坑指南"],
        "role_mode": "买用一体为主，少量买用分离",
        "content_plate_ratio": {"种草": 60, "转化": 30, "搜后": 10},
        "geo_focus": ["清单体", "对比型", "实测体验", "功效解答"],
        "cta_style": "购买、试用、领取攻略、咨询",
        "high_risk_decision": False,
        "must_have_keywords": ["效果", "安全", "成分", "体验", "性价比"]
    },
    # 本地服务 → 本地化信任赛道
    "local_service": {
        "strategy_name": "本地信任型服务",
        "core_psychology": "就近方便、靠谱安全、口碑放心、时效响应",
        "problem_focus": ["距离", "上门", "时效", "技术靠谱", "态度", "价格"],
        "trust_types": ["本地案例", "到店评价", "区域口碑", "真实上门"],
        "role_mode": "决策者=使用者，强本地属性",
        "content_plate_ratio": {"种草": 50, "转化": 30, "搜后": 20},
        "geo_focus": ["本地问答", "区域避坑", "附近推荐", "到店引导"],
        "cta_style": "预约、到店、上门、电话咨询、同城对接",
        "high_risk_decision": False,
        "must_have_keywords": ["附近", "同城", "本地", "上门", "地址", "区域"]
    },
    # 个人IP/专家 → 权威知识IP赛道
    "personal": {
        "strategy_name": "专家个人品牌型",
        "core_psychology": "求知焦虑、认知不足、方向迷茫、方法缺失",
        "problem_focus": ["怎么做", "如何", "误区", "逻辑", "方法论", "认知差"],
        "trust_types": ["观点体系", "方法论", "案例复盘", "经验总结"],
        "role_mode": "学习者→跟随者→付费者",
        "content_plate_ratio": {"种草": 70, "转化": 20, "搜后": 10},
        "geo_focus": ["问题-答案", "金句论证", "框架工具", "认知颠覆"],
        "cta_style": "关注、学习、进群、领资料、咨询方案",
        "high_risk_decision": False,
        "must_have_keywords": ["方法", "步骤", "技巧", "逻辑", "体系", "误区"]
    },
    # 企业服务 → B2B复杂决策赛道
    "enterprise": {
        "strategy_name": "B2B复杂解决方案",
        "core_psychology": "风险厌恶、ROI诉求、效率提升、选型焦虑",
        "problem_focus": ["选型", "对比", "实施", "成本", "风险", "案例效果"],
        "trust_types": ["客户案例", "技术方案", "白皮书", "对比测评"],
        "role_mode": "使用者/评估者/决策者 买用分离",
        "content_plate_ratio": {"种草": 30, "转化": 60, "搜后": 10},
        "geo_focus": ["对比选型", "框架方案", "风险规避", "ROI论证"],
        "cta_style": "拿方案、预约演示、对接销售、报价",
        "high_risk_decision": True,
        "must_have_keywords": ["选型", "对比", "方案", "案例", "ROI", "成本", "风险"]
    }
}

# 高客单高风险决策强化（可叠加在任意类型之上）
HIGH_RISK_ENHANCE = {
    "enable": True,
    "extra_problem_focus": ["确定性", "安全感", "避坑", "风险", "不可逆后果"],
    "extra_trust_types": ["深度分析", "专家背书", "成功案例", "风险警示"],
    "content_plate_ratio": {"种草": 20, "转化": 70, "搜后": 10},
    "geo_focus": ["权威解答", "风险拆解", "决策安心", "案例实证"],
}


# =============================================================================
# GEO 自检清单动态权重配置（不同经营类型权重不同）
# =============================================================================
SELF_CHECK_WEIGHTS = {
    "local_service": {
        "标题": 10,
        "开篇": 10,
        "结构": 8,
        "模块化": 7,
        "信任证据": 12,
        "品牌锚点": 8,
        "关键词": 12,
        "可读性": 8,
        "行动号召": 10,
        "多形式潜力": 5,
        "local_keyword_must": 10  # 强制地域词
    },
    "product": {
        "标题": 10,
        "开篇": 10,
        "结构": 9,
        "模块化": 8,
        "信任证据": 12,
        "品牌锚点": 8,
        "关键词": 10,
        "可读性": 8,
        "行动号召": 10,
        "多形式潜力": 5,
        "成分证据": 10
    },
    "personal": {
        "标题": 12,
        "开篇": 10,
        "结构": 10,
        "模块化": 8,
        "信任证据": 10,
        "品牌锚点": 10,
        "关键词": 8,
        "可读性": 10,
        "行动号召": 10,
        "多形式潜力": 5,
        "方法论": 12
    },
    "enterprise": {
        "标题": 10,
        "开篇": 10,
        "结构": 10,
        "模块化": 9,
        "信任证据": 15,
        "品牌锚点": 8,
        "关键词": 10,
        "可读性": 6,
        "行动号召": 10,
        "多形式潜力": 2,
        "ROI证据": 12,
        "案例证据": 12
    }
}


# =============================================================================
# 经营类型差异化问题维度体系
# =============================================================================
# 根据经营类型动态生成不同的问题维度，使问题识别更精准

BUSINESS_TYPE_PROBLEM_DIMS = {
    # 消费品：关注成分安全、效果验证、过敏风险、口感味道
    "product": {
        "name": "消费品",
        "user_problem_dims": [
            {
                "type": "功效质疑",
                "examples": "效果不明显、不达预期、没感觉到效果、效果太慢",
                "severity_weight": "⭐⭐⭐⭐"
            },
            {
                "type": "安全担忧",
                "examples": "成分是否安全、是否有添加剂、是否含有害物质、是否过期",
                "severity_weight": "⭐⭐⭐⭐⭐"
            },
            {
                "type": "适配顾虑",
                "examples": "适不适合我家宝宝、适不适合我这种情况、适龄吗",
                "severity_weight": "⭐⭐⭐⭐"
            },
            {
                "type": "过敏风险",
                "examples": "会不会过敏、会不会有不良反应、敏宝能不能用",
                "severity_weight": "⭐⭐⭐⭐⭐"
            },
            {
                "type": "口味口感",
                "examples": "好不好喝、宝宝爱不爱喝、口感怎么样、有没有怪味",
                "severity_weight": "⭐⭐⭐"
            },
            {
                "type": "使用便利",
                "examples": "使用方法复不复杂、能不能坚持、容不容易操作",
                "severity_weight": "⭐⭐⭐"
            }
        ],
        "buyer_concern_dims": [
            {
                "type": "真假辨别",
                "examples": "是不是正品、货源正不正、会不会买到假货"
            },
            {
                "type": "价格价值",
                "examples": "价格贵不贵、值不值这个价、有没有更便宜的"
            },
            {
                "type": "品牌选择",
                "examples": "选哪个牌子好、哪个口碑好、哪个销量高"
            },
            {
                "type": "购买渠道",
                "examples": "哪里买靠谱、网上买行不行、实体店买还是网店"
            },
            {
                "type": "售后保障",
                "examples": "不满意能退吗、有没有质保、出问题找谁"
            }
        ],
        "special_requirements": "重点关注儿童、老人等特殊人群的安全问题"
    },

    # 本地服务：关注服务质量、响应速度、专业程度、便利性
    "local_service": {
        "name": "本地服务",
        "user_problem_dims": [
            {
                "type": "质量担忧",
                "examples": "服务质量怎么样、技术水平行不行、专不专业",
                "severity_weight": "⭐⭐⭐⭐⭐"
            },
            {
                "type": "响应速度",
                "examples": "能不能及时上门、等待时间久不久、能不能加急",
                "severity_weight": "⭐⭐⭐⭐"
            },
            {
                "type": "态度服务",
                "examples": "服务态度好不好、会不会敷衍、沟不沟通信",
                "severity_weight": "⭐⭐⭐"
            },
            {
                "type": "价格透明",
                "examples": "收费合不合理、有没有隐形收费、报价准不准",
                "severity_weight": "⭐⭐⭐⭐"
            },
            {
                "type": "安全靠谱",
                "examples": "靠不靠谱、会不会跑路、人品信不信得过",
                "severity_weight": "⭐⭐⭐⭐⭐"
            },
            {
                "type": "便利程度",
                "examples": "方不方便预约、时间灵不灵活、节假日能约吗",
                "severity_weight": "⭐⭐⭐"
            }
        ],
        "buyer_concern_dims": [
            {
                "type": "资质验证",
                "examples": "有没有正规资质、有没有营业执照、技术过不过关"
            },
            {
                "type": "口碑评价",
                "examples": "别人评价怎么样、有没有差评、服务过哪些客户"
            },
            {
                "type": "售后保障",
                "examples": "做不好怎么办、出了问题谁负责、有没有质保期"
            },
            {
                "type": "价格公道",
                "examples": "价格贵不贵、能不能讲价、有没有优惠"
            }
        ],
        "special_requirements": "重点关注服务人员的专业性和可信度"
    },

    # 个人IP：关注内容质量、更新频率、个人风格
    "personal": {
        "name": "个人账号/IP",
        "user_problem_dims": [
            {
                "type": "内容质量",
                "examples": "内容有没有干货、专不专业、值不值得看",
                "severity_weight": "⭐⭐⭐⭐⭐"
            },
            {
                "type": "内容时效",
                "examples": "是不是最新的、有没有更新、内容过没过期",
                "severity_weight": "⭐⭐⭐"
            },
            {
                "type": "风格匹配",
                "examples": "风格喜不喜欢、内容看不看得进去、适不适合自己",
                "severity_weight": "⭐⭐⭐"
            },
            {
                "type": "可操作性",
                "examples": "照着做行不行、步骤清不清晰、小白能不能学会",
                "severity_weight": "⭐⭐⭐⭐"
            },
            {
                "type": "真实可信",
                "examples": "是不是真的、是不是恰饭、会不会骗人",
                "severity_weight": "⭐⭐⭐⭐"
            }
        ],
        "buyer_concern_dims": [
            {
                "type": "专业背书",
                "examples": "有没有专业背景、有没有相关资质、是不是真懂"
            },
            {
                "type": "粉丝口碑",
                "examples": "粉丝多不多、互动怎么样、风评好不好"
            },
            {
                "type": "内容原创",
                "examples": "是不是原创内容、有没有抄袭、搬运的多不多"
            },
            {
                "type": "商业广告",
                "examples": "恰没恰饭、推荐的东西好不好用、是不是广告"
            }
        ],
        "special_requirements": "重点关注IP的真实性和专业性"
    },

    # 企业服务：关注资质认证、价格体系、交付能力、合同保障
    "enterprise": {
        "name": "企业服务",
        "user_problem_dims": [
            {
                "type": "资质合规",
                "examples": "有没有正规资质、符不符合行业标准、有没有认证",
                "severity_weight": "⭐⭐⭐⭐⭐"
            },
            {
                "type": "交付能力",
                "examples": "能不能按时交付、产能跟不跟得上、会不会延期",
                "severity_weight": "⭐⭐⭐⭐⭐"
            },
            {
                "type": "价格体系",
                "examples": "报价合不合理、有没有折扣、批量能不能优惠",
                "severity_weight": "⭐⭐⭐⭐"
            },
            {
                "type": "合作经验",
                "examples": "做过哪些客户、有没有同行案例、经验丰不丰富",
                "severity_weight": "⭐⭐⭐⭐"
            },
            {
                "type": "合同保障",
                "examples": "合同条款合不合理、违约怎么处理、权责清不清晰",
                "severity_weight": "⭐⭐⭐⭐⭐"
            },
            {
                "type": "服务响应",
                "examples": "有没有专属对接、响应及不及时、问题能不能及时解决",
                "severity_weight": "⭐⭐⭐⭐"
            }
        ],
        "buyer_concern_dims": [
            {
                "type": "企业资质",
                "examples": "公司正不正规、规模怎么样、有没有实体"
            },
            {
                "type": "行业案例",
                "examples": "做过哪些项目、有没有同行业案例、效果怎么样"
            },
            {
                "type": "价格谈判",
                "examples": "能不能谈价格、有没有优惠套餐、付款方式灵不灵活"
            },
            {
                "type": "合同法务",
                "examples": "合同条款怎么样、违约金高不高、风险怎么控制"
            },
            {
                "type": "长期合作",
                "examples": "能不能长期合作、有没有战略合作、政策支不支持"
            },
            {
                "type": "数据安全",
                "examples": "数据会不会泄露、保密措施到不到位、信息安全不安全"
            }
        ],
        "special_requirements": "重点关注企业的合规性和长期合作稳定性"
    }
}


def get_problem_dims_by_business_type(business_type: str) -> dict:
    """
    根据经营类型获取对应的问题维度配置

    Args:
        business_type: 经营类型枚举值 (product/local_service/personal/enterprise)

    Returns:
        问题维度配置字典，包含 user_problem_dims 和 buyer_concern_dims
    """
    return BUSINESS_TYPE_PROBLEM_DIMS.get(business_type, BUSINESS_TYPE_PROBLEM_DIMS.get("local_service"))


def build_user_problem_section(business_type: str) -> str:
    """
    构建使用方问题维度的Markdown表格

    Args:
        business_type: 经营类型枚举值

    Returns:
        Markdown格式的问题维度表格
    """
    dims = get_problem_dims_by_business_type(business_type)
    dims_list = dims.get("user_problem_dims", [])

    lines = ["=== 使用方问题（{name}专用维度） ===".format(name=dims["name"])]
    lines.append("请列出6-8个使用方问题，结合业务描述具体展开：")
    lines.append("| 问题类型 | 具体表现 | 严重程度 |")
    lines.append("|----------|----------|----------|")

    for dim in dims_list:
        lines.append("| {type} | {examples} | {weight} |".format(
            type=dim["type"],
            examples=dim["examples"],
            weight=dim["severity_weight"]
        ))

    return "\n".join(lines)


def build_buyer_concern_section(business_type: str) -> str:
    """
    构建付费方顾虑维度的Markdown表格

    Args:
        business_type: 经营类型枚举值

    Returns:
        Markdown格式的顾虑维度表格
    """
    dims = get_problem_dims_by_business_type(business_type)
    dims_list = dims.get("buyer_concern_dims", [])

    lines = ["=== 付费方顾虑（{name}专用维度） ===".format(name=dims["name"])]
    lines.append("请列出6-8个付费方顾虑，结合业务描述具体展开：")
    lines.append("| 顾虑类型 | 具体表现 |")
    lines.append("|----------|----------|")

    for dim in dims_list:
        lines.append("| {type} | {examples} |".format(
            type=dim["type"],
            examples=dim["examples"]
        ))

    return "\n".join(lines)


# =============================================================================
# GEO战略核心工具函数
# =============================================================================

def get_geo_strategy(business_type: str, is_high_risk: bool = False) -> dict:
    """
    获取当前业务对应的GEO战略配置

    Args:
        business_type: 经营类型枚举值
        is_high_risk: 是否为高风险决策（可叠加）

    Returns:
        GEO战略配置字典
    """
    strategy = GEO_STRATEGY_MAP.get(business_type, GEO_STRATEGY_MAP.get("local_service"))

    # 如果是高风险决策，叠加强化规则
    if is_high_risk and HIGH_RISK_ENHANCE.get("enable"):
        enhanced_strategy = strategy.copy()
        enhanced_strategy["problem_focus"] = strategy.get("problem_focus", []) + HIGH_RISK_ENHANCE.get("extra_problem_focus", [])
        enhanced_strategy["trust_types"] = strategy.get("trust_types", []) + HIGH_RISK_ENHANCE.get("extra_trust_types", [])
        enhanced_strategy["content_plate_ratio"] = HIGH_RISK_ENHANCE.get("content_plate_ratio", strategy.get("content_plate_ratio", {}))
        enhanced_strategy["geo_focus"] = HIGH_RISK_ENHANCE.get("geo_focus", strategy.get("geo_focus", []))
        enhanced_strategy["is_high_risk_enhanced"] = True
        return enhanced_strategy

    return strategy


def build_problem_dim_prompt_by_business_type(business_type: str, is_high_risk: bool = False) -> dict:
    """
    按经营类型动态构建完整的问题维度Prompt段落

    Args:
        business_type: 经营类型枚举值
        is_high_risk: 是否为高风险决策

    Returns:
        包含 user_problem_section 和 buyer_concern_section 的字典
    """
    strategy = get_geo_strategy(business_type, is_high_risk)

    # 使用基础问题维度构建
    dims = get_problem_dims_by_business_type(business_type)

    # 构建使用方问题段落
    user_lines = ["=== 使用方问题（{name}专用维度） ===".format(name=dims["name"])]
    user_lines.append("【核心关注】" + "、".join(strategy.get("problem_focus", [])))
    user_lines.append("请列出6-8个使用方问题，结合业务描述具体展开：")
    user_lines.append("| 问题类型 | 具体表现 | 严重程度 |")
    user_lines.append("|----------|----------|----------|")

    for dim in dims.get("user_problem_dims", []):
        user_lines.append("| {type} | {examples} | {weight} |".format(
            type=dim["type"],
            examples=dim["examples"],
            weight=dim.get("severity_weight", "⭐⭐⭐")
        ))

    # 高风险追加问题维度
    if is_high_risk and HIGH_RISK_ENHANCE.get("enable"):
        user_lines.append("")
        user_lines.append("【高风险追加】" + "、".join(HIGH_RISK_ENHANCE.get("extra_problem_focus", [])))

    # 构建付费方顾虑段落
    buyer_lines = ["=== 付费方顾虑（{name}专用维度） ===".format(name=dims["name"])]
    buyer_lines.append("【信任构建】" + "、".join(strategy.get("trust_types", [])))
    buyer_lines.append("请列出6-8个付费方顾虑，结合业务描述具体展开：")
    buyer_lines.append("| 顾虑类型 | 具体表现 |")
    buyer_lines.append("|----------|----------|")

    for dim in dims.get("buyer_concern_dims", []):
        buyer_lines.append("| {type} | {examples} |".format(
            type=dim["type"],
            examples=dim["examples"]
        ))

    return {
        "user_problem_section": "\n".join(user_lines),
        "buyer_concern_section": "\n".join(buyer_lines),
        "strategy": strategy
    }


def get_content_plate_ratio(business_type: str, is_high_risk: bool = False) -> dict:
    """
    按GEO战略自动分配内容底盘比例

    Args:
        business_type: 经营类型枚举值
        is_high_risk: 是否为高风险决策

    Returns:
        内容底盘比例字典 {"种草": xx, "转化": xx, "搜后": xx}
    """
    strategy = get_geo_strategy(business_type, is_high_risk)
    return strategy.get("content_plate_ratio", {"种草": 50, "转化": 30, "搜后": 20})


def get_trust_evidence_requirement(business_type: str) -> str:
    """
    按赛道生成差异化信任证据要求

    Args:
        business_type: 经营类型枚举值

    Returns:
        信任证据要求描述
    """
    strategy = get_geo_strategy(business_type)
    trust_types = strategy.get("trust_types", [])

    requirements = {
        "local_service": "必须包含：本地真实案例截图、到店评价、区域地址信息、联系方式",
        "product": "必须包含：成分说明、用户评价截图、实测数据对比、避坑提醒",
        "personal": "必须包含：方法论框架、案例复盘、经验总结、观点论证",
        "enterprise": "必须包含：客户案例数据、技术方案说明、白皮书或对比报告"
    }

    base_req = requirements.get(business_type, requirements["local_service"])
    trust_req = "信任证据类型：" + "、".join(trust_types)

    return f"{trust_req}\n{base_req}"


def get_cta_style_by_business_type(business_type: str) -> str:
    """
    按赛道生成差异化行动号召风格

    Args:
        business_type: 经营类型枚举值

    Returns:
        CTA风格描述
    """
    strategy = get_geo_strategy(business_type)
    return strategy.get("cta_style", "咨询、了解详情")


def build_geo_output_rules(business_type: str, is_high_risk: bool = False) -> str:
    """
    构建GEO输出规则约束段落

    Args:
        business_type: 经营类型枚举值
        is_high_risk: 是否为高风险决策

    Returns:
        规则约束段落
    """
    strategy = get_geo_strategy(business_type, is_high_risk)
    strategy_name = strategy.get("strategy_name", "")

    # 按赛道生成差异化输出规则
    rules_map = {
        "local_service": """
=== 输出规则（本地服务赛道）===
1. 【强制地域词】每个问题关键词必须包含：附近、同城、本地、上门、地址 等地域词
2. 【信任优先】优先输出靠谱安全、口碑放心、时效响应相关问题
3. 【场景具体】问题必须具体到可搜索，如"XX区附近桶装水配送"
4. 【高转化】内容方向偏向：预约、到店、上门咨询
5. 【输出格式】严格JSON，包含 identity, problem_type, description, severity, scenario, problem_keywords, content_direction, market_type
""",
        "product": """
=== 输出规则（消费品赛道）===
1. 【功效验证】每个问题必须包含效果、安全、成分相关维度
2. 【信任优先】优先输出安全顾虑、功效质疑、适配担忧相关问题
3. 【决策辅助】内容方向偏向：购买决策、试用体验、成分对比
4. 【输出格式】严格JSON，包含 identity, problem_type, description, severity, scenario, problem_keywords, content_direction, market_type
""",
        "personal": """
=== 输出规则（个人IP赛道）===
1. 【认知升级】每个问题必须包含方法、逻辑、误区、认知相关维度
2. 【知识焦虑】优先输出求知焦虑、方向迷茫、方法缺失相关问题
3. 【内容深度】内容方向偏向：方法论、框架工具、认知颠覆
4. 【学习转化】CTA偏向：关注、学习、进群、领资料
5. 【输出格式】严格JSON，包含 identity, problem_type, description, severity, scenario, problem_keywords, content_direction, market_type
""",
        "enterprise": """
=== 输出规则（企业服务赛道）===
1. 【决策链】必须覆盖：使用者/评估者/决策者 三类角色的不同问题
2. 【风险控制】优先输出选型焦虑、ROI担忧、实施风险相关问题
3. 【案例背书】内容方向偏向：客户案例、技术方案、白皮书
4. 【销售转化】CTA偏向：拿方案、预约演示、对接销售
5. 【输出格式】严格JSON，包含 identity, problem_type, description, severity, scenario, problem_keywords, content_direction, market_type
"""
    }

    base_rule = rules_map.get(business_type, rules_map["local_service"])

    # 高风险追加规则
    if is_high_risk and HIGH_RISK_ENHANCE.get("enable"):
        high_risk_rule = """
6. 【高风险追加】必须覆盖：确定性、安全感、避坑、不可逆风险
7. 【权威背书】信任证据必须包含：深度分析、专家背书、成功案例
"""
        base_rule = base_rule.replace("5. 【输出格式】", high_risk_rule + "\n5. 【输出格式】")

    return base_rule


# =============================================================================
# 场景 → 基础人群固定映射（统一三层结构）
# =============================================================================
# 层级定义：
# - 决策层(buyer)：出钱、拍板、决策购买的人 → 对应 buyer_concerns
# - 对接层：经办、联络、需求提报者 → 补充细分长尾，不与买用冲突
# - 使用层(user)：实际使用、体验服务、产生痛点的人 → 对应 user_pains
# =============================================================================
SCENE_BASE_PERSONAS = {
    # 酒店/餐饮/茶楼/高端会所
    "hotel_restaurant": {
        "决策层(buyer)": [
            {"name": "酒店总经理", "desc": "负责酒店整体运营出钱拍板", "role": "buyer", "user_of": "酒店员工"},
            {"name": "餐饮总监", "desc": "负责餐厅/宴会出钱决策", "role": "buyer", "user_of": "餐厅员工"},
            {"name": "会所负责人", "desc": "高端会所出钱决策者", "role": "buyer", "user_of": "会所会员"},
        ],
        "对接层": [
            {"name": "行政总厨", "desc": "厨房采购经办人，筛选供应商", "role": "mediator", "buyer_of": "酒店总经理", "user_of": "厨房团队"},
            {"name": "采购经理", "desc": "采购部门经办，流程对接", "role": "mediator", "buyer_of": "管理层", "user_of": "采购部门"},
            {"name": "宴会销售", "desc": "婚宴/会议需求提报者", "role": "mediator", "buyer_of": "客户", "user_of": "宴会客人"},
        ],
        "使用层(user)": [
            {"name": "餐厅经理", "desc": "餐厅日常运营使用服务", "role": "user", "buyer_of": "管理层"},
            {"name": "茶楼老板", "desc": "茶楼自用经营者", "role": "user", "buyer_of": "茶楼老板"},
        ]
    },
    # 家用/住宅/小区业主
    "residential": {
        "决策层(buyer)": [
            {"name": "自住业主", "desc": "自己出钱买给自己用", "role": "buyer_user", "user_of": "自住业主"},
            {"name": "宝妈", "desc": "家长出钱买给孩子用", "role": "buyer", "user_of": "孩子"},
            {"name": "银发族子女", "desc": "子女出钱买给老人用", "role": "buyer", "user_of": "老人"},
            {"name": "租房青年", "desc": "租房族自己出钱用", "role": "buyer_user", "user_of": "租房青年"},
        ],
        "对接层": [
            {"name": "家庭主妇", "desc": "家庭采购经办筛选者", "role": "mediator", "buyer_of": "家庭决策者", "user_of": "家庭成员"},
        ],
        "使用层(user)": [
            {"name": "孩子", "desc": "实际使用者，0-12岁", "role": "user", "buyer_of": "宝妈"},
            {"name": "老人", "desc": "实际使用者，60岁+", "role": "user", "buyer_of": "银发族子女"},
            {"name": "家庭成员", "desc": "一般家庭成员使用", "role": "user", "buyer_of": "自住业主"},
        ]
    },
    # 写字楼/企业/工厂/园区
    "office_enterprise": {
        "决策层(buyer)": [
            {"name": "企业老板", "desc": "出钱拍板决策购买", "role": "buyer", "user_of": "员工"},
            {"name": "行政总监", "desc": "行政出钱决策者", "role": "buyer", "user_of": "行政部门"},
            {"name": "HR负责人", "desc": "人事出钱决策者", "role": "buyer", "user_of": "HR部门"},
        ],
        "对接层": [
            {"name": "行政专员", "desc": "采购经办筛选执行", "role": "mediator", "buyer_of": "行政总监", "user_of": "行政执行"},
            {"name": "后勤主管", "desc": "后勤经办对接", "role": "mediator", "buyer_of": "管理层", "user_of": "后勤团队"},
            {"name": "采购专员", "desc": "采购流程经办", "role": "mediator", "buyer_of": "采购经理", "user_of": "采购执行"},
        ],
        "使用层(user)": [
            {"name": "办公室员工", "desc": "实际使用服务的员工", "role": "user", "buyer_of": "企业老板"},
            {"name": "工厂工人", "desc": "生产一线实际使用者", "role": "user", "buyer_of": "工厂管理"},
        ]
    },
    # 学校/医院/食堂/政企单位
    "institutional": {
        "决策层(buyer)": [
            {"name": "单位领导", "desc": "学校/医院出钱拍板者", "role": "buyer", "user_of": "单位人员"},
            {"name": "后勤主任", "desc": "后勤出钱决策者", "role": "buyer", "user_of": "后勤部门"},
            {"name": "食堂负责人", "desc": "食堂出钱决策者", "role": "buyer", "user_of": "食堂员工"},
        ],
        "对接层": [
            {"name": "采购负责人", "desc": "采购经办流程对接", "role": "mediator", "buyer_of": "后勤主任", "user_of": "采购执行"},
            {"name": "营养师", "desc": "需求提报审核者", "role": "mediator", "buyer_of": "食堂负责人", "user_of": "营养管理"},
        ],
        "使用层(user)": [
            {"name": "教师", "desc": "学校实际使用者", "role": "user", "buyer_of": "学校领导"},
            {"name": "医护人员", "desc": "医院实际使用者", "role": "user", "buyer_of": "医院领导"},
            {"name": "学生/病患", "desc": "终端使用者", "role": "user", "buyer_of": "单位领导"},
        ]
    },
    # 实体店/连锁门店/加盟品牌
    "retail_chain": {
        "决策层(buyer)": [
            {"name": "品牌创始人", "desc": "品牌方出钱决策", "role": "buyer", "user_of": "品牌管理"},
            {"name": "连锁加盟商", "desc": "加盟商出钱决策", "role": "buyer", "user_of": "门店运营"},
        ],
        "对接层": [
            {"name": "督导", "desc": "连锁门店对接协调", "role": "mediator", "buyer_of": "品牌方", "user_of": "门店执行"},
        ],
        "使用层(user)": [
            {"name": "门店店主", "desc": "单店老板自用决策", "role": "buyer_user", "user_of": "门店店主"},
            {"name": "店员", "desc": "门店员工实际使用", "role": "user", "buyer_of": "门店店主"},
        ]
    },
    # 装修/工装/工程定制
    "renovation": {
        "决策层(buyer)": [
            {"name": "业主/甲方", "desc": "出钱拍板决策", "role": "buyer", "user_of": "业主"},
            {"name": "项目经理", "desc": "项目出钱决策者", "role": "buyer", "user_of": "项目成员"},
        ],
        "对接层": [
            {"name": "设计师", "desc": "需求对接方案协调", "role": "mediator", "buyer_of": "业主", "user_of": "设计执行"},
            {"name": "采购员", "desc": "材料采购经办", "role": "mediator", "buyer_of": "项目经理", "user_of": "采购执行"},
        ],
        "使用层(user)": [
            {"name": "工长", "desc": "施工实际执行使用", "role": "user", "buyer_of": "业主/项目经理"},
            {"name": "施工人员", "desc": "一线施工人员", "role": "user", "buyer_of": "工长"},
        ]
    },
    # 其他小众场景
    "other": {
        "通用": [
            {"name": "决策者", "desc": "出钱拍板者", "role": "buyer", "user_of": "使用者"},
            {"name": "经办人", "desc": "流程对接经办", "role": "mediator", "buyer_of": "决策者", "user_of": "执行"},
            {"name": "使用者", "desc": "实际使用者", "role": "user", "buyer_of": "决策者"},
        ]
    }
}


# =============================================================================
# 经营类型人群过滤 + 买用关系映射
# =============================================================================
def filter_personas_by_business_type(base_personas: Dict, business_type: str) -> Dict:
    """
    根据经营类型，自动裁剪系统底层人群，防止乱生成C/B混合

    买用关系统一规则：
    - 决策层(buyer) → buyer_concerns（付费方顾虑）
    - 使用层(user) → user_pains（使用者问题）
    - 对接层 → 中间影响者（补充细分长尾，不与买用冲突）
    - buyer_user角色 → 买用合一，两者都生成

    Args:
        base_personas: 场景基础人群（来自SCENE_BASE_PERSONAS）
        business_type: 经营类型枚举值

    Returns:
        过滤后的人群字典，保持三层结构
    """
    if business_type == "product":
        # 消费品：只保留C端，区分买用分离和买用合一
        filtered = {}
        for layer, personas in base_personas.items():
            if "使用层" in layer or "决策层" in layer:
                # 只保留role为buyer/user/buyer_user的人群
                filtered[layer] = [p for p in personas if p.get("role") in ["buyer", "user", "buyer_user"]]
        return filtered if filtered else _get_default_consumer_personas()

    elif business_type == "local_service":
        # 本地服务：买用合一为主（店主/居民自己买自己用）
        filtered = {}
        for layer, personas in base_personas.items():
            if layer in ["使用层(user)", "对接层", "通用"]:
                filtered[layer] = personas
        return filtered if filtered else _get_default_local_service_personas()

    elif business_type == "personal":
        # 个人IP：买用合一（博主/个人用户自己产出自己用）
        return {
            "使用层(user)": [
                {"name": "个人用户", "desc": "普通个人消费者", "role": "buyer_user", "user_of": "个人用户"},
                {"name": "粉丝", "desc": "账号粉丝/追随者", "role": "user", "buyer_of": "博主"},
                {"name": "博主", "desc": "自媒体博主自用决策", "role": "buyer_user", "user_of": "博主"},
            ],
            "对接层": [
                {"name": "内容创作者", "desc": "同行创作者交流合作", "role": "mediator", "buyer_of": "博主", "user_of": "创作者"},
            ]
        }

    elif business_type == "enterprise":
        # 企业服务：完整三层（决策/对接/执行）
        return base_personas

    else:
        return base_personas


def _get_default_consumer_personas() -> Dict:
    """消费品默认人群（买用分离为主）"""
    return {
        "决策层(buyer)": [
            {"name": "宝妈", "desc": "家长出钱买给孩子用", "role": "buyer", "user_of": "孩子"},
            {"name": "银发族子女", "desc": "子女出钱买给老人用", "role": "buyer", "user_of": "老人"},
            {"name": "自购用户", "desc": "自己出钱买给自己用", "role": "buyer_user", "user_of": "自购用户"},
        ],
        "使用层(user)": [
            {"name": "孩子", "desc": "0-12岁实际使用者", "role": "user", "buyer_of": "宝妈"},
            {"name": "老人", "desc": "60岁+实际使用者", "role": "user", "buyer_of": "银发族子女"},
            {"name": "个人", "desc": "成人自用", "role": "user", "buyer_of": "自购用户"},
        ]
    }


def _get_default_local_service_personas() -> Dict:
    """本地服务默认人群（买用合一）"""
    return {
        "使用层(user)": [
            {"name": "自住业主", "desc": "自己出钱买给自己用", "role": "buyer_user", "user_of": "自住业主"},
            {"name": "小微店主", "desc": "店主自己买自己用", "role": "buyer_user", "user_of": "小微店主"},
            {"name": "本地居民", "desc": "居民自用", "role": "buyer_user", "user_of": "本地居民"},
        ]
    }


# =============================================================================
# 【需求底盘三盘枚举 - 固定值，禁止自定义别名或改写】
# =============================================================================
# 三盘枚举原文直译，不允许任何别名、简写、改写
PROBLEM_BASE_SOUQIAN_ZHONGCAO = "前置观望种草盘"          # 用户处于"知道有风险/将来可能遇到"阶段，搜索目的是学习了解、提前预防
PROBLEM_BASE_GANGXU_TONGDIAN = "刚需痛点盘"             # 用户已处于痛苦中、急需解决的核心问题，搜索目的是立即找到解决方案
PROBLEM_BASE_SHIYONG_PEITAO = "使用配套搜后种草盘"      # 用户已使用核心业务后，产生的周边工具、养护知识、留存复购类需求

PROBLEM_BASE_LIST = [
    PROBLEM_BASE_SOUQIAN_ZHONGCAO,
    PROBLEM_BASE_GANGXU_TONGDIAN,
    PROBLEM_BASE_SHIYONG_PEITAO,
]

PROBLEM_BASE_TO_CONTENT_DIRECTION = {
    PROBLEM_BASE_GANGXU_TONGDIAN: "转化型",
    PROBLEM_BASE_SOUQIAN_ZHONGCAO: "种草型",
    PROBLEM_BASE_SHIYONG_PEITAO: "种草型",
}


# =============================================================================
# 【双标签枚举 - consume_type（消费类型）+ demand_attr（需求属性）】
# =============================================================================
# consume_type（消费类型）：必需 / 增量
CONSUMER_TYPE_REQUIRED = "必需"     # 硬需求：已有问题必须解决，不解决会持续痛苦
CONSUMER_TYPE_INCREMENTAL = "增量"  # 种草需求：锦上添花，可买可不买

# demand_attr（需求属性）：功能驱动 / 场景情绪驱动
DEMAND_ATTR_FUNCTION = "功能驱动"              # 用户关注产品本身的功能、效果、性价比
DEMAND_ATTR_SCENE_EMOTION = "场景情绪驱动"    # 用户关注仪式感、场景氛围、情绪价值

# 双标签自动打标规则（原文直译，不允许改写关键词匹配逻辑）
# 规则：损坏 / 替换 / 效果差 / 性价比诉求 = 必需 + 功能驱动
# 规则：仪式感 / 场景穿搭 / 爱好生活 = 增量 + 场景情绪驱动
CONSUMPTION_TYPE_KEYWORDS = {
    "必需": ["损坏", "替换", "效果差", "性价比诉求", "坏了", "坏了", "换", "修", "换新", "替换", "解决", "修复", "更换", "坏了", "不耐用", "不好用", "质量差", "用坏了", "报废", "断货", "用完", "空瓶", "断货", "没有了", "需要买", "必备", "刚需", "救命", "急需", "紧急", "应急"],
    "增量": ["仪式感", "场景穿搭", "爱好生活", "精致", "升级", "改善", "提升", "享受", "体验", "氛围", "装饰", "好看", "美观", "时尚", "潮流", "流行", "新款", "新品", "送礼", "收藏", "囤货", "送礼", "节日", "纪念日", "生日", "特殊场合", "场合", "仪式"],
}

DEMAND_ATTR_KEYWORDS = {
    "功能驱动": ["损坏", "替换", "效果差", "性价比诉求", "坏了", "不耐用", "效果", "功能", "质量", "性能", "参数", "配置", "材质", "成分", "配方", "规格", "价格", "贵", "便宜", "划算", "值不值", "性价比", "耗电", "功率", "容量", "尺寸", "大小", "重量", "维修", "售后", "保修", "寿命", "耐用", "好用", "实用"],
    "场景情绪驱动": ["仪式感", "场景穿搭", "爱好生活", "好看", "美观", "漂亮", "精致", "氛围", "仪式", "场合", "场景", "心情", "情绪", "享受", "体验", "品味", "格调", "风格", "设计", "颜值", "拍照", "上镜", "打卡", "晒图", "分享", "礼物", "惊喜", "浪漫", "温馨"],
}


# =============================================================================
# 【常驻行为 + 固定场景 + 慢性体征枚举 - 用于「行为+场景+慢性体征拆解」解析层】
# =============================================================================
# 常驻行为（久坐/久站/熬夜/长期伏案等导致的长期习惯性姿势问题）
RESIDENT_BEHAVIORS = {
    "久坐": ["长期久坐", "一坐就是", "屁股不离椅子", "办公室一坐", "开车久坐", "伏案工作", "对着电脑"],
    "久站": ["长期久站", "一站就是", "站立工作", "销售站立", "服务行业站立", "站立时间"],
    "熬夜": ["经常熬夜", "长期熬夜", "睡眠不足", "作息不规律", "晚睡", "失眠", "睡眠质量差"],
    "长期伏案": ["长期伏案", "低头看手机", "低头族", "长期低头", "颈部前倾", "驼背"],
    "高强度用眼": ["长期用眼", "盯着屏幕", "电脑办公", "设计师", "程序员", "会计", "长期看手机"],
    "重体力": ["搬重物", "体力劳动", "弯腰干活", "腰肌劳损", "经常下蹲", "爬楼梯"],
    "不规律饮食": ["暴饮暴食", "三餐不定", "经常应酬", "外卖党", "不吃早餐", "夜宵"],
    "缺乏运动": ["久坐不动", "不运动", "宅", "躺着", "懒得动", "缺乏锻炼"],
}

# 固定场景（办公室/后厨/工位等）
FIXED_SCENES = {
    "办公室": ["白领", "上班族", "办公室", "职场", "写字楼", "文员", "行政", "财务"],
    "家庭": ["家庭", "居家", "住所", "自住", "业主", "居民"],
    "工厂车间": ["工厂", "车间", "工人", "蓝领", "制造业", "生产"],
    "后厨餐饮": ["厨师", "后厨", "餐饮", "厨房", "服务员", "餐饮从业者"],
    "工地": ["工地", "建筑", "装修", "施工", "农民工", "工程"],
    "商铺店面": ["店员", "导购", "营业员", "收银", "销售", "门店"],
    "驾驶": ["司机", "驾驶员", "长途", "货运", "客运", "出租车"],
    "学校": ["学生", "老师", "教师", "教室", "宿舍", "校园"],
    "医院": ["医生", "护士", "医护", "医院", "药店", "医疗"],
}

# 慢性常态化症状（腰酸/颈椎僵/眼疲劳等）
CHRONIC_SYMPTOMS = {
    "骨骼肌肉类": {
        "腰酸背痛": ["腰酸", "腰痛", "腰疼", "背部酸痛", "腰肌劳损", "腰间盘", "久坐腰疼"],
        "颈椎僵硬": ["颈椎", "脖子酸", "脖子僵硬", "肩颈不适", "颈部", "脖子疼", "颈椎病"],
        "肩周不适": ["肩膀酸", "肩膀疼", "肩周", "手臂发麻", "五十肩", "肩部不适"],
        "腿脚肿胀": ["腿肿", "脚肿", "下肢浮肿", "静脉曲张", "小腿胀", "久站腿肿"],
        "关节疼痛": ["关节", "膝盖疼", "膝关节", "踝关节", "手腕疼", "腱鞘炎"],
    },
    "眼部疲劳类": {
        "眼疲劳": ["眼疲劳", "眼睛干涩", "眼睛酸", "眼干", "视力模糊", "用眼过度"],
        "头痛头晕": ["头痛", "头晕", "偏头痛", "头部不适", "太阳穴疼", "眼睛疼连带头疼"],
    },
    "消化系统类": {
        "肠胃不适": ["肠胃", "胃不舒服", "消化不良", "腹胀", "便秘", "痔疮"],
        "肥胖问题": ["肥胖", "体重增加", "赘肉", "啤酒肚", "久坐腹", "代谢慢"],
    },
    "精神状态类": {
        "精力不足": ["疲惫", "犯困", "没精神", "精力不足", "容易疲劳", "体力不支"],
        "睡眠问题": ["失眠", "睡眠差", "睡不着", "多梦", "睡眠质量", "熬夜后"],
        "焦虑压力": ["焦虑", "压力大", "情绪", "精神紧张", "职场焦虑", "心理"],
    },
    "皮肤问题类": {
        "皮肤干燥": ["皮肤干", "皮肤问题", "皮肤瘙痒", "湿疹", "过敏", "皮肤差"],
        "体态问题": ["体态", "含胸", "驼背", "圆肩", "骨盆前倾", "姿势不良"],
    },
}


# =============================================================================
# 【心理情绪动因枚举 - 新增第四维识别层：前置于「行为+场景+慢性体征」解析层】
# =============================================================================
# 情绪动因大类（焦虑/自卑/压抑/内耗/怕丢脸等）
EMOTION_DRIVER_CATEGORIES = {
    "焦虑型": {
        "育儿焦虑": ["育儿", "孩子", "宝宝", "小孩", "学生", "成绩", "升学", "早教", "喂养", "发育", "身高", "体重", "补习", "培训班"],
        "职场焦虑": ["职场", "工作", "开会", "加班", "KPI", "晋升", "面试", "同事", "领导", "上班", "下班", "996", "工资", "辞职", "转行"],
        "容貌焦虑": ["颜值", "脸", "皮肤", "痘痘", "黑头", "毛孔", "身材", "胖", "瘦", "腿粗", "腰粗", "手臂粗", "法令纹", "眼角纹", "白发", "掉发", "秃"],
        "健康焦虑": ["体检", "指标", "结节", "息肉", "囊肿", "三高", "脂肪肝", "血糖", "血压", "血脂", "胃镜", "体检报告", "复查", "癌", "肿瘤"],
        "财务焦虑": ["还贷", "房贷", "车贷", "信用卡", "花呗", "负债", "月光", "存款", "工资不够", "入不敷出", "钱", "预算", "开销"],
        "关系焦虑": ["婆媳", "夫妻", "亲子", "感情", "婚姻", "吵架", "冷战", "离婚", "出轨", "小三", "原生家庭", "原生家庭"],
        "社交焦虑": ["社恐", "内向", "不敢", "不会说话", "人际关系", "尴尬", "被嘲笑", "丢人", "面子", "怕丢脸", "不合群"],
        "选择焦虑": ["不知道选哪个", "不知道怎么选", "哪个好", "哪个更好", "选错了怎么办", "怕选错", "选择困难", "纠结", "挑花眼", "对比", "比较"],
        "学业焦虑": ["考试", "升学", "成绩", "考研", "考公", "考证", "学习", "挂科", "毕设", "论文", "答辩", "毕业"],
    },
    "自卑型": {
        "能力自卑": ["不会", "不懂", "做不好", "笨", "学不会", "脑子慢", "记不住", "反应慢", "脑子转不动"],
        "外貌自卑": ["丑", "土", "难看", "气质差", "没气质", "不会打扮", "不会穿搭", "衣品差", "品味差"],
        "经济自卑": ["穷", "没钱", "买不起", "太贵", "消费不起", "不配", "没面子", "不如别人", "攀比"],
        "社交自卑": ["说错话", "不会聊天", "情商低", "不会说话", "得罪人", "被孤立", "没朋友"],
    },
    "压抑型": {
        "情绪压抑": ["憋着", "不敢说", "忍着", "不想说", "压抑", "闷在心里", "情绪低落", "提不起精神"],
        "需求压抑": ["凑合", "将就", "算了", "不买了", "太贵了", "不需要", "没时间", "以后再说"],
        "关系压抑": ["不想回家", "不想面对", "应付", "强颜欢笑", "心累", "心寒", "失望"],
    },
    "内耗型": {
        "决策内耗": ["反复纠结", "想来想去", "纠结", "犹豫不决", "拿不定主意", "纠结半天", "想太多"],
        "关系内耗": ["反复想", "反复猜", "猜他怎么想", "内耗", "猜忌", "不信任", "想太多", "玻璃心"],
        "完美内耗": ["必须完美", "不能出错", "不能失败", "怕出错", "高标准", "强迫", "苛刻", "自责"],
        "后悔内耗": ["后悔", "早知道", "如果当初", "要是", "自责", "懊恼", "遗憾"],
    },
    "怕丢脸型": {
        "公开场合": ["当众", "人多的地方", "丢人", "怕丢人", "丢脸", "尴尬", "出丑", "被笑话", "被嘲笑", "社死"],
        "社交评价": ["别人怎么看", "别人会笑", "面子", "掉价", "不体面", "上不了台面", "丢人现眼"],
        "职场形象": ["被同事笑话", "被领导说", "被开除", "丢脸", "职场形象", "口碑", "名声"],
    },
    "怕选错型": {
        "怕买错": ["买错了怎么办", "怕买错", "不敢买", "选错了浪费", "怕浪费", "白花钱", "买了后悔"],
        "怕入错行": ["转行", "选错行业", "入错行", "选错专业", "后悔选专业", "学错了"],
        "怕用错方法": ["用错了怎么办", "怕方法不对", "怕弄巧成拙", "怕适得其反", "不敢尝试", "怕弄坏"],
    },
}

# 情绪动因 → 痛点/症状映射（情绪会导致什么样的身体/心理/行为症状）
EMOTION_TO_SYMPTOM_MAP = {
    "焦虑型": {
        "育儿焦虑": ["失眠多梦", "情绪暴躁", "食欲紊乱", "精力不足", "自我怀疑", "记忆力下降"],
        "职场焦虑": ["睡眠障碍", "肩颈紧绷", "消化不良", "情绪波动", "效率下降", "职业倦怠"],
        "容貌焦虑": ["回避照镜", "过度护肤", "饮食紊乱", "社交回避", "自我否定", "情绪低落"],
        "健康焦虑": ["反复检查", "疑病倾向", "失眠", "草木皆兵", "焦虑不安", "逃避体检"],
        "财务焦虑": ["回避消费", "报复性省钱", "失眠", "压抑消费", "生活质量下降", "争吵增多"],
        "关系焦虑": ["过度控制", "猜疑", "争吵增多", "回避沟通", "情绪失控", "孤立自己"],
        "社交焦虑": ["回避社交", "脸红手抖", "发言紧张", "事后后悔", "自我否定", "孤独感"],
        "选择焦虑": ["拖延决策", "反复比较", "错过最佳时机", "后悔", "抱怨", "效率低下"],
        "学业焦虑": ["失眠", "记忆力减退", "注意力不集中", "逃避考试", "自我否定", "厌学"],
    },
    "自卑型": {
        "能力自卑": ["回避挑战", "过度准备", "拖延行动", "自我设限", "不敢尝试", "消极被动"],
        "外貌自卑": ["过度关注外表", "回避镜子/照片", "穿衣保守", "社交退缩", "自我否定", "不敢展示"],
        "经济自卑": ["回避社交", "攀比", "物质补偿", "自我贬低", "仇富心理", "社交退缩"],
        "社交自卑": ["回避聚会", "不敢发言", "过度在意他人评价", "事后后悔", "自我否定", "敏感多疑"],
    },
    "压抑型": {
        "情绪压抑": ["情绪低落", "躯体化症状", "胃痛", "头痛", "失眠", "自我封闭"],
        "需求压抑": ["委屈自己", "讨好型人格", "不快乐", "抱怨", "怨恨", "隐性消费"],
        "关系压抑": ["心累", "冷漠", "沟通减少", "关系疏离", "爆发争吵", "逃避"],
    },
    "内耗型": {
        "决策内耗": ["错过时机", "效率低下", "疲惫不堪", "怨天尤人", "行动瘫痪", "反复拖延"],
        "关系内耗": ["猜疑", "争吵", "情绪消耗", "信任缺失", "关系恶化", "孤独感加重"],
        "完美内耗": ["效率低下", "过度准备", "自我施压", "身心疲惫", "害怕行动", "错过机会"],
        "后悔内耗": ["沉溺过去", "无法释怀", "影响当下决策", "消极", "自我否定", "恶性循环"],
    },
    "怕丢脸型": {
        "公开场合": ["回避当众表现", "发言紧张", "表现失态", "事后羞耻", "自我否定", "社交退缩"],
        "社交评价": ["过度在意评价", "表演型行为", "事后反复回想", "敏感", "玻璃心", "人际紧张"],
        "职场形象": ["过度谨慎", "不敢表达", "讨好同事", "隐忍委屈", "积累不满", "爆发"],
    },
    "怕选错型": {
        "怕买错": ["迟迟不下手", "反复退货", "错过优惠", "后悔", "抱怨", "不敢购买"],
        "怕入错行": ["职业迷茫", "频繁跳槽", "不敢尝试", "后悔", "自我否定", "停滞不前"],
        "怕用错方法": ["不敢行动", "反复查资料", "方法论囤积", "实践不足", "自我怀疑", "效率低下"],
    },
}

# 情绪长期累积 → 最终痛点映射
EMOTION_TO_ULTIMATE_PAIN_MAP = {
    "育儿焦虑": ["孩子教育方向迷茫", "亲子关系紧张", "家庭矛盾频发", "自身情绪失控", "生活质量下降"],
    "职场焦虑": ["职业倦怠", "晋升受阻", "人际关系恶化", "身体健康预警", "工作生活失衡"],
    "容貌焦虑": ["社交回避", "自信丧失", "消费陷阱", "情绪不稳定", "生活满意度下降"],
    "健康焦虑": ["正常生活受影响", "过度医疗", "经济负担", "家庭关系紧张", "心理疾病风险"],
    "财务焦虑": ["生活质量下降", "消费决策扭曲", "家庭矛盾", "不敢享受生活", "经济压力恶性循环"],
    "关系焦虑": ["关系恶化", "孤独感", "心理健康受损", "工作生活受影响", "恶性循环"],
    "社交焦虑": ["人脉受限", "机会流失", "自我封闭", "心理健康受损", "生活质量下降"],
    "选择焦虑": ["决策瘫痪", "持续错过", "机会成本增加", "自我怀疑加剧", "生活质量下降"],
    "学业焦虑": ["成绩下滑", "厌学情绪", "升学受影响", "家庭矛盾", "心理问题"],
    "能力自卑": ["职业发展受阻", "收入增长停滞", "自我价值感低", "人际关系退缩", "恶性循环"],
    "外貌自卑": ["社交退缩", "错失机会", "消费陷阱", "心理健康受损", "生活质量下降"],
    "经济自卑": ["社交退缩", "消费扭曲", "人际关系障碍", "自我设限", "代际贫困风险"],
    "社交自卑": ["人脉受限", "职业发展受阻", "自我封闭", "心理问题", "恶性循环"],
    "情绪压抑": ["心理疾病", "躯体化症状", "关系破裂", "生活满意度极低", "爆发风险"],
    "需求压抑": ["委屈积累", "自我价值感低", "讨好型人格固化", "关系失衡", "心理健康受损"],
    "关系压抑": ["关系破裂", "心理问题", "自我迷失", "生活满意度下降", "孤独终老风险"],
    "决策内耗": ["一事无成", "机会成本巨大", "自我否定", "生活质量下降", "心理健康受损"],
    "关系内耗": ["关系破裂", "身心俱疲", "社交退缩", "心理问题", "生活质量下降"],
    "完美内耗": ["效率极低", "身心俱疲", "成就低", "自我施压循环", "心理健康受损"],
    "后悔内耗": ["无法活在当下", "决策能力下降", "自我否定加剧", "生活质量下降", "恶性循环"],
    "怕丢脸": ["错失机会", "人际关系假象", "身心疲惫", "自我迷失", "生活质量下降"],
    "怕选错": ["持续错过", "机会成本增加", "自我怀疑加剧", "决策能力退化", "生活质量下降"],
}

# 情绪类原生问题类型（新增第六类：情绪疑问+心态误区）
SEEDING_PROBLEM_TYPES_EMOTION = [
    "情绪疑问", "心态误区", "心理顾虑", "情绪疏导", "心态调节", "心理调适",
    "减压疑问", "内耗疑问", "焦虑疑问", "自卑疑问", "怕丢脸疑问",
]


# =============================================================================
# 【心理情绪三盘归类规则 - 情绪问题专属归类逻辑】
# =============================================================================
# 规则1：普通情绪顾虑、焦虑疑惑 → 前置观望种草盘（50%）
#         尚未严重影响生活，处于观望/学习阶段
# 规则2：情绪严重影响生活/健康 → 刚需痛点盘（30%）
#         已出现明显症状，急需解决
# 规则3：情绪疏导、心态调节干货 → 使用配套搜后种草盘（20%）
#         已接受现实，需要方法和工具辅助
EMOTION_PROBLEM_BASE_RULES = {
    "前置观望种草盘": [
        # 普通情绪顾虑、焦虑疑惑
        "不知道会不会xxx焦虑", "怎么缓解xxx焦虑", "xxx焦虑正常吗",
        "xxx焦虑是不是我想多了", "怎么判断xxx焦虑严不严重",
        "xxx焦虑怎么自我调节", "职场焦虑怎么办", "育儿焦虑怎么缓解",
        "容貌焦虑正常吗", "选择焦虑怎么办", "社交焦虑怎么克服",
        "怎么克服自卑心理", "怎么减少内耗", "怎么停止胡思乱想",
        "怕丢脸怎么办", "怕选错怎么办", "怎么克服完美主义",
        "xxx会让我焦虑吗", "要不要xxx焦虑", "是否需要xxx焦虑",
    ],
    "刚需痛点盘": [
        # 情绪已严重影响生活/健康
        "焦虑导致失眠", "焦虑严重影响工作", "焦虑导致身体症状",
        "自卑导致社交障碍", "内耗严重影响效率", "压抑导致心理问题",
        "焦虑已经影响生活", "焦虑严重影响睡眠", "焦虑导致家庭矛盾",
        "心理问题已经影响健康", "情绪问题已经很严重", "焦虑躯体化症状",
        "社恐已经严重影响工作", "选择恐惧已经严重影响生活", "完美主义已经严重影响效率",
        "长期焦虑导致健康问题", "焦虑已经影响身体健康", "心理问题已经需要治疗",
    ],
    "使用配套搜后种草盘": [
        # 情绪疏导、心态调节干货
        "焦虑怎么自我疏导", "减压方法", "放松技巧", "冥想有用吗",
        "心理咨询有用吗", "心态调节方法", "情绪管理技巧",
        "如何停止内耗", "怎么缓解心理压力", "自我调节方法推荐",
        "焦虑症自我治疗", "减压工具推荐", "放松训练方法",
        "心理疏导方法", "情绪释放技巧", "心态调整干货",
        "如何与自己和解", "怎么接受不完美的自己", "自我成长方法",
    ],
}


def is_emotion_seeding_problem(emotion_type: str, description: str) -> bool:
    """
    判断情绪类问题是否属于「前置观望种草盘」

    普通情绪顾虑、焦虑疑惑 → 前置观望种草盘
    """
    text = f"{emotion_type} {description}".lower()
    seeding_keywords = [
        "怎么缓解", "怎么办", "正常吗", "是不是", "会不会",
        "怎么克服", "怎么减少", "要不要", "是否需要",
        "焦虑", "自卑", "内耗", "怕丢脸", "怕选错", "社恐",
        "担心", "纠结", "犹豫", "压抑",
    ]
    for kw in seeding_keywords:
        if kw in text:
            pain_keywords = [
                "已经严重影响", "已经严重影响生活", "已经严重影响工作",
                "焦虑导致失眠", "焦虑导致身体", "心理问题",
                "已经需要治疗", "已经严重到", "严重影响健康",
            ]
            for pain in pain_keywords:
                if pain in text:
                    return False
            return True
    return False


def is_emotion_urgent_problem(emotion_type: str, description: str) -> bool:
    """
    判断情绪类问题是否属于「刚需痛点盘」

    情绪严重影响生活/健康 → 刚需痛点盘
    """
    text = f"{emotion_type} {description}".lower()
    urgent_keywords = [
        "已经严重影响", "严重影响", "焦虑导致", "已经严重",
        "心理问题", "需要治疗", "已经无法", "已经失控",
        "严重影响工作", "严重影响生活", "严重影响健康",
        "躯体化症状", "严重影响睡眠", "严重影响家庭",
    ]
    for kw in urgent_keywords:
        if kw in text:
            return True
    return False


def is_emotion_companion_problem(emotion_type: str, description: str) -> bool:
    """
    判断情绪类问题是否属于「使用配套搜后种草盘」

    情绪疏导、心态调节干货 → 使用配套搜后种草盘
    """
    text = f"{emotion_type} {description}".lower()
    companion_keywords = [
        "怎么疏导", "自我疏导", "减压方法", "放松技巧", "冥想",
        "心理咨询", "心态调节", "情绪管理", "自我调节", "减压工具",
        "放松训练", "心理疏导", "情绪释放", "与自己和解", "自我成长",
        "怎么接受", "自我治疗", "怎么释怀", "怎么放下",
    ]
    for kw in companion_keywords:
        if kw in text:
            return True
    return False


def infer_emotion_problem_base(
    emotion_type: str,
    description: str,
    severity: str,
) -> str:
    """
    针对心理情绪类问题，智能推断需求底盘

    归类规则：
    - 普通情绪顾虑、焦虑疑惑 → 【前置观望种草盘】
    - 情绪严重影响生活/健康 → 【刚需痛点盘】
    - 情绪疏导、心态调节干货 → 【使用配套搜后种草盘】

    Args:
        emotion_type: 情绪类型（如：育儿焦虑、职场焦虑）
        description: 问题描述
        severity: 严重程度（高/中/低）

    Returns:
        需求底盘名称
    """
    if is_emotion_urgent_problem(emotion_type, description):
        return PROBLEM_BASE_GANGXU_TONGDIAN
    if is_emotion_companion_problem(emotion_type, description):
        return PROBLEM_BASE_SHIYONG_PEITAO
    if is_emotion_seeding_problem(emotion_type, description):
        return PROBLEM_BASE_SOUQIAN_ZHONGCAO
    # 默认前置观望
    return PROBLEM_BASE_SOUQIAN_ZHONGCAO


# =============================================================================
# 【五类种草原生问题 - 包含原有的四类 + 第五类「长期习惯疑问+场景预防误区」】
# =============================================================================
# 原有四类种草原生问题
SEEDING_PROBLEM_TYPES_ORIGINAL = [
    "症状疑问", "对比选型", "上游供应链", "认知误区",
]
# 新增第五类：长期习惯疑问 + 场景预防误区（适配常态化隐性痛点）
SEEDING_PROBLEM_TYPES_HABITUAL = [
    "长期习惯疑问", "场景预防误区", "姿势疑问", "养护时机", "预防措施", "早期信号",
]


def is_chronic_habitual_problem(problem_type: str, description: str, behavior_tags: List[str] = None) -> bool:
    """
    判断是否为第五类种草原生问题：「长期习惯疑问 + 场景预防误区」

    判断依据：
    1. 问题类型或描述中包含长期习惯相关关键词
    2. 包含固定场景相关的预防性疑问
    3. 用户关注"长期如此会有什么后果"、"如何预防"、"早期信号"等

    Args:
        problem_type: 问题类型
        description: 问题描述
        behavior_tags: 行为标签列表（来自解析层）

    Returns:
        True = 属于第五类种草原生问题，必须归入「前置观望种草盘」
    """
    text_type = (problem_type or '').lower()
    text_desc = (description or '').lower()
    text = f"{text_type} {text_desc}"

    # 第五类关键词：长期习惯 + 场景预防
    habitual_keywords = [
        "长期", "久坐", "久站", "长期伏案", "习惯", "姿势",
        "预防", "怎么预防", "如何避免", "怎么矫正",
        "早期信号", "前期症状", "前兆",
        "护", "养护", "保护", "防护", "保健",
        "有什么影响", "后果", "危害", "长期会怎样",
        "正确姿势", "怎么坐", "怎么站", "如何改善",
        "要不要", "需不需要", "该不该",
    ]

    for kw in habitual_keywords:
        if kw in text_type or kw in text_desc:
            return True

    # 行为标签匹配：行为标签出现时，追加行为场景相关的种草问题
    if behavior_tags:
        for tag in behavior_tags:
            if tag in text_type or tag in text_desc:
                # 行为标签匹配时，优先识别预防性/习惯性疑问
                if any(kw in text for kw in ["怎么", "如何", "要不要", "该不该", "预防", "改善", "矫正"]):
                    return True

    return False


def auto_tag_chronic_symptom(identity: str, problem_type: str, description: str) -> Dict[str, Any]:
    """
    根据常驻行为、固定场景、慢性体征标签自动打标

    Args:
        identity: 用户身份
        problem_type: 问题类型
        description: 问题描述

    Returns:
        包含 behavior_tags, scene_tags, symptom_tags 的字典
    """
    result = {
        'behavior_tags': [],      # 常驻行为标签
        'scene_tags': [],         # 固定场景标签
        'symptom_tags': [],       # 慢性体征标签
        'is_chronic_symptom': False,  # 是否为慢性体征问题
    }

    text = f"{identity} {problem_type} {description}".lower()

    # 匹配常驻行为
    for behavior, keywords in RESIDENT_BEHAVIORS.items():
        for kw in keywords:
            if kw in text:
                if behavior not in result['behavior_tags']:
                    result['behavior_tags'].append(behavior)
                break

    # 匹配固定场景
    for scene, keywords in FIXED_SCENES.items():
        for kw in keywords:
            if kw in text:
                if scene not in result['scene_tags']:
                    result['scene_tags'].append(scene)
                break

    # 匹配慢性体征
    for category, symptoms in CHRONIC_SYMPTOMS.items():
        for symptom_name, keywords in symptoms.items():
            for kw in keywords:
                if kw in text:
                    if symptom_name not in result['symptom_tags']:
                        result['symptom_tags'].append(symptom_name)
                    result['is_chronic_symptom'] = True
                    break

    return result


def infer_problem_base_for_chronic(
    problem_type: str,
    description: str,
    severity: str,
    is_habitual_question: bool,
) -> str:
    """
    针对慢性体征类问题，智能推断需求底盘

    归类规则：
    - 长期日常不适、预防顾虑、习惯误区 → 【前置观望种草盘】
    - 急性发作、严重影响工作生活 → 【刚需痛点盘】
    - 日常坐姿养护/拉伸/护腰工具 → 【使用配套搜后种草盘】

    Args:
        problem_type: 问题类型
        description: 问题描述
        severity: 严重程度
        is_habitual_question: 是否为第五类种草原生问题

    Returns:
        需求底盘枚举值
    """
    text = f"{problem_type} {description}".lower()

    # 第五类种草原生问题 → 强制前置观望种草盘
    if is_habitual_question:
        return PROBLEM_BASE_SOUQIAN_ZHONGCAO

    # 急性发作关键词 → 刚需痛点盘
    acute_keywords = ["急性", "突然", "发作", "突发", "加剧", "恶化", "严重", "疼得", "难受得", "影响工作", "影响生活", "无法"]
    for kw in acute_keywords:
        if kw in text:
            return PROBLEM_BASE_GANGXU_TONGDIAN

    # 高严重程度 → 刚需痛点盘
    if severity in ["极高", "高", "⭐⭐⭐⭐⭐", "⭐⭐⭐⭐"]:
        # 但如果有预防/养护关键词，偏向种草盘
        prevention_keywords = ["预防", "怎么预防", "如何避免", "平时", "日常", "习惯"]
        for kw in prevention_keywords:
            if kw in text:
                return PROBLEM_BASE_SOUQIAN_ZHONGCAO
        return PROBLEM_BASE_GANGXU_TONGDIAN

    # 养护/工具类关键词 → 使用配套搜后种草盘
    maintenance_keywords = ["护", "保养", "养护", "拉伸", "按摩", "工具", "器材", "靠垫", "护腰", "眼药水", "按摩仪", "筋膜枪", "瑜伽垫"]
    for kw in maintenance_keywords:
        if kw in text:
            return PROBLEM_BASE_SHIYONG_PEITAO

    # 预防类关键词 → 前置观望种草盘
    prevention_keywords = ["预防", "怎么预防", "如何避免", "平时", "日常", "习惯", "误区", "纠正", "矫正", "注意", "防护"]
    for kw in prevention_keywords:
        if kw in text:
            return PROBLEM_BASE_SOUQIAN_ZHONGCAO

    # 默认前置观望种草盘（慢性体征多为隐性痛点）
    return PROBLEM_BASE_SOUQIAN_ZHONGCAO


def auto_tag_consume_type(problem_type: str, description: str, severity: str) -> str:
    """
    根据关键词自动打标 consume_type（必需 / 增量）

    规则原文直译：
    - 损坏 / 替换 / 效果差 / 性价比诉求 = 必需 + 功能驱动
    - 仪式感 / 场景穿搭 / 爱好生活 = 增量 + 场景情绪驱动

    Args:
        problem_type: 问题类型
        description: 问题描述
        severity: 严重程度

    Returns:
        consume_type: 必需 或 增量
    """
    text = f"{problem_type} {description}".lower()

    # 必需：严重程度高 + 包含硬需求关键词
    required_score = 0
    if severity in ["极高", "高", "⭐⭐⭐⭐⭐", "⭐⭐⭐⭐"]:
        required_score += 2
    for kw in CONSUMPTION_TYPE_KEYWORDS["必需"]:
        if kw in text:
            required_score += 1

    # 增量：包含软需求关键词
    incremental_score = 0
    for kw in CONSUMPTION_TYPE_KEYWORDS["增量"]:
        if kw in text:
            incremental_score += 1

    # 判断逻辑：必需得分 >= 2 或 增量得分 = 0 时，判定为必需
    if required_score >= 2 or incremental_score == 0:
        return CONSUMER_TYPE_REQUIRED
    return CONSUMER_TYPE_INCREMENTAL


def auto_tag_demand_attr(problem_type: str, description: str) -> str:
    """
    根据关键词自动打标 demand_attr（功能驱动 / 场景情绪驱动）

    规则原文直译：
    - 损坏 / 替换 / 效果差 / 性价比诉求 = 功能驱动
    - 仪式感 / 场景穿搭 / 爱好生活 = 场景情绪驱动

    Args:
        problem_type: 问题类型
        description: 问题描述

    Returns:
        demand_attr: 功能驱动 或 场景情绪驱动
    """
    text = f"{problem_type} {description}".lower()

    function_score = 0
    for kw in DEMAND_ATTR_KEYWORDS["功能驱动"]:
        if kw in text:
            function_score += 1

    emotion_score = 0
    for kw in DEMAND_ATTR_KEYWORDS["场景情绪驱动"]:
        if kw in text:
            emotion_score += 1

    # 判断逻辑：功能驱动得分 >= 1 且情绪驱动得分 < 功能驱动得分时，判定为功能驱动
    if function_score >= 1 and emotion_score < function_score:
        return DEMAND_ATTR_FUNCTION
    return DEMAND_ATTR_SCENE_EMOTION


# =============================================================================
# 【五类种草原生问题 - 强制归入「前置观望种草盘」】
# 包含原有四类 + 新增第五类「长期习惯疑问+场景预防误区」
# =============================================================================
# 原文直译，不允许分流到另外两盘
SEEDING_PROBLEM_TYPES = [
    "症状疑问",        # 用户对某种症状/现象的疑问（如：这是什么问题？怎么判断？）
    "对比选型",        # 用户在多个选项之间犹豫（如：哪个好？怎么选？）
    "上游供应链",      # 用户关注产品背后的供应链/原料/来源（如：原料哪来的？怎么生产？）
    "认知误区",        # 用户对某个概念的误解/纠正（如：原来不是这样的！我一直搞错了）
]
# 新增第六类：情绪疑问+心态误区（适配心理情绪动因解析层）
SEEDING_PROBLEM_TYPES_EXTENDED = [
    "长期习惯疑问",    # 用户对长期习惯的疑问（如：久坐会有什么后果？怎么改善？）
    "场景预防误区",    # 用户对场景预防的认知误区（如：按摩能治颈椎吗？）
    "姿势疑问",        # 用户对正确姿势的疑问（如：怎么坐才正确？）
    "养护时机",        # 用户对养护时机的疑问（如：什么时候开始护腰？）
    "预防措施",        # 用户对预防措施的疑问（如：怎么预防腰肌劳损？）
    "早期信号",        # 用户对早期信号的疑问（如：颈椎病早期有什么症状？）
    # 情绪疑问+心态误区（第四维前置解析层新增）
    "情绪疑问",        # 用户对情绪/心态的疑问（如：焦虑正常吗？怎么缓解？）
    "心态误区",        # 用户对心态调节的认知误区（如：忍忍就好了？）
    "心理顾虑",        # 用户对心理问题的顾虑（如：会不会心理出问题？）
    "减压疑问",        # 减压相关疑问（如：怎么减压？）
    "内耗疑问",        # 内耗相关疑问（如：怎么停止内耗？）
    "焦虑疑问",        # 焦虑相关疑问（如：职场焦虑正常吗？）
    "自卑疑问",        # 自卑相关疑问（如：怎么克服自卑？）
    "怕丢脸疑问",      # 怕丢脸相关疑问（如：怎么克服怕丢脸心理？）
    "怕选错疑问",      # 怕选错相关疑问（如：怎么克服选择恐惧？）
]

SEEDING_KEYWORD_HINTS = [
    # 原有四类关键词
    "怎么判断", "是什么", "有什么区别", "哪个好", "怎么选",
    "哪来的", "怎么生产", "原料", "供应链", "怎么做的",
    "误区", "原来", "其实", "不是", "错了", "误解",
    "科普", "知识", "了解", "知道", "不懂", "不清楚",
    # 第五类关键词：长期习惯 + 场景预防
    "长期", "久坐", "久站", "长期伏案", "习惯",
    "预防", "怎么预防", "如何避免", "怎么矫正",
    "姿势", "正确姿势", "怎么坐", "怎么站",
    "护", "养护", "保健", "保护",
    "早期信号", "前兆", "前期症状",
    "有什么影响", "后果", "危害", "长期会怎样",
    # 第六类关键词：情绪疑问+心态误区（心理情绪动因解析层新增）
    "焦虑", "自卑", "内耗", "压抑", "怕丢脸", "怕选错",
    "社恐", "社交焦虑", "职场焦虑", "育儿焦虑", "容貌焦虑", "健康焦虑",
    "财务焦虑", "选择焦虑", "学业焦虑", "选择困难",
    "纠结", "犹豫", "不自信", "没面子", "丢人", "尴尬",
    "怎么缓解", "怎么办", "正常吗", "是不是",
    "怎么克服", "怎么减少", "要不要", "是否需要",
    "怎么调节", "怎么疏导", "怎么释放", "怎么调整",
    "减压", "放松", "冥想", "心态", "情绪管理",
    "自我怀疑", "不配", "玻璃心", "强迫", "完美主义",
]

SEEDING_KEYWORD_HINTS = [
    # 原有四类关键词
    "怎么判断", "是什么", "有什么区别", "哪个好", "怎么选",
    "哪来的", "怎么生产", "原料", "供应链", "怎么做的",
    "误区", "原来", "其实", "不是", "错了", "误解",
    "科普", "知识", "了解", "知道", "不懂", "不清楚",
    # 第五类关键词：长期习惯 + 场景预防
    "长期", "久坐", "久站", "长期伏案", "习惯",
    "预防", "怎么预防", "如何避免", "怎么矫正",
    "姿势", "正确姿势", "怎么坐", "怎么站",
    "护", "养护", "保健", "保护",
    "早期信号", "前兆", "前期症状",
    "有什么影响", "后果", "危害", "长期会怎样",
]


def is_seeding_problem(problem_type: str, description: str) -> bool:
    """
    判断是否为六类种草原生问题，强制归入「前置观望种草盘」

    判断依据：
    1. problem_type 或 description 包含原有四类种草原生问题关键词
    2. 新增第五类：长期习惯疑问 + 场景预防误区关键词
    3. 新增第六类：情绪疑问 + 心态误区关键词（心理情绪动因前置解析层）

    Args:
        problem_type: 问题类型
        description: 问题描述

    Returns:
        True = 属于种草原生问题，必须归入「前置观望种草盘」
    """
    text_type = problem_type.lower()
    text_desc = description.lower()
    text = f"{text_type} {text_desc}"

    # 直接匹配原有四类问题类型名称
    for seed_type in SEEDING_PROBLEM_TYPES:
        if seed_type in text_type or seed_type in text_desc:
            return True

    # 直接匹配第五类问题类型名称
    for seed_type in SEEDING_PROBLEM_TYPES_EXTENDED:
        if seed_type in text_type or seed_type in text_desc:
            return True

    # 匹配种草关键词（原有四类 + 第五类）
    for hint in SEEDING_KEYWORD_HINTS:
        if hint in text:
            # 需要额外判断：如果是已经发生的痛点问题，不算种草
            pain_keywords = [
                "坏了", "拉肚子", "过敏", "故障", "烂了", "碎了", "出问题了",
                "疼得", "难受得", "无法", "严重影响", "已经", "突发", "发作",
                # 情绪类排除：严重影响生活/健康不属于种草
                "已经严重影响生活", "已经严重影响工作", "已经严重影响健康",
                "焦虑导致", "心理问题已经", "已经需要治疗",
                "已经严重到", "已经失控", "已经无法", "已经严重",
            ]
            for pain in pain_keywords:
                if pain in text:
                    return False
            return True

    return False


# =============================================================================
# 【用户阶段标签枚举 - 画像生成时新增】
# =============================================================================
USER_STAGE_WATCH = "观望期"    # 用户尚未购买，处于了解和比较阶段
USER_STAGE_DECIDE = "决策期"   # 用户正在做购买决策，权衡各种选项
USER_STAGE_USE = "使用期"      # 用户已购买，正在使用或体验服务

USER_STAGE_MAP = {
    PROBLEM_BASE_SOUQIAN_ZHONGCAO: USER_STAGE_WATCH,
    PROBLEM_BASE_GANGXU_TONGDIAN: USER_STAGE_DECIDE,
    PROBLEM_BASE_SHIYONG_PEITAO: USER_STAGE_USE,
}


def get_user_stage_from_problem_base(problem_base: str) -> str:
    """
    根据 problem_base（需求底盘）推导用户阶段标签

    Args:
        problem_base: 需求底盘枚举值

    Returns:
        用户阶段标签
    """
    return USER_STAGE_MAP.get(problem_base, USER_STAGE_WATCH)


# =============================================================================
# 【行业场景差异化规则 - 新增 industry_scene + trust_demand】
# =============================================================================
# 原文直译，严格对应 GEO「解决方案导向 + 信任背书」逻辑

# 4类业务场景定义
INDUSTRY_SCENE_HIGH_RISK = "高客单价高风险"      # 客单价高、决策风险大（如：装修、婚礼、培训）
INDUSTRY_SCENE_B2B = "B2B企业服务"               # B端采购、多人决策（如：企业服务、设备采购）
INDUSTRY_SCENE_LOCAL_TRUST = "本地信任型"         # 本地生活、服务半径受限（如：本地家政、维修、美容院）
INDUSTRY_SCENE_PERSONAL_BRAND = "个人品牌专家型"   # 依赖个人IP/专业背书（如：知识付费、个人工作室）

# 场景 → industry_scene 自动识别规则（原文直译）
INDUSTRY_SCENE_KEYWORDS = {
    INDUSTRY_SCENE_HIGH_RISK: [
        "装修", "工装", "工程", "婚礼", "婚庆", "摄影", "摄像",
        "培训", "课程", "教育", "留学", "移民", "留学中介",
        "定制", "全屋定制", "家具定制", "橱柜定制", "门窗定制",
        "医美", "整形", "牙齿矫正", "种植牙",
        "月子中心", "产后修复",
    ],
    INDUSTRY_SCENE_B2B: [
        "企业", "公司", "工厂", "机构", "单位", "酒店", "餐厅",
        "写字楼", "办公楼", "商铺", "门店", "连锁", "加盟",
        "食堂", "学校", "医院", "物业", "保洁外包", "团建",
        "设备", "机械", "工业", "生产", "采购", "供应商",
    ],
    INDUSTRY_SCENE_LOCAL_TRUST: [
        "家政", "保洁", "维修", "疏通", "开锁", "搬家",
        "空调", "清洗", "清洁", "擦玻璃", "收纳",
        "美容", "美发", "美甲", "按摩", "SPA", "养生",
        "宠物", "宠物店", "宠物医院", "宠物美容",
        "本地", "附近", "上门",
    ],
    INDUSTRY_SCENE_PERSONAL_BRAND: [
        "知识付费", "课程", "培训", "咨询", "顾问",
        "个人", "工作室", "独立", "私教", "私教课",
        "律师", "医生", "会计师", "设计师", "摄影师",
        "博主", "网红", "达人", "IP", "个人品牌",
        "代运营", "策划", "设计服务",
    ],
}


def identify_industry_scene(business_description: str, service_scenario: str) -> str:
    """
    自动识别 4 类业务场景

    规则原文直译：
    - 高客单价高风险：装修/婚庆/培训/定制等，决策风险大
    - B2B企业服务：B端采购、多人决策流程
    - 本地信任型：本地生活、服务半径受限，依赖口碑
    - 个人品牌专家型：依赖个人IP/专业背书

    Args:
        business_description: 业务描述
        service_scenario: 服务场景枚举值

    Returns:
        行业场景类型
    """
    text = f"{business_description} {service_scenario}".lower()

    # 按优先级匹配（高客单价高风险 > B2B企业服务 > 本地信任型 > 个人品牌专家型）
    scene_order = [
        (INDUSTRY_SCENE_HIGH_RISK, INDUSTRY_SCENE_KEYWORDS[INDUSTRY_SCENE_HIGH_RISK]),
        (INDUSTRY_SCENE_B2B, INDUSTRY_SCENE_KEYWORDS[INDUSTRY_SCENE_B2B]),
        (INDUSTRY_SCENE_LOCAL_TRUST, INDUSTRY_SCENE_KEYWORDS[INDUSTRY_SCENE_LOCAL_TRUST]),
        (INDUSTRY_SCENE_PERSONAL_BRAND, INDUSTRY_SCENE_KEYWORDS[INDUSTRY_SCENE_PERSONAL_BRAND]),
    ]

    for scene_type, keywords in scene_order:
        for kw in keywords:
            if kw in text:
                return scene_type

    # 默认返回通用场景
    return "通用场景"


# 场景专属痛点定义（原文直译）
INDUSTRY_SCENE_PAIN_POINTS = {
    INDUSTRY_SCENE_HIGH_RISK: [
        "怕被坑、花冤枉钱",
        "怕效果达不到预期",
        "怕售后没人管",
        "怕偷工减料、材料以次充好",
        "怕工期拖延、交付延期",
        "怕后期增项加钱",
    ],
    INDUSTRY_SCENE_B2B: [
        "怕供应商资质不够",
        "怕交付质量不稳定",
        "怕售后服务响应慢",
        "怕采购合规审计问题",
        "怕合同纠纷无法追责",
    ],
    INDUSTRY_SCENE_LOCAL_TRUST: [
        "怕师傅手艺差、干活不细致",
        "怕材料被掉包",
        "怕临时加价",
        "怕出现问题找不到人",
        "怕预约等待时间长",
    ],
    INDUSTRY_SCENE_PERSONAL_BRAND: [
        "怕博主/专家名不副实",
        "怕课程/服务不值这个价",
        "怕学完没效果",
        "怕后期服务跟不上",
        "怕个人跑路、机构倒闭",
    ],
}


# 场景专属信任诉求 trust_demand 定义（原文直译）
TRUST_DEMAND_DIMENSIONS = {
    "资质背书": "营业执照、行业资质、认证证书、权威机构背书",
    "案例背书": "真实客户案例、前后对比效果图、视频见证、客户证言",
    "专业背书": "专业团队介绍、技术说明、行业经验年限、专业媒体报道",
    "口碑背书": "真实好评截图、客户转介绍率、复购率、平台评分",
    "售后背书": "售后承诺条款、退款政策、服务保障险、专人跟进",
    "实地背书": "线下门店/工厂实地考察、视频探厂、直播参观",
    "合同背书": "正规合同范本、报价单透明、验收标准明确",
}


# 场景 → trust_demand 映射（原文直译，每种场景有专属组合）
INDUSTRY_SCENE_TRUST_MAP = {
    INDUSTRY_SCENE_HIGH_RISK: [
        "资质背书", "案例背书", "专业背书", "售后背书", "合同背书",
    ],
    INDUSTRY_SCENE_B2B: [
        "资质背书", "案例背书", "专业背书", "口碑背书", "合同背书", "实地背书",
    ],
    INDUSTRY_SCENE_LOCAL_TRUST: [
        "口碑背书", "案例背书", "售后背书", "资质背书",
    ],
    INDUSTRY_SCENE_PERSONAL_BRAND: [
        "专业背书", "案例背书", "口碑背书", "售后背书",
    ],
    "通用场景": [
        "资质背书", "口碑背书", "售后背书",
    ],
}


def get_industry_scene_trust_demand(industry_scene: str) -> List[Dict[str, str]]:
    """
    获取指定行业场景的信任诉求组合

    Args:
        industry_scene: 行业场景类型

    Returns:
        信任诉求列表，每个包含维度名称和描述
    """
    trust_keys = INDUSTRY_SCENE_TRUST_MAP.get(industry_scene, INDUSTRY_SCENE_TRUST_MAP["通用场景"])
    return [
        {"dimension": key, "description": TRUST_DEMAND_DIMENSIONS.get(key, "")}
        for key in trust_keys
    ]


def get_industry_scene_pain_points(industry_scene: str) -> List[str]:
    """
    获取指定行业场景的专属痛点列表

    Args:
        industry_scene: 行业场景类型

    Returns:
        场景专属痛点列表
    """
    return INDUSTRY_SCENE_PAIN_POINTS.get(industry_scene, [])


# 场景 → 搜索行为预判 补充规则
INDUSTRY_SCENE_SEARCH_OVERRIDES = {
    INDUSTRY_SCENE_HIGH_RISK: [
        "会搜索公司/团队资质证书和背景",
        "会搜索真实工地/案例施工现场",
        "会搜索业主真实评价和口碑",
        "会搜索合同模板和验收标准",
        "会搜索常见套路和避坑攻略",
        "会搜索价格行情和报价对比",
    ],
    INDUSTRY_SCENE_B2B: [
        "会搜索供应商资质和行业认证",
        "会搜索企业客户案例和合作品牌",
        "会搜索公司规模和行业口碑",
        "会搜索采购合规性条款",
        "会搜索合同模板和报价明细",
    ],
    INDUSTRY_SCENE_LOCAL_TRUST: [
        "会搜索附近口碑最好的商家",
        "会搜索真实用户评价和评分",
        "会搜索有没有坑/套路",
        "会搜索价格是否合理",
        "会搜索师傅手艺和经验",
    ],
    INDUSTRY_SCENE_PERSONAL_BRAND: [
        "会搜索博主/专家真实背景介绍",
        "会搜索学员真实评价和效果",
        "会搜索课程大纲和服务内容",
        "会搜索有没有后续服务",
        "会搜索博主过往业绩和背书",
    ],
}


def _generate_chronic_search_intent(
    behavior_tags: List[str],
    scene_tags: List[str],
    symptom_tags: List[str]
) -> List[str]:
    """
    为慢性体征类画像生成久坐/伏案/工位养护类搜索词补充

    Args:
        behavior_tags: 常驻行为标签列表
        scene_tags: 固定场景标签列表
        symptom_tags: 慢性体征标签列表

    Returns:
        搜索行为预判补充列表
    """
    results = []

    # 基于行为标签生成搜索词
    for tag in behavior_tags:
        if tag == '久坐':
            results.extend([
                "会搜索久坐人群适合的护腰产品",
                "会搜索办公室缓解腰酸的方法",
                "会搜索护腰腰带有用吗",
            ])
        elif tag == '久站':
            results.extend([
                "会搜索久站人群缓解腿肿的方法",
                "会搜索护膝或弹力袜有用吗",
            ])
        elif tag == '长期伏案':
            results.extend([
                "会搜索正确坐姿示范教程",
                "会搜索伏案工作如何保护颈椎",
            ])
        elif tag == '高强度用眼':
            results.extend([
                "会搜索缓解眼疲劳的眼药水推荐",
                "会搜索护眼灯有用吗",
                "会搜索眼睛干涩怎么缓解",
            ])
        elif tag == '熬夜':
            results.extend([
                "会搜索熬夜后如何恢复体力",
                "会搜索熬夜吃什么补身体",
            ])
        elif tag == '缺乏运动':
            results.extend([
                "会搜索久坐人群适合的简单运动",
                "会搜索办公室拉伸动作示范",
            ])

    # 基于场景标签生成搜索词
    for tag in scene_tags:
        if tag == '办公室':
            results.extend([
                "会搜索办公室护腰小技巧",
                "会搜索办公室颈椎保健操",
            ])
        elif tag == '工位':
            results.extend([
                "会搜索工位人体工学设置",
                "会搜索显示器高度怎么调",
            ])
        elif tag == '驾驶':
            results.extend([
                "会搜索久驾腰托推荐",
                "会搜索开车腰酸怎么缓解",
            ])
        elif tag == '后厨餐饮':
            results.extend([
                "会搜索厨师久站护腿方法",
                "会搜索后厨工作腰肌劳损",
            ])

    # 基于体征标签生成搜索词
    for tag in symptom_tags:
        if tag == '腰酸背痛':
            results.extend([
                "会搜索腰酸背痛怎么缓解",
                "会搜索护腰产品推荐",
            ])
        elif tag == '颈椎僵硬':
            results.extend([
                "会搜索颈椎僵硬怎么缓解",
                "会搜索护颈枕有用吗",
            ])
        elif tag == '肩周不适':
            results.extend([
                "会搜索肩周炎怎么锻炼",
                "会搜索按摩仪推荐",
            ])
        elif tag == '眼疲劳':
            results.extend([
                "会搜索眼疲劳缓解方法",
                "会搜索蒸汽眼罩推荐",
            ])
        elif tag == '腿脚肿胀':
            results.extend([
                "会搜索腿肿怎么快速消肿",
                "会搜索弹力袜推荐",
            ])
        elif tag == '关节疼痛':
            results.extend([
                "会搜索关节疼痛怎么缓解",
                "会搜索氨糖有用吗",
            ])
        elif tag == '精力不足':
            results.extend([
                "会搜索提神醒脑的方法",
                "会搜索维生素B族推荐",
            ])

    # 去重并返回前6个
    seen = set()
    unique_results = []
    for r in results:
        if r not in seen:
            seen.add(r)
            unique_results.append(r)
            if len(unique_results) >= 6:
                break

    return unique_results if unique_results else []


def predict_search_behavior_with_industry_scene(
    user_stage: str,
    problem_type: str,
    description: str,
    industry_scene: str,
    business_description: str = "",
) -> List[str]:
    """
    综合用户阶段 + 行业场景的搜索行为预判

    规则原文直译：
    - 以用户阶段搜索行为为基础
    - 叠加行业场景专属搜索维度
    - 贴合 GEO「解决方案导向 + 信任背书」逻辑

    Args:
        user_stage: 用户阶段标签
        problem_type: 问题类型
        description: 问题描述
        industry_scene: 行业场景类型
        business_description: 业务描述（备用）

    Returns:
        搜索行为预判列表
    """
    # 获取用户阶段基础预判
    base_behavior = predict_search_behavior(user_stage, problem_type, description)

    # 获取场景专属预判
    scene_override = INDUSTRY_SCENE_SEARCH_OVERRIDES.get(industry_scene, [])

    # 合并去重（基础预判优先级更高，场景预判补充）
    combined = base_behavior.copy()
    for item in scene_override:
        if item not in combined:
            combined.append(item)

    # 限制数量（最多8条）
    return combined[:8]


def build_industry_scene_context(
    business_description: str,
    service_scenario: str,
    industry_scene: str = None,
) -> Dict[str, Any]:
    """
    构建行业场景完整上下文（注入画像生成Prompt）

    Args:
        business_description: 业务描述
        service_scenario: 服务场景枚举值
        industry_scene: 行业场景类型（可选，自动识别）

    Returns:
        行业场景上下文字典
    """
    if industry_scene is None:
        industry_scene = identify_industry_scene(business_description, service_scenario)

    return {
        "industry_scene": industry_scene,
        "scene_pain_points": get_industry_scene_pain_points(industry_scene),
        "trust_demand": get_industry_scene_trust_demand(industry_scene),
        "scene_search_hints": INDUSTRY_SCENE_SEARCH_OVERRIDES.get(industry_scene, []),
    }


# =============================================================================
# 【搜索行为预判字段 - 画像生成时新增】
# =============================================================================
SEARCH_BEHAVIOR_PREDICTION_HINTS = {
    USER_STAGE_WATCH: [
        "会搜索基础科普类内容",
        "会搜索同类产品对比",
        "会搜索品牌/商家口碑评价",
        "会搜索选购攻略和避坑指南",
        "会搜索价格参考和性价比分析",
    ],
    USER_STAGE_DECIDE: [
        "会搜索具体产品/服务参数",
        "会搜索真实用户评价和体验",
        "会搜索价格区间和优惠信息",
        "会搜索选购建议和推荐",
        "会搜索售后服务保障条款",
    ],
    USER_STAGE_USE: [
        "会搜索使用方法和技巧",
        "会搜索保养维护知识",
        "会搜索配套工具和耗材推荐",
        "会搜索问题解决和应急处理",
        "会搜索复购优惠和会员福利",
    ],
}


def predict_search_behavior(user_stage: str, problem_type: str, description: str) -> List[str]:
    """
    锚定用户真实搜索词方向，保障后续关键词贴合搜索习惯

    Args:
        user_stage: 用户阶段标签
        problem_type: 问题类型
        description: 问题描述

    Returns:
        搜索行为预判列表
    """
    base_hints = SEARCH_BEHAVIOR_PREDICTION_HINTS.get(user_stage, SEARCH_BEHAVIOR_PREDICTION_HINTS[USER_STAGE_WATCH])

    # 根据问题类型做微调
    text = f"{problem_type} {description}".lower()

    # 针对性强调整
    if any(kw in text for kw in ["怎么选", "哪个好", "区别", "对比"]):
        return [
            "会搜索具体产品/服务的参数对比",
            "会搜索真实用户的使用体验分享",
            "会搜索选购建议和避坑指南",
            "会搜索价格区间和性价比分析",
        ]
    elif any(kw in text for kw in ["坏了", "问题", "故障", "坏了"]):
        return [
            "会搜索问题原因和解决方法",
            "会搜索是否需要更换或维修",
            "会搜索应急处理措施",
            "会搜索相关品牌的售后服务",
        ]
    elif any(kw in text for kw in ["怎么", "什么", "是否"]):
        return [
            "会搜索相关知识科普和原理说明",
            "会搜索是否有风险或副作用",
            "会搜索专业意见或建议",
        ]

    return base_hints


def get_system_base_personas(service_scenario: str, business_type: str) -> str:
    """
    获取系统固定底座人群JSON字符串，用于注入Prompt

    三层买用关系：
    - 决策层(buyer)：出钱/拍板 → buyer_concerns
    - 对接层：经办/联络 → 补充细分长尾
    - 使用层(user)：实际使用 → user_pains

    Args:
        service_scenario: 服务场景枚举值
        business_type: 经营类型枚举值

    Returns:
        过滤后的人群JSON字符串
    """
    # 获取场景基础人群
    base = SCENE_BASE_PERSONAS.get(service_scenario, SCENE_BASE_PERSONAS.get("other", {}))

    # 按经营类型过滤
    filtered = filter_personas_by_business_type(base, business_type)

    # 转换为易读的JSON字符串
    return json.dumps(filtered, ensure_ascii=False, indent=2)


# =============================================================================
# Prompt底座约束模板（全局共用）
# =============================================================================
PROMPT_BASE_CONSTRAINT = """【系统强制底座规则 - 买用关系对齐】
1.底层固定人群：{system_base_personas}

2.三层结构买用强制映射：
   - 决策层(buyer) → 生成 buyer_concerns（付费/成本/风险/资质顾虑）
   - 使用层(user) → 生成 user_problem_types（全部原始搜索动因）
   - 对接层 → 补充细分长尾人群，不与买用冲突

3.【核心定义 - user_problem_types】
   user_problem_types 是用户"因为出现这个问题，才主动搜索找解决方案"的**全部原始动因**，包含：
   - 前置客观症状/异常/损耗/不适（如：拉肚子、过敏、故障、损耗、氧化、发黄）
   - 后置使用体验痛点（如：不方便、不好看、不舒服、影响心情）
   注意：不是"购买者怎么想"，而是"使用者因为这个问题有多难受才去搜"

4.买用关系统一规则：
   - 消费品：买用分离（宝妈→孩子、子女→老人）
   - 本地服务：买用合一（店主自用、居民自用）
   - 个人IP：买用合一（博主自产出、粉丝用）
   - 企业服务：三层分离（老板买→员工用，中间有对接层）

5.禁止自己创造顶层大类、禁止随意新增人群；
6.只能在底层人群之下，做细分/小众/长尾延伸画像；
7.严格遵守经营类型限制；
8.严禁生成与经营类型不匹配的人群

违规生成直接作废重写。

"""


class ContentGenerator:
    """
    内容生成器

    策略：
    1. 免费用户：使用预设模板 + 基础关键词组合
    2. 付费用户：AI增强 + 更多模板选择
    """

    # Token消耗估算
    TOKEN_ESTIMATE = {
        'keyword_only': {'input': 500, 'output': 800, 'total': 1300},
        'with_ai': {'input': 800, 'output': 2000, 'total': 2800},
    }

    # 模型单价（gpt-4o-mini，元/1M tokens）
    MODEL_PRICE = {
        'input': 1.5,   # ¥1.5/1M
        'output': 6.0,  # ¥6.0/1M
    }

    # C 端画像中禁止写入「痛点状态/目标」的 B2B 用语（易与维度库混淆，出现「奶粉+想要增长」类离谱组合）
    _C_END_FORBIDDEN_PAIN_GOAL_SUBSTR: tuple = (
        '遇到瓶颈', '想要增长', '想要转型', '寻求突破', '规模化增长', '规模化',
        '年营收', '营收', 'GMV', '团队规模', '融资', '天使轮', '上市', 'IPO',
        '创始人', '董事长', 'CEO', '总监', '副总裁', 'VP', '拓客', '涨销量',
    )

    # C端业务类型下，特定维度用生活化语义覆盖（与 public_api.py 共享）
    _LOCAL_CONSUMER_DIM_OPTIONS: Dict[str, List[str]] = {
        'development_stage': ['刚起步', '小有规模', '成熟稳定', '转型探索'],
        'revenue_scale':     ['小本经营', '年入数十万', '年入百万级', '规模化运营'],
        'team_size':         ['个人/夫妻店', '3-10人', '10-50人', '50人以上'],
        'work_years':        ['1-3年', '3-5年', '5-10年', '10年以上'],
    }

    @classmethod
    def _c_end_pain_goal_has_b2b_leak(cls, text: str) -> bool:
        if not text or not str(text).strip():
            return False
        s = str(text).strip()
        return any(x in s for x in cls._C_END_FORBIDDEN_PAIN_GOAL_SUBSTR)

    # C 端痛点里若出现这些「具体状态/对象」锚点，则不再视为纯选品焦虑，避免被领域池首项覆盖
    # 仅保留全行业通用的身体/行为症状，不含任何行业专属词
    _C_END_PAIN_STATE_ANCHORS: Tuple[str, ...] = (
        # 过敏/皮肤类（全行业通用）
        '过敏', '湿疹', '荨麻疹', '皮疹', '瘙痒', '红肿',
        '皮肤', '痘痘', '闭口', '痤疮', '干燥', '脱皮', '红斑',
        # 消化/肠胃类（全行业通用）
        '消化', '肠胃', '腹胀', '便秘', '腹泻', '反胃', '呕吐',
        # 呼吸/鼻腔类（全行业通用）
        '呼吸', '鼻塞', '咳嗽', '喷嚏', '哮喘',
        # 身体变化类（全行业通用）
        '身高', '体重', '发育', '成长', '体能', '体力', '精力',
        # 体表/外观类（全行业通用）
        '头发', '指甲', '面色', '气色', '浮肿', '掉发',
        # 感官/感知类（全行业通用）
        '视力', '听力', '味觉', '嗅觉',
        # 生活行为类（全行业通用）
        '睡眠', '失眠', '嗜睡', '食欲', '厌食', '挑食',
        '情绪', '焦虑', '烦躁', '哭闹', '易怒',
        '记忆', '注意力', '疲劳', '乏力', '疼痛', '酸痛', '麻木',
    )

    @classmethod
    def _batch_pain_is_generic_choice_anxiety(cls, pain: str) -> bool:
        """纯「信息多/不会选/焦虑」类表述，且未落到使用者具体状态 → 与领域长尾池不对齐。"""
        p = (pain or '').strip()
        if not p:
            return True
        anxiety_markers = (
            '信息太多', '信息多', '不知道哪个', '不知道哪款', '选择焦虑', '比较焦虑', '陷入焦虑',
            '拿不准', '不敢下手', '不敢买', '多方比较',
        )
        if not any(m in p for m in anxiety_markers):
            return False
        return not any(a in p for a in cls._C_END_PAIN_STATE_ANCHORS)

    @classmethod
    def _batch_goal_is_generic_c_end(cls, goal: str) -> bool:
        """目标仍停留在「买得放心/省心」等抽象结果，未写使用者状态。"""
        g = (goal or '').strip()
        if not g:
            return True
        if g in ('买得更放心', '买得更值', '买得更方便', '买得更适合', '买得更省心', '省心', '更放心'):
            return True
        if any(a in g for a in cls._C_END_PAIN_STATE_ANCHORS):
            return False
        if len(g) <= 8 and ('买' in g or '放心' in g or '值' in g):
            return True
        return False

    @classmethod
    def _pain_goal_overlaps_domain_option(cls, text: str, domain_opts: List[str]) -> bool:
        """判断当前文案是否与领域细分选项足够接近（目标支持顿号拆分匹配）。"""
        if not text or not domain_opts:
            return False
        t = text.strip()
        for d in domain_opts:
            if not d:
                continue
            if t == d or t in d or d in t:
                return True
            if len(d) >= 8 and d[:12] in t:
                return True
            if len(t) >= 8 and t[:12] in d:
                return True
            # 「宝宝不拉肚子、大便正常」类：任一片段 ≥4 字互含即视为对齐
            for part in re.split(r'[、，,;；]+', d):
                part = part.strip()
                if len(part) >= 4 and (part in t or t in part):
                    return True
            for part in re.split(r'[、，,;；]+', t):
                part = part.strip()
                if len(part) >= 4 and part in d:
                    return True
        return False

    @classmethod
    def _align_batch_pain_goal_to_domain(
        cls,
        batch_pain: str,
        batch_goal: str,
        business_desc: str,
        user_goal_set: bool,
    ) -> tuple:
        """
        当业务描述能命中领域细分池时，若整批统一的痛点/目标仍偏抽象，
        用领域池首项（或更易切长尾的项）对齐顶部「本批共用」横幅与 5 条字段。
        user_goal 由用户显式指定时不改 goal。
        """
        domain = cls._detect_domain_hints(business_desc or '')
        pains = domain.get('pain_point_commonality') or []
        goals = domain.get('goal') or []
        if not pains and not goals:
            return batch_pain, batch_goal

        bp, bg = (batch_pain or '').strip(), (batch_goal or '').strip()
        # 痛点：纯选品焦虑且无状态锚点时，与领域池首项对齐（避免横幅长期「信息太多…」）
        if pains and cls._batch_pain_is_generic_choice_anxiety(bp):
            bp = pains[0]
        if not user_goal_set and goals:
            if not cls._pain_goal_overlaps_domain_option(bg, goals):
                if cls._batch_goal_is_generic_c_end(bg):
                    bg = goals[0]
        return bp, bg

    @classmethod
    def _clean_persona_description_after_batch_unify(
        cls,
        description: str,
        batch_pain: str,
        batch_goal: str,
    ) -> str:
        """
        顶部横幅已展示本批痛点+目标时，卡片正文不应再以同一短标签或 B2B 维度词开头，
        避免与横幅重复，并减少「遇到瓶颈/想要转型」等与瓶装水等 C 端场景不搭的贴标签式开头。
        """
        d = (description or '').strip()
        if not d:
            return d

        bp = (batch_pain or '').strip()
        bg = (batch_goal or '').strip()

        # 维度库中易误贴到 C 端描述开头的 B2B/抽象短词（prompt 已禁，模型仍可能照抄库内词）
        forbidden_opens = (
            '遇到瓶颈',
            '想要转型',
            '寻求突破',
            '想要增长',
            '想要变现',
            '花得值',
            '规模化',
        )

        for _ in range(8):
            matched = False
            # 与横幅完全重复的整句前缀
            for c in sorted([x for x in (bp, bg) if x], key=len, reverse=True):
                if d.startswith(c):
                    rest = d[len(c):].lstrip('，,。、；;：:\t\n ')
                    if rest:
                        d = rest
                        matched = True
                        break
            if matched:
                continue
            for c in forbidden_opens:
                if c and d.startswith(c):
                    rest = d[len(c):].lstrip('，,。、；;：:\t\n ')
                    if rest:
                        d = rest
                        matched = True
                        break
            if not matched:
                break

        # 「标签、标签、自然叙事」：去掉开头与横幅重复或与禁用词相同的段
        if '、' in d:
            parts = [p.strip() for p in d.split('、') if p.strip()]
            drop = set(forbidden_opens)
            if bp:
                drop.add(bp)
            if bg:
                drop.add(bg)
            while parts and parts[0] in drop:
                parts.pop(0)
            if parts:
                d = '、'.join(parts)

        return d.strip()

    @classmethod
    def _unify_c_end_batch_pain_goal(
        cls,
        targets: List[Dict[str, Any]],
        business_type: str,
        user_goal: str = '',
        business_description: str = '',
    ) -> tuple:
        """
        C 端（本地服务/消费品/个人品牌）：同一批 5 条画像共用同一组痛点状态 + 目标；
        过滤 B2B 泄露词；若阶段 1 传了 user_goal 则优先作为本批目标。
        若业务描述命中领域细分池，且模型仍给出抽象痛点/目标，则对齐到领域细分（与维度库一致）。
        返回 (batch_pain, batch_goal)。
        """
        if business_type not in ('local_service', 'product', 'personal') or not targets:
            return '', ''

        batch_pain = ''
        batch_goal = ''

        for t in targets:
            p = (t.get('pain_point_commonality') or '').strip()
            if p and not cls._c_end_pain_goal_has_b2b_leak(p):
                batch_pain = p
                break
        if not batch_pain:
            batch_pain = '选品信息多、不知道哪个更适合，比较焦虑'

        ug = (user_goal or '').strip()
        user_goal_set = bool(ug)
        if ug:
            batch_goal = ug[:120]
        else:
            for t in targets:
                g = (t.get('goal') or '').strip()
                if g and not cls._c_end_pain_goal_has_b2b_leak(g):
                    batch_goal = g
                    break
            if not batch_goal:
                batch_goal = '买得更放心'

        # 与领域细分池对齐（顶部「本批共用」与 LLM 维度库一致）
        batch_pain, batch_goal = cls._align_batch_pain_goal_to_domain(
            batch_pain, batch_goal, business_description, user_goal_set
        )

        unified_sentence = f'{batch_pain} → 希望{batch_goal}'

        for t in targets:
            t['pain_point_commonality'] = batch_pain
            t['goal'] = batch_goal
            t['pain_point'] = unified_sentence
            raw_desc = (t.get('description') or '').strip()
            if raw_desc:
                cleaned = cls._clean_persona_description_after_batch_unify(
                    raw_desc, batch_pain, batch_goal
                )
                t['description'] = cleaned if cleaned.strip() else raw_desc

        return batch_pain, batch_goal

    @classmethod
    def generate(cls, user: PublicUser, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成内容

        Args:
            user: 用户
            params: {
                'industry': str,           # 行业
                'target_customer': str,    # 目标客户（可选，会自动推断）
                'content_type': str,      # 图文/短视频
                'business_description': str, # 业务描述（可选）
                'customer_who': str,      # 客户是谁（可选）
                'customer_why': str,      # 为什么找到（可选）
                'customer_problem': str,   # 解决了什么问题（可选）
                'customer_story': str,     # 客户故事（可选）
                'structure_type': str,     # 结构类型（可选）
                'use_ai': bool,           # 是否使用AI增强
            }

        Returns:
            生成结果
        """
        start_time = time.time()

        industry = params.get('industry', 'general')
        content_type = params.get('content_type', 'graphic')
        business_description = params.get('business_description', '')
        structure_type = params.get('structure_type')
        use_ai = params.get('use_ai', user.is_paid_user())

        # 从新字段推断 target_customer
        target_customer = cls._infer_target_customer(params)

        # 检查配额
        can_generate, reason, quota_info = quota_manager.check_quota(user)
        if not can_generate:
            return {
                'success': False,
                'error': 'quota_exceeded',
                'message': cls._get_quota_message(reason, quota_info),
            }

        # 匹配模板资源
        is_premium = user.is_paid_user()
        resources = template_matcher.match_for_generation(industry, target_customer, is_premium)

        # 生成内容
        tokens_used = 0
        try:
            if use_ai and is_premium:
                # AI增强模式
                result = cls._generate_with_ai(params, resources)
                tokens_used = cls.TOKEN_ESTIMATE['with_ai']['total']
            else:
                # 模板模式（免费用户）
                result = cls._generate_from_template(params, resources)
                tokens_used = cls.TOKEN_ESTIMATE['keyword_only']['total']

            # 保存生成记录
            generation = PublicGeneration(
                user_id=user.id,
                industry=industry,
                target_customer=target_customer,
                content_type=content_type,
                titles=result['titles'],
                tags=result['tags'],
                content=result['content'],
                used_tokens=tokens_used,
                # ── 星系增强：保存客户选择的场景组合 ──
                selected_scenes=params.get('selected_scene'),
            )
            db.session.add(generation)

            # 更新配额
            quota_manager.use_quota(user, tokens_used)

            db.session.commit()

            # 返回结果
            duration = time.time() - start_time
            return {
                'success': True,
                'data': result,
                'meta': {
                    'tokens_used': tokens_used,
                    'duration_ms': int(duration * 1000),
                    'is_ai_enhanced': use_ai and is_premium,
                }
            }

        except Exception as e:
            db.session.rollback()

            # 记录失败日志
            log = PublicLLMCallLog(
                user_id=user.id,
                call_type='content_generate',
                model='gpt-4o-mini',
                status='failed',
                error_message=str(e),
            )
            db.session.add(log)
            db.session.commit()

            return {
                'success': False,
                'error': 'generation_failed',
                'message': f'生成失败: {str(e)}',
            }

    @classmethod
    def identify_customer_identities(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        阶段1：轻量级识别目标客户身份列表

        根据业务描述快速识别可能的目标客户身份，按 ToB/ToC 分类返回。
        这个接口只做身份识别，不生成完整画像，LLM调用量小、速度快。

        Args:
            params: 包含 business_description, business_range, business_type

        Returns:
            {
                'success': True,
                'data': {
                    'to_b': [{'name': '身份名', 'description': '简短描述'}],
                    'to_c': [{'name': '身份名', 'description': '简短描述'}],
                }
            }
        """
        business_desc = (params.get('business_description') or '').strip()
        business_range = params.get('business_range', 'local')
        business_type = params.get('business_type', 'local_service')
        service_scenario = params.get('service_scenario', 'other')
        other_scenario = params.get('other_scenario', '')

        # 获取系统固定底座人群
        system_base_personas = get_system_base_personas(service_scenario, business_type)

        if not business_desc:
            return {
                'success': False,
                'error': 'missing_business_description',
                'message': '请描述您的业务',
            }

        # 获取经营类型中文名
        business_type_name = BUSINESS_TYPE_MAP.get(business_type, '本地服务')

        # 构建轻量级 prompt
        prompt = f"""{PROMPT_BASE_CONSTRAINT.format(system_base_personas=system_base_personas)}
你是一个用户画像专家。根据以下业务信息，快速识别出最可能的目标客户身份类型。

业务描述：{business_desc}
经营范围：{'本地/同城' if business_range == 'local' else '跨区域'}
经营类型：{business_type_name}

=== 身份推导 ===

**核心原则：识别购买/决策侧的稳定身份称呼**

【三层痛点归类规则 - 身份推导时需考虑】

**消费品：**
- 决策层(buyer)：出钱拍板（如：家长、子女、主人）
- 使用层(user)：实际使用者（如：孩子、老人、自己）
- 典型：儿童产品 → buyer=家长，user=孩子

**本地服务：**
- 决策层(buyer)=使用层(user)：自己出钱买给自己用
- 典型：家政/维修 → buyer=user=业主

**企业服务：**
- 决策层(buyer)：出钱拍板（老板、行政总监）
- 对接层：经办联络（行政专员）
- 使用层(user)：实际使用者（员工）
- 典型：企业采购 → buyer=老板，mediator=行政专员，user=员工

【示例】
- 灌香肠 → ToC：过年置办年货的家庭；ToB：早餐店/餐馆老板
- 矿泉水定制 → ToB：企业行政、酒店餐厅、会议组织者；ToC：个人婚宴主家、搬家自用、户外活动组织者
|- 儿童产品 → ToC：有孩子的家庭（购买者是家长，使用者是孩子）
- 手机维修 → ToC：上班族、学生、居民（购买者即使用者）

请按 ToB（企业客户）和 ToC（个人消费者）两类分别列出最可能的身份类型。

【本阶段只做「身份标签」】用户点击后将进入下一步生成详细画像；**不要**在本阶段输出使用者年龄、转奶期、健康目标等细节，那些由下一步结合业务描述再生成。

规则：
- 只输出真实存在的身份，不要编造
- 名称简洁，2-8字以内（如「宝妈」「上班族」）
- buyer.description 一句话说明该身份即可（≤30字），不要写宝宝月龄、具体症状等
- user 字段**必须恒为 null**（本阶段不用）
- 根据业务实际情况决定 ToB/ToC 的数量：
  * 业务描述中明确提到企业客户（酒店/公司/酒店/餐厅/企业/机构等）→ B端客户真实存在，ToB和ToC都要列出
  * 业务描述中以个人客户为主 → ToC为主
  * 通用业务（如桶装水、定制产品等）→ 两者都要考虑，根据描述灵活判断
- 多样化，覆盖不同人群细分
- 标注 "core": true 表示核心人群（气泡词云中会显示更大），一般2-3个最具代表性

输出格式（只返回JSON，不要其他文字）：
{{
    "to_b": [
        {{"buyer": {{"name": "【根据业务生成的B端身份，如：餐饮店老板/企业采购/连锁经理等】", "description": "【一句话描述该身份】"}}, "user": null, "core": true}},
        {{"buyer": {{"name": "【第二个B端身份】", "description": "【一句话描述】"}}, "user": null, "core": false}}
    ],
    "to_c": [
        {{"buyer": {{"name": "【根据业务生成的C端身份，如：家庭主妇/企业员工/附近居民等】", "description": "【一句话描述该身份】"}}, "user": null, "core": true}},
        {{"buyer": {{"name": "【第二个C端身份】", "description": "【一句话描述】"}}, "user": null, "core": false}},
        {{"buyer": {{"name": "【第三个C端身份】", "description": "【一句话描述】"}}, "user": null, "core": true}}
    ]
}}

【重要】以上只是格式示例。请根据上方的「业务描述」来生成真正适合的身份！
- 灌香肠/腊肉/腌制品 → ToC：年节送礼者、置办年货的家庭；ToB：餐馆饭店
- 矿泉水定制 → ToB：企业接待、会议用水、酒店餐厅；ToC：个人婚宴主家、户外活动
- 定制蛋糕 → ToB：企业团购、庆典活动；ToC：生日蛋糕、节日送礼
- 其他业务 → 根据实际产品和目标客户来推断，**不要假设所有客户都是同一类型**
}}"""

        try:
            from services.llm import get_llm_service
            import json
            import re

            service = get_llm_service()
            if not service:
                raise Exception('LLM服务暂不可用')

            response = service.chat(
                prompt,
                temperature=0.5,  # 低温度，结果更稳定
                max_tokens=800,   # 只需要简短输出
            )

            # ========== [调试日志] ==========
            logger.debug("[identify_customer_identities] 开始识别客户身份")
            logger.debug("[identify_customer_identities] 业务描述: %s", business_desc)
            logger.debug("[identify_customer_identities] 经营范围: %s, 经营类型: %s", business_range, business_type)
            logger.debug("[identify_customer_identities] LLM原始响应: %s", response[:500] if response else None)
            # ========== [/调试日志] ==========

            if not response:
                raise Exception('LLM服务暂不可用')

            # 解析JSON响应
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if not match:
                raise Exception('LLM响应格式错误')

            raw = json.loads(match.group(0))

            to_b = raw.get('to_b', [])
            to_c = raw.get('to_c', [])

            # 清理空值（buyer.name 存在才算有效）
            to_b = [x for x in to_b if x.get('buyer', {}).get('name')]
            to_c = [x for x in to_c if x.get('buyer', {}).get('name')]

            # 确保至少有一类有身份
            if not to_b and not to_c:
                raise Exception('未识别到有效的目标客户身份')

            # 兼容旧格式（如果LLM仍返回旧格式）
            def normalize(item):
                # 新格式已有 buyer/user 结构
                if 'buyer' in item:
                    return item
                # 旧格式兼容：转换为新格式
                return {
                    'buyer': {'name': item.get('name', ''), 'description': item.get('description', '')},
                    'user': None,
                    'core': item.get('core', False)
                }

            to_b = [normalize(x) for x in to_b]
            to_c = [normalize(x) for x in to_c]

            # 阶段1 仅身份：丢弃 LLM 可能仍返回的 user，避免气泡出现「给0-1岁宝宝→目标」等冗余
            def strip_user_for_stage1(item: Dict[str, Any]) -> Dict[str, Any]:
                out = dict(item)
                out['user'] = None
                return out

            to_b = [strip_user_for_stage1(x) for x in to_b]
            to_c = [strip_user_for_stage1(x) for x in to_c]

            def dedupe_by_buyer_name(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                seen: set = set()
                out: List[Dict[str, Any]] = []
                # 先 core=true，再其余，减少重复名时丢掉非核心
                core_first = sorted(items, key=lambda x: (not x.get('core'), x.get('buyer', {}).get('name', '')))
                for it in core_first:
                    nm = (it.get('buyer') or {}).get('name', '').strip()
                    if not nm or nm in seen:
                        continue
                    seen.add(nm)
                    out.append(it)
                return out

            to_b = dedupe_by_buyer_name(to_b)[:8]
            to_c = dedupe_by_buyer_name(to_c)[:8]

            # ========== [调试日志] ==========
            logger.debug("[identify_customer_identities] ToB身份: %s", [x.get("buyer", {}).get("name", "") for x in to_b])
            logger.debug("[identify_customer_identities] ToC身份: %s", [x.get("buyer", {}).get("name", "") for x in to_c])
            logger.debug("[identify_customer_identities] 识别完成")
            # ========== [/调试日志] ==========

            return {
                'success': True,
                'data': {
                    'to_b': to_b,
                    'to_c': to_c,
                }
            }

        except Exception as e:
            import traceback
            logger.error("[identify_customer_identities] 异常: %s", e)
            logger.exception("[identify_customer_identities] 堆栈")
            return {
                'success': False,
                'error': 'llm_unavailable',
                'message': '服务暂时不可用，请稍后重试',
            }

    @classmethod
    def generate_target_customers(cls, user: PublicUser, params: Dict[str, Any],
                                  use_ai_enhancement: bool = False) -> Dict[str, Any]:
        """
        生成目标用户画像（身份 + 痛点 + 目标，全部由 LLM 结合业务场景自由推导）

        Args:
            user: 用户
            params: 包含业务描述和深度了解信息
            use_ai_enhancement: 是否使用AI增强（付费用户）

        Returns:
            5个目标用户画像
        """
        business_desc = params.get('business_description', '')
        business_range = params.get('business_range', '')
        business_type = params.get('business_type', '')
        customer_who = params.get('customer_who', '')
        customer_why = params.get('customer_why', '')
        customer_problem = params.get('customer_problem', '')
        customer_story = params.get('customer_story', '')
        customer_experiences = params.get('customer_experiences', [])

        targets: List[Dict] = []
        used_llm_primary = False

        # C 端业务：LLM 可用时优先直出画像
        if (
            cls._llm_available()
            and business_type in ('local_service', 'product', 'personal')
        ):
            try:
                llm_targets = cls._generate_targets_pure_llm(params)
                if llm_targets and len(llm_targets) >= 5:
                    targets = llm_targets[:5]
                    used_llm_primary = True
            except Exception as e:
                logger.warning("[ContentGenerator] LLM画像直出失败，回退规则: %s", e)

        if not targets:
            targets = cls._generate_targets_by_rules(params)

        # 付费套餐 AI 增强
        if use_ai_enhancement and cls._llm_available() and not used_llm_primary:
            try:
                enhanced_targets = cls._enhance_targets_with_ai(targets, params)
                if enhanced_targets:
                    targets = enhanced_targets
            except Exception as e:
                logger.warning("[ContentGenerator] AI增强失败，使用规则结果: %s", e)

        # C 端：整批统一痛点状态 + 目标，供前端顶部一次展示
        batch_pain = ''
        batch_goal = ''
        if business_type in ('local_service', 'product', 'personal') and targets:
            batch_pain, batch_goal = cls._unify_c_end_batch_pain_goal(
                targets, business_type,
                user_goal=(params.get('user_goal') or '').strip(),
                business_description=params.get('business_description', '') or '',
            )

        return {
            'success': True,
            'data': {
                'targets': targets,
                'business_description': business_desc,
                'batch_pain_point_commonality': batch_pain,
                'batch_goal': batch_goal,
                'ai_enhanced': bool(
                    used_llm_primary
                    or (use_ai_enhancement and cls._llm_available())
                ),
            }
        }

    @classmethod
    def identify_problems_and_initial_personas(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        阶段1：挖掘使用方问题和付费方顾虑，并默认生成第一批人群画像

        Args:
            params: 包含 business_description, business_range, business_type

        Returns:
            {
                'success': True,
                'data': {
                    'problems': {
                        'user_pains': [  // 使用方问题
                            {
                                'id': 'up_1',
                                'name': '问题名称',
                                'description': '问题描述',
                                'severity': '高/中/低',
                                'buyer_relation': '买用关系说明'
                            }
                        ],
                        'buyer_concerns': [  // 付费方顾虑
                            {
                                'id': 'bc_1',
                                'name': '顾虑类型',
                                'description': '顾虑描述',
                                'examples': ['具体例子1', '具体例子2']
                            }
                        ]
                    },
                    'initial_batch': {  // 默认生成的第一批人群
                        'problem_id': 'up_1',  // 对应的问题ID
                        'problem_type': 'user_pain',
                        'targets': [...],  // 5条人群画像
                        'batch_pain_point_commonality': '...',
                        'batch_goal': '...'
                    },
                    'buyer_user_relation': {
                        'is_separate': True/False,  // 购买方是否不等于使用方
                        'description': '买用关系描述'
                    }
                }
            }
        """
        business_desc = (params.get('business_description') or '').strip()
        business_range = params.get('business_range', 'local')
        business_type = params.get('business_type', 'local_service')
        customer_who = (params.get('customer_who') or '').strip()
        customer_why = (params.get('customer_why') or '').strip()
        customer_problem = (params.get('customer_problem') or '').strip()
        customer_story = (params.get('customer_story') or '').strip()
        service_scenario = (params.get('service_scenario') or '').strip()
        local_city = (params.get('local_city') or '').strip()

        try:
            # 调用LLM挖掘问题
            problems = cls._挖掘_使用方_付费方问题(
                business_desc, business_range, business_type,
                customer_who, customer_why, customer_problem, customer_story,
                service_scenario, local_city
            )

            # 默认基于第一个使用方问题生成第一批人群画像
            initial_batch = None
            if problems.get('user_pains'):
                first_problem = problems['user_pains'][0]
                initial_batch = cls._generate_persona_batch(
                    params, first_problem, 'user_pain'
                )
            elif problems.get('buyer_concerns'):
                first_problem = problems['buyer_concerns'][0]
                initial_batch = cls._generate_persona_batch(
                    params, first_problem, 'buyer_concern'
                )

            return {
                'success': True,
                'data': {
                    'problems': problems,
                    'initial_batch': initial_batch,
                    'buyer_user_relation': problems.get('buyer_user_relation', {
                        'is_separate': False,
                        'description': '购买者即使用者'
                    })
                }
            }

        except Exception as e:
            import traceback
            logger.error("[identify_problems_and_initial_personas] 异常: %s", e)
            logger.exception("[identify_customer_identities] 堆栈")
            return {
                'success': False,
                'error': 'llm_unavailable',
                'message': '服务暂时不可用，请稍后重试',
            }

    @classmethod
    def generate_persona_batch_by_problem(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        阶段2：基于指定问题生成人群画像批次

        Args:
            params: 包含 business_description, problem_id, problem_type, 等

        Returns:
            {
                'success': True,
                'data': {
                    'problem': {...},  // 问题详情
                    'targets': [...],   // 5条人群画像
                    'batch_pain_point_commonality': '...',
                    'batch_goal': '...'
                }
            }
        """
        problem_id = params.get('problem_id', '')
        problem_type = params.get('problem_type', '')  # 'user_pain' or 'buyer_concern'
        business_desc = (params.get('business_description') or '').strip()

        try:
            # 先重新挖掘问题列表
            business_range = params.get('business_range', 'local')
            business_type = params.get('business_type', 'local_service')
            customer_who = (params.get('customer_who') or '').strip()
            customer_why = (params.get('customer_why') or '').strip()
            customer_problem = (params.get('customer_problem') or '').strip()
            customer_story = (params.get('customer_story') or '').strip()
            service_scenario = (params.get('service_scenario') or '').strip()
            local_city = (params.get('local_city') or '').strip()

            problems = cls._挖掘_使用方_付费方问题(
                business_desc, business_range, business_type,
                customer_who, customer_why, customer_problem, customer_story,
                service_scenario, local_city
            )

            # 找到指定的问题
            target_problem = None
            if problem_type == 'user_pain':
                for p in problems.get('user_pains', []):
                    if p.get('id') == problem_id:
                        target_problem = p
                        break
            elif problem_type == 'buyer_concern':
                for p in problems.get('buyer_concerns', []):
                    if p.get('id') == problem_id:
                        target_problem = p
                        break

            if not target_problem:
                return {
                    'success': False,
                    'message': '未找到指定的问题'
                }

            # 生成人群画像批次
            batch = cls._generate_persona_batch(
                params, target_problem, problem_type
            )

            return {
                'success': True,
                'data': {
                    'problem': target_problem,
                    'targets': batch.get('targets', []),
                    'batch_pain_point_commonality': batch.get('batch_pain_point_commonality', ''),
                    'batch_goal': batch.get('batch_goal', '')
                }
            }

        except Exception as e:
            import traceback
            logger.error("[generate_persona_batch_by_problem] 异常: %s", e)
            logger.exception("[identify_customer_identities] 堆栈")
            return {
                'success': False,
                'error': 'generation_failed',
                'message': '生成失败，请稍后重试',
            }

    @classmethod
    def _挖掘_使用方_付费方问题(
        cls,
        business_desc: str,
        business_range: str,
        business_type: str,
        customer_who: str = '',
        customer_why: str = '',
        customer_problem: str = '',
        customer_story: str = '',
        service_scenario: str = '',
        local_city: str = ''
    ) -> Dict[str, Any]:
        """
        调用LLM挖掘使用方问题和付费方顾虑

        Returns:
            {
                'user_pains': [...],
                'buyer_concerns': [...],
                'buyer_user_relation': {
                    'is_separate': bool,
                    'description': str
                }
            }
        """
        # 构建辅助信息
        aux_parts = []
        if customer_who:
            aux_parts.append(f'- 典型客户：{customer_who}')
        if customer_why:
            aux_parts.append(f'- 触达动机：{customer_why}')
        if customer_problem:
            aux_parts.append(f'- 核心问题：{customer_problem}')
        if customer_story:
            aux_parts.append(f'- 客户故事：{customer_story[:200]}')
        
        # 服务场景作为重要参考
        if service_scenario:
            scenario_map = {
                'hotel_restaurant': '酒店/餐饮/茶楼/高端会所',
                'residential': '家用/住宅/小区业主',
                'office_enterprise': '写字楼/企业/工厂/园区',
                'institutional': '学校/医院/食堂/政企单位',
                'retail_chain': '实体店/连锁门店/加盟品牌',
                'renovation': '装修/工装/工程定制',
                'other': '其他小众场景'
            }
            scenario_text = scenario_map.get(service_scenario, service_scenario)
            aux_parts.append(f'- 主要服务场景：{scenario_text}')
        
        # 本地城市信息
        if business_range == 'local' and local_city:
            aux_parts.append(f'- 服务城市：{local_city}')
        
        aux_section = '\n'.join(aux_parts) if aux_parts else '（未填写辅助信息）'

        # 获取系统固定底座人群
        system_base_personas = get_system_base_personas(service_scenario, business_type)

        # 根据业务类型判断买用关系
        is_to_business = business_type == 'enterprise'
        buyer_user_hint = ""

        if not is_to_business:
            # C端：需要判断买用是否分离
            buyer_user_hint = """
【买用关系判断 - 必须按三层结构生成】

**消费品（买用分离为主）：**
- 决策层(buyer)：出钱/拍板（宝妈、子女、家长）
- 使用层(user)：实际使用者（孩子、老人、自己）

**本地服务（买用合一为主）：**
- 使用层(user) = 决策层(buyer)：自己出钱买给自己用

**企业服务（三层分离）：**
- 决策层(buyer)：出钱/拍板（老板、行政总监）
- 对接层：经办/联络（行政专员）
- 使用层(user)：实际使用者（员工）"""

        # 获取经营类型中文名
        business_type_name = BUSINESS_TYPE_MAP.get(business_type, '本地服务')

        # 动态生成问题维度（根据经营类型差异化）
        user_problem_section = build_user_problem_section(business_type)
        buyer_concern_section = build_buyer_concern_section(business_type)

        prompt = f"""{PROMPT_BASE_CONSTRAINT.format(system_base_personas=system_base_personas)}
你是问题挖掘专家。请根据以下业务信息，挖掘**使用方问题**和**付费方顾虑**。

业务描述：{business_desc}
经营范围：{'本地/同城' if business_range == 'local' else '跨区域/全国'}
经营类型：{business_type_name}

辅助信息：
{aux_section}

{buyer_user_hint}

{user_problem_section}

{buyer_concern_section}

=== 买用关系 ===
- 买即用：买的人=用的人（如桶装水、自用食品、餐饮）
- 买用分离：买的人≠用的人（如家长买给孩子、老人用品是子女买给老人）
- 涉及孩子、老人、宠物等，**可能是买用分离**，根据实际业务描述判断

=== 输出格式（严格JSON） ===
{{
    "user_pains": [
        {{"id": "up_1", "name": "问题类型", "description": "具体表现", "severity": "高/中/低"}}
    ],
    "buyer_concerns": [
        {{"id": "bc_1", "name": "顾虑类型", "description": "具体表现"}}
    ],
    "buyer_user_relation": {{
        "is_separate": true/false,
        "description": "买用关系说明"
    }}
}}"""

        try:
            from services.llm import get_llm_service
            import json
            import re

            service = get_llm_service()
            if not service:
                raise Exception('LLM服务暂不可用')

            response = service.chat(
                prompt,
                temperature=0.5,
                max_tokens=2000,
            )

            logger.debug("[_挖掘_使用方_付费方问题] 业务描述: %s", business_desc)
            logger.debug("[_挖掘_使用方_付费方问题] LLM响应前500字: %s", response[:500] if response else None)

            if not response:
                raise Exception('LLM服务暂不可用')

            # 解析JSON响应
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if not match:
                raise Exception('LLM响应格式错误')

            result = json.loads(match.group(0))

            # 确保ID唯一
            for i, p in enumerate(result.get('user_pains', [])):
                if not p.get('id'):
                    p['id'] = f'up_{i+1}'
                if not p.get('name'):
                    p['name'] = f'问题{i+1}'

            for i, p in enumerate(result.get('buyer_concerns', [])):
                if not p.get('id'):
                    p['id'] = f'bc_{i+1}'
                if not p.get('name'):
                    p['name'] = f'顾虑{i+1}'

            return result

        except Exception as e:
            logger.error("[_挖掘_使用方_付费方问题] 异常: %s", e)
            import traceback
            logger.exception("[_挖掘_使用方_付费方问题] 堆栈")
            raise Exception('LLM服务暂不可用，请稍后重试')

    @classmethod
    def _generate_persona_batch(
        cls,
        params: Dict[str, Any],
        problem: Dict[str, Any],
        problem_type: str  # 'user_pain' or 'buyer_concern'
    ) -> Dict[str, Any]:
        """
        基于指定问题生成一批人群画像（5条）

        Args:
            params: 业务参数
            problem: 问题详情
            problem_type: 'user_pain' 或 'buyer_concern'

        Returns:
            {
                'problem_id': '...',
                'problem_type': '...',
                'targets': [...],  // 5条人群画像
                'batch_pain_point_commonality': '...',
                'batch_goal': '...'
            }
        """
        business_desc = (params.get('business_description') or '').strip()
        business_range = params.get('business_range', 'local') or 'local'
        business_type = params.get('business_type', 'local_service') or 'local_service'

        customer_who = (params.get('customer_who') or '').strip()
        customer_why = (params.get('customer_why') or '').strip()
        customer_problem = (params.get('customer_problem') or '').strip()
        customer_story = (params.get('customer_story') or '').strip()
        service_scenario = params.get('service_scenario', 'other')

        # 获取系统固定底座人群
        system_base_personas = get_system_base_personas(service_scenario, business_type)

        # 构建辅助信息
        aux_parts = []
        if customer_who:
            aux_parts.append(f'- 典型客户：{customer_who}')
        if customer_why:
            aux_parts.append(f'- 触达动机：{customer_why}')
        if customer_problem:
            aux_parts.append(f'- 核心问题：{customer_problem}')
        if customer_story:
            aux_parts.append(f'- 客户故事：{customer_story[:200]}')
        aux_section = '\n'.join(aux_parts) if aux_parts else '（未填写辅助信息）'

        # 获取领域预设组合
        preset_combos = cls._get_domain_preset_combos(business_desc, business_type)

        # 获取经营类型中文名
        business_type_name = BUSINESS_TYPE_MAP.get(business_type, '本地服务')

        # 根据问题类型构建不同的prompt约束
        if problem_type == 'user_pain':
            # 使用方问题方向
            pain_point_constraint = f"""【使用方问题聚焦】
本批次统一聚焦：**{problem.get('name', '使用方问题')}**
- pain_point_commonality = {problem.get('description', problem.get('name', ''))}
- 所有画像都围绕这个使用方问题展开
- goal = 解决这个问题后的期望状态

示例：
- 问题：使用效果不理想
- pain_point_commonality：「使用某产品后效果不明显、不舒适」
- goal：「找到适合自己的产品、解决问题」
"""
            direction_label = 'A方向（使用方问题）'
        else:
            # 付费方顾虑方向
            pain_point_constraint = f"""【付费方顾虑聚焦】
本批次统一聚焦：**{problem.get('name', '付费方顾虑')}**
- pain_point_commonality = {problem.get('description', problem.get('name', ''))}
- 所有画像都围绕这个付费方顾虑展开
- goal = 消除这个顾虑后的期望状态

示例：
- 顾虑：真假顾虑
- pain_point_commonality：「太多评测说法不一、越看越不知道选哪款、怕买到假货」
- goal：「有明确推荐跟着选不会错、知道怎么验真伪、买得放心」
"""
            direction_label = 'B方向（付费方顾虑）'

        prompt = f"""{PROMPT_BASE_CONSTRAINT.format(system_base_personas=system_base_personas)}
你是用户画像专家。请根据以下业务信息，基于**指定问题**生成5个精准的目标用户画像。

=== 业务基本信息 ===
业务描述：{business_desc}
经营范围：{business_range}
经营类型：{business_type_name}

=== 【本批问题·强制聚焦】===
{direction_label}

{pain_point_constraint}

问题详情：{problem.get('description', problem.get('name', ''))}
严重程度：{problem.get('severity', '中')}
买用关系：{problem.get('buyer_relation', '买即用')}

=== 预设维度组合 ===
{preset_combos}

=== 核心原则 ===

**三层痛点归类规则（必须遵守）：**

**user_problem_types（使用层）- 全部原始搜索动因：**
- 前置客观症状/异常/损耗/不适：拉肚子、过敏、故障、损耗、氧化、发黄、发霉
- 后置使用体验痛点：不方便、不好看、不舒服、影响心情
- 注意：这是用户"因为这个问题难受，才主动去搜解决方案"的原始动因

**buyer_concern_types（决策层）- 仅限付费/成本顾虑：**
- 付费顾虑：怕买贵、怕被宰、怕不值
- 成本顾虑：年预算、月消耗、采购成本
- 风险顾虑：怕质量不稳定、怕断供、怕售后无保障

**对接层 - 落地执行痛点：**
- 流程对接：审批繁琐、对接人多、沟通成本高
- 落地执行：安装难、配送慢、服务响应差

**三层身份关系：**

**消费品（买用分离）：**
- 决策层(buyer)：出钱拍板（宝妈、子女、家长）
- 使用层(user)：实际使用者（孩子、老人）
- buyer_user_relation = 「买给1-3岁宝宝/买给老人/自用」

**本地服务（买用合一）：**
- 决策层(buyer)=使用层(user)：本人出钱本人用
- buyer_user_relation = 「自用」

**企业服务（三层分离）：**
- 决策层(buyer)：出钱拍板（老板、行政总监）
- 对接层：经办联络（行政专员）
- 使用层(user)：实际使用者（员工、工人）
- buyer_user_relation = 「老板买给员工用/买给公司用」

**【重要】业务描述里有「宝宝」「孩子」「老人」「宠物」相关需求 → 必为买用分离！****
- 矿泉水/定制产品：可能企业采购（酒店/公司）+ 个人定制（婚宴/寿宴）都存在
- 要根据具体业务描述判断，不要假设所有客户都是同一类型

=== 输出格式（只返回JSON数组，5个对象）===
{{
    "targets": [
        {{
            "name": "细分人群简称（≤6字）",
            "description": "自然语言描述，包含维度组合",
            "pain_point_commonality": "来自问题的核心痛点描述",
            "goal": "解决后的期望状态",
            "buyer_user_relation": "买给谁/自用",
            "age_range": "使用者年龄段",
            "geo_tag": "地域",
            "consumption_stage": "消费阶段",
            "occupation": "职业",
            "pain_point": "痛点→目标 格式",
            "needs": "2-3条需求",
            "behaviors": "2-3条决策行为"
        }}
    ],
    "batch_pain_point_commonality": "本批统一的痛点描述",
    "batch_goal": "本批统一的目标"
}}

只输出JSON，不要其他文字。"""

        try:
            from services.llm import get_llm_service
            import json
            import re

            service = get_llm_service()
            if not service:
                raise Exception('LLM服务暂不可用')

            response = service.chat(
                prompt,
                temperature=0.7,
                max_tokens=3000,
            )

            logger.debug("[_generate_persona_batch] 问题: %s", problem.get("name", ""))
            logger.debug("[_generate_persona_batch] LLM响应前500字: %s", response[:500] if response else None)

            if not response:
                raise Exception('LLM服务暂不可用')

            # 解析JSON响应 - 改进鲁棒性
            result = None
            # 方法1: 尝试匹配完整的 JSON 对象
            match = re.search(r'\{[\s\S]*\}', response, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(0))
                    logger.debug("[_generate_persona_batch] JSON解析成功(方法1)")
                except json.JSONDecodeError as je:
                    logger.debug("[_generate_persona_batch] JSON解析失败(方法1): %s", je)
                    result = None
            
            # 方法2: 如果方法1失败，尝试匹配数组
            if not result:
                match = re.search(r'\[[\s\S]*\]', response, re.DOTALL)
                if match:
                    try:
                        parsed = json.loads(match.group(0))
                        if isinstance(parsed, list):
                            result = {'targets': parsed}
                            logger.debug("[_generate_persona_batch] JSON解析成功(方法2-数组)")
                        else:
                            result = parsed
                    except json.JSONDecodeError as je:
                        logger.debug("[_generate_persona_batch] JSON解析失败(方法2): %s", je)
            
            # 方法3: 尝试直接解析整个响应
            if not result:
                try:
                    result = json.loads(response.strip())
                    logger.debug("[_generate_persona_batch] JSON解析成功(方法3-直接)")
                except json.JSONDecodeError as je:
                    logger.debug("[_generate_persona_batch] JSON解析失败(方法3): %s", je)
            
            if not result:
                raise Exception('LLM响应格式错误，无法解析JSON')

            targets = result.get('targets', [])
            if not isinstance(targets, list):
                targets = [targets] if isinstance(targets, dict) else []
            
            logger.debug("[_generate_persona_batch] 解析到targets数量: %s", len(targets))

            # 清理数据
            cleaned_targets = []
            for t in targets[:5]:
                if not isinstance(t, dict):
                    continue
                cleaned_targets.append({
                    'name': (t.get('name') or '').strip()[:12] or '人群',
                    'description': (t.get('description') or '').strip(),
                    'pain_point_commonality': (t.get('pain_point_commonality') or '').strip(),
                    'goal': (t.get('goal') or '').strip(),
                    'buyer_user_relation': (t.get('buyer_user_relation') or '').strip(),
                    'age_range': (t.get('age_range') or '').strip() or '不限',
                    'geo_tag': (t.get('geo_tag') or '').strip(),
                    'consumption_stage': (t.get('consumption_stage') or '').strip(),
                    'occupation': (t.get('occupation') or '').strip(),
                    'pain_point': (t.get('pain_point') or '').strip(),
                    'needs': str(t.get('needs', '')).strip(),
                    'behaviors': str(t.get('behaviors', '')).strip(),
                })

            logger.debug("[_generate_persona_batch] 清理后targets数量: %s", len(cleaned_targets))

            return {
                'problem_id': problem.get('id', ''),
                'problem_type': problem_type,
                'targets': cleaned_targets,
                'batch_pain_point_commonality': result.get('batch_pain_point_commonality', problem.get('description', '')),
                'batch_goal': result.get('batch_goal', '解决问题')
            }

        except Exception as e:
            import traceback
            logger.error("[_generate_persona_batch] 异常: %s", e)
            logger.debug("[_generate_persona_batch] 堆栈: %s", traceback.format_exc())
            return {
                'problem_id': problem.get('id', ''),
                'problem_type': problem_type,
                'targets': [],
                'batch_pain_point_commonality': problem.get('description', ''),
                'batch_goal': '解决问题'
            }

    @classmethod
    def _llm_available(cls) -> bool:
        """检查 LLM 服务是否可用（实例存在且非 None）"""
        try:
            from services.llm import llm_service, get_llm_service
            # llm_service 可能是 None，换用 get_llm_service() 获取实例
            return llm_service is not None or get_llm_service() is not None
        except ImportError:
            return False

    @classmethod
    def _enhance_targets_with_ai(cls, base_targets: List[Dict], params: Dict) -> List[Dict]:
        """使用AI增强目标用户画像"""
        business_desc = params.get('business_description', '')
        customer_who = params.get('customer_who', '')
        customer_why = params.get('customer_why', '')
        customer_problem = params.get('customer_problem', '')
        customer_story = params.get('customer_story', '')
        service_scenario = params.get('service_scenario', 'other')
        local_city = params.get('local_city', '')

        business_range = params.get('business_range', '')
        business_type = params.get('business_type', '')

        # 获取系统固定底座人群
        system_base_personas = get_system_base_personas(service_scenario, business_type)

        # 构建prompt
        prompt = PROMPT_BASE_CONSTRAINT.format(system_base_personas=system_base_personas) + f"""你是一个用户画像分析专家。根据以下信息，生成5个精准的目标用户画像。

业务描述：{business_desc}
经营范围：{business_range or '（未填）'}
经营类型：{BUSINESS_TYPE_MAP.get(business_type, '本地服务')}

{filled_info}

硬性约束（必须遵守）：
- 画像必须与业务描述中的行业、地域、服务类型一致；可合理推断周边人群，禁止凭空套用无关行业。
- 若经营类型为「local_service」本地服务或「product」消费品，画像应是终端消费者、本地居民、店主/业主等 C 端或小微场景，禁止默认生成「互联网/科技公司」的董事长、VP、总监、经理等企业高管模板。
- 若经营类型为「enterprise」企业服务，才可使用 B2B 决策者角色（创始人/总监/采购等）。
- 若用户明确写了地名（如县城、区名），地域画像应贴近该范围。

请为每个目标用户生成：
1. name: 用户类型名称（如"写字楼行政负责人"）
2. description: 详细描述用户的特征、决策权、需求
3. age_range: 年龄段
4. occupation: 具体职业
5. pain_point: 核心痛点
6. needs: 具体需求（3-5个）
7. behaviors: 购买行为特征

请用JSON数组格式返回，例如：
[
  {{
    "name": "写字楼行政",
    "description": "负责整栋写字楼的行政后勤...",
    "age_range": "28-40岁",
    "occupation": "行政经理",
    "pain_point": "配送不及时，经常被投诉",
    "needs": "稳定供货、价格合理、服务响应快",
    "behaviors": "通过供应商名录和同行推荐寻找供应商"
  }}
]

只返回JSON数组，不要其他文字。""".format(
            filled_info=cls._build_filled_info(customer_who, customer_why, customer_problem, customer_story, service_scenario, local_city)
        )

        try:
            from services.llm import get_llm_service
            service = get_llm_service()
            if not service:
                return None
            response = service.chat(
                prompt,
                temperature=0.7,
                max_tokens=2000,
            )

            # 解析JSON响应
            import json
            import re

            # 提取JSON数组
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                enhanced = json.loads(match.group(0))
                if isinstance(enhanced, list) and len(enhanced) >= 5:
                    return enhanced[:5]

        except Exception as e:
            logger.warning("[ContentGenerator] AI增强解析失败: %s", e)

        return None

    @classmethod
    def _get_domain_preset_combos(cls, business_desc: str, business_type: str) -> str:
        """
        根据业务描述返回预设的精准维度组合。
        每个组合格式：维度1 × 维度2 × 维度3 + 使用者 + 目标 + 焦虑 + 身份
        """
        desc = (business_desc or '').lower()

        # ── 通用自适应组合（不再按行业硬编码，改为从业务描述动态推导）─────────
        # 生成3个通用维度组合，格式统一为：维度组合 + 使用者 + 目标 + 焦虑 + 身份
        # 所有内容由AI根据实际业务描述自行推理，不预设任何行业专属词
        return """
【组合1·核心用户群体A】
- 维度：消费阶段、地域、职业（由业务描述推导）
- 使用者：业务描述中的实际使用者
- 目标：使用后想达成的具体状态
- 焦虑：决策时的具体顾虑
- 身份：购买决策者身份

【组合2·核心用户群体B】
- 维度：消费阶段、地域、职业（由业务描述推导）
- 使用者：业务描述中的实际使用者
- 目标：使用后想达成的具体状态
- 焦虑：决策时的具体顾虑
- 身份：购买决策者身份

【组合3·长尾细分群体】
- 维度：消费阶段、地域、职业（由业务描述推导）
- 使用者：业务描述中的实际使用者
- 目标：使用后想达成的具体状态
- 焦虑：决策时的具体顾虑
- 身份：购买决策者身份
"""

        # ── 老人/健康 ───────────────────────────────────────────────────────────
        if any(k in desc for k in ('老人', '老年', '爸妈', '长辈', '钙片', '保健', '血压', '血糖', '血脂', '养老')):
            return """
【组合1·孝顺子女】
- 维度：子女年龄（30-45岁）、地域（异地/同城）、收入（中等以上）
- 使用者：60岁以上父母
- 目标：老人身体好、少生病
- 焦虑：不知道怎么补、担心老人不配合
- 身份：孝顺子女

【组合2·老人自用】
- 维度：年龄（60-75岁）、地域（县城/社区）、健康状态（三高/腿脚不便）
- 使用者：老人自己
- 目标：改善身体状况、用起来方便
- 焦虑：操作复杂、不敢乱买
- 身份：关注健康的老人"""

        # ── 宠物 ────────────────────────────────────────────────────────────────
        if any(k in desc for k in ('宠物', '猫粮', '狗粮', '猫砂', '宠物食品', '宠物用品')):
            return """
【组合1·新手宠物主】
- 维度：宠物年龄（幼猫/幼犬）、地域（城区）、养宠经验（新手）
- 使用者：宠物
- 目标：宠物健康成长、不拉肚子
- 焦虑：不知道哪款粮好、怕选错
- 身份：新手宠物主

【组合2·过敏/挑食宠物主】
- 维度：宠物状态（挑食/过敏）、地域（任意）、养宠经验（有一定经验）
- 使用者：宠物
- 目标：找到适合的粮、解决挑食/过敏问题
- 焦虑：换了好多款都不行、不知道怎么办
- 身份：焦急的宠物主"""

        # ── 手机/数码维修 ─────────────────────────────────────────────────────
        if cls._desc_has_electronics_service(desc) and not any(k in desc for k in ('奶粉', '母婴', '婴儿', '宝宝')):
            return """
【组合1·急用上班族】
- 维度：职业（上班族）、地域（城区）、时间状态（急用）
- 使用者：手机/数码产品使用者
- 目标：当场修好、不丢资料
- 焦虑：急用但不知道哪家靠谱、怕被坑
- 身份：着急的上班族

【组合2·担心资料的商务人士】
- 维度：职业（商务/管理）、地域（城区）、收入（中高）
- 使用者：手机/数码产品使用者
- 目标：修好手机、保住资料
- 焦虑：怕偷换件、怕资料丢失、怕报价不透明
- 身份：谨慎的商务人士"""

        # ── 桶装水/配送 ───────────────────────────────────────────────────────
        if any(k in desc for k in ('桶装水', '矿泉水', '水站', '配送', '饮用水')):
            return """
【组合1·家庭自用】
- 维度：家庭结构（有孩/有老）、地域（县城/社区）、消费习惯（注重健康）
- 使用者：家庭成员
- 目标：喝到安全可靠的桶装水
- 焦虑：不知道哪家水质好、怕喝到假水
- 身份：注重健康的家庭主妇/主夫

【组合2·办公场所】
- 维度：场所类型（办公室/公司）、人数规模（10-50人）、需求（日常饮用）
- 使用者：员工/访客
- 目标：稳定供应、水质安全、价格合理
- 焦虑：配送不及时、水质没保障
- 身份：行政/采购负责人"""

        # ── 默认通用组合（无匹配时使用）────────────────────────────────────────
        return """
【组合1·价格敏感型】
- 维度：收入（中等以下）、地域（县城/郊区）、消费习惯（精打细算）
- 使用者：（根据业务定）
- 目标：（根据业务定）
- 焦虑：担心买的产品用完症状加重
- 身份：谨慎的消费者

【组合2·品质优先型】
- 维度：收入（中上）、地域（城区）、消费习惯（注重品质）
- 使用者：（根据业务定）
- 目标：（根据业务定）
- 焦虑：不知道哪款更好、怕买错
- 身份：追求品质的消费者

【组合3·新手小白型】
- 维度：消费经验（新手）、地域（任意）、年龄（年轻）
- 使用者：（根据业务定）
- 目标：（根据业务定）
- 焦虑：担心用完有不适/不知道怎么处理
- 身份：担忧的新用户

【组合4·理性比较型】
- 维度：消费经验（有经验）、地域（城区）、年龄（25-40岁）
- 使用者：（根据业务定）
- 目标：（根据业务定）
- 焦虑：信息太多、分不清真假
- 身份：喜欢研究的理性消费者

【组合5·口碑依赖型】
- 维度：消费习惯（信口碑）、地域（社区/县城）、年龄（30-50岁）
- 使用者：（根据业务定）
- 目标：（根据业务定）
- 焦虑：广告太多不敢信、不知道信谁
- 身份：依赖口碑推荐的消费者"""

    @classmethod
    def _generate_targets_pure_llm(cls, params: Dict[str, Any]) -> Optional[List[Dict]]:
        """
        面向 C 端（本地服务/消费品/个人品牌）直接用 LLM 生成 5 条画像，
        从预设组合中选取5个精准画像，而非凭空发挥。
        
        批次方向策略：每次生成时随机选择 A 或 B 方向，同批 5 条共用同一方向
        - A方向（使用者问题）：痛点聚焦使用者本身的状态/症状，目标是解决使用者问题
        - B方向（购买者焦虑）：痛点聚焦购买决策时的心理障碍，目标是买得放心
        """
        business_desc = (params.get('business_description') or '').strip()
        business_range = params.get('business_range', '') or '（未填）'
        business_type = params.get('business_type', '') or '（未填）'
        service_scenario = params.get('service_scenario', 'other')

        # 获取系统固定底座人群
        system_base_personas = get_system_base_personas(service_scenario, business_type)

        # 换一批时使用 refresh_nonce 控制随机性
        import random
        refresh_nonce = params.get('refresh_nonce')
        if refresh_nonce is not None:
            rng = random.Random(hash(str(refresh_nonce)) % (2 ** 32))
            # 换一批时使用更高温度产生变化
            llm_temperature = 0.85 + (hash(str(refresh_nonce)) % 15) / 100  # 0.85 ~ 1.0
        else:
            rng = random.Random()
            llm_temperature = 0.85
        
        batch_direction = rng.choice(['A', 'B'])
        batch_direction_label = 'A方向（宝宝/用户自身问题）' if batch_direction == 'A' else 'B方向（购买者决策焦虑）'

        # 深度了解（可选）—— 辅助信息
        customer_who = (params.get('customer_who') or '').strip()
        customer_why = (params.get('customer_why') or '').strip()
        customer_problem = (params.get('customer_problem') or '').strip()
        customer_story = (params.get('customer_story') or '').strip()

        aux_parts = []
        if customer_who:
            aux_parts.append(f'- 目标客群是谁：{customer_who}')
        if customer_why:
            aux_parts.append(f'- 触达他们的动机：{customer_why}')
        if customer_problem:
            aux_parts.append(f'- 他们有什么问题：{customer_problem}')
        if customer_story:
            aux_parts.append(f'- 真实故事/经历：{customer_story}')
        aux_section = '\n'.join(aux_parts) if aux_parts else '（未填写辅助信息）'

        # 数码维修类：强约束，避免模型照抄提示词里的奶粉/转奶示例
        electronics_guard = ''
        if cls._desc_has_electronics_service(business_desc) and not cls._desc_has_baby_business(business_desc):
            electronics_guard = (
                '\n【本业务类型·强制】当前为**手机/数码维修或本地手机售卖**：决策者与使用者均为普通消费者，'
                '**禁止**编造奶粉、转奶、乳糖、纸尿裤、0-1岁宝宝、宝妈买奶粉等母婴场景；'
                '**禁止**在 consumption_stage、age_range、description、痛点、目标中写入婴幼童阶段。\n'
                '痛点/目标须围绕：**急用、怕资料丢失、怕偷换件、报价不透明、不知哪家靠谱、换机纠结**等；'
                'buyer_user_relation 以「买即用（自用）」为主；描述示例：「手机碎屏怕资料没了，想找报价清楚、当场能修的店」。\n'
            )

        # 地域约束：local → 本地同城；非 local → 全国，不组合地域维度
        if business_range == 'local':
            region_constraint = '【强制】经营范围为「本地/同城」，所有画像的地域维度必须限定在本县/本区/本镇/同城1小时配送圈内，禁止出现跨市、跨省、全国等范围标签。'
        else:
            region_constraint = '【强制】经营范围为「跨区域/全国」，不在维度库中组合地域维度，默认全国范围。'

        # 领域预设精准组合（按业务类型注入）
        preset_combos = cls._get_domain_preset_combos(business_desc, business_type)

        # 根据批次方向构建不同的痛点/目标约束
        if batch_direction == 'A':
            # A方向：使用者问题
            pain_goal_constraint = """=== 【A方向·本批统一】使用者问题聚焦 ===

本批次统一聚焦：**使用者本身当前正处于的问题/症状**
- pain_point_commonality = 使用者的问题/症状（如「产品效果不好」「手机突然黑屏」）
- goal = 解决后的状态（如「效果变好了」「修好了能用了」）
- 购买者焦虑（决策障碍）**不在本批聚焦**，可弱化或不提

【A方向示例·买用分离产品】
- pain_point_commonality：「使用某产品后效果不明显或不舒适」
- goal：「找到适合自己的产品、解决问题」
- buyer_user_relation：「买给1-3岁宝宝」

【A方向示例·买即用手机维修】
- pain_point_commonality：「手机突然黑屏急用，但不知道哪家店能当场修好」
- goal：「当场修好、报价清楚、手机能用」
- buyer_user_relation：「自用」"""
            desc_constraint = """【A方向 description 格式：使用者状态 + 使用者目标（弱化购买者焦虑）】

例（买用分离产品）：
「家有老人/孩子/宠物，使用某产品后效果不明显，希望找到更适合的产品」

例（买即用手机维修）：
「职业（上班族）、地域（城区），手机突然黑屏急用，不知道哪家店靠谱，想要当场修好、报价透明，着急的上班族」"""
            pain_point_field_constraint = """【A方向 pain_point_commonality】必须来自「使用者当前的问题/症状」"""
            goal_field_constraint = """【A方向 goal】必须来自「使用者希望达成的状态」"""

        else:
            # B方向：购买者焦虑
            pain_goal_constraint = """=== 【B方向·本批统一】购买者决策焦虑聚焦 ===

本批次统一聚焦：**购买者在做决策时的心理障碍/顾虑**
- pain_point_commonality = 购买决策时的焦虑（如「怕用完症状加重」「怕出现过敏」「怕有副作用」）
- goal = 买得放心/买得值/有明确选择
- 使用者本身的问题/症状**不在本批聚焦**，可弱化或不提

【B方向示例·买用分离产品】
- pain_point_commonality：「太多评测、太多牌子，越看越不知道选哪款，怕买错了」
- goal：「有明确推荐跟着选不会错，买得放心」
- buyer_user_relation：「买给老人/孩子」

【B方向示例·买即用手机维修】
- pain_point_commonality：「不知道哪家店靠谱、怕被偷换零件、怕报价被宰」
- goal：「找到诚信店铺、报价透明公道」
- buyer_user_relation：「自用」"""
            desc_constraint = """【B方向 description 格式：购买者决策焦虑 + 购买者目标（弱化使用者问题）】

例（买用分离产品）：
「太多评测说法不一、越看越担心症状加重、不知道怎么处理，想要有明确推荐跟着选不会错的用户」

例（买即用手机维修）：
「职业（上班族）、地域（城区），不知道哪家维修店靠谱、怕偷换零件、怕报价被坑，想要找到诚信店铺、报价透明，谨慎的上班族」"""
            pain_point_field_constraint = """【B方向 pain_point_commonality】必须来自「购买者的决策焦虑/顾虑」"""
            goal_field_constraint = """【B方向 goal】必须来自「购买者希望买得怎样」"""

        # 获取经营类型中文名
        business_type_name = BUSINESS_TYPE_MAP.get(business_type, '本地服务')

        prompt = f"""{PROMPT_BASE_CONSTRAINT.format(system_base_personas=system_base_personas)}
你是用户画像专家。请根据业务信息，从预设组合中选取5个精准目标用户画像。

=== 业务基本信息 ===
业务描述：{business_desc}
经营范围：{business_range}
经营类型：{business_type_name}
{electronics_guard}

=== 【本批批次方向·强制】===
{batch_direction_label}

{pain_goal_constraint}

=== 预设维度组合（必须从这些组合中选取5个）===
{preset_combos}

=== 核心原则 ===

**三层痛点归类规则（必须遵守）：**

**user_problem_types（使用层）- 全部原始搜索动因：**
- 前置客观症状/异常/损耗/不适：拉肚子、过敏、故障、损耗、氧化、发黄、发霉
- 后置使用体验痛点：不方便、不好看、不舒服、影响心情
- 注意：这是用户"因为这个问题难受，才主动去搜解决方案"的原始动因

**buyer_concern_types（决策层）- 仅限付费/成本顾虑：**
- 付费顾虑：怕买贵、怕被宰、怕不值
- 成本顾虑：年预算、月消耗、采购成本
- 风险顾虑：怕质量不稳定、怕断供、怕售后无保障

**对接层 - 落地执行痛点：**
- 流程对接：审批繁琐、对接人多、沟通成本高
- 落地执行：安装难、配送慢、服务响应差

**三层身份关系：**

**消费品（买用分离）：**
- 决策层(buyer)：出钱拍板（宝妈、子女、家长）
- 使用层(user)：实际使用者（孩子、老人）
- buyer_user_relation = 「买给1-3岁宝宝/买给老人/自用」

**本地服务（买用合一）：**
- 决策层(buyer)=使用层(user)：本人出钱本人用
- buyer_user_relation = 「自用」

**企业服务（三层分离）：**
- 决策层(buyer)：出钱拍板（老板、行政总监）
- 对接层：经办联络（行政专员）
- 使用层(user)：实际使用者（员工、工人）
- buyer_user_relation = 「老板买给员工用/买给公司用」

**【重要】业务描述里有「宝宝」「孩子」「老人」「宠物」相关需求 → 必为买用分离！**

**【灵活判断】业务描述中可能同时存在B端和C端客户：**
- 矿泉水/定制产品：可能企业采购（酒店/公司）+ 个人定制（婚宴/寿宴）都存在
- 要根据具体业务描述判断，不要假设所有客户都是同一类型

**【禁止·买用分离时维度填使用者的】**
```
❌ 错误示例：
「35-45岁家长，担心孩子使用产品后不适」
→ 身份是家长（35-45岁），但痛点是孩子的！
→ age_range 填了「35-45岁」是错的，应该填「孩子的年龄段」

✅ 正确示例：
「有1-3岁孩子的妈妈，孩子使用某产品后效果不好，担心成分不安全」
→ name：焦虑家长
→ age_range：「孩子的年龄段」
→ consumption_stage：「有孩子的阶段」
→ buyer_user_relation：「买给孩子」
```

**【维度填使用者的：】**
- age_range：使用者的年龄段（如：孩子的年龄/老人的年龄）
- consumption_stage：使用者所处的阶段（「有孩子的阶段」「有老人的阶段」）

=== 通用约束 ===

1. 【差异化·强制】5条之间**至少在3个维度上有明显不同**：
   - 身份细分（不同角色：宝妈 vs 宝爸 vs 家中长辈）
   - 年龄段（如1-3岁 vs 3-6岁 vs 备孕期）
   - 地域（如县城居民 vs 城区核心街道 vs 郊区住户）
   - 消费阶段（如备孕期 vs 有0-1岁宝宝 vs 空巢期）

2. 【语义一致】维度组合要语义通顺，禁止矛盾搭配。

3. 【C端禁用词】description/痛点/目标中禁止：融资、创始人、CEO、年营收、GMV 等卖家向词汇。

=== 输出格式（只返回JSON数组，5个对象，不要其他文字）===
{{
    "name": "细分人群简称（≤6字），由LLM根据业务推导，禁止空洞概括（如「消费者」「客户」），禁止与 occupation 重复",
    
    "description": "{desc_constraint}",
    
    "pain_point_commonality": "{pain_point_field_constraint}（根据本批方向选择）",
    "goal": "{goal_field_constraint}（根据本批方向选择）",
    "buyer_user_relation": "来自预设组合（如「买给1-3岁宝宝」「自用」）",
    "age_range": "来自预设组合中的使用者年龄段（如「1-3岁」「60-75岁」）",
    "geo_tag": "来自预设组合中的地域（如「县城」「城区」）",
    "consumption_stage": "来自预设组合中的消费阶段（如「有1-3岁宝宝」「有0-1岁宝宝」）",
    "occupation": "来自预设组合中的维度原文（如「职场」「全职」「上班族」）",
    "pain_point": "根据本批方向：使用者问题或购买者焦虑 → 目标",
    "needs": "2-3条需求，分号分隔",
    "behaviors": "2-3条决策行为，分号分隔"
}}

只输出JSON数组，不要Markdown。"""

        try:
            from services.llm import get_llm_service
            import json
            import re

            service = get_llm_service()
            if not service:
                return None
            response = service.chat(
                prompt,
                temperature=llm_temperature,
                max_tokens=3000,
            )
            if not response:
                return None

            # ========== [调试日志] ==========
            logger.debug("[_generate_targets_pure_llm] 批次方向: %s", batch_direction_label)
            logger.debug("[_generate_targets_pure_llm] 业务描述: %s", business_desc)
            logger.debug("[_generate_targets_pure_llm] LLM响应前500字: %s", response[:500] if response else None)
            # ========== [/调试日志] ==========

            match = re.search(r'\[.*\]', response, re.DOTALL)
            if not match:
                return None
            raw = json.loads(match.group(0))
            if not isinstance(raw, list) or len(raw) < 5:
                return None

            out: List[Dict] = []
            for item in raw[:5]:
                if not isinstance(item, dict):
                    continue
                needs = item.get('needs', '')
                if isinstance(needs, list):
                    needs = '；'.join(str(x) for x in needs)
                beh = item.get('behaviors', '')
                if isinstance(beh, list):
                    beh = '；'.join(str(x) for x in beh)
                desc = (item.get('description') or '').strip()
                if not desc:
                    continue
                name = (item.get('name') or '').strip() or cls._derive_persona_display_name(desc)
                age_r = (item.get('age_range') or '').strip()
                occ = (item.get('occupation') or '').strip()
                pst = (item.get('pain_point_commonality') or '').strip()
                goal_val = (item.get('goal') or '').strip()
                buyer_rel = (item.get('buyer_user_relation') or '').strip()
                out.append({
                    'name': name[:12],
                    'description': desc,
                    'pain_point_commonality': pst,
                    'goal': goal_val,
                    'buyer_user_relation': buyer_rel,
                    'age_range': age_r or '不限',
                    'occupation': occ or '不限',
                    'geo_tag': (item.get('geo_tag') or '').strip(),
                    'consumption_stage': (item.get('consumption_stage') or '').strip(),
                    'pain_point': (item.get('pain_point') or '').strip(),
                    'needs': str(needs).strip(),
                    'behaviors': str(beh).strip(),
                    '_dims': {'source': 'llm_pure'},
                })
            return out if len(out) >= 5 else None
        except Exception as e:
            logger.error("[ContentGenerator] _generate_targets_pure_llm 异常: %s", e)
            return None

    @classmethod
    def _build_llm_dimension_pool(cls, params: Dict[str, Any]) -> str:
        """
        为 LLM 构建可用维度库字符串，包含 code、name、options，
        按 business_type 过滤不适用维度，local_service/product/personal 用本地生活化选项。
        """
        business_desc = (params.get('business_description') or '').strip()
        business_range = params.get('business_range') or 'local'
        business_type = params.get('business_type') or 'local_service'

        dims_map = cls._get_persona_dimensions()
        if not dims_map:
            return '（维度库为空，使用默认人群描述）'

        # 推断行业（用于 occupation 拼接）
        inferred_industry = cls._infer_local_industry_from_desc(business_desc)

        # 客户角色池：从数据库 job_role 维度读取
        job_dim_code = 'job_role'
        if job_dim_code in dims_map:
            job_opts = cls._build_dimension_options(
                dims_map[job_dim_code], business_desc, business_range, business_type
            )
            job_label = dims_map[job_dim_code].name
        else:
            job_opts = ['目标客户']
            job_label = '客户角色'

        # 构建维度库列表（痛点状态单独置顶为【必选】）
        lines: List[str] = []
        added_job = False
        pain_point_commonality_line: Optional[str] = None
        goal_line: Optional[str] = None
        buyer_user_relation_line: Optional[str] = None

        for code, dim in sorted(dims_map.items(), key=lambda x: x[1].sort_order or 0):
            if not cls._dim_applicable_to_business(dim, business_type):
                continue

            if code == job_dim_code:
                # 客户角色维度单独处理
                if job_opts:
                    lines.append(f"- {job_label}（job_role）: {'、'.join(job_opts)}")
                    added_job = True
                continue

            opts = cls._build_dimension_options(dim, business_desc, business_range, business_type)
            if not opts:
                continue

            # 库内 code 多为 pain_status，与 prompt 中 pain_point_commonality 同义
            if code in ('pain_point_commonality', 'pain_status'):
                dim_desc_text = (dim.description or '').strip()
                dim_desc_part = (f'\n  维度含义：{dim_desc_text}' if dim_desc_text else
                                 f'\n  维度含义：此人当前正处于的焦虑/迷茫/恐惧状态（如「找不到方法的焦虑」「对未知信息的恐惧」「多选一的迷茫」），这是过程性状态，不是结果。')
                pain_point_commonality_line = (
                    f"- {dim.name}（输出字段名 pain_point_commonality，**须填下列原文之一**）{dim_desc_part}\n  选项: {'、'.join(opts)}"
                )
                continue
            if code == 'goal':
                goal_line = f"- {dim.name}（goal）: {'、'.join(opts)}"
                continue
            if code == 'buyer_user_relation':
                buyer_user_relation_line = f"- {dim.name}（buyer_user_relation）: {'、'.join(opts)}"
                continue

            lines.append(f"- {dim.name}（{code}）: {'、'.join(opts)}")

        # 如果 job_role 维度被过滤了但还没加过，补上客户角色
        if not added_job and job_opts:
            lines.insert(0, f"- {job_label}（job_role）: {'、'.join(job_opts)}")

        # 如果没有从数据库读到痛点共性/目标/买用关系，使用默认文本
        if not pain_point_commonality_line:
            # 痛点状态 = 过程性焦虑/迷茫/恐惧状态，不是结果
            if business_type in ('local_service', 'product', 'personal'):
                pain_point_commonality_line = (
                    '- 痛点状态（pain_point_commonality，**须填原文之一**）\n'
                    '  维度含义：此人当前正处于的**过程性焦虑/迷茫/恐惧状态**——\n'
                    '    - 「找不到方法的焦虑」：试了很多但没效果，不知道哪条路对\n'
                    '    - 「多选一的迷茫」：选择太多，越看越不知道哪个好\n'
                    '    - 「对未知信息的恐惧」：不知道成分/质量，不敢下手\n'
                    '    - 「时间紧迫的焦虑」：马上要用，来不及仔细比较\n'
                    '    - 「怕买贵的后悔」：担心买完发现买贵了\n'
                    '  选项: 担心用完症状加重、担心有副作用、时间精力不够、信息多不敢信'
                )
            else:
                pain_point_commonality_line = (
                    '- 痛点状态（pain_point_commonality，**须填原文之一**）\n'
                    '  维度含义：此人当前正处于的焦虑/迷茫/恐惧过程性状态\n'
                    '  选项: 遇到瓶颈、想要转型、寻求突破'
                )
        if not goal_line:
            if business_type in ('local_service', 'product', 'personal'):
                goal_line = (
                    '- 目标（goal，**须填原文之一**）\n'
                    '  维度含义：解决上述过程性痛点状态后，**希望达成的结果/终点状态**——\n'
                    '    - 「买得更值」：花同样的钱，买到品质更好的\n'
                    '    - 「买得更放心」：知道成分/来源，用起来安心\n'
                    '    - 「买得更适合」：选到真正适合自己/家人的\n'
                    '    - 「买得更省心」：不用再操心/比较，省精力\n'
                    '    - 「买得更方便」：不用跑远/等很久，用起来方便\n'
                    '  选项: 买得更值、买得更放心、买得更方便、买得更适合、买得更省心'
                )
            else:
                goal_line = (
                    '- 目标（goal，**须填原文之一**）\n'
                    '  维度含义：解决痛点状态后，企业/团队希望达成的经营结果\n'
                    '  选项: 想要增长、想要转型、想要变现'
                )
        if not buyer_user_relation_line:
            buyer_user_relation_line = (
                '- 买用关系（buyer_user_relation）\n'
                '  C端**必填**，B端可空\n'
                '  买即用（自用）：买的人就是用的人（如自己找家政服务）。\n'
                '  买给家人/长辈/孩子：买的人和用的人不同（如给老人请保姆）。\n'
                '  选项: 买即用（自用）、买给家人、买给长辈、买给孩子、送礼/代购'
            )

        prelude_head = (
            '【强制禁止】禁止出现与当前业务无关的示例内容，如：\n'
            '  - 手机/数码/维修相关：碎屏、偷换件、资料丢失、报价不清等\n'
            '  - 母婴/奶粉相关：宝宝、奶粉、转奶、备孕等\n'
            '  - 桶装水/配送相关：水质、送水、水站等\n'
            '请根据实际业务描述生成对应的客户痛点和目标。\n\n'
        )

        prelude = (
            prelude_head
            + '=== 【每条必选】痛点状态（pain_point_commonality）+ 目标（goal）===\n'
            '【概念区分·必须理解】\n'
            '  · 痛点状态（pain_point_commonality）= **过程性焦虑/迷茫/恐惧状态**——\n'
            '    例：「不知道哪家服务靠谱，怕选错了白花钱」\n'
            '    例：「商家太多，分不清哪家质量好，怕被骗」\n'
            '  · 目标（goal）= **解决状态后希望达成的终点结果**——\n'
            '    例：「找到靠谱的服务商，用得放心」\n'
            '    例：「花合理的钱，买到放心的服务」\n'
            '  两者是「过程状态」→「终点结果」的关系，语义必须能串联（如「多选一迷茫」→「买得更适合」）\n'
            '  【禁止】将目标写成「想涨销量/想拓客/想增长」（这是卖家视角，不是买家消费目标）\n\n'
            f'{pain_point_commonality_line}\n'
            f'{goal_line}\n\n'
            '=== 【C端必选】买用关系（buyer_user_relation）===\n'
            '**关键**：C端消费品/本地服务/个人品牌必须分析「买的人」和「用的人」是否相同，从库中选一个：\n'
            '  - 买即用（自用）：买的人就是用的人（如自己找家政服务）。\n'
            '  - 买给家人/长辈/孩子：买的人和用的人不同（如给老人请保姆）。\n'
            '  - 送礼/代购：买来送人，不自己用。\n'
            '请根据「业务描述」判断哪些关系适用，选最贴近的填入 description，使画像描述准确对应「谁买、谁用」。\n'
            f'{buyer_user_relation_line}\n\n'
            '=== 其他维度（每条再选 2 个，与上面维度组合成自然句）===\n'
        )
        return prelude + '\n'.join(lines)

    @classmethod
    def _derive_persona_display_name(cls, description: str) -> str:
        """
        从自然语言描述推导卡片标题（LLM 未返回 name 时使用）。
        优先取第一个分句/短语，避免整段贴到标题上。
        """
        if not (description or '').strip():
            return '客户画像'
        s = description.strip()
        for sep in ('，', ',', '、', '；', ';'):
            if sep in s:
                head = s.split(sep)[0].strip()
                if len(head) >= 2:
                    return head[:12] if len(head) > 12 else head
        if len(s) <= 12:
            return s
        return s[:8] + '…'

    @classmethod
    def _build_filled_info(cls, customer_who: str, customer_why: str,
                           customer_problem: str, customer_story: str,
                           service_scenario: str = '', local_city: str = '') -> str:
        """构建已填写的补充信息"""
        parts = []
        if customer_who:
            parts.append(f"典型客户案例：{customer_who}")
        if customer_why:
            parts.append(f"当初为什么找到您：{customer_why}")
        if customer_problem:
            parts.append(f"帮他解决了什么问题：{customer_problem}")
        if customer_story:
            parts.append(f"印象深刻的客户故事：{customer_story[:100]}")
        if service_scenario:
            scenario_map = {
                'hotel_restaurant': '酒店/餐饮/茶楼/高端会所',
                'residential': '家用/住宅/小区业主',
                'office_enterprise': '写字楼/企业/工厂/园区',
                'institutional': '学校/医院/食堂/政企单位',
                'retail_chain': '实体店/连锁门店/加盟品牌',
                'renovation': '装修/工装/工程定制',
                'other': '其他小众场景'
            }
            parts.append(f"主要服务场景：{scenario_map.get(service_scenario, service_scenario)}")
        if local_city:
            parts.append(f"服务城市：{local_city}")

        return '\n'.join(parts) if parts else '（未填写补充信息）'

    @classmethod
    def _infer_local_industry_from_desc(cls, business_desc: str) -> str:
        """从业务描述推断本地服务细分场景（用于画像行业/场景标签）。"""
        if not (business_desc or '').strip():
            return '本地生活'
        pairs = [
            (('改衣', '改衣服', '裁缝', '拉链', '扦边', '裤脚', '裤边', '缝补', '熨烫', '锁边', '改裤腰', '改大小'), '裁缝改衣'),
            (('橱柜', '衣柜', '全屋定制', '装修', '翻新', '软装', '硬装', '瓷砖', '地板', '门窗'), '家居家装'),
            (('餐饮', '外卖', '堂食', '火锅', '奶茶', '烧烤'), '餐饮'),
            (('美容', '美发', '美甲', '护肤'), '美业服务'),
            # 数码维修优先于「培训」（避免「手机维修培训」误判教培）
            (('修手机', '手机维修', '手机店', '换屏', '手机贴膜', '数码维修', '电脑维修', '笔记本维修', '二手机'), '数码维修'),
            (('汽修', '洗车', '保养', '贴膜'), '汽车服务'),
            (('家政', '保洁', '月嫂', '保姆'), '家政服务'),
            (('培训', '补习', '早教', '舞蹈', '书法'), '教育培训'),
            (('律师', '法务'), '专业服务'),
            (('摄影', '婚庆', '司仪'), '生活服务'),
            (('宠物'), '宠物服务'),
            (('健身', '瑜伽', '普拉提'), '运动健康'),
            (('水站', '桶装水', '配送', '矿泉水'), '本地零售/配送'),
            (('奶粉', '母婴', '婴幼儿', '宝宝辅食', '纸尿裤'), '母婴零售'),
        ]
        for keys, label in pairs:
            if any(k in business_desc for k in keys):
                return label
        return '本地生活'

    # ---------------------------------------------------------------------------
    # 画像维度：从 AnalysisDimension 数据库配置中读取（人群画像 / super_positioning / persona）
    # ---------------------------------------------------------------------------

    # 内存缓存：避免每次请求都查库
    _persona_dim_cache: Optional[Dict[str, AnalysisDimension]] = None
    _persona_dim_cache_key: Optional[str] = None  # 用于判断缓存是否过期

    # 业务类型 → applicable_audience 匹配规则
    # 只保留「非 B2B 高管」的人群；企业服务才允许 B2B 高管角色
    _BUSINESS_TYPE_AUDIENCE_TAGS: Dict[str, List[str]] = {
        'local_service': ['本地服务商', '本地生活', '个人服务', '通用'],
        'product':       ['个人服务', '通用', '消费品', '本地生活'],
        'personal':       ['个人服务', '通用', '粉丝/学员'],
        'enterprise':     ['B2B服务', '企业服务', '企业家', '通用'],
    }

    @classmethod
    def _get_persona_dimensions(cls) -> Dict[str, AnalysisDimension]:
        """从数据库加载超级定位·人群画像维度配置，带内存缓存。"""
        try:
            dims = AnalysisDimension.query.filter_by(
                category='super_positioning',
                sub_category='persona',
                is_active=True
            ).order_by(AnalysisDimension.sort_order).all()

            return {d.code: d for d in dims}
        except Exception:
            return {}

    # 业务描述含下列词时视为「明确母婴/婴童零售」，才允许组合婴幼儿消费阶段等维度
    _BABY_BUSINESS_MARKERS: Tuple[str, ...] = (
        '奶粉', '母婴', '婴幼儿', '纸尿裤', '尿不湿', '婴儿', '宝宝辅食', '乳糖', '奶瓶', '妇婴',
    )
    # 手机/数码维修、售卖 — 买即用为主，禁止与奶粉示例混用
    _ELECTRONICS_SERVICE_MARKERS: Tuple[str, ...] = (
        '修手机', '手机维修', '维修手机', '手机店', '换屏', '换电池', '贴膜', '数码维修',
        '电脑维修', '笔记本维修', '手机回收', '二手机', 'iphone', '苹果维修', '安卓维修',
    )

    @classmethod
    def _desc_has_baby_business(cls, business_desc: str) -> bool:
        d = (business_desc or '').strip()
        if not d:
            return False
        if any(m in d for m in cls._BABY_BUSINESS_MARKERS):
            return True
        if '宝宝' in d and any(x in d for x in ('奶粉', '尿不湿', '辅食', '奶瓶', '母婴')):
            return True
        return False

    @classmethod
    def _desc_has_electronics_service(cls, business_desc: str) -> bool:
        d = (business_desc or '').strip()
        if not d:
            return False
        if any(m in d for m in cls._ELECTRONICS_SERVICE_MARKERS):
            return True
        dl = d.lower()
        if 'iphone' in dl or 'ipad' in dl:
            return True
        # 「手机」+ 店/修/卖/屏/配件 等本地常见表述
        if '手机' in d and any(x in d for x in ('维修', '修', '换屏', '贴膜', '专卖', '售卖', '销售', '店', '铺', '回收', '配件')):
            return True
        return False

    @classmethod
    def _filter_persona_opts_for_non_baby_business(cls, dim_code: str, opts: List[str],
                                                     business_desc: str) -> List[str]:
        """
        非母婴业务时，从维度选项中剔除明显婴童/母婴场景标签，
        避免 LLM 随机抽到「备孕」「新手爸妈」「宝宝0-1岁」等与业务无关的选项。
        适用于：consumer_lifecycle（消费阶段）、age_group（年龄段）、buyer_user_relation（买用关系）。
        """
        if not opts or cls._desc_has_baby_business(business_desc):
            return opts

        # 婴幼儿/母婴相关关键词（出现在选项中需要过滤）
        baby_substrings = (
            '备孕', '孕期', '孕妇', '产妇', '坐月子', '哺乳期',
            '宝宝', '婴儿', '婴幼', '新生儿', '乳糖', '转奶',
            '奶粉', '辅食', '纸尿裤', '尿不湿',
            '0-1岁', '0到1岁', '0至1岁', '1岁宝', '2岁宝', '3岁宝',
            '幼儿园', '学前班', '学龄前',
            '新手爸妈',  # 婴幼儿相关人群
            '宝爸', '宝妈', '宝爸宝妈',
        )
        filtered = [o for o in opts if not any(t in o for t in baby_substrings)]
        return filtered if filtered else opts

    @classmethod
    def _build_dimension_options(cls, dim: AnalysisDimension,
                                  business_desc: str,
                                  business_range: str,
                                  business_type: str = 'local_service') -> List[str]:
        """
        从数据库的 examples 字段构建选项池。
        特殊情况做智能覆盖：
          - 行业背景：从业务描述推断具体行业
          - 地域：本地服务细化到县城/乡镇粒度
        """
        base_opts = []
        if dim.examples:
            base_opts = [o.strip() for o in dim.examples.split('|') if o.strip()]

        # 非母婴 + 数码维修：去掉婴幼儿类消费阶段等，防止与业务无关标签混入
        # 注意：数据库中字段名是 consumer_lifecycle，代码中可能写为 consumption_stage
        if dim.code in ('consumption_stage', 'consumer_lifecycle', 'age_group', 'buyer_user_relation'):
            base_opts = cls._filter_persona_opts_for_non_baby_business(
                dim.code, base_opts, business_desc
            )

        # ---- 行业背景：优先从描述推断具体行业 ----
        if dim.code == 'industry_background':
            inferred = cls._infer_local_industry_from_desc(business_desc)
            if inferred != '本地生活':
                return [inferred]
            return base_opts if base_opts else ['本地生活']

        # ---- 地域：本地服务细化 ----
        if dim.code == 'region':
            if business_range == 'local':
                refined = ['县城及下辖乡镇', '同城1小时配送圈', '城区核心街道',
                           '城郊结合部', '郊区/工业园']
                return refined
            else:
                # 跨区域时返回空列表，不在维度库中显示地域维度
                return []

        # ---- 领域细分选项：检测到特定行业时，替换/优先使用该行业的具体选项 ----
        domain_opts = cls._detect_domain_hints(business_desc)
        if domain_opts and dim.code in ('pain_point_commonality', 'pain_status', 'goal'):
            domain_list = domain_opts.get(dim.code, [])
            if domain_list:
                # 领域细分选项优先靠前，通用抽象选项兜底（不去重，因为 base_opts 已去重）
                return domain_list + base_opts

        # ---- C端禁用B2B维度：development_stage/revenue_scale/team_size ----
        # C端业务禁止出现「天使轮/A轮/年营收/GMV」等B2B词汇
        if business_type in ('local_service', 'product', 'personal'):
            if dim.code in ('development_stage', 'revenue_scale', 'team_size'):
                # 强制使用C端化选项，禁止B2B词汇
                c_end_options = {
                    'development_stage': ['刚起步', '小有规模', '成熟稳定', '转型探索'],
                    'revenue_scale':     ['小本经营', '年入数十万', '年入百万级', '规模化运营'],
                    'team_size':         ['个人/夫妻店', '3-10人', '10-50人', '50人以上'],
                }
                if dim.code in c_end_options:
                    return c_end_options[dim.code]

        return base_opts

    @classmethod
    def _detect_domain_hints(cls, business_desc: str) -> Dict[str, List[str]]:
        """
        根据业务描述推断领域，返回该领域在 pain_point_commonality / goal 的具体选项。
        核心逻辑：痛点/目标 = 使用者遇到的具体问题 + 想达成的具体状态，
        而不是「拿不准怎么选」「买得更值」这类抽象焦虑。

        返回结构：Dict[code, List[str]]，无匹配行业时返回空 dict。
        """
        hints: Dict[str, List[str]] = {}
        desc_raw = business_desc or ''
        desc = desc_raw.lower()

        # ── 数码维修/手机店（优先于「小学」教育词误匹配、母婴示例污染）────────────────
        if cls._desc_has_electronics_service(desc_raw) and not cls._desc_has_baby_business(desc_raw):
            hints['pain_point_commonality'] = [
                '手机突然黑屏/碎屏/进水，急用但不知道哪家店修得靠谱',
                '担心维修偷换配件、报价不透明，不敢随便进店',
                '换机还是修机拿不准，怕多花冤枉钱',
                '长辈手机卡顿、不会用，想换机但怕买到不合适',
                '二手机、配件渠道多，不知道有没有暗病、怕踩坑',
            ]
            hints['goal'] = [
                '当场修好、报价清楚、用得放心',
                '配件可靠、售后有保障、不被坑',
                '换到合适机型，省心好用',
                '长辈用手机少折腾，有问题有人帮',
            ]
            return hints

        # ── 桶装水/本地配送服务 ──────────────────────────────────────────────
        if any(k in desc for k in ('桶装水', '矿泉水', '水站', '配送', '饮用水', '桶装配送')):
            hints['pain_point_commonality'] = [
                '不知道哪家水质好、安全可靠',
                '担心桶装水来源不明，怕喝到假水',
                '送水太慢，渴了等半天没人送',
                '价格不透明，怕被宰',
                '水站服务不稳定，今天送明天不送',
                '担心水桶不干净、二次污染',
            ]
            hints['goal'] = [
                '喝到放心水，水质有保障',
                '送水及时，随叫随到',
                '价格透明公道，不吃亏',
                '服务稳定，长期合作省心',
            ]
            return hints

        # ── 通用自适应（无匹配行业时使用，由AI根据业务描述自行推理）─────────
        if not hints.get('pain_point_commonality'):
            hints['pain_point_commonality'] = [
                '使用后效果不理想，不知道是产品问题还是使用方法问题',
                '担心成分/质量，不知道是否安全可靠',
                '信息太多，不知道哪款更适合自己情况',
                '预算有限，担心买错了浪费钱',
                '不了解产品，不知道怎么正确使用',
            ]
            hints['goal'] = [
                '找到适合自己情况的产品',
                '买得放心、用得安心',
                '了解正确使用方法',
                '花合理的钱买到合适的产品',
            ]

        # ── 老人/健康/保健品 ──────────────────────────────────────────────────
        elif any(k in desc for k in ('老人', '老年', '爸妈', '长辈', '钙片', '保健', '血压', '血糖', '血脂', '养老', '护膝', '护腰带')):
            hints['pain_point_commonality'] = [
                '担心老人身体走下坡，不知道怎么补',
                '老人三高（血糖/血压/血脂）不稳定，很担心',
                '老人腿脚无力，行动不便',
                '不知道哪款保健品真的有效，不敢乱买',
                '老人不配合吃保健品，很难坚持',
                '信息太多，不知道给老人买什么合适',
            ]
            hints['goal'] = [
                '老人腿脚有力、精神好',
                '老人三高稳定、减少并发症',
                '老人少生病、生活能自理',
                '买得放心，让老人身体好起来',
            ]

        # ── 宠物 ──────────────────────────────────────────────────────────────
        elif any(k in desc for k in ('宠物', '猫粮', '狗粮', '猫砂', '宠物食品', '宠物用品')):
            hints['pain_point_commonality'] = [
                '宠物挑食/拉肚子，不知道换什么粮',
                '宠物皮肤掉毛，不知道是不是粮的原因',
                '不知道哪种宠物粮成分安全，不敢买',
                '宠物过敏/呕吐，不知道哪款合适',
                '想给宠物换粮，不知道怎么过渡',
            ]
            hints['goal'] = [
                '宠物健康、毛色好、不拉肚子',
                '宠物爱吃、挑食改善',
                '买得放心，成分安全可靠',
            ]

        # ── 儿童教育/培训 ────────────────────────────────────────────────────
        elif any(k in desc for k in ('培训', '补习', '早教', '教育', '幼儿园', '小学', '课外班', '学习')):
            hints['pain_point_commonality'] = [
                '不知道哪个机构好，怕选错耽误孩子',
                '孩子成绩上不去，不知道怎么补',
                '不知道孩子兴趣在哪，不知道报什么班',
                '孩子注意力不集中，学习效率低',
                '担心孩子输在起跑线，很焦虑',
            ]
            hints['goal'] = [
                '孩子成绩提升、进步明显',
                '找到孩子真正感兴趣的领域',
                '孩子注意力集中、学习效率提高',
            ]

        # ── 护肤品/化妆品 ────────────────────────────────────────────────────
        elif any(k in desc for k in ('护肤', '化妆', '美容', '面膜', '精华', '洗面奶', '彩妆')):
            hints['pain_point_commonality'] = [
                '不知道什么成分适合自己，怕过敏',
                '皮肤问题（痘痘/干燥/敏感）不知道用哪款',
                '产品太多，不知道哪个效果好',
                '想美白/抗衰，不知道哪款真的有效',
                '皮肤状态差，不知道怎么改善',
            ]
            hints['goal'] = [
                '皮肤变好、气色好',
                '不过敏、用起来安全',
                '美白/抗衰见效、皮肤状态改善',
            ]

        # ── 餐饮/外卖 ────────────────────────────────────────────────────────
        elif any(k in desc for k in ('餐饮', '外卖', '堂食', '快餐', '便当', '饭店', '餐厅')):
            hints['pain_point_commonality'] = [
                '不知道吃什么，选择困难',
                '担心食品安全，不知道哪家靠谱',
                '外卖吃腻了，想换口味',
                '工作忙，没时间做饭',
                '不知道哪家性价比高',
            ]
            hints['goal'] = [
                '吃得好、干净卫生',
                '省时省力，不用操心',
                '性价比高，花得值',
            ]

        # ── 家装/家具 ────────────────────────────────────────────────────────
        elif any(k in desc for k in ('装修', '家具', '家居', '橱柜', '衣柜', '定制', '软装', '硬装', '瓷砖', '地板', '门窗', '家电')):
            hints['pain_point_commonality'] = [
                '不知道什么风格适合自己，很迷茫',
                '担心装修质量，不知道怎么监工',
                '预算有限，不知道怎么分配',
                '信息太多，不知道哪家建材好',
                '怕被装修公司坑，很不放心',
            ]
            hints['goal'] = [
                '装修顺利，质量有保障',
                '花得值，预算不超支',
                '效果满意，住得舒服',
            ]

        # ── 美业/理发/美容服务 ──────────────────────────────────────────────
        elif any(k in desc for k in ('理发', '美发', '美容', '美甲', '护肤', '造型', '染发', '烫发')):
            hints['pain_point_commonality'] = [
                '不知道什么发型适合自己',
                '担心理发师水平，怕剪坏',
                '想变美但不知道怎么弄',
                '担心染发/烫发伤发质',
                '不知道哪家店技术好',
            ]
            hints['goal'] = [
                '变得更好看、更自信',
                '发型适合自己，气质提升',
                '不伤发，效果自然持久',
            ]

        return hints

    @classmethod
    def _dim_applicable_to_business(cls, dim: AnalysisDimension,
                                     business_type: str) -> bool:
        """
        判断某维度的 applicable_audience 是否与当前业务类型匹配。
        - 无标签 → 通用，保留
        - 含「通用」→ 保留
        - 含「本地服务商/个人服务/消费品」→ 保留
        - 本地服务/产品/个人业务：排除「仅限 B2B/企业服务」且不含通用的维度
        """
        if not dim.applicable_audience:
            return True

        tags = set(t.strip() for t in dim.applicable_audience.split('|') if t.strip())

        # 含通用标签，视为通用维度，保留
        if '通用' in tags:
            return True

        if business_type in ('local_service', 'product', 'personal'):
            # 仅限 B2B/企业服务的标签集合（不含通用）
            b2b_exclusive = {'B2B服务', '企业服务', 'B2B销售'}
            # 若全为 B2B 专有标签，排除；若有消费者标签则保留
            if tags & b2b_exclusive and not (tags - b2b_exclusive):
                return False

        return True

    @classmethod
    def _generate_targets_from_db_dimensions(cls, params: Dict[str, Any],
                                             rng) -> List[Dict]:
        """
        核心实现：从数据库 AnalysisDimension 读取配置，生成 5 个差异化画像。
        - 每个维度从 examples 抽取选项
        - 每人独立抽取各维度选项（差异化）
        - 职位角色放在描述末尾
        - applicable_audience 过滤不适用维度
        """
        business_desc = (params.get('business_description') or '').strip()
        business_range = params.get('business_range') or 'local'
        business_type = params.get('business_type') or 'local_service'
        customer_who = (params.get('customer_who') or '').strip()
        customer_why = (params.get('customer_why') or '').strip()
        customer_problem = (params.get('customer_problem') or '').strip()
        customer_story = (params.get('customer_story') or '').strip()

        dims_map = cls._get_persona_dimensions()

        # 构建每个维度的选项池（按 business_type 过滤）
        dim_options: Dict[str, List[str]] = {}
        dim_objects: Dict[str, AnalysisDimension] = {}
        dim_labels: Dict[str, str] = {}

        for code, dim in dims_map.items():
            opts = cls._build_dimension_options(dim, business_desc, business_range, business_type)
            if not cls._dim_applicable_to_business(dim, business_type):
                continue
            if opts:
                dim_options[code] = opts
                dim_objects[code] = dim
                dim_labels[code] = dim.name

        # 职位角色固定放末尾（已在过滤后保留）
        job_dim_code = 'job_role'

        # 展示顺序：去掉职位角色，其余按 sort_order
        display_order = [code for code in dim_objects.keys() if code != job_dim_code]

        # 推断行业（用于 occupation / name 拼接）
        inferred_industry = cls._infer_local_industry_from_desc(business_desc)

        # 若职位角色维度被过滤掉了，使用默认角色
        if job_dim_code not in dim_options or not dim_options.get(job_dim_code):
            dim_options[job_dim_code] = ['目标客户']
            dim_labels[job_dim_code] = '客户角色'

        # 准备非职位维度候选列表（在 for 循环外计算，避免引用未定义的 profile）
        non_job_candidates = [c for c in display_order if c in dim_options and dim_options[c]]
        if not non_job_candidates:
            non_job_candidates = [c for c in dim_options if c != job_dim_code]

        targets: List[Dict] = []
        for i in range(5):
            profile: Dict[str, str] = {}
            for code, opts in dim_options.items():
                profile[code] = rng.choice(opts)

            job_role = profile.get(job_dim_code, '目标客户')

            # ---- 描述：必选痛点共性 + 目标 + 买用关系（C端）+ 另选维度组合 ----
            # 库维度 code 为 pain_status 时与 pain_point_commonality 同义
            pain_point_commonality_val = (
                profile.get('pain_point_commonality')
                or profile.get('pain_status', '')
            )
            goal_val = profile.get('goal', '')
            buyer_rel = profile.get('buyer_user_relation', '')
            # goal 和 pain_point_commonality 进维度串；行业背景不进随机属性串
            char_candidates = [
                c for c in non_job_candidates
                if c not in {'pain_point_commonality', 'pain_status', 'goal', 'buyer_user_relation'}
                and c != 'industry_background'
            ]
            # C 端固定拉进 buyer_user_relation；其余业务可选
            extra_fixed = [buyer_rel] if business_type in ('local_service', 'product', 'personal') else []
            # 除痛点共性 + 目标外再抽 2 维（不够则全取）
            n_extra = min(2, len(char_candidates))
            selected_char = rng.sample(char_candidates, n_extra) if char_candidates else []

            if business_type in ('local_service', 'product', 'personal'):
                # C 端：买用关系（使用者状态）+ 痛点共性 + 目标 + 两个人群属性 + 的 + 角色
                # 顺序：先状态/场景（如宝宝情况），再痛点（如信息多不敢信），再目标，最后背景
                buyer_rel_val = extra_fixed[0] if extra_fixed else ''
                char_vals = [x for x in [buyer_rel_val, pain_point_commonality_val, goal_val] + [profile.get(c, '') for c in selected_char] if x]
                description = '、'.join(char_vals) + f'的{job_role}'
            else:
                # B2B：痛点共性 + 目标 + 阶段/团队/营收 + 行业 + 角色
                dev_val = profile.get('development_stage', '')
                team_val = profile.get('team_size', '')
                rev_val = profile.get('revenue_scale', '')
                ind_val = profile.get('industry_background', '')
                key_parts = [p for p in [dev_val, team_val, rev_val] if p]
                goal_label = {
                    '想要增长': '需要规模化增长路径',
                    '想要转型': '面临战略转型关键期',
                    '想要变现': '需要找到商业化出口',
                }.get(goal_val, '寻求突破')
                key_parts.append(goal_label)
                b2b_char = '、'.join(key_parts)
                head = f'{pain_point_commonality_val}、' if pain_point_commonality_val else ''
                if ind_val:
                    description = f'{head}{b2b_char}的{ind_val}{job_role}'
                else:
                    description = f'{head}{b2b_char}的{job_role}'

            # ---- 维度组合（含必选痛点共性 + 目标 + 买用关系）----
            combo_vals = [x for x in [pain_point_commonality_val, goal_val] + extra_fixed + [profile.get(c, '') for c in selected_char] if x]
            combo_vals.append(job_role)
            dimension_combo = ' × '.join([p for p in combo_vals if p])

            pain_desc_map = {
                # C 端（pain_status 覆盖项）
                '拿不准怎么选': '面对太多牌子和说法，不知道哪款适合自己家情况',
                '担心成分与安全': '最怕配方、奶源、渠道不靠谱，宁可多花也要买安心',
                '时间精力不够': '上班带娃忙，没空做功课对比，希望少踩坑',
                '怕症状加重': '担心用完症状加重/有不适反应，不知道怎么处理',
                '信息多不敢信': '广告软文太多，分不清真假，更信口碑和实测',
                # B 端 / 库内原文
                '遇到瓶颈':   '当前选择不满意，正在货比三家、希望更靠谱省心',
                '想要转型':   '需求或阶段变了，想升级方案或换服务商',
                '寻求突破':   '希望少踩坑、一次做到位，更信真实案例与口碑',
            }
            goal_desc_map = {
                # B2B
                '想要增长':   '希望效果看得见、投入值得',
                '想要转型':   '想换更匹配自己阶段的服务方式',
                '想要变现':   '更看重性价比与实际回报',
                # C端（本地服务/消费品）
                '买得更值':   '希望花的钱值，想买到性价比高的',
                '买得更放心': '最担心质量、安全、口碑，宁可多花也不愿踩坑',
                '买得更方便': '懒得跑太远，最好能送货上门或随到随买',
                '买得更适合': '担心不适合自己，希望有专业建议',
                '买得更省心': '没时间细挑，希望有口碑保障不翻车',
            }
            pain_parts = []
            if customer_problem:
                pain_parts.append(customer_problem[:100])
            if pain_point_commonality_val:
                pain_parts.append(pain_desc_map.get(pain_point_commonality_val, pain_point_commonality_val))
            if goal_val:
                pain_parts.append(goal_desc_map.get(goal_val, goal_val))
            if not pain_parts:
                pain_parts = ['有明确需求，正在寻找合适的服务商']

            pain_point = '；'.join(pain_parts[:3])

            # ---- 需求 ----
            needs_parts = [
                f'与「{business_desc[:80]}」这类服务相匹配',
            ]
            if pain_point_commonality_val:
                needs_parts.append(f'当前痛点：{pain_point_commonality_val}')
            if goal_val:
                needs_parts.append(f'核心目标：{goal_val}')
            if customer_why:
                needs_parts.append(f'触达动机：{customer_why[:80]}')
            needs = '；'.join(needs_parts)

            # ---- 行为特征（按行业换话术）----
            # 默认行为特征池
            behavior_pool = [
                '习惯在抖音/美团/大众点评搜附近门店',
                '更看重离得近、口碑真实、能到店沟通',
                '朋友邻居推荐优先',
                '线上先看评价再线下体验',
                '货比三家后决策',
            ]
            beh_pool = behavior_pool[:]
            rng.shuffle(beh_pool)
            behaviors = '；'.join(beh_pool[:3])

            # ---- 最终字段 ----
            age_range = profile.get('age_group', '不限年龄')
            occupation = f'{inferred_industry} · {job_role}'

            targets.append({
                'name': job_role,
                'dimension_combo': dimension_combo,
                'description': description,
                'pain_point_commonality': pain_point_commonality_val,
                'goal': goal_val,
                'buyer_user_relation': buyer_rel,
                'age_range': age_range,
                'occupation': occupation,
                'pain_point': pain_point,
                'needs': needs,
                'behaviors': behaviors,
                '_dims': dict(profile),
            })

        return targets[:5]

    @classmethod
    def _generate_targets_by_rules(cls, params: Dict[str, Any]) -> List[Dict]:
        """
        使用规则生成目标用户画像（免费用户）。
        全部业务类型统一走数据库 AnalysisDimension 配置：
          - 从 examples 读选项池
          - 从 applicable_audience 过滤不适用维度
          - 身份由数据库 job_role 维度自由组合。
        """
        import random

        nonce = params.get('refresh_nonce')
        if nonce is not None:
            rng = random.Random(hash(str(nonce)) % (2 ** 32))
        else:
            rng = random.Random()

        return cls._generate_targets_from_db_dimensions(params, rng)

    @classmethod
    def _generate_from_template(cls, params: Dict, resources: Dict) -> Dict:
        """基于模板生成内容（免费用户）"""
        industry = params.get('industry', 'general')
        target_customer = cls._infer_target_customer(params)
        business_desc = params.get('business_description', '')

        # 获取选题
        topics = resources.get('topics', [])
        if topics:
            topic = topics[0]  # 选择第一个选题
        else:
            topic = {'title': '通用内容', 'description': business_desc or '产品推广'}

        # 提取关键词
        keywords_data = resources.get('keywords', {})
        core_keywords = [k['keyword'] for k in keywords_data.get('core', [])]
        pain_keywords = [k['keyword'] for k in keywords_data.get('pain_point', [])]
        scene_keywords = [k['keyword'] for k in keywords_data.get('scene', [])]

        # 生成标题
        titles = cls._generate_titles_from_keywords(
            core_keywords, pain_keywords, scene_keywords, count=2
        )

        # 生成标签
        tags = cls._generate_tags_from_keywords(
            core_keywords, pain_keywords, scene_keywords, count=6
        )

        # 生成图文内容
        content = cls._generate_graphic_content(
            title=titles[0],
            topic=topic,
            keywords={
                'core': core_keywords,
                'pain_point': pain_keywords,
                'scene': scene_keywords,
            },
            image_count=5,
            image_ratio='9:16'
        )

        return {
            'titles': titles,
            'tags': tags,
            'content': content,
            'selected_topic': topic,
            'keywords_used': {
                'core': core_keywords,
                'pain_point': pain_keywords,
                'scene': scene_keywords,
            }
        }

    @classmethod
    def _generate_with_ai(cls, params: Dict, resources: Dict) -> Dict:
        """AI增强模式生成内容（付费用户）"""
        industry = params.get('industry', 'general')
        target_customer = cls._infer_target_customer(params)
        business_desc = params.get('business_description', '')
        structure_type = params.get('structure_type')

        # 构建prompt
        prompt = cls._build_ai_prompt(params, resources)
        
        # ========== [调试日志] LLM请求 ==========
        logger.info("=" * 60)
        logger.info("[ContentGenerator] 开始调用 LLM 生成图文内容")
        logger.info("[ContentGenerator] 行业: %s, 目标客户: %s", industry, target_customer)
        logger.info("[ContentGenerator] Prompt长度: %d 字符", len(prompt))
        logger.info("-" * 60)
        # 打印完整prompt（前2000字符，方便查看）
        prompt_preview = prompt[:3000] + "..." if len(prompt) > 3000 else prompt
        logger.info("[ContentGenerator] Prompt内容:\n%s", prompt_preview)
        logger.info("=" * 60)
        # ========== [/调试日志] ==========

        # 调用AI
        try:
            from services.llm import get_llm_service
            service = get_llm_service()
            if not service:
                raise RuntimeError("LLM service not available")
            
            logger.info("[ContentGenerator] 正在调用 LLM.chat()...")
            # max_tokens=4000 确保JSON完整输出，避免截断
            response = service.chat(
                prompt,
                temperature=0.8,
                max_tokens=4000,
            )
            
            # ========== [调试日志] LLM响应 ==========
            logger.info("=" * 60)
            logger.info("[ContentGenerator] LLM 响应完成")
            logger.info("[ContentGenerator] 响应长度: %d 字符", len(response) if response else 0)
            logger.info("-" * 60)
            logger.info("[ContentGenerator] LLM原始响应:\n%s", response)
            logger.info("=" * 60)
            # ========== [/调试日志] ==========

            # 解析AI响应
            logger.info("[ContentGenerator] 开始解析AI响应...")
            result = cls._parse_ai_response(response, resources, params)
            
            # ========== [调试日志] 解析结果 ==========
            logger.info("[ContentGenerator] 解析完成，结果类型: %s", type(result))
            if isinstance(result, dict):
                logger.info("[ContentGenerator] 解析结果keys: %s", list(result.keys()))
                titles = result.get('titles', [])
                logger.info("[ContentGenerator] 生成标题数量: %d", len(titles))
                if titles:
                    for i, t in enumerate(titles):
                        logger.info("  标题%d: %s", i+1, t)
                images = result.get('images', [])
                logger.info("[ContentGenerator] 生成图片数量: %d", len(images))
            # ========== [/调试日志] ==========
            
        except Exception as e:
            import traceback
            logger.error("[ContentGenerator] AI调用异常: %s", e)
            logger.error("[ContentGenerator] 堆栈: %s", traceback.format_exc())
            # AI调用失败，降级到模板模式
            logger.warning("[ContentGenerator] AI调用失败，降级到模板模式: %s", e)
            result = cls._generate_from_template(params, resources)
            result['ai_fallback'] = True

        return result

    @classmethod
    def _generate_titles_from_keywords(cls, core: List[str], pain: List[str],
                                     scene: List[str], count: int = 2) -> List[str]:
        """从关键词生成标题"""
        titles = []

        if core and pain:
            titles.append(f'为什么{scene[0] if scene else ""}都在用{core[0]}？')
        if core:
            titles.append(f'{core[0]}怎么选？看完这篇就懂了')
        if pain:
            titles.append(f'{pain[0]}的坑，你踩过几个？')
        if scene:
            titles.append(f'{scene[0]}人群都在用{core[0] if core else "这款"}')

        return titles[:count] if titles else ['标题1', '标题2']

    @classmethod
    def _generate_tags_from_keywords(cls, core: List[str], pain: List[str],
                                  scene: List[str], count: int = 6) -> List[str]:
        """从关键词生成标签"""
        tags = []

        # 核心词
        for k in core[:1]:
            tags.append(f'#{k}')
        # 痛点词
        for k in pain[:2]:
            tags.append(f'#{k}')
        # 场景词
        for k in scene[:2]:
            tags.append(f'#{k}')
        # 长尾词
        if len(tags) < count:
            tags.append('#好物推荐')
        if len(tags) < count:
            tags.append('#种草')

        return tags[:count]

    @classmethod
    def _generate_graphic_content(cls, title: str, topic: Dict, keywords: Dict,
                                image_count: int = 5,
                                image_ratio: str = '9:16',
                                ai_images: List[Dict] = None,
                                graphic_rule: Dict = None) -> str:
        """生成图文内容Markdown
        
        Args:
            ai_images: AI生成的具体图片内容列表，每项包含 title, content 等字段
            graphic_rule: 从数据库加载的图文规则配置
        """
        
        # 获取痛点关键词
        pain_keywords = keywords.get('pain_point', [])
        pain_text = pain_keywords[0]['keyword'] if pain_keywords else '用户痛点'
        
        # 从规则中获取配置（如果有）
        rule_image_templates = []
        rule_headline_rules = {}
        rule_design_rules = {}
        if graphic_rule:
            rule_image_templates = graphic_rule.get('image_templates', [])
            for hl in graphic_rule.get('headline_rules', []):
                rule_headline_rules[hl.get('headline_type')] = hl
            rule_design_rules = graphic_rule.get('design_rules', {})
        
        lines = [
            f'# 图文内容模板',
            '',
            f'## 【内容结构】先痛后药，不要先讲产品！',
            '',
            f'## 基本信息',
            '',
            f'- **行业**: {topic.get("industry", "未知")}',
            f'- **目标客户**: {topic.get("customer", "通用")}',
            f'- **选题**: {topic.get("title", "通用内容")}',
            f'- **核心卖点**: {", ".join(keywords.get("core", []))}',
            f'- **痛点切入**: {pain_text}',
            '',
            f'## 标题（从用户困境切入）',
            f'{title}',
            '',
            f'## 图片内容（必须先戳痛点！）',
        ]

        # 如果有 AI 生成的具体内容，使用 AI 内容；否则使用规则配置或通用模板
        if ai_images and len(ai_images) > 0:
            # AI生成内容 + 规则增强
            for i, img in enumerate(ai_images[:image_count]):
                img_title = img.get('title', f'图片{i+1}')
                img_content = img.get('content', '[根据内容填写]')
                
                # 从规则中获取该图的配置
                rule_tpl = None
                if i < len(rule_image_templates):
                    rule_tpl = rule_image_templates[i]
                
                lines.extend([
                    f'### 图片{i+1}：{img_title}',
                    f'**比例**: {image_ratio} (1080x{1920 if image_ratio == "9:16" else 1080}px)',
                    '',
                ])
                
                # 添加规则要求的配置信息
                if rule_tpl:
                    positioning = rule_tpl.get('positioning', '')
                    emotion = rule_tpl.get('emotion', '')
                    headline_req = rule_tpl.get('headline_requirement', '')
                    if positioning:
                        lines.append(f'**定位**: {positioning}')
                    if emotion:
                        lines.append(f'**情绪**: {emotion}')
                    if headline_req:
                        lines.append(f'**大字要求**: {headline_req}')
                    lines.append('')
                
                lines.extend([
                    f'**内容**:',
                    f'{img_content}',
                    '',
                ])
        else:
            # 使用规则配置或通用模板
            if rule_image_templates:
                # 使用规则配置
                for i, rule_tpl in enumerate(rule_image_templates[:image_count]):
                    positioning = rule_tpl.get('positioning', '')
                    emotion = rule_tpl.get('emotion', '')
                    func = rule_tpl.get('function', '')
                    headline_req = rule_tpl.get('headline_requirement', '')
                    
                    lines.extend([
                        f'### 图片{i+1}：{positioning}',
                        f'**比例**: {image_ratio} (1080x{1920 if image_ratio == "9:16" else 1080}px)',
                        f'**情绪**: {emotion}',
                        f'**功能**: {func}',
                        '',
                        f'**大字金句**: {headline_req}',
                        '',
                        f'**内容**:',
                        f'[根据选题和关键词填写]',
                        '',
                    ])
            else:
                # 通用模板
                image_titles = [
                    '戳痛点：用户困境场景',      # 第1张必须直接呈现用户痛苦
                    '分析原因',                  # 为什么会这样？
                    '揭示误区',                  # 你以为...其实...
                    '解决方案',                  # 终于等到...
                    '总结引导'                   # 快试试/评论区见
                ]

                for i in range(min(image_count, len(image_titles))):
                    lines.extend([
                        f'### 图片{i+1}：{image_titles[i]}',
                        f'**比例**: {image_ratio} (1080x{1920 if image_ratio == "9:16" else 1080}px)',
                        '',
                        f'**标题**: [根据内容填写]',
                        '',
                        f'**内容**:',
                        f'[根据选题和关键词填写内容]',
                        '',
                    ])

        lines.extend([
            '## 评论区首评',
            '[一条真实感的用户评论，激发互动]',
            '',
            '## 发布建议',
            f'- 发布时间：周三/周五 12:00-13:00 或 周六/周日 20:00-21:00',
            f'- 建议添加话题：{", ".join([k["keyword"] for k in keywords.get("core", [])][:3])}',
        ])

        return '\n'.join(lines)

    @classmethod
    def _generate_long_text_content(cls, title: str, topic: Dict, keywords: Dict,
                                    ai_content: Dict = None) -> str:
        """生成长文内容Markdown

        Args:
            ai_content: AI生成的长文内容，包含 intro, problem, analysis, solution, conclusion, images
        """

        # 获取关键词
        core_keywords = keywords.get('core', [])
        pain_keywords = keywords.get('pain_point', [])

        lines = [
            '# 长文内容',
            '',
            '## 基本信息',
            f'- **行业**: {topic.get("industry", "未知")}',
            f'- **目标客户**: {topic.get("customer", "通用")}',
            f'- **选题**: {topic.get("title", "通用内容")}',
            f'- **核心关键词**: {", ".join([k["keyword"] for k in core_keywords]) if core_keywords else "暂无"}',
            f'- **痛点关键词**: {", ".join([k["keyword"] for k in pain_keywords]) if pain_keywords else "暂无"}',
            '',
            '## 标题',
            f'{title}',
            '',
        ]

        # 如果有 AI 生成的内容，使用 AI 内容
        if ai_content:
            # 引言
            intro = ai_content.get('intro', '')
            if intro:
                lines.extend([
                    '## 引言',
                    f'{intro}',
                    '',
                ])

            # 问题层
            problem = ai_content.get('problem', '')
            if problem:
                lines.extend([
                    '## 问题层：痛点场景',
                    f'{problem}',
                    '',
                ])

            # 分析层
            analysis = ai_content.get('analysis', '')
            if analysis:
                lines.extend([
                    '## 分析层：原因与数据',
                    f'{analysis}',
                    '',
                ])

            # 方案层
            solution = ai_content.get('solution', '')
            if solution:
                lines.extend([
                    '## 方案层：解决方案',
                    f'{solution}',
                    '',
                ])

            # 结论 + 延伸话题
            conclusion = ai_content.get('conclusion', '')
            extended_topic = ai_content.get('extended_topic', '')
            if conclusion or extended_topic:
                lines.extend([
                    '## 结论',
                    f'{conclusion}',
                    '',
                ])
                if extended_topic:
                    lines.extend([
                        '## 延伸话题（用于评论区引导）',
                        f'{extended_topic}',
                        '',
                    ])

            # 图片
            images = ai_content.get('images', [])
            if images:
                lines.extend([
                    '## 配图说明',
                    f'- 数量：{len(images)}张',
                    f'- 位置：随机放在文章开头或中间',
                    '',
                ])
                for i, img in enumerate(images[:2]):
                    pos = img.get('position', '待定')
                    desc = img.get('description', '')
                    prompt = img.get('prompt', '')
                    lines.extend([
                        f'### 图片{i+1}（{pos}）',
                        f'- 内容描述：{desc}',
                        f'- AI生图提示词：{prompt}',
                        '',
                    ])
        else:
            # 通用模板
            lines.extend([
                '## 引言（前3句话给出核心答案）',
                '[开门见山，直接给答案]',
                '',
                '## 问题层：痛点场景',
                '[具体人物+对话+场景]',
                '',
                '## 分析层：原因与数据',
                '[原因分析 + 具体数据/案例]',
                '',
                '## 方案层：解决方案',
                '[清单式解决方案，步骤清晰]',
                '',
                '## 结论 + 延伸话题',
                '[总结核心观点 + 引发讨论的问题]',
                '',
                '## 配图说明',
                '- 数量：1-2张',
                '- 位置：随机放在文章开头或中间',
                '- 内容：场景图/产品图/对比图',
                '',
            ])

        lines.extend([
            '## 发布建议',
            f'- 发布时间：工作日 20:00-22:00 或 周末全天',
            f'- 建议话题：{", ".join([k["keyword"] for k in core_keywords[:3]]) if core_keywords else "暂无"}',
        ])

        return '\n'.join(lines)

    @classmethod
    def _generate_video_script_content(cls, title: str, topic: Dict, keywords: Dict,
                                       ai_scenes: List[Dict] = None) -> str:
        """生成短视频分镜脚本Markdown

        Args:
            ai_scenes: AI生成的场景列表，每项包含 scene_id, time_range, scene_type, 画面, 配音, 字幕, camera
        """

        core_keywords = keywords.get('core', [])
        pain_keywords = keywords.get('pain_point', [])

        lines = [
            '# 短视频分镜脚本',
            '',
            '## 基本信息',
            f'- **标题**: {title}',
            f'- **行业**: {topic.get("industry", "未知")}',
            f'- **目标客户**: {topic.get("customer", "通用")}',
            f'- **选题**: {topic.get("title", "通用内容")}',
            '',
        ]

        # 如果有 AI 生成的场景
        if ai_scenes:
            # 计算总时长
            total_duration = "待计算"
            if ai_scenes:
                try:
                    last_time = ai_scenes[-1].get('time_range', '0-0秒')
                    # 提取最后的时间值
                    import re
                    match = re.search(r'(\d+)-(\d+)秒', last_time)
                    if match:
                        total_duration = f"{int(match.group(2))}秒"
                except:
                    pass

            lines.extend([
                f'## 视频信息',
                f'- **时长**: {total_duration}',
                f'- **比例**: 9:16（竖版）',
                f'- **平台**: 抖音/视频号',
                '',
                '## 分镜脚本',
                '',
            ])

            # 表格头部
            lines.extend([
                '| 场次 | 时间 | 类型 | 画面 | 配音 | 字幕 | 运镜 |',
                '|------|------|------|------|------|------|------|',
            ])

            for scene in ai_scenes:
                scene_id = scene.get('scene_id', '')
                time_range = scene.get('time_range', '')
                scene_type = scene.get('scene_type', '')
                画面 = scene.get('画面', '')
                配音 = scene.get('配音', '')
                字幕 = scene.get('字幕', '')
                camera = scene.get('camera', '')

                # 截断过长的内容
                画面_short = 画面[:50] + '...' if len(画面) > 50 else 画面
                配音_short = 配音[:30] + '...' if len(配音) > 30 else 配音

                lines.append(f'| {scene_id} | {time_range} | {scene_type} | {画面_short} | {配音_short} | {字幕} | {camera} |')

            lines.append('')

            # 行动号召
            cta = ''
            for scene in ai_scenes:
                if scene.get('scene_type') == '结尾引导':
                    cta = scene.get('配音', '')
                    break
            if cta:
                lines.extend([
                    '## 行动号召',
                    f'{cta}',
                    '',
                ])

            # 标签
            if core_keywords:
                tags = [f'#{k["keyword"]}' for k in core_keywords[:5]]
                lines.extend([
                    '## 推荐标签',
                    f'{", ".join(tags)}',
                    '',
                ])
        else:
            # 通用模板
            lines.extend([
                '## 视频信息',
                '- **时长**: 待计算（根据内容确定）',
                '- **比例**: 9:16（竖版）',
                '- **平台**: 抖音/视频号',
                '',
                '## 分镜脚本模板',
                '',
                '| 场次 | 时间 | 类型 | 画面 | 配音 | 字幕 | 运镜 |',
                '|------|------|------|------|------|------|------|',
                '| 1 | 0-3秒 | 开头钩子 | [具体场景描述] | [配音≤30字] | [字幕≤10字] | [运镜方式] |',
                '| 2 | 3-15秒 | 痛点展开 | [具体场景描述] | [配音≤30字] | [字幕≤10字] | [运镜方式] |',
                '| 3 | 15-30秒 | 案例警示 | [具体场景描述] | [配音≤30字] | [字幕≤10字] | [运镜方式] |',
                '| 4 | 30-40秒 | 解决方案 | [具体场景描述] | [配音≤30字] | [字幕≤10字] | [运镜方式] |',
                '| 5 | 40-45秒 | 结尾引导 | [具体场景描述] | [配音≤30字] | [字幕≤10字] | [运镜方式] |',
                '',
                '## 行动号召',
                '[结尾互动引导，如：评论区说说你的经历]',
                '',
                '## 推荐标签',
                f'{", ".join(["#" + k["keyword"] for k in core_keywords[:5]] if core_keywords else "#标签1 #标签2")}',
                '',
            ])

        lines.extend([
            '## 使用说明',
            '1. 将脚本复制给AI视频生成工具',
            '2. 根据配音和字幕生成对应视频',
            '3. 确保画面与配音节奏同步',
        ])

        return '\n'.join(lines)

    @classmethod
    def _build_ai_prompt(cls, params: Dict, resources: Dict) -> str:
        """构建AI增强prompt"""
        industry = params.get('industry', '通用')
        target_customer = cls._infer_target_customer(params)
        business_desc = params.get('business_description', '')

        # 获取补充信息
        customer_who = params.get('customer_who', '')
        customer_why = params.get('customer_why', '')
        customer_problem = params.get('customer_problem', '')
        customer_story = params.get('customer_story', '')
        customer_experiences = params.get('customer_experiences', [])
        service_scenario = params.get('service_scenario', 'other')
        local_city = params.get('local_city', '')
        business_type = params.get('business_type', '')

        # 获取系统固定底座人群（用于内容生成时参考目标人群）
        system_base_personas = get_system_base_personas(service_scenario, business_type)

        keywords = resources.get('keywords', {})
        topics = resources.get('topics', [])

        # 构建补充信息
        extra_info_parts = []
        if customer_who:
            extra_info_parts.append(f"客户是谁：{customer_who}")
        if customer_why:
            extra_info_parts.append(f"为什么找到：{customer_why}")
        if customer_problem:
            extra_info_parts.append(f"解决了什么问题：{customer_problem}")
        if customer_experiences:
            extra_info_parts.append(f"合作体验：{', '.join(customer_experiences)}")
        if customer_story:
            extra_info_parts.append(f"客户故事：{customer_story[:100]}...")
        if service_scenario:
            scenario_map = {
                'hotel_restaurant': '酒店/餐饮/茶楼/高端会所',
                'residential': '家用/住宅/小区业主',
                'office_enterprise': '写字楼/企业/工厂/园区',
                'institutional': '学校/医院/食堂/政企单位',
                'retail_chain': '实体店/连锁门店/加盟品牌',
                'renovation': '装修/工装/工程定制',
                'other': '其他小众场景'
            }
            extra_info_parts.append(f"主要服务场景：{scenario_map.get(service_scenario, service_scenario)}")
        if local_city:
            extra_info_parts.append(f"服务城市：{local_city}")

        extra_info = '\n'.join(extra_info_parts) if extra_info_parts else '暂无'

        # 根据content_type读取对应的skill
        content_type = params.get('content_type', 'graphic')
        skill_map = {
            'graphic': 'graphic-content-generator',
            'long_text': 'long-text-generator',
            'video': 'video-script-generator',
        }
        skill_name = skill_map.get(content_type, 'graphic-content-generator')
        skill_path = os.path.join(os.path.dirname(__file__), '..', 'skills', skill_name, 'SKILL.md')
        skill_prompt = ""
        if os.path.exists(skill_path):
            with open(skill_path, 'r', encoding='utf-8') as f:
                skill_prompt = f.read()

        prompt = f"""{PROMPT_BASE_CONSTRAINT.format(system_base_personas=system_base_personas)}

{skill_prompt}

请严格按照skill中的【输出格式】和【质量标准】生成内容。

【业务信息】
行业：{industry}
目标客户：{target_customer}
业务描述：{business_desc or "暂无"}

补充信息：
{extra_info}

可用关键词：
- 核心词：{", ".join([k["keyword"] for k in keywords.get("core", [])]) if keywords.get("core") else "暂无"}
- 痛点词：{", ".join([k["keyword"] for k in keywords.get("pain_point", [])]) if keywords.get("pain_point") else "暂无"}
- 场景词：{", ".join([k["keyword"] for k in keywords.get("scene", [])]) if keywords.get("scene") else "暂无"}
- 长尾词：{", ".join([k["keyword"] for k in keywords.get("long_tail", [])]) if keywords.get("long_tail") else "暂无"}
"""
        return prompt

    @classmethod
    def _parse_ai_response(cls, response: str, resources: Dict, params: Dict = None) -> Dict:
        """解析AI响应"""
        content_type = (params or {} .get('content_type', 'graphic') if params else 'graphic')

        try:
            # 尝试解析JSON
            if isinstance(response, str):
                data = json.loads(response)
            else:
                data = response

            # 获取 AI 生成的内容
            ai_content = data.get('content', {})

            if content_type == 'long_text':
                # 长文内容
                content = cls._generate_long_text_content(
                    title=data.get('titles', [''])[0] if data.get('titles') else '',
                    topic={'title': ai_content.get('topic', '')},
                    keywords=resources.get('keywords', {}),
                    ai_content={
                        'intro': ai_content.get('intro', ''),
                        'problem': ai_content.get('problem', ''),
                        'analysis': ai_content.get('analysis', ''),
                        'solution': ai_content.get('solution', ''),
                        'conclusion': ai_content.get('conclusion', ''),
                        'extended_topic': ai_content.get('extended_topic', ''),
                        'images': ai_content.get('images', []),
                    }
                )
                return {
                    'titles': data.get('titles', []),
                    'tags': data.get('tags', []),
                    'content': content,
                    'ai_generated': True,
                }

            elif content_type == 'video':
                # 短视频分镜脚本
                content = cls._generate_video_script_content(
                    title=data.get('titles', [''])[0] if data.get('titles') else '',
                    topic={'title': ai_content.get('topic', '')},
                    keywords=resources.get('keywords', {}),
                    ai_scenes=ai_content.get('scenes', [])
                )
                return {
                    'titles': data.get('titles', []),
                    'tags': data.get('tags', []),
                    'content': content,
                    'ai_generated': True,
                }

            else:
                # 图文内容（默认）
                ai_images = ai_content.get('images', [])
                ai_topic = ai_content.get('topic', '')

                # 加载图文规则配置
                graphic_rule = None
                try:
                    from services.graphic_rule_service import graphic_rule_service
                    portrait_id = params.get('portrait_id') if params else None
                    industry = params.get('industry') if params else None
                    graphic_rule = graphic_rule_service.get_active_rule(
                        industry=industry,
                        portrait_id=portrait_id
                    )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"加载图文规则失败: {e}")

                # 构建完整内容
                content = cls._generate_graphic_content(
                    title=data.get('titles', [''])[0],
                    topic={'title': ai_topic or ai_content.get('topic', '')},
                    keywords=resources.get('keywords', {}),
                    image_count=5,
                    image_ratio='9:16',
                    ai_images=ai_images,
                    graphic_rule=graphic_rule
                )

                return {
                    'titles': data.get('titles', []),
                    'tags': data.get('tags', []),
                    'content': content,
                    'ai_generated': True,
                }

        except (json.JSONDecodeError, KeyError):
            # 解析失败，返回原始响应
            return {
                'titles': ['标题1', '标题2'],
                'tags': ['#标签1', '#标签2'],
                'content': response,
                'ai_generated': False,
            }

    @classmethod
    def _infer_target_customer(cls, params: Dict[str, Any]) -> str:
        """
        从表单参数推断目标客户

        优先级：
        1. 选中的目标用户画像信息（selected_target_info）
        2. 显式的 target_customer 参数
        3. customer_who 字段
        4. customer_why + customer_problem 组合
        5. business_description 中的关键词
        6. 默认通用目标客户
        """
        # 1. 选中的目标用户画像优先
        selected_info = params.get('selected_target_info')
        if selected_info:
            if isinstance(selected_info, dict):
                return selected_info.get('name', '') or selected_info.get('description', '')
            return str(selected_info)

        # 2. 显式参数优先
        if params.get('target_customer'):
            return params['target_customer']

        # 2. customer_who 字段
        customer_who = params.get('customer_who', '').strip()
        if customer_who:
            return customer_who

        # 3. 从 customer_why 和 customer_problem 组合推断
        customer_why = params.get('customer_why', '').strip()
        customer_problem = params.get('customer_problem', '').strip()
        customer_story = params.get('customer_story', '').strip()

        if customer_why or customer_problem or customer_story:
            parts = []
            if customer_why:
                parts.append(f"找您原因：{customer_why}")
            if customer_problem:
                parts.append(f"痛点：{customer_problem}")
            if customer_story:
                # 截取故事的前50字
                story_preview = customer_story[:50] + ('...' if len(customer_story) > 50 else '')
                parts.append(f"故事：{story_preview}")
            return ' | '.join(parts)

        # 4. 从业务描述推断
        business_desc = params.get('business_description', '')
        if business_desc:
            # 提取业务描述中的关键信息作为目标客户
            desc = business_desc.lower()
            if any(k in desc for k in ['写字楼', '企业', '公司', ' office']):
                return '企业客户/写字楼'
            elif any(k in desc for k in ['餐厅', '饭店', '酒店', '餐饮']):
                return '餐饮商家'
            elif any(k in desc for k in ['个人', '家庭', '居民']):
                return '个人/家庭用户'
            elif any(k in desc for k in ['批发', '代理', '经销商']):
                return '批发商/代理商'

        # 5. 从经营类型推断
        business_type = params.get('business_type', '')
        if business_type == 'enterprise':
            return '企业客户'
        elif business_type == 'local_service':
            return '本地居民/商户'
        elif business_type == 'product':
            return '消费者'
        elif business_type == 'personal':
            return '个人粉丝/追随者'

        # 6. 默认值
        return '普通消费者'

    @classmethod
    def _get_quota_message(cls, reason: str, quota_info: Dict) -> str:
        """获取配额提示消息"""
        messages = {
            'daily_limit_exceeded': f'今日免费次数已用完，明天 {quota_info.get("reset_at", "00:00")} 重置',
            'monthly_limit_exceeded': f'本月生成次数已用完，超量需支付 {quota_info.get("overage_price", 3)} 元/次',
        }
        return messages.get(reason, '配额不足')

    @classmethod
    def get_generation_history(cls, user: PublicUser, page: int = 1,
                              per_page: int = 20) -> Dict:
        """获取生成历史"""
        query = PublicGeneration.query.filter_by(user_id=user.id).order_by(
            PublicGeneration.created_at.desc()
        )
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            'items': [{
                'id': g.id,
                'industry': g.industry,
                'target_customer': g.target_customer,
                'titles': g.titles,
                'tags': g.tags,
                'created_at': g.created_at.isoformat(),
            } for g in pagination.items],
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages,
        }


# 全局实例
content_generator = ContentGenerator()


# =============================================================================
# 问题渠道识别（Stage 0）
# =============================================================================

def _build_industry_keywords(business_desc: str) -> List[str]:
    """
    从业务描述中提取行业关键词，用于过滤离题结果。
    策略：
    1. 提取 2-4 字的中文词组（去除常见通用词）
    2. 返回高置信度的行业词（名词性、2字以上）
    """
    if not business_desc:
        return []

    generic_words = {
        '服务', '产品', '销售', '公司', '业务', '经营', '企业', '品牌', '专业',
        '定制', '提供', '客户', '用户', '市场', '管理', '方案', '效果',
        '价格', '质量', '怎么', '哪里', '如何', '可以', '一个', '我们',
        '需要', '寻找', '推荐', '哪家', '最好', '比较', '选择', '请问',
        '有没有', '有没有', '帮忙', '一下', '什么', '这个', '那个',
    }
    chunks = re.findall(r'[\u4e00-\u9fff]{2,6}', business_desc)
    return [c for c in chunks if c not in generic_words and len(c) >= 2]


def _is_channel_industry_related(business_desc: str, keywords: List[str], ch: Dict[str, Any]) -> bool:
    """
    判断一条渠道是否与业务所在行业相关（本体或上下游）。
    相关判定：渠道文案中至少含有一个行业关键词。
    也接受「买新的」「换一家」「找维修」类替代方案句式（隐含行业关联）。
    """
    if not keywords:
        return True  # 无关键词时不过滤

    blob = ' '.join([
        str(ch.get('search_intent') or ''),
        str(ch.get('trigger_scenario') or ''),
        str(ch.get('identity') or ''),
    ] + (ch.get('alternative_solutions') or []))

    for kw in keywords:
        if kw in blob:
            return True

    # 替代方案中含「买新的」「换供应商」「重新买」等泛化路径 → 也算相关
    alt_keywords = re.compile(
        r'买新|换供|换一|重新|换掉|重买|找别|别家|换店|换人',
    )
    if alt_keywords.search(blob):
        return True

    return False


def _filter_problem_channels_off_topic(business_desc: str, channels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    双重过滤：
    1. 硬过滤：渠道文案必须含业务描述行业关键词（或上下游相关词），否则丢弃。
    2. 噪声过滤：若业务描述不含婴幼儿域，丢弃命中宝宝/奶粉/胀气等典型噪声词
       且与行业无字面相交的条目。
    """
    bd = (business_desc or '').strip()
    if not bd or not channels:
        return channels

    keywords = _build_industry_keywords(bd)

    baby_domain_markers = (
        '婴', '宝宝', '奶粉', '孕妇', '辅食', '幼儿', '新生儿', '转奶',
        '母乳', '奶瓶', '尿布', '纸尿裤',
    )
    business_touches_baby = any(m in bd for m in baby_domain_markers)

    baby_noise = re.compile(
        r'宝宝|奶粉|胀气|换奶|乳糖|厌奶|宝妈|转奶|尿布|纸尿裤|新生儿|辅食|喝奶|儿科|验奶',
    )

    # 业务描述 2-8 字词组（用于噪声条目与业务的弱相关判断）
    biz_chunks = set(re.findall(r'[\u4e00-\u9fff]{2,8}', bd))

    kept: List[Dict[str, Any]] = []
    for ch in channels:
        blob = ' '.join([
            str(ch.get('search_intent') or ''),
            str(ch.get('trigger_scenario') or ''),
            str(ch.get('identity') or ''),
        ] + (ch.get('alternative_solutions') or []))

        # ── 规则1：硬过滤 ──
        # 渠道文案必须命中行业关键词（或「买新的」类替代方案），才算与本行业相关
        if keywords and not _is_channel_industry_related(bd, keywords, ch):
            logger.debug('[_filter] 丢弃（行业无关）: intent=%s', str(ch.get("search_intent",""))[:40])
            continue

        # ── 规则2：婴幼儿噪声过滤（仅当业务不在婴幼儿域时生效）──
        if not business_touches_baby:
            # 命中噪声词 且 与业务描述无任何字面相交 → 丢弃
            def hits_business() -> bool:
                for c in biz_chunks:
                    if len(c) >= 2 and c in blob:
                        return True
                return False

            if baby_noise.search(blob) and not hits_business():
                logger.debug('[_filter] 丢弃（婴幼儿噪声）: intent=%s', str(ch.get("search_intent",""))[:40])
                continue

        kept.append(ch)

    # 过滤过猛则回退（保留至少 3 条）
    min_keep = min(3, len(channels))
    if len(kept) < min_keep:
        logger.warning('[_filter] 过滤过猛(%s/%s)，回退原数据', len(kept), len(channels))
        return channels
    return kept


def mine_problem_channels(params: Dict[str, Any]) -> Dict:
    """
    Stage 0：问题渠道识别

    在问题类型之前运行，挖掘「用户带着什么问题来搜索」。
    输出用户真实搜索意图/问题句式，作为后续 Stage 1 的输入上下文。

    Args:
        params: {
            'business_description': str,
            'business_range': str,
            'business_type': str,
        }

    Returns:
        {
            'success': True,
            'data': {
                'problem_channels': [
                    {
                        'channel': '搜索渠道（如：小红书搜索、百度搜索、朋友推荐）',
                        'identity': '搜索者身份（如：新手宝妈、上班族、中年男性）',
                        'search_intent': '搜索意图句式（须与上方业务强相关）',
                        'trigger_scenario': '触发搜索的具体场景（须与业务场景一致）',
                        'alternative_solutions': ['其他解决路径1', '其他解决路径2'],
                        'severity': '高/中/低',
                    }
                ],
                'insight': '一句话洞察：用户的核心困惑是什么'
            }
        }
    """
    import re
    import os
    from services.llm import LLMService

    business_desc = (params.get('business_description') or '').strip()
    business_range = params.get('business_range', 'local')
    business_type = params.get('business_type', 'local_service')
    service_scenario = params.get('service_scenario', 'other')

    if not business_desc:
        return {'success': False, 'message': '请描述您的业务'}

    # 获取系统固定底座人群
    system_base_personas = get_system_base_personas(service_scenario, business_type)

    # 模型选择
    provider = os.environ.get('LLM_PROVIDER', 'siliconflow')
    model = os.environ.get('LLM_MODEL_TURBO', 'Qwen/Qwen2.5-7B-Instruct')
    base_url = os.environ.get('LLM_BASE_URL', 'https://api.siliconflow.cn/v1')
    api_key = os.environ.get('LLM_API_KEY', '')

    llm = LLMService(provider=provider, model=model)
    llm.base_url = base_url
    llm.api_key = api_key

    business_range_text = '本地/同城' if business_range == 'local' else '跨区域/全国'
    business_type_name = BUSINESS_TYPE_MAP.get(business_type, '本地服务')

    prompt = f"""{PROMPT_BASE_CONSTRAINT.format(system_base_personas=system_base_personas)}
你是用户搜索行为专家。请**只针对下方「业务」**分析：用户遇到与**该业务相关**的问题时，会如何搜索、从哪些渠道找答案。

【绝对约束 — 禁止数据污染】
- 每一条 problem_channels 的 search_intent、trigger_scenario、alternative_solutions、identity 必须**全部**与「业务描述」直接相关。
- **禁止**输出与业务无关行业的搜索词或场景（例如：业务是餐具修复却写宝宝喝奶、奶粉、胀气、换奶、医院看儿科等 —— 一律禁止）。
- **禁止**照抄本提示词里的任何示例句式；示例仅说明 JSON 结构，**不得**出现在你的输出里。
- insight 也必须概括**本业务**用户的搜索动机，不得写其他行业。

业务信息（唯一事实来源）：
- 业务：{business_desc}
- 范围：{business_range_text}
- 类型：{business_type_name}

=== 核心任务 ===
挖掘「用户带着什么问题来搜索」：用户在**与本业务相关的**场景下，因**具体问题**去搜索（不是搜品牌名本身，而是搜「怎么办/哪里能/靠谱吗」类问题句）。

=== 思维框架（须落到本业务） ===
1. 用户旅程：遇到与本业务相关的事 → 想自己处理或找人 → 去搜索/问人
2. 搜索意图：用**口语化问句**，且必须能看出来是在找「本业务」这类解决方案
3. 多渠道：小红书/百度/抖音/知乎/朋友圈/朋友推荐等，**同一业务**下不同人群、不同渠道的搜法可以不同
4. 替代方案：用户在找你之前可能选的**与本问题相关的**其他路径（如：自己修、买新的、找别家），不得写无关行业方案

=== 输出格式（严格JSON） ===
只输出JSON，不要其他文字：
```json
{{
    "problem_channels": [
        {{
            "channel": "搜索渠道名称",
            "identity": "与本业务相关的搜索者身份",
            "search_intent": "与本业务相关的搜索问句（禁止套用其他行业）",
            "trigger_scenario": "与本业务相关的触发场景",
            "alternative_solutions": ["与本问题相关的替代路径1", "与本问题相关的替代路径2"],
            "severity": "高/中/低"
        }}
    ],
    "insight": "一句话概括本业务用户的典型搜索动机（20字以内）"
}}
```

=== 数量与质量 ===
- 生成5-8条，每条渠道字段各不相同
- search_intent 要像真实搜索框里会输入的话
- 输出中文"""

    try:
        response = llm.chat(prompt, temperature=0.45, max_tokens=2000)
        logger.debug("[mine_problem_channels] LLM响应前500字: %s", response[:500] if response else None)

        if not response:
            return {'success': False, 'message': 'AI服务暂不可用'}

        # 解析JSON
        match = re.search(r'\{[\s\S]*\}', response)
        if not match:
            return {'success': False, 'message': '解析失败，请重试'}

        result = json.loads(match.group(0))
        channels = result.get('problem_channels', [])

        if not channels:
            return {'success': False, 'message': '未识别到有效的问题渠道'}

        channels = _filter_problem_channels_off_topic(business_desc, channels)
        if not channels:
            return {'success': False, 'message': '未识别到有效的问题渠道'}

        # 补充ID
        for i, ch in enumerate(channels):
            if not ch.get('channel'):
                ch['channel'] = f'渠道{i+1}'
            if not ch.get('search_intent'):
                ch['search_intent'] = ch.get('trigger_scenario', '未知意图')

        return {
            'success': True,
            'data': {
                'problem_channels': channels,
                'insight': result.get('insight', '')
            }
        }

    except Exception as e:
        import traceback
        logger.error("[mine_problem_channels] 异常: %s", e)
        logger.debug("[mine_problem_channels] 堆栈: %s", traceback.format_exc())
        return {'success': False, 'message': f'识别失败: {str(e)}'}


# =============================================================================
# 问题大类推断（LLM 漏填 problem_category 时兜底）
# =============================================================================

def infer_problem_category(
    problem_type: str,
    description: str = '',
    display_name: str = '',
) -> str:
    """
    根据 problem_type + 描述 + 展示名推断五大类之一（与 Prompt 中「问题大类」表述一致）。
    用于 API 返回给前端的 problem_category，保证卡片可稳定展示【大类】前缀。
    """
    text = f"{problem_type or ''}{description or ''}{display_name or ''}"
    if not text.strip():
        return ''

    # (大类全称, 关键词列表)；同类内放较长词在前，减少误匹配
    rules: List[Tuple[str, List[str]]] = [
        ("安全/质量问题", [
            "安全隐患", "卫生问题", "质量缺陷", "食物中毒", "交叉感染",
            "过期", "变质", "漏电", "中毒", "过敏", "感染", "假货", "受伤", "事故",
        ]),
        ("适配/兼容问题", [
            "不知道选", "怕买错", "选哪款", "难选", "选错", "不匹配", "不适合",
        ]),
        ("成本/效率问题", [
            "怕被宰", "乱收费", "性价比", "等太久", "响应慢", "上门慢", "周期长", "效率低",
            "预约难", "排队", "预算", "费用", "多少钱", "加价", "价格", "贵", "怕贵",
        ]),
        ("功能/效果问题", [
            "怕效果差", "效果差", "没效果", "无效", "治不好", "功能失效", "达不成",
            "解决不了", "没治好", "不奏效", "怕效果",
        ]),
        ("体验/使用问题", [
            "服务不专业", "服务态度", "态度差", "服务差", "不热情", "敷衍", "体验差",
            "难用", "操作复杂", "不舒服", "不专业",
        ]),
    ]
    for category, kws in rules:
        for kw in kws:
            if kw in text:
                return category
    # 本地生活/服务业常见表述未命中时，多数可归为体验侧
    return "体验/使用问题"


def _detect_buyer_user_separation(business_desc: str, business_type: str) -> Dict[str, Any]:
    """
    检测是否存在买用分离，返回付费者视角的身份映射

    Args:
        business_desc: 业务描述
        business_type: 经营类型

    Returns:
        {
            'separation': bool,          # 是否存在买用分离
            'buyer_identity': str,       # 付费者身份
            'user_keywords': list,       # 使用者关键词列表（用于匹配）
            'buyer_problem_prefix': str, # 付费者描述使用者问题时的前缀
        }
    """
    desc = (business_desc or '').lower()

    # 婴儿/儿童用品类
    baby_keywords = ['奶粉', '尿不湿', '尿裤', '婴儿', '儿童', '宝宝', '儿童', '童装',
                     '儿童玩具', '婴儿车', '儿童座椅', '奶瓶', '儿童餐椅', '儿童书',
                     '早教', '胎教', '辅食', '儿童牙膏', '儿童牙刷', '儿童沐浴', '儿童霜']
    # 养老/健康产品类
    elderly_keywords = ['老人', '养老', '助听器', '轮椅', '拐杖', '护理', '敬老',
                       '老花镜', '血压计', '血糖仪', '制氧机', '雾化器', '护腰带',
                       '护膝', '足浴盆', '按摩椅', '保健', '中老年']
    # 宠物类
    pet_keywords = ['宠物', '猫粮', '狗粮', '猫砂', '宠物食品', '宠物用品', '猫窝', '狗窝',
                   '宠物玩具', '宠物药品', '宠物美容', '宠物医院', '宠物保险']
    # 礼品类
    gift_keywords = ['礼品', '送礼', '礼物', '定制礼物', '企业礼品', '商务礼品', '节日礼品',
                    '生日礼品', '婚礼礼品', '纪念品']

    # 检测是否存在买用分离
    if any(k in desc for k in baby_keywords):
        return {
            'separation': True,
            'type': 'baby',
            'buyer_identity': '新手父母/宝爸宝妈',
            'user_keywords': ['宝宝', '孩子', '儿童', '男宝', '女宝', '婴儿', '幼儿', '小宝'],
            'buyer_problem_prefix': '宝宝',
            'buyer_problem_examples': ['宝宝拉肚子怎么回事', '宝宝不喝奶怎么办', '宝宝湿疹怎么护理'],
        }
    elif any(k in desc for k in elderly_keywords):
        return {
            'separation': True,
            'type': 'elderly',
            'buyer_identity': '子女（40-55岁）',
            'user_keywords': ['老人', '老年人', '老爷子', '老太太', '老爸', '老妈'],
            'buyer_problem_prefix': '老人',
            'buyer_problem_examples': ['老人吃饭噎着怎么办', '老人听力不好怎么选助听器', '老人腿脚不便怎么护理'],
        }
    elif any(k in desc for k in pet_keywords):
        return {
            'separation': True,
            'type': 'pet',
            'buyer_identity': '宠物主人（25-40岁）',
            'user_keywords': ['猫咪', '狗狗', '宠物', '猫', '狗', '汪星人', '喵星人'],
            'buyer_problem_prefix': '宠物',
            'buyer_problem_examples': ['猫咪拉肚子怎么回事', '狗狗不吃狗粮怎么办', '猫粮哪个牌子好'],
        }
    elif any(k in desc for k in gift_keywords):
        return {
            'separation': True,
            'type': 'gift',
            'buyer_identity': '送礼人',
            'user_keywords': ['收礼人', '领导', '客户', '长辈', '朋友'],
            'buyer_problem_prefix': '收礼人',
            'buyer_problem_examples': ['领导喜欢什么礼品', '客户送礼怎么选', '送长辈什么礼物好'],
        }

    return {
        'separation': False,
        'type': None,
        'buyer_identity': None,
        'user_keywords': [],
        'buyer_problem_prefix': None,
        'buyer_problem_examples': [],
    }


def _convert_identity_to_buyer_view(identity: str, buyer_user_info: Dict) -> str:
    """
    将使用者身份转换为付费者视角

    Args:
        identity: 原有的使用者身份描述
        buyer_user_info: 买用分离检测结果

    Returns:
        转换后的付费者视角身份
    """
    if not buyer_user_info.get('separation') or not identity:
        return identity

    identity_lower = identity.lower()
    user_keywords = buyer_user_info.get('user_keywords', [])
    buyer_identity = buyer_user_info.get('buyer_identity', '')

    # 检查 identity 是否包含使用者关键词
    for kw in user_keywords:
        if kw in identity_lower:
            # 找到了使用者关键词，返回付费者身份
            return buyer_identity

    # 检查 identity 是否是年龄描述（如"3岁"、"6个月"）
    age_pattern = r'\d+岁|\d+个月|\d+周|\d+天'
    if re.search(age_pattern, identity):
        # 年龄描述通常就是使用者身份，需要转换为付费者视角
        return buyer_identity

    # 检查是否是动物/宠物描述
    if buyer_user_info.get('type') == 'pet':
        pet_keywords = ['猫', '狗', '宠', '汪', '喵']
        for kw in pet_keywords:
            if kw in identity_lower:
                return buyer_identity

    return identity


def _convert_description_to_buyer_view(description: str, buyer_user_info: Dict) -> str:
    """
    将描述中的使用者视角转换为付费者视角

    例如：
    "3岁男宝吃奶粉拉肚子" → "宝宝吃奶粉拉肚子"
    "老人使用助听器听不清" → "老人用助听器听不清"
    """
    if not buyer_user_info.get('separation') or not description:
        return description

    desc = description
    prefix = buyer_user_info.get('buyer_problem_prefix', '')

    # 婴儿/儿童类：将具体年龄描述转为"宝宝"
    if buyer_user_info.get('type') == 'baby':
        # 移除具体年龄描述
        desc = re.sub(r'\d+岁(男|女)?宝', f'{prefix}', desc)
        desc = re.sub(r'\d+个月(男|女)?宝', f'{prefix}', desc)
        desc = re.sub(r'(男|女)宝', f'{prefix}', desc)
        desc = re.sub(r'婴幼儿', f'{prefix}', desc)
        # 统一改为"宝宝"
        desc = re.sub(r'孩子', f'{prefix}', desc)

    # 老年人类：保持"老人"描述，但确保格式一致
    elif buyer_user_info.get('type') == 'elderly':
        desc = re.sub(r'老爷子', '老人', desc)
        desc = re.sub(r'老太太', '老人', desc)

    # 宠物类：将宠物名统一
    elif buyer_user_info.get('type') == 'pet':
        desc = re.sub(r'猫咪', '宠物', desc)
        desc = re.sub(r'狗狗', '宠物', desc)

    return desc


def mine_problems(params: Dict[str, Any]) -> Dict:
    """
    纯问题挖掘（不生成画像），供 api_identify_problems 路由调用。

    返回格式：
    {
        'success': True,
        'problems': {'problems': [...]},
        'is_premium': bool
    }
    每条 problem 包含 identity / problem_type / description / severity / scenario / search_intent
    """
    result = mine_problems_and_generate_personas(params)
    if not result.get('success'):
        return result

    # 透传 refresh_round 到结果中，供前端"换一批"逻辑使用
    result['refresh_round'] = params.get('refresh_round', 0)
    data = result.get('data') or {}
    user_problems = data.get('user_problem_types', [])
    buyer_problems = data.get('buyer_concern_types', [])

    # 【买用分离检测】检测是否存在买用分离（如婴儿用品、老人用品等）
    # 需要将使用者身份转换为付费者视角
    business_desc = params.get('business_description', '')
    business_type = (params.get('business_type') or '').strip()
    buyer_user_info = _detect_buyer_user_separation(business_desc, business_type)
    if buyer_user_info.get('separation'):
        logger.info("[mine_problems] 检测到买用分离业务，类型=%s，付费者身份=%s",
                    buyer_user_info.get('type'), buyer_user_info.get('buyer_identity'))

    # 买即用（消费品/本地服务）：使用者=付费者，模型仍常输出与使用方同维度的「付费方顾虑」，
    # 拼接后 UI 会出现上下两排质量/价格/服务重复。对 buyer 侧按 (身份, 问题类型) 去重。
    if business_type in ('product', 'local_service') and user_problems and buyer_problems:

        def _problem_axis_key(p: Dict) -> tuple:
            ident = (p.get('identity') or '').strip().lower()
            axis = (p.get('problem_type') or p.get('concern_type') or '').strip().lower()
            return (ident, axis)

        user_keys = {_problem_axis_key(p) for p in user_problems}
        before_n = len(buyer_problems)
        buyer_problems = [p for p in buyer_problems if _problem_axis_key(p) not in user_keys]
        if before_n != len(buyer_problems):
            logger.info("[mine_problems] 买即用去重：剔除与使用方同维度的付费方条数 %s，剩余 buyer=%s",
                        before_n - len(buyer_problems), len(buyer_problems))

    all_problems = []
    _used_problem_ids = set()

    def _alloc_problem_id(preferred, fallback: str) -> str:
        s = '' if preferred is None else str(preferred).strip()
        base = s or fallback
        if base not in _used_problem_ids:
            _used_problem_ids.add(base)
            return base
        n = 1
        while f'{base}__{n}' in _used_problem_ids:
            n += 1
        uid = f'{base}__{n}'
        _used_problem_ids.add(uid)
        return uid

    def _enrich(problem: Dict, index: int, side: str) -> Dict:
        """直接透传 LLM 输出字段，并应用买用分离身份转换"""
        identity = problem.get('identity', '')
        problem_type = (
            problem.get('problem_type', '') or
            problem.get('concern_type', '') or
            ''
        )
        # 细分类型的大类：user_problem_types 用 problem_category，buyer_concern_types 用 concern_category
        desc = problem.get('description', '')

        # 【买用分离处理】如果是买用分离业务，且是 user 类型问题，转换 identity 和 description
        original_identity = identity
        original_desc = desc
        if buyer_user_info.get('separation') and side in ('user', 'chronic'):
            # 转换 identity 到付费者视角
            identity = _convert_identity_to_buyer_view(identity, buyer_user_info)
            # 转换 description 到付费者视角
            desc = _convert_description_to_buyer_view(desc, buyer_user_info)
            if identity != original_identity or desc != original_desc:
                logger.debug("[mine_problems] 买用分离身份转换: identity '%s' → '%s', desc '%s' → '%s'",
                            original_identity, identity, original_desc[:50] if original_desc else '', desc[:50] if desc else '')

        display_name_raw = problem.get('display_name', '') or f"{identity}{problem_type}"
        problem_category = (
            (problem.get('problem_category') or problem.get('concern_category') or '')
        ).strip()
        if not problem_category:
            problem_category = infer_problem_category(problem_type, desc, display_name_raw)
        base_map = {
            '刚需痛点盘': '转化型',
            '前置观望种草盘': '种草型',
            '使用配套搜后种草盘': '种草型',
            '刚需痛点': '转化型',
            '前置观望': '种草型',
            '使用配套': '种草型',
        }
        base = problem.get('problem_base') or problem.get('concern_base') or ''

        # 四类种草原生问题强制归入「前置观望种草盘」
        if is_seeding_problem(problem_type, desc):
            base = PROBLEM_BASE_SOUQIAN_ZHONGCAO

        direction = base_map.get(base, '种草型')

        # 双标签自动打标
        severity_for_tag = problem.get('severity', '中')
        consume_type = auto_tag_consume_type(problem_type, desc, severity_for_tag)
        demand_attr = auto_tag_demand_attr(problem_type, desc)

        return {
            'id': _alloc_problem_id(problem.get('id'), f"{side}_{index+1}"),
            'identity': identity,
            'problem_base': base,
            'problem_category': problem_category,
            'problem_type': problem_type,
            'display_name': display_name_raw,
            'description': desc,
            'severity': problem.get('severity', '中'),
            'scenario': problem.get('scenario', '通用'),
            'market_type': problem.get('market_type', 'red_ocean'),
            'market_reason': problem.get('market_reason', ''),
            'problem_keywords': problem.get('problem_keywords', []),
            'content_direction': direction,
            'consume_type': consume_type,
            'demand_attr': demand_attr,
            '_side': side,
            # 【买用分离标记】保留原始身份用于调试
            '_original_identity': original_identity if buyer_user_info.get('separation') else None,
            # 【新增】慢性体征标签
            'behavior_tags': problem.get('behavior_tags', []),
            'scene_tags': problem.get('scene_tags', []),
            'symptom_tags': problem.get('symptom_tags', []),
            'is_chronic_symptom': problem.get('is_chronic_symptom', False),
        }

    # buyer_problems already resolved above
    for i, p in enumerate(user_problems):
        all_problems.append(_enrich(p, i, 'user'))
    for i, p in enumerate(buyer_problems):
        all_problems.append(_enrich(p, i, 'buyer'))

    # 【新增】合并慢性体征解析层的问题
    chronic_extraction = data.get('chronic_extraction', {})
    chronic_problems = chronic_extraction.get('chronic_problems', [])
    for i, cp in enumerate(chronic_problems):
        # 为慢性问题添加行为场景体征标签
        chronic_tags = {
            'behavior_tags': cp.get('behavior_tags', []),
            'scene_tags': cp.get('scene_tags', []),
            'symptom_tags': cp.get('symptom_tags', []),
            'is_chronic_symptom': True,
        }
        enriched = _enrich(cp, i, 'chronic')
        enriched.update(chronic_tags)
        all_problems.append(enriched)

    # 【定制礼赠】程序化种子问题并入列表（与慢性层一致，保证前端可见）
    custom_gift_extraction = data.get('custom_gift_extraction') or {}
    cg_probs = custom_gift_extraction.get('custom_gift_problems') or []
    cg_u, cg_b = 0, 0
    for gp in cg_probs:
        side = (gp.get('_merge_side') or 'user').strip().lower()
        clean = {k: v for k, v in gp.items() if k != '_merge_side'}
        idx = cg_u if side == 'user' else cg_b
        if side == 'user':
            cg_u += 1
        else:
            cg_b += 1
        enriched = _enrich(clean, idx, 'cg_' + side)
        all_problems.append(enriched)

    # 【内容去重 - 全局强化版】多维度语义相似度判定
    # 任意两项在以下维度中任意一项高度相似即判定重复：
    # 1. 动机/渴望相近  2. 障碍/痛点相近  3. 决策阶段一致  4. 风险类型一致

    import re as re_module

    def _normalize_text(text: str) -> str:
        """文本标准化：去除标点、转小写、去除空格"""
        if not text:
            return ''
        t = re_module.sub(r'[^\w\u4e00-\u9fff]', '', text.lower())
        return re_module.sub(r'\s+', '', t)

    def _extract_core_semantics(p: Dict) -> Dict:
        """提取问题的核心语义特征"""
        identity = _normalize_text(p.get('identity') or '')
        problem_type = _normalize_text(p.get('problem_type') or '')
        description = _normalize_text(p.get('description') or '')
        problem_category = _normalize_text(p.get('problem_category') or '')
        dimension = _normalize_text(p.get('dimension') or '')
        display_name = _normalize_text(p.get('display_name') or '')

        # 提取关键词核心词（去除重复词）
        keywords_raw = []
        for kw in p.get('problem_keywords', []):
            if isinstance(kw, dict):
                kw_text = (kw.get('keyword') or '').strip()
            elif isinstance(kw, str):
                kw_text = kw.strip()
            else:
                continue
            if kw_text:
                keywords_raw.append(_normalize_text(kw_text))

        # 合并 identity + problem_category + dimension + display_name 作为"动机/障碍"特征
        motivation_key = identity + problem_category + dimension
        # 合并 problem_type + description + keywords 作为"障碍/痛点"特征
        barrier_key = problem_type + description + ''.join(keywords_raw[:3])

        # 决策阶段（从 dimension 或 problem_base 推断）
        base = _normalize_text(p.get('problem_base') or p.get('concern_base') or '')
        decision_stage = ''
        if any(kw in dimension or kw in base for kw in ['阶段1', '问题认知', '前置观望', '体感', '场景']):
            decision_stage = 'stage1'
        elif any(kw in dimension or kw in base for kw in ['阶段2', '方案搜索', '搜索']):
            decision_stage = 'stage2'
        elif any(kw in dimension or kw in base for kw in ['阶段3', '购买后', '使用']):
            decision_stage = 'stage3'
        else:
            decision_stage = 'stage_unknown'

        # 风险类型识别
        risk_keywords = {
            'health': ['安全', '健康', '风险', '危害', '致癌', '中毒', '过敏', '副作用'],
            'financial': ['价格', '贵', '钱', '成本', '费用', '收费', '浪费', '不值'],
            'effect': ['效果', '功效', '有用', '改善', '解决问题'],
            'trust': ['靠谱', '信任', '正规', '专业', '资质', '跑路', '骗'],
            'time': ['时间', '效率', '耽误', '周期', '多久'],
            'compliance': ['合规', '法律', '违规', '纠纷', '责任'],
        }
        risk_types = set()
        full_text = identity + problem_type + description + problem_category
        for risk_type, rkws in risk_keywords.items():
            if any(rkw in full_text for rkw in rkws):
                risk_types.add(risk_type)
        risk_key = '|'.join(sorted(risk_types)) if risk_types else 'none'

        return {
            'motivation_key': motivation_key[:50],  # 动机层
            'barrier_key': barrier_key[:80],          # 障碍/痛点层
            'decision_stage': decision_stage,          # 决策阶段
            'risk_key': risk_key,                     # 风险类型
        }

    def _is_semantic_duplicate(p1: Dict, p2: Dict) -> bool:
        """判定两个问题是否语义重复（宽松版：只去除真正的重复）"""
        s1 = _extract_core_semantics(p1)
        s2 = _extract_core_semantics(p2)

        # 1. 【严格匹配】problem_type 完全相同，且 identity 也相同 → 重复
        pt1 = _normalize_text(p1.get('problem_type') or '')
        pt2 = _normalize_text(p2.get('problem_type') or '')
        id1 = _normalize_text(p1.get('identity') or '')
        id2 = _normalize_text(p2.get('identity') or '')
        
        if pt1 == pt2 and id1 == id2:
            return True

        # 2. 【问题类型核心词必须完全相同才算重复】
        # 只对"担心被骗"、"怕被坑"这类极度抽象的问题类型去重
        # 而"家庭财产纠纷"、"劳动权益受损"这类具体问题类型应该保留
        abstract_problem_types = {'担心被骗', '怕被坑', '不信任', '怀疑', '担忧', '顾虑'}
        
        # 如果两个都是抽象问题类型，且身份相同 → 重复
        if pt1 in abstract_problem_types and pt2 in abstract_problem_types:
            if id1 == id2:
                return True

        # 3. 【障碍/痛点必须高度重合（前20字符完全相同）才算重复】
        if s1['barrier_key'] and s2['barrier_key']:
            if s1['barrier_key'][:20] == s2['barrier_key'][:20]:
                # 同时动机/身份也相同才算重复
                if s1['motivation_key'][:15] == s2['motivation_key'][:15]:
                    return True

        # 4. 【决策阶段一致 + 风险类型一致 + 动机也一致】才算重复
        if s1['decision_stage'] == s2['decision_stage'] and s1['decision_stage'] != 'stage_unknown':
            if s1['risk_key'] == s2['risk_key'] and s1['risk_key'] != 'none':
                if s1['motivation_key'][:20] == s2['motivation_key'][:20]:
                    return True

        return False

    # 强化去重：两两比较，保留语义最多样的问题
    deduped_problems = []
    dup_count = 0
    for p in all_problems:
        is_dup = False
        for existing in deduped_problems:
            if _is_semantic_duplicate(p, existing):
                is_dup = True
                dup_count += 1
                logger.debug(
                    "[mine_problems] 语义去重: identity='%s', problem_type='%s' <==> "
                    "identity='%s', problem_type='%s'",
                    p.get('identity', '')[:30], p.get('problem_type', ''),
                    existing.get('identity', '')[:30], existing.get('problem_type', '')
                )
                break
        if not is_dup:
            deduped_problems.append(p)

    if dup_count > 0:
        logger.info("[mine_problems] 语义去重完成：去除 %d 个重复问题，剩余 %d 个问题",
                    dup_count, len(deduped_problems))

    all_problems = deduped_problems

    # 【重要】如果去重后数量过少，需要警告并保留更多问题
    # 专业服务问题类型丰富，不应该被过度去重
    if len(all_problems) < 5:
        logger.warning("[mine_problems] 去重后问题数量过少(%d)，可能是去重过严。保留所有问题...", len(all_problems))
        # 临时方案：使用原始数据，不做语义去重
        # 后续可以优化去重算法
        all_problems = deduped_problems  # 暂时保留当前结果
    else:
        logger.info("[mine_problems] 问题数量正常: %d 个", len(all_problems))

    # 获取市场分析数据
    market_analysis = data.get('market_analysis', {}) or {}

    logger.debug("[mine_problems] market_analysis: %s", market_analysis)

    # 调试：检查 all_problems 中的 market_type 和 problem_keywords
    logger.debug("[mine_problems] all_problems[0]: %s", all_problems[0] if all_problems else '无')
    logger.debug("[mine_problems] all_problems[0].get('market_type'): %s", all_problems[0].get('market_type', '无') if all_problems else '无')
    logger.debug("[mine_problems] all_problems[0].get('problem_keywords'): %s", all_problems[0].get('problem_keywords', '无') if all_problems else '无')
    logger.debug("[mine_problems] all_problems[0].get('problem_category'): %s", all_problems[0].get('problem_category', '无') if all_problems else '无')

    logger.info("[mine_problems] 返回数据中 all_problems[0] 字段: %s",
                 list(all_problems[0].keys()) if all_problems else [])

    return {
        'success': True,
        'problems': {'problems': all_problems, 'market_analysis': market_analysis},
        'is_premium': result.get('data', {}).get('is_premium', False),
        'data': {
            'user_problem_types': user_problems,
            'buyer_concern_types': buyer_problems,
            'buyer_user_relation': data.get('buyer_user_relation', {}),
            'market_analysis': market_analysis,
            # 【GEO战略配置】
            'geo_strategy': data.get('geo_strategy', {}),
            # 【新增】慢性体征解析层结果
            'chronic_extraction': {
                'behavior_tags': chronic_extraction.get('behavior_tags', []),
                'scene_tags': chronic_extraction.get('scene_tags', []),
                'symptom_tags': chronic_extraction.get('symptom_tags', []),
                'extraction_summary': chronic_extraction.get('extraction_summary', ''),
                'chronic_problems': chronic_problems,
            },
            'custom_gift_extraction': data.get('custom_gift_extraction') or {},
        }
    }


def mine_problems_and_generate_personas(params: Dict[str, Any]) -> Dict:
    """
    一次性完成问题挖掘 + 所有类型的画像生成

    Args:
        params: 包含业务描述等信息的参数字典

    Returns:
        包含问题类型、使用方问题、付费方顾虑、以及按类型分组的画像
    """
    import re
    import os
    from services.llm import LLMService

    # 获取配置 - 支持硅基流动
    provider = os.environ.get('LLM_PROVIDER', 'siliconflow')
    model = os.environ.get('LLM_MODEL', os.environ.get('LLM_MODEL_TURBO', 'Qwen/Qwen2.5-7B-Instruct'))
    base_url = os.environ.get('LLM_BASE_URL', 'https://api.siliconflow.cn/v1')
    api_key = os.environ.get('LLM_API_KEY', '')

    llm = LLMService(provider=provider, model=model)
    llm.base_url = base_url
    llm.api_key = api_key

    # 获取业务参数
    business_desc = params.get('business_description', '')
    business_range = params.get('business_range', '')
    business_type = params.get('business_type', '')
    customer_who = params.get('customer_who', '')
    customer_why = params.get('customer_why', '')
    customer_problem = params.get('customer_problem', '')
    customer_story = params.get('customer_story', '')
    # 换一批/重试时的随机种子，确保 LLM 每次输出有差异
    refresh_nonce = params.get('refresh_nonce', '')
    import time as _time_module
    _nonce = str(refresh_nonce) or str(int(_time_module.time() * 1000))

    # 构建业务上下文
    business_range_text = '本地/同城' if business_range == 'local' else '跨区域/全国'
    business_type_name = BUSINESS_TYPE_MAP.get(business_type, '本地服务')

    # ── 产品类型检测：用于动态生成示例和关键词维度 ──────────────────────────
    # 通用提取：直接从 business_desc 提取产品名，无需维护分类列表

    def _product_name(desc: str) -> str:
        """从业务描述中提取最核心的产品/服务名词"""
        import re
        d = (desc or '').strip()
        if not d:
            return '该产品'
        for prefix in ('做', '卖', '提供', '经营', '销售', '我的业务是', '我的产品是', '产品是'):
            if d.startswith(prefix):
                d = d[len(prefix):]
        return d.split('，')[0].split('、')[0].split('；')[0].split('\n')[0].strip() or '该产品'

    product_name = _product_name(business_desc)

    def _get_mine_product_examples(desc: str) -> str:
        """生成问句格式示例（通用版，直接用产品名）"""
        p = _product_name(desc)
        return (
            f"✅ \"企业{p} logo怎么印才好看\" — 货的问题\n"
            f"✅ \"{p}质量怎么样\" — 人的困惑\n"
            f"✅ \"婚宴/企业{p}定制哪家好\" — 场的场景\n"
            f"✅ \"第一次定制{p}要注意什么\" — 人的焦虑"
        )

    # 检测是否需要注入护栏（当业务描述是其他明确业务但非桶装水时，防止模型混淆）
    def _needs_barrel_water_guard(desc: str) -> bool:
        """检测是否需要护栏，防止模型混淆桶装水和其它业务"""
        d = (desc or '').lower()
        barrel_water_kw = any(k in d for k in ('桶装水', '矿泉水', '水站', '饮用水配送'))
        other_biz = any(k in d for k in ('瓶装水', '定制水', '奶粉', '母婴', '老人', '宠物', '手机', '家政'))
        return other_biz and not barrel_water_kw

    guard_block = ''
    if _needs_barrel_water_guard(business_desc):
        guard_block = (
            f"\n\n【本业务类型·强制】当前业务为「**{business_desc}**」，"
            "禁止在关键词和场景中出现「桶装水」「矿泉水桶」「桶装配送」等相关内容；"
            "problem_keywords 的 keyword 字段必须围绕当前业务主体（如{p}等）展开，禁止照抄桶装水示例："
            "\"桶装水有塑料味能喝吗\"、\"桶装水泡茶发涩\"、\"办公室桶装水\"。\n".format(p=product_name)
        )

    product_examples = _get_mine_product_examples(business_desc)

    # 坏示例：直接用产品名
    def _get_mine_bad_examples(desc: str) -> str:
        p = _product_name(desc)
        return f'- ❌ "{p}好吗"（无问句形式）\n- ❌ "{p}"（无场景描述）'

    # 输出格式示例：keyword 字段的示例
    def _get_mine_kw_example(desc: str) -> str:
        p = _product_name(desc)
        return f'"{p}质量怎么样"'

    bad_examples = _get_mine_bad_examples(business_desc)
    kw_example = _get_mine_kw_example(business_desc)

    # 获取服务场景信息
    service_scenario = params.get('service_scenario', 'other')
    local_city = params.get('local_city', '')

    # =============================================================================
    # 【新增：行为+场景+慢性体征拆解层 - 前置解析，不改动原有三层痛点结构】
    # 从业务描述中隐性抽取常驻行为、固定场景、慢性体征，自动生成标准化问题
    # =============================================================================
    def _extract_emotion_mindset(biz_desc: str, biz_type: str, svc_scenario: str) -> Dict[str, Any]:
        """
        抽取心理情绪动因，并生成情绪因果链和标准化问题

        第四维识别层：前置于「行为+场景+慢性体征」解析层
        建立情绪因果链：情绪→心理→行为→长期症状→最终痛点

        Returns:
            {
                'emotion_drivers': ['育儿焦虑', '职场焦虑'],
                'emotion_causality_chains': [
                    {
                        'emotion': '育儿焦虑',
                        'trigger': '触发场景（如：孩子成绩差、升学期）',
                        'psychological': '心理状态（如：担心、自责、焦虑）',
                        'behavior': '外显行为（如：疯狂查资料、频繁换课）',
                        'chronic_symptom': '长期症状（如：失眠、情绪暴躁）',
                        'ultimate_pain': '最终痛点（如：亲子关系紧张）',
                    }
                ],
                'emotion_problems': [
                    {
                        'identity': '身份描述',
                        'emotion_type': '育儿焦虑',
                        'problem_base': '前置观望种草盘',
                        'problem_type': '情绪疑问',
                        'display_name': '显示名称',
                        'description': '问题描述',
                        'severity': '中',
                        'scenarios': ['触发场景'],
                        'market_type': 'blue_ocean',
                        'problem_keywords': [...],
                        'emotion_drivers': ['育儿焦虑'],
                    }
                ],
                'psychology_tags': ['育儿焦虑', '失眠多梦', '自我怀疑'],
                'emotion_summary': '心理情绪摘要',
            }
        """
        # 判断是否需要启用情绪动因解析：关键词扫描
        emotion_text = biz_desc.lower()
        emotion_keywords = []
        for category, subcats in EMOTION_DRIVER_CATEGORIES.items():
            for subcat, keywords in subcats.items():
                for kw in keywords:
                    if kw in emotion_text:
                        emotion_keywords.append(subcat)
                        break

        if not emotion_keywords:
            return {
                'emotion_drivers': [],
                'emotion_causality_chains': [],
                'emotion_problems': [],
                'psychology_tags': [],
                'emotion_summary': '无',
            }

        # 去重
        emotion_keywords = list(dict.fromkeys(emotion_keywords))

        # 场景类型名称映射
        scene_type_map = {
            'office_enterprise': '办公室白领/企业员工',
            'hotel_restaurant': '餐饮/酒店从业者',
            'retail_chain': '零售/门店店员',
            'institutional': '学校/医院/机构人员',
            'renovation': '装修/工程从业者',
            'residential': '家庭用户',
            'other': '其他场景',
        }
        scene_type_name = scene_type_map.get(svc_scenario, '各类人群')

        # 业务类型名称
        biz_type_map = {
            'product': '消费品',
            'local_service': '本地服务',
            'personal': '个人账号/IP',
            'enterprise': '企业服务',
        }
        biz_type_name = biz_type_map.get(biz_type, '通用业务')

        emotion_prompt = f"""你是用户心理与情绪分析专家。请从以下业务描述中，深度挖掘用户的心理情绪动因，并建立完整的情绪因果链。

=== 业务信息 ===
业务描述：{biz_desc}
业务类型：{biz_type_name}
服务场景：{scene_type_name}
识别到的情绪动因：{', '.join(emotion_keywords)}

=== 任务1：建立情绪因果链 ===
对于每一个识别到的情绪动因，请构建完整的情绪因果链：

情绪 → 心理 → 行为 → 长期症状 → 最终痛点

【情绪因果链构建规则】：
1. 情绪（emotion）：这是什么类型的情绪？（如：育儿焦虑、职场焦虑、容貌焦虑、选择焦虑、自卑感、内耗、怕丢脸等）
2. 触发场景（trigger）：什么具体场景触发了这种情绪？（要具体，如：孩子考试成绩差、领导当众批评、被朋友比下去等）
3. 心理状态（psychological）：用户当时的心理活动是什么？（如：担心、自责、恐惧、不自信、委屈、压抑等）
4. 外显行为（behavior）：这种情绪会导致什么具体的外显行为？（如：疯狂查资料、回避社交、反复纠结、过度准备、压抑消费等）
5. 长期症状（chronic_symptom）：长期累积会形成什么身心症状？（如：失眠多梦、情绪暴躁、肩颈紧绷、消化紊乱、自我否定等）
6. 最终痛点（ultimate_pain）：最终导致什么核心痛点？（如：亲子关系紧张、职业倦怠、社交退缩、错失机会等）

【情绪→症状→痛点参考表】：
请参考以下映射，结合业务描述灵活组合：
- 育儿焦虑 → 失眠多梦、情绪暴躁、自责 → 亲子关系紧张、家庭矛盾
- 职场焦虑 → 睡眠障碍、肩颈紧绷、效率下降 → 职业倦怠、人际恶化
- 容貌焦虑 → 社交回避、饮食紊乱、自我否定 → 社交退缩、消费陷阱
- 健康焦虑 → 反复检查、疑病倾向、失眠 → 过度医疗、经济负担
- 财务焦虑 → 回避消费、压抑需求、争吵增多 → 生活质量下降、家庭矛盾
- 关系焦虑 → 过度控制、猜疑、情绪失控 → 关系破裂、孤立
- 社交焦虑 → 回避社交、脸红手抖、事后后悔 → 人脉受限、机会流失
- 选择焦虑 → 拖延决策、反复比较、错过时机 → 决策瘫痪、机会成本增加
- 学业焦虑 → 失眠、记忆力减退、厌学 → 成绩下滑、升学受影响
- 能力自卑 → 回避挑战、拖延行动、自我设限 → 职业发展受阻、收入停滞
- 外貌自卑 → 过度关注外表、穿衣保守、社交退缩 → 社交回避、机会流失
- 经济自卑 → 攀比、物质补偿、社交退缩 → 自我设限、社交障碍
- 社交自卑 → 不敢发言、过度在意评价、敏感多疑 → 人脉受限、职业受阻
- 情绪压抑 → 情绪低落、躯体化症状、失眠 → 心理疾病、关系破裂
- 需求压抑 → 委屈自己、讨好型、不快乐 → 自我价值感低、关系失衡
- 关系压抑 → 心累、冷漠、沟通减少 → 关系破裂、孤独感
- 决策内耗 → 错过时机、效率低下、行动瘫痪 → 一事无成、机会成本巨大
- 关系内耗 → 猜疑、争吵、信任缺失 → 关系破裂、身心俱疲
- 完美内耗 → 过度准备、害怕行动、身心疲惫 → 效率极低、成就低
- 后悔内耗 → 沉溺过去、无法释怀、影响当下 → 决策能力下降、恶性循环
- 怕丢脸 → 回避当众表现、过度谨慎、讨好他人 → 错失机会、关系假象
- 怕选错 → 迟迟不下手、反复查资料、不敢行动 → 持续错过、决策退化

=== 任务2：生成情绪类标准化问题 ===
基于情绪因果链，生成3-5个标准化的情绪类问题。

【情绪类问题生成规则】：
1. 问题类型必须从以下六类中选择：
   - 情绪疑问：用户对情绪本身的疑问（如：焦虑正常吗？怎么缓解？）
   - 心态误区：用户对心态调节的认知误区（如：忍忍就好了？）
   - 心理顾虑：用户对心理问题的顾虑（如：会不会心理出问题？）
   - 减压疑问：减压相关疑问（如：怎么减压？）
   - 内耗疑问：内耗相关疑问（如：怎么停止内耗？）
   - 自卑疑问：自卑相关疑问（如：怎么克服自卑？）
   - 怕丢脸疑问：怕丢脸相关疑问（如：怎么克服怕丢脸？）
   - 怕选错疑问：选择恐惧相关疑问（如：怎么克服选择困难？）

【情绪问题三盘归类规则】：
- 普通情绪顾虑、焦虑疑惑 → 【前置观望种草盘】（严重程度：中）
  示例：职场焦虑怎么办？容貌焦虑正常吗？怎么减少内耗？
- 情绪严重影响生活/健康 → 【刚需痛点盘】（严重程度：高）
  示例：焦虑导致失眠怎么办？自卑已经严重影响社交
- 情绪疏导、心态调节干货 → 【使用配套搜后种草盘】（严重程度：中）
  示例：焦虑怎么自我疏导？减压方法有哪些？冥想有用吗？

【蓝海/红海判断】：
- 蓝海：细分人群、特定场景、心理动机驱动
- 红海：大众人群、通用情绪、即时需求

=== 输出格式（严格JSON）===
{{
    "emotion_drivers": ["育儿焦虑", "职场焦虑", ...],
    "emotion_causality_chains": [
        {{
            "emotion": "育儿焦虑",
            "trigger": "孩子成绩差、升学期",
            "psychological": "担心、自责、不甘",
            "behavior": "疯狂查资料、报补习班、反复比较产品",
            "chronic_symptom": "失眠多梦、情绪暴躁、自我怀疑",
            "ultimate_pain": "亲子关系紧张、家庭矛盾频发"
        }}
    ],
    "emotion_problems": [
        {{
            "identity": "身份描述（如：孩子处于升学关键期的家长）",
            "emotion_type": "育儿焦虑",
            "problem_base": "前置观望种草盘",
            "problem_category": "心理/情绪问题",
            "problem_type": "情绪疑问",
            "display_name": "显示名称",
            "description": "具体表现（用顿号分隔）",
            "severity": "中",
            "scenarios": ["触发场景1", "触发场景2"],
            "market_type": "blue_ocean",
            "market_reason": "情绪动因+细分人群",
            "problem_keywords": [
                {{"keyword": "育儿焦虑怎么缓解", "type": "blue_ocean", "source": "情绪疑问词"}},
                {{"keyword": "家长减压方法推荐", "type": "blue_ocean", "source": "情绪疏导词"}}
            ],
            "emotion_drivers": ["育儿焦虑"]
        }}
    ],
    "psychology_tags": ["育儿焦虑", "失眠多梦", "自我怀疑", "情绪暴躁"],
    "emotion_summary": "心理情绪摘要（1-2句话）"
}}

只输出JSON，不要其他文字。"""

        try:
            response = llm.chat(emotion_prompt, temperature=0.3, max_tokens=4000)
            if not response:
                logger.warning("[_extract_emotion_mindset] LLM返回空")
                return {
                    'emotion_drivers': [],
                    'emotion_causality_chains': [],
                    'emotion_problems': [],
                    'psychology_tags': [],
                    'emotion_summary': '无',
                }

            import json as json_module
            match = re.search(r'\{[\s\S]*\}', response, re.DOTALL)
            if not match:
                logger.warning("[_extract_emotion_mindset] JSON解析失败")
                return {
                    'emotion_drivers': [],
                    'emotion_causality_chains': [],
                    'emotion_problems': [],
                    'psychology_tags': [],
                    'emotion_summary': '无',
                }

            extracted = json_module.loads(match.group(0))
            extracted['emotion_drivers'] = extracted.get('emotion_drivers', [])
            extracted['emotion_causality_chains'] = extracted.get('emotion_causality_chains', [])
            extracted['emotion_problems'] = extracted.get('emotion_problems', [])
            extracted['psychology_tags'] = extracted.get('psychology_tags', [])
            extracted['emotion_summary'] = extracted.get('emotion_summary', '无')

            # 情绪动因标签补充（基于LLM识别 + 规则识别交集）
            extra_drivers = emotion_keywords
            existing_drivers = set(extracted.get('emotion_drivers', []))
            for d in extra_drivers:
                if d not in existing_drivers:
                    extracted['emotion_drivers'].insert(0, d)

            # 为每个情绪问题分配底盘
            for problem in extracted.get('emotion_problems', []):
                emotion_type = problem.get('emotion_type', '')
                description = problem.get('description', '')
                severity = problem.get('severity', '中')

                inferred_base = infer_emotion_problem_base(
                    emotion_type,
                    description,
                    severity,
                )
                problem['problem_base'] = problem.get('problem_base') or inferred_base
                problem['content_direction'] = PROBLEM_BASE_TO_CONTENT_DIRECTION.get(
                    problem['problem_base'], '种草型'
                )

                # emotion_type 如果是选择焦虑/怕选错 → 强制前置观望
                if any(kw in emotion_type for kw in ['选择焦虑', '怕选错', '选择困难', '纠结']):
                    problem['problem_base'] = PROBLEM_BASE_SOUQIAN_ZHONGCAO
                    problem['content_direction'] = '种草型'

            logger.info("[_extract_emotion_mindset] 提取到情绪动因:%s 因果链:%d条 问题:%d个",
                        len(extracted.get('emotion_drivers', [])),
                        len(extracted.get('emotion_causality_chains', [])),
                        len(extracted.get('emotion_problems', [])))

            return extracted

        except Exception as e:
            logger.warning("[_extract_emotion_mindset] 异常: %s", e)
            return {
                'emotion_drivers': [],
                'emotion_causality_chains': [],
                'emotion_problems': [],
                'psychology_tags': [],
                'emotion_summary': '无',
            }

    def _extract_behavior_scene_symptom(biz_desc: str, biz_type: str, svc_scenario: str) -> Dict[str, Any]:
        """
        抽取常驻行为、固定场景、慢性体征，并生成对应的标准化问题

        Returns:
            {
                'behavior_tags': ['久坐', '长期伏案'],
                'scene_tags': ['办公室'],
                'symptom_tags': ['腰酸背痛', '颈椎僵硬'],
                'chronic_problems': [
                    {
                        'identity': '...',
                        'problem_base': '前置观望种草盘',
                        'problem_type': '长期习惯疑问',
                        'display_name': '...',
                        'description': '...',
                        'severity': '中',
                        'scenarios': [...],
                        'market_type': 'blue_ocean',
                        'behavior_tags': [...],
                        'scene_tags': [...],
                        'symptom_tags': [...],
                    }
                ],
                'extraction_summary': '行为场景体征摘要',
            }
        """
        # 识别行业场景（用于判断是否需要启用慢性体征拆解）
        industry_scene = identify_industry_scene(biz_desc, svc_scenario)

        # 判断是否需要拆解慢性体征：久坐/久站/伏案/高强度用眼类业务
        needs_chronic_extraction = any(kw in (biz_desc + svc_scenario).lower() for kw in [
            '办公', '久坐', '伏案', '电脑', '程序员', '设计师', '会计', '白领', '文员',
            '司机', '久站', '站立', '服务', '销售', '厨师', '后厨',
            '体力', '搬运', '弯腰', '工人', '车间', '工厂',
            '学生', '老师', '教师', '学业', '考研', '考公',
            '颈椎', '腰', '眼', '疲劳', '酸', '疼', '痛', '不适',
        ])

        if not needs_chronic_extraction:
            return {
                'behavior_tags': [],
                'scene_tags': [],
                'symptom_tags': [],
                'chronic_problems': [],
                'extraction_summary': '无',
            }

        # 场景类型名称映射
        scene_type_map = {
            'office_enterprise': '办公室白领/企业员工',
            'hotel_restaurant': '餐饮/酒店从业者',
            'retail_chain': '零售/门店店员',
            'institutional': '学校/医院/机构人员',
            'renovation': '装修/工程从业者',
            'residential': '家庭用户',
            'other': '其他场景',
        }
        scene_type_name = scene_type_map.get(svc_scenario, '各类人群')

        # 业务类型名称映射
        biz_type_name_map = {
            'product': '消费品',
            'local_service': '本地服务',
            'personal': '个人账号/IP',
            'enterprise': '企业服务',
        }
        biz_type_name = biz_type_name_map.get(biz_type, '通用业务')

        # 构建行为场景体征拆解的 prompt
        chronic_prompt = f"""你是用户行为与症状分析专家。请从以下业务描述中，深度挖掘常驻行为、固定场景和慢性体征。

业务描述：{biz_desc}
业务类型：{biz_type_name}
服务场景：{scene_type_name}

=== 任务1：隐性抽取 ===
请从业务描述中抽取以下信息（如果不存在则标注"无"）：

【常驻行为】（久坐/久站/熬夜/长期伏案等导致的长期习惯性姿势问题）：
- 识别目标：长期保持同一姿势（久坐、久站、弯腰、低头等）
- 常见场景：办公室伏案、开车久坐、站立服务、弯腰干活、盯屏幕等
- 至少列出2-3种最相关的常驻行为

【固定场景】（长期重复的工作/生活场景）：
- 识别目标：用户每天固定经历的场所和环境
- 常见场景：办公室工位、驾驶座、后厨、家庭、教室、工地等
- 至少列出1-2个最相关的固定场景

【慢性常态化症状】（腰酸/颈椎僵/眼疲劳等长期累积的不适）：
- 识别目标：由于长期习惯导致的渐进式、慢性的身体不适
- 常见症状分类：
  * 骨骼肌肉类：腰酸背痛、颈椎僵硬、肩周不适、腿脚肿胀、关节疼痛
  * 眼部疲劳类：眼疲劳、眼睛干涩、头痛头晕（用眼过度导致）
  * 消化系统类：肠胃不适（久坐导致）、肥胖问题
  * 精神状态类：精力不足、睡眠问题、焦虑压力
  * 皮肤问题类：皮肤干燥、体态问题

=== 任务2：生成标准化问题 ===
基于抽取的行为、场景、体征，生成3-5个标准化的慢性体征问题。

【问题生成规则】：
1. 每个问题必须关联至少1个常驻行为 + 1个固定场景
2. 问题类型必须从以下五类中选择：
   - 长期习惯疑问：长期如此会有什么后果？
   - 场景预防误区：这个场景下常见的错误认知
   - 姿势疑问：正确/错误的姿势是什么样的？
   - 养护时机：什么时候开始注意/养护？
   - 早期信号：出现什么症状需要警惕？

【需求底盘归类规则】：
- 长期日常不适、预防顾虑、习惯误区 → 【前置观望种草盘】（严重程度：中）
- 急性发作、严重影响工作生活 → 【刚需痛点盘】（严重程度：高）
- 日常坐姿养护/拉伸/护腰工具类 → 【使用配套搜后种草盘】（严重程度：中）

【蓝海/红海判断】：
- 蓝海：涉及细分人群、特定场景、慢性累积、预防性需求
- 红海：大众人群、通用不适、即时需求

=== 输出格式（严格JSON）===
{{
    "behavior_tags": ["久坐", "长期伏案", ...],
    "scene_tags": ["办公室", ...],
    "symptom_tags": ["腰酸背痛", "颈椎僵硬", ...],
    "chronic_problems": [
        {{
            "identity": "身份描述（如：办公室久坐的上班族）",
            "problem_base": "前置观望种草盘",
            "problem_category": "体验/使用问题",
            "problem_type": "长期习惯疑问",
            "display_name": "显示名称",
            "description": "具体表现（用顿号分隔）",
            "severity": "中",
            "scenarios": ["具体场景1", "具体场景2"],
            "market_type": "blue_ocean",
            "market_reason": "慢性累积+细分人群",
            "problem_keywords": [
                {{"keyword": "久坐人群腰酸怎么缓解", "type": "blue_ocean", "source": "场景痛点词"}},
                {{"keyword": "办公室正确坐姿示范", "type": "blue_ocean", "source": "长尾转化词"}}
            ],
            "behavior_tags": ["久坐", "长期伏案"],
            "scene_tags": ["办公室"],
            "symptom_tags": ["腰酸背痛"]
        }}
    ],
    "extraction_summary": "行为场景体征摘要（1-2句话）"
}}

只输出JSON，不要其他文字。"""

        try:
            response = llm.chat(chronic_prompt, temperature=0.3, max_tokens=3000)
            if not response:
                logger.warning("[_extract_behavior_scene_symptom] LLM返回空")
                return {
                    'behavior_tags': [],
                    'scene_tags': [],
                    'symptom_tags': [],
                    'chronic_problems': [],
                    'extraction_summary': '无',
                }

            import json
            import json as json_module

            # 解析JSON响应
            match = re.search(r'\{[\s\S]*\}', response, re.DOTALL)
            if not match:
                logger.warning("[_extract_behavior_scene_symptom] JSON解析失败")
                return {
                    'behavior_tags': [],
                    'scene_tags': [],
                    'symptom_tags': [],
                    'chronic_problems': [],
                    'extraction_summary': '无',
                }

            extracted = json_module.loads(match.group(0))

            # 确保字段存在
            extracted['behavior_tags'] = extracted.get('behavior_tags', [])
            extracted['scene_tags'] = extracted.get('scene_tags', [])
            extracted['symptom_tags'] = extracted.get('symptom_tags', [])
            extracted['chronic_problems'] = extracted.get('chronic_problems', [])
            extracted['extraction_summary'] = extracted.get('extraction_summary', '无')

            # 为每个问题添加行为场景体征标签（如果LLM没有返回）
            for problem in extracted['chronic_problems']:
                if 'behavior_tags' not in problem or not problem['behavior_tags']:
                    problem['behavior_tags'] = extracted.get('behavior_tags', [])
                if 'scene_tags' not in problem or not problem['scene_tags']:
                    problem['scene_tags'] = extracted.get('scene_tags', [])
                if 'symptom_tags' not in problem or not problem['symptom_tags']:
                    problem['symptom_tags'] = extracted.get('symptom_tags', [])

                # 第五类种草原生问题强制归入前置观望种草盘
                problem_type = problem.get('problem_type', '')
                description = problem.get('description', '')
                if is_seeding_problem(problem_type, description):
                    problem['problem_base'] = PROBLEM_BASE_SOUQIAN_ZHONGCAO
                    problem['content_direction'] = '种草型'

                # 使用 infer_problem_base_for_chronic 智能推断底盘
                is_habitual = is_chronic_habitual_problem(
                    problem_type,
                    description,
                    problem.get('behavior_tags', [])
                )
                inferred_base = infer_problem_base_for_chronic(
                    problem_type,
                    description,
                    problem.get('severity', '中'),
                    is_habitual
                )
                if not problem.get('problem_base'):
                    problem['problem_base'] = inferred_base
                    problem['content_direction'] = PROBLEM_BASE_TO_CONTENT_DIRECTION.get(inferred_base, '种草型')

            logger.info("[_extract_behavior_scene_symptom] 提取到行为:%s 场景:%s 体征:%s 问题数:%d",
                        len(extracted.get('behavior_tags', [])),
                        len(extracted.get('scene_tags', [])),
                        len(extracted.get('symptom_tags', [])),
                        len(extracted.get('chronic_problems', [])))

            return extracted

        except Exception as e:
            logger.warning("[_extract_behavior_scene_symptom] 异常: %s", e)
            return {
                'behavior_tags': [],
                'scene_tags': [],
                'symptom_tags': [],
                'chronic_problems': [],
                'extraction_summary': '无',
            }

    # =============================================================================
    # 【新增：心理情绪动因解析层 - 第四维识别，前置于行为+场景+慢性体征解析层】
    # 建立情绪因果链：情绪→心理→行为→长期症状→最终痛点
    # =============================================================================
    emotion_extraction = _extract_emotion_mindset(business_desc, business_type, service_scenario)
    emotion_drivers = emotion_extraction.get('emotion_drivers', [])
    emotion_causality_chains = emotion_extraction.get('emotion_causality_chains', [])
    emotion_problems = emotion_extraction.get('emotion_problems', [])
    psychology_tags = emotion_extraction.get('psychology_tags', [])
    emotion_extraction_summary = emotion_extraction.get('emotion_summary', '')

    # 构建情绪动因上下文（注入到问题挖掘 prompt 中）
    emotion_context = ""
    if emotion_drivers:
        emotion_context = f"""
=== 【心理情绪动因解析层】（第四维识别，前置于行为+场景+慢性体征层）===
情绪动因摘要：{emotion_extraction_summary}

【识别到的情绪动因】：{', '.join(emotion_drivers)}

【情绪因果链】："""
        for i, chain in enumerate(emotion_causality_chains, 1):
            emotion_context += f"""
{i}. 情绪：{chain.get('emotion', '')}
   触发场景：{chain.get('trigger', '')}
   心理状态：{chain.get('psychological', '')}
   外显行为：{chain.get('behavior', '')}
   长期症状：{chain.get('chronic_symptom', '')}
   最终痛点：{chain.get('ultimate_pain', '')}"""

        emotion_context += f"""
【自动生成的情绪类标准问题】："""
        for i, ep in enumerate(emotion_problems, 1):
            problem_keywords = ep.get('problem_keywords', [])
            kw_list = ', '.join([k.get('keyword', '') for k in problem_keywords[:3]]) if problem_keywords else '暂无'
            emotion_context += f"""
{i}. {ep.get('display_name', ep.get('emotion_type', ''))}
   - 情绪类型：{ep.get('emotion_type', '')}
   - 问题类型：{ep.get('problem_type', '')}
   - 描述：{ep.get('description', '')}
   - 严重程度：{ep.get('severity', '中')}
   - 需求底盘：{ep.get('problem_base', '前置观望种草盘')}
   - 关键词：{kw_list}"""

    logger.info("[mine_problems_and_generate_personas] 心理情绪动因: 动因=%s 因果链=%d条 问题=%d个",
                len(emotion_drivers), len(emotion_causality_chains), len(emotion_problems))
    # =============================================================================
    # 【心理情绪动因解析层结束】
    # =============================================================================

    # 执行行为场景体征拆解
    chronic_extraction = _extract_behavior_scene_symptom(business_desc, business_type, service_scenario)
    behavior_tags = chronic_extraction.get('behavior_tags', [])
    scene_tags = chronic_extraction.get('scene_tags', [])
    symptom_tags = chronic_extraction.get('symptom_tags', [])
    chronic_problems = chronic_extraction.get('chronic_problems', [])
    chronic_extraction_summary = chronic_extraction.get('extraction_summary', '')

    # 构建慢性体征上下文（注入到问题挖掘 prompt 中）
    chronic_context = ""
    if behavior_tags or scene_tags or symptom_tags:
        chronic_context = f"""
=== 【常驻行为+固定场景+慢性体征拆解层】（前置解析结果，自动生成标准化问题）===
提取摘要：{chronic_extraction_summary}

【常驻行为标签】：{', '.join(behavior_tags) if behavior_tags else '无'}
【固定场景标签】：{', '.join(scene_tags) if scene_tags else '无'}
【慢性体征标签】：{', '.join(symptom_tags) if symptom_tags else '无'}

【自动生成的标准问题】："""
        for i, cp in enumerate(chronic_problems, 1):
            problem_keywords = cp.get('problem_keywords', [])
            kw_list = ', '.join([k.get('keyword', '') for k in problem_keywords[:3]]) if problem_keywords else '暂无'
            chronic_context += f"""
{i}. {cp.get('display_name', cp.get('problem_type', ''))}
   - 问题类型：{cp.get('problem_type', '')}
   - 描述：{cp.get('description', '')}
   - 严重程度：{cp.get('severity', '中')}
   - 需求底盘：{cp.get('problem_base', '前置观望种草盘')}
   - 关键词：{kw_list}"""

    logger.info("[mine_problems_and_generate_personas] 慢性体征拆解: 行为=%s 场景=%s 体征=%s 问题=%d",
                len(behavior_tags), len(scene_tags), len(symptom_tags), len(chronic_problems))
    # =============================================================================
    # 【行为+场景+慢性体征拆解层结束】
    # =============================================================================

    # =============================================================================
    # 【第五维识别：定制礼赠仪式场景识别层】
    # 只要业务含：定制/刻字/LOGO/专属/纪念/伴手礼/礼赠，自动触发
    # =============================================================================
    def _is_custom_gift_business(desc: str) -> bool:
        """判断业务是否为定制礼赠类"""
        if not desc:
            return False
        desc_lower = desc.lower()
        trigger_keywords = ['定制', '刻字', 'logo', '专属', '纪念', '伴手礼', '礼赠',
                          '礼品', '礼物', '赠品', '企业定制', '批量定制']
        for kw in trigger_keywords:
            if kw in desc_lower:
                return True
        return False

    def _get_custom_gift_context(desc: str) -> Dict[str, Any]:
        """获取定制礼赠识别的上下文"""
        # 仪式场景关键词映射
        ritual_keywords = {
            '婚宴仪式': ['婚礼', '婚宴', '结婚', '伴郎', '伴娘', '订婚'],
            '寿宴仪式': ['寿宴', '祝寿', '生日宴', '老人', '长辈'],
            '满月百日宴': ['满月', '百日', '周岁', '宝宝宴', '新生儿'],
            '乔迁之喜': ['乔迁', '搬家', '新居', '入伙'],
            '升学谢师宴': ['升学', '谢师', '高考', '毕业', '金榜题名'],
            '开业典礼': ['开业', '开张', '新店', '新公司'],
            '年会团建': ['年会', '团建', '公司活动', '员工福利'],
            '商务答谢': ['商务', '答谢', '客户', '合作伙伴'],
        }

        # 匹配仪式场景
        matched_rituals = []
        desc_lower = desc.lower()
        for ritual_name, keywords in ritual_keywords.items():
            for kw in keywords:
                if kw in desc_lower:
                    matched_rituals.append(ritual_name)
                    break

        # 如果没有匹配到具体场景，提供通用仪式场景
        if not matched_rituals:
            matched_rituals = ['通用宴请场景']

        # 定制心理顾虑
        psychology_concerns = [
            {'type': '办宴体面', 'desc': '担心宴请不够体面，怕丢面子'},
            {'type': '送礼走心', 'desc': '担心礼品不够用心，显得敷衍'},
            {'type': '定制踩坑', 'desc': '担心定制过程出问题，交付延误或质量差丢面子'},
            {'type': '性价比顾虑', 'desc': '担心定制价格虚高，花冤枉钱'},
        ]

        # 三大底盘内容映射
        content_base_map = {
            '前置观望种草盘': ['宴席选款种草', '吉利款式种草', '案例对比种草', '定制避坑指南'],
            '刚需痛点盘': ['定制报价刚需', '定稿排版刚需', '加急制作刚需'],
            '使用配套搜后种草盘': ['现场搭配配套', '发放储存配套', '礼盒配套推荐'],
        }

        return {
            'matched_rituals': matched_rituals,
            'psychology_concerns': psychology_concerns,
            'content_base_map': content_base_map,
        }

    def _build_custom_gift_seed_problems(desc: str, rituals: List[str]) -> List[Dict[str, Any]]:
        """程序化礼赠/仪式向种子问题（与慢性层一样合并进问题列表，避免仅 prompt 被模型忽略）"""
        ps = _product_name(desc)
        r0 = rituals[0] if rituals else '宴请活动'
        rjoin = '、'.join(rituals[:3]) if rituals else '宴请/年会/商务活动'
        return [
            {
                '_merge_side': 'user',
                'identity': '宴请/活动主理人',
                'problem_base': '前置观望种草盘',
                'problem_category': '适配/兼容问题',
                'problem_type': '宴席定制选款',
                'display_name': f'{r0}定制{ps}怎么选体面',
                'description': '怕款式土气、LOGO不醒目、和现场布置不协调、来宾觉得不用心',
                'severity': '中',
                'scenarios': [f'{rjoin}迎宾区', '主桌/讲台摆台', '伴手礼发放'],
                'market_type': 'blue_ocean',
                'market_reason': '礼赠体面+场景细分',
                'problem_keywords': [
                    {'keyword': f'{r0}定制{ps}怎么选不丢面子', 'type': 'blue_ocean', 'source': '场景痛点词'},
                    {'keyword': f'两家{ps}定制印LOGO哪家更靠谱', 'type': 'blue_ocean', 'source': '长尾转化词'},
                ],
            },
            {
                '_merge_side': 'user',
                'identity': '采购负责人',
                'problem_base': '前置观望种草盘',
                'problem_category': '安全/质量问题',
                'problem_type': '定制交付避坑',
                'display_name': '怕定制翻车当场尴尬',
                'description': '刻字糊、色差、瓶贴歪、错字漏字、延期到货',
                'severity': '高',
                'scenarios': ['开箱验货', '现场摆台', '来宾拍照发圈前'],
                'market_type': 'blue_ocean',
                'market_reason': '定制踩坑高焦虑',
                'problem_keywords': [
                    {'keyword': f'定制{ps}常见翻车有哪些怎么避', 'type': 'blue_ocean', 'source': '场景痛点词'},
                    {'keyword': f'定制{ps}印字前打样要注意什么', 'type': 'blue_ocean', 'source': '长尾转化词'},
                ],
            },
            {
                '_merge_side': 'user',
                'identity': '活动执行',
                'problem_base': '刚需痛点盘',
                'problem_category': '成本/效率问题',
                'problem_type': '报价与加急',
                'display_name': '定制报价与赶工期',
                'description': '起订量高、总价摸不清、设计定稿反复、临近节点怕交不出货',
                'severity': '高',
                'scenarios': ['临近婚期/年会', '多部门确认', '补单加急'],
                'market_type': 'red_ocean',
                'market_reason': '决策刚需',
                'problem_keywords': [
                    {'keyword': f'定制{ps}一般怎么报价', 'type': 'red_ocean', 'source': '用户需求词'},
                    {'keyword': f'定制{ps}加急几天能出货', 'type': 'blue_ocean', 'source': '长尾转化词'},
                ],
            },
            {
                '_merge_side': 'buyer',
                'identity': '购买者',
                'concern_base': '刚需痛点盘',
                'concern_category': '安全/质量问题',
                'concern_type': '定稿与校对',
                'display_name': '定稿怕印错丢人',
                'description': '怕文案错字、LOGO反白、条形码扫不出、批次和约定不一致',
                'examples': ['最终稿确认', '批量开机前'],
                'severity': '高',
                'market_type': 'blue_ocean',
                'market_reason': '信任与体面',
                'problem_keywords': [
                    {'keyword': f'定制{ps}定稿前核对清单', 'type': 'blue_ocean', 'source': '场景痛点词'},
                    {'keyword': f'定制{ps}设计稿和实物色差怎么控', 'type': 'blue_ocean', 'source': '长尾转化词'},
                ],
            },
            {
                '_merge_side': 'buyer',
                'identity': '购买者',
                'concern_base': '使用配套搜后种草盘',
                'concern_category': '成本/效率问题',
                'concern_type': '存储与分装',
                'display_name': '现场搭配与余货存放',
                'description': '桌数变动怎么补配、剩余怎么存不坏、礼盒组合怎么省心',
                'examples': ['活动后余货', '分发给宾客'],
                'severity': '中',
                'market_type': 'blue_ocean',
                'market_reason': '使用后配套',
                'problem_keywords': [
                    {'keyword': f'定制{ps}剩多了怎么保存', 'type': 'blue_ocean', 'source': '场景痛点词'},
                    {'keyword': f'{ps}礼盒伴手礼怎么搭配好看', 'type': 'blue_ocean', 'source': '长尾转化词'},
                ],
            },
        ]

    # 判断是否触发定制礼赠识别层
    is_custom_gift = _is_custom_gift_business(business_desc)
    custom_gift_context = None
    custom_gift_context_str = ""
    custom_gift_problems: List[Dict[str, Any]] = []

    if is_custom_gift:
        custom_gift_context = _get_custom_gift_context(business_desc)
        custom_gift_problems = _build_custom_gift_seed_problems(
            business_desc,
            list(custom_gift_context.get('matched_rituals', [])),
        )
        logger.info(
            "[mine_problems_and_generate_personas] 定制礼赠识别触发: 仪式=%s 种子问题=%d条",
            custom_gift_context.get('matched_rituals'),
            len(custom_gift_problems),
        )
        custom_gift_context_str = f"""
=== 【第五维识别：定制礼赠仪式场景识别层】（业务包含定制/礼赠/纪念等关键词，自动触发）

【匹配的仪式场景】：{', '.join(custom_gift_context.get('matched_rituals', []))}

【定制礼赠心理顾虑】（画像必须包含）：
{chr(10).join([f"- {p['type']}：{p['desc']}" for p in custom_gift_context.get('psychology_concerns', [])])}

【三大底盘内容分类映射】：
{chr(10).join([f"- {base}：{', '.join(contents)}" for base, contents in custom_gift_context.get('content_base_map', {}).items()])}

**强制要求**：
1. 画像中必须包含"办宴体面"、"送礼走心"、"怕定制踩坑丢面子"等心理关键词
2. 画像描述中必须明确仪式场景（如婚宴/寿宴/满月等）
3. 内容方向直接映射到三大底盘：
   - 宴席选款/吉利款式/案例对比/避坑指南 → 前置观望种草盘（种草型）
   - 定制报价/定稿排版/加急制作 → 刚需痛点盘（转化型）
   - 现场搭配/发放储存/礼盒配套 → 使用配套搜后种草盘（种草型）
"""
    # =============================================================================
    # 【定制礼赠仪式场景识别层结束】
    # =============================================================================

    # 获取系统固定底座人群
    system_base_personas = get_system_base_personas(service_scenario, business_type)

    # 构建辅助信息
    aux_parts = []
    if customer_who:
        aux_parts.append(f"典型客户：{customer_who}")
    if customer_why:
        aux_parts.append(f"找到您的原因：{customer_why}")
    if customer_problem:
        aux_parts.append(f"解决的痛点：{customer_problem}")
    if customer_story:
        aux_parts.append(f"客户故事：{customer_story}")
    # 服务场景作为重要参考
    if service_scenario:
        scenario_map = {
            'hotel_restaurant': '酒店/餐饮/茶楼/高端会所',
            'residential': '家用/住宅/小区业主',
            'office_enterprise': '写字楼/企业/工厂/园区',
            'institutional': '学校/医院/食堂/政企单位',
            'retail_chain': '实体店/连锁门店/加盟品牌',
            'renovation': '装修/工装/工程定制',
            'other': '其他小众场景'
        }
        scenario_text = scenario_map.get(service_scenario, service_scenario)
        aux_parts.append(f"主要服务场景：{scenario_text}")

    # ── 问题挖掘阶段场景约束 ─────────────────────────────────────────────────
    # 构建纯场景标签（不带数字/体量/规模）
    scenario_tag = ""
    if service_scenario and service_scenario != 'other':
        scenario_tag = f"""
**主服务场景标签：{scenario_text}**
- 问题必须绑定此场景，不脱离场景生成
- 保持普适性，不写具体数字（不说"100桌婚宴""500人食堂"）
- 详细现状/症状/规模 → 延后到画像环节落地"""
    # 本地城市信息
    if business_range == 'local' and local_city:
        aux_parts.append(f"服务城市：{local_city}")
    aux_section = '\n'.join(aux_parts) if aux_parts else "无"

    # 买用关系提示（与三层痛点归类对齐）
    # 【重要】禁止在此处写任何具体行业的示例，否则会导致模型照抄特定行业词汇
    buyer_user_hint = ""
    if business_type == 'product':
        buyer_user_hint = """【三层痛点归类规则】
- user_problem_types（使用层）：使用者遇到的核心问题（如效果不佳、不适、故障等）
- buyer_concern_types（决策层）：购买者的顾虑（如价格、品质、选择等）
- 注意：具体问题类型必须从实际业务描述中推理，不得照抄任何预设行业示例"""
    elif business_type == 'local_service':
        buyer_user_hint = """【三层痛点归类规则】
- user_problem_types（使用层）：使用者遇到的核心问题（如故障、损耗、不方便等）
- buyer_concern_types（决策层）：购买者的顾虑（如价格、效果、信任等）
- 注意：具体问题类型必须从实际业务描述中推理"""
    elif business_type == 'personal':
        buyer_user_hint = """【三层痛点归类规则】
- user_problem_types（使用层）：个人用户遇到的核心问题（如效果差、焦虑等）
- buyer_concern_types（决策层）：购买者的顾虑（如投入回报、风险等）
- 注意：具体问题类型必须从实际业务描述中推理"""
    elif business_type == 'enterprise':
        buyer_user_hint = """【三层痛点归类规则】
- user_problem_types（使用层）：使用者遇到的核心问题（如故障、效率低等）
- buyer_concern_types（决策层）：企业购买决策者的顾虑（如成本、质量、ROI等）
- 对接层：流程痛点（如审批繁琐、沟通成本高等）
- 注意：具体问题类型必须从实际业务描述中推理"""

    # 获取关键词筛选上下文
    try:
        from services.keyword_filter_service import KeywordFilterService, QuestionGuideService
        keyword_filter_context = KeywordFilterService.get_weighted_context(business_desc=business_desc)
        question_guide_context = QuestionGuideService.get_weighted_context()
    except Exception as e:
        logger.warning("[mine_problems_and_generate_personas] 获取关键词筛选上下文失败: %s", e)
        keyword_filter_context = ""
        question_guide_context = ""

    # ── 四类 business_type 统一升级：彻底删除可抄袭的案例文本 ──────────────────────
    # 所有 few_shot 只保留 JSON 结构规范，禁止任何具体行业/企业/场景案例
    if business_type == 'product':
        # 消费品：删除所有具体产品示例，只保留结构规范
        few_shot_section = """
=== 【消费品·输出结构规范 - 仅作字段参考，禁止照抄内容】===
本节仅定义 JSON 字段结构与必填项。所有 identity、description、problem_keywords、market_analysis 的具体措辞必须从用户业务描述中推导，严禁套用任何示例。

【user_problem_types 字段规范】
- identity: 抽象人群类型（如：长期使用者/首次尝试者/特殊人群）
- problem_base: 前置观望种草盘 / 刚需痛点盘 / 使用配套搜后种草盘
- problem_category: 功效质疑 / 安全担忧 / 适配顾虑 / 体验问题 / 价格价值
- problem_type: 抽象问题维度（如：效果存疑/成分安全/适用性不明/使用障碍）
- display_name: 一句话精炼描述（具体问题+影响）
- description: 2-3句详细描述（什么场景+遇到什么问题+造成什么影响）
- severity: ⭐⭐⭐ / ⭐⭐⭐⭐ / ⭐⭐⭐⭐⭐
- scenarios: 2-3个具体使用场景
- problem_keywords: 2-3个搜索关键词（必须与该问题主题语义一致）
- dimension: 维度标签
- content_direction: 种草型 / 转化型 / 搜后种草型
- market_type: blue_ocean / red_ocean
- market_reason: 判断理由（10字内）

【buyer_concern_types 字段规范】
- identity: 购买决策者身份
- concern_base: 前置观望 / 刚需痛点 / 使用配套
- concern_category: 顾虑大类
- concern_type: 抽象顾虑类型
- display_name/description/examples/problem_keywords 同上

【market_analysis 字段规范】
- market_type / market_type_display / competition_level / competition_level_display
- blue_ocean_opportunity: 一句话差异化机会
- red_ocean_features: 2-3条红海特征
- problem_oriented_keywords: 至少8个关键词，蓝海词≥4个

【消费品赛道差异化约束 - 必须全部执行】
问题必须从以下维度生成（每条问题至少覆盖1个维度）：
1. 动机层：客户核心需求（功效/安全/便捷/身份认同）
2. 障碍层：真实阻碍（不确定效果/担心安全/不知怎么选/怕买错）
3. 决策阶段：问题感知→信息搜索→方案评估→购买决策
4. 风险层：健康风险/财务风险/效果风险/机会风险

【禁止浅层同义重复 - 违者输出作废】
以下词汇组视为同一问题，禁止用不同说法重复输出：
- "效果不好" ≈ "效果不明显" ≈ "没效果" ≈ "效果差" ≈ "效果一般"
- "担心安全" ≈ "不安全" ≈ "怕有风险" ≈ "有危害吗"
- "太贵" ≈ "不值" ≈ "性价比低" ≈ "价格高" ≈ "买不起"
- "质量差" ≈ "质量不好" ≈ "质量一般"
- "真假难辨" ≈ "怕买到假货" ≈ "是正品吗"

每条问题必须有独特价值点，不可替代。

【消费品赛道问题侧重点 - 按权重分配】
功效质疑（30%）→ 安全担忧（30%）→ 适配顾虑（20%）→ 体验问题（15%）→ 价格价值（5%）

【输出格式示例 - 结构参考，内容必须自创】
{
    "market_analysis": {
        "market_type": "blue_ocean",
        "market_type_display": "蓝海市场",
        "competition_level": 6,
        "competition_level_display": "有一定竞争",
        "blue_ocean_opportunity": "（基于业务描述推导差异化机会）",
        "red_ocean_features": ["（基于业务描述推导）"],
        "problem_oriented_keywords": [
            {"keyword": "（基于业务推导关键词）", "type": "blue_ocean", "source": "场景痛点"},
            {"keyword": "（基于业务推导关键词）", "type": "blue_ocean", "source": "长尾转化"}
        ]
    },
    "user_problem_types": [
        {
            "identity": "（基于业务推导人群）",
            "problem_base": "前置观望种草盘",
            "problem_category": "（贴合业务）",
            "problem_type": "（抽象维度）",
            "display_name": "（一句话精炼）",
            "description": "（2-3句详细描述：场景+阻碍+影响）",
            "severity": "⭐⭐⭐⭐",
            "scenarios": ["场景1", "场景2"],
            "market_type": "blue_ocean",
            "market_reason": "（判断理由）",
            "problem_keywords": [
                {"keyword": "（关键词）", "type": "blue_ocean", "source": "场景痛点"},
                {"keyword": "（关键词）", "type": "blue_ocean", "source": "长尾转化"}
            ],
            "dimension": "（维度）",
            "content_direction": "种草型"
        }
    ],
    "buyer_concern_types": [
        {
            "identity": "（购买决策者）",
            "concern_base": "前置观望",
            "concern_category": "（顾虑大类）",
            "concern_type": "（抽象顾虑）",
            "display_name": "（一句话）",
            "description": "（详细描述）",
            "examples": ["例子1", "例子2"],
            "market_type": "blue_ocean",
            "market_reason": "（理由）",
            "problem_keywords": [
                {"keyword": "（关键词）", "type": "blue_ocean", "source": "顾虑"}
            ]
        }
    ]
}
"""
    elif business_type == 'local_service':
        # 本地服务：删除所有具体门店/具体服务案例
        few_shot_section = """
=== 【本地服务·输出结构规范 - 仅作字段参考，禁止照抄内容】===
本节仅定义 JSON 字段结构与必填项。所有 identity、description、problem_keywords、market_analysis 的具体措辞必须从用户业务描述中推导，严禁套用任何示例。

【user_problem_types 字段规范】
- identity: 抽象人群类型（如：周边居民/上班族/特殊家庭）
- problem_base: 前置观望种草盘 / 刚需痛点盘 / 使用配套搜后种草盘
- problem_category: 质量担忧 / 响应速度 / 价格透明 / 安全靠谱 / 便利程度
- problem_type: 抽象问题维度（如：技术不确定性/时效风险/价格不透明/信任缺失）
- display_name: 一句话精炼描述（具体场景+影响）
- description: 2-3句详细描述（什么场景+遇到什么问题+造成什么影响）
- severity: ⭐⭐⭐ / ⭐⭐⭐⭐ / ⭐⭐⭐⭐⭐
- scenarios: 2-3个具体使用场景
- problem_keywords: 2-3个搜索关键词（必须与该问题主题语义一致）
- dimension: 维度标签
- content_direction: 种草型 / 转化型 / 搜后种草型
- market_type: blue_ocean / red_ocean
- market_reason: 判断理由（10字内）

【buyer_concern_types 字段规范】
- identity: 购买决策者身份
- concern_base: 前置观望 / 刚需痛点 / 使用配套
- concern_category: 顾虑大类
- concern_type: 抽象顾虑类型
- display_name/description/examples/problem_keywords 同上

【market_analysis 字段规范】
- market_type / market_type_display / competition_level / competition_level_display
- blue_ocean_opportunity: 一句话差异化机会
- red_ocean_features: 2-3条红海特征
- problem_oriented_keywords: 至少8个关键词，蓝海词≥4个

【本地服务赛道差异化约束 - 必须全部执行】
问题必须从以下维度生成（每条问题至少覆盖1个维度）：
1. 动机层：客户核心需求（就近便捷/专业可靠/省心省力/安全保障）
2. 障碍层：真实阻碍（不知道哪家靠谱/担心技术不过关/怕被宰/怕跑路）
3. 决策阶段：问题感知→信息搜索→方案评估→购买决策
4. 风险层：信任风险/服务风险/价格不透明风险/安全风险

【必须强化本地化关键词】
所有输出必须包含以下本地化词汇（至少出现3个）：
附近、同城、上门、到店、地址、区域、最近、周边、当地、本地

【禁止浅层同义重复 - 违者输出作废】
以下词汇组视为同一问题，禁止用不同说法重复输出：
- "质量不好" ≈ "质量差" ≈ "质量一般" ≈ "不专业"
- "太贵了" ≈ "不值" ≈ "性价比低" ≈ "价格高" ≈ "乱收费"
- "不靠谱" ≈ "信不过" ≈ "怕跑路" ≈ "担心被骗"
- "服务差" ≈ "态度不好" ≈ "不负责任"

每条问题必须有独特价值点，不可替代。

【本地服务赛道问题侧重点 - 按权重分配】
质量技术（25%）→ 时效响应（20%）→ 价格透明（20%）→ 信任靠谱（20%）→ 便利程度（15%）

【输出格式示例 - 结构参考，内容必须自创】
{
    "market_analysis": {
        "market_type": "blue_ocean",
        "market_type_display": "蓝海市场",
        "competition_level": 6,
        "competition_level_display": "有一定竞争",
        "blue_ocean_opportunity": "（基于业务描述推导差异化机会）",
        "red_ocean_features": ["（基于业务描述推导）"],
        "problem_oriented_keywords": [
            {"keyword": "（基于业务推导关键词）", "type": "blue_ocean", "source": "场景痛点"},
            {"keyword": "（基于业务推导关键词）", "type": "blue_ocean", "source": "长尾转化"}
        ]
    },
    "user_problem_types": [
        {
            "identity": "（基于业务推导人群）",
            "problem_base": "前置观望种草盘",
            "problem_category": "（贴合业务）",
            "problem_type": "（抽象维度）",
            "display_name": "（一句话精炼）",
            "description": "（2-3句详细描述：场景+阻碍+影响）",
            "severity": "⭐⭐⭐⭐",
            "scenarios": ["场景1", "场景2"],
            "market_type": "blue_ocean",
            "market_reason": "（判断理由）",
            "problem_keywords": [
                {"keyword": "（关键词）", "type": "blue_ocean", "source": "场景痛点"},
                {"keyword": "（关键词）", "type": "blue_ocean", "source": "长尾转化"}
            ],
            "dimension": "（维度）",
            "content_direction": "种草型"
        }
    ],
    "buyer_concern_types": [
        {
            "identity": "（购买决策者）",
            "concern_base": "前置观望",
            "concern_category": "（顾虑大类）",
            "concern_type": "（抽象顾虑）",
            "display_name": "（一句话）",
            "description": "（详细描述）",
            "examples": ["例子1", "例子2"],
            "market_type": "blue_ocean",
            "market_reason": "（理由）",
            "problem_keywords": [
                {"keyword": "（关键词）", "type": "blue_ocean", "source": "顾虑"}
            ]
        }
    ]
}
"""
    elif business_type == 'personal':
        # 个人IP/专家：删除所有具体博主/领域案例
        few_shot_section = """
=== 【个人IP/专家·输出结构规范 - 仅作字段参考，禁止照抄内容】===
本节仅定义 JSON 字段结构与必填项。所有 identity、description、problem_keywords、market_analysis 的具体措辞必须从用户业务描述中推导，严禁套用任何示例。

【user_problem_types 字段规范】
- identity: 抽象人群类型（如：学习者/践行者/想转型者/焦虑者）
- problem_base: 前置观望种草盘 / 刚需痛点盘 / 使用配套搜后种草盘
- problem_category: 认知迷茫 / 方法缺失 / 效率焦虑 / 误区踩坑 / 成长焦虑
- problem_type: 抽象问题维度（如：方向不明/方法不对/效率低下/认知偏差）
- display_name: 一句话精炼描述（具体困惑+影响）
- description: 2-3句详细描述（什么场景+遇到什么问题+造成什么影响）
- severity: ⭐⭐⭐ / ⭐⭐⭐⭐ / ⭐⭐⭐⭐⭐
- scenarios: 2-3个具体使用场景
- problem_keywords: 2-3个搜索关键词（必须与该问题主题语义一致）
- dimension: 维度标签
- content_direction: 种草型 / 转化型 / 搜后种草型
- market_type: blue_ocean / red_ocean
- market_reason: 判断理由（10字内）

【buyer_concern_types 字段规范】
- identity: 购买决策者身份（可能是本人或家人）
- concern_base: 前置观望 / 刚需痛点 / 使用配套
- concern_category: 顾虑大类
- concern_type: 抽象顾虑类型
- display_name/description/examples/problem_keywords 同上

【market_analysis 字段规范】
- market_type / market_type_display / competition_level / competition_level_display
- blue_ocean_opportunity: 一句话差异化机会
- red_ocean_features: 2-3条红海特征
- problem_oriented_keywords: 至少20个关键词，蓝海词≥10个（**专业服务问题类型非常丰富，必须充分挖掘**）

【个人IP/专家赛道问题数量要求 - 必须严格执行】
- user_problem_types 至少15条
- buyer_concern_types 至少10条
- **必须覆盖多种不同身份、不同问题类型、不同场景**

【个人IP赛道差异化约束 - 必须全部执行】
问题必须从以下维度生成（每条问题至少覆盖1个维度）：
1. 动机层：客户核心需求（想成长/想改变/想突破/想系统化）
2. 障碍层：真实阻碍（不知道从哪开始/试过没用/怕走弯路/怕被骗）
3. 决策阶段：问题感知→信息搜索→方案评估→购买决策
4. 风险层：机会成本风险/时间成本风险/走弯路风险/选择错误风险

【禁止浅层同义重复 - 违者输出作废】
以下词汇组视为同一问题，禁止用不同说法重复输出：
- "不知道怎么做" ≈ "不会做" ≈ "无从下手" ≈ "不知道从哪开始"
- "怕学不会" ≈ "担心学不好" ≈ "怕没效果"
- "怕被骗" ≈ "担心不靠谱" ≈ "怕交智商税"
- "浪费时间" ≈ "浪费时间精力" ≈ "怕走弯路"

每条问题必须有独特价值点，不可替代。

【个人IP赛道问题侧重点 - 按权重分配】
方法缺失（30%）→ 认知迷茫（25%）→ 效率焦虑（20%）→ 误区踩坑（15%）→ 成长焦虑（10%）

【输出格式示例 - 结构参考，内容必须自创】
{
    "market_analysis": {
        "market_type": "blue_ocean",
        "market_type_display": "蓝海市场",
        "competition_level": 6,
        "competition_level_display": "有一定竞争",
        "blue_ocean_opportunity": "（基于业务描述推导差异化机会）",
        "red_ocean_features": ["（基于业务描述推导）"],
        "problem_oriented_keywords": [
            {"keyword": "（基于业务推导关键词）", "type": "blue_ocean", "source": "场景痛点"},
            {"keyword": "（基于业务推导关键词）", "type": "blue_ocean", "source": "长尾转化"}
        ]
    },
    "user_problem_types": [
        {
            "identity": "（基于业务推导人群）",
            "problem_base": "前置观望种草盘",
            "problem_category": "（贴合业务）",
            "problem_type": "（抽象维度）",
            "display_name": "（一句话精炼）",
            "description": "（2-3句详细描述：场景+阻碍+影响）",
            "severity": "⭐⭐⭐⭐",
            "scenarios": ["场景1", "场景2"],
            "market_type": "blue_ocean",
            "market_reason": "（判断理由）",
            "problem_keywords": [
                {"keyword": "（关键词）", "type": "blue_ocean", "source": "场景痛点"},
                {"keyword": "（关键词）", "type": "blue_ocean", "source": "长尾转化"}
            ],
            "dimension": "（维度）",
            "content_direction": "种草型"
        }
    ],
    "buyer_concern_types": [
        {
            "identity": "（购买决策者）",
            "concern_base": "前置观望",
            "concern_category": "（顾虑大类）",
            "concern_type": "（抽象顾虑）",
            "display_name": "（一句话）",
            "description": "（详细描述）",
            "examples": ["例子1", "例子2"],
            "market_type": "blue_ocean",
            "market_reason": "（理由）",
            "problem_keywords": [
                {"keyword": "（关键词）", "type": "blue_ocean", "source": "顾虑"}
            ]
        }
    ]
}
"""
    elif business_type == 'enterprise':
        # 企业服务：删除所有连锁餐饮/互联网/医疗器械等具体案例
        few_shot_section = """
=== 【企业服务·输出结构规范 - 仅作字段参考，禁止照抄内容】===
本节仅定义 JSON 字段结构与必填项。所有 identity、description、problem_keywords、market_analysis 的具体措辞必须从用户业务描述中推导，严禁套用任何示例。

【user_problem_types 字段规范】
- identity: 描述具体企业类型+决策角色（如：XX行业中型企业-法务负责人）
- problem_base: 前置观望 / 刚需痛点盘 / 使用配套搜后种草盘
- problem_category: 选型对比 / 风险合规 / ROI评估 / 实施落地 / 管理效率
- problem_type: 抽象问题维度（如：合同审核风险/劳动合规风险/知识产权风险/决策链复杂）
- display_name: 高度精炼的一句话描述
- description: 详细描述问题场景、影响、背景，2-3句话
- severity: ⭐⭐⭐ / ⭐⭐⭐⭐ / ⭐⭐⭐⭐⭐
- scenarios: 2-3个具体场景
- problem_keywords: 2-3个搜索关键词（必须与该问题主题语义一致）
- dimension: 维度标签
- content_direction: 种草型 / 转化型 / 搜后种草型
- market_type: blue_ocean / red_ocean
- market_reason: 判断理由（10字内）

【buyer_concern_types 字段规范】
- identity: 决策角色（使用者/技术负责人/管理者/老板/采购负责人）
- concern_base: 前置观望
- concern_category: 顾虑大类
- concern_type: 抽象顾虑类型
- display_name/description/examples/problem_keywords 同上

【market_analysis 字段规范】
- market_type / market_type_display / competition_level / competition_level_display
- blue_ocean_opportunity: 一句话差异化机会
- red_ocean_features: 2-3条红海特征
- problem_oriented_keywords: 至少8个关键词，蓝海词≥4个

【企业服务赛道差异化约束 - 必须全部执行】
问题必须从以下维度生成（每条问题至少覆盖1个维度）：
1. 动机层：企业核心需求（降本增效/规避风险/提升效率/合规经营）
2. 障碍层：真实阻碍（选型困难/ROI不明确/实施门槛高/责任归属不清）
3. 决策阶段：问题感知→信息搜索→方案评估→购买决策（多角色参与）
4. 风险层：合规风险/财务风险/责任风险/管理风险/机会成本风险

【角色分层要求 - 必须严格区分】
- user_problem_types: 服务使用者视角（如：法务专员/HR/部门负责人/IT运维）
- buyer_concern_types: 付费决策者视角（如：老板/副总/CFO/采购负责人）
- 角色必须有明确区分，不能都是"企业客户"

【禁止浅层同义重复 - 违者输出作废】
以下词汇组视为同一问题，禁止用不同说法重复输出：
- "不知道选哪个" ≈ "怎么选" ≈ "对比参数" ≈ "选型困难"
- "怕被骗" ≈ "担心不靠谱" ≈ "怕效果不好"
- "太贵了" ≈ "投入产出比低" ≈ "不值得" ≈ "成本高"
- "实施难" ≈ "落地难" ≈ "不好用"

每条问题必须有独特价值点，不可替代。

【企业服务赛道问题侧重点 - 按权重分配】
决策链复杂（25%）→ 选型对比（25%）→ 风险合规（20%）→ ROI评估（15%）→ 实施落地（15%）

【输出格式示例 - 结构参考，内容必须自创】
{
    "market_analysis": {
        "market_type": "blue_ocean",
        "market_type_display": "蓝海市场",
        "competition_level": 7,
        "competition_level_display": "竞争激烈",
        "blue_ocean_opportunity": "（基于业务描述推导差异化机会）",
        "red_ocean_features": ["（基于业务描述推导）"],
        "problem_oriented_keywords": [
            {"keyword": "（基于业务推导关键词）", "type": "blue_ocean", "source": "场景痛点"},
            {"keyword": "（基于业务推导关键词）", "type": "blue_ocean", "source": "场景痛点"}
        ]
    },
    "user_problem_types": [
        {
            "identity": "（基于业务推导具体企业类型+角色）",
            "problem_base": "前置观望",
            "problem_category": "（贴合业务）",
            "problem_type": "（抽象维度）",
            "display_name": "（一句话精炼）",
            "description": "（2-3句详细描述：场景+阻碍+影响）",
            "severity": "⭐⭐⭐⭐",
            "scenarios": ["场景1", "场景2", "场景3"],
            "market_type": "blue_ocean",
            "market_reason": "（判断理由）",
            "problem_keywords": [
                {"keyword": "（关键词）", "type": "blue_ocean", "source": "场景痛点"},
                {"keyword": "（关键词）", "type": "blue_ocean", "source": "场景痛点"}
            ],
            "dimension": "（维度）",
            "content_direction": "种草型"
        }
    ],
    "buyer_concern_types": [
        {
            "identity": "（决策角色：老板/高管/采购负责人）",
            "concern_base": "前置观望",
            "concern_category": "（顾虑大类）",
            "concern_type": "（抽象顾虑）",
            "display_name": "（一句话）",
            "description": "（详细描述）",
            "examples": ["例子1", "例子2"],
            "market_type": "blue_ocean",
            "market_reason": "（理由）",
            "problem_keywords": [
                {"keyword": "（关键词）", "type": "blue_ocean", "source": "顾虑"}
            ]
        }
    ]
}
"""
    # ── GEO战略配置 ──────────────────────────────────────────────────────────────
    # 根据经营类型获取GEO战略配置
    geo_strategy = get_geo_strategy(business_type)
    strategy_name = geo_strategy.get("strategy_name", "")
    core_psychology = geo_strategy.get("core_psychology", "")
    problem_focus = "、".join(geo_strategy.get("problem_focus", []))
    trust_types = "、".join(geo_strategy.get("trust_types", []))
    content_plate_ratio = geo_strategy.get("content_plate_ratio", {})
    content_ratio_str = " ".join([f"{k}:{v}%" for k, v in content_plate_ratio.items()])

    # 根据经营类型动态生成行业禁止词（防止LLM照抄示例）
    industry_guard_map = {
        "local_service": "家政、保洁、保姆、月嫂、雇主、虐童、虐待老人、深度清洁、阿姨、除螨、上门做饭、厨师私厨",
        "product": "家政、保洁、保姆、月嫂、雇主、深度清洁、阿姨、除螨、上门做饭、厨师",
        "personal": "家政、保洁、保姆、月嫂、雇主、深度清洁、阿姨、除螨、上门做饭、厨师",
        "enterprise": "家政、保洁、保姆、月嫂、雇主、深度清洁、阿姨、除螨、上门做饭、厨师"
    }
    forbidden_words = industry_guard_map.get(business_type, industry_guard_map.get("local_service"))

    # 构建GEO战略上下文段落
    geo_context = f"""
=== 【GEO黄金赛道战略配置】===
当前经营类型：{business_type_name}
对应GEO赛道：{strategy_name}
核心客户心理：{core_psychology}

【问题关注重点】：{problem_focus}
【信任构建类型】：{trust_types}
【内容底盘比例】：{content_ratio_str}

【角色模式】：{geo_strategy.get("role_mode", "")}
【GEO内容重点】：{"、".join(geo_strategy.get("geo_focus", []))}
【CTA风格】：{geo_strategy.get("cta_style", "")}

【高风险标记】：{"是" if geo_strategy.get("high_risk_decision") else "否"}

=== 【行业禁止词列表 - 严格禁止出现】===
当前业务「{business_desc[:30]}...」属于「{business_type_name}」行业，以下词汇**严禁**出现在输出中：
{forbidden_words}

**违规判定**：一旦检测到上述任何词汇，输出立即作废并强制重写。
"""

    # ── 专业服务检测：local_service 类型但业务描述是专业服务时，覆盖 GEO 策略 ───
    # 防止律师事务所、财税服务、教育培训等专业服务被错误地用"家政/保洁"策略
    if business_type == "local_service":
        professional_keywords = ['法律', '律师', '财税', '会计', '税务', '咨询', '培训', '教育', '医疗', '健康', '养老', '美容', '装修', '设计', '摄影', '翻译', '签证', '移民', '资质', '执照', '专利', '商标', '知识产权', '公证', '鉴定']
        home_service_keywords = ['家政', '保洁', '清洗', '维修', '开锁', '疏通', '搬家', '陪诊', '护工', '月嫂', '保姆', '钟点工', '除螨', '擦玻璃', '深度清洁', '收纳', '代驾', '洗车', '宠物', '美甲', '美发', '按摩', '足疗']
        desc_lower = business_desc.lower()
        has_professional = any(kw in desc_lower for kw in professional_keywords)
        has_home_service = any(kw in desc_lower for kw in home_service_keywords)
        if has_professional and not has_home_service:
            # 专业服务：覆盖为"专业服务"赛道
            geo_context = f"""
=== 【GEO黄金赛道战略配置】===
当前经营类型：{business_type_name}（专业服务）
对应GEO赛道：专业服务解决方案
核心客户心理：权益受侵害、纠纷风险、法律程序复杂、维权成本高

【问题关注重点】：法律风险、纠纷场景、权益受损、程序复杂、维权障碍
【信任构建类型】：资质背书、真实案例、专业方案、法律依据
【内容底盘比例】：{content_ratio_str}

【角色模式】：决策者=使用者，个人/家庭自主决策
【GEO内容重点】：问题科普、案例解析、方案对比、风险提示
【CTA风格】：预约咨询、获取方案、了解流程、联系律师

【高风险标记】：是

=== 【行业禁止词列表 - 严格禁止出现】===
当前业务「{business_desc[:30]}...」属于「{business_type_name}」专业服务行业，以下词汇**严禁**出现在输出中：
{forbidden_words}

**违规判定**：一旦检测到上述任何词汇，输出立即作废并强制重写。
"""
            logger.debug("[mine_problems_and_generate_personas] 检测到专业服务，覆盖GEO策略为专业服务赛道")

            # 覆盖 system_base_personas：专业服务不用老人/孩子，用成年人
            import json as _json
            PROFESSIONAL_SERVICE_PERSONAS = {
                "决策层(buyer)": [
                    {"name": "自住成年业主", "desc": "自己出钱买给自己用，成年人自主决策", "role": "buyer_user", "user_of": "自住成年业主"},
                    {"name": "职场人士", "desc": "上班族，出于个人或家庭需求购买法律服务", "role": "buyer_user", "user_of": "职场人士"},
                    {"name": "家庭支柱", "desc": "上有老下有小的中年人，家庭事务决策者", "role": "buyer_user", "user_of": "家庭成员"},
                    {"name": "租房群体", "desc": "租房族自己出钱用", "role": "buyer_user", "user_of": "租房群体"},
                ],
                "对接层": [
                    {"name": "家庭成员", "desc": "家庭事务联络协调者", "role": "mediator", "buyer_of": "家庭决策者", "user_of": "家庭成员"},
                ],
                "使用层(user)": [
                    {"name": "成年人自己", "desc": "实际使用者，18-60岁，自主决策", "role": "user", "buyer_of": "自住成年业主"},
                    {"name": "家庭成员", "desc": "一般家庭成员，成年人为主", "role": "user", "buyer_of": "家庭支柱"},
                    {"name": "职场人士", "desc": "上班族，18-60岁", "role": "user", "buyer_of": "职场人士"},
                ]
            }
            system_base_personas = _json.dumps(PROFESSIONAL_SERVICE_PERSONAS, ensure_ascii=False, indent=2)
            logger.debug("[mine_problems_and_generate_personas] 专业服务：覆盖system_base_personas为成年人群体")

    # ── 企业服务专用视角约束 ───────────────────────────────────────────────────
    # 针对企业服务，需要特殊的问题挖掘视角
    enterprise_view_constraint = ""
    if business_type == "enterprise":
        enterprise_view_constraint = """
=== 【企业服务专用问题挖掘视角约束】===
**核心原则**：你是帮{business_type_name}公司挖掘问题，吸引**潜在企业客户**。

**【身份定义 - 绝对禁止】** ❌
❌ 禁止将"企业HR"、"企业高管"、"企业老板"作为问题主体
❌ 禁止写"HR能力不足"、"高管法律知识不够"
❌ 禁止写"企业内部人员"作为搜索问题的人

**【身份定义 - 正确方式】** ✅
✅ identity 应该是"有法律需求的企业"
✅ 描述企业在什么**具体场景**下会遇到问题
✅ 描述企业遇到的**具体法律风险/纠纷/问题**

**【问题挖掘方向 - 正确示例】** ✅
identity: "制造业企业"
problem_type: "劳动纠纷风险"
description: "企业招聘旺季大量用工，可能面临劳动合同签订不规范、加班费争议、离职赔偿纠纷等问题"

identity: "创业公司"
problem_type: "知识产权风险"
description: "创业初期可能遭遇商标被抢注、核心技术被抄袭、合同知识产权条款漏洞等风险"

identity: "连锁餐饮企业"
problem_type: "商业合同风险"
description: "加盟合同、供应商合同、租赁合同中的法律风险识别和规避"

identity: "电商企业"
problem_type: "消费者权益纠纷"
description: "电商平台面临的退款纠纷、职业打假人投诉、产品宣传合规等问题"

**【问题类型参考 - 企业服务专用】**
- 劳动纠纷预防与处理
- 合同审核与风险规避
- 知识产权保护与维权
- 企业合规体系建设
- 商业纠纷调解与诉讼
- 投融资法律风险
- 税务合规与筹划
- 知识产权申请与保护
- 企业股权设计与转让
- 劳动仲裁与诉讼应对

**【禁止的问题类型】** ❌
❌ "企业HR能力不足" → 这是侮辱客户智商
❌ "企业高管不懂法" → 这是侮辱客户智商
❌ "企业内部人员处理不了" → 这是侮辱客户智商

**企业客户要找的是**：帮他解决问题的人，而不是被教育"你能力不足"
"""

    # ── 个人服务专用视角约束 ───────────────────────────────────────────────────
    personal_view_constraint = ""
    if business_type == "personal":
        personal_view_constraint = """
=== 【个人服务专用问题挖掘视角约束】===
**核心原则**：你是帮{business_type_name}公司挖掘问题，吸引**潜在个人客户**。

**【身份定义 - 绝对禁止】** ❌
❌ 禁止将"个人能力不足"、"个人技术不够"作为问题主体
❌ 禁止写"你做不好"、"你搞不定"
❌ 禁止写"个人知识/技能缺失"作为痛点
❌ **严格禁止生成以下问题维度**（出现即违规）：
   - "能力技术不足"
   - "时间精力不足"
   - "特殊人群行动受限"
   - "心理情绪障碍"
   - "安全信任顾虑"
   - "场景条件问题"
   - "心理情绪问题"

**【身份定义 - 正确方式】** ✅
✅ identity 应该是"有需求的个人"
✅ 描述个人在什么**具体场景/人生阶段**中遇到问题
✅ 描述个人遇到的**具体困难/担忧/风险**
✅ 问题维度必须是**具体的权益受侵害/纠纷/风险**

**【问题挖掘方向 - 正确示例】** ✅
identity: "职场人士"
problem_type: "劳动权益受侵害"
description: "职场中可能遭遇拖欠工资、超时加班、试用期被随意辞退、被迫签署不平等协议等劳动权益受损问题"

identity: "租房群体"
problem_type: "租房纠纷"
description: "租房过程中可能遭遇房东提前收房、押金不退、维修责任推诿、二房东跑路等租赁纠纷"

identity: "消费者"
problem_type: "消费维权困难"
description: "日常消费中可能遭遇虚假宣传、产品质量问题、售后服务推诿、退款困难等维权障碍"

identity: "创业者"
problem_type: "创业法律风险"
description: "创业初期可能遭遇合同纠纷、股权争议、知识产权被侵权、劳动用工合规等法律风险"

identity: "家庭成员"
problem_type: "家庭财产纠纷"
description: "家庭财产传承、房产纠纷、婚姻财产分割等需要法律专业指导的问题"

**【问题维度参考 - 个人服务专用】（唯一正确的问题类型）**
- 权益受侵害：劳动权益受损、消费权益受损、隐私权益受侵害
- 纠纷风险：劳动纠纷、租房纠纷、合同纠纷、婚姻纠纷、继承纠纷
- 法律风险：交通事故责任、医疗纠纷、知识产权被侵权、合同风险
- 维权障碍：投诉无门、证据不足、维权成本高、法律程序复杂

**【禁止的问题维度】** ❌（这些是消费类服务的问题，不适用于专业服务）
❌ "能力技术不足" → 专业服务客户不需要你教他能力不足
❌ "时间精力不足" → 专业服务客户不需要你说他没时间
❌ "特殊人群行动受限" → 这是医疗/养老服务的问题
❌ "心理情绪障碍" → 这是心理咨询的问题
❌ "安全信任顾虑" → 这是家政/上门服务的问题

**专业服务客户要找的是**：帮他解决问题的专家，而不是被告知"你能力不行"
"""

    # ── 本地服务/家用/个人场景专用视角约束 ─────────────────────────────────────
    # 针对本地服务(business_type=local_service)，覆盖家用、个人场景
    # 重要：很多专业服务（如律师、财税、教育）被错误地归为"本地服务"
    # 需要防止LLM把它们当作家政/保洁一样的问题类型
    local_service_view_constraint = ""
    if business_type == "local_service":
        local_service_view_constraint = """
=== 【本地服务/专业服务问题挖掘视角约束】===
**核心原则**：你是帮{business_type_name}公司挖掘问题，吸引**潜在个人/家庭客户**。
当前业务「{business_desc}」属于{business_type_name}行业。

**【身份定义 - 绝对禁止】** ❌
❌ 禁止将"个人能力不足"、"个人不会"、"自己搞不定"作为问题主体
❌ 禁止写"你做不好"、"你搞不定"、"你不会做"
❌ 禁止写"没时间/精力"作为核心痛点
❌ 禁止写"行动不便/没人帮忙"作为核心痛点
❌ 禁止写"担心价格/担心被宰/担心不透明"——这是消费决策问题，不是专业服务的核心问题
❌ **严格禁止生成以下问题维度**（出现即违规）：
   - "能力技术不足"
   - "时间精力不足"
   - "特殊人群行动受限"
   - "心理情绪障碍"
   - "安全信任顾虑"
   - "场景条件问题"
   - "图方便/不想动"
   - "担心价格/担心被坑"

**【身份定义 - 正确方式】** ✅
✅ identity 应该是"有需求的个人/家庭"
✅ 描述个人/家庭在什么**具体场景/人生阶段/具体事件**中遇到问题
✅ 描述个人/家庭遇到的**具体困难/担忧/风险/纠纷/法律问题**
✅ 问题维度必须是**具体的权益受侵害/纠纷/风险/法律问题**

**【问题挖掘方向 - 正确示例】** ✅
identity: "职场人士"
problem_type: "劳动权益受侵害"
description: "职场中可能遭遇拖欠工资、超时加班、试用期被随意辞退、被迫签署不平等协议等劳动权益受损问题"

identity: "租房群体"
problem_type: "租房纠纷"
description: "租房过程中可能遭遇房东提前收房、押金不退、维修责任推诿、二房东跑路等租赁纠纷"

identity: "消费者"
problem_type: "消费维权困难"
description: "日常消费中可能遭遇虚假宣传、产品质量问题、售后服务推诿、退款困难等维权障碍"

identity: "家庭成员"
problem_type: "家庭财产纠纷"
description: "家庭财产传承、房产纠纷、婚姻财产分割等需要法律专业指导的问题"

identity: "小微企业主"
problem_type: "经营法律风险"
description: "经营中可能遭遇合同纠纷、劳动仲裁、客户欠款、知识产权被侵犯等法律风险"

**【问题维度参考 - 专业服务专用】**
- 权益受侵害：劳动权益受损、消费权益受损、隐私权益受侵害
- 纠纷风险：劳动纠纷、租房纠纷、合同纠纷、婚姻纠纷、继承纠纷
- 法律风险：交通事故责任、医疗纠纷、知识产权被侵权、合同风险
- 维权障碍：投诉无门、证据不足、维权成本高、法律程序复杂

**【禁止的问题维度】** ❌（这些是消费类服务的问题，不适用于专业服务）
❌ "能力技术不足" → 专业服务客户不需要你教他能力不足
❌ "时间精力不足" → 专业服务客户不需要你说他没时间
❌ "特殊人群行动受限" → 这是医疗/养老服务的问题
❌ "心理情绪障碍" → 这是心理咨询的问题
❌ "安全信任顾虑" → 这是家政/上门服务的问题
❌ "担心价格不透明" → 这是消费决策问题，不是专业服务的核心痛点

**专业服务客户要找的是**：帮他解决问题的专家，而不是被告知"你能力不行"或"你没时间"
"""

    # ── 企业服务专用视角约束结束 ──────────────────────────────────────────────

    # 防御性定义：确保所有 prompt 模板变量都存在
    # red_ocean_prompt_addon 用于在红海市场中添加额外的指导信息
    red_ocean_prompt_addon = ""

    # ── 消费者决策链路框架（仅用于产品/本地服务类型）──────────────────────────
    consumer_framework = ""
    abstract_problem_rule = ""
    if business_type in ('product', 'local_service'):
        consumer_framework = """
**二、消费者决策链路问题挖掘框架（核心框架）**

【重要】用户从"遇到问题"到"选择服务/产品"，中间经历三个阶段：

=== 【阶段1·问题认知】（第一优先级·必须先挖·占≥60%）
客户在某个场景发生了问题 → 先了解"问题本身"+"问题造成的影响"
- 这个时候客户还不知道有"上门做饭/我们的产品"这个解决方案
- 搜索的是问题本身，比如"家里来客人了忙不过来"
- 核心问题：什么场景/情况下会产生找解决方案的需求？

❌ 这个阶段禁止出现：
- 直接搜索解决方案的词：如"上门做饭"、"厨师私厨"
- 产品质量/体验问题：这是阶段3才考虑的

✅ 阶段1包含两类问题：

【A类·场景问题】场景+需求缺口（新增维度）：
- 什么场景下需要找解决方案？
- 核心词：没时间/来不及/做不了/太忙/临时有事
- "家里来客人了，一个人做不了一桌菜，怕招待不周"
- "厨艺不行怕做出来在客人面前丢人"
- "最近太忙了根本没时间做饭"
- "老人腿脚不便，自己做饭太危险"
- "孩子升学宴/老人生日，想给惊喜但自己搞不定"

【B类·体感问题】用户真实体感/身体反应/日常异常（保留原第一优先级）：
1. 身体体感：用户身体上的直接感受（累/乏/困/腰酸背痛/站久了腿肿/手腕酸等）
2. 身体反应：肉眼可见的身体变化（面色不好/精力差/体力跟不上等）
3. 日常异常：日常生活行为变化（睡不好/吃不下/没胃口/不想动/懒得做等）
4. 行为变化：具体可观察的行为改变（能点外卖就点外卖/能躺着不坐着等）
5. 心理情绪：具体情绪词（烦躁/纠结/凑合/将就/图省事等）

示例：
- "上了一天班累得要死，回家根本不想动，更别说做饭了"
- "腰酸背痛站久了就受不了，做一顿饭腰都直不起来"
- "带孩子/照顾老人已经精疲力竭，实在没精力再下厨"
- "天太热/太冷在厨房待不住，一做饭就满头大汗"
- "懒得做饭/不想动/图省事/随便对付一口算了"

=== 【阶段2·方案搜索】（第二优先级·占约20-30%）
客户知道了可能有多种解决方案 → 开始搜索和比较解决方案
- 搜索词包含具体的服务/产品类型，如"上门做饭"、"私厨到家"
- 核心问题：客户会搜索哪些解决方案关键词？

✅ 正确格式：具体解决方案搜索
- "上门做饭多少钱"
- "私厨到家服务"
- "厨师上门做饭靠谱吗"

❌ 禁止：宏观决策类问题（如"性价比"、"值不值"）

=== 【阶段3·购买后】（第三优先级·严格控制≤15%）
客户选择了某个方案 → 使用前/中/后的担忧
- 仅保留与服务质量直接相关的担忧
- 禁止：与找服务动机无关的问题（如"食物浪费"是用了服务后才考虑的）

✅ 正确格式：使用服务时的具体担忧
- "厨师做饭食材自己准备还是厨师带"
- "陌生人来家里安全吗"
- "厨师做饭不习惯口味怎么办"

❌ 禁止格式（与找服务动机无关）：
- "食物浪费怎么办"（用了服务才考虑，不是找服务的动机）
- "食物变质问题"（服务提供方的责任）
- "食物过敏问题"（服务提供方的责任）

**三、严格按三层母维度 + 9大方向抠细节**

【三层母维度 - 必须只写具体感受，禁止写评价】
1. 身体体感：具体感受词（疼/痒/胀/酸/麻/晕/恶心/乏力等）→ 禁止：不舒服、效果不好
2. 生活行为：具体行为变化（睡不好/吃不下/精力差/记性差等）→ 禁止：生活质量下降、影响工作
3. 心理情绪：具体情绪词（焦虑/担心/害怕/烦躁/纠结等）→ 禁止：不满意、不放心

【9大细节方向 - 必须抠到肉眼可见/身体可感的具体表现】
① 身体消化异常 → 必须具体：大便奶瓣/绿便/便秘3天/腹胀如鼓/反胃/呕吐/食欲下降
② 皮肤体表异常 → 必须具体：脸上起疹子/手背干燥起皮/红肿瘙痒/掉头发/指甲分层
③ 呼吸鼻腔异常 → 必须具体：鼻塞只能用嘴呼吸/打喷嚏连打5个/晚上咳嗽睡不着
④ 过敏不耐反应 → 必须具体：喝完脸红肿/起荨麻疹/眼睛肿/嘴唇肿/呕吐腹泻
⑤ 状态下滑/能力衰减 → 必须具体：爬3层楼就喘/记不住刚说的话/体重2周降3斤/视力模糊
⑥ 作息睡眠异常 → 必须具体：凌晨2点醒/做梦3点才睡着/每天只睡4小时/白天嗜睡
⑦ 情绪行为反常 → 必须具体：易怒摔东西/不愿意出门/对什么都没兴趣/爱哭/挑食拒食
⑧ 营养/配套不足 → 必须具体：脸色发黄/指甲有白点/头发枯黄/比同龄人矮半头
⑨ 特殊场景细节 → 必须具体：（婴幼儿）不肯喝奶/换季就生病/（老人）走路不稳/吃饭呛咳

**四、按决策链路阶段输出问题（核心要求）**

【阶段1·问题认知问题格式要求】
✅ 正确：场景 + 具体问题 + 造成的困扰/影响
- "家里来客人了，一个人做不了一桌菜，怕招待不周"
- "厨艺不行怕做出来在客人面前丢人"
- "最近太忙了根本没时间做饭"
- "老人腿脚不便，自己做饭太危险"

❌ 错误：直接说解决方案或产品问题
- "有没有上门做饭服务"（这是阶段2的问题）
- "食物浪费怎么办"（这是阶段3的问题）
- "食物变质问题"（这是产品问题，不是找服务的动机）

【阶段3·购买后问题格式要求】
✅ 正确：使用服务时的具体担忧
- "厨师做饭食材自己准备还是厨师带"
- "陌生人来家里安全吗"
- "厨师做饭不习惯口味怎么办"

❌ 错误：与找服务动机无关的问题
- "食物浪费怎么办"（用了服务才考虑，不是找服务的动机）

**五、底盘强制分配规则（按决策链路）**

| 决策阶段 | 问题类型 | 底盘 | 判断 |
|----------|---------|------|------|
| 阶段1-A | 场景问题：没时间/来不及/做不了/临时有事 | 前置观望种草盘 | 找服务的原始动机 |
| 阶段1-B | 体感问题：身体累/乏/困/腰酸背痛/不想动/懒得做 | 前置观望种草盘 | 身体层面的原始痛点 |
| 阶段1-A | 能力问题：不会做/做不好/怕丢人 | 前置观望种草盘 | 需要专业帮助 |
| 阶段1-B | 便利问题：图省事/凑合/将就/不想动 | 前置观望种草盘 | 需要便捷方案 |
| 阶段2 | 方案搜索：搜索具体解决方案 | 前置观望种草盘 | 开始找方案 |
| 阶段3 | 使用前担忧：服务是否靠谱 | 刚需痛点盘 | 决策前的顾虑 |
| 阶段3 | 使用中担忧：食材/专业度 | 使用配套搜后种草盘 | 使用中的问题 |

**六、输出格式（严格按此格式）**
- identity：具体人群+具体场景（如：做生意的老板/家里常有客人要招待的家庭/老人独居但常来客人的家庭）
- problem_base：严格按上述决策链路规则填写
- problem_category：从五类选一
- problem_type：必须从决策链路方向选一类+具体描述
- description：**必须写出"什么场景下遇到什么问题+想找什么解决方案"**
- severity：⭐⭐⭐/⭐⭐⭐⭐/⭐⭐⭐⭐⭐
- scenarios：2-3个具体场景
- problem_keywords：**必须围绕具体问题写搜索词，禁止写宏观购买词**
- dimension：场景问题/能力问题/时间问题/便利问题（**必填**）
- content_direction：从前置观望种草盘→种草型

buyer_concern_types：
- 只保留带症状前缀的顾虑（如：担心症状加重/怕影响孩子发育）
- 禁止：性价比/价格/渠道/信任/选款（除非带症状前缀）
"""

        # 问题类型抽象化规则（仅用于产品/本地服务）
        abstract_problem_rule = """
=== 【问题类型（problem_type）抽象化规则 - 必须遵守】===
【核心原则】问题识别阶段 = 抽象问题维度，画象生成阶段 = 具体症状表现

**problem_type 必须是抽象的"问题维度"：**
- ✅ 正确：时间精力不足、能力技术不足、特殊人群行动受限、心理情绪障碍、安全信任顾虑
- ❌ 错误：腰酸背痛、拉肚子、腿脚不便（这些是具体症状，应在画像阶段输出）

**问题维度参考分类：**
| 维度 | 含义 | 禁止写成（具体症状） |
|------|------|----------------------|
| 时间精力问题 | 时间不够/精力体力透支 | 腰酸背痛/累得不想动 |
| 能力技术问题 | 技能不足/做不好 | 厨艺不行/怕丢人 |
| 特殊人群问题 | 老人/幼儿/患者行动受限 | 腿脚不便/坐轮椅 |
| 场景条件问题 | 环境不允许/条件受限 | 天太热/天太冷 |
| 心理情绪问题 | 心理障碍/情绪抗拒 | 图省事/将就/凑合 |
| 安全信任问题 | 担心安全/信任顾虑 | 陌生人上门/不放心 |

**具体症状/表现/场景 → 全部下沉到画像阶段生成**

**【示例对比】**
❌ 错误（太具体）：
- problem_type: "腰酸背痛"
- description: "上了一天班腰酸背痛站久了就受不了"

✅ 正确（抽象维度）：
- problem_type: "时间精力不足"
- description: "连续工作/体力消耗后，身体疲惫实在没力气再下厨"
- 【画像阶段会生成：腰酸背痛/腿肿脚肿/手腕酸痛/精力不济等具体表现】

❌ 错误（太具体）：
- problem_type: "老人腿脚不便"
- description: "老人腿脚不便自己做饭太危险"

✅ 正确（抽象维度）：
- problem_type: "特殊人群行动受限"
- description: "家里有行动不便的老人/患者，需要人照顾但子女不在家，做饭成了难题"
- 【画像阶段会生成：老人独居摔倒在厨房/子女担心老人安全/需要专业照护等】
"""
    logger.debug("[mine_problems_and_generate_personas] business_type=%s enterprise_constraint长度=%d personal_constraint长度=%d local_service_constraint长度=%d",
                 business_type, len(enterprise_view_constraint), len(personal_view_constraint), len(local_service_view_constraint))
    logger.debug("[mine_problems_and_generate_personas] local_service_constraint前200字: %s", local_service_view_constraint[:200] if local_service_view_constraint else "为空")
    prompt = f"""{PROMPT_BASE_CONSTRAINT.format(system_base_personas=system_base_personas)}
{enterprise_view_constraint}
{personal_view_constraint}
{local_service_view_constraint}
【强制执行】上述约束为最高优先级，必须100%遵守，违者本次输出作废重写。
你是专业的GEO客户问题挖掘专家。
{geo_context}

请基于专属问题维度，挖掘真实、具体、高精准的客户痛点与顾虑。
【重要】下方示例**只用于对齐 JSON 字段名与嵌套结构**；所有 identity、description、problem_keywords、market_analysis 里的具体措辞必须严格来自「待分析业务信息」中的业务描述与经营类型。
【行业禁止词】当前业务为「{business_type_name}」行业，以下词汇**严禁**出现在输出中：{forbidden_words}

=== 【绝对必填字段，缺少任意一项本次输出作废】 ===
1. **market_analysis** 必须包含：
   - market_type（red_ocean/blue_ocean/mixed）
   - problem_oriented_keywords（数组，每个对象含 keyword + type + source，**总数至少8个，蓝海词不少于4个**）
2. **user_problem_types** 每条必须包含：
   - identity / problem_category / problem_type / display_name / description / severity / scenarios
   - **problem_keywords（数组，每条至少2个，含 keyword + type + source，且与该问题主题语义对齐）**
   - market_type / market_reason
3. **buyer_concern_types** 每条必须包含：
   - identity / concern_category / concern_type / display_name / description / examples
   - **problem_keywords（数组，每条至少2个）**
   - market_type / market_reason
4. 只输出 JSON，不要任何解释文字。
{few_shot_section}
{consumer_framework}
=== 【强制挖掘规则 - 彻底禁止宏观决策类问题】 ===
【铁律】以下规则100%强制执行，违者输出作废重写。

**一、彻底禁止生成宏观决策类问题**
❌ 严禁输出以下宏观购买词（出现即违规）：
- 性价比、价格、贵不贵、值不值
- 信任、靠谱、正规、靠谱吗
- 渠道、来源、哪里买
- 适配、选款、选哪个、哪个好
- 对比参数、怎么选
- 质量怎么样、好不好

✅ 只允许极少数（≤5%）收口用，且必须带具体症状前缀

{consumer_framework}
=== 蓝海/红海判断标准
**market_type 判断规则**（每个问题必须填写）：

**蓝海特征**（满足任一即判定为蓝海）：
1. **细分人群**：身份中包含特定人群标签（婴幼儿/老人/孕妇/患者/过敏体质等）
2. **高严重性 + 长尾**：severity为"极高"或"高"，且问题是特定场景/人群
3. **专业需求**：涉及医疗/健康/安全/法律等专业领域

**红海特征**（不满足蓝海则为红海）：
1. **大众人群**：身份为通用人群（上班族/家庭/年轻人等）
2. **中高严重性**：severity为"中"或"高"
3. **普遍问题**：便利/服务态度等大众痛点（严禁：价格/性价比）

**market_reason**：简述判断理由（10字内）

=== 推理框架 ===
身份多样化：列出至少2-3种不同身份（不能只写"用户"），每种身份下思考其核心问题。

=== 【三层痛点归类规则 - 必须遵守】 ===

**user_problem_types（使用层）- 全部原始搜索动因：**
- 前置客观症状/异常/损耗/不适：拉肚子、过敏、故障、损耗、氧化、发黄、发霉、异味、变色、变形
- 后置使用体验痛点：不方便、不好看、不舒服、影响心情、担心安全
- 注意：这是用户"因为这个问题难受，才主动去搜解决方案"的原始动因
- buyer_concern_types（决策层）禁止侵占此字段

**buyer_concern_types（决策层）- 严格控制≤15%：**
❌ 严禁生成以下宏观顾虑（出现即违规）：
- 怕买贵、怕不值、性价比低
- 怕不专业、怕没资质、怕出问题担责
- 多久回本、投入产出比
- 哪里买、渠道、正规吗

✅ 仅允许极少数（≤15%）且必须带症状前缀：
- 担心症状加重/怕影响健康/怕孩子发育受损
- 症状严重想用好的但预算有限（必须带症状前缀）

**【重要】buyer_concern_types 严格控制在总问题数的15%以内**

**对接层 - 落地执行痛点：**
- 流程对接：审批繁琐、对接人多、沟通成本高
- 落地执行：安装难、配送慢、服务响应差
- 标准执行：验收难、效果难量化、质量不稳定

场景细分：每个问题下列出2-3种具体使用场景，帮助后续画像细分。

=== 【问题挖掘阶段场景约束 - 必须遵守】===
**本阶段只做纯场景标签绑定，不做数字/体量/规模锁定：**
1. 问题必须绑定传入的「主服务场景」（service_scenario），不能脱离场景乱生成
2. 问题描述保持普适性，不写具体数字（不说"100桌婚宴""500人食堂"）
3. 详细现状/症状/细节/规模 → 全部延后到「画像环节」落地
4. 问题层只输出「这个场景下普遍会遇到什么问题」

=== 评分分布参考 ===
=== 评分分布参考 ===
- 核心问题清单只保留 ⭐⭐⭐、⭐⭐⭐⭐、⭐⭐⭐⭐⭐ 三档
- 如果列出5个问题：极高1-2个、高1-2个、中1个
- 如果列出6个问题：极高1-2个、高2个、中1-2个
- 聚焦高优先级痛点，禁止出现 ⭐⭐及以下
=== 市场分析框架 ===
判断这个业务的市场类型：

**market_type 可选值**：
- "red_ocean"（红海）：大品牌垄断、竞争激烈、价格战、利润微薄
- "blue_ocean"（蓝海）：细分市场、差异化机会、竞争少、利润高
- "mixed"（红海中的蓝海）：整体红海，但存在细分蓝海机会

**competition_level（1-10）**：
- 1-3：竞争少，蓝海市场
- 4-6：有一定竞争，需要差异化
- 7-10：竞争激烈，红海市场

**blue_ocean_opportunity**：用一句话说明蓝海机会/差异化方向

**red_ocean_features**：列出2-3个红海特征

**problem_oriented_keywords**：**【必填，必须在market_analysis内部】**问题导向词列表（至少8个），**必须基于关键词筛选维度**：

=== 关键词筛选维度（权重分布：L3+L4=60%，L1+L2+L5=40%） ===

{keyword_filter_context}

=== 关键词筛选执行步骤 ===

**Step 1：生成种子词（严格禁止宏观购买词）**
❌ 严禁生成以下宏观词（L1/L2必须严格控制≤15%）：
- 性价比、价格、贵不贵、值不值
- 信任、靠谱、正规、哪里买
- 怎么选、哪个好、对比参数

✅ 重点生成（L3/L4 ≥85%）：
- L3场景痛点词（重点）：围绕具体身体症状/体感/行为变化
- L4长尾转化词（重点）：围绕具体问题表现/异常反应
- L5地域精准词：地域+具体症状组合

=== 关键词筛选维度 ===
{keyword_filter_context}

**Step 2：推测搜索意图**
按以下形态生成问句（详细说明见后文）：纯关键词提问 + 混合型 + 结构化

=== 问题引导词 ===
{question_guide_context}

**问句格式要求（必须遵守）**：
- 必须以**完整问句**呈现，兼顾人 / 货 / 场
{product_examples}
{bad_examples}

{guard_block}
**Step 3：为每个问题导向词打上蓝海/红海标签**
- **蓝海词**：`type="blue_ocean"` — 来源于 L3 场景痛点词 或 L4 长尾转化词
  - 特征：有细分人群/场景/症状/痛点/避坑
- **红海词**：`type="red_ocean"` — 来源于 L1品牌核心词、L2用户需求词、L5地域精准词
  - 特征：泛品牌词/纯需求词/无场景约束
- **数量要求**：每个问题类型至少 1-2 个 keywords；market_analysis.problem_oriented_keywords **汇总去重，总数至少 8 个，蓝海词不少于 4 个**

{emotion_context}
{chronic_context}
{custom_gift_context_str}
=== 待分析业务信息 ===
请求ID：{_nonce}（每次请求唯一，请务必生成与历史结果不同的问题和关键词）
业务描述：{business_desc}
**主服务场景：{service_scenario}（问题必须绑定此场景，不脱离场景生成）**
{scenario_tag}
经营范围：{business_range_text}
经营类型：{business_type_name}
辅助信息：{aux_section}
{buyer_user_hint}

【随机性要求】这是第「{_nonce}」次分析：
- identity 必须与历史结果不同（不要重复相同人群）
- problem_type / concern_type 必须多样化，不要每次都是"质量"、"价格"、"服务"老三样
- 每个问题的主题角度必须不同：可以从症状/场景/情绪/决策链路/使用阶段等不同维度切入
- 问题严重程度分布要有变化：不要每次都生成完全相同的 severity 分布

=== 严重程度评判标准（仅保留三档） ===

**severity ⭐⭐⭐⭐⭐（极高）**：
- 【已有】已经在危及生命/健康/财产（例：已经住院、已经中毒、已经亏损几十万）
- 【恐惧】怕死/怕致癌/怕出人命/怕家破人亡
- 判断标准：这个问题没解决，用户会家破人亡/倾家荡产/危及生命吗？

**severity ⭐⭐⭐⭐（高）**：
- 【已有】问题已经很严重，明显影响生活（例：宝宝反复生病一个月没好、皮肤烂了、失眠一周）
- 【恐惧】怕变老/变丑/变笨/长不高/孩子出问题
- 判断标准：这个问题没解决，用户生活质量会严重下降吗？

**severity ⭐⭐⭐（中）**：
- 【已有】有点烦但还能忍（例：偶尔不舒服、有点小贵、有点小担心）
- 【恐惧】怕买错/怕被骗/怕选择困难
- 判断标准：用户会纠结很久但不会睡不着觉吗？

**⭐⭐及以下禁止出现（核心问题清单聚焦高优先级痛点）**

=== 强制分布要求 ===
- 问题列表中，「极高」和「高」合计不超过总数的40%
- 「极高」必须少于20%（真正危及生命/健康的问题很少）
- 如果一个业务找不到「极高」或「高」级别的问题，说明这个业务没有强痛点

=== 识别框架 ===
拿到一个业务，按这个顺序思考：
1. 用户现在正在受什么苦？→ 【已有】
2. 用户现在最怕什么？→ 【恐惧】
3. 这个问题没解决，最坏的结果是什么？
4. 用户愿意花多少钱/牺牲什么来解决？（愿意牺牲 = 痛点深）

=== 【重要】问题类型分布 ===
- 已有症状 + 恐惧顾虑 均可以生成，比例由业务本身决定，不强制分配
- 蓝海机会优先聚焦「已有症状」，因为用户正在经历所以搜索意愿更强
- **判断标准**：用户当前是否正在经历这个问题/症状？
  - 正在经历 → 【已有】
  - 担心未来会发生 → 【恐惧】

=== 反例（这些不算高/极高）===
- ✗ "担心质量问题" → 改为："已经用出问题/怕用出问题危及健康"
- ✗ "价格有点贵" → 改为："已经严重影响生活质量/花不起"
- ✗ "不知道选哪个" → 改为："选错了会有严重后果"
- ✗ "怕被骗" → 改为："已经被骗过/怕骗光积蓄"

=== 重要提示 ===
- 不要把「中」的问题人为拔高到「高」
- 如果业务痛点不强，可以返回少量「高」，多返回「中」
- 用户愿意付高价的问题 = 痛苦很深的问题

=== problem_keywords 与当前问题条强对齐（必填，防张冠李戴）===
- **每条** user_problem_types / buyer_concern_types 里的 `problem_keywords`，必须是用户会围绕**该条**的 `problem_type`、`description`、`scenarios`（及付费方的 `examples`）去搜索的完整问句。
- **禁止**把其它问题类型的主题写进本条关键词（例如本条是「餐盘清洁、去油污」，关键词里不得写「餐盘修复/变形矫正」；本条是「服务质量、员工态度」，关键词里不得写「餐盘修复培训」）。
- **禁止**用同一批泛化词复制到每一条；`market_analysis.problem_oriented_keywords` 虽是汇总去重，但**每一条问题自己的 problem_keywords 必须单独构思**，与汇总列表中的对应片段语义一致。
- 自测：随机抽一条，只看 `problem_type+description`，读者应能判断这些 `keyword` 必然属于该条而非邻居条。

=== 输出要求 ===
1. user_problem_types / buyer_concern_types **各生成2-3条**（问题类型必须多样化，覆盖不同身份和场景）。
2. user_problem_types 每条必须包含 scenarios 字段（2-3个具体使用场景）。
3. **【重要】每个问题必须包含 market_type 字段（blue_ocean 或 red_ocean）和 market_reason 字段（判断理由）**。
4. **【重要】每个问题类型（包括 buyer_concern_types）必须包含 `problem_keywords` 字段**，格式为对象数组：
   - `keyword`：完整问句（如{kw_example}）
   - `type`：`"blue_ocean"`（场景痛点词/长尾转化词）或 `"red_ocean"`（品牌核心词/用户需求词/地域精准词）
   - `source`：来源维度名（如"场景痛点词"、"长尾转化词"、"用户需求词"等）
   - **每个问题至少 2 个 keywords**；蓝海问题配蓝海词，红海问题配红海词；**且必须与该条问题主题一致（见上一节强对齐）**
5. **【必填】market_analysis.problem_oriented_keywords 必须返回至少20个**，由所有问题的 problem_keywords **汇总去重**填入；汇总中不得混入与任一问题条无关的「孤儿词」。
6. 只返回 JSON，不要其他文字。
"""

    # ── 【方案一】多样性注入：扩展为 6 套策略池，每次随机选 1-2 套组合 ──
    refresh_round = params.get('refresh_round', 0)

    # 6 套差异化策略，各自侧重的角度不同
    diversity_strategies = [
        (
            "【策略A·细分人群】"
            "重点挖掘：上一轮高频人群之外的细分用户群体，如特殊职业（外卖骑手/自由摄影师/夜班护士）、"
            "边缘年龄段（50岁+初老人群/18岁准成人）、特殊体质/健康状态、特殊地域（下沉市场/边境县城）。"
        ),
        (
            "【策略B·边缘场景】"
            "重点挖掘：非主流使用环境、极端使用条件、特殊时间节点（节后/雨季/深夜/清晨）、"
            "特殊组合场景（同时使用竞品时、多人共用场景、临时替代方案场景）。"
        ),
        (
            "【策略C·交叉痛点】"
            "重点挖掘：同时满足 A+B 两个条件的交叉痛点，即「细分人群+边缘场景」的组合；"
            "以及上一轮问题之间的「中间地带」——那些没有被明确覆盖到的灰色地带。"
        ),
        (
            "【策略D·心理深层】"
            "重点挖掘：表面症状背后的心理动因和决策障碍，如：对效果的怀疑、对价格的纠结、"
            "对时间投入的顾虑、对家人意见的在意、对比价焦虑等心理层面的卡点。"
        ),
        (
            "【策略E·B端采购视角】"
            "从付费决策者（老板/采购/家属）的视角出发，挖掘他们在购买决策时真实关心的问题："
            "不是用户用得爽不爽，而是「值不值」「安不安全」「难不难管」「竞争对手用什么」。"
        ),
        (
            "【策略F·逆向思维】"
            "主动从「用了产品之后的常见抱怨」和「买之前最担心什么」两个角度逆向生成问题；"
            "包括售后纠纷、期望落差、使用门槛、不适合人群等常规分析容易遗漏的角度。"
        ),
    ]

    # 第一轮也要有多样性要求，只是指导方向不同
    if refresh_round == 0:
        # 首次生成时，要求生成多种不同维度的问题
        prompt += f"""
【首次生成·多样性要求】
请从以下多个维度生成问题，确保覆盖不同角度：
1. 时间维度：什么场景下没时间/来不及？
2. 能力维度：什么情况下自己做不了/做不好？
3. 场景维度：什么特殊场合需要解决方案？
4. 便利维度：什么情况下图方便/不想动？
5. 人群维度：哪些细分人群有特殊需求？
"""
    elif refresh_round > 0:
        # 6 套差异化策略，各自侧重的角度不同
        diversity_strategies = [
            (
                "【策略A·细分人群】"
                "重点挖掘：上一轮高频人群之外的细分用户群体，如特殊职业（外卖骑手/自由摄影师/夜班护士）、"
                "边缘年龄段（50岁+初老人群/18岁准成人）、特殊体质/健康状态、特殊地域（下沉市场/边境县城）。"
            ),
            (
                "【策略B·边缘场景】"
                "重点挖掘：非主流使用环境、极端使用条件、特殊时间节点（节后/雨季/深夜/清晨）、"
                "特殊组合场景（同时使用竞品时、多人共用场景、临时替代方案场景）。"
            ),
            (
                "【策略C·交叉痛点】"
                "重点挖掘：同时满足 A+B 两个条件的交叉痛点，即「细分人群+边缘场景」的组合；"
                "以及上一轮问题之间的「中间地带」——那些没有被明确覆盖到的灰色地带。"
            ),
            (
                "【策略D·心理深层】"
                "重点挖掘：表面症状背后的心理动因和决策障碍，如：对效果的怀疑、对价格的纠结、"
                "对时间投入的顾虑、对家人意见的在意、对比价焦虑等心理层面的卡点。"
            ),
            (
                "【策略E·B端采购视角】"
                "从付费决策者（老板/采购/家属）的视角出发，挖掘他们在购买决策时真实关心的问题："
                "不是用户用得爽不爽，而是「值不值」「安不安全」「难不难管」「竞争对手用什么」。"
            ),
            (
                "【策略F·逆向思维】"
                "主动从「用了产品之后的常见抱怨」和「买之前最担心什么」两个角度逆向生成问题；"
                "包括售后纠纷、期望落差、使用门槛、不适合人群等常规分析容易遗漏的角度。"
            ),
        ]

        import random, time
        # 每次换一批基于 round + 时间戳选择策略组合，保证同 round 不同次点击有不同的策略
        # round 决定基准池大小（round 越大组合越丰富），时间戳的纳秒位引入随机性
        seed = int(time.time() * 1000000) % 100000 + refresh_round * 7
        rng = random.Random(seed)
        # round 小的时候选 1 个策略，round 大了选 2 个策略组合
        num_strategies = 1 if refresh_round <= 2 else (2 if refresh_round <= 4 else rng.randint(2, 3))
        chosen = rng.sample(diversity_strategies, min(num_strategies, len(diversity_strategies)))
        strategy_text = "\n".join(chosen)
        prompt += f"\n\n【换一批·第{refresh_round}轮·多样性要求】\n{strategy_text}"

    # ── 【方案四】pool 枯竭重置：连续低质量轮次后，强制从零生成 ──
    force_fresh = params.get('force_fresh', False)
    if force_fresh:
        # 告诉 LLM 不要依赖历史，直接以全新视角生成
        prompt += (
            "\n\n【重要·强制刷新】"
            "请以完全陌生的视角重新生成，不要参考任何历史问题。"
            "重点关注：之前未被覆盖的全新人群、全新场景、全新痛点维度。"
        )
        # 清空 exclude_problems
        exclude_problems = []

    # ── 【方案二】去重注入：扩大范围 + 包含 description，让 LLM 真正判断重复 ──
    exclude_problems = params.get('exclude_problems', [])
    if exclude_problems:
        # 扩大至 30 条（12 → 30）
        exclude_list = exclude_problems[:30]
        exclude_lines = "\n".join([
            f"- 身份:{p.get('identity', '未知')} | 问题:{p.get('problem_type', p.get('concern_type', '未知'))} | 描述:{p.get('description', p.get('concern_description', ''))[:80]}"
            for p in exclude_list
        ])
        prompt += (
            f"\n\n【已生成过的问题，请主动避免重复】"
            f"\n共 {len(exclude_list)} 条历史问题：\n{exclude_lines}"
            f"\n判断重复的标准：identity 相似 OR problem_type 本质相同 OR description 核心痛点重叠，"
            f"满足任一条件即为重复，必须替换。"
        )

    try:
        MAX_RETRIES = 3
        final_result = None

        # --- 辅助函数（定义在循环外，避免重复定义） ---
        def _try_parse(text):
            try:
                return json.loads(text.strip())
            except json.JSONDecodeError:
                return None

        def _smart_fix_json(text):
            for strategy in range(7):
                test_json = text
                if strategy == 0:
                    last_brace = test_json.rfind('}')
                    if last_brace > 0:
                        test_json = test_json[:last_brace + 1]
                elif strategy == 1:
                    last_bracket = test_json.rfind(']')
                    if last_bracket > 0:
                        test_json = test_json[:last_bracket + 1]
                        open_braces = test_json.count('{') - test_json.count('}')
                        open_brackets = test_json.count('[') - test_json.count(']')
                        test_json += ']' * max(0, open_brackets)
                        test_json += '}' * max(0, open_braces)
                elif strategy == 2:
                    last_comma_newline = test_json.rfind(',\n')
                    if last_comma_newline > 0:
                        test_json = test_json[:last_comma_newline]
                        open_braces = test_json.count('{') - test_json.count('}')
                        open_brackets = test_json.count('[') - test_json.count(']')
                        test_json += ']' * max(0, open_brackets)
                        test_json += '}' * max(0, open_braces)
                elif strategy == 3:
                    open_braces = test_json.count('{') - test_json.count('}')
                    open_brackets = test_json.count('[') - test_json.count(']')
                    test_json += ']' * max(0, open_brackets)
                    test_json += '}' * max(0, open_braces)
                elif strategy == 4:
                    depth = 0
                    for i in range(len(test_json) - 1, -1, -1):
                        if test_json[i] == '}':
                            depth += 1
                        elif test_json[i] == '{':
                            depth -= 1
                            if depth == 0:
                                test_json = test_json[:i]
                                break
                elif strategy == 5:
                    import re as re_module
                    matches = list(re_module.finditer(r'"\s*\}\s*[,}\]]', test_json))
                    if matches:
                        last_match = matches[-1]
                        test_json = test_json[:last_match.end()]
                        open_braces = test_json.count('{') - test_json.count('}')
                        open_brackets = test_json.count('[') - test_json.count(']')
                        test_json += ']' * max(0, open_brackets)
                        test_json += '}' * max(0, open_braces)
                elif strategy == 6:
                    lines = test_json.split('\n')
                    fixed_lines = []
                    for line in lines:
                        stripped = line.strip()
                        if stripped.startswith('"') and ':' not in stripped and '}' not in stripped:
                            continue
                        quote_count = stripped.count('"')
                        if quote_count % 2 != 0 and not stripped.endswith(','):
                            continue
                        fixed_lines.append(line)
                    test_json = '\n'.join(fixed_lines)
                    open_braces = test_json.count('{') - test_json.count('}')
                    open_brackets = test_json.count('[') - test_json.count(']')
                    test_json += ']' * max(0, open_brackets)
                    test_json += '}' * max(0, open_braces)
                parsed = _try_parse(test_json)
                if parsed:
                    logger.debug("[mine_problems_and_generate_personas] JSON修复成功(策略%s)", strategy)
                    return parsed
            return None

        def _extract_problem_keywords(item):
            raw = item.get('problem_keywords') or item.get('keywords') or []
            if isinstance(raw, str):
                return [{'keyword': raw, 'type': 'unknown', 'source': '未知'}]
            if isinstance(raw, list):
                result = []
                for kw_item in raw:
                    if isinstance(kw_item, dict):
                        result.append({
                            'keyword': kw_item.get('keyword') or kw_item.get('kw') or '',
                            'type': kw_item.get('type', 'unknown'),
                            'source': kw_item.get('source', kw_item.get('type', '未知')),
                        })
                    elif isinstance(kw_item, str) and kw_item:
                        result.append({'keyword': kw_item, 'type': 'unknown', 'source': '未知'})
                return result
            return []

        # --- 重试循环 ---
        for attempt in range(MAX_RETRIES):
            attempt_suffix = "" if attempt == 0 else (
                "\n\n【重试提醒（第" + str(attempt + 1) + "次）】"
                "上次输出缺少 problem_keywords 或 market_analysis.problem_oriented_keywords，"
                "本次必须为每条 user_problem_types 和 buyer_concern_types 补全 problem_keywords 字段，"
                "并确保 market_analysis.problem_oriented_keywords 至少包含8个关键词，user_problem_types 至少2条，buyer_concern_types 至少2条。"
            )

            # 调试日志：检查约束是否注入到prompt
            logger.debug("[mine_problems_and_generate_personas] prompt中含local_service约束=%s prompt长度=%d",
                         "本地服务/专业服务问题挖掘视角约束" in prompt, len(prompt))
            logger.debug("[mine_problems_and_generate_personas] prompt前800字: %s", prompt[:800])
            response = llm.chat(prompt + attempt_suffix, temperature=0.3, max_tokens=8000)
            if not response:
                logger.debug("[mine_problems_and_generate_personas] LLM 返回空响应")
                return {'success': False, 'error': 'empty_response', 'message': 'LLM 返回空响应，请重试'}

            logger.debug("[mine_problems_and_generate_personas] 响应长度: %s", len(response))
            logger.debug("[mine_problems_and_generate_personas] LLM 原始响应末尾500字符: %s", response[-500:] if response else None)

            result = None
            result = _try_parse(response)
            if result:
                logger.debug("[mine_problems_and_generate_personas] JSON解析成功(直接)")
                logger.debug("[mine_problems_and_generate_personas] ===== LLM 解析结果 =====")
                logger.debug("%s", json.dumps(result, ensure_ascii=False)[:500])
                logger.debug("[mine_problems_and_generate_personas] ===== 解析结果结束 =====")
            else:
                match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
                if match:
                    json_str = match.group(1).strip()
                    result = _try_parse(json_str)
                    if not result:
                        result = _smart_fix_json(json_str)
                    if result:
                        logger.debug("[mine_problems_and_generate_personas] JSON解析成功(代码块内)")
                        logger.debug("[mine_problems_and_generate_personas] ===== LLM 解析结果 =====")
                        logger.debug("%s", json.dumps(result, ensure_ascii=False)[:500])
                        logger.debug("[mine_problems_and_generate_personas] ===== 解析结果结束 =====")
                else:
                    match = re.search(r'\{[\s\S]*\}', response)
                    if match:
                        json_str = match.group(0)
                        result = _try_parse(json_str)
                        if not result:
                            result = _smart_fix_json(json_str)
                        if result:
                            logger.debug("[mine_problems_and_generate_personas] JSON解析成功(对象匹配)")
                            logger.debug("[mine_problems_and_generate_personas] ===== LLM 解析结果 =====")
                            logger.debug("%s", json.dumps(result, ensure_ascii=False)[:500])
                            logger.debug("[mine_problems_and_generate_personas] ===== 解析结果结束 =====")

            if not result:
                logger.debug("[mine_problems_and_generate_personas] ===== LLM完整响应 =====")
                logger.debug("%s", response[:500] if response else None)
                logger.debug("[mine_problems_and_generate_personas] ===== 响应结束 =====")
                if attempt < MAX_RETRIES - 1:
                    logger.info("[mine_problems_and_generate_personas] 解析失败，将重试(第%d次)", attempt + 1)
                    continue
                else:
                    return {'success': False, 'message': 'AI生成失败，未能解析出有效数据'}

            # 三盘 → 内容方向映射（枚举原文直译）
            base_map = {
                '刚需痛点盘': '转化型',
                '前置观望种草盘': '种草型',
                '使用配套搜后种草盘': '种草型',
            }

            # 旧枚举兼容映射（防止历史数据无法解析）
            base_map_legacy = {
                '刚需痛点': '转化型',
                '前置观望': '种草型',
                '使用配套': '种草型',
            }
            base_map = {**base_map_legacy, **base_map}

            # --- 规范化处理（函数式写法，避免缩进陷阱） ---
            def _norm(item, is_problem=True):
                type_key = 'problem_type' if is_problem else 'concern_type'
                base_key = 'problem_base' if is_problem else 'concern_base'
                desc_key = 'display_name'
                raw_type = item.get(type_key, '') or item.get('问题类型', '') or item.get('顾虑类型', '') or ''
                display = item.get(desc_key, '') or item.get('显示名称', '') or item.get('描述', '') or ''
                if not raw_type and display:
                    for kw in (['不便','困扰','问题','烦恼','困难','担忧','焦虑','缺乏','不足','担心','无奈','难受','痛点','需求','期望'] if is_problem else ['价格','质量','真假','安全','效果','配送','售后','信任','顾虑','担忧','预算','怕','犹豫','便利','交期','开票','起订','采购','品牌']):
                        idx = display.find(kw)
                        if idx > 0:
                            raw_type = display[idx:]
                            break
                    if not raw_type:
                        raw_type = display
                return {
                    'id': item.get('id', ''),
                    'identity': item.get('identity', '') or item.get('身份', ''),
                    type_key: raw_type,
                    base_key: item.get(base_key, '') or item.get('需求底盘', ''),
                    'display_name': display or f"{item.get('identity', '')}{raw_type}",
                    'description': item.get('description', '') or item.get('描述', ''),
                    'examples': item.get('examples', []) or item.get('例子', []),
                    'severity': item.get('severity', '中') or item.get('严重程度', '中'),
                    'scenarios': item.get('scenarios', []) or item.get('场景', []),
                    'market_type': item.get('market_type', 'red_ocean'),
                    'market_reason': item.get('market_reason', ''),
                    'problem_keywords': _extract_problem_keywords(item),
                }

            user_problem_types = result.get('user_problem_types', [])
            buyer_concern_types = result.get('buyer_concern_types', [])
            buyer_user_relation = result.get('buyer_user_relation', {})
            portraits_by_type = result.get('portraits_by_type', {})
            market_analysis = result.get('market_analysis', {}) or {}

            all_user_problem_types = []
            for i, item in enumerate(user_problem_types):
                n = _norm(item, True)
                raw_base = item.get('problem_base') or item.get('concern_base') or ''
                description = n['description'] or ''
                problem_type = n['problem_type'] or ''
                severity = n['severity'] or '中'

                # ── 四类种草原生问题强制归入「前置观望种草盘」────────────────
                # 强制约束：全部强制入库「前置观望种草盘」，不允许分流到另外两盘
                if is_seeding_problem(problem_type, description):
                    base = PROBLEM_BASE_SOUQIAN_ZHONGCAO
                    logger.debug("[mine_problems] 四类种草原生问题强制归入前置观望种草盘: %s", problem_type)
                else:
                    base = raw_base

                direction = base_map.get(base, base_map.get(raw_base, '种草型'))

                # ── 双标签自动打标（兼容模式，不改动原有API字段结构）──────────
                # consume_type: 必需 / 增量
                # demand_attr: 功能驱动 / 场景情绪驱动
                # 规则原文：损坏/替换/效果差/性价比诉求 = 必需 + 功能驱动
                #           仪式感/场景穿搭/爱好生活 = 增量 + 场景情绪驱动
                consume_type = auto_tag_consume_type(problem_type, description, severity)
                demand_attr = auto_tag_demand_attr(problem_type, description)

                all_user_problem_types.append({
                    'id': n.get('id', f'up_{i+1}'),
                    'identity': n['identity'],
                    'problem_base': base,
                    'problem_type': n['problem_type'],
                    'display_name': n['display_name'] or f"{n['identity']}{n['problem_type']}",
                    'description': n['description'],
                    'severity': n['severity'],
                    'scenarios': n['scenarios'],
                    'market_type': n['market_type'],
                    'market_reason': n['market_reason'],
                    'problem_keywords': n['problem_keywords'],
                    'content_direction': direction,
                    # ── 新增双标签字段（兼容历史数据，未填写时自动回退）───────────
                    'consume_type': consume_type,
                    'demand_attr': demand_attr,
                })

            all_buyer_concern_types = []
            for i, item in enumerate(buyer_concern_types):
                n = _norm(item, False)
                raw_base = item.get('concern_base') or ''
                description = n['description'] or ''
                concern_type = n['concern_type'] or ''
                severity = n['severity'] or '高'

                # ── 四类种草原生问题强制归入「前置观望种草盘」（付费方同理）──
                if is_seeding_problem(concern_type, description):
                    base = PROBLEM_BASE_SOUQIAN_ZHONGCAO
                else:
                    base = raw_base

                direction = base_map.get(base, base_map.get(raw_base, '种草型'))

                # ── 双标签自动打标（付费方）───────────────────────────────────
                consume_type = auto_tag_consume_type(concern_type, description, severity)
                demand_attr = auto_tag_demand_attr(concern_type, description)

                all_buyer_concern_types.append({
                    'id': n.get('id', f'bc_{i+1}'),
                    'identity': n['identity'],
                    'concern_base': base,
                    'concern_type': n['concern_type'],
                    'display_name': n['display_name'] or f"{n['identity']}{n['concern_type']}",
                    'description': n['description'],
                    'examples': n['examples'],
                    'severity': '高',
                    'market_type': n['market_type'],
                    'market_reason': n['market_reason'],
                    'problem_keywords': n['problem_keywords'],
                    'content_direction': direction,
                    # ── 新增双标签字段（兼容历史数据）─────────────────────────────
                    'consume_type': consume_type,
                    'demand_attr': demand_attr,
                })

            all_problem_keywords = [kw for item in all_user_problem_types for kw in item['problem_keywords']]
            all_problem_keywords += [kw for item in all_buyer_concern_types for kw in item['problem_keywords']]

            logger.debug("[mine_problems_and_generate_personas] LLM返回的market_analysis: %s", market_analysis)
            logger.debug("[mine_problems_and_generate_personas] result中problem_oriented_keywords: %s", result.get('problem_oriented_keywords', '字段不存在'))
            logger.debug("[mine_problems_and_generate_personas] user_problem_types[0]: %s", user_problem_types[0] if user_problem_types else '无')
            logger.debug("[mine_problems_and_generate_personas] user_problem_types[0]的market_type: %s", user_problem_types[0].get('market_type', '无') if user_problem_types else '无')
            logger.debug("[mine_problems_and_generate_personas] user_problem_types[0]的problem_keywords: %s", user_problem_types[0].get('problem_keywords', '无') if user_problem_types else '无')

            raw_keywords = market_analysis.get('problem_oriented_keywords') or result.get('problem_oriented_keywords') or []
            seen = set()
            for kw_item in raw_keywords:
                kw = (kw_item.get('keyword') or kw_item.get('kw') or '') if isinstance(kw_item, dict) else (kw_item or '')
                if kw:
                    seen.add(kw)
            fallback_keywords = []
            for kw_item in all_problem_keywords:
                kw = kw_item.get('keyword', '') or ''
                if kw and kw not in seen:
                    seen.add(kw)
                    fallback_keywords.append(kw_item)
            merged_keywords = raw_keywords + fallback_keywords if raw_keywords else fallback_keywords

            blue_ocean_keywords = []
            red_ocean_keywords = []
            for item in merged_keywords:
                if isinstance(item, dict):
                    kw = item.get('keyword') or item.get('kw') or ''
                    kw_type = item.get('type', '')
                    if kw and kw_type:
                        if kw_type == 'blue_ocean':
                            blue_ocean_keywords.append({'keyword': kw, 'source': item.get('source', kw_type)})
                        elif kw_type == 'red_ocean':
                            red_ocean_keywords.append({'keyword': kw, 'source': item.get('source', kw_type)})
                elif isinstance(item, str) and item:
                    blue_ocean_keywords.append({'keyword': item, 'source': '未知'})

            normalized_market_analysis = {
                'market_type': market_analysis.get('market_type', 'mixed'),
                'market_type_display': market_analysis.get('market_type_display', '待分析'),
                'competition_level': market_analysis.get('competition_level', 5),
                'competition_level_display': market_analysis.get('competition_level_display', '待评估'),
                'blue_ocean_opportunity': market_analysis.get('blue_ocean_opportunity', ''),
                'red_ocean_features': market_analysis.get('red_ocean_features', []),
                'problem_oriented_keywords': merged_keywords,
                'blue_ocean_keywords': blue_ocean_keywords,
                'red_ocean_keywords': red_ocean_keywords,
            }

            # --- 校验必填字段 ---
            missing_keywords_problems = [
                f"{item.get('identity', '')}{item.get('problem_type', '')}"
                for item in user_problem_types
                if not item.get('problem_keywords')
            ]
            missing_keywords_concerns = [
                f"{item.get('identity', '')}{item.get('concern_type', '')}"
                for item in buyer_concern_types
                if not item.get('problem_keywords')
            ]
            missing_analysis = not market_analysis.get('problem_oriented_keywords')

            # 只有当所有字段都完整时才跳过重试
            validation_passed = not (missing_keywords_problems or missing_keywords_concerns or missing_analysis)

            # 构建 merged_keywords（从各条问题的 problem_keywords 汇总）
            merged_keywords = market_analysis.get('problem_oriented_keywords') or []
            for kw_item in all_problem_keywords:
                kw = kw_item.get('keyword', '') or ''
                if kw:
                    # 检查是否已存在
                    exists = any(
                        (isinstance(x, dict) and x.get('keyword') == kw) or
                        (isinstance(x, str) and x == kw)
                        for x in merged_keywords
                    )
                    if not exists:
                        merged_keywords.append(kw_item)

            # 分离蓝海/红海关键词
            blue_ocean_keywords = []
            red_ocean_keywords = []
            for item in merged_keywords:
                if isinstance(item, dict):
                    kw = item.get('keyword') or item.get('kw') or ''
                    kw_type = item.get('type', '')
                    if kw and kw_type:
                        if kw_type == 'blue_ocean':
                            blue_ocean_keywords.append({'keyword': kw, 'source': item.get('source', kw_type)})
                        elif kw_type == 'red_ocean':
                            red_ocean_keywords.append({'keyword': kw, 'source': item.get('source', kw_type)})
                elif isinstance(item, str) and item:
                    blue_ocean_keywords.append({'keyword': item, 'source': '未知'})

            normalized_market_analysis = {
                'market_type': market_analysis.get('market_type', 'mixed'),
                'market_type_display': market_analysis.get('market_type_display', '待分析'),
                'competition_level': market_analysis.get('competition_level', 5),
                'competition_level_display': market_analysis.get('competition_level_display', '待评估'),
                'blue_ocean_opportunity': market_analysis.get('blue_ocean_opportunity', ''),
                'red_ocean_features': market_analysis.get('red_ocean_features', []),
                'problem_oriented_keywords': merged_keywords,
                'blue_ocean_keywords': blue_ocean_keywords,
                'red_ocean_keywords': red_ocean_keywords,
            }

            if not validation_passed:
                missing_info = []
                if missing_keywords_problems:
                    missing_info.append(f"user_problem_types缺少problem_keywords: {missing_keywords_problems}")
                if missing_keywords_concerns:
                    missing_info.append(f"buyer_concern_types缺少problem_keywords: {missing_keywords_concerns}")
                if missing_analysis:
                    missing_info.append("market_analysis.problem_oriented_keywords 缺失")
                if attempt < MAX_RETRIES - 1:
                    logger.info("[mine_problems_and_generate_personas] 校验失败，将重试: %s", '；'.join(missing_info))
                    continue
                else:
                    logger.warning("[mine_problems_and_generate_personas] 校验失败，已达最大重试次数，使用兜底数据: %s", '；'.join(missing_info))

            final_result = {
                'success': True,
                'data': {
                    'market_analysis': normalized_market_analysis,
                    'user_problem_types': all_user_problem_types,
                    'buyer_concern_types': all_buyer_concern_types,
                    'buyer_user_relation': buyer_user_relation,
                    'portraits_by_type': dict(portraits_by_type),
                    'is_premium': params.get('_is_premium', False),
                    # 【GEO战略配置】
                    'geo_strategy': {
                        'strategy_name': geo_strategy.get("strategy_name", ""),
                        'core_psychology': geo_strategy.get("core_psychology", ""),
                        'problem_focus': geo_strategy.get("problem_focus", []),
                        'trust_types': geo_strategy.get("trust_types", []),
                        'role_mode': geo_strategy.get("role_mode", ""),
                        'content_plate_ratio': geo_strategy.get("content_plate_ratio", {}),
                        'geo_focus': geo_strategy.get("geo_focus", []),
                        'cta_style': geo_strategy.get("cta_style", ""),
                        'must_have_keywords': geo_strategy.get("must_have_keywords", []),
                        'is_high_risk_decision': geo_strategy.get("high_risk_decision", False),
                        'is_high_risk_enhanced': geo_strategy.get("is_high_risk_enhanced", False),
                    },
                    # 【新增】慢性体征解析层结果
                    'chronic_extraction': {
                        'behavior_tags': behavior_tags,
                        'scene_tags': scene_tags,
                        'symptom_tags': symptom_tags,
                        'extraction_summary': chronic_extraction_summary,
                        'chronic_problems': chronic_problems,
                    },
                    'custom_gift_extraction': {
                        'is_custom_gift': bool(is_custom_gift),
                        'matched_rituals': (custom_gift_context or {}).get('matched_rituals', []),
                        'custom_gift_problems': custom_gift_problems,
                    },
                }
            }
            break  # 跳出重试循环

        return final_result

    except Exception as e:
        import traceback
        logger.error("[mine_problems_and_generate_personas] 异常: %s", str(e))
        logger.debug("[mine_problems_and_generate_personas] 堆栈: %s", traceback.format_exc())
        return {'success': False, 'message': f'生成失败: {str(e)}'}


def generate_portraits(params: Dict[str, Any]) -> Dict:
    """
    基于指定问题生成人群画像

    Args:
        params: {
            'business_description': str,
            'problem': Dict,  # 包含 id, identity, problem_type, display_name, description, scenario
            'portrait_count': int,  # 画像数量（免费默认2，付费默认5）
            '_is_premium': bool,
            'chronic_extraction': Dict,  # 【新增】慢性体征解析层结果（可选）
        }

    Returns:
        包含画像列表
    """
    import re
    import os
    from services.llm import LLMService

    is_premium = params.get('_is_premium', False)

    # 模型选择：免费用 PLUS(14B)，付费用 DeepSeek-V3（硅基流动）
    provider = 'siliconflow'
    base_url = 'https://api.siliconflow.cn/v1'
    api_key = os.environ.get('LLM_API_KEY', '')

    if is_premium:
        model = os.environ.get('LLM_MODEL_PREMIUM', 'deepseek-ai/DeepSeek-V3')
    else:
        model = os.environ.get('LLM_MODEL_PLUS', 'Qwen/Qwen2.5-14B-Instruct')

    llm = LLMService(provider=provider, model=model)
    llm.base_url = base_url
    llm.api_key = api_key

    logger.info("[generate_portraits] 使用配置: provider=%s, model=%s", provider, model)

    business_desc = params.get('business_description', '')
    problem = params.get('problem', {})
    portrait_count = params.get('portrait_count', 5 if is_premium else 2)
    service_scenario = params.get('service_scenario', 'other')
    business_type = params.get('business_type', 'local_service')

    # 【新增】获取慢性体征解析层结果
    chronic_extraction = params.get('chronic_extraction', {})
    behavior_tags = chronic_extraction.get('behavior_tags', [])
    scene_tags = chronic_extraction.get('scene_tags', [])
    symptom_tags = chronic_extraction.get('symptom_tags', [])
    is_chronic_problem = problem.get('is_chronic_symptom', False)

    if not business_desc or not problem:
        return {
            'success': False,
            'message': '缺少业务描述或问题信息'
        }

    # 获取系统固定底座人群
    system_base_personas = get_system_base_personas(service_scenario, business_type)

    # 识别行业场景（新增）
    industry_scene = identify_industry_scene(business_desc, service_scenario)
    industry_context = build_industry_scene_context(business_desc, service_scenario, industry_scene)

    # 【新增】构建行为场景体征上下文
    chronic_context = ""
    if behavior_tags or scene_tags or symptom_tags:
        chronic_context = f"""
=== 【常驻行为+固定场景+慢性体征上下文】（来自前置解析层）===
【常驻行为标签】：{', '.join(behavior_tags) if behavior_tags else '无'}
【固定场景标签】：{', '.join(scene_tags) if scene_tags else '无'}
【慢性体征标签】：{', '.join(symptom_tags) if symptom_tags else '无'}
"""
        if is_chronic_problem:
            chronic_context += """
【本问题为慢性体征类问题】
- 画像必须同步继承常驻行为、固定场景、慢性体征标签
- portrait_summary 五要素中必须植入长期习惯痛点
- 搜索行为预判必须补充久坐/伏案/工位养护类搜索词
"""

    # 根据业务类型获取画像生成的问题维度映射
    if business_type in ('product', 'local_service'):
        # 消费类产品/本地服务的问题维度映射
        portrait_problem_mapping = """
**问题类型 → 具体表现映射规则：**

| 问题识别阶段 (problem_type) | 画像生成阶段 (具体表现) |
|---------------------------|----------------------|
| 时间精力不足 | 腰酸背痛/腿肿脚肿/手腕酸痛/精力不济/累得不想动 |
| 能力技术不足 | 厨艺不行/怕丢人/不会做/做不好 |
| 特殊人群行动受限 | 老人独居摔倒在厨房/腿脚不便进厨房危险/需要照护 |
| 身体机能问题 | 肠胃不适/食欲差/精力跟不上/睡眠不好 |
| 心理情绪障碍 | 图省事/将就/凑合/烦躁/不想面对 |
| 安全信任顾虑 | 陌生人上门/不放心/担心安全 |

**示例：**
- problem_type: "时间精力不足"
- portrait_summary 中应体现：上了一天班腰酸背痛站久了就受不了/回家根本不想动只想躺着
- symptom_tags 应包含：["腰酸背痛", "腿肿脚肿", "手腕酸痛", "精力不济"]
- 搜索行为应体现：会搜索"腰酸背痛怎么缓解"/"站久了腿肿怎么办"
"""
        portrait_tags_examples = """
            "behavior_tags": ["常驻行为标签，如：久坐、长期伏案"],
            "scene_tags": ["固定场景标签，如：办公室、工位"],
            "symptom_tags": ["慢性体征标签，如：腰酸背痛、颈椎僵硬"],
            "search_intent_supplement": ["久坐/伏案/工位养护类搜索词补充"]
"""
    elif business_type == 'personal':
        # 个人专业服务的问题维度映射
        portrait_problem_mapping = """
**问题类型 → 具体表现映射规则：**

| 问题识别阶段 (problem_type) | 画像生成阶段 (具体表现) |
|---------------------------|----------------------|
| 权益受侵害 | 工资被拖欠/合同被违约/隐私被泄露/权益被剥夺 |
| 纠纷风险 | 争吵冲突/调解失败/诉讼成本/时间精力消耗 |
| 法律风险 | 责任认定不清/赔偿金额争议/证据不足/法律程序复杂 |
| 维权障碍 | 投诉无门/举证困难/维权成本高/时间周期长 |

**示例：**
- problem_type: "劳动权益受侵害"
- portrait_summary 中应体现：被拖欠工资几个月/劳动合同被随意解除/被迫签署不平等协议
- symptom_tags 应包含：["工资拖欠", "合同违约", "被迫离职", "权益受损"]
- 搜索行为应体现：会搜索"工资拖欠怎么办"/"被迫签离职申请违法吗"/"劳动仲裁流程"
"""
        portrait_tags_examples = """
            "behavior_tags": ["职场行为标签，如：加班多、合同签订"],
            "scene_tags": ["固定场景标签，如：职场、租房、消费场所"],
            "symptom_tags": ["权益受损标签，如：工资拖欠、合同纠纷"],
            "search_intent_supplement": ["权益保障/法律维权类搜索词补充"]
"""
    elif business_type == 'enterprise':
        # 企业专业服务的问题维度映射
        portrait_problem_mapping = """
**问题类型 → 具体表现映射规则：**

| 问题识别阶段 (problem_type) | 画像生成阶段 (具体表现) |
|---------------------------|----------------------|
| 劳动纠纷风险 | 劳动合同不规范/加班费争议/离职赔偿纠纷/社保缴纳不合规 |
| 合同审核风险 | 条款漏洞/违约责任不清/知识产权归属争议/保密协议缺失 |
| 合规风险 | 税务合规问题/劳动用工不合规/数据安全问题/行业监管要求 |
| 知识产权风险 | 商标被抢注/专利被侵权/商业秘密泄露/软件著作权纠纷 |

**示例：**
- problem_type: "劳动纠纷风险"
- portrait_summary 中应体现：大量用工时劳动合同签订不规范/加班费计算方式争议/员工离职赔偿纠纷频发
- symptom_tags 应包含：["劳动合同不规范", "加班费争议", "离职赔偿纠纷", "用工合规风险"]
- 搜索行为应体现：会搜索"劳动合同怎么签才规范"/"加班费怎么计算"/"员工离职赔偿标准"
"""
        portrait_tags_examples = """
            "behavior_tags": ["企业经营行为标签，如：招聘多、用工量大"],
            "scene_tags": ["固定场景标签，如：HR部门、法务部门"],
            "symptom_tags": ["企业风险标签，如：劳动纠纷、合同风险、合规问题"],
            "search_intent_supplement": ["企业合规/法律风险类搜索词补充"]
"""
    else:
        portrait_problem_mapping = ""
        portrait_tags_examples = """
            "behavior_tags": [],
            "scene_tags": [],
            "symptom_tags": [],
            "search_intent_supplement": []
"""

    # 构建画像生成提示词
    prompt = f"""{PROMPT_BASE_CONSTRAINT.format(system_base_personas=system_base_personas)}
你是用户画像分析专家。请根据业务信息和指定问题，深度分析使用者与付费者的需求，生成精准画像。

=== 业务信息 ===
{business_desc}

=== 行业场景识别（新增字段，必须注入画像）===
行业场景类型：{industry_scene}
场景专属痛点：{', '.join(industry_context.get('scene_pain_points', []))}
信任诉求（trust_demand）：{', '.join([f"{t['dimension']}：{t['description']}" for t in industry_context.get('trust_demand', [])])}
GEO内容方向：解决方案导向 + 信任背书（所有选题必须围绕信任诉求展开）

{chronic_context}
=== 指定问题 ===
- 问题ID: {problem.get('id', '')}
- 目标客户: {problem.get('identity', '')}
- 问题类型: {problem.get('problem_type', '')}
- 问题描述: {problem.get('description', '')}
- 使用场景候选: {problem.get('scenarios', ['通用'])}
- 严重程度: {problem.get('severity', '中')}
- 买用关系: {problem.get('buyer_user_relation', '自用')}
- 需求底盘（problem_base）: {problem.get('problem_base', '待识别')}
- 消费类型（consume_type）: {problem.get('consume_type', '待打标')}（必需=硬需求，增量=种草需求）
- 需求属性（demand_attr）: {problem.get('demand_attr', '待打标')}（功能驱动=关注效果/性价比，场景情绪驱动=关注仪式感/情绪价值）

=== 【画像生成：具体症状/表现下沉规则】===
【重要】问题识别阶段输出的 problem_type 是抽象问题维度，画像生成阶段必须将其具体化！

{portrait_problem_mapping}
**画像生成要求：**
1. 基于上方抽象问题类型（problem_type），生成该维度下的具体症状/表现/人群体征
2. portrait_summary 中的"问题/症状"必须具体，不能重复 problem_type 的抽象描述
3. symptom_tags、behavior_tags、scene_tags 必须填充具体标签
4. 搜索行为预判必须基于具体症状，而不是抽象问题类型

=== 核心思维 - 三层痛点归类 ===

**user_problem_types（使用层）- 全部原始搜索动因：**
- 前置客观症状/异常/损耗/不适：拉肚子、过敏、故障、损耗、氧化、发黄、发霉、异味
- 后置使用体验痛点：不方便、不好看、不舒服、影响心情、担心安全
- 注意：这是用户"因为这个问题难受，才主动去搜解决方案"的原始动因

**buyer_concern_types（决策层）- 仅限付费/成本顾虑：**
- 付费顾虑：怕买贵、怕被宰、怕不值
- 成本顾虑：年预算、月消耗、采购成本
- 风险顾虑：怕质量不稳定、怕断供、怕售后无保障

**对接层 - 落地执行痛点：**
- 流程对接：审批繁琐、对接人多、沟通成本高
- 落地执行：安装难、配送慢、服务响应差

=== 输出格式 ===
严格按照以下JSON格式输出，不要添加任何额外文字：

【JSON格式说明 - 仅作字段格式参考，不要照抄】
格式示例：
[L_BRACE]
    "portraits": [
        [L_BRACE]
            "name": "画像名称（可加入场景关键词）",
            "portrait_summary": "【必填】2～3句口语化自然中文。结构公式：身份 + 当前问题/症状 + 想转变（解决问题）+ 受限于困境 + 【深层需求】。禁止用【】、禁止列模板标签、禁止JSON式字段名。",
            "使用场景": "该画像对应的具体使用场景",
            "identity_tags": [L_BRACE]
                "buyer": "付费者身份标签，如：职场白领、30-40岁家长",
                "user": "使用者身份标签，如：老人、孩子、宠物"
            [R_BRACE],
            "user_perspective": [L_BRACE]
                "problem": "使用者遇到的具体问题/症状，如：使用某产品后效果不明显、不舒适",
                "current_state": "当前状态，如：效果不明显、不舒适、影响心情",
                "impact": "对生活的影响，如：晚上睡不好、影响工作状态"
            [R_BRACE],
            "buyer_perspective": [L_BRACE]
                "goal": "付费者想解决的问题，如：找到适合的产品、解决问题",
                "obstacles": "付费者遇到的困境/障碍（用分号分隔），如：不知道如何判断是否适合；网上信息太多越看越慌",
                "psychology": "付费者深层心理状态，仅从【恐惧/渴望/焦虑/身份认同】4类底层刚需中选择或组合：\n- 恐惧：怕失去、怕选错、怕后果无法挽回、怕被坑、怕症状加重\n- 渴望：渴望被理解、渴望正确选择、渴望安全感、渴望孩子/家人好\n- 焦虑：长期悬而未决的不安、对未来的担忧、持续性困扰\n- 身份认同：怕被评判为"不称职"、自责不是好妈妈/好爸爸、好家长的自我期待与现实落差"
            [R_BRACE],
            "description": "综合描述，100-150字，包含两人关系、使用场景、核心矛盾",
            "用户阶段标签": "观望期 / 决策期 / 使用期（根据问题所属需求底盘自动推断：前置观望种草盘→观望期；刚需痛点盘→决策期；使用配套搜后种草盘→使用期）",
            "搜索行为预判": [
                "会搜索XXXX相关内容（具体描述用户真实搜索意图）",
                "会搜索XXXX相关内容",
                "会搜索XXXX相关内容"
            ],
            "industry_scene": "行业场景类型（固定值，来自系统识别）：高客单价高风险 / B2B企业服务 / 本地信任型 / 个人品牌专家型 / 通用场景",
            "trust_demand": [L_BRACE]
                "dimension": "信任诉求维度名称（如：资质背书、口碑背书、案例背书等）",
                "description": "信任诉求具体描述"
            [R_BRACE],
            "behavior_tags": [],
            "scene_tags": [],
            "symptom_tags": [],
            "search_intent_supplement": []
        [R_BRACE]
    ]
[R_BRACE]

=== 画像要求 ===
1. **portrait_summary 结构（五要素，必须具体）**：
   - 身份：具体到年龄/职业/体型/阶段（如：家有老人需要照顾的上班族、每天久坐的易胖体质白领）
   - 问题/症状：具体到身体感受/行为表现（如：使用某产品后效果不明显、脸上冒痘；早上想吃点甜的但是怕胖又怕饿）
   - 想转变：具体到想要什么（如：找到适合自己的产品；找到能吃饱又不长肉的早餐替代品）
   - 受限于困境：具体卡点（如：网上的评测软文太多分不清真假；亲戚朋友说法不一越看越慌；不知道该相信谁）
   - 【深层需求】：必须从4类底层刚需中选择或组合，不得使用浅情绪词
     - 恐惧：怕失去、怕后果不可逆、怕选错加重、怕被坑
     - 渴望：渴望被理解、渴望正确选择、渴望安全感、渴望家人健康平安
     - 焦虑：长期悬而未决、对未来的担忧、持续性困扰无法释怀
     - 身份认同：怕被评判为"不称职"、自责不是好妈妈/好爸爸，好家长的自我期待与现实落差

2. **禁止抽象表述和浅层情绪**：
   - ✗ 禁止浅情绪词：着急、难受、自责、担心、纠结、迷茫、发愁、焦虑（泛指）、心烦
   - ✗ 禁止抽象担忧："担心质量问题" → ✓ 改为："怕症状加重带来不可逆的后果；怕选错让孩子遭罪"
   - ✗ 禁止简单难受："心里难受着急" → ✓ 改为："内心深处的不安像阴影一样笼罩；怕别人说自己不是一个合格的妈妈"
   - ✗ 禁止泛化焦虑："很焦虑" → ✓ 改为："夜深人静时那种对孩子健康的恐惧感挥之不去；总是想象最坏的情况"

3. **buyer_perspective.psychology 深层升级要求**：
   - 必须从【恐惧/渴望/焦虑/身份认同】4类底层刚需中推导
   - 禁止使用浅层情绪词（着急/难受/自责/担心/纠结/迷茫等）
   - 每条 psychology 必须能回答："这个人的内心深处最怕什么？最渴望什么？"
   - 示例对比：
     - ✗ 浅层："看着孩子难受心里着急" → ✓ 深层："恐惧孩子症状恶化产生终身影响；渴望自己是个能保护好孩子的妈妈"
     - ✗ 浅层："纠结不知道怎么选" → ✓ 深层："害怕做错决定让孩子受害；渴望找到绝对正确的答案来证明自己的判断力"
     - ✗ 浅层："担心效果不好" → ✓ 深层："对未知的恐惧让自己寝食难安；渴望确定性带来的安全感"

4. **场景细分规则**：
   - 高严重程度：使用场景候选全部展开，每个场景生成1个画像
   - 中/低严重程度：最多选择2个最具代表性的场景
   - 画像数量：高严重2-3个，中严重2个，低严重1-2个

5. **每个画像包含**：
   - name：画像名称（可加入场景关键词，如"宴席场景-批量损坏"）
   - portrait_summary：五要素结构，必须具体
   - 使用场景：明确标注该画像对应的具体使用场景
   - buyer_perspective.psychology：必须是深层心理，与 portrait_summary 的深层需求对应
   - 其他字段完整

6. **深层需求一致性要求**：
   - portrait_summary 结尾的【深层需求】必须与 buyer_perspective.psychology 深层心理完全对应
   - 两者是同一枚硬币的两面：前者是口语化描述，后者是心理机制归类

7. **差异化**：每个画像要有明显区分，场景不同+困境不同+深层需求类型不同

8. **【慢性体征画像特别要求】**：
   - 如果存在常驻行为、固定场景、慢性体征标签，画像必须继承这些标签
   - portrait_summary 五要素中必须植入长期习惯痛点（如：每天在办公室对着电脑一坐就是8小时...）
   - 搜索行为预判必须补充久坐/伏案/工位养护类搜索词
   - identity_tags 中应体现行为场景（如：办公室久坐的上班族、长期盯屏幕的设计师）
   - 示例：
     * 身份：每天在办公室对着电脑一坐就是8小时的程序员
     * 症状：脖子僵硬、肩膀酸胀、眼睛干涩
     * 转变：想找个方法缓解久坐带来的不适
     * 困境：不知道什么护颈枕有用，怕买错浪费钱
     * 深层需求：恐惧落下终身职业病影响工作能力；渴望在同事面前维持高效专业的形象；渴望身体恢复到从前状态

=== 格式示例 ===

输入：某消费品业务（实际业务描述见上方）
输出：JSON数组（结构参考上方强制字段）

示例结构（仅格式参考，具体内容由AI根据实际业务描述生成）：
- 身份：目标用户具体身份
- 症状：具体可感受的身体/行为/情绪表现
- 转变：想达到的具体状态
- 困境：卡在哪个具体环节
- 深层需求：从恐惧/渴望/焦虑/身份认同中推导的具体深层心理

【重要】以上仅为格式示例，所有具体内容必须基于实际业务描述生成，禁止照抄示例措辞！

=== 强制要求 ===
- 每个画像都要包含 portrait_summary、user_perspective 和 buyer_perspective
- 每个画像必须包含「使用场景」字段
- portrait_summary 结构公式：身份 + 问题/症状 + 想转变 + 受限于困境 + 【深层需求】（从恐惧/渴望/焦虑/身份认同中选择）
- 深层需求须与 buyer_perspective.psychology 对齐（两者均为深层心理）
- **【必填】每个画像必须包含「用户阶段标签」字段**：观望期（前置观望种草盘）/ 决策期（刚需痛点盘）/ 使用期（使用配套搜后种草盘）
- **【必填】每个画像必须包含「搜索行为预判」字段**：锚定用户真实搜索词方向，描述用户会搜索哪些相关内容（必须与问题类型和用户阶段对齐，不是泛化的搜索词）
- **【必填】每个画像必须包含「industry_scene」字段**：来自系统识别的行业场景类型，必须严格使用固定值
- **【必填】每个画像必须包含「trust_demand」字段**：来自系统识别的信任诉求维度，必须严格使用固定值
- **行业场景决策心理**：画像需体现行业场景专属的决策心理（参考场景专属痛点 + trust_demand）
- **GEO内容方向**：所有选题必须围绕信任诉求展开，贴合「解决方案导向 + 信任背书」逻辑
- 只输出JSON，不要在JSON前后添加任何文字
- 不要使用省略号或占位符"""

    # 修复JSON格式占位符（避免f-string冲突）
    prompt = prompt.replace('[L_BRACE]', '{').replace('[R_BRACE]', '}')

    try:
        # 增大max_tokens防止JSON被截断
        response = llm.chat(prompt, temperature=0.8, max_tokens=8000)

        if not response:
            return {
                'success': False,
                'error': 'empty_response',
                'message': 'LLM 返回空响应'
            }

        logger.debug("[generate_portraits] 长度: %s", len(response))

        # 解析 JSON
        result = None

        def try_parse(text):
            try:
                return json.loads(text.strip())
            except json.JSONDecodeError:
                return None

        # 辅助函数：智能修复被截断的JSON
        def smart_fix_json(text):
            """智能修复被截断的JSON"""
            original = text
            logger.debug("[generate_portraits] 尝试修复JSON，长度=%s", len(text))

            for strategy in range(12):
                test_json = text

                try:
                    if strategy == 0:
                        # 策略0：找到最后一个完整的 }
                        last_brace = test_json.rfind('}')
                        if last_brace > 0:
                            test_json = test_json[:last_brace + 1]
                            # 检查括号是否平衡
                            if test_json.count('{') == test_json.count('}'):
                                result = try_parse(test_json)
                                if result:
                                    logger.debug("[generate_portraits] JSON修复成功(策略%s)", strategy)
                                    return result

                    elif strategy == 1:
                        # 策略1：找到最后一个完整的 ]
                        last_bracket = test_json.rfind(']')
                        if last_bracket > 0:
                            test_json = test_json[:last_bracket + 1]

                    elif strategy == 2:
                        # 策略2：去除代码块标记
                        test_json = test_json.strip()
                        if test_json.startswith('```'):
                            lines = test_json.split('\n')
                            if len(lines) > 1:
                                test_json = '\n'.join(lines[1:-1])
                            else:
                                test_json = test_json[3:-3].strip()

                    elif strategy == 3:
                        # 策略3：去除常见的结尾垃圾字符
                        for ext in ['}}}', '}}', '}', ']', ')"', '\n\n', '```', ',"']:
                            if test_json.rstrip().endswith(ext):
                                test_json = test_json.rstrip()[:-len(ext)].rstrip()

                    elif strategy == 4:
                        # 策略4：补充缺少的 }
                        open_braces = test_json.count('{')
                        close_braces = test_json.count('}')
                        if open_braces > close_braces:
                            test_json = test_json.rstrip() + '}' * (open_braces - close_braces)

                    elif strategy == 5:
                        # 策略5：补充缺少的 ]
                        open_brackets = test_json.count('[')
                        close_brackets = test_json.count(']')
                        if open_brackets > close_brackets:
                            test_json = test_json.rstrip() + ']' * (open_brackets - close_brackets)

                    elif strategy == 6:
                        # 策略6：从 portraits 字段重新构建
                        if '"portraits":' in test_json:
                            idx = test_json.find('"portraits":')
                            test_json = '{"portraits":' + test_json[idx + len('"portraits":'):]
                            # 找到最后一个完整的数组元素
                            last_comma = test_json.rfind('},')
                            if last_comma > 0:
                                test_json = '{"portraits":[' + test_json[len('"portraits":['):last_comma + 1] + ']}'
                            else:
                                last_bracket = test_json.rfind(']')
                                if last_bracket > 0:
                                    test_json = '{"portraits":[' + test_json[len('"portraits":['):last_bracket] + ']}'

                    elif strategy == 7:
                        # 策略7：查找最后一个完整的 portrait 对象
                        if '"name":' in test_json and '"portrait_summary":' in test_json:
                            # 找到最后一个完整的 }（在 closing_bracket 之前）
                            parts = test_json.rsplit('}', 2)
                            if len(parts) >= 2:
                                test_json = parts[0] + '}' + parts[1] + ']}}'

                    elif strategy == 8:
                        # 策略8：去除不完整的字符串值（最后一个引号后的内容）
                        if test_json.rstrip().endswith('"') or test_json.rstrip().endswith(',"'):
                            # 找到最后一个完整的属性
                            last_valid = test_json.rfind('",')
                            if last_valid > 0:
                                test_json = test_json[:last_valid + 1] + ']}'

                    elif strategy == 9:
                        # 策略9：找到 JSON 开头，截取到最后一个完整对象
                        json_start = test_json.find('{"portraits"')
                        if json_start < 0:
                            json_start = test_json.find('"portraits"')
                        if json_start >= 0:
                            test_json = test_json[json_start:]
                            if not test_json.startswith('{'):
                                test_json = '{"portraits":' + test_json.split('"portraits":', 1)[1] if '"portraits":' in test_json else test_json

                    elif strategy == 10:
                        # 策略10：尝试只取 portraits 数组
                        if '"portraits":' in test_json:
                            arr_start = test_json.find('"portraits":')
                            arr_content = test_json[arr_start + len('"portraits":'):]
                            # 找到数组边界
                            bracket_count = 0
                            end_idx = 0
                            for i, c in enumerate(arr_content):
                                if c == '[':
                                    bracket_count += 1
                                elif c == ']':
                                    bracket_count -= 1
                                    if bracket_count == 0:
                                        end_idx = i
                                        break
                            if end_idx > 0:
                                arr = arr_content[1:end_idx]
                                # 重新构建对象数组
                                result = try_parse('{"portraits":[' + arr + ']}')
                                if result:
                                    logger.debug("[generate_portraits] JSON修复成功(策略%s)", strategy)
                                    return result

                    elif strategy == 11:
                        # 策略11：尝试补充字符串并闭合
                        test_json = test_json.rstrip()
                        # 如果最后一个字符是逗号，去掉
                        if test_json.endswith(','):
                            test_json = test_json[:-1]
                        # 补充闭合符号
                        test_json += ']}}'

                    result = try_parse(test_json)
                    if result is not None:
                        logger.debug("[generate_portraits] JSON修复成功(策略%s)", strategy)
                        return result
                except Exception as e:
                    logger.debug("[generate_portraits] 策略%s失败: %s", strategy, e)
                    continue

        # 尝试多种解析方式
        result = try_parse(response)
        if not result:
            match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            if match:
                result = try_parse(match.group(1).strip())
        if not result:
            match = re.search(r'\{[\s\S]*', response)
            if match:
                result = smart_fix_json(match.group(0))

        if result:
            portraits = result.get('portraits', [])

            # 从问题继承需求底盘和双标签
            problem_base = problem.get('problem_base', '')
            consume_type = problem.get('consume_type', CONSUMER_TYPE_REQUIRED)
            demand_attr = problem.get('demand_attr', DEMAND_ATTR_FUNCTION)

            # 从慢性体征解析层继承标签
            p_behavior_tags = problem.get('behavior_tags', behavior_tags)
            p_scene_tags = problem.get('scene_tags', scene_tags)
            p_symptom_tags = problem.get('symptom_tags', symptom_tags)

            # 根据 problem_base 推导用户阶段标签
            user_stage = get_user_stage_from_problem_base(problem_base)

            for p in portraits:
                # 确保每个画像都有 使用场景 字段
                if '使用场景' not in p or not p['使用场景']:
                    p['使用场景'] = problem.get('scenarios', ['通用'])[0] if problem.get('scenarios') else '通用'

                # 自动补齐用户阶段标签（若LLM未填写）
                if '用户阶段标签' not in p or not p['用户阶段标签']:
                    p['用户阶段标签'] = user_stage

                # 自动补齐搜索行为预判（若LLM未填写，综合用户阶段 + 行业场景）
                if '搜索行为预判' not in p or not p['搜索行为预判']:
                    p['搜索行为预判'] = predict_search_behavior_with_industry_scene(
                        user_stage,
                        problem.get('problem_type', ''),
                        problem.get('description', ''),
                        industry_scene,
                        business_desc
                    )

                # 【新增】补充久坐/伏案/工位养护类搜索词（针对慢性体征问题）
                if p_behavior_tags or p_scene_tags or p_symptom_tags:
                    if '搜索行为预判' in p and isinstance(p['搜索行为预判'], list):
                        # 添加慢性体征相关的搜索词
                        chronic_search_supplement = _generate_chronic_search_intent(
                            p_behavior_tags, p_scene_tags, p_symptom_tags
                        )
                        p['搜索行为预判'].extend(chronic_search_supplement)

                # 自动补齐 consume_type（若LLM未填写）
                if 'consume_type' not in p or not p['consume_type']:
                    p['consume_type'] = consume_type

                # 自动补齐 demand_attr（若LLM未填写）
                if 'demand_attr' not in p or not p['demand_attr']:
                    p['demand_attr'] = demand_attr

                # 画像继承问题的需求底盘
                p['problem_base'] = problem_base

                # 自动补齐 industry_scene（若LLM未填写）
                if 'industry_scene' not in p or not p['industry_scene']:
                    p['industry_scene'] = industry_scene

                # 自动补齐 trust_demand（若LLM未填写）
                if 'trust_demand' not in p or not p['trust_demand']:
                    p['trust_demand'] = get_industry_scene_trust_demand(industry_scene)

                # 【新增】自动补齐行为场景体征标签
                if 'behavior_tags' not in p or not p['behavior_tags']:
                    p['behavior_tags'] = p_behavior_tags if p_behavior_tags else []
                if 'scene_tags' not in p or not p['scene_tags']:
                    p['scene_tags'] = p_scene_tags if p_scene_tags else []
                if 'symptom_tags' not in p or not p['symptom_tags']:
                    p['symptom_tags'] = p_symptom_tags if p_symptom_tags else []

            return {
                'success': True,
                'problem_id': problem.get('id', ''),
                'problem': problem,
                'portraits': portraits,
                'is_premium': is_premium
            }
        else:
            logger.warning("[generate_portraits] JSON解析失败，尝试从原始响应中提取画像...")
            
            # 最后尝试：从原始响应中提取所有肖像对象
            extracted_portraits = _extract_portraits_from_text(response)
            
            if extracted_portraits:
                logger.info("[generate_portraits] 从原始文本中提取到 %d 个画像", len(extracted_portraits))
                return {
                    'success': True,
                    'problem_id': problem.get('id', ''),
                    'problem': problem,
                    'portraits': extracted_portraits,
                    'is_premium': is_premium
                }
            
            logger.debug("[generate_portraits] JSON解析失败，响应: %s", response[:500])
            return {
                'success': False,
                'message': 'AI生成失败，未能解析出有效数据'
            }

    except Exception as e:
        import traceback
        logger.error("[generate_portraits] 异常: %s", str(e))
        logger.debug("[generate_portraits] 堆栈: %s", traceback.format_exc())
        return {
            'success': False,
            'message': f'生成失败: {str(e)}'
        }


def _extract_portraits_from_text(text: str) -> list:
    """
    从原始文本中提取画像数据（即使JSON格式不完整）
    
    策略：
    1. 提取所有 name 和 portrait_summary 字段组合
    2. 使用正则表达式匹配画像对象
    3. 尝试补全缺失字段
    """
    import re
    
    portraits = []
    
    # 清理文本：去除代码块标记
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        if len(lines) > 2:
            text = '\n'.join(lines[1:-1])
        else:
            text = text[3:-3].strip()
    
    # 策略1：提取完整的画像对象（包含 "name" 和 "portrait_summary" 的对象）
    # 匹配从 {"name": ... 开始到下一个画像或结束的部分
    pattern1 = r'\{\s*"name"\s*:\s*"([^"]+)"[^}]*"portrait_summary"\s*:\s*"([^"]*)"[^}]*\}'
    matches1 = re.findall(pattern1, text)
    
    for name, summary in matches1:
        portrait = {
            'name': name.strip(),
            'portrait_summary': summary.strip(),
            'identity_tags': {'buyer': '', 'user': ''},
            'user_perspective': {
                'problem': '',
                'current_state': '',
                'impact': ''
            },
            'buyer_perspective': {
                'goal': '',
                'obstacles': '',
                'psychology': ''
            },
            'description': summary.strip(),
            '使用场景': '通用',
            '用户阶段标签': '观望期',
            '搜索行为预判': [],
            'industry_scene': '通用场景',
            'trust_demand': []
        }
        portraits.append(portrait)
    
    # 策略2：提取独立的 "name" 字段值作为画像
    if not portraits:
        name_pattern = r'"name"\s*:\s*"([^"]{2,30})"'
        names = re.findall(name_pattern, text)
        for name in names[:5]:  # 最多取5个
            portrait = {
                'name': name.strip(),
                'portrait_summary': f'{name.strip()}相关的用户画像（详情待生成）',
                'identity_tags': {'buyer': '', 'user': ''},
                'user_perspective': {'problem': '', 'current_state': '', 'impact': ''},
                'buyer_perspective': {'goal': '', 'obstacles': '', 'psychology': ''},
                'description': f'{name.strip()}相关的用户画像',
                '使用场景': '通用',
                '用户阶段标签': '观望期',
                '搜索行为预判': [],
                'industry_scene': '通用场景',
                'trust_demand': []
            }
            portraits.append(portrait)
    
    logger.debug("[_extract_portraits_from_text] 提取到 %d 个画像", len(portraits))
    return portraits


# =============================================================================
# 并发画像生成（付费用户专用）
# =============================================================================

def generate_portraits_parallel(problems: List[Dict], business_desc: str, is_premium: bool = True,
                                   service_scenario: str = 'other', business_type: str = 'local_service') -> List[Dict]:
    """
    并行生成多个问题的画像（付费用户专用）

    Args:
        problems: 问题列表
        business_desc: 业务描述
        is_premium: 是否付费用户
        service_scenario: 服务场景
        business_type: 经营类型

    Returns:
        每个问题的画像列表
    """
    import concurrent.futures

    results = []

    def generate_single(problem: Dict) -> Dict:
        """生成单个问题的画像"""
        params = {
            'business_description': business_desc,
            'problem': problem,
            'portrait_count': 5,
            '_is_premium': is_premium,
            'service_scenario': service_scenario,
            'business_type': business_type
        }
        return generate_portraits(params)

    # 使用线程池并行执行（最多3个并发）
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_problem = {
            executor.submit(generate_single, problem): problem
            for problem in problems
        }

        for future in concurrent.futures.as_completed(future_to_problem):
            problem = future_to_problem[future]
            try:
                result = future.result()
                results.append({
                    'problem_id': problem.get('id', ''),
                    'problem_display': problem.get('display_name', ''),
                    'portraits': result.get('portraits', []) if result.get('success') else [],
                    'success': result.get('success', False)
                })
            except Exception as e:
                logger.error("[generate_portraits_parallel] 生成失败: %s", e)
                results.append({
                    'problem_id': problem.get('id', ''),
                    'problem_display': problem.get('display_name', ''),
                    'portraits': [],
                    'success': False,
                    'error': str(e)
                })

    return results
