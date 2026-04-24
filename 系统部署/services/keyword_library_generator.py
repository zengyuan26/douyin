"""
关键词库生成服务

功能：
基于业务描述，按照关键词库模板生成精准的关键词库（9大分类，100+个关键词）。

关键词库模板分类（9大类）：
1. 直接需求关键词（≥20个）：核心品类词 + 品质服务类
2. 痛点关键词（≥15个）：问题型 + 担心型 + 后果型
3. 搜索关键词（≥15个）：疑问型 + 方法型 + 对比型
4. 场景关键词（≥15个）：客户类型 + 具体场景
5. 地域关键词（≥10个）：本地 + 周边扩展
6. 季节/时间关键词（≥10个）：旺季 + 淡季
7. 技巧/干货关键词（≥10个）：干货型 + 数字型/承诺型
8. 认知颠覆/反向关键词（≥5个）：颠覆常识
9. 节日/节气关键词（≥15个）：传统节日 + 现代节日 + 节气

使用方式：
from services.keyword_library_generator import KeywordLibraryGenerator

generator = KeywordLibraryGenerator()
result = generator.generate_template(
    business_info={'business_description': '灌香肠加工服务'},
    core_business='灌香肠',
    region='南漳',
)

result.success
result.keyword_library  # 关键词库（9分类，100+个）
result.total_keywords   # 总关键词数
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from services.llm import get_llm_service

logger = logging.getLogger(__name__)


@dataclass
class ProblemType:
    """问题类型（画像分类标签）"""
    type_name: str                   # 类型名称，如"价格问题"
    description: str                 # 描述
    target_audience: str             # 目标人群
    keywords: List[str]               # 关联关键词
    scene_keywords: List[str] = field(default_factory=list)  # 场景关键词列表（用于选题扩展）


@dataclass
class QuestionSample:
    """问句示范（前置/后置）"""
    question: str           # 问句
    question_type: str      # pre（前置）/ post（后置）
    components: Dict[str, str] = field(default_factory=dict)  # 组成成分：{人群: "...", 场景: "...", 症状: "...", 解决方案: "..."}


@dataclass
class KeywordLibraryResult:
    """关键词库生成结果"""
    success: bool = False
    error_message: str = ""

    # 核心产出
    keyword_library: Dict[str, Any] = field(default_factory=dict)
    problem_types: List[ProblemType] = field(default_factory=list)
    question_samples: List[QuestionSample] = field(default_factory=list)  # 新增：问句示范
    portrait_keywords: List[Dict] = field(default_factory=list)  # 画像关键词

    # 原始LLM输出（用于调试）
    raw_output: Dict[str, Any] = field(default_factory=dict)

    # 统计信息
    total_keywords: int = 0
    blue_ocean_keywords: int = 0
    red_ocean_keywords: int = 0
    common_keywords_count: int = 0  # 公用关键词数量
    portrait_keywords_count: int = 0  # 个性化关键词数量

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'success': self.success,
            'error_message': self.error_message,
            'keyword_library': self.keyword_library or {},
            'problem_types': [
                {
                    'type_name': pt.type_name,
                    'description': pt.description,
                    'target_audience': pt.target_audience,
                    'keywords': pt.keywords,
                    'scene_keywords': pt.scene_keywords,
                }
                for pt in self.problem_types
            ],
            'question_samples': [
                {
                    'question': qs.question,
                    'question_type': qs.question_type,
                    'components': qs.components,
                }
                for qs in self.question_samples
            ],
            'total_keywords': self.total_keywords,
            'blue_ocean_keywords': self.blue_ocean_keywords,
            'red_ocean_keywords': self.red_ocean_keywords,
        }


class KeywordLibraryGenerator:
    """
    关键词库生成器

    核心能力：
    1. 基于选定的业务方向，生成精准的关键词库
    2. 生成问题类型标签
    3. 区分蓝海/红海关键词

    与 MarketAnalyzer 的区别：
    - MarketAnalyzer：一次性生成蓝海机会 + 关键词库（快速但不精准）
    - KeywordLibraryGenerator：基于已选定的业务方向，精准生成关键词库
    """

    def __init__(self):
        self.llm = get_llm_service()

    def generate(
        self,
        business_info: Dict[str, Any],
        core_business: str = None,
        max_keywords: int = 100,
        blue_ocean_opportunity: str = None,
        portraits: list = None,
        portrait_data: dict = None,
    ) -> KeywordLibraryResult:
        """
        生成关键词库

        Args:
            business_info: 业务信息
                - business_description: 原始业务描述
                - industry: 行业
                - business_type: 业务类型 (product/service)
            core_business: 核心业务词（可选，默认从业务描述提取）
            max_keywords: 最大关键词数量，默认100
            blue_ocean_opportunity: 蓝海机会描述（可选，用于指导关键词生成方向）
            portraits: 画像列表（可选，来自已保存的画像）
            portrait_data: 画像数据字典（可选，包含 pain_points、pain_scenarios、barriers）

        Returns:
            KeywordLibraryResult: 生成结果
        """
        result = KeywordLibraryResult()

        try:
            business_desc = business_info.get('business_description', '')
            industry = business_info.get('industry', '')
            business_type = business_info.get('business_type', 'product')

            if not business_desc:
                result.error_message = "业务描述不能为空"
                return result

            keyword_core = core_business
            if not keyword_core:
                keyword_core = self._extract_core_business(business_desc, industry)

            if not keyword_core:
                result.error_message = "核心业务不能为空"
                return result

            # 从 portrait_data 提取痛点信息（用于 prompt 中的画像专属关键词生成指引）
            pain_points = []
            pain_scenarios = []
            barriers = []
            if portrait_data:
                def _to_list(val):
                    if val is None:
                        return []
                    if isinstance(val, list):
                        return val
                    if isinstance(val, str):
                        return [val] if val.strip() else []
                    return []
                pain_points = _to_list(portrait_data.get('pain_points', []))
                pain_scenarios = _to_list(portrait_data.get('pain_scenarios', []))
                barriers = _to_list(portrait_data.get('barriers', []))
                if not pain_points:
                    pp = portrait_data.get('pain_point', '')
                    if isinstance(pp, str) and pp.strip():
                        pain_points = [pp.strip()]

            prompt = self._build_keyword_prompt(
                business_desc=business_desc,
                industry=industry,
                business_type=business_type,
                keyword_core=keyword_core,
                max_keywords=max_keywords,
                blue_ocean_opportunity=blue_ocean_opportunity,
                portraits=portraits,
                portrait_data=portrait_data,
            )

            logger.info("[KeywordLibraryGenerator] 开始调用LLM...")
            logger.info(f"[KeywordLibraryGenerator] 核心业务: {keyword_core}")
            if blue_ocean_opportunity:
                logger.info(f"[KeywordLibraryGenerator] 蓝海机会: {blue_ocean_opportunity}")

            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages, temperature=0.7, max_tokens=8000)

            if not response or not response.strip():
                result.error_message = "LLM调用返回为空"
                return result

            result = self._parse_result(response, result)

            if result.keyword_library:
                result.keyword_library = self._filter_keywords(result.keyword_library, keyword_core)

            if result.keyword_library:
                kw_lib = result.keyword_library or {}
                all_kw = []
                # 公用关键词（common_keywords）
                common = kw_lib.get('common_keywords') or {}
                for cat_kws in common.values():
                    if isinstance(cat_kws, list):
                        all_kw.extend(cat_kws)
                # 画像专属关键词（personas）
                for p in kw_lib.get('personas') or []:
                    if not isinstance(p, dict):
                        continue
                    all_kw.extend(p.get('pain_points') or [])
                    all_kw.extend(p.get('scene_keywords') or [])
                    all_kw.extend(p.get('concerns') or [])
                # 上下游关键词
                all_kw.extend(kw_lib.get('upstream_keywords') or [])
                all_kw.extend(kw_lib.get('downstream_keywords') or [])
                all_kw.extend(kw_lib.get('supporting_tools_keywords') or [])
                all_kw.extend(kw_lib.get('technique_keywords') or [])
                result.total_keywords = len(all_kw)
                # 蓝海/红海统计：关键词可能是字符串或 dict
                def get_level(kw):
                    if isinstance(kw, dict):
                        return (kw.get('competition_level') or '').lower()
                    return ''
                result.blue_ocean_keywords = sum(1 for kw in all_kw if get_level(kw) == 'low')
                result.red_ocean_keywords = sum(1 for kw in all_kw if get_level(kw) == 'high')

            result.success = True
            logger.info(
                "[KeywordLibraryGenerator] 生成完成: 问题类型=%d, 关键词=%d (蓝海=%d, 红海=%d), 问句=%d",
                len(result.problem_types),
                result.total_keywords,
                result.blue_ocean_keywords,
                result.red_ocean_keywords,
                len(result.question_samples),
            )

        except Exception as e:
            logger.error("[KeywordLibraryGenerator] 生成异常: %s", str(e))
            result.error_message = f"生成异常: {str(e)}"

        return result

    def generate_template(
        self,
        business_info: Dict[str, Any],
        core_business: str = None,
        region: str = None,
        portrait_data: Dict[str, Any] = None,
    ) -> KeywordLibraryResult:
        """
        按照关键词库模板（9大分类）生成100+个关键词。

        分类结构：
        1. 直接需求关键词（≥20个）：核心品类词 + 品质服务类
        2. 痛点关键词（≥15个）：问题型 + 担心型 + 后果型
        3. 搜索关键词（≥15个）：疑问型 + 方法型 + 对比型
        4. 场景关键词（≥15个）：客户类型 + 具体场景
        5. 地域关键词（≥10个）：本地 + 周边扩展
        6. 季节/时间关键词（≥10个）：旺季 + 淡季
        7. 技巧/干货关键词（≥10个）：干货型 + 数字型/承诺型
        8. 认知颠覆/反向关键词（≥5个）：颠覆常识
        9. 节日/节气关键词（≥15个）：传统节日 + 现代节日 + 节气

        Args:
            business_info: 业务信息（business_description, industry）
            core_business: 核心业务词（用于生成关键词前缀）
            region: 主要地域（如"南漳"）
            portrait_data: 画像数据（可选，包含 pain_points、pain_scenarios、barriers）

        Returns:
            KeywordLibraryResult: 生成结果
        """
        result = KeywordLibraryResult()

        try:
            business_desc = business_info.get('business_description', '') or ''
            industry = business_info.get('industry', '') or ''
            keyword_core = core_business or business_desc or ''

            if not keyword_core:
                result.error_message = "核心业务不能为空"
                return result

            # 提取画像信息
            pain_points = []
            pain_scenarios = []
            barriers = []
            if portrait_data:
                def _to_list(val):
                    if val is None:
                        return []
                    if isinstance(val, list):
                        return val
                    if isinstance(val, str):
                        return [val] if val.strip() else []
                    return []
                pain_points = _to_list(portrait_data.get('pain_points', []))
                pain_scenarios = _to_list(portrait_data.get('pain_scenarios', []))
                barriers = _to_list(portrait_data.get('barriers', []))
                if not pain_points:
                    pp = portrait_data.get('pain_point', '')
                    if isinstance(pp, str) and pp.strip():
                        pain_points = [pp.strip()]

            prompt = self._build_template_prompt(
                keyword_core=keyword_core,
                region=region or '',
                industry=industry,
                pain_points=pain_points,
                pain_scenarios=pain_scenarios,
                barriers=barriers,
            )

            logger.info("[KeywordLibraryGenerator] 开始按模板生成关键词库，核心业务: %s", keyword_core)
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages, temperature=0.7, max_tokens=12000)

            if not response or not response.strip():
                result.error_message = "LLM调用返回为空"
                return result

            result = self._parse_template_result(response, result, keyword_core)

            if result.success:
                total = result.total_keywords
                logger.info(
                    "[KeywordLibraryGenerator] 模板关键词库生成完成: 总关键词=%d",
                    total,
                )

        except Exception as e:
            logger.error("[KeywordLibraryGenerator] 生成异常: %s", str(e))
            result.error_message = f"生成异常: {str(e)}"

        return result

    def _build_template_prompt(
        self,
        keyword_core: str,
        region: str,
        industry: str,
        pain_points: List[str],
        pain_scenarios: List[str],
        barriers: List[str],
    ) -> str:
        """构建关键词库模板Prompt（根据业务类型自动选择分类逻辑）"""

        core_lower = keyword_core.lower()
        # 付费者≠使用者关键词：用户与付费者分离
        # 仅检测明确的婴儿/孕妇产品关键词，不包括"学生/孩子"（容易误判教育/咨询服务）
        is_separate_payer = any(
            kw in core_lower
            for kw in ['宝宝', '婴儿', '奶粉', '孕妇', '童装',
                       ' baby', 'infant', 'kids']
        )

        pain_points_str = "\n".join([f"- {p}" for p in pain_points]) if pain_points else "（未提供）"
        pain_scenarios_str = "\n".join([f"- {s}" for s in pain_scenarios]) if pain_scenarios else "（未提供）"
        barriers_str = "\n".join([f"- {b}" for b in barriers]) if barriers else "（未提供）"
        region_str = region or '（未指定，根据业务推断）'

        if is_separate_payer:
            cleaned_core = self._extract_core_business(keyword_core, industry)
            return self._build_separate_payer_prompt(
                cleaned_core, region_str, industry,
                pain_points_str, pain_scenarios_str, barriers_str
            )
        else:
            return self._build_same_payer_prompt(
                keyword_core, region_str, industry,
                pain_points_str, pain_scenarios_str, barriers_str
            )

    def _build_same_payer_prompt(
        self,
        keyword_core: str,
        region_str: str,
        industry: str,
        pain_points_str: str,
        pain_scenarios_str: str,
        barriers_str: str,
    ) -> str:
        """精简版 Prompt：付费者=使用者"""
        cleaned_core = self._extract_core_business(keyword_core, industry)
        return f"""你是关键词库生成专家。基于「{keyword_core}」生成用户真实搜索词。

