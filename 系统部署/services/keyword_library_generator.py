"""
关键词库生成服务

功能：
基于画像数据，生成精准的关键词库（200个关键词，包含画像专属词、蓝海标签等）。

分类结构：
1. 公用关键词（80个）：所有画像共享
2. 画像专属关键词（120个）：基于3个画像的痛点生成

使用方式：
from services.keyword_library_generator import KeywordLibraryGenerator

generator = KeywordLibraryGenerator()
result = generator.generate(
    business_info={'business_description': '婚介服务', 'industry': '婚恋'},
    core_business='婚介服务',
    portraits=[...],  # 画像列表
    portrait_data={'pain_points': [...], 'pain_scenarios': [...], 'barriers': [...]},
    max_keywords=200,
)

result.success
result.keyword_library  # 关键词库
result.total_keywords   # 总关键词数
result.blue_ocean_tag_stats  # 蓝海标签统计
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

    # ===== 蓝海长尾词统计（任务1.4新增）=====
    blue_ocean_scene_keywords: int = 0      # 细分场景词数量
    blue_ocean精准需求_keywords: int = 0     # 精准需求词数量
    blue_ocean_pain_point_keywords: int = 0  # 痛点解决方案词数量
    blue_ocean_long_tail_keywords: int = 0   # 长尾问题词数量
    blue_ocean_tag_stats: Dict[str, int] = field(default_factory=dict)  # 蓝海标签统计

    # ===== 增强字段（任务1.3新增）=====
    geo_score: Dict[str, Any] = field(default_factory=dict)  # 地理评分：{"region": "...", "score": 85, "reason": "..."}
    trust_keywords: List[str] = field(default_factory=list)    # 信任关键词列表
    data_sources: List[str] = field(default_factory=list)     # 数据来源：["行业报告", "用户调研"]

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
            # 蓝海长尾词统计（任务1.4新增）
            'blue_ocean_tag_stats': self.blue_ocean_tag_stats,
            # 增强字段（任务1.3新增）
            'geo_score': self.geo_score,
            'trust_keywords': self.trust_keywords,
            'data_sources': self.data_sources,
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
        industry_insight: str = None,
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
            industry_insight: 行业洞察（可选，来自行业分析报告）

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

            logger.info("[KeywordLibraryGenerator] 开始调用LLM（分批模式）...")
            logger.info(f"[KeywordLibraryGenerator] 核心业务: {keyword_core}")
            if blue_ocean_opportunity:
                logger.info(f"[KeywordLibraryGenerator] 蓝海机会: {blue_ocean_opportunity}")

            # 使用分批生成
            batch_prompts = self._build_batch_prompts(
                business_desc=business_desc,
                industry=industry,
                business_type=business_type,
                keyword_core=keyword_core,
                blue_ocean_opportunity=blue_ocean_opportunity,
                industry_insight=industry_insight,
                portraits=portraits,
                portrait_data=portrait_data,
            )

            batch_results = []
            for batch in batch_prompts:
                batch_name = batch['batch_name']
                batch_num = batch['batch_num']
                batch_prompt = batch['prompt']

                logger.info(f"[KeywordLibraryGenerator] 开始生成第{batch_num}批: {batch_name}...")

                messages = [{"role": "user", "content": batch_prompt}]
                # 每批输出约40-60个关键词，预留充足空间
                response = self.llm.chat(messages, temperature=0.7, max_tokens=8000)

                logger.info(f"[KeywordLibraryGenerator] 第{batch_num}批 LLM返回长度={len(response) if response else 0}")

                if not response or not response.strip():
                    logger.warning(f"[KeywordLibraryGenerator] 第{batch_num}批 LLM返回为空，跳过")
                    continue

                # 解析本批结果
                batch_result = KeywordLibraryResult()
                batch_result = self._parse_result(response, batch_result)
                batch_results.append(batch_result)

                logger.info(f"[KeywordLibraryGenerator] 第{batch_num}批解析完成")

            # 合并所有批次结果
            if batch_results:
                merged_kw_lib = self._merge_batch_results(batch_results)
                result.keyword_library = merged_kw_lib
                logger.info("[KeywordLibraryGenerator] 分批生成完成，已合并结果")

            if result.keyword_library:
                result.keyword_library = self._filter_keywords(result.keyword_library, keyword_core)

            if result.keyword_library:
                kw_lib = result.keyword_library or {}
                all_kw = []
                
                # 详细统计每个分类的关键词数量（与 Geo SEO 对齐）
                detail_stats = {}
                
                # 搜前搜关键词
                pre_search = kw_lib.get('pre_search_keywords') or {}
                detail_stats['搜前搜关键词'] = {}
                for cat_name, cat_kws in pre_search.items():
                    if isinstance(cat_kws, list):
                        all_kw.extend(cat_kws)
                        detail_stats['搜前搜关键词'][cat_name] = len(cat_kws)
                    else:
                        detail_stats['搜前搜关键词'][cat_name] = 0
                
                # 搜后搜关键词
                post_search = kw_lib.get('post_search_keywords') or {}
                detail_stats['搜后搜关键词'] = {}
                for cat_name, cat_kws in post_search.items():
                    if isinstance(cat_kws, list):
                        all_kw.extend(cat_kws)
                        detail_stats['搜后搜关键词'][cat_name] = len(cat_kws)
                    else:
                        detail_stats['搜后搜关键词'][cat_name] = 0
                
                # 信任佐证关键词
                trust = kw_lib.get('trust_keywords') or {}
                detail_stats['信任佐证关键词'] = {}
                for cat_name, cat_kws in trust.items():
                    if isinstance(cat_kws, list):
                        all_kw.extend(cat_kws)
                        detail_stats['信任佐证关键词'][cat_name] = len(cat_kws)
                    else:
                        detail_stats['信任佐证关键词'][cat_name] = 0
                
                # 竞争优势关键词
                competitive = kw_lib.get('competitive_keywords') or {}
                detail_stats['竞争优势关键词'] = {}
                for cat_name, cat_kws in competitive.items():
                    if isinstance(cat_kws, list):
                        all_kw.extend(cat_kws)
                        detail_stats['竞争优势关键词'][cat_name] = len(cat_kws)
                    else:
                        detail_stats['竞争优势关键词'][cat_name] = 0
                
                # 地域关键词
                region = kw_lib.get('region_keywords') or {}
                detail_stats['地域关键词'] = {}
                for cat_name, cat_kws in region.items():
                    if isinstance(cat_kws, list):
                        all_kw.extend(cat_kws)
                        detail_stats['地域关键词'][cat_name] = len(cat_kws)
                    else:
                        detail_stats['地域关键词'][cat_name] = 0
                
                # 直接需求关键词
                direct_demand = kw_lib.get('direct_demand_keywords') or {}
                detail_stats['直接需求关键词'] = {}
                for cat_name, cat_kws in direct_demand.items():
                    if isinstance(cat_kws, list):
                        all_kw.extend(cat_kws)
                        detail_stats['直接需求关键词'][cat_name] = len(cat_kws)
                    else:
                        detail_stats['直接需求关键词'][cat_name] = 0
                
                # 上下游关键词
                all_kw.extend(kw_lib.get('upstream_keywords') or [])
                all_kw.extend(kw_lib.get('downstream_keywords') or [])
                all_kw.extend(kw_lib.get('supporting_tools_keywords') or [])
                all_kw.extend(kw_lib.get('technique_keywords') or [])
                result.total_keywords = len(all_kw)
                
                # 详细输出统计日志
                import datetime as _dt
                logger.info(f"[KeywordLibraryGenerator] 关键词详细分布（Geo SEO 结构）:")
                logger.info(f"  - 搜前搜关键词: {detail_stats.get('搜前搜关键词', {})}")
                logger.info(f"  - 搜后搜关键词: {detail_stats.get('搜后搜关键词', {})}")
                logger.info(f"  - 信任佐证关键词: {detail_stats.get('信任佐证关键词', {})}")
                logger.info(f"  - 竞争优势关键词: {detail_stats.get('竞争优势关键词', {})}")
                logger.info(f"  - 地域关键词: {detail_stats.get('地域关键词', {})}")
                logger.info(f"  - 直接需求关键词: {detail_stats.get('直接需求关键词', {})}")
                logger.info(f"  - 上下游关键词:")
                logger.info(f"    upstream: {len(kw_lib.get('upstream_keywords') or [])}")
                logger.info(f"    downstream: {len(kw_lib.get('downstream_keywords') or [])}")
                logger.info(f"    supporting_tools: {len(kw_lib.get('supporting_tools_keywords') or [])}")
                logger.info(f"    technique: {len(kw_lib.get('technique_keywords') or [])}")
                logger.info(f"  - 总计: {result.total_keywords}个")
                
                # 写入调试日志
                with open('/Volumes/增元/项目/douyin/.cursor/debug-f05487.log', 'a') as _lf:
                    import json as _json
                    _lf.write(_json.dumps({
                        'sessionId': 'f05487',
                        'id': f'kw_detail_{_dt.datetime.now().strftime("%H%M%S%f")}',
                        'timestamp': _dt.datetime.now().timestamp() * 1000,
                        'location': 'keyword_library_generator.py:generate',
                        'message': '关键词详细分布（Geo SEO 结构）',
                        'data': {
                            'total': result.total_keywords,
                            'pre_search': detail_stats.get('搜前搜关键词', {}),
                            'post_search': detail_stats.get('搜后搜关键词', {}),
                            'trust': detail_stats.get('信任佐证关键词', {}),
                            'competitive': detail_stats.get('竞争优势关键词', {}),
                            'region': detail_stats.get('地域关键词', {}),
                            'direct_demand': detail_stats.get('直接需求关键词', {}),
                            'upstream': len(kw_lib.get('upstream_keywords') or []),
                            'downstream': len(kw_lib.get('downstream_keywords') or []),
                            'supporting_tools': len(kw_lib.get('supporting_tools_keywords') or []),
                            'technique': len(kw_lib.get('technique_keywords') or []),
                        },
                    }) + '\n')
                
                # 蓝海/红海统计：关键词可能是字符串或 dict
                def get_level(kw):
                    if isinstance(kw, dict):
                        return (kw.get('competition_level') or '').lower()
                    return ''
                
                def get_blue_ocean_tag(kw):
                    """获取蓝海标签"""
                    if isinstance(kw, dict):
                        return kw.get('blue_ocean_tag', '') or ''
                    return ''
                
                result.blue_ocean_keywords = sum(1 for kw in all_kw if get_level(kw) == 'low')
                result.red_ocean_keywords = sum(1 for kw in all_kw if get_level(kw) == 'high')
                
                # 蓝海标签统计（任务1.4新增）
                blue_ocean_tag_counts = {
                    '细分场景词': 0,
                    '精准需求词': 0,
                    '痛点解决方案词': 0,
                    '长尾问题词': 0,
                    '': 0,
                }
                for kw in all_kw:
                    tag = get_blue_ocean_tag(kw)
                    if tag in blue_ocean_tag_counts:
                        blue_ocean_tag_counts[tag] += 1
                
                result.blue_ocean_scene_keywords = blue_ocean_tag_counts.get('细分场景词', 0)
                result.blue_ocean精准需求_keywords = blue_ocean_tag_counts.get('精准需求词', 0)
                result.blue_ocean_pain_point_keywords = blue_ocean_tag_counts.get('痛点解决方案词', 0)
                result.blue_ocean_long_tail_keywords = blue_ocean_tag_counts.get('长尾问题词', 0)
                result.blue_ocean_tag_stats = {k: v for k, v in blue_ocean_tag_counts.items() if v > 0}

            # 增强字段提取（任务1.3新增）
            self._extract_enhanced_fields(result, kw_lib, business_info)

            result.success = True
            logger.info(
                "[KeywordLibraryGenerator] 生成完成: 问题类型=%d, 关键词=%d (蓝海=%d, 红海=%d), 问句=%d",
                len(result.problem_types),
                result.total_keywords,
                result.blue_ocean_keywords,
                result.red_ocean_keywords,
                len(result.question_samples),
            )
            logger.info(
                "[KeywordLibraryGenerator] 蓝海标签统计: %s",
                result.blue_ocean_tag_stats,
            )

        except Exception as e:
            logger.error("[KeywordLibraryGenerator] 生成异常: %s", str(e))
            result.error_message = f"生成异常: {str(e)}"

        return result


    def _parse_template_result(
        self,
        response: str,
        result: KeywordLibraryResult,
        keyword_core: str,
        business_info: Dict[str, Any],
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

        def _normalize_kw_obj(kw):
            """将关键词转换为标准对象格式，保留完整元数据"""
            if isinstance(kw, dict):
                return {
                    'keyword': kw.get('keyword', ''),
                    'competition_level': kw.get('competition_level', ''),
                    'decision_stage': kw.get('decision_stage', ''),
                    'scene_description': kw.get('scene_description', ''),
                    'blue_ocean_tag': kw.get('blue_ocean_tag', ''),
                }
            elif isinstance(kw, str):
                return {
                    'keyword': kw,
                    'competition_level': '',
                    'decision_stage': '',
                    'scene_description': '',
                    'blue_ocean_tag': '',
                }
            else:
                return {
                    'keyword': str(kw),
                    'competition_level': '',
                    'decision_stage': '',
                    'scene_description': '',
                    'blue_ocean_tag': '',
                }

        def _clean_kw_objs(kw_list):
            """关键词对象去重，保持顺序"""
            seen = set()
            result = []
            for kw in (kw_list or []):
                kw_obj = _normalize_kw_obj(kw)
                kw_str = kw_obj.get('keyword', '')
                if kw_str and kw_str not in seen:
                    seen.add(kw_str)
                    result.append(kw_obj)
            return result

        # ── 解析新格式：common_keywords（公用关键词，每类是关键词对象数组）─────────────────
        # Prompt 返回: {"决策顾虑": [...], "认知了解": [...], ...}
        common_keywords_map = {
            '决策顾虑': '决策顾虑类',
            '认知了解': '认知了解类',
            '选择纠结': '选择纠结类',
            '使用后问题': '使用后问题类',
            '信任佐证': '信任佐证类',
            '地域关键词': '地域关键词类',
            '季节/时间': '季节/时间类',
            '季节关键词': '季节/时间类',
            '技巧/干货': '技巧/干货类',
            '技巧关键词': '技巧/干货类',
            '认知颠覆': '认知颠覆类',
            '节日/节气': '节日/节气类',
            '节日关键词': '节日/节气类',
        }
        common_kws = kl_data.get('common_keywords', {})
        if isinstance(common_kws, dict):
            for zh_cat, en_cat in common_keywords_map.items():
                kw_list = common_kws.get(zh_cat, [])
                if kw_list and isinstance(kw_list, list):
                    clean_objs = _clean_kw_objs(kw_list)
                    if clean_objs:
                        categories.append({
                            'category_name': en_cat,
                            'field_key': zh_cat,
                            'keywords': clean_objs,
                        })
                        total_count += len(clean_objs)

        # ── 解析新格式：personas（画像专属关键词）─────────────────────────────
        # Prompt 返回: [{"portrait_name": "...", "pain_points": [...], "scene_keywords": [...], "concerns": [...]}]
        personas_data = kl_data.get('personas', [])
        if isinstance(personas_data, list):
            for i, persona in enumerate(personas_data):
                if not isinstance(persona, dict):
                    continue
                # 痛点关键词
                pain_kws = persona.get('pain_points', [])
                if pain_kws and isinstance(pain_kws, list):
                    clean_objs = _clean_kw_objs(pain_kws)
                    if clean_objs:
                        categories.append({
                            'category_name': f'画像{i+1}痛点',
                            'field_key': f'pain_point_p{i+1}',
                            'keywords': clean_objs,
                        })
                        total_count += len(clean_objs)
                # 场景关键词
                scene_kws = persona.get('scene_keywords', [])
                if scene_kws and isinstance(scene_kws, list):
                    clean_objs = _clean_kw_objs(scene_kws)
                    if clean_objs:
                        categories.append({
                            'category_name': f'画像{i+1}场景',
                            'field_key': f'scene_p{i+1}',
                            'keywords': clean_objs,
                        })
                        total_count += len(clean_objs)
                # 顾虑关键词
                concern_kws = persona.get('concerns', [])
                if concern_kws and isinstance(concern_kws, list):
                    clean_objs = _clean_kw_objs(concern_kws)
                    if clean_objs:
                        categories.append({
                            'category_name': f'画像{i+1}顾虑',
                            'field_key': f'concern_p{i+1}',
                            'keywords': clean_objs,
                        })
                        total_count += len(clean_objs)

        # ── 解析新格式：上下游关键词 ─────────────────────────────────────────
        for field_key, cat_name in [
            ('upstream_keywords', '上游关键词'),
            ('downstream_keywords', '下游关键词'),
            ('supporting_tools_keywords', '配套工具关键词'),
            ('technique_keywords', '技艺/工艺关键词'),
        ]:
            kw_list = kl_data.get(field_key, [])
            if kw_list and isinstance(kw_list, list):
                clean_objs = _clean_kw_objs(kw_list)
                if clean_objs:
                    categories.append({
                        'category_name': cat_name,
                        'field_key': field_key,
                        'keywords': clean_objs,
                    })
                    total_count += len(clean_objs)

        # ── 兼容旧格式：如果新格式没有解析到关键词，尝试旧格式 ──────────────────
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

        # 记录已有的 field_key，避免旧格式重复添加
        seen_field_keys = set(c['field_key'] for c in categories)
        for field_key, cat_name in category_map:
            # 跳过已在新格式中解析过的字段
            if field_key in seen_field_keys:
                continue
            kws = kl_data.get(field_key)
            if not kws:
                continue
            if not isinstance(kws, list):
                continue
            # 使用 _clean_kw_objs 保留对象格式
            clean_objs = _clean_kw_objs(kws)
            # 跳过空分类
            if not clean_objs:
                continue
            seen_field_keys.add(field_key)
            categories.append({
                'category_name': cat_name,
                'field_key': field_key,
                'keywords': clean_objs,
            })
            total_count += len(clean_objs)

        # 构建扁平字段（兼容下游服务：选题库、前端渲染、肖像生成）
        flat_fields = {}

        def _kw_to_str(kw):
            """将关键词对象或字符串转换为字符串"""
            if isinstance(kw, dict):
                return kw.get('keyword', '')
            return str(kw) if kw else ''

        def _clean_kws(raw_list):
            """字符串关键词去重，保持顺序"""
            seen = set()
            result = []
            for kw in (raw_list or []):
                kw_str = _kw_to_str(kw)
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
                'message': '解析后的categories数量和名称及关键词数',
                'data': {
                    'categories_count': len(categories),
                    'cat_names': [c['category_name'] for c in categories],
                    'cat_keyword_counts': {c['category_name']: len(c.get('keywords', [])) for c in categories},
                    'total_count': total_count,
                    'llm_keys': llm_keys,
                },
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
        
        # 蓝海标签统计（任务1.4新增）- 用于模板模式
        blue_ocean_tag_counts = {
            '细分场景词': 0,
            '精准需求词': 0,
            '痛点解决方案词': 0,
            '长尾问题词': 0,
            '': 0,
        }
        
        def _get_blue_ocean_tag(kw):
            """获取蓝海标签"""
            if isinstance(kw, dict):
                return kw.get('blue_ocean_tag', '') or ''
            return ''
        
        def _collect_kws_for_stats(kws):
            """收集关键词用于统计"""
            if isinstance(kws, list):
                for kw in kws:
                    tag = _get_blue_ocean_tag(kw)
                    if tag in blue_ocean_tag_counts:
                        blue_ocean_tag_counts[tag] += 1
                    elif tag == '':
                        blue_ocean_tag_counts[''] += 1
        
        # 从categories收集统计（兼容字符串关键词和对象关键词）
        for cat in categories:
            cat_kws = cat.get('keywords', [])
            if cat_kws and isinstance(cat_kws, list):
                # 检查第一个元素来判断是字符串还是对象
                first_item = cat_kws[0] if cat_kws else None
                if isinstance(first_item, dict):
                    # 对象格式，直接统计
                    _collect_kws_for_stats(cat_kws)
                else:
                    # 字符串格式（从新格式转换来的），统计为空标签
                    blue_ocean_tag_counts[''] += len(cat_kws)
        
        result.blue_ocean_tag_stats = {k: v for k, v in blue_ocean_tag_counts.items() if v > 0}
        result.blue_ocean_keywords = blue_ocean_tag_counts.get('细分场景词', 0) + \
                                 blue_ocean_tag_counts.get('精准需求词', 0) + \
                                 blue_ocean_tag_counts.get('痛点解决方案词', 0) + \
                                 blue_ocean_tag_counts.get('长尾问题词', 0)
        
        # 增强字段提取（任务1.3新增）
        self._extract_enhanced_fields(result, kl_data, business_info)
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

        # 行业洞察section构建
        insight_section = ""
        if industry_insight:
            insight_section = f"""

