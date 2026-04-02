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
        {'name': '对比选型类', 'key': 'compare', 'base': '前置观望', 'content_direction': '种草型',
         'desc': 'A与B区别/选型对比/哪种更好/划算对比，品牌分析，种草型', 'priority': 'P0'},
        {'name': '原因分析类', 'key': 'cause', 'base': '前置观望', 'content_direction': '种草型',
         'desc': '为什么会/原因分析/形成机理，认知教育，种草型', 'priority': 'P1'},
        {'name': '上游科普类', 'key': 'upstream', 'base': '前置观望', 'content_direction': '种草型',
         'desc': '原料/材质/供应链/选材鉴别知识，行业上游，种草型', 'priority': 'P1'},
        {'name': '避坑指南类', 'key': 'pitfall', 'base': '前置观望', 'content_direction': '种草型',
         'desc': '避坑/误区/骗局/怎么分辨，行业防骗，种草型', 'priority': 'P1'},
        {'name': '行情价格类', 'key': 'price', 'base': '前置观望', 'content_direction': '种草型',
         'desc': '价格/报价/行情/成本构成，预算参考，种草型', 'priority': 'P2'},
        {'name': '认知颠覆类', 'key': 'rethink', 'base': '前置观望', 'content_direction': '种草型',
         'desc': '打破认知/颠覆常识，易传播，种草型', 'priority': 'P2'},
        {'name': '知识教程类', 'key': 'tutorial', 'base': '前置观望', 'content_direction': '种草型',
         'desc': '主动搜索，精准流量，种草型', 'priority': 'P1'},
        {'name': '场景细分类', 'key': 'scene', 'base': '前置观望', 'content_direction': '种草型',
         'desc': '精准人群细分，种草型', 'priority': 'P2'},
        {'name': '地域精准类', 'key': 'region', 'base': '前置观望', 'content_direction': '种草型',
         'desc': '本地流量，种草型', 'priority': 'P3'},

        # ②刚需痛点盘（30%，转化型）：强化决策安心，解决临门一脚
        {'name': '痛点解决类', 'key': 'pain_point', 'base': '刚需痛点', 'content_direction': '转化型',
         'desc': '直面核心痛点，提供解决方案，引导成交，转化型', 'priority': 'P0'},
        {'name': '决策安心类', 'key': 'decision_encourage', 'base': '刚需痛点', 'content_direction': '转化型',
         'desc': '靠谱吗/会不会坑/售后怎么样/别人怎么选，打消顾虑，转化型', 'priority': 'P0'},
        {'name': '效果验证类', 'key': 'effect_proof', 'base': '刚需痛点', 'content_direction': '转化型',
         'desc': '产品效果对比/使用前后对比/真实案例，建立信任，转化型', 'priority': 'P1'},

        # ③使用配套搜后种草盘（20%，种草型）：使用后实操留存
        {'name': '实操技巧类', 'key': 'skill', 'base': '使用配套', 'content_direction': '种草型',
         'desc': '使用后方法/步骤流程/晾晒保存/配方调料/辅料佐料，种草型', 'priority': 'P1'},
        {'name': '工具耗材类', 'key': 'tools', 'base': '使用配套', 'content_direction': '种草型',
         'desc': '专用工具/周边耗材/后期养护推荐，种草型', 'priority': 'P2'},
        {'name': '行业关联系列类', 'key': 'industry', 'base': '使用配套', 'content_direction': '种草型',
         'desc': '上下游关联/复购引导/升级推荐，种草型', 'priority': 'P2'},
        {'name': '季节营销类', 'key': 'seasonal', 'base': '使用配套', 'content_direction': '种草型',
         'desc': '时效性强，季节关联，种草型', 'priority': 'P2'},
        {'name': '节日营销类', 'key': 'festival', 'base': '使用配套', 'content_direction': '种草型',
         'desc': '节日刚需，复购引导，种草型', 'priority': 'P1'},
        {'name': '情感故事类', 'key': 'emotional', 'base': '使用配套', 'content_direction': '种草型',
         'desc': '易引发转发，种草型', 'priority': 'P3'},
    ]

    # 三套选题配比（内容阶段联动）
    STAGE_TOPIC_RATIO_MAP = {
        '起号阶段': {
            '前置观望搜前种草盘': 0.90,
            '刚需痛点盘': 0.00,
            '使用配套搜后种草盘': 0.10,
            'description': '90%前置种草 + 0%刚需转化 + 10%使用配套',
            'tag_strategy': '种草标签为主，无转化标签',
        },
        '成长阶段': {
            '前置观望搜前种草盘': 0.60,
            '刚需痛点盘': 0.15,
            '使用配套搜后种草盘': 0.25,
            'description': '60%前置种草 + 15%刚需转化 + 25%使用配套',
            'tag_strategy': '种草标签60% + 转化标签40%',
        },
        '成熟阶段': {
            '前置观望搜前种草盘': 0.30,
            '刚需痛点盘': 0.50,
            '使用配套搜后种草盘': 0.20,
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
                "【强制要求】你必须严格按照用户提供的业务描述生成选题！\n"
                "禁止添加任何未提供的信息！禁止编造产品名称！\n"
                "\n"
                "你是一位抖音爆款选题策划专家，精通本地商家内容营销。\n"
                "必须严格按照JSON格式输出，选题必须有差异化、能引发共鸣。"
            )
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat(messages)

            # 解析结果
            result = self._parse_response(response, business_info.get('business_description', ''))

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
            logger.error("[TopicLibraryGenerator] Error: %s", e)
            return {'success': False, 'error': str(e)}

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
            '目标客户身份': identity,
            '核心痛点': pain_point,
            '核心顾虑': concern,
            '使用场景': scenario,

            # 业务
            '业务描述': business_info.get('business_description', ''),
            '行业': business_info.get('industry', ''),
            '产品': ', '.join(business_info.get('products', [])),
            '地域': business_info.get('region', ''),
            '目标客户': business_info.get('target_customer', ''),

            # 实时
            '当前季节': realtime.get('当前季节', ''),
            '月份名称': realtime.get('月份名称', ''),
            '季节消费特点': realtime.get('季节消费特点', ''),
            '当前节日': realtime.get('当前节日', '无'),
            '当前节气': realtime.get('当前节气', '无'),

            # 关键词
            '关键词库': keywords_text,
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
① **前置观望搜前种草盘（50%，种草型）**：对比选型/原因分析/上游科普/避坑指南/行情价格，专抓前期迷茫、做对比、查原因的潜在客户。选题类型：对比选型类、原因分析类、上游科普类、避坑指南类、行情价格类、认知颠覆类、知识教程类、场景细分类、地域精准类
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

## 实时上下文
- 当前季节：{context['当前季节']}（{context['月份名称']}）
- 季节消费特点：{context['季节消费特点']}
- 当前节日：{context['当前节日']}
- 当前节气：{context['当前节气']}

## 关键词参考（选题须与关键词关联）
{context['关键词库'] or '（无关键词库，将根据业务描述生成）'}

## 选题分类要求（严格对应三盘，各选题的 content_direction 已标注，强制归类）

{type_rules}

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
- title: 选题标题
- type_key: 选题类型键名
- type_name: 选题类型名称
- priority: 优先级（P0/P1/P2/P3）
- source: 来源说明
- keywords: 关键词列表
- content_direction: **必须严格遵守：种草型=种草内容；转化型=转化内容**
- recommended_reason: 推荐理由

## 输出数量要求
生成恰好 **20个** 选题，三大底盘分配严格遵循当前阶段配比。
生成恰好{topic_count}个选题：前置观望搜前种草盘约{stage_config.get('前置观望搜前种草盘', 0.6) * topic_count:.0f}个、刚需痛点盘约{stage_config.get('刚需痛点盘', 0.15) * topic_count:.0f}个、使用配套搜后种草盘约{stage_config.get('使用配套搜后种草盘', 0.25) * topic_count:.0f}个。

请生成JSON格式的选题库："""

    def _parse_response(self, response: str, business_description: str = '') -> Dict:
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
                except json.JSONDecodeError:
                    pass
            
            # 方法2：正则匹配 JSON 对象
            if result is None:
                json_match = re.search(r'\{[\s\S]*\}', clean_response)
                if json_match:
                    json_str = json_match.group(0)
                    json_str = json_str.replace('{{', '{').replace('}}', '}')
                    try:
                        result = json.loads(json_str)
                        if result:
                            result = self._convert_to_standard_format(result)
                    except json.JSONDecodeError as e:
                        logger.debug("[TopicLibraryGenerator] 正则匹配JSON解析失败: %s", e)
            
            # 方法3：修复常见 JSON 错误后重试
            if result is None:
                fixed = self._fix_json_errors(clean_response)
                if fixed:
                    try:
                        result = json.loads(fixed)
                        if result:
                            result = self._convert_to_standard_format(result)
                    except json.JSONDecodeError as e:
                        logger.debug("[TopicLibraryGenerator] 修复后仍解析失败: %s", e)
            
            # 方法4：更激进的修复
            if result is None:
                # 尝试提取 "topic_library" 或 "topics" 部分的 JSON
                topics_match = re.search(r'"topics"\s*:\s*\[([\s\S]*)\]', clean_response)
                if topics_match:
                    topics_str = '[' + topics_match.group(1)
                    # 找到结束括号
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
                        except:
                            pass
                
                # 尝试提取 "topic_library" 对象
                if result is None:
                    lib_match = re.search(r'"topic_library"\s*:\s*\{([\s\S]*)\}', clean_response)
                    if lib_match:
                        lib_str = '{"topic_library": {' + lib_match.group(1)
                        # 找到结束括号
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
                            except:
                                pass

            # 方法5：解析直接返回的选题数组（无外层包装）
            if result is None:
                try:
                    # 尝试匹配数组格式 [...]
                    array_match = re.search(r'\[\s*\{', clean_response)
                    if array_match:
                        # 提取从第一个 { 开始的整个 JSON
                        start_pos = array_match.start()
                        # 尝试找到一个能解析的结束位置
                        for end_pos in range(len(clean_response), start_pos, -1):
                            test_str = clean_response[start_pos:end_pos]
                            try:
                                parsed = json.loads(test_str)
                                if isinstance(parsed, list) and len(parsed) > 0:
                                    result = {'topics': parsed}
                                    logger.debug("[TopicLibraryGenerator] 方法5成功提取%d个选题", len(parsed))
                                    break
                            except:
                                continue
                except Exception as e:
                    logger.debug("[TopicLibraryGenerator] 方法5解析失败: %s", e)

            # 方法6：逐个提取 JSON 对象并组合
            if result is None:
                try:
                    topics = []
                    # 查找所有完整的 JSON 对象 { ... }
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
                        logger.debug("[TopicLibraryGenerator] 方法6成功提取%d个选题", len(topics))
                except Exception as e:
                    logger.debug("[TopicLibraryGenerator] 方法6解析失败: %s", e)

            if result is None:
                raise ValueError("所有JSON解析方式均失败")
            
            # 处理 emoji key（如 "📚选题库" -> "topic_library"）
            result = self._normalize_keys(result)
            
            # 转换为标准格式
            result = self._convert_to_standard_format(result)
            
            return self._validate_and_fill(result, business_description)
            
        except json.JSONDecodeError as e:
            logger.error("[TopicLibraryGenerator] JSON解析失败: %s", e)
            logger.error("[TopicLibraryGenerator] 原始响应前500字符: %s", response[:500])
            return self._get_default_library(business_description)
        except Exception as e:
            logger.error("[TopicLibraryGenerator] Parse error: %s", e)
            logger.error("[TopicLibraryGenerator] 原始响应前500字符: %s", response[:500])
            return self._get_default_library(business_description)

    def _fix_json_errors(self, json_str: str) -> str:
        """修复常见 JSON 格式错误"""
        import re
        
        # 移除注释（// 开头的行）
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
        
        # 移除不可见控制字符（除 \n, \r, \t 外）
        json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', json_str)
        
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

    def _convert_to_standard_format(self, result: Dict) -> Dict:
        """将 LLM 返回的任意格式转换为标准格式"""
        if not isinstance(result, dict):
            return result
        
        # 已经是标准格式
        if 'topics' in result and isinstance(result.get('topics'), list):
            return result
        
        # 尝试转换 "选题库" 格式
        # 例如: {"选题库": {...}} 或 {"选题": [...]} -> {"topics": [...]}
        converted = {
            'topics': [],
        }
        
        # 尝试从多个可能的结构中提取选题
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
        
        # 处理选题列表
        if topics_data and isinstance(topics_data, list):
            for item in topics_data:
                if isinstance(item, dict):
                    # 提取选题字段
                    topic_base = item.get('problem_base', '')
                    type_key = item.get('type') or item.get('分类', 'unknown')
                    type_key_dir = self._get_type_key_map().get(type_key, '种草型')
                    topic = {
                        'title': item.get('标题') or item.get('title') or item.get('选题'),
                        'type_key': type_key,
                        'type_name': item.get('类型名称') or item.get('type_name') or '',
                        'priority': item.get('优先级') or item.get('priority') or 'P2',
                        'source': item.get('来源') or item.get('source') or '',
                        'keywords': item.get('关键词') or item.get('keywords') or [],
                        'reason': item.get('原因') or item.get('reason') or item.get('说明', ''),
                        'publish_timing': item.get('发布时间') or item.get('publish_timing') or '',
                        'content_hints': item.get('内容提示') or item.get('content_hints') or '',
                        'content_direction': item.get('content_direction') or type_key_dir,
                    }
                    if topic['title']:
                        converted['topics'].append(topic)
        
        # 如果没有提取到任何选题，返回原结果（让后续验证处理）
        if not converted['topics']:
            # 尝试在 result 的任何位置找选题列表
            for key, value in result.items():
                if isinstance(value, list) and len(value) > 0:
                    first_item = value[0]
                    if isinstance(first_item, dict) and ('标题' in first_item or 'title' in first_item or '选题' in first_item):
                        # 这是一个选题列表
                        for item in value:
                            if isinstance(item, dict):
                                topic_base = item.get('problem_base', '')
                                topic = {
                                    'title': item.get('标题') or item.get('title') or item.get('选题'),
                                    'type_key': item.get('类型') or item.get('type') or item.get('分类', 'unknown'),
                                    'type_name': item.get('类型名称') or item.get('type_name') or '',
                                    'priority': item.get('优先级') or item.get('priority') or 'P2',
                                    'source': item.get('来源') or item.get('source') or '',
                                    'keywords': item.get('关键词') or item.get('keywords') or [],
                                    'reason': item.get('原因') or item.get('reason') or item.get('说明', ''),
                                    'publish_timing': item.get('发布时间') or item.get('publish_timing') or '',
                                    'content_hints': item.get('内容提示') or item.get('content_hints') or '',
                                    'content_direction': item.get('content_direction') or self._infer_content_direction(topic_base),
                                }
                                if topic['title']:
                                    converted['topics'].append(topic)
                        break
        
        if not converted['topics']:
            return result  # 返回原结果
        
        return converted

    def _validate_and_fill(self, result: Dict, business_description: str = '') -> Dict:
        """验证并补充选题库"""
        default = self._get_default_library(business_description)

        # 处理可能的 key 变化
        if 'topics' not in result:
            # 可能用其他 key 名（如 normalized 后的）
            for key in ['topics', '选题库', 'topic_list', 'items']:
                if key in result:
                    result['topics'] = result.pop(key)
                    break
        
        if 'topics' not in result or not result['topics']:
            result['topics'] = default['topics']

        # 确保 topics 是列表
        if not isinstance(result['topics'], list):
            result['topics'] = default['topics']

        # 补充缺失字段
        base_to_direction = {'刚需痛点': '转化型', '前置观望': '种草型', '使用配套': '种草型'}
        type_key_to_direction = self._get_type_key_map()
        for topic in result['topics']:
            if not isinstance(topic, dict):
                continue
            if 'type_key' not in topic:
                topic['type_key'] = topic.get('type', topic.get('分类', 'unknown'))
            if 'priority' not in topic:
                topic['priority'] = topic.get('优先级', 'P2')
            if 'type_name' not in topic:
                topic['type_name'] = topic.get('type_name', topic.get('类型', ''))
            # content_direction：先从 type_key 推导，再从 base 兜底
            if 'content_direction' not in topic or not topic['content_direction']:
                topic['content_direction'] = type_key_to_direction.get(
                    topic.get('type_key', ''),
                    base_to_direction.get(topic.get('problem_base', ''), '种草型')
                )

        if 'by_type' not in result:
            result['by_type'] = self._count_by_type(result['topics'])

        if 'priorities' not in result:
            result['priorities'] = self._count_by_priority(result['topics'])

        return result

    def _infer_content_direction(self, topic_base: str) -> str:
        """从选题底盘推导内容方向"""
        direction_map = {
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

    def _get_default_library(self, business_description: str = '') -> Dict:
        """获取默认选题库（当LLM生成失败时使用）

        Args:
            business_description: 业务描述，用于生成通用占位选题
        """
        # 从业务描述提取核心关键词作为占位选题的原料
        core = business_description or '业务'
        return {
            'topics': [
                {
                    'title': f'{core}好不好？真实用户反馈来了',
                    'type_name': '对比选型类',
                    'type_key': 'compare',
                    'source': '对比选型系列',
                    'priority': 'P0',
                    'keywords': [],
                    'reason': '专抓前期迷茫客户，种草型',
                    'publish_timing': '周末晚间',
                    'content_direction': '种草型',
                    'content_hints': '真实反馈 + 客观分析',
                },
                {
                    'title': f'为什么越来越多人选择{core}？3个原因说透了',
                    'type_name': '原因分析类',
                    'type_key': 'cause',
                    'source': '原因分析系列',
                    'priority': 'P1',
                    'keywords': [],
                    'reason': '认知教育，种草型',
                    'publish_timing': '工作日下午',
                    'content_direction': '种草型',
                    'content_hints': '原因拆解 + 行业趋势',
                },
                {
                    'title': f'选择{core}前，先看完这篇少走弯路',
                    'type_name': '痛点解决类',
                    'type_key': 'pain_point',
                    'source': '刚需痛点盘',
                    'priority': 'P0',
                    'keywords': [],
                    'reason': '直面核心痛点，转化型',
                    'publish_timing': '工作日午间',
                    'content_direction': '转化型',
                    'content_hints': '展示痛点场景 + 解决方案 + 引导成交',
                },
                {
                    'title': f'{core}怎么选不踩坑？过来人经验分享',
                    'type_name': '避坑指南类',
                    'type_key': 'pitfall',
                    'source': '避坑指南系列',
                    'priority': 'P1',
                    'keywords': [],
                    'reason': '行业防骗，种草型',
                    'publish_timing': '周末晚间',
                    'content_direction': '种草型',
                    'content_hints': '避坑场景 + 正确做法',
                },
                {
                    'title': f'{core}到底靠不靠谱？看完你就明白了',
                    'type_name': '决策安心类',
                    'type_key': 'decision_encourage',
                    'source': '刚需痛点盘',
                    'priority': 'P0',
                    'keywords': [],
                    'reason': '打消付费顾虑，临门一脚，转化型',
                    'publish_timing': '工作日下午',
                    'content_direction': '转化型',
                    'content_hints': '靠谱验证 + 售后保障 + 口碑案例',
                },
                {
                    'title': f'{core}使用心得，看完少走弯路',
                    'type_name': '实操技巧类',
                    'type_key': 'skill',
                    'source': '使用配套盘',
                    'priority': 'P1',
                    'keywords': [],
                    'reason': '实操方法，种草型',
                    'publish_timing': '工作日下午',
                    'content_direction': '种草型',
                    'content_hints': '实操经验 + 注意事项',
                },
            ],
            'by_type': {'compare': 1, 'cause': 1, 'pain_point': 1, 'pitfall': 1, 'decision_encourage': 1, 'skill': 1},
            'priorities': {'P0': 2, 'P1': 3, 'P2': 0, 'P3': 0},
        }

    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """估算 token 消耗"""
        return int((len(prompt) / 2) + (len(response) / 2))


# 全局实例
topic_library_generator = TopicLibraryGenerator()