=== 业务 ===
核心业务：{keyword_core} | 地域：{region_str} | 行业：{industry}

=== 用户画像 ===
痛点：{pain_points_str}
场景：{pain_scenarios_str}
顾虑：{barriers_str}

=== 核心理念 ===
关键词 = 用户脑子里真正在想的词，不是产品介绍。
禁止：前缀拼接生硬词；禁止：流程/攻略/指南类介绍词
必须：用户搜这个词想解决什么问题？

=== 分类生成（总计>=145个） ===

**搜前搜（25个）**：决定前——担忧、顾虑、纠结
规则：从pain_points和barriers出发，用户决定时最担心什么？

**搜后搜（25个）**：使用后——出现了什么意外
规则：从pain_points和pain_scenarios出发，使用后可能出现什么偏差？

**信任佐证（15个）**：用户问"能不能帮我做好"
规则：从barriers出发，用户不信任什么？

**直接需求（15个）**：用户直接要买

**地域关键词（10个）**：用户找附近供应商
注：如未指定地域用"本地/附近/周边"

**季节/时间（10个）**：节假日/换季影响购买

**技巧/干货（10个）**：用户想学辨别知识

**认知颠覆（8个）**：打破常识引发好奇

**节日关键词（10个）**：节日送礼需求

=== 输出格式 ===
英文key：pre_search/post_search/trust/direct_demand/region/season/skill/reverse/festival

