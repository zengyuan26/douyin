"""
蓝海分析服务 - 一次性生成完整的蓝海分析报告

参考 Skill: .cursor/skills/blue-ocean-expert/SKILL.md
参考模板: .cursor/skills/blue-ocean-expert/prompt_template.md

设计原则：
1. Skill 是单一事实来源 (Single Source of Truth)
2. API 代码引用 Skill 中的 Prompt 模板
3. 使用 SkillManager 自动感知文件变更
"""

import json
import re
import os
from typing import Dict, Any, Optional
from services.llm import LLMService
from services.skill_manager import get_skill_manager


class BlueOceanAnalyzer:
    """蓝海分析服务"""

    def __init__(self):
        self.llm = LLMService()
        self.current_date = self._get_current_date()
        self._skill_manager = get_skill_manager()

    def _get_current_date(self) -> str:
        """获取当前日期"""
        from datetime import datetime
        return datetime.now().strftime('%Y年%m月%d日')

    def _build_prompt_from_template(self, description: str, business_type: str, industry: str = None) -> str:
        """从 Skill 模板构建 Prompt"""
        # 使用 SkillManager 获取模板（自动缓存和更新）
        template = self._skill_manager.get_prompt_template('blue-ocean-expert')

        if template:
            try:
                return template.format(
                    current_date=self.current_date,
                    business_description=description,
                    business_type=business_type,
                    industry=industry or '根据业务描述自动判断'
                )
            except KeyError:
                # 模板格式不匹配，回退到内置方法
                pass

        # 回退到内置模板（向后兼容）
        return self._build_analysis_prompt(description, business_type, industry)

    async def analyze(self, description: str, business_type: str, industry: str = None) -> Dict[str, Any]:
        """
        一次性生成完整的蓝海分析报告

        Args:
            description: 业务描述
            business_type: 业务类型（toc/tob/both）
            industry: 行业（可选）

        Returns:
            包含所有分析结果的字典
        """
        # 构造 Prompt（从 Skill 模板加载）
        prompt = self._build_prompt_from_template(description, business_type, industry)

        # 调用 LLM（同步调用）
        response = self.llm.chat(prompt, max_tokens=16000)

        # 解析结果
        result = self._parse_response(response)

        # 确保数据完整性
        result = self._ensure_data_integrity(result)

        return result

    # ============================================================
    # 内置模板（已废弃，仅作向后兼容参考）
    # 请优先使用 .cursor/skills/blue-ocean-expert/prompt_template.md
    # ============================================================

    def _build_analysis_prompt(self, description: str, business_type: str, industry: str = None) -> str:
        """构造分析 Prompt - 参考 insights-analyst skill.md 模板"""
        return f"""你是蓝海分析专家，参考行业分析报告模板，请基于以下业务描述，一次性生成完整的蓝海分析报告。

【当前日期】：{self.current_date}

【业务描述】：
{description}

【业务类型】：{business_type}
- toc: 面向消费者（如：奶粉、化妆品、服装）
- tob: 面向企业（如：企业培训、设备采购、B2B服务）
- both: 两者都有

【行业】：{industry or '根据业务描述自动判断'}

【核心思维】：问题在先，人群在后 | 产品服务化

请一次性生成以下全部内容（必须严格遵循模板结构）：

## 一、行业概况

### 1.1 行业定义与边界
- 行业定义：明确行业的核心定义和边界
- 产品类型：标品/非标品
- 季节特征：无明显季节性/有明显季节性（需说明）

### 1.2 市场规模与趋势
- 市场规模：给出具体数据（如：年销售额约XX亿元）
- 市场增速：年增速约XX%，保持XX增长
- 市场格局：高度集中/分散，前几大品牌占XX%份额
- 头部品牌：至少列出5个主要品牌
- 进入门槛：技术门槛、渠道门槛、品牌信任度等

### 1.3 竞争格局（红海分析）
- 主要竞争对手及市场份额
- 红海特征：价格战、利润微薄、假货频发等
- 竞争层级分析

## 二、核心问题挖掘（问题在先）

### 2.1 宝宝的问题（使用者痛点）
- 问题类型、具体表现、严重程度
- 至少列出3个核心痛点

### 2.2 宝爸宝妈的顾虑（付费者担忧）
- 顾虑类型、具体表现、焦虑程度
- 至少列出3个核心顾虑

### 2.3 用户决策链分析
- 付费者与使用者是否分离
- 决策流程分析

## 三、人群定位（人群在后）

### 3.1 核心目标人群（至少3个）
每个画像必须包含：
- 人群名称（如：新手爸妈、敏感宝宝家长等）
- 特征描述
- 核心需求
- 内容策略

### 3.2 人群需求层次
- 从底层到顶层的需求层次分析

## 四、行业生态分析

### 4.1 上游供应链
- 原料/供应环节
- 生产/服务环节
- 选题方向建议

### 4.2 下游配套服务
- 关联服务
- 关联需求

## 五、蓝海机会分析

### 5.1 红海 vs 蓝海策略对比

### 5.2 蓝海切入点（至少3个）
每个机会必须包含：
- name: 机会名称
- direction: 方向（用于卡片展示）
- why_blue_ocean: 为什么是蓝海
- potential: 市场潜力
- difficulty: 进入难度
- market_analysis: 市场分析详情
- content_angle: 内容切入角度

### 5.3 推荐方向
- 给出1-2个最推荐的蓝海方向

## 六、关键词库（必须≥100个）

### 6.1 公用关键词（至少40个）
格式：{{"keyword": "关键词", "type": "类型", "search_intent": "搜索意图"}}
类型包括：意愿/价格、渠道/真假、效果/安全、使用/保存、选择/对比

### 6.2 画像专属关键词
格式示例：persona_name: pain_points/scenarios/concerns数组

### 6.3 蓝海长尾词矩阵
- L1核心蓝海词（标题必现）
- L2长尾蓝海词（内容分布）
- L3地域蓝海词（精准覆盖）
- L4季节蓝海词（提前布局）

## 七、选题库（必须≥285个）

### 7.1 公用选题（至少45个）
格式：{{"topic": "选题内容", "type": "类型", "content_angle": "内容角度"}}
类型包括：顾虑消除、直接需求、技巧干货、问题解决、信任建立

### 7.2 画像专属选题（按类型分类，每个画像至少80个）
格式：persona_name对象包含以下数组字段：
#   "audience_lock": [...],      # 受众锁定
#   "pain_point_amplify": [...], # 痛点放大
#   "solution_compare": [...],    # 方案对比
#   "vision_canvas": [...],      # 愿景勾画
#   "concern_resolve": [...],    # 顾虑消除
#   "direct_demand": [...],      # 直接需求
#   "skill_tips": [...]          # 技巧干货

### 7.3 选题优先级排序
- 按热度/时效性排序

## 八、执行策略建议

### 8.1 内容矩阵
- 内容类型占比
- 各类型目的

### 8.2 账号定位建议
- 账号名称建议
- 账号定位
- 人设形象
- 内容风格
- 核心价值

【重要规则】：
1. 关键词库必须≥100个，首次生成必须达标
2. 选题库必须≥285个，首次生成必须达标
3. 每个蓝海机会必须包含：name, direction, why_blue_ocean, potential, difficulty
4. 画像数量至少3个，每个画像必须有详细的人群描述、核心需求、具体痛点
5. 输出格式必须是有效的JSON
6. 所有中文内容使用中文标点符号

请以JSON格式输出所有内容：
"""

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        try:
            # 尝试提取 JSON
            json_str = self._extract_json(response)
            if json_str:
                return json.loads(json_str)
            else:
                raise ValueError("无法从响应中提取JSON")
        except Exception as e:
            print(f"解析响应失败: {e}")
            # 返回空结构
            return self._get_empty_structure()

    def _extract_json(self, text: str) -> Optional[str]:
        """从文本中提取 JSON"""
        # 尝试多种方式提取 JSON
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',  # 代码块
            r'```\s*([\s\S]*?)\s*```',  # 代码块（无语言标识）
            r'(\{[\s\S]*\})',  # 大括号包裹
            r'(\[[\s\S]*\])',  # 大括号包裹
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return None

    def _get_empty_structure(self) -> Dict[str, Any]:
        """返回空结构"""
        return {
            "industry_report": {},
            "industry_overview": {},
            "target_personas": [],
            "industry_ecology": {},
            "blue_ocean_opportunities": [],
            "keyword_library": {
                "public_keywords": [],
                "persona_keywords": {},
                "blue_ocean_matrix": {},
                "total_count": 0
            },
            "topic_library": {
                "public_topics": [],
                "persona_topics": {},
                "total_count": 0
            },
            "execution_strategy": {},
            "time_insights": self._get_default_time_insights()
        }

    def _ensure_data_integrity(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """确保数据完整性"""
        # 标准化 industry_report 结构
        if "industry_report" not in result or not result["industry_report"]:
            result["industry_report"] = self._normalize_industry_report(result)

        # 确保蓝海机会列表格式统一
        opportunities = result.get("blue_ocean_opportunities", [])
        for i, opp in enumerate(opportunities):
            # 确保每个机会有 direction/name 用于卡片展示
            if "direction" not in opp and "name" in opp:
                opp["direction"] = opp["name"]
            if "name" not in opp and "direction" in opp:
                opp["name"] = opp["direction"]

            # 计算蓝海指数（基于 difficulty 和 potential）
            difficulty = opp.get("difficulty", "中")
            potential = opp.get("potential", "中")

            # 难度转换为竞争分数（低难度=高蓝海）
            if "高" in difficulty:
                comp_score = 0.8
                diff_score = 0.7
            elif "中" in difficulty:
                comp_score = 0.5
                diff_score = 0.5
            else:
                comp_score = 0.2
                diff_score = 0.3

            # 潜力转换为需求分数
            if "大" in potential:
                demand_score = 0.85
            elif "中" in potential:
                demand_score = 0.6
            else:
                demand_score = 0.4

            # 计算综合蓝海指数
            overall_score = (demand_score * 0.4 + (1 - comp_score) * 0.4 + diff_score * 0.2)

            # 确保 verification_data 存在（用于蓝海指数弹框）
            if "verification_data" not in opp:
                opp["verification_data"] = {}
            vData = opp["verification_data"]
            vData["overall_score"] = overall_score
            vData["demand_score"] = demand_score
            vData["competition_score"] = comp_score
            vData["scarcity_score"] = 0.7  # 内容稀缺度默认值
            vData["content_gap_score"] = 0.65  # 内容缺口默认值
            opp["logic_chain"] = f"需求{demand_score:.0%} × 竞争{1-comp_score:.0%} × 难度{diff_score:.0%}"
            opp["final_verdict"] = f"综合蓝海指数 {overall_score*100:.0f}分，{'蓝海机会明显' if overall_score >= 0.6 else '存在中等机会' if overall_score >= 0.4 else '红海竞争激烈'}"

            # 确保 decision_cost 存在（用于决策成本弹框）
            if "decision_cost" not in opp:
                opp["decision_cost"] = {}
            dcData = opp["decision_cost"]

            # 基于 difficulty 和 difficulty_desc 计算决策成本
            if "高" in difficulty:
                base_score = 8
                dcData["money_score"] = 8
                dcData["time_score"] = 7
                dcData["info_access_score"] = 7
                dcData["info_judge_score"] = 8
                dcData["trust_build_score"] = 9
                dcData["risk_score"] = 7
                dcData["mental_score"] = 8
                dcData["judgment"] = "高决策成本"
                dcData["analysis"] = {
                    "money": "进入门槛较高，需要较大的资金投入",
                    "time": "需要较长时间建立品牌认知和用户信任",
                    "info_access": "行业信息获取有一定门槛",
                    "info_judge": "用户对产品辨别能力较强，需要专业背书",
                    "trust_build": "品牌信任度是关键壁垒，新进入者难度大",
                    "risk": "存在一定的市场风险和政策风险",
                    "mental": "用户决策心理门槛较高，需要建立情感连接"
                }
                dcData["insight"] = f"建议内容方向：重点解决用户在【信任】【辨识】【心理】维度的顾虑，降低决策门槛。内容应强调品牌背书、专业认证、用户案例和售后保障。"
            elif "中" in difficulty:
                base_score = 6
                dcData["money_score"] = 6
                dcData["time_score"] = 5
                dcData["info_access_score"] = 6
                dcData["info_judge_score"] = 6
                dcData["trust_build_score"] = 7
                dcData["risk_score"] = 5
                dcData["mental_score"] = 6
                dcData["judgment"] = "中等决策成本"
                dcData["analysis"] = {
                    "money": "需要一定的资金投入，但规模要求适中",
                    "time": "需要一定时间建立市场认知",
                    "info_access": "行业信息基本可获取",
                    "info_judge": "用户有一定的产品辨别能力",
                    "trust_build": "需要建立一定的品牌信任",
                    "risk": "市场风险可控",
                    "mental": "用户决策心理门槛中等"
                }
                dcData["insight"] = f"建议内容方向：重点解决用户在【信任】【金钱】维度的顾虑，降低决策门槛。内容应强调性价比、售后服务保障和真实用户反馈。"
            else:
                base_score = 4
                dcData["money_score"] = 4
                dcData["time_score"] = 4
                dcData["info_access_score"] = 5
                dcData["info_judge_score"] = 5
                dcData["trust_build_score"] = 5
                dcData["risk_score"] = 4
                dcData["mental_score"] = 4
                dcData["judgment"] = "低决策成本"
                dcData["analysis"] = {
                    "money": "资金门槛较低，适合小成本创业",
                    "time": "市场启动较快",
                    "info_access": "行业信息容易获取",
                    "info_judge": "用户产品辨别能力一般",
                    "trust_build": "信任建立相对容易",
                    "risk": "市场风险较低",
                    "mental": "用户决策心理门槛较低"
                }
                dcData["insight"] = f"建议内容方向：快速建立差异化优势，强调产品特点和便捷服务。内容应突出使用效果、方便性和用户好评。"

            # 计算总评分
            scores = [dcData.get(f"{dim}_score", 5) for dim in ["money", "time", "info_access", "info_judge", "trust_build", "risk", "mental"]]
            dcData["total_score"] = sum(scores) / len(scores) if scores else 5

            # 确保 supply_gap 存在（用于供需分析弹框）
            if "supply_gap" not in opp:
                opp["supply_gap"] = {}
            opp["supply_gap"]["supply_quality_issue"] = "市场现有产品质量参差不齐"
            opp["supply_gap"]["supply_form_issue"] = "现有解决方案未能很好满足细分需求"

            # 确保 unmet_problem, severity_consequence, urgency_trigger 存在
            opp["unmet_problem"] = opp.get("why_blue_ocean", "存在未被充分满足的用户需求")
            opp["severity_consequence"] = opp.get("potential", "用户可能选择不购买或选择劣质产品")
            opp["urgency_trigger"] = f"当{opp.get('direction', '该领域')}需求出现时，用户会主动搜索解决方案"

            # 确保 why_unsolved 存在
            if "why_unsolved" not in opp:
                opp["why_unsolved"] = {}
            opp["why_unsolved"]["reasons"] = ["大品牌垄断流量", "内容同质化严重", "缺乏差异化定位"]
            opp["why_unsolved"]["business_type"] = "小商家"
            opp["why_unsolved"]["decision_cost"] = dcData.get("judgment", "中等")

        # 确保关键词库结构
        kw_lib = result.get("keyword_library", {})
        if not kw_lib:
            kw_lib = {"public_keywords": [], "persona_keywords": {}, "blue_ocean_matrix": {}, "total_count": 0}
            result["keyword_library"] = kw_lib

        # 确保选题库结构
        tp_lib = result.get("topic_library", {})
        if not tp_lib:
            tp_lib = {"public_topics": [], "persona_topics": {}, "total_count": 0}
            result["topic_library"] = tp_lib

        # 统计关键词和选题数量
        kw_count = self._count_keywords(kw_lib)
        tp_count = self._count_topics(tp_lib)

        # ⚠️ 强制要求关键词≥100个，如果不够则标记警告
        if kw_count < 100:
            print(f"⚠️ 警告：关键词库数量不足 ({kw_count} < 100)，请检查LLM输出")

        # ⚠️ 强制要求选题≥285个，如果不够则标记警告
        if tp_count < 285:
            print(f"⚠️ 警告：选题库数量不足 ({tp_count} < 285)，请检查LLM输出")

        kw_lib["total_count"] = kw_count
        tp_lib["total_count"] = tp_count

        # 确保时间洞察
        if not result.get("time_insights"):
            result["time_insights"] = self._get_default_time_insights()

        return result

    def _normalize_industry_report(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """标准化行业报告结构"""
        report = {}

        # 从各个可能的字段提取行业概况
        if "industry_overview" in result:
            report["industry_overview"] = result["industry_overview"]

        # 从蓝海机会中提取关键词统计
        opportunities = result.get("blue_ocean_opportunities", [])
        blue_ocean_kws = []
        for opp in opportunities:
            if "blue_ocean_keywords" in opp:
                blue_ocean_kws.extend(opp.get("blue_ocean_keywords", []))
            if "keywords" in opp:
                if isinstance(opp["keywords"], list):
                    blue_ocean_kws.extend(opp["keywords"])

        if blue_ocean_kws:
            report["blue_ocean_keywords"] = blue_ocean_kws

        return report

    def _count_keywords(self, keyword_library: Dict) -> int:
        """统计关键词数量"""
        count = 0
        # 公用关键词
        public = keyword_library.get("public_keywords", [])
        if isinstance(public, list):
            count += len(public)

        # 画像专属关键词
        persona = keyword_library.get("persona_keywords", {})
        if isinstance(persona, dict):
            for p_keywords in persona.values():
                if isinstance(p_keywords, dict):
                    for key in ["pain_points", "scenarios", "concerns"]:
                        if key in p_keywords and isinstance(p_keywords[key], list):
                            count += len(p_keywords[key])
                elif isinstance(p_keywords, list):
                    count += len(p_keywords)

        # 蓝海词矩阵
        matrix = keyword_library.get("blue_ocean_matrix", {})
        if isinstance(matrix, dict):
            for key in ["L1_core", "L2_long_tail", "L3_regional", "L4_seasonal"]:
                if key in matrix and isinstance(matrix[key], list):
                    count += len(matrix[key])

        return count

    def _count_topics(self, topic_library: Dict) -> int:
        """统计选题数量"""
        count = 0
        # 公用选题
        public = topic_library.get("public_topics", [])
        if isinstance(public, list):
            count += len(public)
        # 画像专属选题
        persona = topic_library.get("persona_topics", {})
        if isinstance(persona, dict):
            for p_topics in persona.values():
                if isinstance(p_topics, dict):
                    for key in ["audience_lock", "pain_point_amplify", "solution_compare",
                                "vision_canvas", "concern_resolve", "direct_demand", "skill_tips"]:
                        if key in p_topics and isinstance(p_topics[key], list):
                            count += len(p_topics[key])
        return count

    def _get_default_time_insights(self) -> Dict[str, Any]:
        """获取默认时间洞察"""
        from datetime import datetime
        now = datetime.now()
        month = now.month

        # 判断季节
        if month in [1, 2]:
            season = "年后淡季"
            content_dir = "知识干货为主、促销为辅"
        elif month in [3, 4]:
            season = "回暖期"
            content_dir = "预热引流、春季上新"
        elif month in [5, 6]:
            season = "常规期+618预热"
            content_dir = "常规运营、大促攻略"
        elif month in [7, 8]:
            season = "暑期"
            content_dir = "夏季场景、亲子出行"
        elif month == 9:
            season = "回暖期+双11预热"
            content_dir = "秋季上新、大促准备"
        elif month in [10, 11]:
            season = "旺季+双11"
            content_dir = "大促冲量、年终采购"
        else:
            season = "旺季尾巴"
            content_dir = "年末清仓、跨年策划"

        return {
            "current_date": self.current_date,
            "season": season,
            "season_features": f"{month}月特征",
            "content_direction": content_dir,
            "topic_priority": {}
        }
