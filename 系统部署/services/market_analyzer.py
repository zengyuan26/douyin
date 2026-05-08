"""
市场蓝海分析服务

功能：
1. 基于业务描述分析市场机会
2. 识别细分人群和长尾市场
3. 挖掘蓝海关键词和差异化方向
4. 生成问题类型标签（用于画像分类）
5. 整合关键词库生成（蓝海/红海区分）

使用方式：
from services.market_analyzer import MarketAnalyzer, MarketAnalysisResult

analyzer = MarketAnalyzer()
result = analyzer.analyze({
    'business_description': '卖奶粉',
    'industry': '奶粉',
    'business_type': 'product'
})

# 获取分析结果
result.market_opportunities  # 蓝海市场机会
result.keyword_library       # 关键词库（区分蓝海/红海）
result.problem_types         # 问题类型标签
result.subdivision_insights  # 细分赛道洞察
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from services.llm import get_llm_service

logger = logging.getLogger(__name__)


# =============================================================================
# 延迟导入（避免循环依赖）
# =============================================================================

def _get_search_verifier():
    """延迟获取搜索验证器"""
    try:
        from services.blue_ocean_search_verifier import BlueOceanSearchVerifier, CandidateDirection
        return BlueOceanSearchVerifier, CandidateDirection
    except ImportError:
        return None, None


def _get_keyword_generator():
    """延迟获取关键词库生成器"""
    try:
        from services.keyword_library_generator import KeywordLibraryGenerator
        return KeywordLibraryGenerator
    except ImportError:
        return None


class MarketType(Enum):
    """市场类型枚举"""
    BLUE_OCEAN = "blue_ocean"  # 蓝海：细分人群/长尾需求
    RED_OCEAN = "red_ocean"    # 红海：大众竞争市场


@dataclass
class MarketOpportunity:
    """市场机会"""
    opportunity_name: str           # 机会名称（业务细分方向，如"进口有机羊奶粉"）
    business_direction: str         # 核心业务方向（用于填入"核心业务"输入框）
    target_audience: str            # 目标人群描述
    pain_points: List[str]         # 痛点列表
    keywords: List[str]             # 关键词
    content_direction: str          # 内容方向
    market_type: str                # blue_ocean / red_ocean
    differentiation: str = ""       # 差异化说明（告诉客户机会在哪）
    logic_chain: str = ""          # 逻辑链自证

    # ============================================================
    # 问题导向分析（Skill 框架核心：问题在先，人群在后）
    # ============================================================
    unmet_problem: str = ""         # 未满足的问题是什么（核心问题）
    severity: int = 0               # 严重程度 (1-10)
    urgency: int = 0               # 紧急程度 (1-10)
    why_unsolved: str = ""         # 为什么没人解决（认知缺失/技能缺失/信任缺失/资源缺失）
    supply_gap: str = ""            # 供给缺口：当前市场供给和用户需求的差距
    entry_angle: str = ""           # 切入角度：从哪个细分点切入最容易突破

    # ============================================================
    # 用户失败经历分析（爆款选题来源）
    # ============================================================
    failure_experiences: List[Dict] = field(default_factory=list)  # 用户失败经历列表
    """
    格式：
    {
        "type": "制作失败类|使用失败类|选择失败类|储存失败类",
        "description": "失败场景描述",
        "keywords": ["用户搜索关键词"],
        "topic_formula": "失败→选题模板"
    }
    """

    # ============================================================
    # 问题类型标签
    # ============================================================
    problem_types: List[ProblemType] = field(default_factory=list)  # 问题类型列表

    # ============================================================
    # 决策成本分析
    # ============================================================
    decision_cost: Dict = field(default_factory=dict)  # 决策成本分析


@dataclass
class ProblemType:
    """问题类型（用户遇到的问题大类，如"肠道问题"）"""
    name: str                    # 问题类型名称，如"肠道问题"、"过敏问题"
    description: str             # 问题类型描述
    keywords: List[str]          # 问题类型关键词
    scenes: List[Dict] = field(default_factory=list)  # 问题场景列表（每个场景生成一个画像），格式：[{name, description}]
    target_audience: str = ""   # 该问题类型对应的细分人群（用于画像生成，粒度比 opportunity.target_audience 更细）
    category: str = ""           # 问题大类：付费者问题（宝爸宝妈顾虑）/ 使用者问题（宝宝症状）


@dataclass
class KeywordCategory:
    """关键词分类"""
    category_name: str              # 分类名称
    keywords: List[str]             # 关键词列表
    market_type: str                # blue_ocean / red_ocean
    proportion: float = 0.0         # 占比


@dataclass
class MarketAnalysisResult:
    """市场分析结果"""
    success: bool = False
    error_message: str = ""

    # 核心产出
    market_opportunities: List[MarketOpportunity] = field(default_factory=list)
    problem_types: List[ProblemType] = field(default_factory=list)
    keyword_library: Dict[str, Any] = field(default_factory=dict)

    # 细分洞察
    subdivision_insights: Dict[str, Any] = field(default_factory=dict)

    # 原始LLM输出（用于调试）
    raw_output: Dict[str, Any] = field(default_factory=dict)

    # 统计信息
    total_keywords: int = 0
    blue_ocean_keywords: int = 0
    red_ocean_keywords: int = 0


class MarketAnalyzer:
    """
    市场蓝海分析器

    核心能力：
    1. 挖掘细分人群和长尾市场（analyze_opportunities）
    2. 生成问题类型标签
    3. 关键词库/选题库改由 keyword_topic_generator.py 在画像保存后独立生成
    """

    def __init__(self):
        self.llm = get_llm_service()

    def analyze_opportunities(
        self,
        business_info: Dict[str, Any],
        max_opportunities: int = 5,
        use_search_verification: bool = True,  # 默认开启，由 API 层根据请求参数决定
    ) -> Dict[str, Any]:
        """
        仅挖掘蓝海市场机会（第一阶段）

        Args:
            business_info: 业务信息
            max_opportunities: 最大市场机会数量
            use_search_verification: 是否启用搜索增强验证（默认开启）

        Returns:
            Dict: 包含 market_opportunities 和 subdivision_insights
        """
        result = {
            'success': False,
            'error_message': '',
            'market_opportunities': [],
            'subdivision_insights': {},
            'search_verification': None,  # 搜索验证数据
        }

        try:
            business_desc = business_info.get('business_description', '')
            industry = business_info.get('industry', '')
            business_type = business_info.get('business_type', 'product')
            business_range = business_info.get('business_range', '')
            local_city = business_info.get('local_city', '')
            service_scenario = business_info.get('service_scenario', '')

            if not business_desc:
                result['error_message'] = "业务描述不能为空"
                return result

            # Phase 1: LLM 提出候选方向（含搜索假设）
            prompt = self._build_opportunity_prompt(
                business_desc=business_desc,
                industry=industry,
                business_type=business_type,
                business_range=business_range,
                local_city=local_city,
                service_scenario=service_scenario,
                max_opportunities=max_opportunities,
            )

            logger.info(f"[MarketAnalyzer] Step 1: 挖掘蓝海机会（搜索增强={use_search_verification}）...")

            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages, temperature=0.7, max_tokens=4000)

            if not response or not response.strip():
                result['error_message'] = "LLM调用返回为空"
                return result

            # 解析结果
            data = self._try_fix_json(response)
            if not data:
                result['error_message'] = "JSON解析失败"
                return result

            # 解析市场机会
            raw_opportunities = data.get('market_opportunities', [])

            # 调试日志：打印每个机会的 problem_types 数量和 category 分布
            for i, opp in enumerate(raw_opportunities):
                pts = opp.get('problem_types') or []
                cats = {}
                for pt in pts:
                    c = pt.get('category', '') or '(空)'
                    cats[c] = cats.get(c, 0) + 1
                logger.info(
                    f"[MarketAnalyzer] 机会{i+1}「{opp.get('opportunity_name','')}」"
                    f"problem_types={len(pts)}个 | category分布: {cats} | "
                    f"names: {[pt.get('name','') for pt in pts]}"
                )

            # Phase 2: 搜索增强验证（如果启用）
            search_verification = None
            if use_search_verification and raw_opportunities:
                search_verification = self._verify_with_search(raw_opportunities, business_info)

            # 合并结果
            for i, opp in enumerate(raw_opportunities):
                opp_data = {
                    'opportunity_name': opp.get('opportunity_name', ''),
                    'business_direction': opp.get('business_direction', ''),
                    'target_audience': opp.get('target_audience', ''),
                    'pain_points': opp.get('pain_points', []),
                    'keywords': opp.get('keywords', []),
                    'content_direction': opp.get('content_direction', ''),
                    'market_type': opp.get('market_type', 'blue_ocean'),
                    'differentiation': opp.get('differentiation', ''),
                    'logic_chain': opp.get('logic_chain', ''),
                    'problem_types': opp.get('problem_types', []),
                    'decision_cost': opp.get('decision_cost', {}),

                    # ── 问题导向分析（Skill 框架核心） ──
                    'unmet_problem': opp.get('unmet_problem', ''),
                    'severity': opp.get('severity', 0),
                    'urgency': opp.get('urgency', 0),
                    'why_unsolved': opp.get('why_unsolved', ''),
                    'supply_gap': opp.get('supply_gap', ''),
                    'entry_angle': opp.get('entry_angle', ''),

                    # ── 用户失败经历分析（爆款选题来源） ──
                    'failure_experiences': opp.get('failure_experiences', []),
                }

                # 如果有搜索验证数据，合并进去
                if search_verification and i < len(search_verification):
                    sv = search_verification[i]
                    opp_data['final_verdict'] = sv.get('final_verdict', '')
                    opp_data['search_evidence'] = sv.get('search_evidence', [])
                    opp_data['verification_data'] = sv.get('verification_data', {})

                result['market_opportunities'].append(opp_data)

            # 解析细分洞察
            result['subdivision_insights'] = data.get('subdivision_insights', {})
            result['search_verification'] = search_verification

            # 关键词库改由画像保存后独立生成（KeywordLibraryGenerator），此处不再生成
            result['keyword_library'] = {}
            result['keyword_stats'] = {'total': 0, 'blue_ocean': 0, 'red_ocean': 0}

            result['success'] = True

            logger.info(f"[MarketAnalyzer] Step 1 完成: 发现 {len(result['market_opportunities'])} 个蓝海机会")

        except Exception as e:
            import traceback
            logger.error(f"[MarketAnalyzer] Step 1 异常: type={type(e).__name__}, msg={str(e)}, tb={traceback.format_exc()}")
            result['error_message'] = f"异常: {str(e)}"

        return result

    def _generate_keyword_library(
        self,
        business_info: Dict[str, Any],
        opportunities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """生成关键词库"""
        KeywordLibraryGenerator = _get_keyword_generator()
        if not KeywordLibraryGenerator:
            logger.warning("[MarketAnalyzer] 关键词库生成器不可用，跳过")
            return {}

        try:
            business_desc = business_info.get('business_description', '')
            industry = business_info.get('industry', '')
            business_type = business_info.get('business_type', 'product')

            # 从机会中提取第一个（最优先）的蓝海机会作为关键词生成方向
            blue_opp = None
            for opp in opportunities:
                if opp.get('market_type') == 'blue_ocean' and opp.get('business_direction'):
                    blue_opp = opp
                    break
            if not blue_opp and opportunities:
                blue_opp = opportunities[0]

            blue_ocean_desc = blue_opp.get('opportunity_name', '') if blue_opp else ''
            core_business = blue_opp.get('business_direction', '') if blue_opp else ''

            logger.info(f"[MarketAnalyzer] 生成关键词库: 蓝海机会={blue_ocean_desc}, 核心业务={core_business}")

            generator = KeywordLibraryGenerator()
            kw_result = generator.generate(
                business_info={
                    'business_description': business_desc,
                    'industry': industry,
                    'business_type': business_type,
                },
                core_business=core_business or None,
                max_keywords=200,
                blue_ocean_opportunity=blue_ocean_desc or None,
                portraits=None,
            )

            if kw_result.success:
                logger.info(f"[MarketAnalyzer] 关键词库生成完成: {kw_result.total_keywords} 个")
                return kw_result.keyword_library or {}
            else:
                logger.warning(f"[MarketAnalyzer] 关键词库生成失败: {kw_result.error_message}")
                return {}

        except Exception as e:
            logger.error(f"[MarketAnalyzer] 关键词库生成异常: {e}")
            return {}

    def _verify_with_search(
        self,
        opportunities: List[Dict],
        business_info: Dict[str, Any],
    ) -> Optional[List[Dict]]:
        """
        使用搜索增强验证机会

        Returns:
            List[Dict]: 每个机会的验证数据
        """
        BlueOceanSearchVerifier, CandidateDirection = _get_search_verifier()

        if not BlueOceanSearchVerifier:
            logger.warning("[MarketAnalyzer] 搜索验证器不可用，跳过搜索增强")
            return None

        try:
            verifier = BlueOceanSearchVerifier(max_workers=8, timeout=8)

            # 转换为 CandidateDirection 对象
            candidates = []
            for opp in opportunities:
                candidate = CandidateDirection(
                    opportunity_name=opp.get('opportunity_name', ''),
                    business_direction=opp.get('business_direction', ''),
                    target_audience=opp.get('target_audience', ''),
                    pain_points=opp.get('pain_points', []),
                    keywords=opp.get('keywords', []),
                    content_direction=opp.get('content_direction', ''),
                )

                # 从 opportunity 提取搜索假设（如果有）
                search_hypotheses = opp.get('search_hypotheses', {})
                if search_hypotheses:
                    candidate.search_hypotheses = search_hypotheses

                candidates.append(candidate)

            # 执行验证
            verification_result = verifier.verify_candidates(candidates, business_info)

            if verification_result.success:
                result_dict = verifier.to_dict(verification_result)
                search_candidates = result_dict.get('candidates', [])

                # 将搜索验证数据合并回原始 opportunities（避免 to_dict 覆盖原始字段如 logic_chain）
                for i, opp in enumerate(opportunities):
                    orig_pt = opp.get('problem_types', [])  # 保留原始问题类型
                    if i < len(search_candidates):
                        sv = search_candidates[i]
                        opp['final_verdict'] = sv.get('final_verdict', '')
                        opp['search_evidence'] = sv.get('search_evidence', [])
                        opp['verification_data'] = sv.get('verification_data', {})
                        if orig_pt:
                            opp['problem_types'] = orig_pt  # 恢复原始 problem_types（to_dict 可能会丢失 category）

                return opportunities

            logger.warning(f"[MarketAnalyzer] 搜索验证失败: {verification_result.error_message}")
            return None

        except Exception as e:
            logger.warning(f"[MarketAnalyzer] 搜索验证异常: {e}")
            return None

    def analyze(
        self,
        business_info: Dict[str, Any],
        max_opportunities: int = 5,
        max_keywords: int = 200,
    ) -> MarketAnalysisResult:
        """
        【已重构】执行市场分析

        该方法现在委托给 analyze_opportunities()，不再生成关键词库。
        关键词库/选题库改由 keyword_topic_generator.py 在画像保存后独立生成。

        Args:
            business_info: 业务信息
                - business_description: 业务描述
                - industry: 行业
                - business_type: 业务类型 (product/service)
            max_opportunities: 最大市场机会数量
            max_keywords: 已废弃（保留参数兼容）

        Returns:
            MarketAnalysisResult: 分析结果
        """
        result = MarketAnalysisResult()

        try:
            # 委托给 analyze_opportunities（不再生成关键词库）
            raw_result = self.analyze_opportunities(
                business_info=business_info,
                max_opportunities=max_opportunities,
                use_search_verification=True,  # 保留搜索增强
            )

            if not raw_result.get('success'):
                result.error_message = raw_result.get('error_message', '分析失败')
                return result

            # 转换结果格式
            for opp_data in raw_result.get('market_opportunities', []):
                opp = MarketOpportunity(
                    opportunity_name=opp_data.get('opportunity_name', ''),
                    target_audience=opp_data.get('target_audience', ''),
                    pain_points=opp_data.get('pain_points', []),
                    keywords=opp_data.get('keywords', []),
                    content_direction=opp_data.get('content_direction', ''),
                    market_type=opp_data.get('market_type', 'blue_ocean'),
                    decision_cost=opp_data.get('decision_cost', {}),

                    # ── 问题导向分析（Skill 框架核心） ──
                    unmet_problem=opp_data.get('unmet_problem', ''),
                    severity=opp_data.get('severity', 0),
                    urgency=opp_data.get('urgency', 0),
                    why_unsolved=opp_data.get('why_unsolved', ''),
                    supply_gap=opp_data.get('supply_gap', ''),
                    entry_angle=opp_data.get('entry_angle', ''),

                    # ── 用户失败经历分析 ──
                    failure_experiences=opp_data.get('failure_experiences', []),
                )
                # 解析问题类型
                for pt_data in opp_data.get('problem_types', []):
                    if isinstance(pt_data, dict):
                        opp.problem_types.append(ProblemType(
                            name=pt_data.get('type_name', '') or pt_data.get('name', ''),
                            description=pt_data.get('description', ''),
                            target_audience=pt_data.get('target_audience', ''),
                            keywords=pt_data.get('keywords', []),
                            category=pt_data.get('category', ''),
                        ))
                result.market_opportunities.append(opp)

            result.subdivision_insights = raw_result.get('subdivision_insights', {})
            result.keyword_library = raw_result.get('keyword_library', {})

            # 统计
            kw_stats = raw_result.get('keyword_stats') or {}
            result.total_keywords = kw_stats.get('total', 0)
            result.blue_ocean_keywords = kw_stats.get('blue_ocean', 0)
            result.red_ocean_keywords = kw_stats.get('red_ocean', 0)

            result.success = True
            logger.info(
                "[MarketAnalyzer.analyze] 分析完成: 机会=%d, 关键词=%d (蓝海=%d, 红海=%d)",
                len(result.market_opportunities),
                result.total_keywords,
                result.blue_ocean_keywords,
                result.red_ocean_keywords,
            )

        except Exception as e:
            logger.error("[MarketAnalyzer] 分析异常: %s", str(e))
            result.error_message = f"分析异常: {str(e)}"

        return result

    def _build_opportunity_prompt(
        self,
        business_desc: str,
        industry: str,
        business_type: str,
        business_range: str = '',
        local_city: str = '',
        service_scenario: str = '',
        max_opportunities: int = 5,
    ) -> str:
        """构建蓝海机会挖掘Prompt（整合 Skill 框架：问题在先，人群在后）

        Skill 框架核心维度：
        1. unmet_problem - 未满足的问题是什么
        2. severity × urgency - 严重程度 × 紧急程度
        3. why_unsolved - 为什么没人解决（认知缺失/技能缺失/信任缺失/资源缺失）
        4. supply_gap - 供给缺口
        5. entry_angle - 切入角度
        6. failure_experiences - 用户失败经历分析（爆款选题来源）
        """

        # ── 业务类型适配 ──
        business_type_map = {
            'product': '消费品：重点关注使用者症状、购买者顾虑、选择对比',
            'local_service': '本地服务：重点关注服务场景、时效顾虑、信任问题',
            'enterprise': '企业服务：重点关注决策流程、ROI顾虑、供应商选择',
        }
        business_type_hint = business_type_map.get(business_type, '业务类型：{}'.format(business_type))

        # ── 经营范围适配 ──
        if business_range == 'local':
            range_hint = '本地服务（{}），聚焦同城差异化'.format(local_city or '未指定城市')
        elif business_range == 'cross_region':
            range_hint = '全国/跨区域，可聚焦全国性需求'
        else:
            range_hint = ''

        # ── 服务场景（强制约束：谁是我的客户） ──
        scenario_hint = ''
        scenario_constraints = {
            'to_personal': '【强制】目标客户=个人/家庭消费者（如家长、个人、散户），禁止生成企业/机构客户',
            'to_business': '【强制】目标客户=企业/商家（如企业主、店主、加盟商），禁止生成个人/家庭消费者',
            'to_government': '【强制】目标客户=政府/机构（如学校、医院、政企单位），禁止生成个人/家庭消费者',
            'mixed': '目标客户=混合型，个人消费者和企业客户都可以，按业务自然延伸生成',
        }
        if service_scenario and service_scenario in scenario_constraints:
            scenario_hint = scenario_constraints[service_scenario]
        elif service_scenario:
            scenario_hint = f'【参考】服务场景={service_scenario}，按业务自然延伸生成人群'

        # ── 通用红线约束 ──
        redlines = """