```json
{{"keyword_library": {{
    "pre_search_keywords": ["词1","词2"],
    "post_search_keywords": ["词1"],
    "trust_keywords": ["词1"],
    "direct_demand_keywords": ["词1"],
    "region_keywords": ["词1"],
    "season_keywords": ["词1"],
    "skill_keywords": ["词1"],
    "reverse_keywords": ["词1"],
    "festival_keywords": ["词1"]
}}}}
```
禁止复制示例，必须基于「{keyword_core}」真实生成。

请开始生成："""

    def _build_separate_payer_prompt(
        self,
        keyword_core: str,
        region_str: str,
        industry: str,
        pain_points_str: str,
        pain_scenarios_str: str,
        barriers_str: str,
    ) -> str:
        """精简版 Prompt：付费者≠使用者（如奶粉、母婴）"""
        cleaned_core = self._extract_core_business(keyword_core, industry)
        kw_short = cleaned_core[:4] if len(cleaned_core) >= 4 else cleaned_core
        return f"""你是关键词库生成专家。基于「{keyword_core}」生成用户真实搜索词。

=== 业务 ===
核心业务：{keyword_core} | 地域：{region_str} | 行业：{industry}

=== 用户画像 ===
使用者痛点：{pain_points_str}
使用场景：{pain_scenarios_str}
付费者顾虑：{barriers_str}

=== 核心理念 ===
本业务为"付费者≠使用者"：使用者（如宝宝）有症状，付费者（如家长）在担心。
关键词 = 付费者脑子里真正在想的词，不是产品介绍。
禁止：前缀拼接生硬词；禁止：流程/攻略类介绍词

=== 分类生成（总计>=145个） ===

**搜前搜（20个）**：付费者决定前——担忧、顾虑、对比
规则：从barriers出发，家长选购时最担心什么？

**搜后搜（15个）**：付费者使用后——孩子出现什么异常
规则：从pain_points出发，使用后可能出现什么症状？

**使用者问题（25个）**：使用者自身的身体/心理反应
规则：从pain_points出发，孩子有什么具体症状？
例："喝了{kw_short}后XX情况"

**付费者顾虑（25个）**：家长的购买担忧
覆盖：真假/信任、价格/划算、安全性/成分、选择/对比

**产品推荐（15个）**：用户对比具体产品时的搜索词

**地域关键词（10个）**：用户找附近供应商
注：如未指定地域用"本地/附近/周边"

**季节/时间（10个）**：节假日/换季影响购买

**技巧/干货（10个）**：用户想学辨别知识

**认知颠覆（8个）**：打破常识引发好奇

**节日关键词（10个）**：节日送礼需求

=== 输出格式 ===
英文key：pre_search/post_search/user_problem/payer_concern/product_recommend/region/season/skill/reverse/festival

```json
{{"keyword_library": {{
    "pre_search_keywords": ["词1","词2"],
    "post_search_keywords": ["词1"],
    "user_problem_keywords": ["词1"],
    "payer_concern_keywords": ["词1"],
    "product_recommend_keywords": ["词1"],
    "region_keywords": ["词1"],
    "season_keywords": ["词1"],
    "skill_keywords": ["词1"],
    "reverse_keywords": ["词1"],
    "festival_keywords": ["词1"]
}}}}
```
禁止复制示例，必须基于「{keyword_core}」真实生成。

