"""
商业模式设计服务 - 纳瓦尔宝典视角

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
架构规划：三层分析体系
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【第一层：系统分析】- 本服务完成
  → 静态知识库匹配，无需实时数据
  → 10个维度的基础分析
  → 系统直接给出结论

  适用维度：
  ├── 业务模式 (business_mode) - 产品/服务/时间/体力
  ├── 行业阶段 (industry_stage) - 成熟期/增长期/新兴
  ├── 赛道增速 (track_growth) - 静态趋势判断
  ├── 需求类型 (demand_type) - 刚需/改善/可选
  ├── 时间被困 (time_trap) - 能否规模化
  ├── 资产盘点 (asset_check) - 现有资产
  ├── 杠杆诊断 (leverage_diagnosis) - 可用杠杆
  ├── 复制路径 (replication) - 培训/加盟/内容
  ├── 决策难度 (decision_difficulty) - 入场门槛
  └── AI危机 (ai_crisis) - 替代风险与机遇

【第二层：LLM增强】- API接口 /api/decision-cost/llm-conclusion
  → 动态推理，基于系统分析结果
  → 生成战略建议和行动路径
  → 需要LLM能力

  用途：
  ├── 综合结论生成 - 核心优势/问题/行动
  ├── 个性化建议 - 结合用户画像微调
  └── 深度洞察 - 模式识别与趋势预判

【第三层：实时数据】- 后续扩展
  → 需要外部API或爬虫
  → 实时行业数据

  计划接入：
  ├── 行业增速数据 - 第三方API
  ├── 竞品分析 - 实时爬取
  ├── 政策动态 - 新闻API
  └── 市场规模 - 研报数据

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

产品定位：从"诊断"到"指路"，帮有业务的人看清方向
目标用户：有明确产品/服务、能做转化的人
"""

from typing import Dict, List, Optional, Any
import re
import json


# ==================== 纳瓦尔宝典核心原则 ====================
# 财富 = 睡觉时仍在为你赚钱的资产
# 核心 = 从「卖时间」切换到「建立资产」
#
# 第一阶段任务：停止所有无法沉淀为资产的单纯时间售卖
# 如果必须做，也要同时提炼出标准化流程或教程
#
# 资产类型（按容易程度排序）：
# 1. 内容/影响力 - 一次生产，无限分发
# 2. 产品/版权 - 标准化后可无限销售
# 3. 品牌/授权 - 信任的可复制
# 4. 资本 - 需要前期积累

# ==================== 剥离阶段定义 ====================

DETACH_PHASES = {
    "phase_1": {
        "name": "阶段一：止损",
        "icon": "🛑",
        "color": "#ef4444",
        "description": "停止无法沉淀资产的单纯时间售卖",
        "tasks": [
            "识别哪些工作是在卖时间",
            "停止或减少低价值的时间售卖",
            "把必须做的时间售卖变成提炼过程"
        ]
    },
    "phase_2": {
        "name": "阶段二：沉淀",
        "icon": "💎",
        "color": "#3b82f6",
        "description": "把经验提炼成可复制的资产",
        "tasks": [
            "标准化流程/SOP",
            "方法论提炼",
            "案例/数据积累"
        ]
    },
    "phase_3": {
        "name": "阶段三：杠杆",
        "icon": "🚀",
        "color": "#10b981",
        "description": "用杠杆放大资产价值",
        "tasks": [
            "内容杠杆（短视频/文章）",
            "产品杠杆（课程/工具）",
            "品牌杠杆（授权/加盟）"
        ]
    }
}


# ==================== 剥离路径生成函数 ====================

def generate_detach_path(business_data: Dict) -> Dict:
    """根据业务数据生成剥离路径"""
    replication = business_data.get("维度分析", {}).get("replication", {})
    business_mode = business_data.get("维度分析", {}).get("business_mode", {})

    # 当前模式
    current_mode = business_mode.get("mode", "服务为主")
    is_time_selling = "服务" in current_mode or "时间" in current_mode

    # 核心资源
    core_resources = replication.get("核心资源", "")
    resource_difficulty = replication.get("资源获取", {})

    # 分析哪些资源是可标准化的
    standardizable = []
    non_standardizable = []
    for resource, difficulty in resource_difficulty.items():
        if "可" in difficulty or "标准" in difficulty or "核心" in difficulty:
            standardizable.append(resource)
        else:
            non_standardizable.append(resource)

    # 生成路径
    detach_path = {
        "current_mode": current_mode,
        "is_time_selling": is_time_selling,
        "standardizable_resources": standardizable,
        "non_standardizable_resources": non_standardizable,
        "recommendation": replication.get("剥离路径", ""),
        "advice": replication.get("advice", ""),
        "phases": [
            DETACH_PHASES["phase_1"] if is_time_selling else DETACH_PHASES["phase_2"],
            DETACH_PHASES["phase_2"],
            DETACH_PHASES["phase_3"]
        ]
    }

    return detach_path


# ==================== 杠杆类型定义 ====================
# 按容易程度排序：影响力 > 产品 > 人力 > 资本

LEVERAGE_TYPES = {
    "influence": {
        "name": "影响力杠杆",
        "icon": "📱",
        "color": "#10b981",  # 绿色 - 最容易
        "priority": 1,
        "paths": ["内容获客", "课程", "社群", "IP", "短视频", "自媒体"],
        "characteristics": {
            "时间成本": "中等（3-12个月见效）",
            "操作难度": "★★★☆☆",
            "资源稀缺度": "低（人人可做）",
            "边际成本": "极低，可复用",
            "适合阶段": "早期/有经验者"
        }
    },
    "product": {
        "name": "产品杠杆",
        "icon": "📦",
        "color": "#3b82f6",  # 蓝色
        "priority": 2,
        "paths": ["工具", "SaaS", "标准化产品", "课程产品", "模板", "素材包"],
        "characteristics": {
            "时间成本": "高（6-18个月开发）",
            "操作难度": "★★★★☆",
            "资源稀缺度": "中（需技术/设计）",
            "边际成本": "低，可规模化",
            "适合阶段": "中期/有积累者"
        }
    },
    "human": {
        "name": "人力杠杆",
        "icon": "👥",
        "color": "#f59e0b",  # 橙色
        "priority": 3,
        "paths": ["培训", "加盟", "学徒", "团队", "合伙人", "外包"],
        "characteristics": {
            "时间成本": "高（6-24个月建立）",
            "操作难度": "★★★★★",
            "资源稀缺度": "高（需人才/管理）",
            "边际成本": "中等，管理成本高",
            "适合阶段": "成熟期/有资金者"
        }
    },
    "capital": {
        "name": "资本杠杆",
        "icon": "💰",
        "color": "#ef4444",  # 红色 - 最难
        "priority": 4,
        "paths": ["融资", "直投", "收购", "扩张"],
        "characteristics": {
            "时间成本": "不确定（看融资周期）",
            "操作难度": "★★★★★",
            "资源稀缺度": "极高（需资源/背景）",
            "边际成本": "高（股权稀释）",
            "适合阶段": "成熟期/有规模者"
        }
    }
}


def classify_leverage_path(path: str) -> str:
    """根据路径名称分类杠杆类型"""
    for leverage_type, config in LEVERAGE_TYPES.items():
        for keyword in config["paths"]:
            if keyword in path:
                return leverage_type
    return "human"  # 默认归类为人力杠杆


def analyze_replication_paths(paths: List[str]) -> List[Dict]:
    """分析复制路径，返回带详细信息的列表"""
    analyzed = []
    for path in paths:
        leverage_type = classify_leverage_path(path)
        config = LEVERAGE_TYPES[leverage_type]
        analyzed.append({
            "name": path.strip(),
            "type": leverage_type,
            "type_name": config["name"],
            "type_icon": config["icon"],
            "type_color": config["color"],
            "priority": config["priority"],
            **config["characteristics"]
        })
    # 按优先级排序（影响力优先）
    analyzed.sort(key=lambda x: x["priority"])
    return analyzed


# ==================== 维度配置 ====================