=== 行业洞察（基于真实搜索场景分析）===
{industry_insight}

以上洞察说明了这个行业用户的真实搜索场景。请基于这些洞察生成关键词。"""

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

        # 预渲染行业洞察段落（避免在.format()里写复杂表达式）
        _insight_block = f"""
## 【重要】行业洞察（来源：行业分析报告）

{industry_insight if industry_insight else "（暂无行业洞察数据）"}

**使用指引**：结合行业洞察中的真实搜索场景，生成更精准的关键词。

"""

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
B类画像专属词必须围绕"画像人群在具体使用场景中遇到的具体问题"。
画像专属词要能回答：这类人群最担心什么、最常问什么、最容易遇到什么。
一个画像专属词就是一个精准的"圈人"钩子。

---

{_insight_block}

---

## 【重要】专科医生思维（核心方法论）

在生成关键词时，必须遵循以下专科医生思维：

### 1. 行业分析 → 发现蓝海问题
- 分析行业的供给缺口，找到被大品牌忽略的细分机会
- 蓝海词 = 用户有需求但没人做好 = 低竞争高转化

### 2. 人群细分 → 找到长尾需求
- 三类客户群体：
  - 本地居民：实惠、方便、新鲜
  - 返乡人：品质、包装、便携
  - 在外本地人：正宗、情怀、邮寄

### 3. 付费人/使用人区分
| 角色 | 关注点 | 示例 |
|------|--------|------|
| 付费人 | 价值、成本、效果、可报销 | 老板、老公、父母 |
| 使用人 | 体验、品质、方便 | 员工、孩子、老婆 |

### 4. 搜前搜后全阶段覆盖
| 阶段 | 关键词类型 | 示例 |
|------|-----------|------|
| 搜前 | 问题探索 | "XX怎么办" |
| 搜中 | 方案对比 | "XX和XX哪个好" |
| 搜后 | 购买决策 | "XX多少钱" |

### 5. 行业关联：上下游联动
- 上游供应链：原材料、货源正宗
- 下游配套服务：配送、售后、增值

---

## 【重要】质量红线

每个关键词必须满足以下条件才能输出：

1. **有具体场景**：不是泛泛的"质量不放心"，而是"宝宝喝奶粉拉肚子"、"灌香肠肥瘦比例多少"。避免空洞的问题词如"质量怎么判断"，必须有具体场景支撑。
2. **有明确搜索意图**：用户搜索这个词是想解决什么问题？
3. **禁止泛化词**：仅"怎么选"、"哪家好"、"多少钱" 没有具体场景支撑不得输出。
4. **禁止红海大词**：品类大词（如"灌香肠"单独出现）、节假日通用词（如"春节灌香肠"）竞争太激烈，新号不要正面竞争，改为长尾化。
5. **禁止产品介绍句式**：
   - ❌ 禁止"XX公司/平台/服务+如何/怎么/是否"开头
   - ❌ 错误示例："婚介平台如何验证信息真实性"、"婚介公司怎么收费"、"婚介服务是否靠谱"
   - ✅ 正确示例："相亲对象信息是真的吗"、"网上认识的人靠谱吗"、"收费多少钱"

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

### 蓝海长尾词要求（占25%）

蓝海长尾词 = 细分场景 + 精准需求 + 痛点解决 + 长尾问题，必须占25%

| 细分类型 | 占比 | 示例 |
|----------|------|------|
| 细分场景词 | 8% | 凌晨送豆芽、火锅店豆芽配送 |
| 精准需求词 | 6% | 精品豆芽礼盒装、净菜配送 |
| 痛点解决方案词 | 6% | 豆芽隔夜不坏方法、豆芽去苦味 |
| 长尾问题词 | 5% | 发豆芽要不要见光、豆芽有根好还是无根好 |

---

## 生成任务

关键词库共需生成 **200个关键词**，分为四部分：

公用关键词（80个，所有画像共享）占40%
画像专属关键词（120个）占60%

---

### 第一部分：公用关键词（80个，所有画像共享）

围绕核心业务「{keyword_core}」，覆盖所有用户都会关心的通用问题，共80个，分10类，每类8个。

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

#### 地域关键词类（8个）
目的：用户找附近供应商/服务的地域相关问题

生成规则：从业务特点出发，生成用户找附近服务的地域词。
示例："XX哪里有"、"XX附近哪家好"、"本地XX服务"

#### 季节/时间类（8个）
目的：节假日、换季等时间节点影响购买的需求词

生成规则：从业务的时间属性出发，生成季节性/节假日相关词。
示例："XX季要注意什么"、"节假日前XX优惠"、"XX天凉了怎么办"

#### 技巧/干货类（8个）
目的：用户想学辨别知识、使用技巧的相关问题

生成规则：从用户的知识盲区出发，生成用户想了解的实用技巧。
示例："XX怎么辨别好坏"、"XX小技巧"、"XX要注意什么"

#### 认知颠覆类（8个）
目的：打破常识引发好奇的逆向思维词

生成规则：从行业常识出发，生成颠覆认知的反常识词。
示例："XX不一定贵的好"、"为什么XX没人说"、"XX的真相"

#### 节日/节气类（8个）
目的：节日送礼、节日场景相关的需求词

生成规则：从传统节日出发，生成节日场景相关词。
示例："XX节送什么"、"春节期间XX"、"节后XX要注意什么"

---

### 第二部分：画像专属关键词（120个）

每个画像 = 痛点14个 + 场景14个 + 顾虑12个 = 40个，3个画像共120个。

**【核心公式】关键词 = [问题特征/场景/顾虑] + [具体疑问]**
**【关键约束】画像关键词禁止以核心业务「{keyword_core}」开头！**
**【质量要求】每个关键词必须带 scene_description（场景描述），解释这个关键词背后的用户真实场景。**
**【蓝海要求】画像专属词中，蓝海长尾词（competition_level=low）占比≥60%，必须标注blue_ocean_tag**

蓝海标签说明：
- 细分场景词：带地域/人群/时间修饰的精准场景词
- 精准需求词：针对特定人群的精准需求词
- 痛点解决方案词：解决具体痛点的问题词
- 长尾问题词：具体细节问题的长尾词

#### 画像A：{pA_name}
> 问题类型：{pA_pt}
> 目标人群：{pA_desc}

- **细分画像名称**（受众锁定用）：[问题类型/身份标签] + 身份词，如"选择困难型用户"

**痛点关键词（14个）**：该画像面临的具体问题，直接写问题本身，不加核心业务词前缀
**场景关键词（14个）**：该画像的具体使用场景，场景+问题，不加核心业务词
**顾虑关键词（12个）**：该画像的担忧和疑虑，顾虑+问题，不加核心业务词

#### 画像B：{pB_name}
> 问题类型：{pB_pt}
> 目标人群：{pB_desc}

痛点关键词（14个）、场景关键词（14个）、顾虑关键词（12个）

#### 画像C：{pC_name}
> 问题类型：{pC_pt}
> 目标人群：{pC_desc}

痛点关键词（14个）、场景关键词（14个）、顾虑关键词（12个）

---

### 第三部分：行业上下游关键词（30个以上）

围绕核心业务的产业链上下游，挖掘用户可能关心的关联词。

**重要**：必须生成用户真实的搜索问题，不是产品/服务介绍！

#### 上游关键词（8个以上）
上游：用户在购买前可能遇到的原材料、准备相关问题
示例："XX原材料哪里买正宗"、"XX材料怎么选"、"XX添加剂安全吗"

#### 下游关键词（8个以上）
下游：用户使用后可能遇到的问题
示例："XX坏了怎么办"、"XX味道不对正常吗"、"XX保存方法"

#### 配套工具关键词（7个以上）
配套工具：用户可能需要的周边产品/工具相关问题
示例："XX用什么工具"、"XX机器哪里有卖"、"XX配件哪里买"

#### 技艺/工艺关键词（7个以上）
技艺类：用户关心的使用技巧、制作知识
示例："XX要不要加YY"、"XX晒干需要几天"、"XX用什么材料好"

**禁止生成**：禁止生成"XX服务"、"XX定制"、"XX加工"等产品服务介绍词！

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

每个关键词项必须包含5个字段：
- keyword: 关键词
- competition_level: 竞争度（low/medium/high）
- decision_stage: 决策阶段（awareness/consideration/decision）
- scene_description: 场景描述
- blue_ocean_tag: 蓝海标签（细分场景词/精准需求词/痛点解决方案词/长尾问题词/空字符串）

{{
    "keyword_library": {{
        "keyword_core": "{keyword_core}",
        "common_keywords": {{
            "决策顾虑": [
                {{"keyword": "找人做不靠谱怎么办", "competition_level": "low", "decision_stage": "awareness", "scene_description": "用户担心选错服务商/产品，后果严重", "blue_ocean_tag": "痛点解决方案词"}},
                {{"keyword": "选错了后果谁来承担", "competition_level": "low", "decision_stage": "awareness", "scene_description": "用户在担心如果做了错误的选择", "blue_ocean_tag": "长尾问题词"}}
            ],
            "认知了解": [
                {{"keyword": "这家和别家有什么区别", "competition_level": "medium", "decision_stage": "consideration", "scene_description": "用户正在对比两家商家", "blue_ocean_tag": ""}},
                {{"keyword": "贵和便宜差在哪", "competition_level": "medium", "decision_stage": "consideration", "scene_description": "用户对价格差异感到困惑", "blue_ocean_tag": ""}}
            ],
            "选择纠结": [
                {{"keyword": "选便宜的还是选口碑好的", "competition_level": "medium", "decision_stage": "consideration", "scene_description": "用户在选择困难中", "blue_ocean_tag": ""}},
                {{"keyword": "听家人还是听朋友的", "competition_level": "low", "decision_stage": "consideration", "scene_description": "用户意见分歧，不知听谁的", "blue_ocean_tag": "细分场景词"}}
            ],
            "使用后问题": [
                {{"keyword": "做完感觉不对劲怎么办", "competition_level": "low", "decision_stage": "decision", "scene_description": "用户购买后感到不满意，想知道如何处理", "blue_ocean_tag": "痛点解决方案词"}},
                {{"keyword": "下次还找这家还是换一家", "competition_level": "low", "decision_stage": "decision", "scene_description": "用户在复购决策中犹豫", "blue_ocean_tag": "精准需求词"}}
            ],
            "信任佐证": [
                {{"keyword": "有问题能找得到人吗", "competition_level": "low", "decision_stage": "awareness", "scene_description": "用户担心售后服务缺失", "blue_ocean_tag": "痛点解决方案词"}},
                {{"keyword": "评价是不是刷的", "competition_level": "low", "decision_stage": "consideration", "scene_description": "用户怀疑评价真实性", "blue_ocean_tag": "长尾问题词"}}
            ]
        }},
        "personas": [
            {{
                "portrait_name": "XX型需求用户",
                "persona_problem_type": "XX问题型",
                "target_audience": "XX需求的用户群体",
                "pain_points": [
                    {{"keyword": "XX问题怎么处理", "competition_level": "low", "decision_stage": "consideration", "scene_description": "用户在遇到XX情况时不知道如何处理", "blue_ocean_tag": "痛点解决方案词"}},
                    {{"keyword": "XX情况怎么选", "competition_level": "medium", "decision_stage": "consideration", "scene_description": "用户在XX场景下需要做选择", "blue_ocean_tag": ""}}
                ],
                "scene_keywords": [
                    {{"keyword": "XX场景+怎么处理", "competition_level": "low", "decision_stage": "awareness", "scene_description": "用户在XX具体场景中遇到问题", "blue_ocean_tag": "细分场景词"}}
                ],
                "concerns": [
                    {{"keyword": "XX风险怎么避免", "competition_level": "low", "decision_stage": "awareness", "scene_description": "用户担心XX风险，希望提前了解", "blue_ocean_tag": "痛点解决方案词"}}
                ]
            }}
        ],
        "upstream_keywords": [
            {{"keyword": "猪肉哪里买正宗", "competition_level": "low", "decision_stage": "awareness", "scene_description": "用户在上游寻找正宗原材料", "blue_ocean_tag": "细分场景词"}}
        ],
        "downstream_keywords": [
            {{"keyword": "香肠熏制服务", "competition_level": "low", "decision_stage": "consideration", "scene_description": "用户在寻找下游加工服务", "blue_ocean_tag": "精准需求词"}}
        ],
        "supporting_tools_keywords": [
            {{"keyword": "灌香肠机器哪里有卖", "competition_level": "low", "decision_stage": "decision", "scene_description": "用户在寻找配套制作工具", "blue_ocean_tag": "精准需求词"}}
        ],
        "technique_keywords": [
            {{"keyword": "灌香肠要不要加香油", "competition_level": "low", "decision_stage": "consideration", "scene_description": "用户在制作工艺上有疑问，指导具体选题方向", "blue_ocean_tag": "长尾问题词"}}
        ]
    }}
}}

=== 强制约束 ===
1. **【最重要】数量约束**：公用关键词80个（每类8个）+ 画像专属120个（3画像×40）+ 上下游至少30个 = 总计≥200个
   ⚠️ **警告**：如果输出关键词总数少于200个，将被视为不合格！
2. **竞争度分布**：low至少80个、medium至少70个、high最多20个（high只出现在选择纠结类）
3. **画像比例**：画像专属关键词中蓝海词（competition_level=low）占比≥60%
4. **蓝海标签**：所有competition_level=low的关键词必须标注blue_ocean_tag
   - 细分场景词：带地域/人群/时间修饰的精准场景词
   - 精准需求词：针对特定人群的精准需求词
   - 痛点解决方案词：解决具体痛点的问题词
   - 长尾问题词：具体细节问题的长尾词
5. **质量红线**：每个keyword必须有合理的scene_description，禁止空洞泛化词
6. **画像多样性**：三个画像的痛点关键词必须彼此不同，聚焦各自特定问题
7. **禁止重复**：同一个意思只保留1个最自然的表达
8. **前缀规则**：公用关键词前缀用「{short_core}」，画像关键词禁止以「{keyword_core}」开头
9. **必须包含分类**：输出必须包含所有分类（common_keywords全部5类 + personas全部3个 + 上下游4类），缺一不可！

请开始生成：""")

        prompt = prompt.format(
            keyword_core=safe_keyword_core,
            business_desc=business_desc,
            industry_or=industry or '根据业务描述推断',
            business_type_hint=business_type_hint,
            blue_ocean_hint=blue_ocean_hint,
            insight_section=insight_section,
            _insight_block=_insight_block,
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

    def _build_batch_prompts(
        self,
        business_desc: str,
        industry: str,
        business_type: str,
        keyword_core: str,
        blue_ocean_opportunity: str = None,
        industry_insight: str = None,
        portraits: list = None,
        portrait_data: dict = None,
    ) -> list:
        """
        构建分批生成的Prompt列表（3批）

        批1: 公用关键词（50个）- 5类×10个
        批2: 画像专属关键词（90个）- 3画像×30个（痛点10+场景10+顾虑10）
        批3: 上下游关键词（30个）- 上游8+下游8+配套7+技艺7
        """
        prompts = []

        # 提取痛点信息
        def _to_list(val):
            if val is None:
                return []
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                return [val] if val.strip() else []
            return []

        pain_points = _to_list(portrait_data.get('pain_points', [])) if portrait_data else []
        pain_scenarios = _to_list(portrait_data.get('pain_scenarios', [])) if portrait_data else []
        barriers = _to_list(portrait_data.get('barriers', [])) if portrait_data else []
        if portrait_data and not pain_points:
            pp = portrait_data.get('pain_point', '')
            if isinstance(pp, str) and pp.strip():
                pain_points = [pp.strip()]

        pain_points_str = "\n".join([f"- {p}" for p in pain_points]) if pain_points else "（未提供）"
        pain_scenarios_str = "\n".join([f"- {s}" for s in pain_scenarios]) if pain_scenarios else "（未提供）"
        barriers_str = "\n".join([f"- {b}" for b in barriers]) if barriers else "（未提供）"

        blue_ocean_hint = ""
        if blue_ocean_opportunity:
            blue_ocean_hint = f"\n=== 蓝海机会背景 ===\n用户已选择以下蓝海机会：「{blue_ocean_opportunity}」\n请围绕这个细分方向生成关键词。\n"

        # 预渲染画像信息（核心业务画像）
        def _safe(val, default=''):
            return val if val else default

        # 核心业务画像（来自当前保存的画像）
        core_portrait_name = ''
        core_portrait_desc = ''

        if portraits and len(portraits) > 0:
            # 使用第一个画像作为核心画像
            core_portrait_name = _safe(portraits[0].get('name'), '核心用户')
            # 优先使用 description，其次使用 portrait_summary
            portrait_desc = _safe(portraits[0].get('description'))
            if not portrait_desc:
                portrait_desc = _safe(portraits[0].get('portrait_summary'))
            core_portrait_desc = portrait_desc if portrait_desc else '目标用户群体'
        else:
            # 没有画像时，从业务描述和痛点信息推断
            core_portrait_name = '核心用户'
            # 从痛点信息构建描述
            if pain_points_str and pain_points_str != '（未提供）':
                # 取第一个痛点作为画像描述
                first_pain = pain_points_str.split('\n')[0] if '\n' in pain_points_str else pain_points_str
                core_portrait_desc = f'关注{keyword_core}的用户群体，核心痛点：{first_pain}'
            else:
                core_portrait_desc = f'关注{keyword_core}的潜在客户'

        # 画像A（核心画像）
        pA_name = _safe(portraits[0].get('name')) if portraits and len(portraits) > 0 else core_portrait_name
        pA_pt = _safe(portraits[0].get('problem_type')) if portraits and len(portraits) > 0 else '核心需求'
        pA_desc = _safe(portraits[0].get('description')) if portraits and len(portraits) > 0 else core_portrait_desc

        # 画像B（如果有第二画像，否则使用通用描述）
        if portraits and len(portraits) > 1:
            pB_name = _safe(portraits[1].get('name'))
            pB_pt = _safe(portraits[1].get('problem_type'))
            pB_desc = _safe(portraits[1].get('description'))
        else:
            # 使用业务痛点构建通用画像
            pB_name = '潜在用户'
            pB_pt = '潜在顾虑'
            pB_desc = f'对{keyword_core}有需求但存在顾虑的用户'

        # 画像C（如果有第三画像，否则使用通用描述）
        if portraits and len(portraits) > 2:
            pC_name = _safe(portraits[2].get('name'))
            pC_pt = _safe(portraits[2].get('problem_type'))
            pC_desc = _safe(portraits[2].get('description'))
        else:
            # 使用业务痛点构建通用画像
            pC_name = '精准用户'
            pC_pt = '精准需求'
            pC_desc = f'对{keyword_core}有明确需求的目标用户'

        # ========== 批1: 搜前搜+搜后搜关键词 ==========
        prompt_batch1 = f"""你是关键词库生成专家。请基于核心业务「{keyword_core}」，生成用户搜索行为关键词库。

=== 业务信息 ===
原始业务描述：{business_desc}
行业：{industry or '根据业务描述推断'}
{blue_ocean_hint}

=== 画像痛点信息（关键词生成依据）===
核心痛点：{pain_points_str}
使用场景：{pain_scenarios_str}
顾虑障碍：{barriers_str}

=== 生成任务：搜前搜+搜后搜关键词（共70个）===

【核心思维】关键词按用户搜索行为阶段分类：搜前（认知了解）、搜后（决策购买）

【关键要求】关键词像真实用户自然搜索，长度6-14字，不要拼接无意义的完整业务词！

#### 一、搜前搜关键词（35个）- 用户搜索前的认知阶段
目的：用户在购买前会问的问题，覆盖"搜索前"的认知阶段

##### 1.1 工艺认知类（8个）
用户在了解"怎么做/怎么做才好"
示例："怎么做正宗"、"有什么讲究"

##### 1.2 价格认知类（8个）
用户在了解"值不值/贵不贵"
示例："收费合理吗"、"多少钱正常"

##### 1.3 质量认知类（8个）
用户在了解"好不好/靠不靠谱"
示例："哪家做得好"、"怎么判断正宗"

##### 1.4 便捷认知类（6个）
用户在了解"方不方便/麻不麻烦"
示例："自己做还是找人做"、"需要准备什么"

##### 1.5 服务认知类（5个）
用户在了解"有没有这个服务"
示例："哪里有做的"、"能不能上门"

#### 二、搜后搜关键词（35个）- 用户搜索后的决策阶段
目的：用户在搜索后会问的问题，覆盖"搜索后"的决策阶段

##### 2.1 工艺问题类（8个）
用户在问"具体怎么做/注意什么"
示例："肥瘦比例多少"、"盐放多少"

##### 2.2 保存存储类（8个）
用户在问"怎么保存/能放多久"
示例："能放多久"、"冷冻还是冷藏"

##### 2.3 决策顾虑类（8个）
用户在担心"万一不好怎么办"
示例："不满意能退吗"、"不好吃怎么办"

##### 2.4 售后保障类（6个）
用户在问"有没有保障"
示例："有售后吗"、"不满意怎么处理"

##### 2.5 实际需求类（5个）
用户在问"具体怎么做/多少钱"
示例："需要带什么"、"可以先看看吗"

=== 输出格式 ===
严格按以下JSON格式输出，每个关键词必须包含5个字段：
- keyword: 关键词（自然搜索语言，6-14字）
- competition_level: 竞争度（low/medium/high）
- decision_stage: 决策阶段（awareness/consideration/decision）
- scene_description: 场景描述（20字以内）
- blue_ocean_tag: 蓝海标签（细分场景词/精准需求词/痛点解决方案词/长尾问题词/空字符串）

{{
    "keyword_library": {{
        "pre_search_keywords": {{
            "工艺认知": [
                {{"keyword": "怎么做才好吃", "competition_level": "medium", "decision_stage": "awareness", "scene_description": "用户在了解制作方法", "blue_ocean_tag": "精准需求词"}}
            ],
            "价格认知": [...],
            "质量认知": [...],
            "便捷认知": [...],
            "服务认知": [...]
        }},
        "post_search_keywords": {{
            "工艺问题": [
                {{"keyword": "肥瘦比例多少", "competition_level": "low", "decision_stage": "consideration", "scene_description": "用户在准备制作", "blue_ocean_tag": "长尾问题词"}}
            ],
            "保存存储": [...],
            "决策顾虑": [...],
            "售后保障": [...],
            "实际需求": [...]
        }}
    }}
}}

=== 强制约束 ===
1. 必须生成70个关键词，搜前搜35个+搜后搜35个，不足则不合格！
2. competition_level=low至少35个，medium最多25个，high最多10个
3. 所有low必须标注blue_ocean_tag
4. 关键词禁止以核心业务「{keyword_core}」开头！

请开始生成："""

        prompts.append({
            'batch_name': '搜前搜+搜后搜关键词',
            'batch_num': 1,
            'prompt': prompt_batch1,
        })

        # ========== 批2: 信任佐证+竞争优势+地域关键词 ==========
        prompt_batch2 = f"""你是关键词库生成专家。请基于核心业务「{keyword_core}」，生成信任佐证、竞争优势和地域关键词。

=== 业务信息 ===
核心业务：{keyword_core}
原始业务描述：{business_desc}
行业：{industry or '根据业务描述推断'}
{blue_ocean_hint}

=== 生成任务：信任佐证+竞争优势+地域关键词（共45个）===

【核心思维】
- 信任佐证：解决用户"能不能帮我做好"的问题
- 竞争优势：解决用户"为什么要选你"的问题
- 地域关键词：解决本地用户"哪里有/找哪家"的问题

【关键要求】关键词像真实用户自然搜索，长度6-14字！

#### 一、信任佐证关键词（15个）
目的：用户在问"能不能帮我做好"时的信任障碍

##### 1.1 专业资质类（5个）
示例："有多少年经验"、"专业培训过吗"

##### 1.2 案例证明类（5个）
示例："有成功案例吗"、"客户反馈怎么样"

##### 1.3 环境展示类（5个）
示例："可以现场观看吗"、"卫生条件怎么样"

#### 二、竞争优势关键词（15个）
目的：解决用户"为什么要选你"的问题

##### 2.1 省心优势类（5个）
示例："一条龙服务"、"全程不用操心"

##### 2.2 省钱优势类（5个）
示例："比自己做划算"、"收费透明"

##### 2.3 放心优势类（5个）
示例："不满意包退"、"先做满意再付款"

#### 三、地域关联关键词（15个）
目的：解决本地用户"哪里有/找哪家"的问题

##### 3.1 本地服务类（8个）
示例："XX本地服务"、"XX同城上门"

##### 3.2 地域品牌类（7个）
示例："XX老店"、"XX本地口碑"

=== 输出格式 ===
严格按以下JSON格式输出，每个关键词必须包含5个字段：
- keyword: 关键词（自然搜索语言，6-14字）
- competition_level: 竞争度（low/medium/high）
- decision_stage: 决策阶段（awareness/consideration/decision）
- scene_description: 场景描述（20字以内）
- blue_ocean_tag: 蓝海标签（细分场景词/精准需求词/痛点解决方案词/长尾问题词/空字符串）

{{
    "keyword_library": {{
        "trust_keywords": {{
            "专业资质": [
                {{"keyword": "有多少年经验", "competition_level": "low", "decision_stage": "consideration", "scene_description": "用户在评估专业度", "blue_ocean_tag": "精准需求词"}}
            ],
            "案例证明": [...],
            "环境展示": [...]
        }},
        "competitive_keywords": {{
            "省心优势": [
                {{"keyword": "一条龙服务", "competition_level": "medium", "decision_stage": "decision", "scene_description": "用户在选择服务商", "blue_ocean_tag": ""}}
            ],
            "省钱优势": [...],
            "放心优势": [...]
        }},
        "region_keywords": {{
            "本地服务": [
                {{"keyword": "XX同城服务", "competition_level": "low", "decision_stage": "awareness", "scene_description": "本地用户搜索", "blue_ocean_tag": "细分场景词"}}
            ],
            "地域品牌": [...]
        }}
    }}
}}

=== 强制约束 ===
1. 必须生成45个关键词（信任15+竞争优势15+地域15），不足则不合格！
2. competition_level=low至少22个（50%），medium最多15个，high最多8个
3. 所有low必须标注blue_ocean_tag
4. 地域关键词中的"XX"需要替换为具体地域名称（如果有地域信息）

请开始生成："""

        prompts.append({
            'batch_name': '信任佐证+竞争优势+地域',
            'batch_num': 2,
            'prompt': prompt_batch2,
        })

        # ========== 批3: 直接需求关键词 ==========
        prompt_batch3 = f"""你是关键词库生成专家。请基于核心业务「{keyword_core}」，生成直接需求关键词。

=== 业务信息 ===
核心业务：{keyword_core}
原始业务描述：{business_desc}
行业：{industry or '根据业务描述推断'}
{blue_ocean_hint}

=== 生成任务：直接需求关键词（25个）===

【核心思维】用户有明确需求时会搜索的关键词，直接表明意图

【关键要求】关键词像真实用户自然搜索，长度6-14字！

#### 一、服务需求类（10个）
用户直接找服务商的关键词
示例："哪里有做的"、"电话多少"、"可以上门吗"

#### 二、价格需求类（8个）
用户直接问价格的关键词
示例："多少钱"、"怎么收费"、"贵不贵"

#### 三、地址需求类（7个）
用户直接找地址的关键词
示例："在哪里"、"地址多少"、"怎么走"

=== 输出格式 ===
严格按以下JSON格式输出，每个关键词必须包含5个字段：
- keyword: 关键词（自然搜索语言，6-14字）
- competition_level: 竞争度（low/medium/high）
- decision_stage: 决策阶段（awareness/consideration/decision）
- scene_description: 场景描述（20字以内）
- blue_ocean_tag: 蓝海标签（细分场景词/精准需求词/痛点解决方案词/长尾问题词/空字符串）

{{
    "keyword_library": {{
        "direct_demand_keywords": {{
            "服务需求": [
                {{"keyword": "哪里有做的", "competition_level": "high", "decision_stage": "decision", "scene_description": "用户直接找服务", "blue_ocean_tag": ""}}
            ],
            "价格需求": [
                {{"keyword": "做一次多少钱", "competition_level": "medium", "decision_stage": "consideration", "scene_description": "用户直接问价格", "blue_ocean_tag": ""}}
            ],
            "地址需求": [
                {{"keyword": "在哪里", "competition_level": "high", "decision_stage": "decision", "scene_description": "用户直接找地址", "blue_ocean_tag": ""}}
            ]
        }}
    }}
}}

=== 强制约束 ===
1. 必须生成25个关键词（服务10+价格8+地址7），不足则不合格！
2. 直接需求词竞争度普遍较高，high可以占40%左右
3. 所有low必须标注blue_ocean_tag

请开始生成："""

        prompts.append({
            'batch_name': '直接需求关键词',
            'batch_num': 3,
            'prompt': prompt_batch3,
        })

        # ========== 批4: 上下游关键词 ==========
        prompt_batch4 = f"""你是关键词库生成专家。请基于核心业务「{keyword_core}」，生成行业上下游关键词库。

=== 业务信息 ===
核心业务：{keyword_core}
{blue_ocean_hint}

=== 生成任务：行业上下游关键词（30个）===

围绕核心业务的产业链上下游，挖掘用户可能关心的关联问题。

【重要】必须生成用户真实的搜索问题，不是产品/服务介绍！

#### 上游关键词（8个）
上游：用户在购买前可能遇到的原材料、准备相关问题
示例："XX原材料哪里买正宗"、"XX材料怎么选"

#### 下游关键词（8个）
下游：用户使用后可能遇到的问题
示例："XX坏了怎么办"、"XX味道不对正常吗"

#### 配套工具关键词（7个）
配套工具：用户可能需要的周边产品/工具相关问题
示例："XX用什么工具"、"XX机器哪里有卖"

#### 技艺/工艺关键词（7个）
技艺类：用户关心的使用技巧、制作知识
示例："XX要不要加YY"、"XX晒干需要几天"

【禁止生成】禁止生成"XX服务"、"XX定制"、"XX加工"等产品服务介绍词！

=== 输出格式 ===
严格按以下JSON格式输出：

{{
    "keyword_library": {{
        "upstream_keywords": [
            {{"keyword": "上游问题词", "competition_level": "low", "decision_stage": "awareness", "scene_description": "场景描述", "blue_ocean_tag": "细分场景词"}}
        ],
        "downstream_keywords": [
            {{"keyword": "下游问题词", "competition_level": "low", "decision_stage": "decision", "scene_description": "场景描述", "blue_ocean_tag": "痛点解决方案词"}}
        ],
        "supporting_tools_keywords": [
            {{"keyword": "配套工具问题词", "competition_level": "medium", "decision_stage": "consideration", "scene_description": "场景描述", "blue_ocean_tag": ""}}
        ],
        "technique_keywords": [
            {{"keyword": "技艺工艺问题词", "competition_level": "low", "decision_stage": "consideration", "scene_description": "场景描述", "blue_ocean_tag": "长尾问题词"}}
        ]
    }}
}}

=== 强制约束 ===
1. 必须生成30个关键词（上游8+下游8+配套7+技艺7），不足则不合格！
2. competition_level=low至少15个
3. 所有low必须标注blue_ocean_tag

请开始生成："""

        prompts.append({
            'batch_name': '上下游关键词',
            'batch_num': 4,
            'prompt': prompt_batch4,
        })

        return prompts

    def _merge_batch_results(self, batch_results: list) -> dict:
        """
        合并多个批次的生成结果

        Args:
            batch_results: 每个批次的 KeywordLibraryResult 列表

        Returns:
            dict: 合并后的完整关键词库
        """
        merged = {
            'keyword_core': '',
            # 搜前搜关键词
            'pre_search_keywords': {
                '工艺认知': [],
                '价格认知': [],
                '质量认知': [],
                '便捷认知': [],
                '服务认知': [],
            },
            # 搜后搜关键词
            'post_search_keywords': {
                '工艺问题': [],
                '保存存储': [],
                '决策顾虑': [],
                '售后保障': [],
                '实际需求': [],
            },
            # 信任佐证关键词
            'trust_keywords': {
                '专业资质': [],
                '案例证明': [],
                '环境展示': [],
            },
            # 竞争优势关键词
            'competitive_keywords': {
                '省心优势': [],
                '省钱优势': [],
                '放心优势': [],
            },
            # 地域关键词
            'region_keywords': {
                '本地服务': [],
                '地域品牌': [],
            },
            # 直接需求关键词
            'direct_demand_keywords': {
                '服务需求': [],
                '价格需求': [],
                '地址需求': [],
            },
            # 上下游关键词
            'upstream_keywords': [],
            'downstream_keywords': [],
            'supporting_tools_keywords': [],
            'technique_keywords': [],
        }

        for batch_result in batch_results:
            if not batch_result or not batch_result.keyword_library:
                continue

            kw_lib = batch_result.keyword_library or {}

            # 合并搜前搜关键词
            pre_search = kw_lib.get('pre_search_keywords') or {}
            for cat_name in merged['pre_search_keywords'].keys():
                if cat_name in pre_search and isinstance(pre_search[cat_name], list):
                    merged['pre_search_keywords'][cat_name].extend(pre_search[cat_name])

            # 合并搜后搜关键词
            post_search = kw_lib.get('post_search_keywords') or {}
            for cat_name in merged['post_search_keywords'].keys():
                if cat_name in post_search and isinstance(post_search[cat_name], list):
                    merged['post_search_keywords'][cat_name].extend(post_search[cat_name])

            # 合并信任佐证关键词
            trust = kw_lib.get('trust_keywords') or {}
            for cat_name in merged['trust_keywords'].keys():
                if cat_name in trust and isinstance(trust[cat_name], list):
                    merged['trust_keywords'][cat_name].extend(trust[cat_name])

            # 合并竞争优势关键词
            competitive = kw_lib.get('competitive_keywords') or {}
            for cat_name in merged['competitive_keywords'].keys():
                if cat_name in competitive and isinstance(competitive[cat_name], list):
                    merged['competitive_keywords'][cat_name].extend(competitive[cat_name])

            # 合并地域关键词
            region = kw_lib.get('region_keywords') or {}
            for cat_name in merged['region_keywords'].keys():
                if cat_name in region and isinstance(region[cat_name], list):
                    merged['region_keywords'][cat_name].extend(region[cat_name])

            # 合并直接需求关键词
            direct_demand = kw_lib.get('direct_demand_keywords') or {}
            for cat_name in merged['direct_demand_keywords'].keys():
                if cat_name in direct_demand and isinstance(direct_demand[cat_name], list):
                    merged['direct_demand_keywords'][cat_name].extend(direct_demand[cat_name])

            # 合并上下游关键词
            merged['upstream_keywords'].extend(kw_lib.get('upstream_keywords') or [])
            merged['downstream_keywords'].extend(kw_lib.get('downstream_keywords') or [])
            merged['supporting_tools_keywords'].extend(kw_lib.get('supporting_tools_keywords') or [])
            merged['technique_keywords'].extend(kw_lib.get('technique_keywords') or [])

        return merged

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

    # ===========================================================================
    # 增强字段提取（任务1.3新增）
    # ===========================================================================

    def _extract_enhanced_fields(
        self,
        result: KeywordLibraryResult,
        kw_lib: Dict[str, Any],
        business_info: Dict[str, Any],
    ):
        """
        提取和计算增强字段：geo_score, trust_keywords, data_sources

        Args:
            result: 关键词库结果对象
            kw_lib: 关键词库数据
            business_info: 业务信息
        """
        # ── 1. 提取信任关键词 ──
        trust_kws = []

        # 从 trust_keywords 字段提取
        if 'trust_keywords' in kw_lib:
            trust_raw = kw_lib['trust_keywords']
            if isinstance(trust_raw, list):
                for kw in trust_raw:
                    if isinstance(kw, str):
                        trust_kws.append(kw)
                    elif isinstance(kw, dict):
                        trust_kws.append(kw.get('keyword', ''))

        # 从 concern_keywords 提取
        if 'concern_keywords' in kw_lib:
            concern_raw = kw_lib['concern_keywords']
            if isinstance(concern_raw, list):
                for kw in concern_raw:
                    if isinstance(kw, str):
                        trust_kws.append(kw)
                    elif isinstance(kw, dict):
                        trust_kws.append(kw.get('keyword', ''))

        # 从 common_keywords.信任佐证 提取
        common = kw_lib.get('common_keywords', {})
        if isinstance(common, dict):
            trust_from_common = common.get('信任佐证', [])
            for kw in trust_from_common:
                if isinstance(kw, str):
                    trust_kws.append(kw)
                elif isinstance(kw, dict):
                    trust_kws.append(kw.get('keyword', ''))

        # 去重
        result.trust_keywords = list(dict.fromkeys([k for k in trust_kws if k]))

        # ── 2. 计算地理评分 ──
        region = business_info.get('region', '')
        keyword_core = kw_lib.get('keyword_core', '')

        # 提取地域关键词计算评分
        region_keywords = []
        if 'region_keywords' in kw_lib:
            region_raw = kw_lib['region_keywords']
            if isinstance(region_raw, list):
                for kw in region_raw:
                    if isinstance(kw, str):
                        region_keywords.append(kw)
                    elif isinstance(kw, dict):
                        region_keywords.append(kw.get('keyword', ''))

        # 评分逻辑
        geo_score = 50  # 基础分
        if region:
            geo_score += 10  # 有地域信息
        if region_keywords:
            geo_score += min(20, len(region_keywords) * 2)  # 地域关键词越多分越高
        if keyword_core and any(kw in region for kw in region_keywords):
            geo_score += 10  # 核心业务与地域匹配
        geo_score = min(100, geo_score)

        reason_parts = []
        if region:
            reason_parts.append(f"地域：{region}")
        if region_keywords:
            reason_parts.append(f"地域关键词：{len(region_keywords)}个")
        if geo_score >= 70:
            reason_parts.append("地域覆盖度高")
        elif geo_score >= 50:
            reason_parts.append("地域覆盖度中等")

        result.geo_score = {
            'region': region or keyword_core[:4] if keyword_core else '通用',
            'score': geo_score,
            'reason': '，'.join(reason_parts) if reason_parts else '基于关键词库分析',
            'region_keywords': [k for k in region_keywords if k][:10],
        }

        # ── 3. 数据来源 ──
        data_sources = []

        # 通用来源
        if result.total_keywords > 0:
            data_sources.append('关键词库生成')

        # 画像关键词来源
        if result.portrait_keywords_count > 0:
            data_sources.append('画像专属关键词')

        # 蓝海/红海分类来源
        if result.blue_ocean_keywords > 0 or result.red_ocean_keywords > 0:
            data_sources.append('竞争度分析')

        # 地域评分来源
        if region_keywords:
            data_sources.append('地域分析')

        # 问题类型来源
        if result.problem_types:
            data_sources.append('问题类型提取')

        result.data_sources = data_sources if data_sources else ['系统生成']


# ============================================================
# 便捷函数
# ============================================================

def generate_keyword_library(
    business_info: Dict[str, Any],
    max_keywords: int = 100,
) -> KeywordLibraryResult:
    """
    便捷函数：生成关键词库

    使用方式：
        from services.keyword_library_generator import generate_keyword_library

        result = generate_keyword_library(
            business_info={'business_description': 'XX产品定制服务', 'industry': '定制服务'},
            max_keywords=100
        )

        if result.success:
            print(f"生成 {result.total_keywords} 个关键词")
            print(f"蓝海关键词: {result.blue_ocean_keywords}")
    """
    generator = KeywordLibraryGenerator()
    return generator.generate(business_info, core_business=None, max_keywords=max_keywords)