请开始生成："""

    def _parse_template_result(
        self,
        response: str,
        result: KeywordLibraryResult,
        keyword_core: str,
    ) -> KeywordLibraryResult:
        """解析模板格式LLM返回结果"""

        try:
            text = response.strip()
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
            data = json.loads(text)
            if data is None:
                logger.warning("[KeywordLibraryGenerator] LLM返回了null JSON")
                result.error_message = "LLM返回了null JSON"
                return result
            result.raw_output = data

        except json.JSONDecodeError:
            logger.warning("[KeywordLibraryGenerator] JSON解析失败，尝试修复")
            data = self._try_fix_json(response)
            if not data or not isinstance(data, dict):
                result.error_message = "JSON解析失败"
                return result
            result.raw_output = data

        kl_data = data.get('keyword_library') or {}
        if not isinstance(kl_data, dict):
            kl_data = {}

        # 【调试】记录LLM原始返回的所有key
        llm_keys = list(kl_data.keys())
        logger.info(
            "[KeywordLibraryGenerator] LLM原始返回keyword_library的keys（共%d个）: %s",
            len(llm_keys), llm_keys
        )
        # >>> DEBUG: write raw keys to NDJSON log
        import datetime as _dt
        with open('/Volumes/增元/项目/douyin/.cursor/debug-f05487.log', 'a') as _lf:
            import json as _json
            _lf.write(_json.dumps({
                'sessionId': 'f05487', 'id': f'llm_keys_{_dt.datetime.now().strftime("%H%M%S%f")}',
                'timestamp': _dt.datetime.now().timestamp() * 1000,
                'location': 'keyword_library_generator.py:_parse_template_result',
                'message': 'LLM返回的keyword_library keys',
                'data': {'llm_keys': llm_keys},
                'hypothesisId': 'H1'
            }) + '\n')

        # 中文key→英文key 兜底映射（LLM有时用中文key）
        zh_to_en = {
            '搜前搜关键词': 'pre_search_keywords',
            '搜后搜关键词': 'post_search_keywords',
            '行业上下游关联词': 'industry_chain_keywords',
            '上下游关键词': 'industry_chain_keywords',
            '信任佐证关键词': 'trust_keywords',
            '直接需求关键词': 'direct_demand_keywords',
            '使用者问题关键词': 'user_problem_keywords',
            '使用者问题词': 'user_problem_keywords',
            '付费者顾虑关键词': 'payer_concern_keywords',
            '付费者顾虑词': 'payer_concern_keywords',
            '产品推荐关键词': 'product_recommend_keywords',
            '产品推荐词': 'product_recommend_keywords',
            '痛点关键词': 'pain_point_keywords',
            '痛点词': 'pain_point_keywords',
            '场景关键词': 'scene_keywords',
            '顾虑关键词': 'concern_keywords',
            '顾虑词': 'concern_keywords',
            '地域关键词': 'region_keywords',
            '季节关键词': 'season_keywords',
            '技巧/干货关键词': 'skill_keywords',
            '技巧关键词': 'skill_keywords',
            '认知颠覆关键词': 'reverse_keywords',
            '节日/节气关键词': 'festival_keywords',
            '节日关键词': 'festival_keywords',
        }
        # 将中文key替换为英文key
        for zh, en in zh_to_en.items():
            if zh in kl_data:
                kl_data[en] = kl_data.get(en) or kl_data[zh]

        categories = []
        total_count = 0

        # category_map：必须和 prompt 中定义的分类完全一致，否则新增的分类会被丢弃
        # same-payer prompt 新增了地域/季节/技巧/认知颠覆/节日，共10类
        # 旧格式兜底（兼容）：仅当独立 key 未命中时使用
        category_map = [
            # 付费者=使用者（5个key）
            ('pre_search_keywords', '搜前搜关键词'),
            ('post_search_keywords', '搜后搜关键词'),
            ('industry_chain_keywords', '行业上下游关联词'),
            ('trust_keywords', '信任佐证关键词'),
            ('direct_demand_keywords', '直接需求关键词'),
            # same-payer 新增5类（prompt 新增：地域/季节/技巧/认知颠覆/节日）
            ('region_keywords', '地域关键词'),
            ('season_keywords', '季节/时间关键词'),
            ('skill_keywords', '技巧/干货关键词'),
            ('reverse_keywords', '认知颠覆/反向关键词'),
            ('festival_keywords', '节日/节气关键词'),
            # 付费者≠使用者（3个key，替代 same-payer 的痛点/场景/顾虑）
            ('user_problem_keywords', '使用者问题关键词'),
            ('payer_concern_keywords', '付费者顾虑关键词'),
            ('product_recommend_keywords', '产品推荐关键词'),
            # 旧格式兜底（兼容）
            ('pain_point_keywords', '痛点关键词'),
            ('scene_keywords', '场景关键词'),
            ('concern_keywords', '顾虑关键词'),
        ]

        seen_in_categories = set()  # 避免同一 field_key 被重复添加到 categories
        for field_key, cat_name in category_map:
            kws = kl_data.get(field_key)
            if not kws:
                continue
            if not isinstance(kws, list):
                continue
            # 字符串关键词去重
            clean_kws = []
            seen = set()
            for kw in kws:
                kw_str = kw if isinstance(kw, str) else str(kw)
                if kw_str and kw_str not in seen:
                    seen.add(kw_str)
                    clean_kws.append(kw_str)
            # 跳过空分类
            if not clean_kws:
                continue
            # 跳过已出现过的 field_key（避免重复）
            if field_key in seen_in_categories:
                continue
            seen_in_categories.add(field_key)
            categories.append({
                'category_name': cat_name,
                'field_key': field_key,
                'keywords': clean_kws,
            })
            total_count += len(clean_kws)

        # 构建扁平字段（兼容下游服务：选题库、前端渲染、肖像生成）
        flat_fields = {}

        def _clean_kws(raw_list):
            """字符串关键词去重，保持顺序"""
            seen = set()
            result = []
            for kw in (raw_list or []):
                kw_str = kw if isinstance(kw, str) else str(kw)
                if kw_str and kw_str not in seen:
                    seen.add(kw_str)
                    result.append(kw_str)
            return result

        # same-payer: 搜前搜 → problem_type_keywords
        if kl_data.get('pre_search_keywords'):
            flat_fields['problem_type_keywords'] = _clean_kws(kl_data['pre_search_keywords'])
        # same-payer: 搜后搜 → pain_point_keywords
        if kl_data.get('post_search_keywords'):
            flat_fields['pain_point_keywords'] = _clean_kws(kl_data['post_search_keywords'])
        # 使用者问题关键词（separate-payer 专用）
        if kl_data.get('user_problem_keywords'):
            flat_fields['user_problem_keywords'] = _clean_kws(kl_data['user_problem_keywords'])
            if 'pain_point_keywords' not in flat_fields:
                flat_fields['pain_point_keywords'] = list(flat_fields['user_problem_keywords'])
            else:
                for kw in flat_fields['user_problem_keywords']:
                    if kw not in flat_fields['pain_point_keywords']:
                        flat_fields['pain_point_keywords'].append(kw)
        # 行业上下游 → scene_keywords
        if kl_data.get('industry_chain_keywords'):
            flat_fields['scene_keywords'] = _clean_kws(kl_data['industry_chain_keywords'])
        # 产品推荐关键词（separate-payer 专用）
        if kl_data.get('product_recommend_keywords'):
            flat_fields['product_recommend_keywords'] = _clean_kws(kl_data['product_recommend_keywords'])
            if 'scene_keywords' not in flat_fields:
                flat_fields['scene_keywords'] = list(flat_fields['product_recommend_keywords'])
            else:
                for kw in flat_fields['product_recommend_keywords']:
                    if kw not in flat_fields['scene_keywords']:
                        flat_fields['scene_keywords'].append(kw)
        # 信任佐证 → concern_keywords
        if kl_data.get('trust_keywords'):
            flat_fields['concern_keywords'] = _clean_kws(kl_data['trust_keywords'])
        # 付费者顾虑关键词（separate-payer 专用）
        if kl_data.get('payer_concern_keywords'):
            flat_fields['payer_concern_keywords'] = _clean_kws(kl_data['payer_concern_keywords'])
            if 'concern_keywords' not in flat_fields:
                flat_fields['concern_keywords'] = list(flat_fields['payer_concern_keywords'])
            else:
                for kw in flat_fields['payer_concern_keywords']:
                    if kw not in flat_fields['concern_keywords']:
                        flat_fields['concern_keywords'].append(kw)
        # 直接需求
        if kl_data.get('direct_demand_keywords'):
            flat_fields['direct_demand_keywords'] = _clean_kws(kl_data['direct_demand_keywords'])
        # 旧格式兜底（pain_point / scene / concern）
        for old_kw, flat_key in [
            ('pain_point_keywords', 'pain_point_keywords'),
            ('scene_keywords', 'scene_keywords'),
            ('concern_keywords', 'concern_keywords'),
        ]:
            for kw in _clean_kws(kl_data.get(old_kw)):
                if flat_key not in flat_fields:
                    flat_fields[flat_key] = [kw]
                elif kw not in flat_fields[flat_key]:
                    flat_fields[flat_key].append(kw)
        # 其他旧格式字段
        for old_key in ['region_keywords', 'season_keywords',
                         'skill_keywords', 'reverse_keywords', 'festival_keywords']:
            if kl_data.get(old_key) and old_key not in flat_fields:
                flat_fields[old_key] = _clean_kws(kl_data[old_key])

        # 【调试】记录解析结果
        cat_summary = [(c['category_name'], len(c['keywords'])) for c in categories]
        logger.info(
            "[KeywordLibraryGenerator] 解析完成: 总分类=%d, 总关键词=%d, 分类摘要=%s",
            len(categories), total_count, cat_summary
        )
        # >>> DEBUG: write parsed categories to NDJSON log
        import datetime as _dt
        with open('/Volumes/增元/项目/douyin/.cursor/debug-f05487.log', 'a') as _lf:
            import json as _json
            _lf.write(_json.dumps({
                'sessionId': 'f05487', 'id': f'parse_done_{_dt.datetime.now().strftime("%H%M%S%f")}',
                'timestamp': _dt.datetime.now().timestamp() * 1000,
                'location': 'keyword_library_generator.py:_parse_template_result',
                'message': '解析后的categories数量和名称',
                'data': {'categories_count': len(categories), 'cat_names': [c['category_name'] for c in categories]},
                'hypothesisId': 'H2'
            }) + '\n')

        result.keyword_library = {
            'categories': categories,
            'keyword_core': keyword_core,
            # 扁平字段：兼容下游服务（选题库、前端渲染）
            'problem_type_keywords': flat_fields.get('problem_type_keywords', []),
            'pain_point_keywords': flat_fields.get('pain_point_keywords', []),
            'scene_keywords': flat_fields.get('scene_keywords', []),
            'concern_keywords': flat_fields.get('concern_keywords', []),
            'direct_demand_keywords': flat_fields.get('direct_demand_keywords', []),
            # separate-payer 专用字段
            'user_problem_keywords': flat_fields.get('user_problem_keywords', []),
            'payer_concern_keywords': flat_fields.get('payer_concern_keywords', []),
            'product_recommend_keywords': flat_fields.get('product_recommend_keywords', []),
        }
        result.total_keywords = total_count
        result.success = True

        return result

    def _build_keyword_prompt(
        self,
        business_desc: str,
        industry: str,
        business_type: str,
        keyword_core: str,
        max_keywords: int,
        blue_ocean_opportunity: str = None,
        industry_insight: str = None,
        portraits: list = None,
        portrait_data: dict = None,
    ) -> str:
        """构建关键词库生成Prompt（v3：固定100个+决策链路+竞争度+场景支撑+上下游）"""

        # 从 portrait_data 提取痛点信息
        pain_points = []
        pain_scenarios = []
        barriers = []
        if portrait_data:
            def _to_list(val):
                if val is None:
                    return []
                if isinstance(val, list):
                    return val
                if isinstance(val, str):
                    return [val] if val.strip() else []
                return []
            pain_points = _to_list(portrait_data.get('pain_points', []))
            pain_scenarios = _to_list(portrait_data.get('pain_scenarios', []))
            barriers = _to_list(portrait_data.get('barriers', []))
            if not pain_points:
                pp = portrait_data.get('pain_point', '')
                if isinstance(pp, str) and pp.strip():
                    pain_points = [pp.strip()]

        pain_points_str = "\n".join([f"- {p}" for p in pain_points]) if pain_points else "（未提供）"
        pain_scenarios_str = "\n".join([f"- {s}" for s in pain_scenarios]) if pain_scenarios else "（未提供）"
        barriers_str = "\n".join([f"- {b}" for b in barriers]) if barriers else "（未提供）"

        blue_ocean_hint = ""
        if blue_ocean_opportunity:
            blue_ocean_hint = f"\n=== 蓝海机会背景 ===\n用户已选择以下蓝海机会：「{blue_ocean_opportunity}」\n请围绕这个细分方向生成关键词，重点挖掘该方向下的细分人群、场景和痛点。\n"

        insight_section = ""
        if industry_insight:
            insight_section = f"\n=== 行业洞察（基于真实搜索场景分析）===\n{industry_insight}\n\n以上洞察说明了这个行业用户的真实搜索场景。请基于这些洞察生成关键词。"

        business_type_hint = ""
        if business_type == 'product':
            business_type_hint = "业务为消费品，重点关注：使用者症状、购买者顾虑、选择对比"
        elif business_type == 'local_service':
            business_type_hint = "业务为本地服务，重点关注：服务场景、时效顾虑、信任问题"
        elif business_type == 'enterprise':
            business_type_hint = "业务为企业服务，重点关注：决策流程、ROI顾虑、供应商选择"
        else:
            business_type_hint = "业务为个人服务，重点关注：使用场景、效果顾虑、服务选择"

        safe_keyword_core = keyword_core or ''
        short_core = safe_keyword_core[:4] if len(safe_keyword_core) >= 4 else safe_keyword_core

        portraits_info = ""
        if portraits:
            for i, p in enumerate(portraits):
                portrait_id = chr(65 + i)
                portrait_name = p.get('name', f'画像{portrait_id}')
                problem_type = p.get('problem_type', '')
                portraits_info += f"\n- 画像{portrait_id}：{portrait_name}（{problem_type}）"

        # ── 预渲染画像段落（A/B/C），避免在 .format() 模板里写复杂表达式 ──
        def _safe(val, default=''):
            return val if val else default

        pA_name = _safe(portraits[0].get('name')) if portraits and len(portraits) > 0 else '画像A名称'
        pA_pt   = _safe(portraits[0].get('problem_type')) if portraits and len(portraits) > 0 else '画像A的问题类型'
        pA_desc = _safe(portraits[0].get('description')) if portraits and len(portraits) > 0 else '画像A的目标人群描述'

        pB_name = _safe(portraits[1].get('name')) if portraits and len(portraits) > 1 else '画像B名称'
        pB_pt   = _safe(portraits[1].get('problem_type')) if portraits and len(portraits) > 1 else '画像B的问题类型'
        pB_desc = _safe(portraits[1].get('description')) if portraits and len(portraits) > 1 else '画像B的目标人群描述'

        pC_name = _safe(portraits[2].get('name')) if portraits and len(portraits) > 2 else '画像C名称'
        pC_pt   = _safe(portraits[2].get('problem_type')) if portraits and len(portraits) > 2 else '画像C的问题类型'
        pC_desc = _safe(portraits[2].get('description')) if portraits and len(portraits) > 2 else '画像C的目标人群描述'

        prompt = ("""你是关键词库生成专家。请基于核心业务「{keyword_core}」，生成一份高质量的关键词库。