DIMENSIONS_CONFIG = {
    "industry_stage": {
        "name": "行业阶段",
        "icon": "📊",
        "description": "赛道长度与入场时机",
        "system_able": True,
    },
    "track_growth": {
        "name": "赛道增速",
        "icon": "🚀",
        "description": "行业发展速度与天花板",
        "system_able": True,
    },
    "replication": {
        "name": "复制能力",
        "icon": "🔄",
        "description": "业务可复制性与路径",
        "system_able": True,
    },
    "demand_type": {
        "name": "需求类型",
        "icon": "💡",
        "description": "刚需 vs 非刚需分析",
        "system_able": True,
    },
    "business_mode": {
        "name": "业务模式",
        "icon": "🏪",
        "description": "产品/服务/时间/体力",
        "system_able": True,
    },
    "time_trap": {
        "name": "时间被困",
        "icon": "⏰",
        "description": "是否被困在时间里",
        "system_able": True,
    },
    "asset_check": {
        "name": "资产盘点",
        "icon": "🏦",
        "description": "现有资产与杠杆",
        "system_able": True,
    },
    "leverage_diagnosis": {
        "name": "杠杆诊断",
        "icon": "⚖️",
        "description": "可用杠杆分析",
        "system_able": True,
    },
    "decision_difficulty": {
        "name": "决策难度",
        "icon": "🎯",
        "description": "入场门槛评估",
        "system_able": True,
    },
    "ai_crisis": {
        "name": "AI危机",
        "icon": "🤖",
        "description": "AI替代风险与机遇",
        "system_able": True,
    },
}


# ==================== 行业知识图谱 ====================

