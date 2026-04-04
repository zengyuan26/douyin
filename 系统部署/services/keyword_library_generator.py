"""
画像专属关键词库生成服务

功能：
1. 读取模板配置，生成专属关键词库
2. 结合实时上下文（季节/节日/热点）
3. 持久化到 saved_portraits.keyword_library
4. 支持实时刷新 + 配额检查
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from models.public_models import SavedPortrait, db
from services.template_config_service import template_config_service, TemplateConfigService
from services.llm import get_llm_service

logger = logging.getLogger(__name__)


class KeywordLibraryGenerator:
    """
    关键词库生成器

    复用 geo-seo skill 中的关键词库模板逻辑：
    - 10大关键词分类
    - 蓝海词挖掘
    - 配比策略（起号期/成长期/成熟期）
    """

    def _escape_fstring(self, s: str) -> str:
        """转义字符串中的花括号，防止在 f-string 中被误解析为占位符"""
        if not isinstance(s, str):
            return ''
        return s.replace('{', '{{').replace('}', '}}')

    # 关键词分类常量（严格对应三大需求底盘 + 强制固定归类）
    # 三盘比例：前置观望搜前种草盘 50% / 刚需痛点盘 30% / 使用配套搜后种草盘 20%
    # 强制规则：对比选型/决策安心/上下游/原料/配料/工具/对比等全部固定归类，AI 禁止自由发挥
    CATEGORIES = [
        # ────────────── ① 前置观望搜前种草盘（50%）────────────────────────────
        # 【新增】对比型搜索专区：专抓前期迷茫、做对比、查原因的潜在客户
        {'name': '对比型搜索关键词', 'key': 'compare', 'base': '前置观望种草盘', 'min': 15,
         'desc': 'A与B区别/选型对比/哪种更好/划算对比/品牌对比，问题导向，不推产品<br>'
                 '<b>禁止</b>：纯业务拼接如"高考志愿填报辅导哪家好"<br>'
                 '<b>正确示例</b>："高考志愿填报机构哪家靠谱"、"一对一辅导和班课哪个好"'},
        {'name': '症状疑问关键词', 'key': 'symptom', 'base': '前置观望种草盘', 'min': 10,
         'desc': '前期症状/问题征兆疑问型词，不推产品，捕捉犹豫期客户<br>'
                 '<b>禁止</b>：纯业务拼接如"高考志愿填报辅导迷茫"<br>'
                 '<b>正确示例</b>："不知道该报哪个学校怎么办"、"家长和孩子的意见不一致怎么选"'},
        {'name': '原因分析关键词', 'key': 'cause', 'base': '前置观望种草盘', 'min': 10,
         'desc': '为什么会/原因分析/形成机理，从评论区挖认知需求<br>'
                 '<b>禁止</b>：纯业务拼接如"高考志愿填报辅导为什么"<br>'
                 '<b>正确示例</b>："为什么越到高三越焦虑"、"为什么家长比孩子还着急"'},
        {'name': '上游供应链原料选材关键词', 'key': 'upstream', 'base': '前置观望种草盘', 'min': 10,
         'desc': '选机构看什么/师资怎么辨别/课程内容怎么判断，搜前对比评估类词<br>'
                 '<b>重要</b>：服务业/教育类业务生成此类词时，必须站在用户角度：<br>'
                 '<b>禁止</b>："高考志愿填报辅导师资选材"、"志愿填报机构供应链"<br>'
                 '<b>正确示例</b>："怎么判断志愿填报老师专不专业"、"志愿填报机构怎么看评价"'},
        {'name': '行情价格关键词', 'key': 'price', 'base': '前置观望种草盘', 'min': 5,
         'desc': '收费合理吗/不同机构价格差异/值不值，预算顾虑类词<br>'
                 '<b>禁止</b>：纯业务拼接如"高考志愿填报辅导价格行情"<br>'
                 '<b>正确示例</b>："高考志愿填报收费一般多少"、"找专业机构帮忙值不值"'},
        {'name': '避坑科普关键词', 'key': 'pitfall', 'base': '前置观望种草盘', 'min': 10,
         'desc': '黑机构套路/虚假承诺/不靠谱机构特征，辟谣类词（搜前种草）<br>'
                 '<b>禁止</b>：纯业务拼接如"高考志愿填报辅导骗局"<br>'
                 '<b>正确示例</b>："高考志愿填报哪些机构不可信"、"志愿填报机构常见的坑"'
        },

        # ────────────── ② 刚需痛点盘（30%）────────────────────────────────────
        # 【强化】新增决策鼓励 + 打消顾虑专区：解决临门一脚犹豫
        {'name': '直接需求关键词', 'key': 'direct', 'base': '刚需痛点盘', 'min': 10,
         'desc': '要报/赶紧找/马上报名，直接表达购买意向的紧迫词<br>'
                 '<b>正确示例</b>："高考出分了赶紧找志愿填报"、"现在不找机构还来得及吗"'},
        {'name': '痛点关键词', 'key': 'pain_point', 'base': '刚需痛点盘', 'min': 10,
         'desc': '怎么办/来不及了/不甘心，后果焦虑型词<br>'
                 '<b>正确示例</b>："分数刚好压线怎么报"、"滑档了还能补救吗"'},
        {'name': '决策鼓励关键词', 'key': 'decision_encourage', 'base': '刚需痛点盘', 'min': 8,
         'desc': '靠谱吗/会不会坑/售后怎么样/划算吗，临门一脚打消顾虑类<br>'
                 '<b>禁止</b>：纯业务拼接如"高考志愿填报辅导靠谱吗"<br>'
                 '<b>正确示例</b>："找专业机构帮忙报志愿靠谱吗"、"志愿填报机构会不会坑人"'},
        {'name': '安心保障关键词', 'key': 'reassure', 'base': '刚需痛点盘', 'min': 7,
         'desc': '别人怎么选/真实案例/口碑评价/退款保障，强化下单信心类<br>'
                 '<b>禁止</b>：纯业务拼接如"高考志愿填报辅导真实案例"<br>'
                 '<b>正确示例</b>："报了志愿填报的家长都怎么选"、"志愿填报不满意能退钱吗"'
        },

        # ────────────── ③ 使用配套搜后种草盘（20%）────────────────────────────
        {'name': '地域关键词', 'key': 'region', 'base': '使用配套搜后种草盘', 'min': 8,
         'desc': 'XX城市志愿填报辅导/本地靠谱机构推荐，本地流量词<br>'
                 '<b>正确示例</b>："北京高考志愿填报机构推荐"、"上海靠谱的志愿填报辅导"'},
        # 【扩充】旺/淡季词 + 干货数字承诺型词 + 认知颠覆词（前置观望种草盘新增）
        {'name': '季节时间关键词', 'key': 'season', 'base': '使用配套搜后种草盘', 'min': 10,
         'desc': '出分前/出分后/填报截止前，时间节点焦虑词，搜后种草<br>'
                 '<b>禁止</b>："春季高考志愿填报辅导"、"冬季志愿填报辅导保存"<br>'
                 '<b>正确示例</b>："高三家长三月焦虑：要不要提前报志愿辅导"、"高考出分前家长能做哪些准备"'},
        {'name': '实操技巧干货关键词', 'key': 'skill', 'base': '使用配套搜后种草盘', 'min': 10,
         'desc': '平行志愿怎么填/压线生怎么报/城市vs学校谁优先，从用户具体问题出发的实操词，搜后种草<br>'
                 '<b>禁止</b>："高考志愿填报辅导技巧"、"高考志愿填报辅导5个技巧"<br>'
                 '<b>正确示例</b>："平行志愿怎么填不滑档"、"压线生怎么选学校和专业"、"城市和学校哪个优先"'
        },
        {'name': '工具耗材关键词', 'key': 'tools', 'base': '使用配套搜后种草盘', 'min': 5,
         'desc': '志愿填报辅助工具/测评量表/历年分数线App，报后辅助使用类词，搜后种草<br>'
                 '<b>注意</b>：服务业/教育类业务慎用，避免生成"工具耗材"类硬拼接词<br>'
                 '<b>正确示例</b>："高考志愿填报用哪个App"、"历年录取分数线哪里查"'},
        {'name': '行业关联关键词', 'key': 'industry', 'base': '使用配套搜后种草盘', 'min': 5,
         'desc': '强基计划/综合评价/提前批区别，志愿填报延伸知识类词，搜后种草<br>'
                 '<b>注意</b>：服务业/教育类业务慎用<br>'
                 '<b>正确示例</b>："强基计划和普通批次冲突吗"、"综合评价录取是什么"'
        },
        # 【新增】认知颠覆关键词（前置观望种草盘）
        {'name': '认知颠覆关键词', 'key': 'rethink', 'base': '前置观望种草盘', 'min': 5,
         'desc': '以为随便选就行/不找机构也来得及/分数够了不用规划，打破固有偏见的认知颠覆类词，搜前种草<br>'
                 '<b>禁止</b>："高考志愿填报辅导90%都错了"、"高考志愿填报辅导别再这样想了"<br>'
                 '<b>正确示例</b>："以为随便选就行？历年家长的血泪教训"、"不找机构孩子就输了吗"'
        },
    ]

    def __init__(self):
        self.llm = get_llm_service()

    # 内容阶段配比映射（关键词库）
    STAGE_RATIO_MAP = {
        '起号阶段': {
            'long_tail_ratio': 0.50,
            'region_ratio': 0.30,
            'core_ratio': 0.20,
            'description': '长尾词50% + 地域词30% + 大词20%',
        },
        '成长阶段': {
            'long_tail_ratio': 0.35,
            'region_ratio': 0.30,
            'core_ratio': 0.35,
            'description': '长尾词35% + 地域词30% + 大词35%',
        },
        '成熟阶段': {
            'long_tail_ratio': 0.20,
            'region_ratio': 0.20,
            'core_ratio': 0.60,
            'description': '长尾词20% + 地域词20% + 大词60%',
        },
    }

    def generate(
        self,
        portrait_data: Dict,
        business_info: Dict,
        plan_type: str = 'professional',
        use_template: bool = True,
        max_keywords: int = 200,
        portrait_id: Optional[int] = None,
        content_stage: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成关键词库（缓存优先）

        Args:
            portrait_data: 画像数据（身份/痛点/顾虑/场景）
            business_info: 业务信息
            plan_type: 套餐类型（影响配比策略）
            use_template: 是否使用模板配置（False=简单模式）
            max_keywords: 最大关键词数量
            portrait_id: 画像ID（用于缓存检查）
            content_stage: 内容阶段（起号阶段/成长阶段/成熟阶段），优先级高于 plan_type
        """
        try:
            # 缓存检查：如果画像有关键词库且未过期，直接返回
            if portrait_id:
                portrait = SavedPortrait.query.get(portrait_id)
                if portrait and not portrait.keyword_library_expired:
                    logger.info("[KeywordLibraryGenerator] 命中缓存，跳过生成 portrait_id=%s", portrait_id)
                    return {
                        'success': True,
                        'keyword_library': portrait.keyword_library,
                        'tokens_used': 0,
                        '_meta': {'from_cache': True, 'content_stage': content_stage or '成长阶段'},
                    }
                    # 读取画像的 content_stage 字段（优先使用）
                    if portrait and not content_stage:
                        content_stage = portrait.content_stage or '成长阶段'

            # 防御性检查
            if not isinstance(portrait_data, dict):
                portrait_data = {}
            if not isinstance(business_info, dict):
                business_info = {}

            # 获取实时上下文（季节/节日/热点）
            realtime = template_config_service.get_realtime_context()

            # 构建变量上下文
            context = self._build_context(portrait_data, business_info, realtime)

            # 获取阶段配比
            stage = content_stage or '成长阶段'
            stage_config = self.STAGE_RATIO_MAP.get(stage, self.STAGE_RATIO_MAP['成长阶段'])

            # 调试日志
            logger.info("[KeywordLibraryGenerator] 业务信息: business_description=%s, industry=%s",
                business_info.get('business_description', ''), business_info.get('industry', ''))
            logger.info("[KeywordLibraryGenerator] 内容阶段: %s，配比: %s", stage, stage_config['description'])

            # 直接使用默认提示词，不使用数据库模板（模板包含示例数据会干扰生成）
            prompt = self._build_default_prompt(context, realtime, max_keywords, stage, stage_config)

            # 调用 LLM
            system_msg = (
                "【强制要求】你必须严格按照用户提供的业务描述和画像信息生成关键词！\n"
                "禁止添加任何未提供的信息！禁止编造产品名称！\n"
                "\n"
                "你是一位抖音SEO关键词专家，精通本地商家获客关键词挖掘。\n"
                "必须严格按照JSON格式输出，关键词必须符合抖音搜索习惯。\n"
                "关键词必须全部来源于用户提供的业务描述，不得包含任何其他产品。\n"
                "\n"
                "【绝对禁止的关键词格式】（违反将导致输出无效）\n"
                '1. 禁止"业务描述开头拼接词" → 直接写用户会搜的词\n'
                '   禁止："高考志愿填报辅导价格行情"\n'
                '   正确："高考志愿填报收费一般多少"\n'
                '2. 禁止"XX工具耗材/原材料" → 除非业务真是制造业\n'
                '3. 禁止"春季XX/冬季XX"拼接 → 改为具体时间节点的用户问题\n'
                '4. 禁止"XX的原料/供应链" → 除非业务真是制造业\n'
                '5. 禁止"XX90%都错了" → 改为具体偏见描述\n'
                "\n"
                "【关键词生成核心原则】\n"
                "用户搜索的是自己的问题，不是业务介绍\n"
                "把业务关键词转化为用户真实问题\n"
            )
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat(messages)

            # 解析结果
            result = self._parse_response(response, realtime)

            return {
                'success': True,
                'keyword_library': result,
                'tokens_used': self._estimate_tokens(prompt, response),
                '_meta': {
                    'plan_type': plan_type,
                    'content_stage': stage,
                    'realtime': realtime,
                    'used_template': use_template,
                }
            }

        except Exception as e:
            error_str = str(e)
            if len(error_str) > 300:
                error_str = error_str[:300] + '...'
            logger.error("[KeywordLibraryGenerator] Error: " + error_str)
            return {'success': False, 'error': error_str}

    def save_to_portrait(
        self,
        portrait_id: int,
        keyword_library: Dict,
        user_id: int,
        plan_type: str = 'professional',
    ) -> bool:
        """
        将关键词库保存到画像记录

        Args:
            portrait_id: 画像ID
            keyword_library: 关键词库数据
            user_id: 用户ID
            plan_type: 套餐类型（决定过期时间）

        Returns:
            是否保存成功
        """
        portrait = SavedPortrait.query.get(portrait_id)
        if not portrait:
            return False

        # 计算过期时间（根据套餐）
        ttl_hours = {
            'basic': 24,
            'professional': 168,  # 7天
            'enterprise': 720,    # 30天
        }.get(plan_type, 24)

        portrait.keyword_library = keyword_library
        portrait.keyword_updated_at = datetime.utcnow()
        portrait.keyword_update_count = (portrait.keyword_update_count or 0) + 1
        portrait.keyword_cache_expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

        db.session.commit()
        return True

    def get_from_portrait(self, portrait_id: int) -> Optional[Dict]:
        """
        从画像获取已保存的关键词库

        Returns:
            关键词库数据 或 None
        """
        portrait = SavedPortrait.query.get(portrait_id)
        if not portrait:
            return None

        # 检查过期
        if portrait.keyword_library_expired:
            return None

        return portrait.keyword_library

    def _build_context(
        self,
        portrait_data: Dict,
        business_info: Dict,
        realtime: Dict,
    ) -> Dict:
        """构建模板变量上下文"""
        # 防御性检查
        if not isinstance(portrait_data, dict):
            portrait_data = {}
        if not isinstance(business_info, dict):
            business_info = {}
        if not isinstance(realtime, dict):
            realtime = {}

        # 支持多种画像格式
        # 新格式（超级定位）：portrait_summary, user_perspective, buyer_perspective, identity_tags
        # 旧格式：identity, pain_point, concern, scenario
        identity_tags = portrait_data.get('identity_tags', {})
        user_persp = portrait_data.get('user_perspective', {})
        buyer_persp = portrait_data.get('buyer_perspective', {})

        # 目标客户身份
        identity = portrait_data.get('identity', portrait_data.get('用户身份', ''))
        if not identity:
            identity = identity_tags.get('user', '') or identity_tags.get('buyer', '')

        # 核心痛点
        pain_point = portrait_data.get('pain_point', portrait_data.get('核心痛点', ''))
        if not pain_point:
            pain_point = user_persp.get('problem', '')
            if not pain_point:
                # 从 portrait_summary 提取
                summary = portrait_data.get('portrait_summary', '')
                if summary and '，' in summary:
                    pain_point = summary.split('，')[0]

        # 核心顾虑
        concern = portrait_data.get('concern', portrait_data.get('核心顾虑', ''))
        if not concern:
            concern = buyer_persp.get('obstacles', '')
            if not concern:
                concern = buyer_persp.get('psychology', '')

        # 使用场景
        scenario = portrait_data.get('scenario', portrait_data.get('场景', ''))
        if not scenario:
            scenario = user_persp.get('current_state', '')

        # 完整画像摘要 + 用户视角（注入 prompt 强化关键词与画像绑定）
        portrait_summary = portrait_data.get('portrait_summary', '')
        user_perspective_text = portrait_data.get('user_perspective', {}).get('problem', '')
        buyer_perspective_text = portrait_data.get('buyer_perspective', {}).get('obstacles', '') or \
                                 portrait_data.get('buyer_perspective', {}).get('psychology', '')
        user_current_state = user_persp.get('current_state', '')

        # 优先使用表单输入的业务描述和行业（business_info）
        # 这些是用户当前输入的最新数据
        business_desc = business_info.get('business_description', '')
        industry = business_info.get('industry', '')
        
        # 产品信息：如果表单提供了业务描述，忽略画像数据中的产品信息
        products = business_info.get('products', [])
        if not products and business_desc:
            # 从业务描述提取产品
            products = [business_desc]
        
        # 地域信息
        region = business_info.get('region', '')
        target_customer = business_info.get('target_customer', '')

        # 核心业务（用于季节/认知颠覆/技巧关键词模板变量）
        core_business = business_desc or (', '.join(products) if isinstance(products, list) and products else str(products or ''))

        # 季节时间（旺季/淡季）
        current_month = realtime.get('月份', 4)
        # 根据月份判断淡旺季（可按业务特性调整，这里默认）
        if current_month in [1, 2, 12]:
            旺季时间 = '冬季'
            淡季时间 = '夏季'
        elif current_month in [3, 4, 5]:
            旺季时间 = '春季'
            淡季时间 = '冬季'
        elif current_month in [6, 7, 8]:
            旺季时间 = '夏季'
            淡季时间 = '春季'
        else:  # 9,10,11
            旺季时间 = '秋季'
            淡季时间 = '夏季'

        context = {
            # 画像信息（支持新旧格式）
            '目标客户身份': self._escape_fstring(identity),
            '核心痛点': self._escape_fstring(pain_point),
            '核心顾虑': self._escape_fstring(concern),
            '使用场景': self._escape_fstring(scenario),
            # 完整画像摘要 + 用户视角（强化关键词与画像绑定）
            'portrait_summary': self._escape_fstring(portrait_summary),
            '用户视角描述': self._escape_fstring(user_perspective_text),
            '买单方视角描述': self._escape_fstring(buyer_perspective_text),
            '用户当前状态': self._escape_fstring(user_current_state),

            # 业务信息（优先使用表单输入 business_info）
            '业务描述': self._escape_fstring(business_desc),
            '行业': self._escape_fstring(industry),
            '产品': self._escape_fstring(', '.join(products) if isinstance(products, list) and products else str(products or '')),
            '地域': self._escape_fstring(region),
            '目标客户': self._escape_fstring(target_customer),

            # 实时上下文
            '当前季节': self._escape_fstring(realtime.get('当前季节', '')),
            '月份名称': self._escape_fstring(realtime.get('月份名称', '')),
            '季节消费特点': self._escape_fstring(realtime.get('季节消费特点', '')),
            '当前节日': self._escape_fstring(realtime.get('当前节日', '无')),
            '当前节气': self._escape_fstring(realtime.get('当前节气', '无')),

            # 模板变量（用于 prompt 中的占位符替换）
            '旺季时间': 旺季时间,
            '淡季时间': 淡季时间,
            '核心业务': self._escape_fstring(core_business),
        }
        return context

    def _build_default_prompt(
        self,
        context: Dict,
        realtime: Dict,
        max_keywords: int,
        content_stage: str = '成长阶段',
        stage_config: Dict = None,
    ) -> str:
        """构建默认提示词（当模板不存在时使用）

        Args:
            content_stage: 内容阶段（起号阶段/成长阶段/成熟阶段）
            stage_config: 阶段配比配置
        """
        if stage_config is None:
            stage_config = self.STAGE_RATIO_MAP.get(content_stage, self.STAGE_RATIO_MAP['成长阶段'])
        stage_desc = stage_config['description']

        category_rules = '\n'.join([
            f"{i+1}. **{c['name']}**（底盘:{c['base']}，≥{c['min']}个）：{c['desc']}"
            for i, c in enumerate(self.CATEGORIES)
        ])

        return f"""你是一位抖音SEO关键词专家。请为以下业务生成关键词库，严格遵循三大需求底盘结构，全链路执行：前期对比种草→中期安心转化→后期留存种草。

=== 三大需求底盘（固定比例，禁止 AI 自由发挥归类）===
① **前置观望种草盘（50%）**：对比型搜索/症状疑问/原因分析/上游供应链原料选材/行情价格/避坑科普/**认知颠覆**，问题导向，专抓前期迷茫、做对比、查原因的潜在客户，不推产品
② **刚需痛点盘（30%）**：直接需求/痛点/决策鼓励/安心保障，临门一脚解决下单犹豫，强化转化
③ **使用配套搜后种草盘（20%）**：地域/季节时间（旺季词+淡季词）/实操技巧干货（技巧/方法/秘方/数字型/承诺型）/**工具耗材**/行业关联，使用后实操留存种草
**强制规则：所有关键词必须严格从上述分类中提取，禁止临时补充种草内容。对比选型/决策安心/上下游/原料/配料/工具/对比等全部固定归类，旺/淡季词、干货数字承诺型词、认知颠覆词已固定归类，AI 禁止自行新增分类或自由归类**

## 业务信息
- 行业：{context['行业']}
- 业务描述：{context['业务描述']}
- 产品：{context['产品']}
- 地域：{context['地域']}
- 目标客户：{context['目标客户']}

## 目标用户画像
- 用户身份：{context['目标客户身份']}
- 核心痛点：{context['核心痛点']}
- 核心顾虑：{context['核心顾虑']}
- 使用场景：{context['使用场景']}

## 画像视角约束（所有关键词必须绑定此画像，强制执行）
- **画像摘要**：{context['portrait_summary'] or '（无）'}
- **用户视角（这个用户遇到了什么问题）**：{context['用户视角描述'] or '（无）'}
- **买单方视角（出钱的人担心什么）**：{context['买单方视角描述'] or '（无）'}
- **用户当前状态**：{context['用户当前状态'] or '（无）'}

**【强制约束】**：
1. 所有关键词必须围绕上述画像用户的真实搜索意图生成
2. 关键词的主语/第一视角必须是画像用户自己，不是泛化的"用户"或"客户"
3. 举例：如果画像是"信息不对称家长"，关键词应从"家长"的视角出发：
   - 家长搜："高考志愿填报机构哪家靠谱"
   - 不是："高考志愿填报辅导的服务内容"
4. 不同画像的同一业务，关键词主语和搜索角度必须不同

## 关键词格式禁令（强制执行，违反将导致输出无效）
**绝对禁止以下关键词格式：**
1. ❌ "高考志愿填报辅导XXX"（业务描述开头拼接词）
   - 禁止："高考志愿填报辅导价格行情"、"高考志愿填报辅导服务流程"
   - 正确：直接写用户会搜的词："高考志愿填报收费一般多少"、"机构服务流程是什么"
2. ❌ "XX工具耗材"、"XX原材料"
   - 禁止："志愿填报工具耗材"、"高考辅导原材料"
   - 正确："志愿填报用什么App"、"历年分数线哪里查"
3. ❌ "春季XX"、"冬季XX"时间拼接
   - 禁止："春季高考志愿填报辅导优惠"、"冬季志愿填报辅导保存"
   - 正确："高三家长三月焦虑"、"高考出分前家长做什么"
4. ❌ "XX的原料"、"XX的供应链"
   - 禁止："志愿填报机构供应链管理"、"辅导班原料鉴别"
   - 正确："怎么判断志愿填报老师专业度"、"机构资质怎么查"
5. ❌ "XX90%都错了"、"XX别再这样想了"
   - 禁止："高考志愿填报辅导90%都错了"
   - 正确："以为随便选就行？血泪教训"、"这些误区害了多少人"

## 实时上下文
- 当前季节：{context['当前季节']}（{context['月份名称']}）
- 季节消费特点：{context['季节消费特点']}
- 当前节日：{context['当前节日']}
- 当前节气：{context['当前节气']}

## 关键词分类要求（严格对应三盘，各底盘内容方向已标注，强制归类）

{category_rules}

## 关键词正确生成方式（必须站在用户视角）
- 用户不是搜索"业务介绍"，而是搜索"自己的问题"
- 把业务关键词转化为用户真实问题
- 例如：不是"高考志愿填报辅导价格"，而是"志愿填报收费一般多少"
- 例如：不是"高考志愿填报辅导技巧"，而是"平行志愿怎么填不滑档"

## 配比策略（根据内容阶段自动联动，当前生效配置）
- 当前阶段：**{content_stage}**（{stage_desc}）
- 起号期：长尾词50% + 地域词30% + 大词20%
- 成长期：长尾词35% + 地域词30% + 大词35%
- 成熟期：长尾词20% + 地域词20% + 大词60%
- **AI 必须严格按照当前阶段的比例生成关键词库**

## 输出格式要求
必须输出标准的JSON格式，包含以下字段：
- categories: 关键词分类数组，每个分类包含 name, key, base, count, keywords
- blue_ocean: 蓝海长尾词数组
- ratio_strategy: 配比策略对象（stage/long_tail_ratio/region_ratio/core_ratio）
**注意：输出中不包含 hot_keywords（已移除近期热点关键词）**

## 重要提醒
1. 必须使用真实的中文关键词，不要使用任何占位符如 {{变量名}}
2. 关键词必须与上述业务信息紧密相关
3. 关键词数量不少于100个
4. 输出必须是可直接解析的标准JSON格式
5. **所有关键词必须严格归入上述分类，不得新增分类或自由归类**
6. **所有关键词必须站在用户视角，而非业务视角**

请生成JSON格式的关键词库："""

    def _parse_response(self, response: str, realtime: Dict) -> Dict:
        """解析 LLM 返回"""
        import re
        import json
        try:
            # 预处理：去除 markdown 代码块
            clean_response = response.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            elif clean_response.startswith('```'):
                clean_response = clean_response[3:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()
            
            result = None
            parse_method = ''
            
            # 方法1：直接解析
            try:
                result = json.loads(clean_response)
                if result:
                    result = self._convert_to_standard_format(result)
                    parse_method = '方法1'
            except json.JSONDecodeError:
                pass
            
            # 方法2：找到第一个完整的 JSON 对象（而非贪婪匹配到最后一个 }）
            if result is None:
                try:
                    start = clean_response.find('{')
                    if start == -1:
                        raise ValueError("No JSON object found")
                    end = len(clean_response)
                    for try_end in range(end, start, -1):
                        candidate = clean_response[start:try_end]
                        candidate = candidate.replace('{{', '{').replace('}}', '}')
                        try:
                            parsed = json.loads(candidate)
                            if parsed:
                                result = self._convert_to_standard_format(parsed)
                                parse_method = '方法2'
                                break
                        except json.JSONDecodeError:
                            continue
                except Exception as e:
                    logger.debug("[KeywordLibraryGenerator] 方法2异常: " + str(e))
            
            # 方法3：修复常见 JSON 错误后重试
            if result is None:
                fixed = self._fix_json_errors(clean_response)
                if fixed:
                    try:
                        result = json.loads(fixed)
                        if result:
                            result = self._convert_to_standard_format(result)
                            parse_method = '方法3'
                    except json.JSONDecodeError as e:
                        logger.debug("[KeywordLibraryGenerator] 修复后仍解析失败: " + str(e))
            
            # 方法4：从后向前提取完整对象（处理LLM返回被截断的情况）
            if result is None:
                try:
                    categories = self._extract_valid_categories_backward(clean_response)
                    if categories:
                        result = {
                            'categories': categories,
                            'blue_ocean': [],
                            'ratio_strategy': {
                                'stage': '成长期',
                                'long_tail_ratio': 0.35,
                                'region_ratio': 0.30,
                                'core_ratio': 0.35,
                            },
                        }
                        parse_method = '方法4'
                except Exception as e:
                    logger.debug("[KeywordLibraryGenerator] 方法4解析失败: " + str(e))
            
            # 方法5：逐个提取 JSON 对象并组合
            if result is None:
                try:
                    categories = self._extract_categories_by_braces(clean_response)
                    if categories:
                        result = {
                            'categories': categories,
                            'blue_ocean': [],
                            'ratio_strategy': {
                                'stage': '成长期',
                                'long_tail_ratio': 0.35,
                                'region_ratio': 0.30,
                                'core_ratio': 0.35,
                            },
                        }
                        parse_method = '方法5'
                except Exception as e:
                    logger.debug("[KeywordLibraryGenerator] 方法5解析失败: " + str(e))
            
            if result is None:
                logger.error("[KeywordLibraryGenerator] 所有JSON解析方式均失败")
                logger.error("[KeywordLibraryGenerator] 原始响应前500字符: %r", response[:500])
                return self._get_default_library(realtime)
            
            logger.info("[KeywordLibraryGenerator] 解析成功，使用: %s", parse_method)
            return self._validate_and_fill(result)
        except Exception as e:
            error_str = str(e)
            if len(error_str) > 300:
                error_str = error_str[:300] + '...'
            logger.error("[KeywordLibraryGenerator] Parse error: " + error_str)
            logger.error("[KeywordLibraryGenerator] 原始响应前500字符: %r", response[:500])
            return self._get_default_library(realtime)
    
    def _extract_valid_categories_backward(self, text: str) -> list:
        """从后向前查找完整有效的 category 对象（处理 LLM 返回被截断的情况）"""
        categories = []
        n = len(text)

        for start in range(n - 2, -1, -1):
            if text[start] != '{':
                continue
            candidate = text[start:]
            if not candidate.strip().startswith('{'):
                continue
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict):
                    # 检查是否是 category 对象
                    if 'name' in obj and 'keywords' in obj:
                        categories.insert(0, obj)
                    # 检查是否是外层包裹对象
                    elif 'categories' in obj and isinstance(obj['categories'], list):
                        for cat in obj['categories']:
                            if isinstance(cat, dict) and 'name' in cat and 'keywords' in cat:
                                categories.insert(0, cat)
            except json.JSONDecodeError:
                continue

        return categories

    def _extract_categories_by_braces(self, text: str) -> list:
        """通过括号匹配提取 category 对象"""
        categories = []
        i = 0
        n = len(text)
        
        while i < n:
            # 找到 category 对象的开始
            if text[i] == '{':
                depth = 0
                start = i
                in_string = False
                escape = False
                
                for j in range(i, n):
                    c = text[j]
                    if escape:
                        escape = False
                        continue
                    if c == '\\':
                        escape = True
                        continue
                    if c == '"' and not escape:
                        in_string = not in_string
                        continue
                    if in_string:
                        continue
                    
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            json_str = text[start:j+1]
                            try:
                                obj = json.loads(json_str)
                                if isinstance(obj, dict):
                                    # 检查是否是 category 对象
                                    if 'name' in obj and 'keywords' in obj:
                                        categories.append(obj)
                                    # 检查是否是外层包裹对象
                                    elif 'categories' in obj and isinstance(obj['categories'], list):
                                        for cat in obj['categories']:
                                            if isinstance(cat, dict) and 'name' in cat and 'keywords' in cat:
                                                categories.append(cat)
                            except json.JSONDecodeError:
                                pass
                            i = j + 1
                            break
                else:
                    i += 1
                    continue
            else:
                i += 1
        
        return categories
    
    def _convert_to_standard_format(self, result: Dict) -> Dict:
        """将 LLM 返回的任意格式转换为标准格式"""
        if not isinstance(result, dict):
            return None
        
        # 已经是标准格式
        if 'categories' in result and isinstance(result.get('categories'), list):
            return result
        
        # 尝试转换 "关键词库" 或 "关键词" 格式
        # 例如: {"关键词库": {"直接需求关键词": [...]}} -> {"categories": [...]}
        converted = {
            'categories': [],
            'blue_ocean': [],
            'ratio_strategy': {
                'stage': '成长期',
                'long_tail_ratio': 0.35,
                'region_ratio': 0.30,
                'core_ratio': 0.35,
            },
            'hot_keywords': [],
        }
        
        # 定义关键词分类映射
        category_map = {
            '直接需求关键词': 'direct',
            '痛点关键词': 'pain_point',
            '对比型搜索关键词': 'compare',
            '对比关键词': 'compare',
            '症状疑问关键词': 'symptom',
            '原因分析关键词': 'cause',
            '上游供应链原料选材关键词': 'upstream',
            '行情价格关键词': 'price',
            '避坑科普关键词': 'pitfall',
            '搜索关键词': 'search',
            '场景关键词': 'scene',
            '品牌关键词': 'brand',
            '长尾关键词': 'long_tail',
            '地域关键词': 'region',
            '人群关键词': 'crowd',
            '时效关键词': 'time_limited',
            '季节关键词': 'season',
            '季节时间关键词': 'season',
            '实操技巧关键词': 'skill',
            '实操技巧干货关键词': 'skill',
            '工具耗材关键词': 'tools',
            '行业关联关键词': 'industry',
            '行业生态词': 'industry',
            '决策鼓励关键词': 'decision_encourage',
            '安心保障关键词': 'reassure',
        }
        
        # 尝试从多个可能的结构中提取关键词
        keywords_data = None
        
        # 结构1: {"关键词库": {...}}
        if '关键词库' in result and isinstance(result['关键词库'], dict):
            keywords_data = result['关键词库']
        # 结构2: 直接是关键词字典
        else:
            # 检查是否是嵌套结构（如 {"直接需求关键词": {"核心品类词": [...]}}）
            # 找出所有关键词分类
            for cat_name in category_map.keys():
                if cat_name in result:
                    keywords_data = result
                    break
            # 如果没有找到标准分类名，检查整个 result
            if keywords_data is None:
                keywords_data = result
        
        # 遍历关键词分类
        for cat_name, cat_key in category_map.items():
            if cat_name in keywords_data:
                cat_data = keywords_data[cat_name]
                keywords_list = []
                
                if isinstance(cat_data, list):
                    # 直接是关键词列表
                    for item in cat_data:
                        if isinstance(item, dict):
                            kw = item.get('关键词') or item.get('keyword') or item.get('kw')
                            if kw:
                                keywords_list.append(kw)
                        elif isinstance(item, str):
                            keywords_list.append(item)
                elif isinstance(cat_data, dict):
                    # 嵌套结构：{"核心品类词": [...], "品质保障": [...]}
                    for sub_cat_name, sub_keywords in cat_data.items():
                        if isinstance(sub_keywords, list):
                            for item in sub_keywords:
                                if isinstance(item, dict):
                                    kw = item.get('关键词') or item.get('keyword') or item.get('kw')
                                    if kw:
                                        keywords_list.append(kw)
                                elif isinstance(item, str):
                                    keywords_list.append(item)
                
                if keywords_list:
                    base = next((c['base'] for c in self.CATEGORIES if c['key'] == cat_key), '前置观望种草盘')
                    converted['categories'].append({
                        'name': cat_name,
                        'key': cat_key,
                        'base': base,
                        'count': len(keywords_list),
                        'keywords': keywords_list
                    })
        
        # 如果没有提取到任何关键词，尝试更通用的方式
        if not converted['categories']:
            # 遍历 result 中所有的值，尝试提取关键词
            for key, value in keywords_data.items():
                if isinstance(value, list) and len(value) > 0:
                    keywords_list = []
                    for item in value:
                        if isinstance(item, dict):
                            kw = item.get('关键词') or item.get('keyword') or item.get('kw')
                            if kw:
                                keywords_list.append(kw)
                        elif isinstance(item, str):
                            keywords_list.append(item)
                    if keywords_list:
                        base = next((c['base'] for c in self.CATEGORIES if c['key'] == category_map.get(key, 'other')), '前置观望种草盘')
                        converted['categories'].append({
                            'name': key,
                            'key': category_map.get(key, 'other'),
                            'base': base,
                            'count': len(keywords_list),
                            'keywords': keywords_list
                        })
                elif isinstance(value, dict):
                    # 嵌套结构
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, list):
                            keywords_list = []
                            for item in sub_value:
                                if isinstance(item, str):
                                    keywords_list.append(item)
                                elif isinstance(item, dict):
                                    kw = item.get('关键词') or item.get('keyword')
                                    if kw:
                                        keywords_list.append(kw)
                            if keywords_list:
                                base = next((c['base'] for c in self.CATEGORIES if c['key'] == category_map.get(key, 'other')), '前置观望种草盘')
                                converted['categories'].append({
                                    'name': f"{key}_{sub_key}",
                                    'key': category_map.get(key, 'other'),
                                    'base': base,
                                    'count': len(keywords_list),
                                    'keywords': keywords_list
                                })
        
        # 如果仍然没有提取到，返回失败
        if not converted['categories']:
            logger.warning("[KeywordLibraryGenerator] 无法从响应中提取关键词格式")
            return None
        
        return converted
    
    def _fix_json_errors(self, json_str: str) -> str:
        """修复常见 JSON 格式错误"""
        import re

        # 预处理：去除 markdown 代码块标记
        json_str = json_str.strip()
        if json_str.startswith('```json'):
            json_str = json_str[7:]
        elif json_str.startswith('```'):
            json_str = json_str[3:]
        if json_str.endswith('```'):
            json_str = json_str[:-3]
        json_str = json_str.strip()

        # ── 修复1：中文单引号和中文双引号（LLM 常用「'」「"」替代 JSON 的 "）──
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

        # ── 修复2：字符串值内单引号被误用作闭合引号（如 "xxx'）──
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

        # 移除注释（// 开头的行）
        lines = json_str.split('\n')
        cleaned_lines = []
        for line in lines:
            if '//' in line:
                in_string = False
                escape = False
                for c in line:
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

        # 修复末尾多余逗号
        json_str = re.sub(r',(\s*[\]}])', r'\1', json_str)

        # 修复被意外拆分的行（字符串值被换行中断）
        lines = json_str.split('\n')
        merged_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            quote_count = 0
            escape = False
            in_string = False
            for c in line:
                if escape:
                    escape = False
                    continue
                if c == '\\':
                    escape = True
                    continue
                if c == '"':
                    in_string = not in_string
                    quote_count += 1

            if quote_count % 2 == 1 and not in_string:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and (next_line[0] in '",}]' or next_line.startswith('"')):
                        line = line + ' ' + next_line
                        i += 1

            merged_lines.append(line)
            i += 1

        json_str = '\n'.join(merged_lines)

        # 修复被截断的字符串值（Unterminated string starting at line X column Y）
        lines = json_str.split('\n')
        fixed_lines = []
        for line in lines:
            trailing_content = ""
            in_string = False
            escape = False
            for c in line:
                if escape:
                    escape = False
                    trailing_content += c
                    continue
                if c == '\\':
                    escape = True
                    trailing_content += c
                    continue
                if c == '"':
                    in_string = not in_string
                if not in_string:
                    trailing_content += c
                else:
                    trailing_content += c

            if not in_string:
                trailing = trailing_content.strip()
                if trailing and trailing[-1] not in ',"}])':
                    # 被截断的字符串内容，截断到最后一个合法字符
                    for j in range(len(line) - 1, -1, -1):
                        if line[j] in ',"}])\n\t ':
                            continue
                        else:
                            line = line[:j+1]
                            break
            fixed_lines.append(line)
        json_str = '\n'.join(fixed_lines)

        # 移除不可见控制字符
        json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', json_str)

        # 尝试找到最后一个能完整解析的位置（从后向前扫描）
        last_valid_pos = -1
        for i in range(len(json_str) - 1, -1, -1):
            c = json_str[i]
            if c in '}':
                try:
                    json.loads(json_str[:i+1])
                    last_valid_pos = i + 1
                    break
                except:
                    continue
            elif c == ']':
                try:
                    json.loads(json_str[:i+1])
                    last_valid_pos = i + 1
                    break
                except:
                    continue
        if last_valid_pos > 0 and last_valid_pos < len(json_str):
            json_str = json_str[:last_valid_pos]
            logger.debug("[KeywordLibraryGenerator] JSON被截断，保留到位置 %d", last_valid_pos)

        return json_str

    def _validate_and_fill(self, result: Dict) -> Dict:
        """验证并补充关键词库"""
        default = self._get_default_library({})
        for key in ['categories', 'blue_ocean', 'ratio_strategy', 'hot_keywords']:
            if key not in result:
                result[key] = default.get(key, [] if key != 'ratio_strategy' else {})
        # 确保每个 category 都有 base 字段
        if 'categories' in result and isinstance(result['categories'], list):
            for cat in result['categories']:
                if isinstance(cat, dict) and 'base' not in cat:
                    cat['base'] = next(
                        (c['base'] for c in self.CATEGORIES if c['key'] == cat.get('key', '')),
                        '前置观望种草盘'
                    )
        return result

    def _get_default_library(self, realtime: Dict) -> Dict:
        """获取默认关键词库"""
        return {
            'categories': [
                {'name': c['name'], 'key': c['key'], 'base': c['base'], 'count': c['min'], 'keywords': []}
                for c in self.CATEGORIES
            ],
            'blue_ocean': [],
            'ratio_strategy': {
                'stage': '成长期',
                'long_tail_ratio': 0.35,
                'region_ratio': 0.30,
                'core_ratio': 0.35,
            },
            # hot_keywords 已移除
        }

    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """估算 token 消耗"""
        # 粗略估算：中文约2字/token，英文约4字符/token
        return int((len(prompt) / 2) + (len(response) / 2))


# 全局实例
keyword_library_generator = KeywordLibraryGenerator()