=== 业务信息 ===
原始业务描述：{business_desc}
行业：{industry_or}
业务类型：{business_type_hint}{blue_ocean_hint}

=== 核心业务 ===
{keyword_core}
{insight_section}

=== 画像列表 ===
{portraits_info}

=== 画像痛点信息（关键词生成的核心依据）===
核心痛点（用户在担心什么）：{pain_points_str}
使用场景：{pain_scenarios_str}
顾虑障碍：{barriers_str}

【画像专属关键词生成指引】
关键词从画像人群的视角出发，描述他们在现实中遇到的具体困惑。
B类画像专属词必须围绕"画像人群在{场景}中遇到的{具体问题}"。
画像专属词要能回答：这类人群最担心什么、最常问什么、最容易遇到什么。
一个画像专属词就是一个精准的"圈人"钩子。

---

## 【重要】质量红线

每个关键词必须满足以下条件才能输出：

1. **有具体场景**：不是泛泛的"质量不放心"，而是"宝宝喝奶粉拉肚子"、"灌香肠肥瘦比例多少"。避免空洞的问题词如"质量怎么判断"，必须有具体场景支撑。
2. **有明确搜索意图**：用户搜索这个词是想解决什么问题？
3. **禁止泛化词**：仅"怎么选"、"哪家好"、"多少钱" 没有具体场景支撑不得输出。
4. **禁止红海大词**：品类大词（如"灌香肠"单独出现）、节假日通用词（如"春节灌香肠"）竞争太激烈，新号不要正面竞争，改为长尾化。

