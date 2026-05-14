"""
纳瓦尔宝典模块化分析系统

核心框架：财富 = 睡觉时仍在为你赚钱的资产

分析流程：
  M1：业务本质诊断 → 你在卖什么？
  M2：时间陷阱评估 → 你被困住了吗？
  M3：资产盘点 → 你有什么资产？
  M4：杠杆诊断 → 哪些杠杆可用？
  M5：剥离路径 → 怎么从0到1？

最终输出：
  - 各模块详细分析
  - 三阶段行动计划
  - 综合结论与洞察
"""

from typing import Dict, List, Optional, Any
import json
import re


# ==================== 分析模块定义 ====================

ANALYSIS_MODULES = {
    "M1": {
        "id": "M1",
        "name": "业务本质诊断",
        "icon": "🔍",
        "description": "你在卖什么？卖给谁？怎么卖？",
        "color": "#6366f1",
    },
    "M2": {
        "id": "M2",
        "name": "时间陷阱评估",
        "icon": "⏰",
        "description": "你被困住了吗？能规模化吗？",
        "color": "#ef4444",
    },
    "M3": {
        "id": "M3",
        "name": "资产盘点",
        "icon": "💎",
        "description": "你有什么资产？哪些能沉淀？",
        "color": "#f59e0b",
    },
    "M4": {
        "id": "M4",
        "name": "杠杆诊断",
        "icon": "🚀",
        "description": "哪些杠杆可用？怎么放大？",
        "color": "#10b981",
    },
    "M5": {
        "id": "M5",
        "name": "剥离路径",
        "icon": "🎯",
        "description": "怎么从卖时间到建立资产？",
        "color": "#3b82f6",
    }
}


# ==================== 卖什么类型定义 ====================

SELL_TYPES = {
    "产品": {"name": "产品（有形商品）", "icon": "📦", "scalable": True},
    "服务": {"name": "服务（技能/时间）", "icon": "🛠️", "scalable": False},
    "信息差": {"name": "信息差（代理/中介）", "icon": "🔄", "scalable": True},
    "许可": {"name": "许可（资质/牌照）", "icon": "📜", "scalable": True},
    "注意力": {"name": "注意力（流量/广告）", "icon": "👁️", "scalable": True}
}


# ==================== 时间陷阱等级 ====================

TIME_TRAP_LEVELS = {
    1: {"level": 1, "name": "可规模化", "icon": "🟢", "color": "#10b981"},
    2: {"level": 2, "name": "部分受限", "icon": "🟡", "color": "#f59e0b"},
    3: {"level": 3, "name": "严重被困", "icon": "🔴", "color": "#ef4444"}
}


# ==================== 资产层级定义 ====================

ASSET_LEVELS = {
    1: {"level": 1, "name": "数字资产", "icon": "💎", "color": "#8b5cf6"},
    2: {"level": 2, "name": "实体资产", "icon": "🏗️", "color": "#f59e0b"},
    3: {"level": 3, "name": "人力资产", "icon": "🤝", "color": "#3b82f6"},
    4: {"level": 4, "name": "金融资产", "icon": "📈", "color": "#10b981"}
}


# ==================== 杠杆类型定义 ====================

LEVERAGE_TYPES = {
    "influence": {
        "id": "influence", "name": "影响力杠杆", "icon": "📱", "level": 1,
        "description": "最容易，零成本起步", "examples": ["内容", "短视频", "社群", "IP"]
    },
    "product": {
        "id": "product", "name": "产品杠杆", "icon": "📦", "level": 2,
        "description": "一次开发，多次销售", "examples": ["软件", "课程", "书籍", "加盟"]
    },
    "labor": {
        "id": "labor", "name": "人力杠杆", "icon": "👥", "level": 3,
        "description": "用别人的时间放大", "examples": ["团队", "外包", "合伙人"]
    },
    "capital": {
        "id": "capital", "name": "资本杠杆", "icon": "💰", "level": 4,
        "description": "用钱生钱，需要积累", "examples": ["投资", "融资"]
    }
}


# ==================== 三阶段剥离路径 ====================

DETACH_PHASES = {
    "phase1": {
        "id": "phase1", "name": "阶段一：止损", "icon": "🛑", "color": "#ef4444",
        "description": "停止无法沉淀资产的单纯时间售卖",
        "tasks": [
            "列出每天做的工作",
            "标记哪些是只有你能做",
            "标记哪些是可标准化/可外包",
            "停止或外包纯卖时间的工作"
        ],
        "key_question": "这件事如果不我用，会怎样？"
    },
    "phase2": {
        "id": "phase2", "name": "阶段二：沉淀", "icon": "🏗️", "color": "#f59e0b",
        "description": "建立可复制的资产",
        "tasks": [
            "提炼SOP（标准化流程）",
            "开发教程/课程",
            "建立案例库",
            "打造个人IP"
        ],
        "key_question": "这件事能做第二份吗？"
    },
    "phase3": {
        "id": "phase3", "name": "阶段三：杠杆", "icon": "🚀", "color": "#10b981",
        "description": "用杠杆放大资产价值",
        "tasks": [
            "内容杠杆：做内容获客",
            "产品杠杆：把教程产品化",
            "人力杠杆：组建团队/招代理",
            "资本杠杆：（后期）投资扩张"
        ],
        "key_question": "这件事能规模化吗？"
    }
}


