"""
画像专属选题库生成服务

功能：
1. 读取模板配置，生成专属选题库
2. 基于关键词库 + 实时上下文
3. 持久化到 saved_portraits.topic_library
4. 支持实时刷新 + 配额检查
"""

import json
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from models.public_models import SavedPortrait, db

logger = logging.getLogger(__name__)

from services.template_config_service import template_config_service
from services.llm import get_llm_service


class TopicLibraryGenerator:
    """
    选题库生成器

    复用 geo-seo skill 中的选题库模板逻辑：
    - 10大选题来源（评论区挖痛点、颠覆常识、搜索框挖需求等）
    - 选题优先级矩阵（P0-P3）
    - B/C端区分
    """

    # 选题分类（严格对应三大需求底盘 + 强制固定归类）
    # 三盘比例：前置观望搜前种草盘 50% / 刚需痛点盘 30% / 使用配套搜后种草盘 20%
    # 内容方向：前置观望=种草型；刚需痛点=转化型；使用配套=种草型
    # 强制规则：对比选型/决策安心/上下游/实操等全部固定归类，选题方向不得跨界
    TOPIC_TYPES = [
        # ①前置观望搜前种草盘（50%，种草型）：专抓前期迷茫/做对比/查原因客户
        {'name': '对比选型类', 'key': 'compare', 'base': '前置观望种草盘', 'content_direction': '种草型',
         'desc': 'A与B区别/选型对比/哪种更好/划算对比，品牌分析，种草型 【P0】<br>'
                 '<b>禁止格式</b>："XX的正确认知"、"XX的底层逻辑"、"XX的真相"、"XX全面解析"',
         'priority': 'P0'},
        {'name': '原因分析类', 'key': 'cause', 'base': '前置观望种草盘', 'content_direction': '种草型',
         'desc': '为什么会/原因分析/形成机理，认知教育，种草型 【P1】<br>'
                 '<b>禁止格式</b>："XX的原因找到了"、"XX的形成机理"',
         'priority': 'P1'},
        {'name': '上游科普类', 'key': 'upstream', 'base': '前置观望种草盘', 'content_direction': '种草型',
         'desc': '选机构看什么/师资怎么辨别/课程内容怎么判断，行业上游，种草型 【P1】<br>'
                 '<b>禁止格式</b>："XX的原料"、"XX的供应链"（除非业务真是制造业）',
         'priority': 'P1'},
        {'name': '避坑指南类', 'key': 'pitfall', 'base': '前置观望种草盘', 'content_direction': '种草型',
         'desc': '避坑/误区/骗局/怎么分辨，行业防骗，种草型 【P1】<br>'
                 '<b>禁止格式</b>："XX常见误区"（应改为具体场景如"XX千万别这么做"）',
         'priority': 'P1'},
        {'name': '行情价格类', 'key': 'price', 'base': '前置观望种草盘', 'content_direction': '种草型',
         'desc': '价格/报价/行情/成本构成，预算参考，种草型 【P2】<br>'
                 '<b>禁止格式</b>："XX价格行情"、"XX成本构成"',
         'priority': 'P2'},
        {'name': '认知颠覆类', 'key': 'rethink', 'base': '前置观望种草盘', 'content_direction': '种草型',
         'desc': '打破用户固有偏见/颠覆常识，易传播，种草型 【P2】<br>'
                 '<b>必须包含具体偏见描述</b>，如"以为XX就行？"、"XX是误区！"<br>'
                 '<b>禁止格式</b>："XX的正确认知"、"XX的真相"、"XX90%都错了"',
         'priority': 'P2'},
        {'name': '知识教程类', 'key': 'tutorial', 'base': '前置观望种草盘', 'content_direction': '种草型',
         'desc': '主动搜索，精准流量，种草型 【P1】<br>'
                 '<b>禁止格式</b>："XX完全指南"、"XX入门"',
         'priority': 'P1'},
        {'name': '场景细分类', 'key': 'scene', 'base': '前置观望种草盘', 'content_direction': '种草型',
         'desc': '精准人群细分，种草型 【P2】',
         'priority': 'P2'},
        {'name': '地域精准类', 'key': 'region', 'base': '前置观望种草盘', 'content_direction': '种草型',
         'desc': '本地流量，种草型 【P3】',
         'priority': 'P3'},

        # ②刚需痛点盘（30%，转化型）：强化决策安心，解决临门一脚
        {'name': '痛点解决类', 'key': 'pain_point', 'base': '刚需痛点盘', 'content_direction': '转化型',
         'desc': '直面核心痛点，提供解决方案，引导成交，转化型 【P0】<br>'
                 '<b>禁止格式</b>："XX怎么办？"（应改为"XX怎么办？三步搞定"等具体方案）',
         'priority': 'P0'},
        {'name': '决策安心类', 'key': 'decision_encourage', 'base': '刚需痛点盘', 'content_direction': '转化型',
         'desc': '靠谱吗/会不会坑/售后怎么样/别人怎么选，打消顾虑，转化型 【P0】<br>'
                 '<b>禁止格式</b>："XX靠谱吗？"（应改为"XX靠不靠谱？看完你就明白了"）',
         'priority': 'P0'},
        {'name': '效果验证类', 'key': 'effect_proof', 'base': '刚需痛点盘', 'content_direction': '转化型',
         'desc': '产品效果对比/使用前后对比/真实案例，建立信任，转化型 【P1】',
         'priority': 'P1'},

        # ③使用配套搜后种草盘（20%，种草型）：使用后实操留存
        {'name': '实操技巧类', 'key': 'skill', 'base': '使用配套搜后种草盘', 'content_direction': '种草型',
         'desc': '使用后方法/步骤流程/实操经验，种草型 【P1】<br>'
                 '<b>禁止格式</b>："XX技巧"、"XX5个技巧"',
         'priority': 'P1'},
        {'name': '工具耗材类', 'key': 'tools', 'base': '使用配套搜后种草盘', 'content_direction': '种草型',
         'desc': '专用工具/周边耗材/后期养护推荐，种草型 【P2】<br>'
                 '<b>注意</b>：服务业/教育类业务慎用此类型，避免生成"工具耗材"类标题',
         'priority': 'P2'},
        {'name': '行业关联系列类', 'key': 'industry', 'base': '使用配套搜后种草盘', 'content_direction': '种草型',
         'desc': '上下游关联/复购引导/升级推荐，种草型 【P2】<br>'
                 '<b>注意</b>：教育类业务慎用此类型',
         'priority': 'P2'},
        {'name': '季节营销类', 'key': 'seasonal', 'base': '使用配套搜后种草盘', 'content_direction': '种草型',
         'desc': '时效性强，季节关联，种草型 【P2】<br>'
                 '<b>禁止格式</b>："春季XX"、"冬季XX"（应改为"高考出分前家长要做什么"）<br>'
                 '<b>注意</b>：教育/服务类业务慎用此类型，避免生成"春季高考志愿填报辅导"等机械拼接',
         'priority': 'P2'},
        {'name': '节日营销类', 'key': 'festival', 'base': '使用配套搜后种草盘', 'content_direction': '种草型',
         'desc': '节日刚需，复购引导，种草型 【P1】',
         'priority': 'P1'},
        {'name': '情感故事类', 'key': 'emotional', 'base': '使用配套搜后种草盘', 'content_direction': '种草型',
         'desc': '易引发转发，种草型 【P3】',
         'priority': 'P3'},
    ]

    # 三套选题配比（内容阶段联动）- 兼容新旧枚举
    STAGE_TOPIC_RATIO_MAP = {
        '起号阶段': {
            '前置观望种草盘': 0.90,
            '刚需痛点盘': 0.00,
            '使用配套搜后种草盘': 0.10,
            '前置观望搜前种草盘': 0.90,
            '前置观望': 0.90,
            '使用配套': 0.10,
            'description': '90%前置种草 + 0%刚需转化 + 10%使用配套',
            'tag_strategy': '种草标签为主，无转化标签',
        },
        '成长阶段': {
            '前置观望种草盘': 0.60,
            '刚需痛点盘': 0.15,
            '使用配套搜后种草盘': 0.25,
            '前置观望搜前种草盘': 0.60,
            '前置观望': 0.60,
            '使用配套': 0.25,
            'description': '60%前置种草 + 15%刚需转化 + 25%使用配套',
            'tag_strategy': '种草标签60% + 转化标签40%',
        },
        '成熟阶段': {
            '前置观望种草盘': 0.30,
            '刚需痛点盘': 0.50,
            '使用配套搜后种草盘': 0.20,
            '前置观望搜前种草盘': 0.30,
            '前置观望': 0.30,
            '使用配套': 0.20,
            'description': '30%前置种草 + 50%刚需转化 + 20%使用配套',
            'tag_strategy': '转化标签为主，种草标签30%',
        },
    }

    def __init__(self):
        self.llm = get_llm_service()

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
    ) -> Dict[str, Any]:
        """
        生成选题库（缓存优先）

        Args:
            portrait_data: 画像数据
            business_info: 业务信息
            keyword_library: 关键词库（可选，用于精准选题）
            plan_type: 套餐类型
            use_template: 是否使用模板配置
            topic_count: 选题数量
            portrait_id: 画像ID（用于缓存检查）
            content_stage: 内容阶段（起号阶段/成长阶段/成熟阶段），优先于 plan_type
        """
        try:
            # 缓存检查：如果画像有选题库且未过期，直接返回
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
                # 读取画像的 content_stage 字段（优先使用）
                if portrait and not content_stage:
                    content_stage = portrait.content_stage or '成长阶段'

            # 防御性检查
            if not isinstance(portrait_data, dict):
                portrait_data = {}
            if not isinstance(business_info, dict):
                business_info = {}

            # 获取实时上下文
            realtime = template_config_service.get_realtime_context()

            # 获取阶段配比
            stage = content_stage or '成长阶段'
            stage_config = self.STAGE_TOPIC_RATIO_MAP.get(stage, self.STAGE_TOPIC_RATIO_MAP['成长阶段'])
            logger.info("[TopicLibraryGenerator] 内容阶段: %s，配比: %s", stage, stage_config['description'])

            # 构建变量上下文
            context = self._build_context(portrait_data, business_info, keyword_library, realtime)

            # 构建 Prompt - 直接使用默认提示词，不使用数据库模板
            prompt = self._build_default_prompt(context, keyword_library, topic_count, stage, stage_config)

            # 调用 LLM
            system_msg = (
                "【强制要求】你必须严格按照用户提供的业务描述和画像信息生成选题！\n"
                "禁止添加任何未提供的信息！禁止编造产品名称！\n"
                "\n"
                "你是一位抖音爆款选题策划专家，精通本地商家内容营销。\n"
                "必须严格按照JSON格式输出，选题必须有差异化、能引发共鸣。\n"
                "\n"
                "【绝对禁止的标题格式】（违反将导致输出无效）\n"
                '1. 禁止"XX的正确认知"格式 → 改为具体问题描述\n'
                '2. 禁止"XX的底层逻辑"格式 → 改为用户实际问题\n'
                '3. 禁止"XX的真相"格式 → 改为具体疑问\n'
                '4. 禁止"XX全面解析"格式 → 改为具体角度\n'
                '5. 禁止"XX原料/供应链" → 除非业务真是制造业\n'
                '6. 禁止"春季XX/冬季XX"拼接 → 改为具体时间节点的用户问题\n'
                "\n"
                "【JSON格式强制约束】\n"
                "1. 所有字符串值必须使用英文双引号 \"（严禁使用中文单引号 ' 或中文双引号 ""）\n"
                "2. keywords 数组内的每个关键词也必须用英文双引号包裹\n"
                "3. 输出必须是可直接被 Python json.loads() 解析的有效 JSON"
            )
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ]

            logger.info("[TopicLibraryGenerator] 画像数据 portrait_data keys=%s", list(portrait_data.keys()) if isinstance(portrait_data, dict) else type(portrait_data))
            logger.info("[TopicLibraryGenerator] 业务信息 business_description=%s", business_info.get('business_description', ''))
            logger.info("[TopicLibraryGenerator] context keys=%s", list(context.keys()) if context else None)
            logger.info("[TopicLibraryGenerator] 画像核心字段: 身份=%s, 痛点=%s, 顾虑=%s",
                         context.get('目标客户身份', ''), context.get('核心痛点', ''), context.get('核心顾虑', ''))
            response = self.llm.chat(messages)
            logger.info("[TopicLibraryGenerator] LLM原始响应长度=%d, 前200字符=%r", len(response), response[:200])

            # 解析结果
            result = self._parse_response(response, portrait_data, business_info.get('business_description', ''), topic_count)
            logger.info("[TopicLibraryGenerator] 解析后result topics数量=%d, by_type=%s",
                         len(result.get('topics', [])), result.get('by_type', {}))

            return {
                'success': True,
                'topic_library': result,
                'tokens_used': self._estimate_tokens(prompt, response),
                '_meta': {
                    'plan_type': plan_type,
                    'realtime': realtime,
                    'used_template': use_template,
                    'based_on_keywords': bool(keyword_library),
                    'content_stage': stage,
                }
            }

        except Exception as e:
            # 追踪错误来源 - 用 print 绕过 logger 二次格式化问题
            import sys, traceback
            print(f"[DEBUG TopicLibraryGenerator] === EXCEPTION CAUGHT AT generate() ===", file=sys.stderr)
            print(f"[DEBUG] exception type: {type(e).__name__}", file=sys.stderr)
            print(f"[DEBUG] exception msg: {str(e)[:500]}", file=sys.stderr)
            print(f"[DEBUG] traceback:\n{traceback.format_exc()}", file=sys.stderr)
            print(f"[DEBUG] === END ===", file=sys.stderr)
            error_str = str(e)
            if len(error_str) > 300:
                error_str = error_str[:300] + '...'
            logger.error("[TopicLibraryGenerator] Error: " + error_str)
            return {'success': False, 'error': error_str}

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

        ttl_hours = {
            'basic': 24,
            'professional': 168,
            'enterprise': 720,
        }.get(plan_type, 24)

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
        """
        从选题库中选择选题

        Args:
            topic_library: 选题库
            count: 选择数量
            topic_type: 指定类型
            keyword_hint: 关键词提示（用于筛选相关选题）

        Returns:
            选中的选题列表
        """
        topics = topic_library.get('topics', [])

        if not topics:
            return []

        # 按关键词过滤
        if keyword_hint and keyword_hint.strip():
            keyword = keyword_hint.strip().lower()
            topics = [
                t for t in topics
                if keyword in (t.get('title', '') + t.get('keywords', '')).lower()
            ]

        # 按类型筛选
        if topic_type:
            topics = [t for t in topics if t.get('type_key') == topic_type]

        # 按优先级排序
        priority_order = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
        topics = sorted(
            topics,
            key=lambda t: priority_order.get(t.get('priority', 'P3'), 3)
        )

        # 随机打乱同优先级
        random.shuffle(topics)

        return topics[:count]

    def _escape_fstring(self, s: str) -> str:
        """转义字符串中的花括号，防止在 f-string 中被误解析为占位符"""
        if not isinstance(s, str):
            return ''
        return s.replace('{', '{{').replace('}', '}}')

    def _build_context(
        self,
        portrait_data: Dict,
        business_info: Dict,
        keyword_library: Dict = None,
        realtime: Dict = None,
    ) -> Dict:
        """构建模板变量上下文"""
        # 防御性检查：确保所有输入都是字典
        if not isinstance(portrait_data, dict):
            portrait_data = {}
        if not isinstance(business_info, dict):
            business_info = {}
        if not isinstance(keyword_library, dict):
            keyword_library = None
        if not isinstance(realtime, dict):
            realtime = {}

        # 支持多种画像格式
        # 新格式（超级定位）：portrait_summary, user_perspective, buyer_perspective, identity_tags
        # 旧格式：identity, pain_point, concern, scenario
        identity_tags = portrait_data.get('identity_tags', {})
        user_persp = portrait_data.get('user_perspective', {})
        buyer_persp = portrait_data.get('buyer_perspective', {})

        # 目标客户身份
        identity = portrait_data.get('identity', '')
        if not identity:
            identity = identity_tags.get('user', '') or identity_tags.get('buyer', '')

        # 核心痛点
        pain_point = portrait_data.get('pain_point', '')
        if not pain_point:
            pain_point = user_persp.get('problem', '')
            if not pain_point:
                summary = portrait_data.get('portrait_summary', '')
                if summary and '，' in summary:
                    pain_point = summary.split('，')[0]

        # 核心顾虑
        concern = portrait_data.get('concern', '')
        if not concern:
            concern = buyer_persp.get('obstacles', '')
            if not concern:
                concern = buyer_persp.get('psychology', '')

        # 使用场景
        scenario = portrait_data.get('scenario', '')
        if not scenario:
            scenario = user_persp.get('current_state', '')

        # 完整画像摘要（注入 prompt 约束选题围绕此画像展开）
        portrait_summary = portrait_data.get('portrait_summary', '')
        # 用户视角完整描述
        user_perspective_text = portrait_data.get('user_perspective', {}).get('problem', '')
        # 买单方视角完整描述
        buyer_perspective_text = portrait_data.get('buyer_perspective', {}).get('obstacles', '') or \
                                 portrait_data.get('buyer_perspective', {}).get('psychology', '')
        # 用户当前状态
        user_current_state = user_persp.get('current_state', '')

        # 从关键词库提取关键词
        keywords_text = ''
        if keyword_library:
            all_kw = []
            for cat in keyword_library.get('categories', []):
                if isinstance(cat, dict):
                    kws = cat.get('keywords', [])
                    if isinstance(kws, list):
                        all_kw.extend(kws[:5])
            keywords_text = ', '.join(all_kw[:50])

        context = {
            # 画像（支持新旧格式）
            '目标客户身份': self._escape_fstring(identity),
            '核心痛点': self._escape_fstring(pain_point),
            '核心顾虑': self._escape_fstring(concern),
            '使用场景': self._escape_fstring(scenario),
            # 完整画像摘要 + 用户视角（注入 prompt 强化选题与画像绑定）
            'portrait_summary': self._escape_fstring(portrait_summary),
            '用户视角描述': self._escape_fstring(user_perspective_text),
            '买单方视角描述': self._escape_fstring(buyer_perspective_text),
            '用户当前状态': self._escape_fstring(user_current_state),

            # 业务
            '业务描述': self._escape_fstring(business_info.get('business_description', '')),
            '行业': self._escape_fstring(business_info.get('industry', '')),
            '产品': self._escape_fstring(', '.join(business_info.get('products', []))),
            '地域': self._escape_fstring(business_info.get('region', '')),
            '目标客户': self._escape_fstring(business_info.get('target_customer', '')),

            # 实时
            '当前季节': self._escape_fstring(realtime.get('当前季节', '')),
            '月份名称': self._escape_fstring(realtime.get('月份名称', '')),
            '季节消费特点': self._escape_fstring(realtime.get('季节消费特点', '')),
            '当前节日': self._escape_fstring(realtime.get('当前节日', '无')),
            '当前节气': self._escape_fstring(realtime.get('当前节气', '无')),

            # 关键词
            '关键词库': self._escape_fstring(keywords_text),
        }
        return context

    def _build_default_prompt(
        self,
        context: Dict,
        keyword_library: Dict = None,
        topic_count: int = 20,
        content_stage: str = '成长阶段',
        stage_config: Dict = None,
    ) -> str:
        """构建默认提示词

        Args:
            content_stage: 内容阶段（起号阶段/成长阶段/成熟阶段）
            stage_config: 阶段配比配置
        """
        if stage_config is None:
            stage_config = self.STAGE_TOPIC_RATIO_MAP.get(content_stage, self.STAGE_TOPIC_RATIO_MAP['成长阶段'])

        type_rules = '\n'.join([
            f"{i+1}. **{t['name']}**（底盘:{t['base']} 内容方向:{t['content_direction']}）：{t['desc']} 【{t['priority']}】"
            for i, t in enumerate(self.TOPIC_TYPES)
        ])

        return f"""你是一位抖音爆款选题策划专家。请为以下业务生成{topic_count}个精准选题，严格遵循三大需求底盘结构，全链路执行：前期对比种草→中期安心转化→后期留存种草。

=== 三大需求底盘（选题数量分配 + 内容方向，强制对应）===
① **前置观望种草盘（50%，种草型）**：对比选型/原因分析/上游科普/避坑指南/行情价格，专抓前期迷茫、做对比、查原因的潜在客户。选题类型：对比选型类、原因分析类、上游科普类、避坑指南类、行情价格类、认知颠覆类、知识教程类、场景细分类、地域精准类
② **刚需痛点盘（30%，转化型）**：痛点解决/决策安心/效果验证，临门一脚解决下单犹豫。选题类型：痛点解决类、决策安心类、效果验证类
③ **使用配套搜后种草盘（20%，种草型）**：季节时间（旺季/淡季）/实操技巧干货（技巧/方法/秘方/数字型）/工具耗材，使用后实操留存。选题类型：实操技巧类、工具耗材类、行业关联系列类、季节营销类、节日营销类、情感故事类
**强制规则：所有选题必须严格从上述分类中提取，对比选型/决策安心/上游/认知颠覆/实操技巧干货/季节时间等关键词已固定归入对应底盘，选题方向不得跨界。AI 禁止自行新增分类或自由归类**

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

## 画像视角约束（所有选题必须绑定此画像，强制执行）
- **画像摘要**：{context['portrait_summary'] or '（无）'}
- **用户视角（这个用户遇到了什么问题）**：{context['用户视角描述'] or '（无）'}
- **买单方视角（出钱的人担心什么）**：{context['买单方视角描述'] or '（无）'}
- **用户当前状态**：{context['用户当前状态'] or '（无）'}

**【强制约束】**：
1. 所有选题必须从这个画像出发，选题的标题和内容角度必须服务于上述画像用户的具体问题
2. 选题主角是"画像用户"，不是抽象的"客户"或泛化的"用户"
3. 举例：如果画像是"信息不对称家长"，选题应该从"一个高三孩子的家长在志愿填报前遇到了XX困惑/焦虑/误区"角度切入，而不是泛泛讨论"高考志愿填报辅导"
4. 同一业务不同画像，选题角度必须不同；画像决定了选题的第一人称视角和核心问题方向

## 实时上下文
- 当前季节：{context['当前季节']}（{context['月份名称']}）
- 季节消费特点：{context['季节消费特点']}
- 当前节日：{context['当前节日']}
- 当前节气：{context['当前节气']}

## 关键词参考（选题须与关键词关联）
{context['关键词库'] or '（无关键词库，将根据业务描述生成）'}

## 选题分类要求（严格对应三盘，各选题的 content_direction 已标注，强制归类）

{type_rules}

## 选题格式禁令（强制执行，LLM 必须遵守）
**禁止以下标题格式：**
1. ❌ "XX的正确认知"（如"专业选择的正确认知"）—— 应改为具体问题描述
2. ❌ "XX的底层逻辑"（如"志愿填报的底层逻辑"）—— 应改为用户实际问题
3. ❌ "XX的真相"（如"高考志愿填报辅导的真相"）—— 应改为具体疑问
4. ❌ "XX全面解析" / "XX完全指南" —— 应改为具体角度
5. ❌ "XX的原因找到了" —— 应改为"为什么XX？"格式
6. ❌ "XX的原料" / "XX的供应链" —— 除非业务是制造业
7. ❌ "春季XX" / "冬季XX" —— 应改为具体时间节点的用户问题
8. ❌ "XX工具推荐" / "XX耗材推荐" —— 服务业/教育类慎用
9. ❌ "XX上下游关联" —— 服务业/教育类慎用

**正确标题示例：**
- ✅ "孩子成绩一般怎么报志愿？"（而非"成绩一般学生志愿填报的正确认知"）
- ✅ "压线生怎么选学校？"（而非"压线生志愿填报的底层逻辑"）
- ✅ "以为随便选就行？历年家长血泪教训"（而非"志愿填报的真相"）
- ✅ "高考出分前家长要做哪些准备？"（而非"春季高考志愿填报辅导"）

## 选题要求
1. 必须围绕用户真实痛点，差异化明显
2. 优先选择高优先级（P0/P1）选题
3. 融入季节、节日等实时因素
4. 每条选题包含：标题、类型、来源、关键词、推荐理由、content_direction（**必须从底盘自动推导**）
5. 涵盖至少5种以上选题类型
6. **content_direction 强制规则**：痛点解决类/决策安心类/效果验证类=转化型；其余类型=种草型
7. 选题必须与关键词库中的关键词形成关联
8. **对比型选型类选题须映射自关键词库中的"对比型搜索关键词"分类**
9. **决策安心类选题须映射自关键词库中的"决策鼓励关键词"和"安心保障关键词"分类**

## 三套固定选题配比（管理员配置阶段，系统自动联动）
**【当前生效阶段】：** **{content_stage}**（{stage_config['description']}）
- 起号阶段（90%前置种草 + 10%使用配套）：无刚需转化选题
  - 前置观望搜前种草盘：90%（对比选型类/原因分析类/上游科普类/避坑指南类/认知颠覆类/知识教程类/场景细分类/地域精准类）
  - 使用配套搜后种草盘：10%（实操技巧类/工具耗材类/行业关联系列类/季节营销类/节日营销类/情感故事类）
  - 刚需痛点盘：0%（无）
- 成长阶段（60%前置种草 + 25%使用配套 + 15%刚需转化）
  - 前置观望搜前种草盘：60%
  - 使用配套搜后种草盘：25%
  - 刚需痛点盘：15%（痛点解决类/决策安心类/效果验证类）
- 成熟阶段（30%前置种草 + 20%使用配套 + 50%刚需转化）
  - 前置观望搜前种草盘：30%
  - 使用配套搜后种草盘：20%
  - 刚需痛点盘：50%（痛点解决类/决策安心类/效果验证类）
**【AI 强制执行】**：严格按照上述"当前生效阶段"的配比分配选题数量，不得偏离！标签策略：{stage_config['tag_strategy']}

## 输出格式（每条选题必须包含以下字段）
- title: 选题标题（中文，不抽象）
- type_key: **类型键名，英文小写**，必须从以下枚举选取：`compare`/`cause`/`upstream`/`pitfall`/`price`/`rethink`/`tutorial`/`scene`/`region`/`pain_point`/`decision_encourage`/`effect_proof`/`skill`/`tools`/`industry`/`seasonal`/`festival`/`emotional`。**禁止填写中文类型名称如"对比选型类"**
- type_name: 中文类型名称，如"对比选型类"
- priority: 优先级（P0/P1/P2/P3）
- source: 来源说明
- keywords: 关键词列表（与该选题强关联）
- content_direction: 内容方向，种草型 或 转化型
- recommended_reason: 推荐理由

## JSON输出示例（请严格参照此格式）
```json
{{
  "topics": [
    {{
      "title": "进口奶粉 vs 国产奶粉，过敏宝宝该如何选择？",
      "type_key": "compare",
      "type_name": "对比选型类",
      "priority": "P0",
      "source": "用户需求调研",
      "keywords": ["婴儿奶粉对比", "过敏奶粉推荐"],
      "content_direction": "种草型",
      "recommended_reason": "帮助过敏宝宝家长做出明智选择"
    }}
  ]
}}
```
**注意：输出必须用 {{"topics": [ ... ]}} 对象包裹，不是纯数组！type_key 必须填英文枚举，禁止填中文！**

## 输出数量要求（唯一指令，请严格执行）
根据内容阶段 **{content_stage}** 的配比，生成恰好 **20个** 选题：
- 前置观望种草盘（{stage_config.get('前置观望种草盘', 0.6)*100:.0f}%）：约 **{int(stage_config.get('前置观望种草盘', 0.6) * 20):d}个**
- 刚需痛点盘（{stage_config.get('刚需痛点盘', 0.15)*100:.0f}%）：约 **{int(stage_config.get('刚需痛点盘', 0.15) * 20):d}个**
- 使用配套搜后种草盘（{stage_config.get('使用配套搜后种草盘', 0.25)*100:.0f}%）：约 **{int(stage_config.get('使用配套搜后种草盘', 0.25) * 20):d}个**

> 注意：输出必须是恰好20条JSON，不多不少，直接返回 {{\"topics\": [ ... ]}} 对象，不要有markdown代码块包裹。

请严格按上述JSON格式输出，直接返回JSON，不要有其他文字说明："""

    def _parse_response(self, response: str, portrait_data: Dict = None, business_description: str = '', topic_count: int = 20) -> Dict:
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
            
            # 尝试多种解析方式
            result = None
            
            # 方法1：直接解析
            if result is None:
                try:
                    result = json.loads(clean_response)
                    if result:
                        result = self._convert_to_standard_format(result)
                        logger.info("[TopicLibraryGenerator] ✓ 方法1直接解析成功")
                except json.JSONDecodeError:
                    pass
            
            # 方法2：找到第一个完整的 JSON 对象（而非贪婪匹配到最后一个 }）
            if result is None:
                try:
                    # 从第一个 { 开始，向后找第一个能完整解析的位置
                    start = clean_response.find('{')
                    if start == -1:
                        raise ValueError("No JSON object found")
                    # 从后向前尝试，找到第一个完整解析的位置
                    end = len(clean_response)
                    for try_end in range(end, start, -1):
                        candidate = clean_response[start:try_end]
                        candidate = candidate.replace('{{', '{').replace('}}', '}')
                        try:
                            parsed = json.loads(candidate)
                            if parsed:
                                result = self._convert_to_standard_format(parsed)
                                logger.debug("[TopicLibraryGenerator] 方法2成功找到完整JSON对象")
                                break
                        except json.JSONDecodeError:
                            continue
                    if result is None:
                        logger.debug("[TopicLibraryGenerator] 方法2未找到完整JSON对象")
                except Exception as e:
                    # e 可能是 KeyError（字符串含 { }），str(e) 不能再做 %-格式化
                    logger.debug("[TopicLibraryGenerator] 方法2异常: " + str(e))
            
            # 方法3：修复常见 JSON 错误后重试
            if result is None:
                fixed = self._fix_json_errors(clean_response)
                if fixed:
                    try:
                        result = json.loads(fixed)
                        if result:
                            result = self._convert_to_standard_format(result)
                            logger.info("[TopicLibraryGenerator] ✓ 方法3修复JSON错误后成功")
                    except json.JSONDecodeError as e:
                        logger.debug("[TopicLibraryGenerator] 修复后仍解析失败: " + str(e))

            # 方法4：更激进的修复
            if result is None:
                topics_match = re.search(r'"topics"\s*:\s*\[([\s\S]*)\]', clean_response)
                if topics_match:
                    topics_str = '[' + topics_match.group(1)
                    bracket_count = 1
                    for i, c in enumerate(topics_match.group(1)):
                        if c == '[':
                            bracket_count += 1
                        elif c == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                topics_str = '[' + topics_match.group(1)[:i+1]
                                break
                    if topics_str.endswith(']'):
                        try:
                            result = {'topics': json.loads(topics_str)}
                            logger.info("[TopicLibraryGenerator] ✓ 方法4提取topics数组成功")
                        except:
                            pass

                if result is None:
                    lib_match = re.search(r'"topic_library"\s*:\s*\{([\s\S]*)\}', clean_response)
                    if lib_match:
                        lib_str = '{"topic_library": {' + lib_match.group(1)
                        bracket_count = 1
                        for i, c in enumerate(lib_match.group(1)):
                            if c == '{':
                                bracket_count += 1
                            elif c == '}':
                                bracket_count -= 1
                                if bracket_count == 0:
                                    lib_str = '{"topic_library": {' + lib_match.group(1)[:i+1] + '}'
                                    break
                        if lib_str.endswith('}'):
                            try:
                                result = json.loads(lib_str)
                                logger.info("[TopicLibraryGenerator] ✓ 方法4提取topic_library对象成功")
                            except:
                                pass

            # 方法5：解析直接返回的选题数组（无外层包装）
            if result is None:
                try:
                    array_match = re.search(r'\[\s*\{', clean_response)
                    if array_match:
                        start_pos = array_match.start()
                        for end_pos in range(len(clean_response), start_pos, -1):
                            test_str = clean_response[start_pos:end_pos]
                            try:
                                parsed = json.loads(test_str)
                                if isinstance(parsed, list) and len(parsed) > 0:
                                    result = {'topics': parsed}
                                    logger.info("[TopicLibraryGenerator] ✓ 方法5成功提取%d条选题", len(parsed))
                                    break
                            except:
                                continue
                except Exception as e:
                    logger.debug("[TopicLibraryGenerator] 方法5解析失败: " + str(e))

            # 方法6：逐个提取 JSON 对象并组合
            if result is None:
                try:
                    topics = []
                    bracket_depth = 0
                    in_json = False
                    json_start = -1
                    for i, c in enumerate(clean_response):
                        if c == '{':
                            if not in_json:
                                json_start = i
                                in_json = True
                            bracket_depth += 1
                        elif c == '}':
                            bracket_depth -= 1
                            if in_json and bracket_depth == 0:
                                json_str = clean_response[json_start:i+1]
                                try:
                                    obj = json.loads(json_str)
                                    if isinstance(obj, dict) and ('title' in obj or '标题' in obj or '选题' in obj):
                                        topics.append(obj)
                                except:
                                    pass
                                in_json = False
                                json_start = -1
                    if topics:
                        result = {'topics': topics}
                        logger.info("[TopicLibraryGenerator] ✓ 方法6逐个提取成功，共%d个选题", len(topics))
                except Exception as e:
                    logger.debug("[TopicLibraryGenerator] 方法6解析失败: " + str(e))

            # 方法7：从后向前提取完整对象（处理LLM返回被截断的情况）
            if result is None:
                try:
                    topics = self._extract_valid_topics_backward(clean_response)
                    if topics:
                        result = {'topics': topics}
                        logger.info("[TopicLibraryGenerator] 方法7从后向前提取到%d个选题", len(topics))
                except Exception as e:
                    logger.debug("[TopicLibraryGenerator] 方法7解析失败: " + str(e))

            if result is None:
                raise ValueError("所有JSON解析方式均失败")
            
            # 处理 emoji key（如 "📚选题库" -> "topic_library"）
            result = self._normalize_keys(result)
            
            # 转换为标准格式
            result = self._convert_to_standard_format(result)
            
            return self._validate_and_fill(result, portrait_data, business_description, topic_count)
            
        except json.JSONDecodeError as e:
            logger.error("[TopicLibraryGenerator] JSON解析失败: " + str(e)[:200])
            logger.error("[TopicLibraryGenerator] 原始响应前500字符: " + repr(response[:500]))
            logger.warning("[TopicLibraryGenerator] 使用默认选题库兜底 (JSONDecodeError)")
            return self._get_default_library(portrait_data, business_description)
        except ValueError as e:
            if "all parse" in str(e):
                logger.warning("[TopicLibraryGenerator] 使用默认选题库兜底 (ValueError)")
                return self._get_default_library(portrait_data, business_description)
            raise
        except Exception as e:
            # 使用 %(message)s 语法避免格式化冲突，或直接打印字符串
            logger.error("[TopicLibraryGenerator] Exception: " + str(e)[:300])
            logger.error("[TopicLibraryGenerator] 原始响应前500字符: %r", response[:500])
            logger.warning("[TopicLibraryGenerator] 使用默认选题库兜底 (Exception)")
            return self._get_default_library(portrait_data, business_description)

    def _fix_json_errors(self, json_str: str) -> str:
        """修复常见 JSON 格式错误"""
        import re

        # 预处理：去除 markdown 代码块标记（LLM 可能返回 ```json ... ```）
        json_str = json_str.strip()
        if json_str.startswith('```json'):
            json_str = json_str[7:]
        elif json_str.startswith('```'):
            json_str = json_str[3:]
        if json_str.endswith('```'):
            json_str = json_str[:-3]
        json_str = json_str.strip()

        # ── 修复1：中文单引号「'」和中文双引号「""」 ──
        # LLM 常返回 Chinese single quote ' (U+2019) 替代 JSON 的 "
        # 策略：先将所有中文引号替换为占位符，再在字符串值内正确还原
        # 更安全的做法：逐行处理，在字符串值内替换，中文引号 → "
        # 原理：JSON 字符串值内的中文引号一定成对出现（开/闭），且中间是中文内容
        def replace_curly_quotes(text):
            result = []
            i = 0
            in_string = False
            while i < len(text):
                c = text[i]
                if c == '"' and (i == 0 or text[i-1] != '\\'):
                    in_string = not in_string
                    result.append(c)
                elif not in_string and c in '\u2018\u2019\u201b':  # ' ' '
                    result.append('"')  # 中文单引号 → "
                elif not in_string and c in '\u201c\u201d\u201f':  # " " "
                    result.append('"')  # 中文双引号 → "
                else:
                    result.append(c)
                i += 1
            return ''.join(result)
        json_str = replace_curly_quotes(json_str)

        # ── 修复2：ASCII 单引号在字符串值内被误用作闭合引号 ──
        # 如果某行有 "xxx' 这样的不完整字符串（双开单闭），补上双引号
        # 匹配: 值以 " 开头但以 ' 结尾
        json_str = re.sub(r'("(?:[^"\\]|\\.)*)\'(?=[,\s\r\n\]}])', r'\1"', json_str)
        # 如果字符串内容里出现混用引号，把 '..." 或 "...' 的中文引号区域替换
        # 更简单粗暴：对每一行，统计引号对，修复奇数个引号的情况
        lines = json_str.split('\n')
        fixed_lines = []
        for line in lines:
            # 检查引号配对是否正确
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
            # 如果有奇数个引号（不成对），且行末有内容，尝试补全
            if quote_count % 2 == 1:
                line = line.rstrip() + '"'
            fixed_lines.append(line)
        json_str = '\n'.join(fixed_lines)

        # ── 预处理：去除注释（// 开头的行）──
        lines = json_str.split('\n')
        cleaned_lines = []
        for line in lines:
            # 保留字符串中的 //，只移除代码注释
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

        # 修复末尾多余逗号（如 "key": "value", } -> "key": "value" }）
        json_str = re.sub(r',(\s*[\]}])', r'\1', json_str)

        # 修复换行符在字符串值中的问题（JSON 字符串值不能有未转义的换行）
        # 这是一个激进修复：尝试合并被意外拆分的行
        lines = json_str.split('\n')
        merged_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # 检查这一行是否有奇数个未闭合的引号（表示字符串值被换行中断）
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

            # 如果引号数量是奇数，可能字符串被换行中断
            if quote_count % 2 == 1 and not in_string:
                # 尝试和下一行合并
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # 检查下一行是否以逗号、引号、花括号等结尾
                    if next_line and (next_line[0] in '",}]' or next_line.startswith('"')):
                        line = line + ' ' + next_line
                        i += 1

            merged_lines.append(line)
            i += 1

        json_str = '\n'.join(merged_lines)

        # 修复被截断的字符串值（Unterminated string）
        # 如果某行的最后一个非空字符是未闭合的字符串内容（无引号结尾），则截断该行
        lines = json_str.split('\n')
        fixed_lines = []
        for line in lines:
            # 检查行尾是否有未闭合的字符串
            quote_count = 0
            escape = False
            in_string = False
            trailing_content = ""
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
                    quote_count += 1
                    trailing_content += c
                else:
                    trailing_content += c

            # 如果不在字符串中，且末尾有内容（可能是被截断的字符串值），检查是否需要截断
            if not in_string:
                # 行尾的内容应该是有效的 JSON 语法（逗号/括号等），否则截断
                trailing = trailing_content.strip()
                if trailing and trailing[-1] not in ',"}])':
                    # 被截断的字符串内容，丢弃行尾的垃圾内容
                    # 找到最后一个有效的 JSON 结束点
                    cut_pos = len(line) - len(trailing_content.rstrip())
                    # 找到最后一个合法的 JSON 字符
                    valid_end = 0
                    for j in range(len(line) - 1, -1, -1):
                        if line[j] in '",}])':
                            valid_end = j + 1
                            break
                    if valid_end > 0:
                        line = line[:valid_end]
            fixed_lines.append(line)
        json_str = '\n'.join(fixed_lines)

        # 移除不可见控制字符（除 \n, \r, \t 外）
        json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', json_str)

        # 移除末尾的断裂内容（从最后一个完整对象后截断）
        # 找到最后一个 } 或 ] 作为可能的结束点
        last_valid_pos = -1
        for i in range(len(json_str) - 1, -1, -1):
            c = json_str[i]
            if c in '}':
                # 检查这个 } 能否形成有效的闭合
                try:
                    test = json_str[:i+1]
                    import json as _json
                    _json.loads(test)
                    last_valid_pos = i + 1
                    break
                except:
                    continue
            elif c == ']':
                try:
                    test = json_str[:i+1]
                    import json as _json
                    _json.loads(test)
                    last_valid_pos = i + 1
                    break
                except:
                    continue
        if last_valid_pos > 0 and last_valid_pos < len(json_str):
            json_str = json_str[:last_valid_pos]
            logger.debug("[TopicLibraryGenerator] JSON被截断，保留到位置 %d", last_valid_pos)

        return json_str

    def _normalize_keys(self, obj: Any) -> Any:
        """规范化 JSON key，处理 emoji 等特殊字符"""
        if isinstance(obj, dict):
            new_obj = {}
            for key, value in obj.items():
                # 标准化 key：移除 emoji、统一为下划线格式
                normalized_key = self._normalize_key(key)
                new_obj[normalized_key] = self._normalize_keys(value)
            return new_obj
        elif isinstance(obj, list):
            return [self._normalize_keys(item) for item in obj]
        else:
            return obj

    def _normalize_key(self, key: str) -> str:
        """将中文或 emoji key 转换为标准 key"""
        import re
        
        # 移除 emoji
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        cleaned = emoji_pattern.sub('', key)
        
        # 保留中文、英文、数字、下划线
        # 如果清理后是空的或只剩中文，使用预设映射
        if not cleaned.strip() or cleaned == key:
            # 常见 emoji key 映射
            key_map = {
                '📚选题库': 'topic_library',
                '📊数据': 'data',
                '📈统计': 'statistics',
                '🔢计数': 'count',
                '✅成功': 'success',
                '❌失败': 'failed',
            }
            if key in key_map:
                return key_map[key]
            # 移除所有非ASCII字符
            cleaned = key.encode('ascii', 'ignore').decode('ascii')
        
        return cleaned.strip() if cleaned else key

    def _convert_to_standard_format(self, result) -> Dict:
        """将 LLM 返回的任意格式转换为标准格式"""
        # 处理裸数组情况（如 LLM 直接返回 [{...}, {...}] 而不是 {"topics": [...]}）
        if isinstance(result, list):
            topics = []
            for item in result:
                if isinstance(item, dict):
                    topics.append(self._normalize_topic_item(item))
            if topics:
                return {'topics': topics}
            return {'topics': []}

        if not isinstance(result, dict):
            return {'topics': []}

        # 已经是标准格式
        if 'topics' in result and isinstance(result.get('topics'), list):
            # 也对 topics 数组里每条做规范化
            result['topics'] = [self._normalize_topic_item(t) for t in result['topics'] if isinstance(t, dict)]
            return result

        # 尝试转换 "选题库" 格式
        converted = {'topics': []}
        topics_data = None

        # 结构1: {"选题库": {...}}
        if '选题库' in result and isinstance(result['选题库'], dict):
            topics_data = result['选题库']
            if '选题' in topics_data:
                topics_data = topics_data['选题']
        # 结构2: {"选题": [...]} 或 {"topics": [...]}
        elif '选题' in result:
            topics_data = result['选题']
        # 结构3: {"选题库": [...]}
        elif '选题库' in result and isinstance(result['选题库'], list):
            topics_data = result['选题库']

        if topics_data and isinstance(topics_data, list):
            for item in topics_data:
                if isinstance(item, dict):
                    converted['topics'].append(self._normalize_topic_item(item))

        if not converted['topics']:
            for key, value in result.items():
                if isinstance(value, list) and len(value) > 0:
                    first_item = value[0]
                    if isinstance(first_item, dict) and ('标题' in first_item or 'title' in first_item or '选题' in first_item):
                        for item in value:
                            if isinstance(item, dict):
                                converted['topics'].append(self._normalize_topic_item(item))
                        break

        return converted if converted['topics'] else result

    def _normalize_topic_item(self, item: Dict) -> Dict:
        """规范化单条选题字段，包括 type_key/type_name 映射"""
        # type_name → type_key 映射（解决 LLM 填错字段的问题）
        type_name_to_key = {
            '对比选型类': 'compare',
            '原因分析类': 'cause',
            '上游科普类': 'upstream',
            '避坑指南类': 'pitfall',
            '行情价格类': 'price',
            '认知颠覆类': 'rethink',
            '知识教程类': 'tutorial',
            '场景细分类': 'scene',
            '地域精准类': 'region',
            '痛点解决类': 'pain_point',
            '决策安心类': 'decision_encourage',
            '效果验证类': 'effect_proof',
            '实操技巧类': 'skill',
            '工具耗材类': 'tools',
            '行业关联系列类': 'industry',
            '季节营销类': 'seasonal',
            '节日营销类': 'festival',
            '情感故事类': 'emotional',
        }
        # content_direction 映射
        type_key_to_direction = self._get_type_key_map()

        raw_type = item.get('type') or item.get('分类', '')
        raw_type_key = item.get('type_key', '')

        # 优先用 type_key，如果它是 type_name 就转换
        if raw_type_key and raw_type_key not in type_name_to_key:
            type_key = raw_type_key
        elif raw_type:
            type_key = type_name_to_key.get(raw_type, raw_type_key or 'unknown')
        else:
            type_key = raw_type_key or 'unknown'

        # type_name 标准化
        type_name = item.get('type_name') or item.get('类型名称', '')
        if type_name in type_name_to_key:
            type_name = list({k: v for v, k in type_name_to_key.items()}.get(type_name, (type_name,)))[0] if False else type_name

        return {
            'title': item.get('标题') or item.get('title') or item.get('选题') or '',
            'type_key': type_key,
            'type_name': type_name or raw_type or type_key,
            'priority': item.get('优先级') or item.get('priority', 'P2'),
            'source': item.get('来源') or item.get('source', ''),
            'keywords': item.get('关键词') or item.get('keywords', []),
            'reason': item.get('原因') or item.get('reason') or item.get('说明') or item.get('recommended_reason') or '',
            'publish_timing': item.get('发布时间') or item.get('publish_timing', ''),
            'content_hints': item.get('内容提示') or item.get('content_hints', ''),
            'content_direction': item.get('content_direction') or type_key_to_direction.get(type_key, '种草型'),
        }

    def _validate_and_fill(self, result: Dict, portrait_data: Dict = None, business_description: str = '', topic_count: int = 20) -> Dict:
        """验证并补充选题库，确保最终输出恰好 topic_count 条"""
        import re

        portrait_data = portrait_data or {}
        business_description = business_description or ''

        # 从画像提取关键信息作为选题生成素材
        # 优先级：pain_point > portrait_summary > business_description
        pain_point = portrait_data.get('pain_point', '') or portrait_data.get('核心痛点', '')
        if not pain_point:
            user_persp = portrait_data.get('user_perspective', {})
            if isinstance(user_persp, dict):
                pain_point = user_persp.get('problem', '')
        if not pain_point:
            summary = portrait_data.get('portrait_summary', '')
            if summary and isinstance(summary, str):
                pain_point = summary.split('，')[0] if '，' in summary else summary.split(',')[0]

        concern = portrait_data.get('concern', '') or portrait_data.get('核心顾虑', '')
        if not concern:
            buyer_persp = portrait_data.get('buyer_perspective', {})
            if isinstance(buyer_persp, dict):
                concern = buyer_persp.get('obstacles', '') or buyer_persp.get('psychology', '')

        identity = portrait_data.get('identity', '') or portrait_data.get('目标客户身份', '')
        if not identity:
            identity_tags = portrait_data.get('identity_tags', {})
            if isinstance(identity_tags, dict):
                identity = identity_tags.get('user', '') or identity_tags.get('buyer', '')

        # 清洗字符串中的引号
        def clean(s):
            if not isinstance(s, str):
                return ''
            s = s.replace('"', ' ').replace("'", ' ').strip()
            s = re.sub(r'\s+', ' ', s)
            return s[:50]

        pain_point = clean(pain_point)
        concern = clean(concern)
        identity = clean(identity)

        # 核心关键词用于生成标题
        core = pain_point if pain_point else (identity if identity else business_description if business_description else '该业务')

        # 提取 pain_point 中的关键词
        pain_keywords = []
        if pain_point:
            pain_keywords = re.findall(r'[\u4e00-\u9fa5]{2,10}', pain_point)
            pain_keywords = [k for k in pain_keywords if len(k) >= 2][:5]

        # 处理可能的 key 变化
        if 'topics' not in result:
            for key in ['topics', '选题库', 'topic_list', 'items']:
                if key in result:
                    result['topics'] = result.pop(key)
                    break

        if 'topics' not in result or not isinstance(result.get('topics'), list):
            result['topics'] = []

        topics = result['topics']
        current = len(topics)

        # 补充缺失字段
        base_to_direction = {
            '刚需痛点盘': '转化型',
            '前置观望种草盘': '种草型',
            '使用配套搜后种草盘': '种草型',
            '刚需痛点': '转化型',
            '前置观望': '种草型',
            '使用配套': '种草型',
        }
        type_key_to_direction = self._get_type_key_map()
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            if 'type_key' not in topic:
                topic['type_key'] = topic.get('type', topic.get('分类', 'unknown'))
            if 'priority' not in topic:
                topic['priority'] = topic.get('优先级', 'P2')
            if 'type_name' not in topic:
                topic['type_name'] = topic.get('type_name', topic.get('类型', ''))
            if 'content_direction' not in topic or not topic['content_direction']:
                topic['content_direction'] = type_key_to_direction.get(
                    topic.get('type_key', ''),
                    base_to_direction.get(topic.get('problem_base', ''), '种草型')
                )

        # 统计现有 type_key，避免重复
        existing_keys = {t.get('type_key') for t in topics if isinstance(t, dict)}

        # 核心关键词提取（用于生成补充选题的原料）
        keywords_text = ''
        if isinstance(result.get('keywords_for_fill'), list):
            keywords_text = '、'.join(result.pop('keywords_for_fill')[:10])

        # 补充缺失选题（从 topic_count 不足时）
        if current < topic_count:
            missing = topic_count - current
            logger.info("[TopicLibraryGenerator] 仅提取到%d条选题，补充%d条以达到目标数量%d",
                        current, missing, topic_count)
            fill_types = [
                {'type_key': 'cause', 'type_name': '原因分析类', 'priority': 'P1',
                 'source': '原因分析系列', 'base': '前置观望种草盘',
                 'content_direction': '种草型',
                 'title_template': f'{pain_point}的原因找到了，看完恍然大悟',
                 'desc': '为什么会、原因分析、形成机理'},
                {'type_key': 'pain_point', 'type_name': '痛点解决类', 'priority': 'P0',
                 'source': '刚需痛点盘', 'base': '刚需痛点盘',
                 'content_direction': '转化型',
                 'title_template': f'{pain_point}怎么办？教你一招搞定',
                 'desc': '直面核心痛点，提供解决方案'},
                {'type_key': 'pitfall', 'type_name': '避坑指南类', 'priority': 'P1',
                 'source': '避坑指南系列', 'base': '前置观望种草盘',
                 'content_direction': '种草型',
                 'title_template': f'处理{pain_point}，这几种做法千万别用',
                 'desc': '避坑、误区、骗局、怎么分辨'},
                {'type_key': 'rethink', 'type_name': '认知颠覆类', 'priority': 'P2',
                 'source': '认知颠覆系列', 'base': '前置观望种草盘',
                 'content_direction': '种草型',
                 'title_template': f'别再误解了！{pain_point}其实没那么复杂',
                 'desc': '打破认知、颠覆常识'},
                {'type_key': 'skill', 'type_name': '实操技巧类', 'priority': 'P1',
                 'source': '使用配套盘', 'base': '使用配套搜后种草盘',
                 'content_direction': '种草型',
                 'title_template': f'{pain_point}处理心得，看完少走弯路',
                 'desc': '使用后方法、步骤流程、实操经验'},
                {'type_key': 'price', 'type_name': '行情价格类', 'priority': 'P2',
                 'source': '行情价格系列', 'base': '前置观望种草盘',
                 'content_direction': '种草型',
                 'title_template': f'{pain_point}要花多少钱？这笔账给你算清楚了',
                 'desc': '价格、报价、行情、成本构成'},
                {'type_key': 'seasonal', 'type_name': '季节营销类', 'priority': 'P2',
                 'source': '季节营销系列', 'base': '使用配套搜后种草盘',
                 'content_direction': '种草型',
                 'title_template': f'{pain_point}高峰期到了，这些事一定要知道',
                 'desc': '季节关联、时效性强'},
                {'type_key': 'upstream', 'type_name': '上游科普类', 'priority': 'P1',
                 'source': '上游科普系列', 'base': '前置观望种草盘',
                 'content_direction': '种草型',
                 'title_template': f'关于{pain_point}，一篇文章讲透底层逻辑',
                 'desc': '原料、材质、供应链、选材鉴别'},
            ]
            filled = 0
            for ft in fill_types:
                if filled >= missing:
                    break
                # 跳过已存在的 type_key（避免重复）
                if ft['type_key'] in existing_keys:
                    continue
                topic = {
                    # 基于画像痛点生成具体标题，禁止使用「XXX的正确认知」等无实质格式
                    'title': ft.get('title_template', '').format(pain_point=pain_point, customer_role=customer_role, worry_desc=worry_desc) or f'{pain_point}怎么办？',
                    'type_key': ft['type_key'],
                    'type_name': ft['type_name'],
                    'priority': ft['priority'],
                    'source': ft['source'],
                    'keywords': pain_keywords[:3] if pain_keywords else [],
                    'reason': f'基于画像痛点「{pain_point}」生成，覆盖{ft["desc"]}维度',
                    'publish_timing': '',
                    'content_hints': '',
                    'content_direction': ft['content_direction'],
                }
                # 包含关键词关联
                if keywords_text:
                    topic['keywords'] = keywords_text.split('、')[:3]
                    topic['reason'] = f'基于关键词「{keywords_text}」生成，覆盖{ft["desc"]}'
                topics.append(topic)
                existing_keys.add(ft['type_key'])
                filled += 1
            logger.info("[TopicLibraryGenerator] 补充后共%d条选题", len(topics))

        # 最终裁剪到目标数量（防止意外多余）
        result['topics'] = topics[:topic_count]

        if 'by_type' not in result:
            result['by_type'] = self._count_by_type(result['topics'])

        if 'priorities' not in result:
            result['priorities'] = self._count_by_priority(result['topics'])

        return result

    def _infer_content_direction(self, topic_base: str) -> str:
        """从选题底盘推导内容方向（兼容新旧枚举）"""
        direction_map = {
            '刚需痛点盘': '转化型',
            '前置观望种草盘': '种草型',
            '使用配套搜后种草盘': '种草型',
            '刚需痛点': '转化型',
            '前置观望': '种草型',
            '使用配套': '种草型',
        }
        return direction_map.get(topic_base, '种草型')

    def _get_type_key_map(self) -> Dict[str, str]:
        """获取 type_key 的 content_direction 映射"""
        return {
            'compare': '种草型',
            'cause': '种草型',
            'upstream': '种草型',
            'pitfall': '种草型',
            'price': '种草型',
            'rethink': '种草型',
            'tutorial': '种草型',
            'scene': '种草型',
            'region': '种草型',
            'pain_point': '转化型',
            'decision_encourage': '转化型',
            'effect_proof': '转化型',
            'skill': '种草型',
            'tools': '种草型',
            'industry': '种草型',
            'seasonal': '种草型',
            'festival': '种草型',
            'emotional': '种草型',
        }

    def _count_by_type(self, topics: List[Dict]) -> Dict:
        counts = {}
        for t in topics:
            if not isinstance(t, dict):
                continue
            key = t.get('type_key', 'unknown')
            counts[key] = counts.get(key, 0) + 1
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

    def _get_default_library(self, portrait_data: Dict = None, business_description: str = '') -> Dict:
        """获取默认选题库（当LLM解析完全失败时使用）。必须输出20条

        核心原则：选题必须从用户痛点出发，而不是从业务描述出发
        """
        import re

        # 从画像数据中提取关键信息
        portrait_data = portrait_data or {}

        # 提取用户身份/角色
        identity = portrait_data.get('identity', '') or portrait_data.get('目标客户身份', '')
        if not identity:
            identity_tags = portrait_data.get('identity_tags', {})
            if isinstance(identity_tags, dict):
                identity = identity_tags.get('user', '') or identity_tags.get('buyer', '')
            elif isinstance(identity_tags, str):
                identity = identity_tags

        # 提取核心痛点
        pain_point = portrait_data.get('pain_point', '') or portrait_data.get('核心痛点', '')
        if not pain_point:
            user_persp = portrait_data.get('user_perspective', {})
            if isinstance(user_persp, dict):
                pain_point = user_persp.get('problem', '')
            elif isinstance(user_persp, str):
                pain_point = user_persp
        # 从 portrait_summary 提取
        if not pain_point:
            summary = portrait_data.get('portrait_summary', '')
            if summary and isinstance(summary, str):
                pain_point = summary.split('，')[0] if '，' in summary else summary.split(',')[0]

        # 提取核心顾虑
        concern = portrait_data.get('concern', '') or portrait_data.get('核心顾虑', '')
        if not concern:
            buyer_persp = portrait_data.get('buyer_perspective', {})
            if isinstance(buyer_persp, dict):
                concern = buyer_persp.get('obstacles', '') or buyer_persp.get('psychology', '')
            elif isinstance(buyer_persp, str):
                concern = buyer_persp

        # 使用场景
        scenario = portrait_data.get('scenario', '') or portrait_data.get('使用场景', '')
        if not scenario:
            user_persp = portrait_data.get('user_perspective', {})
            if isinstance(user_persp, dict):
                scenario = user_persp.get('current_state', '')

        # 清洗字符串中的引号（防止生成无效的 title）
        def clean(s):
            if not isinstance(s, str):
                return ''
            s = s.replace('"', ' ').replace("'", ' ').strip()
            # 去除多余空格
            s = re.sub(r'\s+', ' ', s)
            return s[:50]

        identity = clean(identity)
        pain_point = clean(pain_point)
        concern = clean(concern)
        scenario = clean(scenario)

        # 如果没有任何画像信息，退化为通用模板
        if not any([identity, pain_point, concern, scenario]):
            core = business_description or '该业务'
            return self._get_generic_library(core)

        # 基于画像构建选题标题模板
        # 标题结构：围绕用户身份 + 痛点场景 + 解决方案导向

        # 判断是否是对商家/服务的需求（如"找XX"、"买XX"、"用XX"）
        # 还是B端商家的营销需求
        is_customer_topic = True  # 默认以C端用户视角

        # 从 identity 判断用户身份
        customer_role = identity if identity else '用户'
        problem_desc = pain_point if pain_point else '有需求但不知如何选择'
        worry_desc = concern if concern else '担心选错/被坑'
        scene_desc = scenario if scenario else '日常'

        # 提取痛点中的关键词用于生成标题
        pain_keywords = []
        if pain_point:
            pain_keywords = re.findall(r'[\u4e00-\u9fa5]{2,10}', pain_point)
            pain_keywords = [k for k in pain_keywords if len(k) >= 2][:5]

        concern_keywords = []
        if concern:
            concern_keywords = re.findall(r'[\u4e00-\u9fa5]{2,10}', concern)
            concern_keywords = [k for k in concern_keywords if len(k) >= 2][:5]

        topics = []

        # ── 前置观望种草盘（12条） ──
        # 标题原则：必须包含「身份」+ 「具体痛点场景」+ 「用户真正会搜的表达」
        # 禁止：「XXX的正确认知」「XXX的底层逻辑」「XXX的真相」等无实质的标题格式
        topics.append({
            'title': f'{customer_role}面对{pain_point}，到底该怎么办？',
            'type_key': 'cause',
            'type_name': '原因分析类',
            'source': '原因分析系列',
            'priority': 'P0',
            'keywords': pain_keywords[:3],
            'reason': f'直面{customer_role}核心困惑，认知教育，种草型',
            'publish_timing': '周末晚间',
            'content_direction': '种草型',
            'content_hints': '痛点场景 + 原因拆解'
        })

        # 2. 对比选型类 - 围绕痛点的不同解决方案对比
        topics.append({
            'title': f'{pain_point}怎么办？不同方案各有什么优缺点？',
            'type_key': 'compare',
            'type_name': '对比选型类',
            'source': '对比选型系列',
            'priority': 'P0',
            'keywords': pain_keywords[:3],
            'reason': f'帮助{customer_role}做选择对比，种草型',
            'publish_timing': '周末晚间',
            'content_direction': '种草型',
            'content_hints': '方案对比 + 优缺点分析'
        })

        # 3. 原因分析类 - 深入根因
        topics.append({
            'title': f'为什么{customer_role}总是{pain_point}？看完就知道了',
            'type_key': 'cause',
            'type_name': '原因分析类',
            'source': '原因分析系列',
            'priority': 'P1',
            'keywords': pain_keywords[:3],
            'reason': f'深入分析{customer_role}遇到问题的根因，种草型',
            'publish_timing': '工作日下午',
            'content_direction': '种草型',
            'content_hints': '原因拆解 + 机理说明'
        })

        # 4. 避坑指南类 - 常见误区
        topics.append({
            'title': f'处理{pain_point}，这几种做法千万别用',
            'type_key': 'pitfall',
            'type_name': '避坑指南类',
            'source': '避坑指南系列',
            'priority': 'P1',
            'keywords': pain_keywords[:3],
            'reason': f'帮助{customer_role}避免常见错误，种草型',
            'publish_timing': '周末晚间',
            'content_direction': '种草型',
            'content_hints': '反面案例 + 正确做法'
        })

        # 5. 避坑指南类 - 选购误区
        topics.append({
            'title': f'关于{pain_point}，90%的{customer_role}都踩过这些坑',
            'type_key': 'pitfall',
            'type_name': '避坑指南类',
            'source': '避坑指南系列',
            'priority': 'P0',
            'keywords': pain_keywords[:3],
            'reason': f'高共鸣避坑内容，易引发转发，种草型',
            'publish_timing': '周末晚间',
            'content_direction': '种草型',
            'content_hints': '踩坑场景 + 避坑指南'
        })

        # 6. 认知颠覆类 - 打破常见误解
        topics.append({
            'title': f'处理{pain_point}，这么多年你可能都做错了',
            'type_key': 'rethink',
            'type_name': '认知颠覆类',
            'source': '认知颠覆系列',
            'priority': 'P2',
            'keywords': pain_keywords[:3],
            'reason': f'颠覆{customer_role}的固有认知，种草型',
            'publish_timing': '周末晚间',
            'content_direction': '种草型',
            'content_hints': '错误认知 + 正确认知对比'
        })

        # 7. 认知颠覆类
        topics.append({
            'title': f'别再误解了！{pain_point}其实没那么复杂',
            'type_key': 'rethink',
            'type_name': '认知颠覆类',
            'source': '认知颠覆系列',
            'priority': 'P2',
            'keywords': pain_keywords[:3],
            'reason': f'打破偏见，建立正确认知，种草型',
            'publish_timing': '周末晚间',
            'content_direction': '种草型',
            'content_hints': '打破误解 + 真相说明'
        })

        # 8. 场景细分类 - 精准人群
        topics.append({
            'title': f'{customer_role}遇到{pain_point}，不同情况怎么处理？',
            'type_key': 'scene',
            'type_name': '场景细分类',
            'source': '场景细分系列',
            'priority': 'P2',
            'keywords': pain_keywords[:2] + concern_keywords[:2],
            'reason': f'精准人群细分，提高代入感，种草型',
            'publish_timing': '工作日下午',
            'content_direction': '种草型',
            'content_hints': '场景分类 + 针对性方案'
        })

        # 9. 知识教程类 - 知识科普
        topics.append({
            'title': f'关于{pain_point}，一篇文章讲透底层逻辑',
            'type_key': 'tutorial',
            'type_name': '知识教程类',
            'source': '知识教程系列',
            'priority': 'P1',
            'keywords': pain_keywords[:3],
            'reason': f'系统性知识科普，种草型',
            'publish_timing': '工作日午间',
            'content_direction': '种草型',
            'content_hints': '系统性知识 + 新手友好'
        })

        # 10. 知识教程类
        topics.append({
            'title': f'{pain_point}完全指南，看完从小白变专家',
            'type_key': 'tutorial',
            'type_name': '知识教程类',
            'source': '知识教程系列',
            'priority': 'P1',
            'keywords': pain_keywords[:3],
            'reason': f'知识科普，种草型',
            'publish_timing': '工作日午间',
            'content_direction': '种草型',
            'content_hints': '系统知识 + 实操指南'
        })

        # 11. 地域精准类（如果有地域信息）
        topics.append({
            'title': f'{pain_point}本地攻略，这几个地方最靠谱',
            'type_key': 'region',
            'type_name': '地域精准类',
            'source': '地域精准系列',
            'priority': 'P3',
            'keywords': pain_keywords[:2],
            'reason': f'本地流量，种草型',
            'publish_timing': '周末晚间',
            'content_direction': '种草型',
            'content_hints': '本地化 + 地域特色'
        })

        # 12. 价格行情类
        topics.append({
            'title': f'{pain_point}需要花多少钱？这笔账给你算清楚了',
            'type_key': 'price',
            'type_name': '行情价格类',
            'source': '行情价格系列',
            'priority': 'P2',
            'keywords': concern_keywords[:3],
            'reason': f'价格透明度，种草型',
            'publish_timing': '周末晚间',
            'content_direction': '种草型',
            'content_hints': '价格构成 + 性价比分析'
        })

        # ── 刚需痛点盘（5条） ──
        # 13. 痛点解决类 - 核心痛点解决方案
        topics.append({
            'title': f'{pain_point}，看完这篇你就知道怎么办了',
            'type_key': 'pain_point',
            'type_name': '痛点解决类',
            'source': '刚需痛点盘',
            'priority': 'P0',
            'keywords': pain_keywords[:3],
            'reason': f'直面{customer_role}核心痛点，转化型',
            'publish_timing': '工作日午间',
            'content_direction': '转化型',
            'content_hints': '痛点场景 + 解决方案 + 引导行动'
        })

        # 14. 痛点解决类
        topics.append({
            'title': f'面对{pain_point}，最有效的解决方法是什么？',
            'type_key': 'pain_point',
            'type_name': '痛点解决类',
            'source': '刚需痛点盘',
            'priority': 'P0',
            'keywords': pain_keywords[:3],
            'reason': f'提供解决方案，转化型',
            'publish_timing': '工作日下午',
            'content_direction': '转化型',
            'content_hints': '方案推荐 + 使用效果'
        })

        # 15. 决策安心类 - 解决顾虑
        topics.append({
            'title': f'{worry_desc}？看完你就彻底放心了',
            'type_key': 'decision_encourage',
            'type_name': '决策安心类',
            'source': '刚需痛点盘',
            'priority': 'P0',
            'keywords': concern_keywords[:3],
            'reason': f'打消{customer_role}付费顾虑，转化型',
            'publish_timing': '工作日下午',
            'content_direction': '转化型',
            'content_hints': '顾虑解答 + 安心保障'
        })

        # 16. 决策安心类
        topics.append({
            'title': f'担心{worry_desc}？看完这篇不再纠结',
            'type_key': 'decision_encourage',
            'type_name': '决策安心类',
            'source': '刚需痛点盘',
            'priority': 'P0',
            'keywords': concern_keywords[:3],
            'reason': f'消除决策障碍，临门一脚，转化型',
            'publish_timing': '工作日下午',
            'content_direction': '转化型',
            'content_hints': '打消顾虑 + 建立信心'
        })

        # 17. 效果验证类
        topics.append({
            'title': f'{pain_point}处理效果好吗？真实案例告诉你',
            'type_key': 'effect_proof',
            'type_name': '效果验证类',
            'source': '刚需痛点盘',
            'priority': 'P1',
            'keywords': pain_keywords[:2] + concern_keywords[:2],
            'reason': f'效果验证，建立信任，转化型',
            'publish_timing': '周末晚间',
            'content_direction': '转化型',
            'content_hints': '前后对比 + 真实案例'
        })

        # ── 使用配套搜后种草盘（3条） ──
        # 18. 实操技巧类
        topics.append({
            'title': f'{pain_point}处理心得，看完少走弯路',
            'type_key': 'skill',
            'type_name': '实操技巧类',
            'source': '使用配套盘',
            'priority': 'P1',
            'keywords': pain_keywords[:3],
            'reason': f'实操方法，种草型',
            'publish_timing': '工作日下午',
            'content_direction': '种草型',
            'content_hints': '实操经验 + 注意事项'
        })

        # 19. 工具耗材类
        topics.append({
            'title': f'处理{pain_point}，这些工具和办法少不了',
            'type_key': 'tools',
            'type_name': '工具耗材类',
            'source': '使用配套盘',
            'priority': 'P2',
            'keywords': pain_keywords[:2],
            'reason': f'配套工具推荐，种草型',
            'publish_timing': '工作日下午',
            'content_direction': '种草型',
            'content_hints': '工具推荐 + 使用方法'
        })

        # 20. 情感故事类
        topics.append({
            'title': f'作为一个{customer_role}，处理{pain_point}这些年的真实感受',
            'type_key': 'emotional',
            'type_name': '情感故事类',
            'source': '使用配套盘',
            'priority': 'P3',
            'keywords': pain_keywords[:2],
            'reason': f'情感共鸣，种草型',
            'publish_timing': '周末晚间',
            'content_direction': '种草型',
            'content_hints': '个人故事 + 情感触动'
        })

        # 清理标题中的无效占位符
        for topic in topics:
            title = topic['title']
            # 清理连续空格
            title = re.sub(r'\s+', ' ', title)
            # 清理句末重复标点
            title = re.sub(r'([。！？])\1+', r'\1', title)
            # 清理可能的 "的怎么办" 句式
            title = re.sub(r'的怎么办', '怎么办', title)
            title = re.sub(r'怎么办怎么办', '怎么办', title)
            # 限制标题长度
            if len(title) > 35:
                title = title[:34] + '…'
            topic['title'] = title

        # 如果标题中仍有无法填充的空值（如所有都是空的），使用通用版
        empty_titles = sum(1 for t in topics if not t['title'] or len(t['title']) < 5)
        if empty_titles > 10:
            return self._get_generic_library(business_description or pain_point or identity or '该业务')

        return {
            'topics': topics,
            'by_type': self._count_by_type(topics),
            'priorities': self._count_by_priority(topics),
        }

    def _get_generic_library(self, core: str) -> Dict:
        """通用选题库（当画像数据完全为空时使用兜底）"""
        return {
            'topics': [
                # ── 前置观望种草盘（12条） ──
                {'title': f'{core}好不好？真实用户反馈来了', 'type_key': 'compare',
                 'type_name': '对比选型类', 'source': '对比选型系列', 'priority': 'P0',
                 'keywords': [], 'reason': '专抓前期迷茫客户，种草型',
                 'publish_timing': '周末晚间', 'content_direction': '种草型', 'content_hints': '真实反馈 + 客观分析'},
                {'title': f'为什么越来越多人选择{core}？3个原因说透了', 'type_key': 'cause',
                 'type_name': '原因分析类', 'source': '原因分析系列', 'priority': 'P1',
                 'keywords': [], 'reason': '认知教育，种草型',
                 'publish_timing': '工作日下午', 'content_direction': '种草型', 'content_hints': '原因拆解 + 行业趋势'},
                {'title': f'{core}怎么选不踩坑？过来人经验分享', 'type_key': 'pitfall',
                 'type_name': '避坑指南类', 'source': '避坑指南系列', 'priority': 'P1',
                 'keywords': [], 'reason': '行业防骗，种草型',
                 'publish_timing': '周末晚间', 'content_direction': '种草型', 'content_hints': '避坑场景 + 正确做法'},
                {'title': f'选{core}前，先搞懂这几点不花冤枉钱', 'type_key': 'upstream',
                 'type_name': '上游科普类', 'source': '上游科普系列', 'priority': 'P1',
                 'keywords': [], 'reason': '上游原料科普，种草型',
                 'publish_timing': '工作日下午', 'content_direction': '种草型', 'content_hints': '原料/材质科普'},
                {'title': f'{core}的价格猫腻，这篇文章全说清了', 'type_key': 'price',
                 'type_name': '行情价格类', 'source': '行情价格系列', 'priority': 'P2',
                 'keywords': [], 'reason': '价格透明度，种草型',
                 'publish_timing': '周末晚间', 'content_direction': '种草型', 'content_hints': '价格构成 + 行情分析'},
                {'title': f'别再被误导了！{core}的真相是这样的', 'type_key': 'rethink',
                 'type_name': '认知颠覆类', 'source': '认知颠覆系列', 'priority': 'P2',
                 'keywords': [], 'reason': '打破认知误区，种草型',
                 'publish_timing': '周末晚间', 'content_direction': '种草型', 'content_hints': '颠覆认知 + 正确认知'},
                {'title': f'{core}入门指南，看完从小白变内行', 'type_key': 'tutorial',
                 'type_name': '知识教程类', 'source': '知识教程系列', 'priority': 'P1',
                 'keywords': [], 'reason': '知识科普，种草型',
                 'publish_timing': '工作日午间', 'content_direction': '种草型', 'content_hints': '系统性知识 + 新手友好'},
                {'title': f'什么样的人最适合{core}？看完就知道了', 'type_key': 'scene',
                 'type_name': '场景细分类', 'source': '场景细分系列', 'priority': 'P2',
                 'keywords': [], 'reason': '精准人群细分，种草型',
                 'publish_timing': '工作日下午', 'content_direction': '种草型', 'content_hints': '人群画像 + 场景匹配'},
                {'title': f'本地找{core}，这几个地方最靠谱', 'type_key': 'region',
                 'type_name': '地域精准类', 'source': '地域精准系列', 'priority': 'P3',
                 'keywords': [], 'reason': '本地流量，种草型',
                 'publish_timing': '周末晚间', 'content_direction': '种草型', 'content_hints': '本地化 + 地域特色'},
                {'title': f'这几种{core}千万别买，后悔都来不及', 'type_key': 'pitfall',
                 'type_name': '避坑指南类', 'source': '避坑指南系列', 'priority': 'P0',
                 'keywords': [], 'reason': '防骗警示，种草型',
                 'publish_timing': '周末晚间', 'content_direction': '种草型', 'content_hints': '反面案例 + 正确选择'},
                {'title': f'关于{core}，80%的人都搞错了这几点', 'type_key': 'rethink',
                 'type_name': '认知颠覆类', 'source': '认知颠覆系列', 'priority': 'P2',
                 'keywords': [], 'reason': '认知纠正，种草型',
                 'publish_timing': '周末晚间', 'content_direction': '种草型', 'content_hints': '纠正误区 + 正确认知'},
                {'title': f'{core}怎么判断好不好？教你三招快速鉴别', 'type_key': 'cause',
                 'type_name': '原因分析类', 'source': '原因分析系列', 'priority': 'P1',
                 'keywords': [], 'reason': '判断标准，种草型',
                 'publish_timing': '工作日下午', 'content_direction': '种草型', 'content_hints': '判断标准 + 实用技巧'},

                # ── 刚需痛点盘（5条） ──
                {'title': f'选择{core}前，先看完这篇少走弯路', 'type_key': 'pain_point',
                 'type_name': '痛点解决类', 'source': '刚需痛点盘', 'priority': 'P0',
                 'keywords': [], 'reason': '直面核心痛点，转化型',
                 'publish_timing': '工作日午间', 'content_direction': '转化型', 'content_hints': '展示痛点场景 + 解决方案 + 引导成交'},
                {'title': f'{core}到底靠不靠谱？看完你就明白了', 'type_key': 'decision_encourage',
                 'type_name': '决策安心类', 'source': '刚需痛点盘', 'priority': 'P0',
                 'keywords': [], 'reason': '打消付费顾虑，临门一脚，转化型',
                 'publish_timing': '工作日下午', 'content_direction': '转化型', 'content_hints': '靠谱验证 + 售后保障 + 口碑案例'},
                {'title': f'{core}效果真的好吗？真实案例告诉你', 'type_key': 'effect_proof',
                 'type_name': '效果验证类', 'source': '刚需痛点盘', 'priority': 'P1',
                 'keywords': [], 'reason': '效果验证，建立信任，转化型',
                 'publish_timing': '周末晚间', 'content_direction': '转化型', 'content_hints': '前后对比 + 真实案例'},
                {'title': f'{core}值不值？算完这笔账就知道了', 'type_key': 'pain_point',
                 'type_name': '痛点解决类', 'source': '刚需痛点盘', 'priority': 'P1',
                 'keywords': [], 'reason': '性价比分析，转化型',
                 'publish_timing': '工作日下午', 'content_direction': '转化型', 'content_hints': '成本分析 + 价值对比'},
                {'title': f'选{core}怕被坑？看完这期彻底放心了', 'type_key': 'decision_encourage',
                 'type_name': '决策安心类', 'source': '刚需痛点盘', 'priority': 'P0',
                 'keywords': [], 'reason': '打消顾虑，转化型',
                 'publish_timing': '工作日下午', 'content_direction': '转化型', 'content_hints': '防坑指南 + 靠谱推荐'},

                # ── 使用配套搜后种草盘（3条） ──
                {'title': f'{core}使用心得，看完少走弯路', 'type_key': 'skill',
                 'type_name': '实操技巧类', 'source': '使用配套盘', 'priority': 'P1',
                 'keywords': [], 'reason': '实操方法，种草型',
                 'publish_timing': '工作日下午', 'content_direction': '种草型', 'content_hints': '实操经验 + 注意事项'},
                {'title': f'用了{core}才发现，这些工具少不了', 'type_key': 'tools',
                 'type_name': '工具耗材类', 'source': '使用配套盘', 'priority': 'P2',
                 'keywords': [], 'reason': '配套工具推荐，种草型',
                 'publish_timing': '工作日下午', 'content_direction': '种草型', 'content_hints': '工具推荐 + 使用方法'},
                {'title': f'做{core}这些年，最深的感悟是什么', 'type_key': 'emotional',
                 'type_name': '情感故事类', 'source': '使用配套盘', 'priority': 'P3',
                 'keywords': [], 'reason': '情感共鸣，种草型',
                 'publish_timing': '周末晚间', 'content_direction': '种草型', 'content_hints': '个人故事 + 情感触动'},
            ],
            'by_type': {
                'compare': 1, 'cause': 2, 'pitfall': 2, 'upstream': 1,
                'price': 1, 'rethink': 2, 'tutorial': 1, 'scene': 1,
                'region': 1, 'pain_point': 2, 'decision_encourage': 2,
                'effect_proof': 1, 'skill': 1, 'tools': 1, 'emotional': 1,
            },
            'priorities': {'P0': 4, 'P1': 8, 'P2': 6, 'P3': 2},
        }

    def _extract_valid_topics_backward(self, text: str) -> list:
        """从后向前查找完整有效的 topic 对象（处理 LLM 返回被截断的情况）

        从文本末尾开始向前扫描，找到所有完整的 { ... } 对象，
        只要对象包含 title/标题/选题 字段就认为是有效选题。
        """
        topics = []
        n = len(text)

        for start in range(n - 2, -1, -1):
            if text[start] != '{':
                continue
            candidate = text[start:]
            if not candidate.strip().startswith('{'):
                continue
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict) and ('title' in obj or '标题' in obj or '选题' in obj):
                    # 找到有效选题，插入列表头部（因为是从后向前找的）
                    topics.insert(0, obj)
                    # 继续向前找下一个
            except json.JSONDecodeError:
                continue

        return topics

    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """估算 token 消耗"""
        return int((len(prompt) / 2) + (len(response) / 2))


# 全局实例
topic_library_generator = TopicLibraryGenerator()