---

## 【关键词生成方法论】

### 决策链路三阶段

每个关键词必须归入以下一个阶段：

| 阶段 | 特征 | 示例 |
|------|------|------|
| **认知阶段（awareness）** | 用户发现问题但还没确定方向，以"哪里有""是怎么回事""怎么判断"为主 | 灌香肠去哪里做好、怎么判断肉新不新鲜 |
| **考量阶段（consideration）** | 用户有方向后在比较方案，以"哪个好""有什么区别""怎么选"为主 | 灌香肠加肥肉好吃还是瘦肉、香肠烟熏几天最好 |
| **决策阶段（decision）** | 用户在做最终选择，以"多少钱""怎么联系""哪家靠谱"为主 | 灌香肠多少钱一斤、南漳灌香肠电话 |

### 竞争度三档

| 竞争度 | 特征 | 策略 |
|--------|------|------|
| **high** | 品类大词、节假日词、无地域修饰的通用词 | 新号避让，或长尾化后使用 |
| **medium** | 带方法/技巧/对比的词，场景细分词 | 可做，需差异化内容 |
| **low** | 具体痛点词、带地域/人群修饰的长尾词、专业场景词 | 蓝海机会，优先做 |

---

## 生成任务

关键词库共需生成 **100个关键词**，分为四部分：

---

### 第一部分：公用关键词（40个，所有画像共享）

围绕核心业务「{keyword_core}」，覆盖所有用户都会关心的通用问题，共40个，分5类，每类8个。

**【关键要求】关键词像真实用户自然搜索，长度6-14字。不要拼接无意义的完整业务词！**

#### 决策顾虑类（8个）
目的：用户在买之前最担心的问题。这个担心本身就标识了特定人群。
说明：关键词 = 用户在现实中遇到的具体问题，这个问题本身就圈定了人群。禁止业务流程词前缀。

生成规则：从画像的顾虑障碍（barriers）出发，把每个顾虑翻译成用户脑子里真正在想的词。
示例：画像顾虑=怕浪费分 → "分数不够想冲好学校怎么办"、画像顾虑=怕被调剂 → "分数不够被调剂到差专业怎么办"

#### 认知了解类（8个）
目的：用户在研究"这是什么/为什么"时的具体困惑。

生成规则：从画像人群的认知盲区出发，生成他们真正不了解的具体问题。
示例：画像痛点=不知道有什么选择 → "XX分能上什么档次的学校"、画像痛点=不了解规则 → "平行志愿和顺序志愿有什么区别"

#### 选择纠结类（8个）
目的：用户在纠结"选哪个"时的具体对比点。

生成规则：从画像人群的选择困难出发，生成他们真正在纠结的具体问题。
示例：画像顾虑=不知道冲还是保 → "冲好学校还是保稳"、画像顾虑=不知道选哪个专业 → "分数一般选学校还是选专业"

#### 使用后问题类（8个）
目的：用户使用/体验后遇到的具体问题。这是已购用户的真实困惑。

生成规则：从画像的使用场景痛点出发，生成他们使用后真正担心的问题。
示例：画像痛点=怕结果不如预期 → "录取结果和预期差太多怎么办"、画像痛点=怕修改窗口关闭 → "提交后发现填错了还能改吗"

#### 信任佐证类（8个）
目的：用户在问"能不能帮我做好"时的具体信任障碍。

生成规则：从画像的顾虑障碍出发，生成他们真正担心的信任问题。
示例：画像顾虑=不知道机构靠不靠谱 → "志愿填报机构落榜了怎么办"、画像顾虑=不知道效果真假 → "往年找他填的家长后来怎么样了"

---

### 第二部分：画像专属关键词（60个）

每个画像 = 痛点8个 + 场景8个 + 顾虑4个 = 20个，3个画像共60个。

**【核心公式】关键词 = [问题特征/场景/顾虑] + [具体疑问]**
**【关键约束】画像关键词禁止以核心业务「{keyword_core}」开头！**
**【质量要求】每个关键词必须带 scene_description（场景描述），解释这个关键词背后的用户真实场景。**

#### 画像A：{pA_name}
> 问题类型：{pA_pt}
> 目标人群：{pA_desc}

- **细分画像名称**（受众锁定用）：[问题类型/身份标签] + 身份词，如"选择困难型用户"

**痛点关键词（8个）**：该画像面临的具体问题，直接写问题本身，不加核心业务词前缀
**场景关键词（8个）**：该画像的具体使用场景，场景+问题，不加核心业务词
**顾虑关键词（4个）**：该画像的担忧和疑虑，顾虑+问题，不加核心业务词

#### 画像B：{pB_name}
> 问题类型：{pB_pt}
> 目标人群：{pB_desc}

痛点关键词（8个）、场景关键词（8个）、顾虑关键词（4个）

#### 画像C：{pC_name}
> 问题类型：{pC_pt}
> 目标人群：{pC_desc}

痛点关键词（8个）、场景关键词（8个）、顾虑关键词（4个）

---

### 第三部分：行业上下游关键词（20个）

围绕核心业务的产业链上下游，挖掘用户可能关心的关联词。

#### 上游关键词（5个）
上游：原材料、供应链相关
示例（灌香肠场景）：猪肉哪里买正宗、肠衣哪里有卖、香肠调料配方

#### 下游关键词（5个）
下游：加工服务、配套服务
示例（灌香肠场景）：香肠熏制服务、香肠包装设计、香肠礼盒定制

#### 配套工具关键词（5个）
配套工具：制作工具、辅助材料
示例（灌香肠场景）：灌香肠机器哪里有卖、绞肉机推荐、香肠烟熏炉

#### 技艺/工艺关键词（5个）
技艺类：制作技巧、工艺知识（指导后续选题生成）
示例（灌香肠场景）：灌香肠要不要加香油、香肠晒干需要几天、烟熏用什么木料

---

### 第四部分：禁用红海大词清单（供参考，不要生成）

以下大词竞争太激烈，新号不要用，改为长尾化：
- `{keyword_core}` 单独出现（无任何修饰）
- `{keyword_core}+多少钱` 类无地域修饰的价格词
- 节假日通用词（如"春节灌香肠"无特色）
- 品牌对比词（如"XX品牌和XX品牌哪个好"）

---

=== 输出格式 ===

请严格按以下JSON格式输出，不要输出任何其他内容：

