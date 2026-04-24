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
    confidence: float = 0.8        # 置信度
    differentiation: str = ""       # 差异化说明（告诉客户机会在哪）
    logic_chain: str = ""           # 逻辑链自证
    problem_types: List[ProblemType] = field(default_factory=list)  # 问题类型列表


@dataclass
class ProblemType:
    """问题类型（用户遇到的问题大类，如"肠道问题"）"""
    name: str                    # 问题类型名称，如"肠道问题"、"过敏问题"
    description: str             # 问题类型描述
    keywords: List[str]          # 问题类型关键词
    scenes: List[Dict] = field(default_factory=list)  # 问题场景列表（每个场景生成一个画像），格式：[{name, description}]


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
                    'problem_types': opp.get('problem_types', []),  # 修复：漏掉了问题类型
                }

                # 如果有搜索验证数据，合并进去
                if search_verification and i < len(search_verification):
                    sv = search_verification[i]
                    opp_data['confidence'] = sv.get('final_confidence', opp.get('confidence', 0.8))
                    opp_data['final_verdict'] = sv.get('final_verdict', '')
                    opp_data['search_evidence'] = sv.get('search_evidence', [])
                    opp_data['verification_data'] = sv.get('verification_data', {})
                else:
                    opp_data['confidence'] = opp.get('confidence', 0.8)

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
            logger.error("[MarketAnalyzer] Step 1 异常: %s", str(e))
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
                    confidence=opp.get('confidence', 0.8),
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
                    if i < len(search_candidates):
                        sv = search_candidates[i]
                        opp['confidence'] = sv.get('final_confidence', opp.get('confidence', 0.8))
                        opp['final_verdict'] = sv.get('final_verdict', '')
                        opp['search_evidence'] = sv.get('search_evidence', [])
                        opp['verification_data'] = sv.get('verification_data', {})

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
                    confidence=opp_data.get('confidence', 0.5),
                )
                # 解析问题类型
                for pt_data in opp_data.get('problem_types', []):
                    if isinstance(pt_data, dict):
                        opp.problem_types.append(ProblemType(
                            type_name=pt_data.get('type_name', ''),
                            description=pt_data.get('description', ''),
                            target_audience=pt_data.get('target_audience', ''),
                            keywords=pt_data.get('keywords', []),
                            scene_keywords=pt_data.get('scene_keywords', []),
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
        """构建蓝海机会挖掘Prompt（精简版）"""

        # ── 业务类型适配 ──
        business_type_map = {
            'product': '消费品：重点关注使用者症状、购买者顾虑、选择对比',
            'local_service': '本地服务：重点关注服务场景、时效顾虑、信任问题',
            'enterprise': '企业服务：重点关注决策流程、ROI顾虑、供应商选择',
        }
        business_type_hint = business_type_map.get(business_type, f'业务类型：{business_type}')

        # ── 经营范围适配 ──
        if business_range == 'local':
            range_hint = f'本地服务（{local_city or "未指定城市"}），聚焦同城差异化'
        elif business_range == 'cross_region':
            range_hint = '全国/跨区域，可聚焦全国性需求'
        else:
            range_hint = ''

        # ── 服务场景 ──
        scenario_hint = f'服务场景：{service_scenario}' if service_scenario else ''

        # ── 通用红线约束（提炼到prompt顶部，避免LLM套模板） ──
        redlines = f"""
**红线（违反则输出作废）**
1. 细分方向必须与「{business_desc}」有直接逻辑关联，禁止凭空创造无关产品/服务
2. 目标人群禁止虚构，必须基于业务自然延伸（如买主→使用者、用户→决策者）
3. 问题类型必须是真实痛点，禁止填业务流程步骤（如"付款方式"、"取车手续"）
4. 输出内容必须基于输入业务，禁止复制示例格式套用"""

        return f"""你是蓝海市场分析专家。请为以下业务识别 {max_opportunities} 个蓝海机会。

=== 业务信息 ===
{business_desc}
行业：{industry or '从业务描述推断'}
类型：{business_type_hint}
{range_hint}
{scenario_hint}
{redlines}

=== 任务 ===
识别 {max_opportunities} 个蓝海市场机会，每个机会输出：

1. **opportunity_name**：机会名称，直接命中细分人群/需求
2. **business_direction**：细分方向，直接填入"核心业务"输入框
   - 格式：「{business_desc} + 服务形式」或「{business_desc} + 人群细分」
   - 不得替换核心关键词
3. **logic_chain**：逻辑链自证，格式：输入业务是X，目标人群是Y，因为Z（真实原因），所以提供W
4. **differentiation**：一句话差异化说明
5. **target_audience**：细分人群描述（如"XX情况但不知怎么选的30-40岁XX"）
6. **pain_points**：该人群的2-4个真实痛点
7. **problem_types**：问题类型+场景，每个机会1-3个问题类型
   - 问题类型：该人群遇到的具体问题大类（如"担心XX"、"不知道怎么选XX"）
   - 场景：该问题下的具体症状/情境（如"XX情况但不知道怎么解决"）

=== 输出格式 ===
```json
{{
    "market_opportunities": [
        {{
            "opportunity_name": "具体人群+具体需求的市场",
            "business_direction": "{business_desc}+细分形式",
            "logic_chain": "输入业务是X，目标人群是Y，因为Z，所以提供W",
            "differentiation": "一句话说明好在哪",
            "target_audience": "细分人群描述",
            "pain_points": ["痛点1", "痛点2"],
            "problem_types": [
                {{
                    "name": "担心/不知/不会+具体问题",
                    "scenes": [
                        {{"name": "具体症状情境"}},
                        {{"name": "第二个具体症状"}}
                    ]
                }}
            ]
        }}
    ]
}}
```
**禁止复制上述示例格式**，必须基于输入业务「{business_desc}」真实生成。

请开始分析："""

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
                    ))

            result.market_opportunities.append(MarketOpportunity(
                opportunity_name=opp.get('opportunity_name', ''),
                business_direction=opp.get('business_direction', ''),
                target_audience=opp.get('target_audience', ''),
                pain_points=opp.get('pain_points', []),
                keywords=opp.get('keywords', []),
                content_direction=opp.get('content_direction', ''),
                market_type=opp.get('market_type', 'blue_ocean'),
                confidence=opp.get('confidence', 0.8),
                differentiation=opp.get('differentiation', ''),
                logic_chain=opp.get('logic_chain', ''),
                problem_types=problem_types,
            ))

        # 解析关键词库
        result.keyword_library = data.get('keyword_library', {})

        # 解析细分洞察
        result.subdivision_insights = data.get('subdivision_insights', {})

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