# ==================== 模块化分析服务 ====================

class ModularAnalysisService:
    """模块化分析服务"""

    def __init__(self):
        self.modules = ANALYSIS_MODULES
        self.sell_types = SELL_TYPES
        self.time_trap_levels = TIME_TRAP_LEVELS
        self.asset_levels = ASSET_LEVELS
        self.leverage_types = LEVERAGE_TYPES
        self.detach_phases = DETACH_PHASES

    def analyze(self, business_keyword: str, user_profile: Dict = None, use_llm: bool = True) -> Dict:
        """执行完整模块化分析"""
        business_name = business_keyword.strip()

        # M1: 业务本质诊断
        m1_result = self.analyze_business_essence(business_name, use_llm)

        # M2: 时间陷阱评估
        m2_result = self.analyze_time_trap(business_name, m1_result, use_llm)

        # M3: 资产盘点
        m3_result = self.analyze_assets(business_name, m1_result, use_llm)

        # M4: 杠杆诊断
        m4_result = self.analyze_leverage(business_name, m1_result, m2_result, use_llm)

        # M5: 剥离路径
        m5_result = self.generate_detach_path(m1_result, m2_result, m3_result, m4_result)

        # 综合结论
        conclusion = self.generate_conclusion(m1_result, m2_result, m3_result, m4_result, m5_result)

        return {
            "success": True,
            "business_keyword": business_name,
            "modules": {"M1": m1_result, "M2": m2_result, "M3": m3_result, "M4": m4_result, "M5": m5_result},
            "conclusion": conclusion,
            "module_order": ["M1", "M2", "M3", "M4", "M5"]
        }

    # ==================== M1: 业务本质诊断 ====================

    def analyze_business_essence(self, business_keyword: str, use_llm: bool = True) -> Dict:
        """M1: 业务本质诊断"""
        basic_analysis = self._identify_sell_type(business_keyword)

        if use_llm:
            llm_result = self._llm_analyze_essence(business_keyword, basic_analysis)
            if llm_result:
                basic_analysis.update(llm_result)

        sell_type = basic_analysis.get("sell_type", "服务")
        sell_type_info = self.sell_types.get(sell_type, self.sell_types["服务"])

        return {
            "module_id": "M1",
            "module_name": self.modules["M1"]["name"],
            "icon": self.modules["M1"]["icon"],
            "color": self.modules["M1"]["color"],
            "sell_type": sell_type,
            "sell_type_info": sell_type_info,
            "customer_type": basic_analysis.get("customer_type", "toC"),
            "customer_desc": basic_analysis.get("customer_desc", "个人消费者"),
            "target_users": basic_analysis.get("target_users", ["待分析"]),
            "price_range": basic_analysis.get("price_range", "待定"),
            "price_unit": basic_analysis.get("price_unit", "元/次"),
            "revenue_model": basic_analysis.get("revenue_model", "一次性"),
            "revenue_desc": basic_analysis.get("revenue_desc", "做完一次收一次钱"),
            "scalable": basic_analysis.get("scalable", False),
            "description": basic_analysis.get("description", ""),
            "insights": basic_analysis.get("insights", ""),
            "score": basic_analysis.get("M1_score", 5),
            "level": self._get_score_level(basic_analysis.get("M1_score", 5)),
            "recommendations": basic_analysis.get("recommendations", [
                "明确你的核心卖的是什么",
                "识别高价值客户群体",
                "探索可规模化的收入模式"
            ])
        }

    def _identify_sell_type(self, keyword: str) -> Dict:
        """识别卖什么类型"""
        keyword_lower = keyword.lower()

        # 产品类
        if any(k in keyword_lower for k in ["零售", "电商", "淘宝", "店铺", "超市", "批发", "制造", "生产", "加工"]):
            return {
                "sell_type": "产品", "scalable": True, "customer_type": "toC",
                "customer_desc": "个人消费者", "revenue_model": "一次性+重复",
                "revenue_desc": "卖货为主，可开发会员/复购", "M1_score": 7
            }

        # 信息差/代理类
        if any(k in keyword_lower for k in ["中介", "代理", "经纪", "居间", "撮合", "平台"]):
            return {
                "sell_type": "信息差", "scalable": True, "customer_type": "toB",
                "customer_desc": "企业客户", "revenue_model": "佣金/服务费",
                "revenue_desc": "撮合交易，收取佣金", "M1_score": 7
            }

        # 许可/资质类
        if any(k in keyword_lower for k in ["医疗", "诊所", "法律", "律师", "教育", "培训"]):
            return {
                "sell_type": "许可", "scalable": True, "customer_type": "toC",
                "customer_desc": "个人消费者", "revenue_model": "服务费",
                "revenue_desc": "靠资质门槛，建立品牌", "M1_score": 8
            }

        # 餐饮类
        if any(k in keyword_lower for k in ["餐", "饭店", "酒楼", "厨师", "外卖", "小吃", "烧烤", "火锅", "面馆", "早餐", "奶茶", "咖啡"]):
            return {
                "sell_type": "产品+服务", "scalable": False, "customer_type": "toC",
                "customer_desc": "个人消费者", "revenue_model": "一次性",
                "revenue_desc": "做完一次收一次钱", "M1_score": 4,
                "description": "餐饮业务既卖产品又卖服务，核心依赖厨师手艺",
                "insights": "餐饮最大的问题是口味难以标准化，扩张受限"
            }

        # 注意力/流量类
        if any(k in keyword_lower for k in ["内容", "创作", "自媒体", "短视频", "直播", "博主", "网红", "主播"]):
            return {
                "sell_type": "注意力", "scalable": True, "customer_type": "toC",
                "customer_desc": "粉丝/用户", "revenue_model": "广告+带货+打赏",
                "revenue_desc": "积累流量，变现多元化", "M1_score": 8
            }

        # 咨询/顾问类
        if any(k in keyword_lower for k in ["咨询", "顾问", "心理", "财务", "设计", "策划", "代账", "记账"]):
            return {
                "sell_type": "服务", "scalable": False, "customer_type": "toB",
                "customer_desc": "企业客户", "revenue_model": "项目制/顾问费",
                "revenue_desc": "按项目或时间收费", "M1_score": 5
            }

        # 默认：服务
        return {
            "sell_type": "服务", "scalable": False, "customer_type": "toC",
            "customer_desc": "个人消费者", "revenue_model": "一次性",
            "revenue_desc": "做完一次收一次钱", "M1_score": 5
        }

    def _llm_analyze_essence(self, business_keyword: str, basic_analysis: Dict) -> Optional[Dict]:
        """LLM增强业务本质分析"""
        try:
            from services.llm import get_llm_service
            llm = get_llm_service()

            prompt = f"""你是纳瓦尔宝典商业战略专家。请分析以下业务的本质：

业务：{business_keyword}
基础识别：卖{basic_analysis.get('sell_type')}

请分析：
1. 目标客户是谁？具体画像？
2. 典型的价格区间？
3. 收入模式是一次性还是重复性？
4. 这个业务可规模化吗？

请用JSON格式返回：
{{
    "customer_desc": "客户描述",
    "target_users": ["用户1", "用户2"],
    "price_range": "价格区间",
    "revenue_model": "收入模式",
    "scalable": true/false,
    "description": "业务本质描述",
    "insights": "关键洞察",
    "M1_score": 1-10
}}"""
            result = llm.chat(messages=prompt, max_tokens=1500)
            if result:
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            print(f"LLM分析M1失败: {e}")
        return None

    # ==================== M2: 时间陷阱评估 ====================

    def analyze_time_trap(self, business_keyword: str, m1_result: Dict, use_llm: bool = True) -> Dict:
        """M2: 时间陷阱评估"""
        basic_analysis = self._assess_time_trap(business_keyword, m1_result)

        if use_llm:
            llm_result = self._llm_analyze_time_trap(business_keyword, m1_result, basic_analysis)
            if llm_result:
                basic_analysis.update(llm_result)

        trap_score = basic_analysis.get("trap_score", 6)
        if trap_score >= 7:
            trap_level = 3
        elif trap_score >= 5:
            trap_level = 2
        else:
            trap_level = 1

        return {
            "module_id": "M2",
            "module_name": self.modules["M2"]["name"],
            "icon": self.modules["M2"]["icon"],
            "color": self.modules["M2"]["color"],
            "trap_score": trap_score,
            "trap_level": trap_level,
            "trap_info": self.time_trap_levels[trap_level],
            "can_continue_without_you": basic_analysis.get("can_continue_without_you", "待评估"),
            "core_worker_replacement": basic_analysis.get("core_worker_replacement", "待评估"),
            "your_exclusive_work_ratio": basic_analysis.get("your_exclusive_work_ratio", "待评估"),
            "trapped_reason": basic_analysis.get("trapped_reason", ""),
            "scalable_reason": basic_analysis.get("scalable_reason", ""),
            "description": basic_analysis.get("description", ""),
            "insights": basic_analysis.get("insights", ""),
            "score": trap_score,
            "level": self._get_score_level(trap_score),
            "key_questions": [
                "把你踢出业务，业务能继续运转吗？",
                "你不在的时候，谁来做核心工作？",
                "有多少时间在做只有你能做的事？"
            ],
            "recommendations": basic_analysis.get("recommendations", [
                "识别业务中对你的依赖点",
                "把核心工作标准化或找人替代",
                "减少只有你能做的工作占比"
            ])
        }

    def _assess_time_trap(self, keyword: str, m1_result: Dict) -> Dict:
        """评估时间陷阱程度"""
        keyword_lower = keyword.lower()
        sell_type = m1_result.get("sell_type", "")

        # 严重被困
        if any(k in keyword_lower for k in ["餐", "厨师", "医生", "手艺人", "理发", "美容", "按摩"]):
            return {
                "trap_score": 8,
                "can_continue_without_you": "不能",
                "core_worker_replacement": "很难，你是核心",
                "your_exclusive_work_ratio": "80%以上",
                "trapped_reason": "核心工作需要你的亲自参与",
                "scalable_reason": "手艺/服务难以复制",
                "description": "严重时间陷阱：人停店停",
                "insights": "必须想办法标准化或找人替代",
                "recommendations": [
                    "把核心技能提炼成可复制的流程",
                    "培养徒弟/团队分担工作",
                    "考虑用产品化替代部分服务"
                ]
            }

        # 中度陷阱
        if any(k in keyword_lower for k in ["咨询", "顾问", "培训", "教练", "心理"]):
            return {
                "trap_score": 6,
                "can_continue_without_you": "部分可以",
                "core_worker_replacement": "可以培养替代者",
                "your_exclusive_work_ratio": "50%左右",
                "trapped_reason": "咨询需要专业能力，但可以标准化部分",
                "scalable_reason": "方法论可以复制，但个人品牌难",
                "description": "中度时间陷阱：部分可规模化",
                "insights": "把你的方法论标准化，做课程/培训",
                "recommendations": [
                    "提炼咨询方法论",
                    "开发标准化的咨询工具",
                    "培养其他咨询师"
                ]
            }

        # 可规模化
        if any(k in keyword_lower for k in ["内容", "创作", "电商", "零售", "批发", "代理", "中介"]):
            return {
                "trap_score": 4,
                "can_continue_without_you": "可以",
                "core_worker_replacement": "容易，找人替代",
                "your_exclusive_work_ratio": "20%以下",
                "trapped_reason": "业务可标准化，流程可复制",
                "scalable_reason": "产品/流程容易复制",
                "description": "轻度时间陷阱：业务可规模化",
                "insights": "优化流程，建立团队，用杠杆放大",
                "recommendations": [
                    "建立标准操作流程",
                    "组建团队分担工作",
                    "探索加盟/代理模式"
                ]
            }

        return {
            "trap_score": 6,
            "can_continue_without_you": "待评估",
            "core_worker_replacement": "待评估",
            "your_exclusive_work_ratio": "待评估",
            "trapped_reason": "需要进一步评估",
            "scalable_reason": "需要进一步评估",
            "description": "时间陷阱程度待评估",
            "insights": "需要深度分析才能确定",
            "recommendations": ["深入分析业务中对人的依赖", "识别可标准化的环节", "制定去人化计划"]
        }

    def _llm_analyze_time_trap(self, business_keyword: str, m1_result: Dict, basic_analysis: Dict) -> Optional[Dict]:
        """LLM增强时间陷阱分析"""
        try:
            from services.llm import get_llm_service
            llm = get_llm_service()

            prompt = f"""评估以下业务的时间陷阱程度：

业务：{business_keyword}
卖什么：{m1_result.get('sell_type')}

请回答：
1. 把你踢出业务，业务能继续运转吗？（完全能/部分能/不能）
2. 这个业务的时间陷阱评分（1-10）

请用JSON格式返回：
{{
    "can_continue_without_you": "能/部分能/不能",
    "core_worker_replacement": "描述",
    "your_exclusive_work_ratio": "百分比",
    "trap_score": 1-10,
    "trapped_reason": "被困原因",
    "scalable_reason": "可规模化的原因",
    "description": "一句话描述",
    "insights": "关键洞察"
}}"""
            result = llm.chat(messages=prompt, max_tokens=1000)
            if result:
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            print(f"LLM分析M2失败: {e}")
        return None

    # ==================== M3: 资产盘点 ====================

    def analyze_assets(self, business_keyword: str, m1_result: Dict, use_llm: bool = True) -> Dict:
        """M3: 资产盘点"""
        basic_analysis = self._inventory_assets(business_keyword, m1_result)

        if use_llm:
            llm_result = self._llm_analyze_assets(business_keyword, m1_result, basic_analysis)
            if llm_result:
                basic_analysis.update(llm_result)

        assets = basic_analysis.get("assets", [])
        digital_assets = [a for a in assets if a.get("level") == 1]
        physical_assets = [a for a in assets if a.get("level") == 2]
        human_assets = [a for a in assets if a.get("level") == 3]

        return {
            "module_id": "M3",
            "module_name": self.modules["M3"]["name"],
            "icon": self.modules["M3"]["icon"],
            "color": self.modules["M3"]["color"],
            "all_assets": assets,
            "digital_assets": digital_assets,
            "physical_assets": physical_assets,
            "human_assets": human_assets,
            "asset_levels": self.asset_levels,
            "can_assetize": basic_analysis.get("can_assetize", []),
            "missing_assets": basic_analysis.get("missing_assets", []),
            "description": basic_analysis.get("description", ""),
            "insights": basic_analysis.get("insights", ""),
            "score": basic_analysis.get("M3_score", 5),
            "level": self._get_score_level(basic_analysis.get("M3_score", 5)),
            "recommendations": basic_analysis.get("recommendations", [
                "盘点现有资产，分类管理",
                "识别可资产化的资源",
                "制定资产积累计划"
            ])
        }

    def _inventory_assets(self, keyword: str, m1_result: Dict) -> Dict:
        """盘点资产"""
        keyword_lower = keyword.lower()

        # 餐饮类资产
        if any(k in keyword_lower for k in ["餐", "饭店", "厨师", "小吃", "外卖"]):
            return {
                "assets": [
                    {"name": "招牌菜品", "level": 1, "type": "数字", "assetizable": True, "desc": "配方可做成调料产品"},
                    {"name": "客户口碑", "level": 1, "type": "数字", "assetizable": True, "desc": "可积累成品牌"},
                    {"name": "制作流程", "level": 1, "type": "数字", "assetizable": True, "desc": "可标准化成培训"},
                    {"name": "实体店铺", "level": 2, "type": "实体", "assetizable": False, "desc": "重资产，难以复制"},
                    {"name": "厨师手艺", "level": 3, "type": "人力", "assetizable": False, "desc": "核心依赖，难以转移"}
                ],
                "can_assetize": ["菜品配方", "制作流程", "口碑品牌"],
                "missing_assets": ["标准化体系", "可复制产品", "品牌授权"],
                "description": "餐饮核心资产是口味和地段",
                "insights": "口味难以资产化，但流程可以标准化",
                "M3_score": 5
            }

        # 咨询类资产
        if any(k in keyword_lower for k in ["咨询", "顾问", "心理", "法律", "财务"]):
            return {
                "assets": [
                    {"name": "方法论", "level": 1, "type": "数字", "assetizable": True, "desc": "可做成课程/工具"},
                    {"name": "案例库", "level": 1, "type": "数字", "assetizable": True, "desc": "可做成内容/产品"},
                    {"name": "个人品牌", "level": 1, "type": "数字", "assetizable": True, "desc": "可做IP/社群"},
                    {"name": "客户关系", "level": 3, "type": "人力", "assetizable": False, "desc": "难以复制"},
                    {"name": "专业资质", "level": 1, "type": "数字", "assetizable": True, "desc": "可授权/挂靠"}
                ],
                "can_assetize": ["方法论", "案例库", "个人品牌"],
                "missing_assets": ["标准化产品", "团队", "内容矩阵"],
                "description": "咨询核心资产是专业能力和方法论",
                "insights": "把方法论产品化，做课程/培训/工具",
                "M3_score": 7
            }

        # 内容创作类资产
        if any(k in keyword_lower for k in ["内容", "创作", "自媒体", "短视频", "直播"]):
            return {
                "assets": [
                    {"name": "内容版权", "level": 1, "type": "数字", "assetizable": True, "desc": "可多平台分发"},
                    {"name": "粉丝流量", "level": 1, "type": "数字", "assetizable": True, "desc": "可变现多元化"},
                    {"name": "创作方法", "level": 1, "type": "数字", "assetizable": True, "desc": "可培训其他人"},
                    {"name": "个人IP", "level": 1, "type": "数字", "assetizable": True, "desc": "可授权/联名"}
                ],
                "can_assetize": ["内容版权", "粉丝流量", "创作方法", "个人IP"],
                "missing_assets": ["多元化变现", "团队协作", "版权保护"],
                "description": "内容创作天然是数字资产",
                "insights": "最大化内容杠杆，建立IP矩阵",
                "M3_score": 9
            }

        return {
            "assets": [
                {"name": "专业技能", "level": 3, "type": "人力", "assetizable": False, "desc": "核心依赖"},
                {"name": "客户关系", "level": 3, "type": "人力", "assetizable": False, "desc": "难以转移"},
                {"name": "口碑信誉", "level": 1, "type": "数字", "assetizable": True, "desc": "可积累成品牌"}
            ],
            "can_assetize": ["口碑信誉"],
            "missing_assets": ["标准化产品", "数字资产"],
            "description": "核心资产是专业能力和口碑",
            "insights": "识别可标准化的部分，建立资产",
            "M3_score": 5
        }

    def _llm_analyze_assets(self, business_keyword: str, m1_result: Dict, basic_analysis: Dict) -> Optional[Dict]:
        """LLM增强资产盘点"""
        try:
            from services.llm import get_llm_service
            llm = get_llm_service()

            prompt = f"""盘点以下业务的资产：

业务：{business_keyword}
卖什么：{m1_result.get('sell_type')}

请分析：
1. 有哪些资产？（分有形和无形的）
2. 哪些可以资产化（变成睡后收入）？
3. 缺少哪些资产？

请用JSON格式返回：
{{
    "assets": [
        {{"name": "资产名", "level": 1-4, "assetizable": true/false, "desc": "描述"}}
    ],
    "can_assetize": ["可资产化的资产"],
    "missing_assets": ["缺少的资产"],
    "description": "资产盘点描述",
    "insights": "关键洞察",
    "M3_score": 1-10
}}"""
            result = llm.chat(messages=prompt, max_tokens=1500)
            if result:
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            print(f"LLM分析M3失败: {e}")
        return None

    # ==================== M4: 杠杆诊断 ====================

    def analyze_leverage(self, business_keyword: str, m1_result: Dict, m2_result: Dict, use_llm: bool = True) -> Dict:
        """M4: 杠杆诊断"""
        basic_analysis = self._diagnose_leverage(business_keyword, m1_result, m2_result)

        if use_llm:
            llm_result = self._llm_analyze_leverage(business_keyword, m1_result, m2_result, basic_analysis)
            if llm_result:
                basic_analysis.update(llm_result)

        return {
            "module_id": "M4",
            "module_name": self.modules["M4"]["name"],
            "icon": self.modules["M4"]["icon"],
            "color": self.modules["M4"]["color"],
            "leverage_types": self.leverage_types,
            "current_leverages": basic_analysis.get("current_leverages", []),
            "available_leverages": basic_analysis.get("available_leverages", []),
            "recommended_leverage": basic_analysis.get("recommended_leverage", "影响力杠杆"),
            "description": basic_analysis.get("description", ""),
            "insights": basic_analysis.get("insights", ""),
            "score": basic_analysis.get("M4_score", 5),
            "level": self._get_score_level(basic_analysis.get("M4_score", 5)),
            "recommendations": basic_analysis.get("recommendations", [
                "从低成本杠杆开始（影响力杠杆）",
                "积累可复制的产品（产品杠杆）",
                "后期考虑团队扩张（人力杠杆）"
            ])
        }

    def _diagnose_leverage(self, keyword: str, m1_result: Dict, m2_result: Dict) -> Dict:
        """诊断杠杆类型"""
        keyword_lower = keyword.lower()

        # 餐饮类杠杆
        if any(k in keyword_lower for k in ["餐", "饭店", "厨师", "小吃", "外卖"]):
            return {
                "current_leverages": ["人力杠杆（厨师团队）"],
                "available_leverages": [
                    self.leverage_types["product"],
                    self.leverage_types["influence"],
                    self.leverage_types["labor"]
                ],
                "recommended_leverage": "产品杠杆（标准化菜品+加盟）",
                "description": "餐饮可探索产品化和加盟",
                "insights": "把菜品标准化，做成调料包/半成品，开加盟",
                "M4_score": 6
            }

        # 咨询类杠杆
        if any(k in keyword_lower for k in ["咨询", "顾问", "心理", "法律", "财务"]):
            return {
                "current_leverages": ["人力杠杆（咨询师）"],
                "available_leverages": [
                    self.leverage_types["influence"],
                    self.leverage_types["product"],
                    self.leverage_types["labor"]
                ],
                "recommended_leverage": "产品杠杆（课程/工具）",
                "description": "咨询可探索课程和产品化",
                "insights": "把方法论做成课程，开发标准化工具",
                "M4_score": 7
            }

        # 内容创作天然杠杆
        if any(k in keyword_lower for k in ["内容", "创作", "自媒体", "短视频", "直播"]):
            return {
                "current_leverages": ["影响力杠杆（内容）"],
                "available_leverages": [
                    self.leverage_types["influence"],
                    self.leverage_types["product"],
                    self.leverage_types["capital"]
                ],
                "recommended_leverage": "影响力杠杆（内容矩阵）",
                "description": "内容创作天然是影响力杠杆",
                "insights": "最大化内容杠杆，建立IP矩阵",
                "M4_score": 9
            }

        return {
            "current_leverages": ["人力杠杆（团队）"],
            "available_leverages": list(self.leverage_types.values()),
            "recommended_leverage": "影响力杠杆（低成本起步）",
            "description": "从影响力杠杆开始",
            "insights": "先做内容获客，积累影响力",
            "M4_score": 5
        }

    def _llm_analyze_leverage(self, business_keyword: str, m1_result: Dict, m2_result: Dict, basic_analysis: Dict) -> Optional[Dict]:
        """LLM增强杠杆诊断"""
        try:
            from services.llm import get_llm_service
            llm = get_llm_service()

            prompt = f"""诊断以下业务的杠杆类型：

业务：{business_keyword}
卖什么：{m1_result.get('sell_type')}
时间陷阱：{m2_result.get('trap_level')}/3

请分析：
1. 这个业务现在用了哪些杠杆？
2. 可以尝试哪些杠杆？
3. 应该优先选择哪个杠杆？

请用JSON格式返回：
{{
    "current_leverages": ["当前使用的杠杆"],
    "available_leverages": ["可用的杠杆"],
    "recommended_leverage": "推荐优先使用的杠杆",
    "description": "杠杆诊断描述",
    "insights": "关键洞察和建议",
    "M4_score": 1-10
}}"""
            result = llm.chat(messages=prompt, max_tokens=1200)
            if result:
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            print(f"LLM分析M4失败: {e}")
        return None

    # ==================== M5: 剥离路径 ====================

    def generate_detach_path(self, m1_result: Dict, m2_result: Dict, m3_result: Dict, m4_result: Dict) -> Dict:
        """M5: 剥离路径"""
        trap_level = m2_result.get("trap_level", 2)

        # 根据时间陷阱程度生成路径
        if trap_level >= 3:
            phase1_tasks = ["识别核心依赖你的人", "把核心工作写成SOP", "找替代者并培训", "减少亲自做的服务"]
            phase2_tasks = ["把方法论/流程标准化", "开发配套工具/产品", "打造个人IP", "建立案例库"]
            phase3_tasks = ["用内容杠杆获客", "把产品规模化", "建立团队/代理体系", "探索资本杠杆"]
        elif trap_level >= 2:
            phase1_tasks = ["提炼方法论和流程", "开发标准化产品", "建立内容矩阵"]
            phase2_tasks = ["推出付费课程/产品", "建立社群/会员", "培养其他讲师/顾问"]
            phase3_tasks = ["扩大团队规模", "探索加盟/代理", "引入资本扩张"]
        else:
            phase1_tasks = ["优化现有流程", "建立团队分工", "开始内容获客"]
            phase2_tasks = ["推出标准化产品", "扩大内容影响力", "建立渠道合作"]
            phase3_tasks = ["规模化扩张", "引入资本", "探索上市"]

        return {
            "module_id": "M5",
            "module_name": self.modules["M5"]["name"],
            "icon": self.modules["M5"]["icon"],
            "color": self.modules["M5"]["color"],
            "phases": [
                {**self.detach_phases["phase1"], "tasks": phase1_tasks},
                {**self.detach_phases["phase2"], "tasks": phase2_tasks},
                {**self.detach_phases["phase3"], "tasks": phase3_tasks}
            ],
            "recommended_leverage": m4_result.get("recommended_leverage", ""),
            "can_assetize_items": m3_result.get("can_assetize", []),
            "quick_wins": self._get_quick_wins(m1_result, m2_result, m3_result),
            "description": "三阶段剥离路径",
            "insights": self._generate_path_insights(m1_result, m2_result, m3_result, m4_result),
            "score": 10 - trap_level * 2,
            "level": self._get_score_level(10 - trap_level * 2)
        }

    def _get_quick_wins(self, m1_result: Dict, m2_result: Dict, m3_result: Dict) -> List[Dict]:
        """获取快速见效的行动"""
        quick_wins = []
        can_assetize = m3_result.get("can_assetize", [])

        if any(x in str(can_assetize) for x in ["方法论", "流程"]):
            quick_wins.append({"action": "提炼方法论", "desc": "把做事流程写成文档", "time_cost": "1周", "difficulty": "低"})

        if any(x in str(can_assetize) for x in ["个人品牌", "口碑"]):
            quick_wins.append({"action": "开始做内容", "desc": "每天分享一点专业内容", "time_cost": "30分钟/天", "difficulty": "低"})

        if m2_result.get("trap_level", 2) >= 3:
            quick_wins.append({"action": "培养替代者", "desc": "找一个可以替代你的人", "time_cost": "3-6个月", "difficulty": "中"})

        if not quick_wins:
            quick_wins = [
                {"action": "识别核心资产", "desc": "盘点你最重要的资源", "time_cost": "1天", "difficulty": "低"},
                {"action": "开始做内容", "desc": "选择平台开始输出", "time_cost": "30分钟/天", "difficulty": "低"}
            ]

        return quick_wins

    def _generate_path_insights(self, m1_result: Dict, m2_result: Dict, m3_result: Dict, m4_result: Dict) -> str:
        """生成路径洞察"""
        trap_level = m2_result.get("trap_level", 2)
        sell_type = m1_result.get("sell_type", "")

        insights = []
        if "产品" in sell_type:
            insights.append("产品型业务重点是建立品牌和渠道")
        elif "服务" in sell_type:
            insights.append("服务型业务关键是标准化方法论")
        elif "注意力" in sell_type:
            insights.append("注意力型业务要最大化内容杠杆")

        if trap_level >= 3:
            insights.append("先去人化，否则无法规模化")
        elif trap_level >= 2:
            insights.append("同步做标准化和内容获客")

        leverage = m4_result.get("recommended_leverage", "")
        if "影响力" in leverage:
            insights.append("优先做内容，建立影响力")
        elif "产品" in leverage:
            insights.append("先把核心能力产品化")

        return "；".join(insights) if insights else "制定适合自己的剥离路径"

    # ==================== 综合结论 ====================

    def generate_conclusion(self, m1_result: Dict, m2_result: Dict, m3_result: Dict, m4_result: Dict, m5_result: Dict) -> Dict:
        """生成综合结论"""
        scores = [m1_result.get("score", 5), m2_result.get("score", 5), m3_result.get("score", 5),
                  m4_result.get("score", 5), m5_result.get("score", 5)]
        avg_score = round(sum(scores) / len(scores), 1)

        core_strengths = []
        if m3_result.get("digital_assets"):
            core_strengths.append("有可数字化的资产")
        if m4_result.get("recommended_leverage") == "影响力杠杆":
            core_strengths.append("适合做内容杠杆")
        if m1_result.get("scalable"):
            core_strengths.append("业务本身可规模化")

        core_problems = []
        trap_level = m2_result.get("trap_level", 2)
        if trap_level >= 3:
            core_problems.append("严重被困在时间里")
        elif trap_level >= 2:
            core_problems.append("部分受限，难以规模化")
        if not m3_result.get("digital_assets"):
            core_problems.append("缺乏可沉淀的数字资产")

        priority_actions = [qw["action"] for qw in m5_result.get("quick_wins", [])[:3]]
        if trap_level >= 3:
            priority_actions.insert(0, "先去人化/标准化")

        return {
            "overall_score": avg_score,
            "overall_level": self._get_score_level(avg_score),
            "core_strengths": core_strengths or ["有待深度分析"],
            "core_problems": core_problems or ["有待深度分析"],
            "priority_actions": priority_actions or ["等待分析"],
            "one_line_insight": self._generate_one_line_insight(m1_result, m2_result, m3_result, m4_result),
            "module_scores": {
                "M1_业务本质": m1_result.get("score", 0),
                "M2_时间陷阱": m2_result.get("score", 0),
                "M3_资产盘点": m3_result.get("score", 0),
                "M4_杠杆诊断": m4_result.get("score", 0),
                "M5_剥离路径": m5_result.get("score", 0)
            }
        }

    def _generate_one_line_insight(self, m1_result: Dict, m2_result: Dict, m3_result: Dict, m4_result: Dict) -> str:
        """生成一句话洞察"""
        sell_type = m1_result.get("sell_type", "服务")
        trap_level = m2_result.get("trap_level", 2)

        if trap_level >= 3:
            return f"{sell_type}型业务最大的坑是人停店停，必须想办法标准化或找人替代"
        elif trap_level >= 2:
            return f"{sell_type}型业务要同步做标准化和内容获客，建立可复制的资产"
        else:
            return f"{sell_type}型业务可规模化，重点是用杠杆放大现有优势"

    # ==================== 工具方法 ====================

    def _get_score_level(self, score: float) -> str:
        """根据评分获取等级"""
        if score >= 8:
            return "优秀"
        elif score >= 6:
            return "良好"
        elif score >= 4:
            return "中等"
        else:
            return "较差"


# ==================== 导出单例 ====================

modular_analysis_service = ModularAnalysisService()