{{
    "keyword_library": {{
        "keyword_core": "{keyword_core}",
        "common_keywords": {{
            "决策顾虑": [
                {{"keyword": "找人做不靠谱怎么办", "competition_level": "low", "decision_stage": "awareness", "scene_description": "用户担心选错服务商/产品，后果严重"}},
                {{"keyword": "选错了后果谁来承担", "competition_level": "low", "decision_stage": "awareness", "scene_description": "用户在担心如果做了错误的选择"}}
            ],
            "认知了解": [
                {{"keyword": "这家和别家有什么区别", "competition_level": "medium", "decision_stage": "consideration", "scene_description": "用户正在对比两家商家"}},
                {{"keyword": "贵和便宜差在哪", "competition_level": "medium", "decision_stage": "consideration", "scene_description": "用户对价格差异感到困惑"}}
            ],
            "选择纠结": [
                {{"keyword": "选便宜的还是选口碑好的", "competition_level": "medium", "decision_stage": "consideration", "scene_description": "用户在选择困难中"}},
                {{"keyword": "听家人还是听朋友的", "competition_level": "low", "decision_stage": "consideration", "scene_description": "用户意见分歧，不知听谁的"}}
            ],
            "使用后问题": [
                {{"keyword": "做完感觉不对劲怎么办", "competition_level": "low", "decision_stage": "decision", "scene_description": "用户购买后感到不满意，想知道如何处理"}},
                {{"keyword": "下次还找这家还是换一家", "competition_level": "low", "decision_stage": "decision", "scene_description": "用户在复购决策中犹豫"}}
            ],
            "信任佐证": [
                {{"keyword": "有问题能找得到人吗", "competition_level": "low", "decision_stage": "awareness", "scene_description": "用户担心售后服务缺失"}},
                {{"keyword": "评价是不是刷的", "competition_level": "low", "decision_stage": "consideration", "scene_description": "用户怀疑评价真实性"}}
            ]
        }},
        "personas": [
            {{
                "portrait_name": "XX型需求用户",
                "persona_problem_type": "XX问题型",
                "target_audience": "XX需求的用户群体",
                "pain_points": [
                    {{"keyword": "XX问题怎么处理", "competition_level": "low", "decision_stage": "consideration", "scene_description": "用户在遇到XX情况时不知道如何处理"}},
                    {{"keyword": "XX情况怎么选", "competition_level": "medium", "decision_stage": "consideration", "scene_description": "用户在XX场景下需要做选择"}}
                ],
                "scene_keywords": [
                    {{"keyword": "XX场景+怎么处理", "competition_level": "low", "decision_stage": "awareness", "scene_description": "用户在XX具体场景中遇到问题"}}
                ],
                "concerns": [
                    {{"keyword": "XX风险怎么避免", "competition_level": "low", "decision_stage": "awareness", "scene_description": "用户担心XX风险，希望提前了解"}}
                ]
            }}
        ],
        "upstream_keywords": [
            {{"keyword": "猪肉哪里买正宗", "competition_level": "low", "decision_stage": "awareness", "scene_description": "用户在上游寻找正宗原材料"}}
        ],
        "downstream_keywords": [
            {{"keyword": "香肠熏制服务", "competition_level": "low", "decision_stage": "consideration", "scene_description": "用户在寻找下游加工服务"}}
        ],
        "supporting_tools_keywords": [
            {{"keyword": "灌香肠机器哪里有卖", "competition_level": "low", "decision_stage": "decision", "scene_description": "用户在寻找配套制作工具"}}
        ],
        "technique_keywords": [
            {{"keyword": "灌香肠要不要加香油", "competition_level": "low", "decision_stage": "consideration", "scene_description": "用户在制作工艺上有疑问，指导具体选题方向"}}
        ]
    }}
}}

=== 强制约束 ===
1. **数量约束**：公用关键词40个（每类8个）+ 画像专属60个（3画像×20）+ 上下游20个 = 总计100个
2. **竞争度分布**：low至少40个、medium至少30个、high最多10个（high只出现在选择纠结类）
3. **画像比例**：公用关键词中B类画像专属词占比约50%，围绕画像pain_points/barriers生成
4. **质量红线**：每个keyword必须有合理的scene_description，禁止空洞泛化词
5. **画像多样性**：三个画像的痛点关键词必须彼此不同，聚焦各自特定问题
6. **禁止重复**：同一个意思只保留1个最自然的表达
7. **前缀规则**：公用关键词前缀用「{short_core}」，画像关键词禁止以「{keyword_core}」开头