**红线（违反则输出作废）**
1. 细分方向必须与「{business_desc}」有直接逻辑关联，禁止凭空创造无关产品/服务
2. 目标人群禁止虚构，必须基于业务自然延伸（如买主→使用者、用户→决策者）
3. 问题类型必须是真实痛点，禁止填业务流程步骤（如"付款方式"、"取车手续"）
4. 输出内容必须基于输入业务，禁止复制示例格式套用
{service_constraint}""".format(business_desc=business_desc, service_constraint=scenario_hint)

        # ── 占位符（用于 JSON 示例中的 business_desc） ──
        _BD_ = '__BUSINESS_DESC__'

        # ── 输出格式模板（使用 .format() 而非 f-string） ──
        output_format = """=== 输出格式 ===
```json
{{
    "market_opportunities": [
        {{
            "opportunity_name": "担心孩子喝奶出问题的焦虑宝妈",
            "business_direction": "{{{bd}}}+细分形式",
            "logic_chain": "输入业务是X，目标人群是Y，因为Z，所以提供W",

            // ── 问题导向分析（Skill 框架核心） ──
            "unmet_problem": "未满足的问题是什么（核心问题，1-2句话）",
            "severity": 8,  // 严重程度 1-10
            "urgency": 7,   // 紧急程度 1-10
            "why_unsolved": "为什么没人解决？认知缺失/技能缺失/信任缺失/资源缺失",
            "supply_gap": "当前市场供给和用户需求的差距是什么",
            "entry_angle": "从哪个细分点切入最容易突破",

            // ── 供需失衡分析（可视化） ──
            // 需求侧                    供给侧
            // 问题是什么？  ←── 严重程度/紧急程度 ──→  为什么没人做/做不好？
            // 需求有多强？  ←── 决策成本高      ──→  供给缺口在哪？

            // ── 用户失败经历分析（爆款选题来源）⭐ ──
            "failure_experiences": [
                {{
                    "type": "制作失败类",  // 制作失败类|使用失败类|选择失败类|储存失败类
                    "description": "用户制作/使用时容易犯什么错、最容易失败在哪一步",
                    "keywords": ["用户失败后会搜索的问题"],
                    "topic_formula": "为什么你[做成某事]总是[失败]，3招教你解决"
                }},
                {{
                    "type": "使用失败类",
                    "description": "用户使用产品时遇到的问题",
                    "keywords": ["香肠咬不动、太硬、发霉"],
                    "topic_formula": "为什么你[使用某产品]总是[失败表现]，原因找到了"
                }},
                {{
                    "type": "选择失败类",
                    "description": "用户选择时犯的错误",
                    "keywords": ["买错了品牌、买错了口味"],
                    "topic_formula": "90%的人都在[选择某产品]时犯这个错误"
                }},
                {{
                    "type": "储存失败类",
                    "description": "用户储存不当导致的问题",
                    "keywords": ["香肠变质、有异味"],
                    "topic_formula": "[产品]保存不当，后果很严重！[正确保存方法]"
                }}
            ],

            // ── 基础字段 ──
            "pain_points": ["痛点1", "痛点2"],
            "decision_cost": {{
                "money_score": 7,
                "time_score": 6,
                "info_access_score": 5,
                "info_judge_score": 8,
                "trust_build_score": 7,
                "risk_score": 7,
                "mental_score": 9,
                "total_score": 7.0,
                "judgment": "高价值",
                "analysis": {{
                    "money": "进口奶粉价格较高，一罐200-400元...",
                    "time": "用户需要投入大量时间研究...",
                    "info_access": "奶粉配方知识专业...",
                    "info_judge": "假货泛滥，套路深...",
                    "trust_build": "需要专业性/权威性...",
                    "risk": "奶粉质量直接影响宝宝健康...",
                    "mental": "妈妈们普遍焦虑..."
                }}
            }},
            "problem_types": [
                {{
                    "category": "使用者问题",
                    "name": "肠道不适-拉肚子",
                    "target_audience": "宝宝喝奶粉后出现肠道问题的家长",
                    "scenes": [
                        {{"name": "宝宝喝奶粉拉肚子怎么办"}},
                        {{"name": "换奶粉后拉肚子"}},
                        {{"name": "乳糖不耐受喝什么奶粉"}}
                    ]
                }}
            ]
        }}
    ]
}}
```
**禁止复制上述示例格式**，必须基于输入业务「{bd}」真实生成。""".format(bd=_BD_)

        # ── 组装最终 prompt（使用字符串拼接） ──
        lines = [
            "# 蓝海市场分析 - 问题在先，人群在后",
            "",
            "你是蓝海市场分析专家。请为以下业务识别 {} 个蓝海机会。".format(max_opportunities),
            "",
            "## 核心思维：问题在先，人群在后",
            "```",
            "❌ 错误思路（先有人，再找需求）：",
            "  先定义人群：新手妈妈、二胎妈妈",
            "  ↓ 找需求：担心假货、不会选",
            "  ↓ 卖产品：进口奶粉",
            "",
            "✅ 正确思路（先有问题，再有人群）：",
            "  先发现问题：孩子乳糖不耐受、便秘、过敏",
            "  ↓ 人群自动出现：有个这样的宝宝的妈妈",
            "  ↓ 提供解决方案：特殊奶粉 + 专业指导",
            "```",
            "",
            "=== 业务信息 ===",
            business_desc,
            "行业：{}".format(industry or '从业务描述推断'),
            "类型：{}".format(business_type_hint),
            range_hint,
            scenario_hint,
            redlines,
            "",
            "=== 分析任务 ===",
            "识别 {} 个蓝海市场机会，每个机会必须输出以下 6 大维度：".format(max_opportunities),
            "",
            "## 维度1：问题导向分析（核心）",
            "1. **unmet_problem**：未满足的问题是什么（1-2句话精准描述）",
            "   - 这是整个机会的起点，问题必须具体、可感知",
            "   - 示例：「宝宝喝普通奶粉后反复腹泻、哭闹不止」",
            "",
            "2. **severity × urgency**：严重程度 × 紧急程度",
            "   - severity：这个问题对用户影响有多大？(1-10)",
            "   - urgency：用户有多急着解决这个问题？(1-10)",
            "   - 示例：severity=9（影响生长发育）, urgency=8（急需解决）",
            "",
            "3. **why_unsolved**：为什么没人解决？",
            "   - 认知缺失：用户不知道有更好的解决方案",
            "   - 技能缺失：用户知道但不会做",
            "   - 信任缺失：用户不信任现有解决方案",
            "   - 资源缺失：用户知道但找不到合适的服务/产品",
            "   - 示例：「家长不知道特殊奶粉的存在，或者不知道如何选择」",
            "",
            "## 维度2：供需失衡分析",
            "```",
            "  需求侧                    供给侧",
            "  ─────────────────────────────────────────────",
            "  问题是什么？  ←── 严重程度/紧急程度 ──→  为什么没人做/做不好？",
            "  需求有多强？  ←── 决策成本高      ──→  供给缺口在哪？",
            "```",
            "4. **supply_gap**：供给缺口在哪里？",
            "   - 市场上有哪些供给？它们做得好不好？",
            "   - 用户的真实需求有没有被满足？差距在哪？",
            "   - 示例：「市场上有特殊奶粉，但家长不知道怎么选、没有专业指导」",
            "",
            "5. **entry_angle**：切入角度（最容易突破的点）",
            "   - 从哪个细分点切入，竞争最小、需求最强？",
            "   - 示例：「从'乳糖不耐受宝宝专属奶粉'这个细分切入，提供专业咨询」",
            "",
            "## 维度3：用户失败经历分析（爆款选题来源）⭐",
            "",
            "**核心洞察**：爆款内容往往来自用户真实的失败经历",
            "",
            "### 失败经历挖掘维度：",
            "| 维度 | 说明 | 示例 |",
            "|------|------|------|",
            "| **制作失败类** | 用户自己制作时遇到的问题 | 灌的香肠一切就散、一晒就酸 |",
            "| **使用失败类** | 用户使用产品时遇到的问题 | 香肠咬不动、太硬、发霉 |",
            "| **选择失败类** | 用户选择时犯的错误 | 买错了品牌、买错了口味 |",
            "| **储存失败类** | 用户储存不当导致的问题 | 香肠变质、有异味 |",
            "",
            "### 失败经历问题挖掘方法：",
            "```",
            'Step 1: 问自己「用户在做这件事时，容易犯什么错？」',
            'Step 2: 问自己「用户做成这件事，需要注意什么？」',
            'Step 3: 问自己「用户在这个过程中，最容易失败在哪一步？」',
            'Step 4: 问自己「用户失败后，会搜索什么问题？」',
            "```",
            "",
            "### 失败经历 → 选题转化公式：",
            "```",
            "用户失败经历 = 爆款选题",
            "",
            "公式：为什么你[做成某事]总是[失败]，3招教你解决",
            "",
            "应用案例：",
            "- 为什么你灌的香肠一切就散 → 制作失败",
            "- 为什么你腌的腊肉一炒就硬 → 制作失败",
            "- 为什么你选的奶粉宝宝拉肚子 → 选择失败",
            "- 为什么你买的家具没用多久就坏 → 使用失败",
            "```",
            "",
            "## 维度4：基础信息",
            "6. **opportunity_name**：机会名称，格式：「被XX问题困扰的XX人群」",
            "   - 必须包含问题词（如：担心、困扰、害怕、不懂、不会、纠结）",
            "   - 示例：「担心宝宝乳糖不耐受的焦虑宝妈」✓",
            "",
            "7. **business_direction**：细分方向，格式：「业务 + 服务形式」或「业务 + 人群细分」",
            "",
            "8. **logic_chain**：逻辑链自证，格式：输入业务是X，目标人群是Y，因为Z（真实原因），所以提供W",
            "",
            "9. **pain_points**：该人群的 2-4 个真实痛点",
            "",
            "10. **decision_cost**：决策成本分析（参考评分标准）",
            "    - mental_score：由以上五项综合导致，问题紧迫但暂时无法解决，用户陷入决策瘫痪",
            "",
            "11. **problem_types**：问题类型+场景（用于生成画像）",
            "    - 每个机会至少包含 3 个使用者问题 + 3 个付费者问题",
            "    - 每个问题类型下 2-4 个场景（用户真实搜索句）",
            "",
            output_format.replace(_BD_, business_desc),
            "",
            "请开始分析：",
        ]

        return "\n".join(lines)

    def _parse_analysis_result(
        self,
        response: str,
        result: MarketAnalysisResult
    ) -> MarketAnalysisResult:
        """解析LLM返回结果"""

        # 尝试JSON解析
        try:
            # 清理响应文本
            text = response.strip()
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)
            # json.loads('null') 会返回 Python None，需要兜底
            if data is None:
                logger.warning("[MarketAnalyzer] LLM返回了null JSON")
                result.error_message = "LLM返回了null JSON"
                return result
            result.raw_output = data

        except json.JSONDecodeError as e:
            logger.warning("[MarketAnalyzer] JSON解析失败，尝试修复: %s", e)
            # 尝试修复JSON
            data = self._try_fix_json(response)
            if not data or not isinstance(data, dict):
                result.error_message = "JSON解析失败"
                return result
            result.raw_output = data

        # 解析市场机会（包含问题类型和场景）
        opportunities = data.get('market_opportunities') or []
        for opp in (opportunities or []):
            # 解析问题类型和场景（每个场景生成一个画像）
            problem_types = []
            for pt_data in (opp.get('problem_types') or []):
                # 场景直接用简单字典格式：{name, description}
                scenes = []
                for scene_data in (pt_data.get('scenes') or []):
                    scene_name = scene_data.get('name', '')
                    if scene_name:  # 跳过空场景
                        scenes.append({
                            'name': scene_name,
                            'description': scene_data.get('description', ''),
                        })

                if scenes:  # 只保留有场景的问题类型
                    problem_types.append(ProblemType(
                        name=pt_data.get('name', ''),
                        description=pt_data.get('description', ''),
                        keywords=pt_data.get('keywords', []),
                        scenes=scenes,
                        target_audience=pt_data.get('target_audience', ''),
                        category=pt_data.get('category', ''),
                    ))

            result.market_opportunities.append(MarketOpportunity(
                opportunity_name=opp.get('opportunity_name', ''),
                business_direction=opp.get('business_direction', ''),
                target_audience=opp.get('target_audience', ''),
                pain_points=opp.get('pain_points', []),
                keywords=opp.get('keywords', []),
                content_direction=opp.get('content_direction', ''),
                market_type=opp.get('market_type', 'blue_ocean'),
                differentiation=opp.get('differentiation', ''),
                logic_chain=opp.get('logic_chain', ''),
                problem_types=problem_types,
                decision_cost=opp.get('decision_cost', {}),
            ))

        # 调试日志：打印每个机会的问题类型数量和 category 分布
        for i, o in enumerate(result.market_opportunities):
            cats = {}
            for pt in o.problem_types:
                c = pt.category or '(空)'
                cats[c] = cats.get(c, 0) + 1
            logger.info(
                f"[MarketAnalyzer] 机会{i+1}「{o.opportunity_name}」problem_types="
                f"{len(o.problem_types)}个 | category分布: {cats}"
            )

        # 解析关键词库
        result.keyword_library = data.get('keyword_library', {})

        # 解析细分洞察
        result.subdivision_insights = data.get('subdivision_insights', {})

        # 调试：确保 result 可以 JSON 序列化
        import json as _json_debug
        try:
            _test = {
                'success': result.get('success'),
                'market_opportunities': [
                    {
                        'opportunity_name': o.opportunity_name if hasattr(o, 'opportunity_name') else str(o),
                        'problem_types': [{'name': p.name} for p in (o.problem_types if hasattr(o, 'problem_types') else [])]
                    }
                    for o in result.market_opportunities
                ]
            }
            _json_debug.dumps(_test)
            logger.info("[MarketAnalyzer] 返回数据 JSON 序列化检查通过")
        except Exception as _e2:
            logger.error(f"[MarketAnalyzer] 返回数据序列化失败: {_e2}", exc_info=True)

        return result

    def _try_fix_json(self, text: str) -> Optional[Dict]:
        """尝试修复损坏的JSON"""

        # 策略1：提取JSON块
        import re

        # 尝试找到JSON开始和结束
        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx >= 0 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]

            # 尝试解析
            try:
                return json.loads(json_str)
            except:
                pass

            # 策略2：修复常见问题
            # 移除trailing comma
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)

            try:
                return json.loads(json_str)
            except:
                pass

        return None

    def get_problem_type_for_portrait(
        self,
        portrait_context: Dict[str, Any],
        problem_types: List[ProblemType]
    ) -> Optional[ProblemType]:
        """
        根据画像上下文匹配合适的问题类型

        Args:
            portrait_context: 画像上下文（痛点、场景等）
            problem_types: 可用的问题类型列表

        Returns:
            匹配的问题类型或None
        """
        if not problem_types:
            return None

        portrait_keywords = set()
        for v in portrait_context.values():
            if isinstance(v, str):
                portrait_keywords.update(v.split())

        # 简单匹配：找关键词重叠最多的
        best_match = None
        best_score = 0

        for pt in problem_types:
            pt_keywords = set(pt.keywords)
            overlap = len(portrait_keywords & pt_keywords)
            if overlap > best_score:
                best_score = overlap
                best_match = pt

        return best_match


# ============================================================
# 便捷函数
# ============================================================

def analyze_market(business_info: Dict[str, Any]) -> MarketAnalysisResult:
    """
    便捷函数：执行市场分析

    使用方式：
        from services.market_analyzer import analyze_market

        result = analyze_market({
            'business_description': '卖奶粉',
            'industry': '奶粉',
            'business_type': 'product'
        })

        if result.success:
            print(f"发现 {len(result.market_opportunities)} 个蓝海机会")
            print(f"关键词库: {result.keyword_library}")
    """
    analyzer = MarketAnalyzer()
    return analyzer.analyze(business_info)


def get_blue_ocean_keywords(keyword_library: Dict[str, Any]) -> List[str]:
    """
    从关键词库中提取蓝海关键词

    Args:
        keyword_library: 关键词库数据

    Returns:
        蓝海关键词列表
    """
    blue_ocean_kw = []

    # 旧结构：categories[].keywords
    for cat in keyword_library.get('categories', []):
        if cat.get('market_type') == 'blue_ocean':
            blue_ocean_kw.extend(cat.get('keywords', []))

    # 新结构：各字段中 competition_level == 'low' 的关键词
    all_kw_fields = [
        keyword_library.get('common_keywords', {}).values(),
        [p.get('pain_points', []) for p in keyword_library.get('personas', [])],
        [p.get('scene_keywords', []) for p in keyword_library.get('personas', [])],
        [p.get('concerns', []) for p in keyword_library.get('personas', [])],
        [keyword_library.get('upstream_keywords', [])],
        [keyword_library.get('downstream_keywords', [])],
        [keyword_library.get('supporting_tools_keywords', [])],
        [keyword_library.get('technique_keywords', [])],
    ]

    for field_group in all_kw_fields:
        for field in field_group:
            if isinstance(field, list):
                for kw in field:
                    if isinstance(kw, dict) and (kw.get('competition_level') or '').lower() == 'low':
                        kw_text = kw.get('keyword', '')
                        if kw_text and kw_text not in blue_ocean_kw:
                            blue_ocean_kw.append(kw_text)
                    elif isinstance(kw, str) and kw not in blue_ocean_kw:
                        blue_ocean_kw.append(kw)

    return blue_ocean_kw


def get_red_ocean_keywords(keyword_library: Dict[str, Any]) -> List[str]:
    """
    从关键词库中提取红海关键词

    Args:
        keyword_library: 关键词库数据

    Returns:
        红海关键词列表
    """
    red_ocean_kw = []

    # 旧结构
    for cat in keyword_library.get('categories', []):
        if cat.get('market_type') == 'red_ocean':
            red_ocean_kw.extend(cat.get('keywords', []))

    # 新结构
    all_kw_fields = [
        keyword_library.get('common_keywords', {}).values(),
        [p.get('pain_points', []) for p in keyword_library.get('personas', [])],
        [p.get('scene_keywords', []) for p in keyword_library.get('personas', [])],
        [p.get('concerns', []) for p in keyword_library.get('personas', [])],
        [keyword_library.get('upstream_keywords', [])],
        [keyword_library.get('downstream_keywords', [])],
        [keyword_library.get('supporting_tools_keywords', [])],
        [keyword_library.get('technique_keywords', [])],
    ]

    for field_group in all_kw_fields:
        for field in field_group:
            if isinstance(field, list):
                for kw in field:
                    if isinstance(kw, dict) and (kw.get('competition_level') or '').lower() == 'high':
                        kw_text = kw.get('keyword', '')
                        if kw_text and kw_text not in red_ocean_kw:
                            red_ocean_kw.append(kw_text)
                    elif isinstance(kw, str) and kw not in red_ocean_kw:
                        red_ocean_kw.append(kw)

    return red_ocean_kw