BUSINESS_KNOWLEDGE_GRAPH: Dict[str, Dict] = {
    "灌香肠加工": {
        "基础特征": {
            "客户范围": "local",
            "价格区间": "500-5000元/批",
            "目标用户": ["本地餐饮商家", "超市", "个人消费者"],
        },
        "维度分析": {
            "industry_stage": {
                "score": 7,
                "status": "成熟期",
                "description": "传统行业，市场成熟稳定",
                "advice": "差异化竞争 + 规模化突围",
            },
            "track_growth": {
                "score": 5,
                "growth_rate": "稳定",
                "description": "年增速约3-5%，市场稳定但增长有限",
                "advice": "寻找细分场景或出口机会",
            },
            "replication": {
                "score": 5,
                "核心资源": "口味配方 + 工艺诀窍",
                "经验来源": "长期实践摸索",
                "资源获取": {
                    "配方": "可标准化（核心）",
                    "技术人才": "难培养（需跟师）",
                    "客户信任": "靠口碑积累"
                },
                "difficulty_rating": "★★★☆☆",
                "replication_path": "内容/教程/培训",
                "advice": "把'手感'标准化成配方教程 → 用短视频传播 → 卖课程/收学员"
            },
            "demand_type": {
                "score": 8,
                "type": "刚需+面子",
                "description": "年节必备（刚需）+ 送礼体面（面子）",
                "seven_sins": ["傲慢", "暴食"],
                "advice": "强化送礼场景，突出品质与面子价值",
            },
            "business_mode": {
                "score": 6,
                "mode": "产品为主，服务为辅",
                "description": "卖产品，但有定制/代加工服务",
                "advice": "产品标准化，服务差异化",
            },
            "time_trap": {
                "score": 7,
                "status": "部分被困",
                "description": "生产环节耗时，但可雇佣工人",
                "advice": "用工人解决时间问题，专注配方研发",
            },
            "asset_check": {
                "score": 4,
                "assets": ["口碑", "配方", "客户关系"],
                "missing": ["品牌", "渠道", "规模"],
                "advice": "积累品牌资产和渠道网络",
            },
            "leverage_diagnosis": {
                "score": 3,
                "current_leverages": ["产品杠杆（有限）"],
                "available_leverages": ["影响力杠杆（短视频/教程）", "人力杠杆（学徒/加盟）"],
                "advice": "优先建立内容资产（配方教程/教程），用影响力复制",
            },
            "decision_difficulty": {
                "score": 5,
                "cognition_gap": "中等（需要口味调试经验）",
                "info_gap": "低（工艺公开可查）",
                "skill_gap": "高（靠长期实践）",
                "resource_gap": "中（启动资金5-20万）",
                "advice": "核心门槛是口味，需要1-3年沉淀",
            },
            "ai_crisis": {
                "score": 6,
                "replacement_risk": "★★★☆☆",
                "quantifiable": True,
                "quantification_desc": "口味可通过数据化配方部分量化",
                "mode_change": "口味标准化后 → 可培训/可加盟",
                "opportunity": "AI配方优化 + 标准化流程",
                "advice": "趁AI成熟前，先建立品牌和培训体系",
            },
        },
        "综合结论": {
            "核心优势": ["口味独特", "本地口碑", "价格优势"],
            "核心问题": ["被困在时间里", "难以标准化复制"],
            "优先级": ["标准化配方", "建立内容资产", "探索加盟模式"],
        },
    },

    "医美整形": {
        "基础特征": {
            "客户范围": "national",
            "价格区间": "5千-50万",
            "目标用户": ["25-45岁女性", "追求颜值人群"],
        },
        "维度分析": {
            "industry_stage": {
                "score": 8,
                "status": "正当时",
                "description": "颜值经济爆发期，市场高速增长",
                "advice": "品牌化、差异化是突围关键",
            },
            "track_growth": {
                "score": 8,
                "growth_rate": "15-25%/年",
                "description": "行业持续高速增长，预计持续10年+",
                "advice": "是长期赛道，可深耕",
            },
            "replication": {
                "score": 3,
                "核心资源": "医生技术 + 口碑案例",
                "经验来源": "医学教育 + 多年临床",
                "资源获取": {
                    "医生": "极难（培养周期长）",
                    "口碑": "靠案例积累",
                    "资质": "需要执照"
                },
                "difficulty_rating": "★★★★☆",
                "replication_path": "内容/课程/品牌",
                "advice": "医生难复制，但案例/方法论可标准化 → 内容建立信任 → 课程/品牌授权"
            },
            "demand_type": {
                "score": 9,
                "type": "刚需+面子",
                "description": "变美是刚需，面子需求强烈",
                "seven_sins": ["傲慢", "虚荣"],
                "advice": "强化'变美改变命运'叙事",
            },
            "business_mode": {
                "score": 7,
                "mode": "服务为主",
                "description": "手术/注射/皮肤管理服务",
                "advice": "高客单价需要高信任，内容建立专业形象",
            },
            "time_trap": {
                "score": 8,
                "status": "严重被困",
                "description": "医生时间有限，手术排期紧张",
                "advice": "培养医生团队，用品牌降低对个人的依赖",
            },
            "asset_check": {
                "score": 5,
                "assets": ["医生技术", "口碑案例", "资质"],
                "missing": ["品牌全国知名度", "标准化流程"],
                "advice": "积累品牌资产和案例库",
            },
            "leverage_diagnosis": {
                "score": 4,
                "current_leverages": ["人力杠杆（医生团队）"],
                "available_leverages": ["影响力杠杆（案例/科普）", "资本杠杆（融资扩张）"],
                "advice": "用内容建立影响力，降低获客成本",
            },
            "decision_difficulty": {
                "score": 9,
                "cognition_gap": "高（需要医学背景）",
                "info_gap": "中（信息不对称严重）",
                "skill_gap": "极高（手术技能）",
                "resource_gap": "高（资质/资金）",
                "advice": "核心门槛是资质和技术，难以速成",
            },
            "ai_crisis": {
                "score": 5,
                "replacement_risk": "★★☆☆☆",
                "quantifiable": True,
                "quantification_desc": "AI辅助诊断/术前模拟，但手术需医生",
                "mode_change": "AI辅助 → 降低手术门槛",
                "opportunity": "AI咨询/术后模拟/客户管理",
                "advice": "拥抱AI工具提升效率，但核心仍靠医生",
            },
        },
        "综合结论": {
            "核心优势": ["客单价高", "需求持续", "技术壁垒"],
            "核心问题": ["医生依赖", "扩张困难", "信任门槛高"],
            "优先级": ["建立品牌", "培养团队", "内容获客"],
        },
    },

    "装修": {
        "基础特征": {
            "客户范围": "local",
            "价格区间": "10-100万",
            "目标用户": ["准备装修的业主", "二手房东"],
        },
        "维度分析": {
            "industry_stage": {
                "score": 7,
                "status": "成熟期",
                "description": "市场成熟，但散乱差",
                "advice": "品牌化、标准化是机会",
            },
            "track_growth": {
                "score": 6,
                "growth_rate": "5-8%/年",
                "description": "稳定增长，但受房地产影响",
                "advice": "关注存量房翻新市场",
            },
            "replication": {
                "score": 4,
                "核心资源": "设计能力 + 施工经验 + 供应链",
                "经验来源": "多年行业积累",
                "资源获取": {
                    "设计": "可培养",
                    "施工队": "难管理",
                    "供应链": "需长期建立"
                },
                "difficulty_rating": "★★★★☆",
                "replication_path": "内容/课程/工具",
                "advice": "施工难复制，但设计/流程可标准化 → 做成教程/工具 → 内容获客"
            },
            "demand_type": {
                "score": 8,
                "type": "刚需",
                "description": "买房必装，但决策谨慎",
                "seven_sins": ["懒惰", "贪婪"],
                "advice": "解决'省心省力省钱'的诉求",
            },
            "business_mode": {
                "score": 6,
                "mode": "服务+产品",
                "description": "设计+施工+材料",
                "advice": "整装模式利润更高",
            },
            "time_trap": {
                "score": 7,
                "status": "严重被困",
                "description": "项目周期长，每个工地都耗时",
                "advice": "标准化流程，项目制管理",
            },
            "asset_check": {
                "score": 5,
                "assets": ["施工经验", "供应商关系", "口碑"],
                "missing": ["品牌", "标准化", "系统"],
                "advice": "积累品牌和SOP体系",
            },
            "leverage_diagnosis": {
                "score": 3,
                "current_leverages": [],
                "available_leverages": ["影响力杠杆（工地记录）", "产品杠杆（主材包）"],
                "advice": "用短视频记录工地，建立信任",
            },
            "decision_difficulty": {
                "score": 7,
                "cognition_gap": "中（装修知识可学）",
                "info_gap": "高（猫腻多）",
                "skill_gap": "中（管理和协调）",
                "resource_gap": "高（启动资金）",
                "advice": "核心是管理和信任",
            },
            "ai_crisis": {
                "score": 5,
                "replacement_risk": "★★☆☆☆",
                "quantifiable": True,
                "quantification_desc": "AI设计辅助，但施工难替代",
                "mode_change": "AI设计 → 提高效率",
                "opportunity": "AI量房/设计/报价",
                "advice": "用AI工具提升效率和获客",
            },
        },
        "综合结论": {
            "核心优势": ["市场大", "客单价高", "复购可能"],
            "核心问题": ["管理困难", "信任难建立", "扩张慢"],
            "优先级": ["标准化", "品牌化", "内容获客"],
        },
    },

    "高考志愿": {
        "基础特征": {
            "客户范围": "national",
            "价格区间": "500-1万",
            "目标用户": ["高三学生家长", "高考考生"],
        },
        "维度分析": {
            "industry_stage": {
                "score": 7,
                "status": "正当时",
                "description": "新高考改革，信息需求爆发",
                "advice": "专业度高、时效性强是机会",
            },
            "track_growth": {
                "score": 7,
                "growth_rate": "10-15%/年",
                "description": "家长付费意愿增强",
                "advice": "内容+服务结合",
            },
            "replication": {
                "score": 6,
                "核心资源": "历年数据 + 方法论 + 经验",
                "经验来源": "多年录取数据 + 填报经验",
                "资源获取": {
                    "数据": "可积累（核心）",
                    "方法论": "可标准化",
                    "经验": "需沉淀"
                },
                "difficulty_rating": "★★☆☆☆",
                "replication_path": "内容/课程/工具",
                "advice": "数据和方法论高度可复制 → 做成课程/工具 → 内容杠杆放大"
            },
            "demand_type": {
                "score": 9,
                "type": "刚需+焦虑",
                "description": "影响一生，焦虑极强",
                "seven_sins": ["傲慢", "贪婪"],
                "advice": "强化'选错毁一生'的紧迫感",
            },
            "business_mode": {
                "score": 7,
                "mode": "服务+产品",
                "description": "咨询+课程+工具",
                "advice": "课程标准化，咨询高端化",
            },
            "time_trap": {
                "score": 5,
                "status": "部分被困",
                "description": "旺季集中在6-7月",
                "advice": "用内容/工具/团队突破时间限制",
            },
            "asset_check": {
                "score": 6,
                "assets": ["历史数据", "经验方法", "口碑案例"],
                "missing": ["全国数据", "品牌"],
                "advice": "积累数据资产，做成工具/课程",
            },
            "leverage_diagnosis": {
                "score": 6,
                "current_leverages": ["知识杠杆（方法论）"],
                "available_leverages": ["代码杠杆（工具）", "影响力杠杆（内容）"],
                "advice": "做内容/做工具，突破时间限制",
            },
            "decision_difficulty": {
                "score": 6,
                "cognition_gap": "中（需要学习）",
                "info_gap": "高（数据不对称）",
                "skill_gap": "中（分析能力）",
                "resource_gap": "低（轻资产）",
                "advice": "核心是数据和经验积累",
            },
            "ai_crisis": {
                "score": 7,
                "replacement_risk": "★★★★☆",
                "quantifiable": True,
                "quantification_desc": "AI数据分析录取概率，可替代基础咨询",
                "mode_change": "AI工具 → 替代基础服务",
                "opportunity": "AI+人工结合，提升效率",
                "advice": "用AI做工具，用人做高端咨询",
            },
        },
        "综合结论": {
            "核心优势": ["需求刚", "可标准化", "可规模化"],
            "核心问题": ["时间集中", "AI冲击", "竞争加剧"],
            "优先级": ["做工具", "做内容", "AI结合"],
        },
    },

    "留学中介": {
        "基础特征": {
            "客户范围": "national",
            "价格区间": "3-30万",
            "目标用户": ["有意向留学生", "学生家长"],
        },
        "维度分析": {
            "industry_stage": {
                "score": 6,
                "status": "成熟期",
                "description": "市场成熟，但DIY增多",
                "advice": "差异化（高端/专业）是出路",
            },
            "track_growth": {
                "score": 6,
                "growth_rate": "5-10%/年",
                "description": "留学需求稳定，但增速放缓",
                "advice": "聚焦高端/小众国家",
            },
            "replication": {
                "score": 5,
                "核心资源": "申请经验 + 海外关系 + 成功案例",
                "经验来源": "多年申请经验",
                "资源获取": {
                    "经验": "可标准化",
                    "海外关系": "难建立",
                    "案例": "可积累"
                },
                "difficulty_rating": "★★☆☆☆",
                "replication_path": "内容/课程/工具",
                "advice": "把申请经验标准化 → 做成课程/DIY工具 → 内容杠杆放大"
            },
            "demand_type": {
                "score": 8,
                "type": "刚需+面子",
                "description": "留学改变命运，面子需求强",
                "seven_sins": ["傲慢", "虚荣"],
                "advice": "强化'逆袭'叙事",
            },
            "business_mode": {
                "score": 7,
                "mode": "服务为主",
                "description": "申请咨询+文书+申请",
                "advice": "高端服务，溢价空间大",
            },
            "time_trap": {
                "score": 6,
                "status": "部分被困",
                "description": "每个学生都耗时，但可批量化",
                "advice": "流程标准化，团队分工",
            },
            "asset_check": {
                "score": 5,
                "assets": ["申请经验", "成功案例", "海外关系"],
                "missing": ["品牌", "标准化流程"],
                "advice": "积累案例和方法论资产",
            },
            "leverage_diagnosis": {
                "score": 5,
                "current_leverages": ["知识杠杆（经验）"],
                "available_leverages": ["影响力杠杆（内容）", "代码杠杆（工具）"],
                "advice": "做内容获客，降低获客成本",
            },
            "decision_difficulty": {
                "score": 7,
                "cognition_gap": "高（信息复杂）",
                "info_gap": "高（各国政策不同）",
                "skill_gap": "中（文书/申请）",
                "resource_gap": "中（海外关系）",
                "advice": "核心是信息和人脉",
            },
            "ai_crisis": {
                "score": 8,
                "replacement_risk": "★★★★☆",
                "quantifiable": True,
                "quantification_desc": "AI写文书/选校，可替代大部分工作",
                "mode_change": "AI申请 → 大幅降低人工",
                "opportunity": "AI+人工，用AI提效",
                "advice": "拥抱AI，做AI做不了的高端咨询",
            },
        },
        "综合结论": {
            "核心优势": ["客单价高", "需求稳定", "可建立品牌"],
            "核心问题": ["AI冲击", "信任难建立", "获客贵"],
            "优先级": ["AI化", "品牌化", "高端化"],
        },
    },

    "金融投资": {
        "基础特征": {
            "客户范围": "national",
            "价格区间": "1千-无限",
            "目标用户": ["投资小白", "理财用户", "有钱人"],
        },
        "维度分析": {
            "industry_stage": {
                "score": 8,
                "status": "正当时",
                "description": "财富管理需求爆发",
                "advice": "专业内容是入口",
            },
            "track_growth": {
                "score": 9,
                "growth_rate": "15-20%/年",
                "description": "居民财富持续增长",
                "advice": "长期赛道，可深耕",
            },
            "replication": {
                "score": 7,
                "核心资源": "投资知识 + 方法论 + 信任",
                "经验来源": "市场实战经验",
                "资源获取": {
                    "知识": "可学习（可标准化）",
                    "方法论": "可沉淀",
                    "信任": "靠内容建立"
                },
                "difficulty_rating": "★☆☆☆☆",
                "replication_path": "内容/课程/社群",
                "advice": "知识和方法高度可复制 → 内容建立信任 → 课程/社群变现"
            },
            "demand_type": {
                "score": 10,
                "type": "刚需+贪婪",
                "description": "都想赚钱，需求极强",
                "seven_sins": ["贪婪", "傲慢"],
                "advice": "满足'快速赚钱'的幻想",
            },
            "business_mode": {
                "score": 8,
                "mode": "服务+产品",
                "description": "咨询/课程/代客理财",
                "advice": "内容获客，服务变现",
            },
            "time_trap": {
                "score": 4,
                "status": "轻度被困",
                "description": "内容可复用，服务有限制",
                "advice": "内容优先，服务分层",
            },
            "asset_check": {
                "score": 7,
                "assets": ["投资知识", "方法论", "粉丝信任"],
                "missing": ["牌照", "资金"],
                "advice": "积累影响力和方法论",
            },
            "leverage_diagnosis": {
                "score": 8,
                "current_leverages": ["影响力杠杆"],
                "available_leverages": ["代码杠杆（工具）", "资本杠杆"],
                "advice": "内容杠杆是核心武器",
            },
            "decision_difficulty": {
                "score": 9,
                "cognition_gap": "高（需要专业）",
                "info_gap": "中",
                "skill_gap": "高（实战能力）",
                "resource_gap": "中（牌照）",
                "advice": "核心是建立信任和影响力",
            },
            "ai_crisis": {
                "score": 6,
                "replacement_risk": "★★★☆☆",
                "quantifiable": True,
                "quantification_desc": "AI投顾崛起，但信任难替代",
                "mode_change": "AI辅助 → 但人需要背书",
                "opportunity": "AI工具 + 个人IP",
                "advice": "用AI工具，用人建立信任",
            },
        },
        "综合结论": {
            "核心优势": ["需求极刚", "可高度复制", "杠杆强大"],
            "核心问题": ["信任难建立", "监管风险", "竞争激烈"],
            "优先级": ["建立IP", "内容获客", "服务分层"],
        },
    },

    "儿童教育": {
        "基础特征": {
            "客户范围": "local",
            "价格区间": "1千-10万/年",
            "目标用户": ["3-12岁儿童家长", "鸡娃家长"],
        },
        "维度分析": {
            "industry_stage": {
                "score": 8,
                "status": "正当时",
                "description": "教育焦虑驱动市场扩大",
                "advice": "差异化定位（高端/特长）是机会",
            },
            "track_growth": {
                "score": 8,
                "growth_rate": "15-20%/年",
                "description": "家长付费意愿持续增强",
                "advice": "素质教育/特长培训是蓝海",
            },
            "replication": {
                "score": 5,
                "核心资源": "教学方法 + 课程内容 + 师资培训",
                "经验来源": "教学经验 + 课程研发",
                "资源获取": {
                    "师资": "难培养",
                    "课程": "可研发（核心）",
                    "品牌": "需积累"
                },
                "difficulty_rating": "★★☆☆☆",
                "replication_path": "内容/课程/加盟",
                "advice": "课程高度可标准化 → 做成产品 → 加盟/授权放大"
            },
            "demand_type": {
                "score": 9,
                "type": "刚需+焦虑",
                "description": "不能让孩子输，面子+焦虑",
                "seven_sins": ["傲慢", "贪婪"],
                "advice": "强化'起跑线'焦虑",
            },
            "business_mode": {
                "score": 7,
                "mode": "服务为主",
                "description": "培训/课程/托管",
                "advice": "课程标准化，服务差异化",
            },
            "time_trap": {
                "score": 6,
                "status": "部分被困",
                "description": "教学需要时间，但可排班",
                "advice": "标准化课程，团队执行",
            },
            "asset_check": {
                "score": 5,
                "assets": ["教学经验", "课程", "口碑"],
                "missing": ["品牌", "标准化"],
                "advice": "积累课程和品牌资产",
            },
            "leverage_diagnosis": {
                "score": 4,
                "current_leverages": ["人力杠杆（教师）"],
                "available_leverages": ["影响力杠杆（内容）", "产品杠杆（课程）"],
                "advice": "做内容获客，课程产品化",
            },
            "decision_difficulty": {
                "score": 6,
                "cognition_gap": "中",
                "info_gap": "低",
                "skill_gap": "中（教学能力）",
                "resource_gap": "中（场地/师资）",
                "advice": "核心是师资和课程",
            },
            "ai_crisis": {
                "score": 7,
                "replacement_risk": "★★★★☆",
                "quantifiable": True,
                "quantification_desc": "AI一对一陪练，可替代部分教学",
                "mode_change": "AI辅助 → 降低师资依赖",
                "opportunity": "AI+人工结合",
                "advice": "用AI提效，专注AI做不了的",
            },
        },
        "综合结论": {
            "核心优势": ["需求刚", "家长付费强", "可品牌化"],
            "核心问题": ["师资依赖", "扩张难", "AI冲击"],
            "优先级": ["课程标准化", "品牌化", "线上化"],
        },
    },

    "心理咨询": {
        "基础特征": {
            "客户范围": "national",
            "价格区间": "200-2000/次",
            "目标用户": ["心理困扰者", "情绪问题人群", "自我成长者"],
        },
        "维度分析": {
            "industry_stage": {
                "score": 8,
                "status": "爆发期",
                "description": "心理健康意识觉醒，市场爆发",
                "advice": "专业+温度是制胜关键",
            },
            "track_growth": {
                "score": 9,
                "growth_rate": "20%+/年",
                "description": "需求高速增长，年轻群体接受度高",
                "advice": "是长期赛道，但需要专业",
            },
            "replication": {
                "score": 6,
                "核心资源": "专业方法论 + 咨询经验 + 共情力",
                "经验来源": "专业训练 + 案例积累",
                "资源获取": {
                    "方法论": "可标准化（核心资产）",
                    "共情力": "难以复制",
                    "资质": "需考证"
                },
                "difficulty_rating": "★★☆☆☆",
                "replication_path": "内容/课程/教程",
                "advice": "把咨询经验标准化成方法论 → 做成课程/教程 → 用内容杠杆放大"
            },
            "demand_type": {
                "score": 8,
                "type": "刚需+情绪",
                "description": "心理问题普遍，但付费意识增强",
                "seven_sins": ["懒惰", "贪婪"],
                "advice": "解决'不想承认但需要'的心理障碍",
            },
            "business_mode": {
                "score": 8,
                "mode": "服务为主",
                "description": "咨询/课程/内容",
                "advice": "咨询高客单，内容/课程规模化",
            },
            "time_trap": {
                "score": 6,
                "status": "部分被困",
                "description": "咨询耗时间，但可排班",
                "advice": "内容获客，咨询分层",
            },
            "asset_check": {
                "score": 6,
                "assets": ["专业能力", "案例经验", "来访者信任"],
                "missing": ["品牌", "标准化"],
                "advice": "积累专业品牌和方法论",
            },
            "leverage_diagnosis": {
                "score": 5,
                "current_leverages": ["知识杠杆"],
                "available_leverages": ["影响力杠杆（科普）", "产品杠杆（课程）"],
                "advice": "做科普内容建立信任",
            },
            "decision_difficulty": {
                "score": 7,
                "cognition_gap": "高（专业知识）",
                "info_gap": "低",
                "skill_gap": "高（共情/咨询技术）",
                "resource_gap": "中（资质）",
                "advice": "核心是专业能力和信任",
            },
            "ai_crisis": {
                "score": 5,
                "replacement_risk": "★★☆☆☆",
                "quantifiable": True,
                "quantification_desc": "AI可做初筛/陪伴，难替代深度咨询",
                "mode_change": "AI辅助 → 但深度仍靠人",
                "opportunity": "AI初筛 + 人工深度",
                "advice": "AI做不了的情感共鸣是核心价值",
            },
        },
        "综合结论": {
            "核心优势": ["需求爆发", "客单价高", "可建立IP"],
            "核心问题": ["专业门槛高", "信任难建立", "时间被困"],
            "优先级": ["专业积累", "个人IP", "内容获客"],
        },
    },

    "法律咨询": {
        "基础特征": {
            "客户范围": "national",
            "价格区间": "500-10万+",
            "目标用户": ["有纠纷当事人", "企业主", "普通民众"],
        },
        "维度分析": {
            "industry_stage": {
                "score": 7,
                "status": "成熟期",
                "description": "法律意识增强，市场扩大",
                "advice": "专业+性价比是机会",
            },
            "track_growth": {
                "score": 7,
                "growth_rate": "10-15%/年",
                "description": "民事纠纷增加，需求稳定增长",
                "advice": "做垂直领域专家",
            },
            "replication": {
                "score": 5,
                "核心资源": "法律知识 + 经验 + 案例",
                "经验来源": "多年执业经验",
                "资源获取": {
                    "法律知识": "可标准化（核心）",
                    "经验": "需积累",
                    "资质": "需考证"
                },
                "difficulty_rating": "★★☆☆☆",
                "replication_path": "内容/课程/工具",
                "advice": "把法律知识标准化 → 做成课程/工具书 → 内容杠杆放大"
            },
            "demand_type": {
                "score": 9,
                "type": "刚需+恐惧",
                "description": "纠纷恐惧，付费意识强",
                "seven_sins": ["贪婪", "傲慢"],
                "advice": "解决'怕打官司'的恐惧",
            },
            "business_mode": {
                "score": 7,
                "mode": "服务为主",
                "description": "诉讼/非诉/咨询",
                "advice": "咨询/课程标准化，诉讼高端化",
            },
            "time_trap": {
                "score": 5,
                "status": "部分被困",
                "description": "案件耗时间，但可分工",
                "advice": "团队化+流程化",
            },
            "asset_check": {
                "score": 6,
                "assets": ["法律知识", "办案经验", "客户信任"],
                "missing": ["品牌", "渠道"],
                "advice": "积累专业品牌和案例",
            },
            "leverage_diagnosis": {
                "score": 5,
                "current_leverages": ["知识杠杆"],
                "available_leverages": ["影响力杠杆（普法）", "产品杠杆（工具）"],
                "advice": "做普法内容获客",
            },
            "decision_difficulty": {
                "score": 8,
                "cognition_gap": "高（专业知识）",
                "info_gap": "中",
                "skill_gap": "高（诉讼能力）",
                "resource_gap": "中（资质）",
                "advice": "核心是专业和信任",
            },
            "ai_crisis": {
                "score": 7,
                "replacement_risk": "★★★★☆",
                "quantifiable": True,
                "quantification_desc": "AI法律咨询崛起，基础问题可被替代",
                "mode_change": "AI回答 → 替代基础咨询",
                "opportunity": "AI辅助 + 人工深度",
                "advice": "专注AI做不了的高端诉讼",
            },
        },
        "综合结论": {
            "核心优势": ["需求刚", "客单价高", "可建立品牌"],
            "核心问题": ["专业门槛高", "获客难", "AI冲击"],
            "优先级": ["专业深耕", "个人IP", "垂直领域"],
        },
    },

    "房产买卖": {
        "基础特征": {
            "客户范围": "local",
            "价格区间": "50-1000万+",
            "目标用户": ["购房刚需", "投资客", "改善型"],
        },
        "维度分析": {
            "industry_stage": {
                "score": 6,
                "status": "成熟期",
                "description": "市场成熟，但分化严重",
                "advice": "专业选房服务是机会",
            },
            "track_growth": {
                "score": 5,
                "growth_rate": "受政策影响大",
                "description": "市场波动，机会与风险并存",
                "advice": "关注政策，精选赛道",
            },
            "replication": {
                "score": 4,
                "核心资源": "房源信息 + 谈判能力 + 行业经验",
                "经验来源": "多年踩盘实战",
                "资源获取": {
                    "房源": "可积累（核心）",
                    "谈判": "需经验",
                    "关系": "难复制"
                },
                "difficulty_rating": "★★★☆☆",
                "replication_path": "内容/课程/培训",
                "advice": "把购房经验标准化 → 做成课程/培训 → 内容杠杆放大"
            },
            "demand_type": {
                "score": 9,
                "type": "刚需+面子",
                "description": "买房是大事，面子需求强",
                "seven_sins": ["傲慢", "懒惰"],
                "advice": "解决'怕买错'的恐惧",
            },
            "business_mode": {
                "score": 6,
                "mode": "服务为主",
                "description": "中介/咨询/代购",
                "advice": "提高客单价，做深度服务",
            },
            "time_trap": {
                "score": 6,
                "status": "部分被困",
                "description": "带看耗时，但可团队",
                "advice": "团队分工，专业化",
            },
            "asset_check": {
                "score": 5,
                "assets": ["房源信息", "客户关系", "经验"],
                "missing": ["品牌", "独家房源"],
                "advice": "积累专业口碑和房源",
            },
            "leverage_diagnosis": {
                "score": 4,
                "current_leverages": ["关系杠杆"],
                "available_leverages": ["影响力杠杆（内容）", "信息杠杆（数据）"],
                "advice": "做选房内容建立专业形象",
            },
            "decision_difficulty": {
                "score": 8,
                "cognition_gap": "高（需要专业）",
                "info_gap": "高（信息不对称）",
                "skill_gap": "中（谈判/分析）",
                "resource_gap": "中（房源/资金）",
                "advice": "核心是信息和人脉",
            },
            "ai_crisis": {
                "score": 5,
                "replacement_risk": "★★☆☆☆",
                "quantifiable": True,
                "quantification_desc": "AI匹配房源，但线下服务难替代",
                "mode_change": "AI辅助 → 提高效率",
                "opportunity": "AI找房 + 人工服务",
                "advice": "用AI工具提效，专注服务",
            },
        },
        "综合结论": {
            "核心优势": ["需求刚", "客单价高", "本地资源"],
            "核心问题": ["政策风险", "竞争激烈", "获客难"],
            "优先级": ["专业深耕", "内容获客", "服务差异化"],
        },
    },
}