请开始生成：""")

        prompt = prompt.format(
            keyword_core=safe_keyword_core,
            business_desc=business_desc,
            industry_or=industry or '根据业务描述推断',
            business_type_hint=business_type_hint,
            blue_ocean_hint=blue_ocean_hint,
            insight_section=insight_section,
            portraits_info=portraits_info or '（未提供画像，将自动推断3个画像）',
            pain_points_str=pain_points_str,
            pain_scenarios_str=pain_scenarios_str,
            barriers_str=barriers_str,
            short_core=short_core,
            pA_name=pA_name, pA_pt=pA_pt, pA_desc=pA_desc,
            pB_name=pB_name, pB_pt=pB_pt, pB_desc=pB_desc,
            pC_name=pC_name, pC_pt=pC_pt, pC_desc=pC_desc,
        )

        return prompt

    def _parse_result(
        self,
        response: str,
        result: KeywordLibraryResult
    ) -> KeywordLibraryResult:
        """解析LLM返回结果"""

        try:
            text = response.strip()
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
            data = json.loads(text)
            if data is None:
                logger.warning("[KeywordLibraryGenerator] LLM返回了null JSON")
                result.error_message = "LLM返回了null JSON"
                return result
            result.raw_output = data

        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
            import traceback
            logger.warning(
                "[KeywordLibraryGenerator] JSON解析失败，尝试修复: %s | response前200字符: %s | 堆栈: %s",
                e, text[:200] if text else '', traceback.format_exc()
            )
            data = self._try_fix_json(response)
            if not data or not isinstance(data, dict):
                result.error_message = f"JSON解析失败: {e}"
                return result
            result.raw_output = data

        problem_types = (data.get('problem_types') or [])
        for pt in (problem_types or []):
                result.problem_types.append(ProblemType(
                    type_name=pt.get('type_name', '') if isinstance(pt, dict) else '',
                    description=pt.get('description', '') if isinstance(pt, dict) else '',
                    target_audience=pt.get('target_audience', '') if isinstance(pt, dict) else '',
                    keywords=pt.get('keywords') or [],
                    scene_keywords=pt.get('scene_keywords') or [],
                ))

        raw_kw_lib = data.get('keyword_library')
        if raw_kw_lib is None:
            raw_kw_lib = {}
        # 防御：如果 LLM 返回的 keyword_library 不是 dict，记录并跳过
        if not isinstance(raw_kw_lib, dict):
            logger.warning(
                "[KeywordLibraryGenerator] keyword_library 类型异常: type=%s, 值前200字: %s",
                type(raw_kw_lib), str(raw_kw_lib)[:200]
            )
            raw_kw_lib = {}
        result.keyword_library = raw_kw_lib

        personas = (raw_kw_lib.get('personas') or []) or []
        if personas:
            for p in personas:
                if not isinstance(p, dict):
                    continue
                portrait_kw = {
                    'portrait_name': p.get('portrait_name', ''),
                    'persona_problem_type': p.get('persona_problem_type', ''),
                    'target_audience': p.get('target_audience', ''),
                    'pain_points': p.get('pain_points') or [],
                    'scene_keywords': p.get('scene_keywords') or [],
                    'concerns': p.get('concerns') or [],
                }
                result.portrait_keywords.append(portrait_kw)
                result.portrait_keywords_count += (
                    len(p.get('pain_points') or []) +
                    len(p.get('scene_keywords') or []) +
                    len(p.get('concerns') or [])
                )

        common_kw = raw_kw_lib.get('common_keywords') or {}
        if common_kw:
            for cat_kws in common_kw.values():
                if isinstance(cat_kws, list):
                    result.common_keywords_count += len(cat_kws)

        question_samples_data = data.get('question_samples') or {}
        if question_samples_data and isinstance(question_samples_data, dict):
            for q in (question_samples_data.get('pre_questions') or []):
                result.question_samples.append(QuestionSample(
                    question=q.get('question', '') if isinstance(q, dict) else '',
                    question_type='pre',
                    components=q.get('components') or {},
                ))
            for q in (question_samples_data.get('post_questions') or []):
                result.question_samples.append(QuestionSample(
                    question=q.get('question', '') if isinstance(q, dict) else '',
                    question_type='post',
                    components=q.get('components') or {},
                ))

        return result

    def _extract_core_business(self, business_desc: str, industry: str = '') -> str:
        """
        从业务描述中提取核心业务词（产品/服务名称）

        Args:
            business_desc: 业务描述
            industry: 行业（可选）

        Returns:
            str: 核心业务词
        """
        if not business_desc:
            return industry or ''

        text = business_desc.strip()

        prefixes = ['我们公司是', '我们是', '主要做', '主要从事', '业务是', '业务范围是',
                    '主要业务是', '公司主要做', '公司主要从事', '公司业务是',
                    '专业做', '专业从事', '从事', '做']
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        for prefix in ['卖', '销售', '提供', '经营']:
            if text.startswith(prefix) and len(text) > len(prefix):
                text = text[len(prefix):].strip()

        for suffix in ['的公司', '的业务', '的服务', '的产品', '的生意',
                       '有限公司', '有限责任公司', '股份公司', '集团']:
            if text.endswith(suffix):
                text = text[:-len(suffix)].strip()

        if len(text) <= 5:
            return text if text else industry or ''

        product_indicators = [
            '羊奶粉', '牛奶粉', '奶粉', '牛奶', '酸奶', '鲜奶',
            '婴幼儿奶粉', '儿童奶粉', '成人奶粉', '中老年奶粉',
            '有机奶粉', '配方奶粉', '辅食', '米粉', '果泥', '肉泥',
            '纸尿裤', '尿不湿', '婴儿车', '婴儿床', '奶瓶', '奶嘴',
            '护肤品', '化妆品', '面霜', '乳液', '精华', '面膜',
            '净水器', '空气净化器', '扫地机器人', '洗碗机',
            '香肠', '腊肉', '腊肠', '火腿', '肉制品', '豆制品',
            '家政服务', '保洁服务', '月嫂', '育儿嫂', '保姆', '钟点工',
            '培训服务', '咨询服务', '设计服务', '摄影服务', '摄像服务',
            '装修服务', '搬家服务', '家政保洁', '清洗服务',
            '志愿填报', '高考志愿', '留学服务', '移民服务',
            '法律咨询', '财务咨询', '税务代理', '知识产权',
            '软件开发', '网站建设', 'APP开发', '小程序开发',
            '矿泉水', '饮用水', '桶装水', '瓶装水',
            '土灶', '打土灶', '农村土灶', '土灶建造', '土灶维修',
            '上门服务', '家政', '维修', '安装', '清洗', '清洁',
            '农村服务', '农机', '农具', '农作物', '农产品',
            '婚姻介绍', '婚介', '相亲', '交友', '婚恋服务',
        ]

        for product in product_indicators:
            if product in text:
                return product

        if len(text) <= 8:
            marketing_words = ['市场', '蓝海', '红海', '赛道', '机会', '定位',
                             '高端', '细分', '垂直', '特色', '专业', '品质',
                             '优质', '创新', '独特', '个性', '专属', '定制化']
            for word in marketing_words:
                if word in text:
                    for indicator in ['服务', '维修', '安装', '建造', '清洗', '销售', '定制', '介绍']:
                        if indicator in text:
                            idx = text.index(indicator)
                            return text[:idx+len(indicator)].strip()
                    return ''
            return text

        return text[:8].strip() if text else industry or ''

    def _filter_keywords(self, keyword_library: Dict, keyword_core: str) -> Dict:
        """
        过滤明显不合适的关键词

        Args:
            keyword_library: 关键词库
            keyword_core: 核心业务词

        Returns:
            过滤后的关键词库
        """
        if not keyword_library:
            return keyword_library or {}

        bad_suffixes = [
            '长期喝', '长期用', '长期服用', '长期食用',
            '高铁上', '高铁', '飞机上', '旅行携带', '断奶期', '断奶',
            '早餐', '早餐用', '睡前喝', '睡前用',
            '婴儿', '新生儿', '宝宝', '儿童', '奶粉', '辅食',
        ]

        bad_questions = [
            '可以长期喝', '可以长期用', '可以长期服用',
            '对身体有害吗', '会有副作用吗', '能长期喝吗',
        ]

        def _filter_keyword_item(item: Any) -> bool:
            """判断单个关键词项是否应该保留"""
            kw_text = item.get('keyword', '') if isinstance(item, dict) else str(item)
            for suffix in bad_suffixes:
                if kw_text.endswith(suffix):
                    return False
            for q in bad_questions:
                if q in kw_text:
                    return False
            return True

        def filter_list(kw_list: List) -> List:
            return [kw for kw in kw_list if _filter_keyword_item(kw)]

        # 公用关键词
        common = (keyword_library or {}).get('common_keywords') or {}
        for cat, kws in common.items():
            if isinstance(kws, list):
                common[cat] = filter_list(kws)

        # 画像专属关键词
        for p in (keyword_library or {}).get('personas') or []:
            if not isinstance(p, dict):
                continue
            p['pain_points'] = filter_list(p.get('pain_points') or [])
            p['scene_keywords'] = filter_list(p.get('scene_keywords') or [])
            p['concerns'] = filter_list(p.get('concerns') or [])

        # 上下游关键词
        for field in ['upstream_keywords', 'downstream_keywords',
                       'supporting_tools_keywords', 'technique_keywords']:
            kw_list = (keyword_library or {}).get(field)
            if isinstance(kw_list, list):
                keyword_library[field] = filter_list(kw_list)

        return keyword_library

    def _try_fix_json(self, text: str) -> Optional[Dict]:
        """尝试修复损坏的JSON"""

        import re

        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx >= 0 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]

            try:
                return json.loads(json_str)
            except:
                pass

            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)

            try:
                return json.loads(json_str)
            except:
                pass

        return None


# ============================================================
# 便捷函数
# ============================================================

def generate_keyword_library(
    business_info: Dict[str, Any],
    business_direction: str,
    max_keywords: int = 100,
) -> KeywordLibraryResult:
    """
    便捷函数：生成关键词库

    使用方式：
        from services.keyword_library_generator import generate_keyword_library

        result = generate_keyword_library(
            business_info={'business_description': 'XX产品定制服务', 'industry': '定制服务'},
            business_direction='XX产品定制代理',
            max_keywords=100
        )

        if result.success:
            print(f"生成 {result.total_keywords} 个关键词")
            print(f"蓝海关键词: {result.blue_ocean_keywords}")
    """
    generator = KeywordLibraryGenerator()
    return generator.generate(business_info, core_business=None, max_keywords=max_keywords)
