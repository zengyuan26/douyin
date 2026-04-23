"""
画像专属选题库生成服务

核心原则：
- LLM 只负责生成：title、keywords、recommended_reason、type_key
- 本地代码控制：五段式阶段配比、选题类型分配、兜底补全、缓存
- 每个选题强制归属一个五段式阶段（受众锁定 / 痛点放大 / 方案对比 / 愿景勾画 / 顾虑消除）
- GEO 模式在内容生成时由 content_generator.match_geo_mode() 动态决定
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


class TopicLibraryGenerator:
    """
    选题库生成器

    核心原则：
    - LLM 只生成内容：title、keywords、recommended_reason、type_key
    - 所有规则由本地控制：五段式阶段配比、选题类型分配、校验、兜底
    - GEO 模式在内容生成时由 content_generator.match_geo_mode() 动态决定
    """

    # =============================================================================
    # 本地静态规则 - LLM 不参与计算
    # =============================================================================

    # 选题分类（五段式内容框架）
    # 五段式内容框架：
    # ① 受众锁定 → ② 痛点放大 → ③ 方案对比 → ④ 愿景勾画 → ⑤ 顾虑消除
    TOPIC_TYPES = [
        # ① 受众锁定（圈人：让用户判断"这说的是不是我"）
        {'name': '人群锁定',   'key': 'identity',         'stage': 'audience',    'direction': '种草型', 'priority': 'P1'},
        {'name': '场景细分',   'key': 'scene',            'stage': 'audience',    'direction': '种草型', 'priority': 'P2'},
        {'name': '地域精准',   'key': 'region',           'stage': 'audience',    'direction': '种草型', 'priority': 'P3'},

        # ② 痛点放大（放大痛苦：让人意识到现在的做法有多糟糕）
        {'name': '原因分析',   'key': 'cause',           'stage': 'pain',        'direction': '种草型', 'priority': 'P1'},
        {'name': '避坑指南',   'key': 'pitfall',         'stage': 'pain',        'direction': '种草型', 'priority': 'P1'},
        {'name': '认知颠覆',   'key': 'rethink',         'stage': 'pain',        'direction': '种草型', 'priority': 'P2'},
        {'name': '知识教程',   'key': 'tutorial',        'stage': 'pain',        'direction': '种草型', 'priority': 'P1'},

        # ③ 方案对比（给方案：突出"我的方案为什么更好"）
        {'name': '方案对比',   'key': 'compare',         'stage': 'compare',     'direction': '种草型', 'priority': 'P0'},
        {'name': '效果验证',   'key': 'effect_proof',    'stage': 'compare',     'direction': '种草型', 'priority': 'P1'},
        {'name': '上游科普',   'key': 'upstream',        'stage': 'compare',     'direction': '种草型', 'priority': 'P2'},
        {'name': '行业关联',   'key': 'industry',        'stage': 'compare',     'direction': '种草型', 'priority': 'P2'},

        # ④ 愿景勾画（画饼：让人期待"用之后会变多好"）
        {'name': '实操技巧',   'key': 'skill',           'stage': 'vision',      'direction': '种草型', 'priority': 'P1'},
        {'name': '季节营销',   'key': 'seasonal',        'stage': 'vision',      'direction': '种草型', 'priority': 'P2'},
        {'name': '节日营销',   'key': 'festival',        'stage': 'vision',      'direction': '种草型', 'priority': 'P1'},
        {'name': '情感故事',   'key': 'emotional',       'stage': 'vision',      'direction': '种草型', 'priority': 'P3'},

        # ⑤ 顾虑消除（打消顾虑："用了之后有问题怎么办"）
        {'name': '痛点放大',   'key': 'pain_point',      'stage': 'hesitation', 'direction': '转化型', 'priority': 'P0'},
        {'name': '决策安心',   'key': 'decision_encourage', 'stage': 'hesitation', 'direction': '转化型', 'priority': 'P0'},
        {'name': '行情价格',   'key': 'price',           'stage': 'hesitation', 'direction': '转化型', 'priority': 'P2'},
        {'name': '工具耗材',   'key': 'tools',           'stage': 'hesitation', 'direction': '种草型', 'priority': 'P2'},
    ]

    TYPE_KEY_MAP = {t['key']: t for t in TOPIC_TYPES}

    # 五段式阶段 → 中文名
    STAGE_NAMES = {
        'audience':   '受众锁定',
        'pain':       '痛点放大',
        'compare':    '方案对比',
        'vision':     '愿景勾画',
        'hesitation': '顾虑消除',
    }

    # 五段式阶段顺序（数字越小越靠前）
    STAGE_ORDER = {
        'audience':   1,
        'pain':       2,
        'compare':    3,
        'vision':     4,
        'hesitation': 5,
    }

    # 三套选题配比（内容阶段联动）- 本地控制
    STAGE_RATIO_MAP = {
        '起号阶段': {
            'audience':   0.20,
            'pain':       0.40,
            'compare':    0.25,
            'vision':     0.10,
            'hesitation': 0.05,
            'description': '20%受众锁定 + 40%痛点放大 + 25%方案对比 + 10%愿景勾画 + 5%顾虑消除',
        },
        '成长阶段': {
            'audience':   0.15,
            'pain':       0.25,
            'compare':    0.30,
            'vision':     0.15,
            'hesitation': 0.15,
            'description': '15%受众锁定 + 25%痛点放大 + 30%方案对比 + 15%愿景勾画 + 15%顾虑消除',
        },
        '成熟阶段': {
            'audience':   0.10,
            'pain':       0.15,
            'compare':    0.30,
            'vision':     0.20,
            'hesitation': 0.25,
            'description': '10%受众锁定 + 15%痛点放大 + 30%方案对比 + 20%愿景勾画 + 25%顾虑消除',
        },
    }

    # 五段式阶段 → type_key 列表的本地映射
    STAGE_TO_TYPES = {
        'audience':   [t['key'] for t in TOPIC_TYPES if t['stage'] == 'audience'],
        'pain':       [t['key'] for t in TOPIC_TYPES if t['stage'] == 'pain'],
        'compare':    [t['key'] for t in TOPIC_TYPES if t['stage'] == 'compare'],
        'vision':     [t['key'] for t in TOPIC_TYPES if t['stage'] == 'vision'],
        'hesitation': [t['key'] for t in TOPIC_TYPES if t['stage'] == 'hesitation'],
    }

    # 五段式阶段 → 中文说明（prompt 中用）
    STAGE_RATIO_DESCRIPTIONS = {
        'audience':   '20%受众锁定：重在圈人，让人判断"这说的是不是我"',
        'pain':       '40%痛点放大：重在放大痛苦，让人意识到"现在的做法有多糟糕"',
        'compare':    '25%方案对比：重在给方案，突出"我的方案为什么更好"',
        'vision':     '10%愿景勾画：重在画饼，期待"用之后会变多好"',
        'hesitation': '5%顾虑消除：重在打消顾虑，"用了之后有问题怎么办"',
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
            'keywords': ['顾虑', '担心', '害怕', '疑虑', '怕', '担忧', '不确定', '安全', '质量', '真假', '成分', '价格贵'],
            'dimension_name': '购买顾虑',
        },
        'scenario': {
            'keywords': ['场景', '时候', '情况', '高铁', '旅行', '旅游', '上班', '上学', '早餐', '睡前', '断奶', '辅食', '术后', '产后'],
            'dimension_name': '使用场景',
        },
    }

    # 画像维度 → 五段式阶段优先映射
    DIMENSION_STAGE_PRIORITY = {
        'identity': {
            'primary_stage': 'audience',
            'secondary_stages': ['vision'],
            'preferred_type_keys': ['identity', 'scene', 'region', 'emotional', 'seasonal'],
            'dimension_weight': 0.8,
            'dimension_name': '人群身份',
        },
        'pain_point': {
            'primary_stage': 'pain',
            'secondary_stages': ['compare'],
            'preferred_type_keys': ['cause', 'pitfall', 'rethink', 'tutorial', 'compare', 'effect_proof'],
            'dimension_weight': 0.9,
            'dimension_name': '痛点需求',
        },
        'concern': {
            'primary_stage': 'hesitation',
            'secondary_stages': ['pain'],
            'preferred_type_keys': ['pain_point', 'decision_encourage', 'price', 'cause', 'pitfall'],
            'dimension_weight': 0.85,
            'dimension_name': '购买顾虑',
        },
        'scenario': {
            'primary_stage': 'vision',
            'secondary_stages': ['compare'],
            'preferred_type_keys': ['skill', 'seasonal', 'festival', 'scene', 'compare'],
            'dimension_weight': 0.75,
            'dimension_name': '使用场景',
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
        4. 本地分配 type_key（五段式阶段配比）
        5. 兜底补全

        注意：GEO 模式在内容生成时由 content_generator.match_geo_mode() 动态确定
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
            logger.info("[TopicLibraryGenerator] 阶段: %s | 五段式: %s",
                        stage, stage_config['description'])

            # ── 4.1 画像维度分析 → 调整五段式配比 ───────────
            portrait_dimensions = self._analyze_portrait_dimensions(portrait_data)
            if portrait_dimensions:
                stage_config = self._adjust_stage_ratio_by_portrait(
                    portrait_data, portrait_dimensions, stage_config, topic_count
                )
                logger.info("[TopicLibraryGenerator] 画像维度: %s | 调整后五段式: %s",
                           portrait_dimensions, stage_config.get('_adjusted_description', ''))

            # ── 5. 构建上下文 ───────────────────────────
            import datetime as _dt
            with open('/Volumes/增元/项目/douyin/.cursor/debug-f05487.log', 'a') as _lf:
                import json as _json
                _lf.write(_json.dumps({
                    'sessionId': 'f05487', 'id': f'pre_ctx_{_dt.datetime.now().strftime("%H%M%S%f")}',
                    'timestamp': _dt.datetime.now().timestamp() * 1000,
                    'location': 'topic_library_generator.py:generate',
                    'message': '传入_build_context的keyword_library结构',
                    'data': {
                        'kl_keys': list(keyword_library.keys()) if isinstance(keyword_library, dict) else type(keyword_library).__name__,
                        'categories_count': len(keyword_library.get('categories', [])) if isinstance(keyword_library, dict) else -1,
                    },
                    'hypothesisId': 'H4'
                }) + '\n')
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
            # 排除非五段式阶段字段
            result_stage_ratio = {
                k: v for k, v in stage_config.items()
                if k in ('audience', 'pain', 'compare', 'vision', 'hesitation')
            }
            result = {
                'topics': filled_topics,
                'by_type': self._count_by_type(filled_topics),
                'by_stage': self._count_by_stage(filled_topics),
                'priorities': self._count_by_priority(filled_topics),
                'stage': stage,
                'stage_ratio': result_stage_ratio,
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

        只生成选题核心字段（title、keywords、recommended_reason、type_key），
        其他字段由本地计算或内容生成时动态确定。
        """
        return f"""你是一位抖音爆款选题策划专家。

请为以下业务生成{topic_count}个选题，严格按五段式内容框架分配：

=== 五段式内容框架（从左到右推进用户决策）===
① 受众锁定（20%）：让人立刻判断"这说的是不是我"
  关键词：人群锁定类、场景细分类、地域精准类
  核心问题：你是这种人吗？
② 痛点放大（40%）：让人意识到"现在的做法有多糟糕"
  关键词：原因分析类、避坑指南类、认知颠覆类、知识教程类
  核心问题：你正在经历这些问题
③ 方案对比（25%）：突出"我的方案为什么更好"
  关键词：对比选型类、效果验证类、上游科普类、行业关联系列类
  核心问题：选我们能解决这些问题
④ 愿景勾画（10%）：让人期待"用之后会变多好"
  关键词：实操技巧类、季节营销类、节日营销类、情感故事类
  核心问题：用完之后你会发现...
⑤ 顾虑消除（5%）：打消"用了之后有问题怎么办"
  关键词：决策安心类、行情价格类、工具耗材类、痛点放大类
  核心问题：后期遇到问题怎么办

=== 账号阶段：{stage} ===
起号阶段：重受众锁定+痛点放大，种草为主
成长阶段：平衡五段式，逐步增加方案对比和顾虑消除
成熟阶段：重方案对比+顾虑消除，转化为主

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

=== 关键词库（选题必须命中这些关键词，按类别分组）
【类别名称】关键词1, 关键词2, 关键词3...
{context.get('关键词库', '（无关键词库数据）')}

=== 选题格式禁令（严格遵守）===
1. ❌ "XX的正确认知" → ✅ "XX怎么办？"
2. ❌ "XX的底层逻辑" → ✅ "什么是XX？"
3. ❌ "XX的真相" → ✅ "别再误解了！XX"
4. ❌ "XX全面解析" → ✅ "XX清单！3个要点"
5. ❌ "春季XX/冬季XX" → ✅ "高考出分前家长要做什么"
6. ❌ "XX原料/供应链"（非制造业禁止）

【关键词命中要求】
- 每个选题的 title 必须包含至少 1 个关键词库的词
- 每个选题的 keywords 字段必须包含 2-5 个关键词库的词
- 优先使用痛点需求/用户问题类别的词，其次使用场景类别的词

=== LLM 输出字段（只生成这4个核心字段）===
1. **title**：选题标题（必须包含业务关键词，必须是用户真实搜索的问题）
2. **keywords**：关键词列表（必须从关键词库中选择 2-5 个）
3. **recommended_reason**：推荐理由（为什么这个选题好）
4. **type_key**：选题类型键（从以下列表选择1个）：
   - identity：人群锁定类（你是这种人吗？）
   - scene：场景细分（场景+业务）
   - region：地域精准（地域+业务）
   - cause：原因分析类（为什么XX）
   - pitfall：避坑指南类（XX最常见的坑）
   - rethink：认知颠覆类（你以为对的，其实是错的）
   - tutorial：知识教程类（XX的正确做法）
   - compare：方案对比类（XX选A还是B）
   - effect_proof：效果验证类（XX效果展示）
   - upstream：上游科普类（XX原材料/原理）
   - industry：行业关联类（XX行业内幕）
   - skill：实操技巧类（XX具体怎么做）
   - seasonal：季节营销类（当季XX要注意）
   - festival：节日营销类（节假日XX攻略）
   - emotional：情感故事类（XX的真实故事）
   - pain_point：痛点放大类（XX的痛苦经历）
   - decision_encourage：决策安心类（现在做来得及吗）
   - price：行情价格类（XX多少钱）
   - tools：工具耗材类（XX需要什么工具）

=== JSON输出格式（严格JSON，不要markdown代码块）===
```json
[
  {{
    "title": "选题标题（必须包含业务关键词）",
    "keywords": ["关键词1", "关键词2"],
    "recommended_reason": "推荐理由",
    "type_key": "cause"
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

        # 结构化关键词库（按类别分组，供 prompt 使用）
        keywords_text = ''
        if keyword_library:
            kw_parts = []
            for cat in keyword_library.get('categories', []):
                if isinstance(cat, dict):
                    cat_name = cat.get('category_name', '') or cat.get('category', '') or cat.get('name', '')
                    kws = cat.get('keywords', [])
                    if isinstance(kws, list) and kws:
                        # 每类取前 8 个，避免 prompt 过长
                        kw_str = ', '.join(kws[:8])
                        kw_parts.append(f"【{cat_name}】{kw_str}")
            if kw_parts:
                keywords_text = '\n'.join(kw_parts)
            # >>> DEBUG: log what arrived
            import datetime as _dt
            with open('/Volumes/增元/项目/douyin/.cursor/debug-f05487.log', 'a') as _lf:
                import json as _json
                _lf.write(_json.dumps({
                    'sessionId': 'f05487', 'id': f'build_ctx_{_dt.datetime.now().strftime("%H%M%S%f")}',
                    'timestamp': _dt.datetime.now().timestamp() * 1000,
                    'location': 'topic_library_generator.py:_build_context',
                    'message': '_build_context收到的keyword_library.categories数量',
                    'data': {
                        'kl_keys': list(keyword_library.keys()),
                        'categories_count': len(keyword_library.get('categories', [])),
                        'cat_names': [c.get('category_name','') or c.get('category','') or c.get('name','') for c in keyword_library.get('categories',[])],
                        'keywords_text_preview': keywords_text[:200] if keywords_text else '(空)',
                    },
                    'hypothesisId': 'H3'
                }) + '\n')

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

    def _adjust_stage_ratio_by_portrait(
        self,
        portrait_data: Dict,
        portrait_dimensions: Dict[str, float],
        stage_config: Dict,
        topic_count: int,
    ) -> Dict:
        """
        根据画像维度调整五段式阶段配比

        策略：
        1. 分析画像的主要维度特征
        2. 根据维度强度调整五段式比例
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
        dim_config = self.DIMENSION_STAGE_PRIORITY.get(dim_key, {})

        if not dim_config:
            return adjusted

        # 获取当前阶段的基础配比
        stage_ratio = {
            k: v for k, v in adjusted.items()
            if k not in ('description', '_adjusted_description')
        }

        # 根据维度强度调整
        adjustment_factor = dim_score * 0.3  # 最大调整30%

        if dim_key == 'pain_point':
            # 痛点维度：增加痛点放大阶段
            stage_ratio['pain'] = min(0.60, stage_ratio.get('pain', 0.25) + adjustment_factor)
            stage_ratio['audience'] = max(0.10, stage_ratio.get('audience', 0.15) - adjustment_factor * 0.5)
            stage_ratio['compare'] = max(0.20, stage_ratio.get('compare', 0.30) - adjustment_factor * 0.5)

        elif dim_key == 'concern':
            # 顾忌维度：增加顾虑消除阶段
            stage_ratio['hesitation'] = min(0.50, stage_ratio.get('hesitation', 0.15) + adjustment_factor)
            stage_ratio['audience'] = max(0.10, stage_ratio.get('audience', 0.15) - adjustment_factor * 0.3)
            stage_ratio['vision'] = stage_ratio.get('vision', 0.15)

        elif dim_key == 'identity':
            # 人群维度：增加受众锁定阶段
            stage_ratio['audience'] = min(0.40, stage_ratio.get('audience', 0.15) + adjustment_factor)
            stage_ratio['pain'] = max(0.20, stage_ratio.get('pain', 0.25) - adjustment_factor * 0.3)
            stage_ratio['hesitation'] = stage_ratio.get('hesitation', 0.15)

        elif dim_key == 'scenario':
            # 场景维度：增加愿景勾画阶段
            stage_ratio['vision'] = min(0.40, stage_ratio.get('vision', 0.15) + adjustment_factor)
            stage_ratio['audience'] = max(0.10, stage_ratio.get('audience', 0.15) - adjustment_factor * 0.5)
            stage_ratio['compare'] = stage_ratio.get('compare', 0.30)

        # 归一化，确保总和为1
        total = sum(stage_ratio.values())
        if total > 0 and abs(total - 1.0) > 0.01:
            for k in stage_ratio:
                stage_ratio[k] = stage_ratio[k] / total

        # 更新配置
        adjusted.update(stage_ratio)
        adjusted['_adjusted_description'] = (
            f"画像维度调整({dim_config['dimension_name']}={dim_score:.1f}): "
            f"受众={stage_ratio.get('audience', 0):.0%}, "
            f"痛点={stage_ratio.get('pain', 0):.0%}, "
            f"对比={stage_ratio.get('compare', 0):.0%}, "
            f"愿景={stage_ratio.get('vision', 0):.0%}, "
            f"顾虑={stage_ratio.get('hesitation', 0):.0%}"
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
            key=lambda x: self.DIMENSION_STAGE_PRIORITY.get(x[0], {}).get('dimension_weight', 0) * x[1],
            reverse=True
        )

        for dim_key, score in sorted_dims:
            dim_config = self.DIMENSION_STAGE_PRIORITY.get(dim_key, {})
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
        """
        本地按五段式阶段比例分配 type_key。

        核心原则：LLM 返回的 type_key 优先保留，本地只做：
        1. 补全 LLM 返回空 type_key 的选题
        2. 校验 type_key 合法性（无效则本地分配）
        3. 补全 type_name / priority / stage_key 等衍生字段
        4. 按五段式阶段配比补充分配
        """
        if not topics:
            return topics

        stage_keys = {
            'audience':   [t['key'] for t in self.TOPIC_TYPES if t['stage'] == 'audience'],
            'pain':       [t['key'] for t in self.TOPIC_TYPES if t['stage'] == 'pain'],
            'compare':    [t['key'] for t in self.TOPIC_TYPES if t['stage'] == 'compare'],
            'vision':     [t['key'] for t in self.TOPIC_TYPES if t['stage'] == 'vision'],
            'hesitation': [t['key'] for t in self.TOPIC_TYPES if t['stage'] == 'hesitation'],
        }

        # 获取调整后的五段式配比（排除非阶段字段）
        stage_ratio = {
            k: v for k, v in stage_config.items()
            if k in stage_keys
        }

        stage_counts = {}
        for stage_name, ratio in stage_ratio.items():
            count = int(round(ratio * topic_count))
            stage_counts[stage_name] = count

        total_assigned = sum(stage_counts.values())
        if total_assigned != topic_count:
            stage_counts['audience'] = stage_counts.get('audience', 0) + (topic_count - total_assigned)

        result = []
        stage_assignments = {stage: 0 for stage in stage_counts}
        used_keys = set()

        # 获取画像维度优先的type_key
        preferred_keys_by_dim = []
        if portrait_dimensions:
            preferred_keys_by_dim = self._get_preferred_type_keys_by_dimension(portrait_dimensions)

        for topic in topics:
            if len(result) >= topic_count:
                break

            # ── ① 优先保留 LLM 返回的有效 type_key ──
            llm_type_key = topic.get('type_key', '')
            if llm_type_key and llm_type_key in self.TYPE_KEY_MAP:
                # LLM 返回了有效 type_key，保留
                type_info = self.TYPE_KEY_MAP[llm_type_key]
            else:
                # ── ② LLM type_key 无效，本地按阶段配比分配 ──
                assigned = False
                for stage_name, count in stage_counts.items():
                    if stage_assignments[stage_name] >= count:
                        continue

                    available_keys = [k for k in stage_keys[stage_name] if k not in used_keys]

                    if preferred_keys_by_dim:
                        dim_preferred = [k for k in preferred_keys_by_dim if k in available_keys]
                        if dim_preferred:
                            available_keys = dim_preferred

                    if not available_keys:
                        available_keys = stage_keys[stage_name]

                    chosen_key = random.choice(available_keys)
                    type_info = self.TYPE_KEY_MAP[chosen_key]
                    topic['type_key'] = chosen_key
                    assigned = True
                    break

                if not assigned:
                    chosen_key = random.choice(stage_keys['audience'])
                    type_info = self.TYPE_KEY_MAP[chosen_key]
                    topic['type_key'] = chosen_key

            # ── ③ 补全衍生字段 ──
            topic['type_name'] = type_info['name']
            topic['priority'] = type_info['priority']
            topic['stage_key'] = type_info['stage']
            topic['stage_name'] = self.STAGE_NAMES.get(type_info['stage'], type_info['stage'])
            topic['content_direction'] = type_info['direction']
            topic['source'] = self._get_source_by_stage(topic['type_key'])
            topic['id'] = str(uuid.uuid4())
            topic['generation_count'] = 0
            topic['created_at'] = datetime.utcnow().isoformat()
            topic['title'] = self._clean_title(topic.get('title', ''))

            result.append(topic)
            # 更新阶段计数（仅当本地分配时计入）
            stage = topic.get('stage_key')
            if stage in stage_assignments:
                stage_assignments[stage] += 1
            used_keys.add(topic['type_key'])

        return result

    def _get_source_by_stage(self, type_key: str) -> str:
        """根据 type_key 返回五段式阶段说明"""
        stage_map = {
            'identity':            '受众锁定',
            'scene':               '受众锁定',
            'region':              '受众锁定',
            'cause':              '痛点放大',
            'pitfall':            '痛点放大',
            'rethink':            '痛点放大',
            'tutorial':           '痛点放大',
            'compare':            '方案对比',
            'effect_proof':       '方案对比',
            'upstream':           '方案对比',
            'industry':           '方案对比',
            'skill':              '愿景勾画',
            'seasonal':           '愿景勾画',
            'festival':           '愿景勾画',
            'emotional':          '愿景勾画',
            'pain_point':         '顾虑消除',
            'decision_encourage': '顾虑消除',
            'price':              '顾虑消除',
            'tools':              '顾虑消除',
        }
        return stage_map.get(type_key, '选题推荐')

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
        - GEO 模式 → 内容生成时由 content_generator.match_geo_mode() 动态决定
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

        注意：GEO 模式在内容生成时动态确定，不在此处处理
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

        # 兜底选题类型（按五段式阶段均匀分配）
        fallback_types = [
            # 受众锁定
            ('identity',    'audience'),
            # 痛点放大
            ('cause',       'pain'),
            ('pitfall',     'pain'),
            ('tutorial',    'pain'),
            ('rethink',     'pain'),
            # 方案对比
            ('compare',     'compare'),
            ('effect_proof', 'compare'),
            # 愿景勾画
            ('skill',       'vision'),
            ('seasonal',    'vision'),
            ('festival',    'vision'),
            # 顾虑消除
            ('pain_point',  'hesitation'),
            ('decision_encourage', 'hesitation'),
            ('price',       'hesitation'),
            ('tools',       'hesitation'),
        ]

        # 按 type_key 生成针对性兜底标题模板
        for type_key, stage in fallback_types:
            if len(topics) >= topic_count:
                break
            if type_key in existing_keys:
                continue

            type_info = self.TYPE_KEY_MAP.get(type_key, {})
            if not type_info:
                continue

            title = self._generate_fallback_title(type_key, identity, pain_point, concern, business_desc)

            topics.append({
                'id': str(uuid.uuid4()),
                'title': self._clean_title(title),
                'type_key': type_key,
                'type_name': type_info.get('name', type_key),
                'priority': type_info.get('priority', 'P2'),
                'stage_key': type_info.get('stage', stage),
                'stage_name': self.STAGE_NAMES.get(type_info.get('stage', stage), stage),
                'content_direction': type_info.get('direction', '种草型'),
                'source': self._get_source_by_stage(type_key),
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
        # 确保是字典列表
        topics = [t for t in topics if isinstance(t, dict)]

        # 旧数据兼容：base → stage_key 兜底
        for t in topics:
            if not t.get('stage_key') and t.get('base'):
                t['stage_key'] = self._BASE_TO_STAGE_MAP.get(t.get('base', ''), 'audience')

        if keyword_hint and keyword_hint.strip():
            keyword = keyword_hint.strip().lower()
            topics = [
                t for t in topics
                if keyword in (t.get('title', '') + ' '.join(t.get('keywords', []))).lower()
            ]

        if topic_type:
            topics = [t for t in topics if t.get('type_key') == topic_type]

        # 按优先级排序（P0优先）
        priority_order = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}

        def sort_key(t):
            priority = priority_order.get(t.get('priority', 'P2'), 2)
            return priority

        topics = sorted(topics, key=sort_key)
        random.shuffle(topics)
        return topics[:count]

    # ===========================================================================
    # 工具方法
    # ===========================================================================

    # 旧数据 base → stage_key 兜底映射（用于兼容旧选题数据）
    _BASE_TO_STAGE_MAP = {
        '前置观望种草盘':     'audience',
        '刚需痛点盘':         'hesitation',
        '使用配套搜后种草盘':  'vision',
    }

    def _generate_fallback_title(
        self,
        type_key: str,
        identity: str,
        pain_point: str,
        concern: str,
        business_desc: str,
    ) -> str:
        """
        根据 type_key 生成针对性兜底标题，替代通用的'XX怎么办'模板。

        每个 type_key 对应一个真实搜索场景化的标题结构。
        """
        # 核心词优先级：痛点 > 身份 > 业务描述
        core = pain_point or identity or business_desc or '相关内容'

        # 按 type_key 生成针对性标题
        title_templates = {
            # 受众锁定类
            'identity':   f'{core}人群有你吗？',
            'scene':      f'{core}场景下怎么选？',
            'region':     f'本地{core}服务哪里好？',

            # 痛点放大类
            'cause':      f'为什么{core}总出问题？',
            'pitfall':    f'{core}最常见的坑有哪些？',
            'rethink':    f'{core}的误区，你中了几个？',
            'tutorial':   f'{core}的正确做法是什么？',

            # 方案对比类
            'compare':    f'{core}选哪个最靠谱？',
            'effect_proof': f'用了{core}效果怎么样？',
            'upstream':   f'{core}的原理你了解多少？',
            'industry':   f'{core}行业内幕揭秘',

            # 愿景勾画类
            'skill':      f'{core}技巧，学到就是赚到',
            'seasonal':   f'季节变化，{core}要注意什么？',
            'festival':   f'节假日{core}攻略，建议收藏',
            'emotional':  f'真实经历：我是怎么搞定{core}的',

            # 顾虑消除类
            'pain_point': f'{core}的顾虑，一次说清楚',
            'decision_encourage': f'{core}现在做来得及吗？',
            'price':      f'{core}到底要花多少钱？',
            'tools':      f'{core}需要准备哪些工具？',
        }

        return title_templates.get(type_key, f'{core}相关问题解答')

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

    def _count_by_stage(self, topics: List[Dict]) -> Dict:
        counts = {'audience': 0, 'pain': 0, 'compare': 0, 'vision': 0, 'hesitation': 0}
        for t in topics:
            if not isinstance(t, dict):
                continue
            key = t.get('stage_key', '')
            if key in counts:
                counts[key] += 1
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
            type_key = list(self.TYPE_KEY_MAP.keys())[i % len(self.TYPE_KEY_MAP)]
            type_info = self.TYPE_KEY_MAP[type_key]
            title = '相关内容'

            topics.append({
                'id': str(uuid.uuid4()),
                'title': self._clean_title(title),
                'type_key': type_key,
                'type_name': type_info['name'],
                'priority': type_info['priority'],
                'stage_key': type_info['stage'],
                'stage_name': self.STAGE_NAMES.get(type_info['stage'], type_info['stage']),
                'content_direction': type_info['direction'],
                'source': self._get_source_by_stage(type_key),
                'keywords': [],
                'recommended_reason': '兜底选题',
                'generation_count': 0,
                'created_at': datetime.utcnow().isoformat(),
            })
        return topics

    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """估算token消耗"""
        return int((len(prompt) / 2) + (len(response) / 2))


# 全局实例
topic_library_generator = TopicLibraryGenerator()