# ==================== 知识图谱扩展：通用模式 ====================

def extend_knowledge_graph():
    """扩展知识图谱 - 为未收录行业生成默认分析"""
    pass


# ==================== 辅助函数 ====================

def get_dimension_config(key: str) -> Dict:
    """获取维度配置"""
    return DIMENSIONS_CONFIG.get(key, {
        "name": key,
        "icon": "📊",
        "description": "",
        "system_able": True,
    })


def get_status_emoji(status: str) -> str:
    """状态emoji映射"""
    mapping = {
        "太早": "🔴",
        "刚好": "🟢",
        "正当时": "🟢",
        "爆发期": "🟢",
        "成熟期": "🟡",
        "夕阳": "⚫",
    }
    return mapping.get(status, "⚪")


def get_score_level(score: float) -> str:
    """评分等级"""
    if score >= 8:
        return "high"
    elif score >= 6:
        return "medium"
    else:
        return "low"


# ==================== 主服务类 ====================

class BusinessModelDesignService:
    """商业模式设计服务"""

    def __init__(self):
        self.knowledge_graph = BUSINESS_KNOWLEDGE_GRAPH
        self.dimensions_config = DIMENSIONS_CONFIG

    def match_business(self, business_keyword: str) -> Optional[str]:
        """匹配业务类型（优先精确/模糊匹配知识库）"""
        if not business_keyword:
            return None
        keyword = business_keyword.lower().strip()
        if not keyword:
            return None

        # 精确匹配
        for business_type in self.knowledge_graph.keys():
            if keyword == business_type or keyword in business_type:
                return business_type

        # 模糊匹配
        mappings = {
            "整形": "医美整形", "医美": "医美整形", "美容": "医美整形",
            "装修": "装修", "装潢": "装修",
            "留学": "留学中介", "中介": "留学中介",
            "投资": "金融投资", "理财": "金融投资", "基金": "金融投资",
            "教育": "儿童教育", "培训": "儿童教育",
            "心理": "心理咨询", "咨询": "心理咨询",
            "法律": "法律咨询", "律师": "法律咨询",
            "买房": "房产买卖", "房产": "房产买卖",
            "灌肠": "灌香肠加工", "香肠": "灌香肠加工", "腊肠": "灌香肠加工",
            "高考": "高考志愿", "志愿": "高考志愿",
        }

        for k, v in mappings.items():
            if k in keyword:
                return v

        # 没有匹配到，返回None表示需要用通用方法论
        return None

    def _analyze_business_keyword(self, keyword: str) -> Dict:
        """
        根据业务关键词智能分析
        基于纳瓦尔宝典方法论，从语义推断业务特征
        """
        keyword_lower = keyword.lower().strip()

        # ==================== 行业类型识别 ====================
        industry_type = "通用服务"
        is_time_selling = True
        time_trap_score = 6  # 默认部分被困
        business_mode = "服务为主"
        core_resources = []
        standardizable = []
        non_standardizable = []

        # 餐饮类
        if any(k in keyword_lower for k in ["餐", "饭店", "酒楼", "厨师", "外卖", "小吃"]):
            industry_type = "餐饮"
            core_resources = ["配方", "手艺", "地段", "口碑"]
            standardizable = ["菜品配方", "操作流程", "供应链", "培训手册"]
            non_standardizable = ["厨师手艺", "核心口味", "地段流量"]
            time_trap_score = 7
            business_mode = "产品+服务"

        # 教育培训类
        elif any(k in keyword_lower for k in ["培训", "教育", "学校", "辅导", "家教", "课程"]):
            industry_type = "教育培训"
            core_resources = ["师资", "课程", "方法论", "口碑"]
            standardizable = ["课程内容", "教学方法", "教材", "SOP流程"]
            non_standardizable = ["优秀师资", "个人魅力"]
            time_trap_score = 5
            business_mode = "服务为主"

        # 咨询类
        elif any(k in keyword_lower for k in ["咨询", "顾问", "律师", "心理", "财务", "设计"]):
            industry_type = "专业咨询"
            core_resources = ["专业知识", "经验", "资质", "案例"]
            standardizable = ["方法论", "流程", "模板", "案例库"]
            non_standardizable = ["个人经验", "信任关系"]
            time_trap_score = 6
            business_mode = "服务为主"

        # 销售/零售类
        elif any(k in keyword_lower for k in ["销售", "零售", "电商", "淘宝", "开店", "店铺"]):
            industry_type = "销售零售"
            core_resources = ["货源", "流量", "运营", "供应链"]
            standardizable = ["运营流程", "话术", "供应链", "选品方法"]
            non_standardizable = ["个人关系", "特殊货源"]
            time_trap_score = 4
            business_mode = "产品为主"

        # 医疗健康类
        elif any(k in keyword_lower for k in ["医疗", "诊所", "医院", "健康", "医美", "整形"]):
            industry_type = "医疗健康"
            core_resources = ["资质", "技术", "口碑", "医生"]
            standardizable = ["流程", "服务SOP", "培训体系"]
            non_standardizable = ["医生技术", "资质许可"]
            time_trap_score = 8
            business_mode = "服务为主"

        # 制造生产类
        elif any(k in keyword_lower for k in ["生产", "制造", "工厂", "加工", "定制"]):
            industry_type = "生产制造"
            core_resources = ["技术", "设备", "供应链", "产能"]
            standardizable = ["工艺流程", "配方", "质量标准", "管理SOP"]
            non_standardizable = ["核心工艺", "设备投资"]
            time_trap_score = 6
            business_mode = "产品为主"

        # 内容创作/媒体类
        elif any(k in keyword_lower for k in ["内容", "创作", "自媒体", "短视频", "直播", "博主"]):
            industry_type = "内容创作"
            core_resources = ["内容创作能力", "粉丝", "IP", "流量"]
            standardizable = ["创作方法论", "选题策略", "变现模式"]
            non_standardizable = ["个人魅力", "独特视角"]
            time_trap_score = 3
            business_mode = "内容为主"
            is_time_selling = False  # 内容创作天然不是纯卖时间

        # 通用服务业（默认）
        else:
            core_resources = ["专业技能", "客户关系", "口碑"]
            standardizable = ["服务流程", "方法论", "SOP", "教程"]
            non_standardizable = ["个人经验", "人际能力"]

        # ==================== 计算评分 ====================

        # 赛道增速（根据行业类型）
        track_growth_map = {
            "餐饮": {"score": 6, "rate": "稳定", "desc": "民以食为天，但竞争激烈"},
            "教育培训": {"score": 7, "rate": "10-15%/年", "desc": "需求持续增长"},
            "专业咨询": {"score": 7, "rate": "稳定增长", "desc": "专业服务需求增加"},
            "销售零售": {"score": 6, "rate": "受平台影响", "desc": "线上线下融合"},
            "医疗健康": {"score": 8, "rate": "15%+/年", "desc": "健康意识提升"},
            "生产制造": {"score": 5, "rate": "稳定", "desc": "传统行业，稳健"},
            "内容创作": {"score": 9, "rate": "高速增长", "desc": "新媒体爆发期"},
            "通用服务": {"score": 6, "rate": "待分析", "desc": "需要具体了解"},
        }
        track_info = track_growth_map.get(industry_type, track_growth_map["通用服务"])

        # ==================== 生成分析结果 ====================

        return {
            "industry_type": industry_type,
            "is_time_selling": is_time_selling,
            "time_trap_score": time_trap_score,
            "business_mode": business_mode,
            "core_resources": core_resources,
            "standardizable": standardizable,
            "non_standardizable": non_standardizable,
            "track_info": track_info,
            "demand_type": self._get_demand_type_for_industry(industry_type),
            "ai_crisis_info": self._get_ai_crisis_for_industry(industry_type),
        }

    def _get_demand_type_for_industry(self, industry_type: str) -> Dict:
        """获取需求类型分析"""
        demand_map = {
            "餐饮": {"type": "刚需+面子", "desc": "日常必需，聚会体面", "score": 8},
            "教育培训": {"type": "刚需+焦虑", "desc": "不能输在起跑线", "score": 9},
            "专业咨询": {"type": "刚需+恐惧", "desc": "解决问题，降低风险", "score": 8},
            "销售零售": {"type": "可选+贪便宜", "desc": "货比三家，追求性价比", "score": 6},
            "医疗健康": {"type": "刚需+面子", "desc": "健康刚需，医美面子", "score": 9},
            "生产制造": {"type": "刚需", "desc": "B端需求稳定", "score": 7},
            "内容创作": {"type": "娱乐+焦虑", "desc": "杀时间，缓解焦虑", "score": 7},
            "通用服务": {"type": "待分析", "desc": "需要具体了解", "score": 5},
        }
        return demand_map.get(industry_type, demand_map["通用服务"])

    def _get_ai_crisis_for_industry(self, industry_type: str) -> Dict:
        """获取AI危机分析"""
        ai_map = {
            "餐饮": {"risk": "★★☆☆☆", "desc": "口味难以完全替代，但标准化环节可优化"},
            "教育培训": {"risk": "★★★☆☆", "desc": "AI辅助教学，但深度互动仍需人"},
            "专业咨询": {"risk": "★★☆☆☆", "desc": "AI辅助分析，但信任关系仍靠人"},
            "销售零售": {"risk": "★★★☆☆", "desc": "AI客服兴起，销售话术可复制"},
            "医疗健康": {"risk": "★★☆☆☆", "desc": "AI辅助诊断，但手术仍需医生"},
            "生产制造": {"risk": "★★★☆☆", "desc": "自动化替代人工生产"},
            "内容创作": {"risk": "★★★★☆", "desc": "AI生成内容冲击，但原创IP仍稀缺"},
            "通用服务": {"risk": "★★☆☆☆", "desc": "需要具体评估"},
        }
        return ai_map.get(industry_type, ai_map["通用服务"])

    def generate_generic_analysis(self, business_keyword: str) -> Dict:
        """
        为未知业务类型生成分析
        核心逻辑交给LLM，智能分析任意业务
        """
        business_name = business_keyword.strip()

        # 先用基础规则快速识别行业类型
        analysis = self._analyze_business_keyword(business_name)

        # 构建通用维度框架（让LLM填充深度内容）
        dimensions = []
        dimension_scores = {}

        for key, config in self.dimensions_config.items():
            dimension_result = {
                "key": key,
                "name": config["name"],
                "icon": config["icon"],
                "score": 5,
                "level": "中等",
                "description": "等待LLM深度分析...",
                "advice": "",
            }

            # 复制能力维度特殊处理
            if key == "replication":
                dimension_result["core_resources"] = "、".join(analysis["core_resources"]) if analysis["core_resources"] else "待分析"
                dimension_result["experience_source"] = "待LLM分析"
                dimension_result["difficulty_rating"] = "★★★☆☆"
                dimension_result["replication_path"] = "内容/课程/标准化"
                path_list = ["内容", "课程", "标准化"]
                dimension_result["paths_detail"] = analyze_replication_paths(path_list)

            dimensions.append(dimension_result)
            dimension_scores[key] = 5

        # 调用LLM生成深度分析
        llm_analysis = self._call_llm_for_analysis(business_name, analysis)

        # 用LLM结果更新dimensions
        if llm_analysis.get("dimensions"):
            for llm_dim in llm_analysis["dimensions"]:
                for dim in dimensions:
                    if dim["key"] == llm_dim["key"]:
                        dim.update(llm_dim)
                        dimension_scores[dim["key"]] = llm_dim.get("score", 5)
                        break

        # 计算平均分
        avg_score = round(sum(dimension_scores.values()) / len(dimension_scores), 1)

        # 构建剥离路径
        detach_path = {
            "current_mode": llm_analysis.get("business_mode", analysis["business_mode"]),
            "is_time_selling": analysis["is_time_selling"],
            "standardizable_resources": llm_analysis.get("standardizable", analysis["standardizable"]),
            "non_standardizable_resources": llm_analysis.get("non_standardizable", analysis["non_standardizable"]),
            "advice": llm_analysis.get("detach_advice", "识别核心资源，制定剥离计划"),
            "phases": [
                DETACH_PHASES["phase_1"],
                DETACH_PHASES["phase_2"],
                DETACH_PHASES["phase_3"]
            ]
        }

        # 构建结论
        conclusion = {
            "core_strengths": llm_analysis.get("core_strengths", analysis["core_resources"][:3] if analysis["core_resources"] else ["待分析"]),
            "core_problems": llm_analysis.get("core_problems", ["需要深度分析"]),
            "priority_actions": llm_analysis.get("priority_actions", ["等待LLM分析"]),
            "llm_insights": llm_analysis.get("insights", ""),
        }

        return {
            "success": True,
            "is_generic": True,
            "is_llm_analyzed": True,
            "business_type": business_name,
            "input_keyword": business_keyword,
            "basic_info": {
                "行业类型": llm_analysis.get("industry_type", analysis["industry_type"]),
                "业务模式": llm_analysis.get("business_mode", analysis["business_mode"]),
                "是否卖时间": "是" if analysis["is_time_selling"] else "否",
                "客户范围": llm_analysis.get("customer_scope", "待定"),
                "价格区间": llm_analysis.get("price_range", "待定"),
                "目标用户": llm_analysis.get("target_users", ["待分析"]),
            },
            "dimensions": dimensions,
            "dimension_scores": dimension_scores,
            "avg_score": avg_score,
            "content_value": self._get_content_value(avg_score),
            "detach_path": detach_path,
            "conclusion": conclusion,
            "all_business_types": list(self.knowledge_graph.keys()),
        }

    def _call_llm_for_analysis(self, business_keyword: str, basic_analysis: Dict) -> Dict:
        """
        调用LLM深度分析业务
        """
        try:
            from services.llm import get_llm_service
            llm = get_llm_service()

            prompt = self._build_llm_analysis_prompt(business_keyword, basic_analysis)
            result = llm.chat(
                messages=prompt,
                task_type='market_analysis',
                max_tokens=3000
            )

            if result:
                return self._parse_llm_analysis_result(result, basic_analysis)
            else:
                raise Exception("LLM返回为空")

        except Exception as e:
            print(f"LLM分析失败: {e}")
            return self._get_fallback_analysis(basic_analysis)

    def _build_llm_analysis_prompt(self, business_keyword: str, basic_analysis: Dict) -> str:
        """构建LLM分析提示词"""
        industry = basic_analysis.get("industry_type", "通用服务")
        core_resources = basic_analysis.get("core_resources", [])
        standardizable = basic_analysis.get("standardizable", [])
        non_standardizable = basic_analysis.get("non_standardizable", [])
        time_trap = basic_analysis.get("time_trap_score", 6)
        business_mode = basic_analysis.get("business_mode", "服务为主")

        prompt = f"""
你是纳瓦尔宝典商业战略专家。请深度分析以下业务：

【业务关键词】{business_keyword}
【识别行业类型】{industry}
【识别业务模式】{business_mode}
【识别核心资源】{', '.join(core_resources) if core_resources else '待识别'}
【可标准化资源】{', '.join(standardizable) if standardizable else '待识别'}
【难以标准化】{', '.join(non_standardizable) if non_standardizable else '待识别'}
【时间被困程度】{'严重' if time_trap >= 7 else '部分'}（{time_trap}/10）

请基于纳瓦尔宝典的核心原则（从"卖时间"到"建立资产"）进行深度分析：

1. **行业本质** - 这个生意的本质是什么？卖什么？
2. **客户范围** - 目标客户是谁？全国还是本地？
3. **价格区间** - 典型的价格范围是多少？
4. **目标用户** - 具体是哪类人群？
5. **核心优势** - 这个业务的核心优势是什么？
6. **核心问题** - 这个业务的核心问题是什么？尤其是时间被困的问题
7. **剥离路径** - 如何从"卖时间"转变为"建立资产"？具体分几步？
8. **优先行动** - 第一步应该做什么？
9. **一句话洞察** - 用一句话说出这个业务最关键的洞察

10维度评分（1-10分）：
- 行业阶段：市场成熟度如何？
- 赛道增速：这个行业增长如何？
- 需求类型：刚需还是可选？需求强度？
- 业务模式：卖产品/服务/时间/体力？优劣？
- 时间被困：多严重？能否规模化？
- 复制能力：核心资源能否复制？
- 资产盘点：有哪些资产？缺什么？
- 杠杆诊断：有哪些杠杆可用？
- 决策难度：入场门槛高吗？
- AI危机：AI能替代吗？机遇在哪？

请用JSON格式返回：
{{
    "industry_type": "行业类型",
    "business_mode": "卖什么",
    "customer_scope": "全国/本地",
    "price_range": "价格区间",
    "target_users": ["用户1", "用户2"],
    "core_strengths": ["优势1", "优势2"],
    "core_problems": ["问题1", "问题2"],
    "standardizable": ["可标准化1", "可标准化2"],
    "non_standardizable": ["难标准化1"],
    "detach_advice": "剥离路径建议",
    "priority_actions": ["行动1", "行动2", "行动3"],
    "insights": "一句话洞察",
    "dimensions": [
        {{"key": "industry_stage", "score": 6, "description": "...", "advice": "..."}},
        {{"key": "track_growth", "score": 6, "description": "...", "advice": "..."}},
        {{"key": "demand_type", "score": 7, "description": "...", "advice": "..."}},
        {{"key": "business_mode", "score": 6, "description": "...", "advice": "..."}},
        {{"key": "time_trap", "score": {time_trap}, "description": "...", "advice": "..."}},
        {{"key": "replication", "score": 5, "description": "...", "advice": "..."}},
        {{"key": "asset_check", "score": 5, "description": "...", "advice": "..."}},
        {{"key": "leverage_diagnosis", "score": 5, "description": "...", "advice": "..."}},
        {{"key": "decision_difficulty", "score": 5, "description": "...", "advice": "..."}},
        {{"key": "ai_crisis", "score": 6, "description": "...", "advice": "..."}}
    ]
}}

要求：
- 分析要深入具体，不要空泛
- 评分要符合业务实际情况
- 剥离路径要具体可行
"""
        return prompt

    def _parse_llm_analysis_result(self, result: str, basic_analysis: Dict) -> Dict:
        """解析LLM返回结果"""
        try:
            # 尝试从结果中提取JSON
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        # 解析失败，返回基础分析
        return self._get_fallback_analysis(basic_analysis)

    def _get_fallback_analysis(self, basic_analysis: Dict) -> Dict:
        """获取备用分析（LLM不可用时）"""
        industry = basic_analysis.get("industry_type", "通用服务")

        return {
            "industry_type": industry,
            "business_mode": basic_analysis.get("business_mode", "服务为主"),
            "customer_scope": "待定",
            "price_range": "待定",
            "target_users": ["待分析"],
            "core_strengths": basic_analysis.get("core_resources", ["待分析"])[:3],
            "core_problems": ["需要深度分析才能给出具体建议"],
            "standardizable": basic_analysis.get("standardizable", []),
            "non_standardizable": basic_analysis.get("non_standardizable", []),
            "detach_advice": f"对于{industry}业务，首先识别核心资源，然后制定剥离计划",
            "priority_actions": ["明确核心资源", "识别可标准化部分", "规划杠杆路径"],
            "insights": f"{industry}业务的关键是建立可沉淀的资产",
            "dimensions": []
        }

    def _get_mode_description(self, mode: str, industry: str) -> str:
        """获取模式描述"""
        if "产品+服务" in mode:
            return f"「{industry}」业务，既卖产品又卖服务"
        elif "产品" in mode:
            return f"「{industry}」业务，以产品销售为主"
        elif "内容" in mode:
            return f"「{industry}」业务，以内容创作为核心"
        else:
            return f"「{industry}」业务，以专业服务为主"

    def _get_time_trap_description(self, score: int, industry: str) -> str:
        """获取时间被困描述"""
        if score >= 7:
            return f"「{industry}」业务严重依赖个人时间，较难规模化"
        elif score >= 5:
            return f"「{industry}」业务部分依赖时间，有一定规模化可能"
        else:
            return f"「{industry}」业务相对自由，可规模化"

    def _get_replication_advice(self, industry: str, standardizable: list) -> str:
        """获取复制建议"""
        if not standardizable:
            return "识别可标准化的资源，建立培训体系"
        top_3 = standardizable[:3]
        return f"把「{'/'.join(top_3)}」标准化 → 做成教程/流程 → 内容杠杆放大"

    def _get_detach_advice(self, analysis: Dict) -> str:
        """获取剥离建议"""
        industry = analysis["industry_type"]
        standardizable = analysis["standardizable"][:2] if analysis["standardizable"] else ["流程", "方法"]

        advice_map = {
            "餐饮": f"把菜品配方和操作流程标准化 → 做成中央厨房/加盟体系 → 睡后收入",
            "教育培训": f"把教学方法和课程内容标准化 → 做成课程产品 → 睡后收入",
            "专业咨询": f"把咨询流程和方法论标准化 → 做成课程/工具 → 睡后收入",
            "销售零售": f"把运营流程和选品方法标准化 → 做成培训/工具 → 可规模化",
            "医疗健康": f"把服务流程和培训体系标准化 → 品牌授权 → 可规模化",
            "生产制造": f"把工艺流程和质量标准固化 → 技术授权/加盟 → 可规模化",
            "内容创作": f"建立个人IP和方法论 → 课程/广告/带货 → 天然睡后收入",
            "通用服务": f"把「{'/'.join(standardizable)}」标准化 → 做成教程/培训 → 睡后收入",
        }
        return advice_map.get(industry, advice_map["通用服务"])

    def _get_priority_actions(self, analysis: Dict) -> list:
        """获取优先行动"""
        industry = analysis["industry_type"]
        actions_map = {
            "餐饮": ["标准化核心菜品", "建立培训体系", "尝试内容获客"],
            "教育培训": ["提炼教学方法", "开发课程产品", "建立内容矩阵"],
            "专业咨询": ["整理方法论", "制作案例库", "开发标准化服务"],
            "销售零售": ["优化运营流程", "建立选品标准", "尝试内容电商"],
            "医疗健康": ["建立服务SOP", "培养团队", "建立品牌"],
            "生产制造": ["固化工艺流程", "建立质量标准", "探索加盟"],
            "内容创作": ["确定IP定位", "建立内容方法论", "设计变现路径"],
            "通用服务": ["识别核心资源", "建立标准流程", "尝试内容放大"],
        }
        return actions_map.get(industry, actions_map["通用服务"])

    def analyze(
        self,
        business_keyword: str,
        user_profile: Dict = None
    ) -> Dict:
        """
        分析业务模式

        Args:
            business_keyword: 业务关键词
            user_profile: 用户画像 {
                "scope": "local/national/global",
                "years": 5,
                "accumulations": ["客户资源", "口碑", ...]
            }

        Returns:
            分析结果字典
        """
        # 匹配业务类型
        matched_business = self.match_business(business_keyword)

        if not matched_business:
            # 没有匹配到具体行业，使用通用方法论分析
            return self.generate_generic_analysis(business_keyword)

        # 获取知识图谱
        business_data = self.knowledge_graph[matched_business]
        dimension_analysis = business_data.get("维度分析", {})
        base_conclusion = business_data.get("综合结论", {})

        # 构建10维度结果
        dimensions = []
        dimension_scores = []

        for key, config in self.dimensions_config.items():
            analysis = dimension_analysis.get(key, {})
            score = analysis.get("score", 5)

            dimension_result = {
                "key": key,
                "name": config["name"],
                "icon": config["icon"],
                "score": score,
                "level": get_score_level(score),
                "status": analysis.get("status", analysis.get("type", "")),
                "description": analysis.get("description", ""),
                "advice": analysis.get("advice", ""),
                # 复制能力专用
                "core_resources": analysis.get("核心资源", ""),
                "experience_source": analysis.get("经验来源", ""),
                "resource_difficulty": analysis.get("资源获取", {}),
                "difficulty_rating": analysis.get("difficulty_rating", ""),
                "replication_path": analysis.get("replication_path", ""),
                "剥离路径": analysis.get("剥离路径", ""),
                # AI危机专用
                "replacement_risk": analysis.get("replacement_risk", ""),
                "quantifiable": analysis.get("quantifiable", False),
                "quantification_desc": analysis.get("quantification_desc", ""),
                "mode_change": analysis.get("mode_change", ""),
                "opportunity": analysis.get("opportunity", ""),
                # 决策难度专用
                "cognition_gap": analysis.get("cognition_gap", ""),
                "info_gap": analysis.get("info_gap", ""),
                "skill_gap": analysis.get("skill_gap", ""),
                "resource_gap": analysis.get("resource_gap", ""),
                # 资产/杠杆专用
                "current_assets": analysis.get("assets", []),
                "missing_assets": analysis.get("missing", []),
                "current_leverages": analysis.get("current_leverages", []),
                "available_leverages": analysis.get("available_leverages", []),
            }

            # 复制路径特殊处理：生成详细分析
            if key == "replication" and analysis.get("replication_path"):
                path_list = analysis["replication_path"].split("/")
                dimension_result["paths_detail"] = analyze_replication_paths(path_list)

            dimensions.append(dimension_result)
            dimension_scores.append(score)

        # 生成剥离路径（基于纳瓦尔宝典）
        detach_path = generate_detach_path(business_data)
        avg_score = round(sum(dimension_scores) / len(dimension_scores), 1)

        # 综合结论（可后续用LLM增强）
        conclusion = {
            "overall_score": avg_score,
            "core_strengths": base_conclusion.get("核心优势", []),
            "core_problems": base_conclusion.get("核心问题", []),
            "priority_actions": base_conclusion.get("优先级", []),
            "score_breakdown": {
                "维度得分": f"{avg_score}/10",
                "方向建议": "基于分析结果，用户应优先关注以下方向...",
            }
        }

        # 构建最终结果
        result = {
            "success": True,
            "business_type": matched_business,
            "input_keyword": business_keyword,
            "user_profile": user_profile or {},
            "basic_info": business_data.get("基础特征", {}),
            "dimensions": dimensions,
            "dimension_scores": {
                d["key"]: d["score"] for d in dimensions
            },
            "avg_score": avg_score,
            "content_value": self._get_content_value(avg_score),
            "conclusion": conclusion,
            "detach_path": detach_path,  # 剥离路径（纳瓦尔宝典）
            "all_business_types": list(self.knowledge_graph.keys()),
        }

        return result

    def _get_content_value(self, score: float) -> str:
        """内容价值评级"""
        if score >= 8:
            return "极高价值"
        elif score >= 7:
            return "高价值"
        elif score >= 6:
            return "中等价值"
        else:
            return "低价值"

    def generate_llm_conclusion(
        self,
        business_keyword: str,
        analysis_result: Dict
    ) -> Dict:
        """
        用LLM生成综合结论（后续增强）

        Returns:
            增强后的结论
        """
        # 预留接口，后续接入LLM
        return analysis_result.get("conclusion", {})

    def get_available_businesses(self) -> List[Dict]:
        """获取所有可用的业务类型"""
        businesses = []
        for name, data in self.knowledge_graph.items():
            businesses.append({
                "name": name,
                "scope": data.get("基础特征", {}).get("客户范围", ""),
                "price_range": data.get("基础特征", {}).get("价格区间", ""),
            })
        return businesses


# ==================== 导出单例 ====================

business_model_service = BusinessModelDesignService()
