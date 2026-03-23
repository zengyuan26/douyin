"""
公开内容生成平台 - 内容生成服务

功能：
1. 基于模板和关键词生成内容
2. AI增强（可选）
3. 生成标题方案
4. 生成标签方案
5. 生成图文内容
"""

import time
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from models.public_models import (
    PublicUser, PublicGeneration, PublicLLMCallLog
)
from models.models import db, AnalysisDimension
from services.public_template_matcher import template_matcher
from services.public_quota_manager import quota_manager


class ContentGenerator:
    """
    内容生成器

    策略：
    1. 免费用户：使用预设模板 + 基础关键词组合
    2. 付费用户：AI增强 + 更多模板选择
    """

    # Token消耗估算
    TOKEN_ESTIMATE = {
        'keyword_only': {'input': 500, 'output': 800, 'total': 1300},
        'with_ai': {'input': 800, 'output': 2000, 'total': 2800},
    }

    # 模型单价（gpt-4o-mini，元/1M tokens）
    MODEL_PRICE = {
        'input': 1.5,   # ¥1.5/1M
        'output': 6.0,  # ¥6.0/1M
    }

    # C 端画像中禁止写入「痛点状态/目标」的 B2B 用语（易与维度库混淆，出现「奶粉+想要增长」类离谱组合）
    _C_END_FORBIDDEN_PAIN_GOAL_SUBSTR: tuple = (
        '遇到瓶颈', '想要增长', '想要转型', '寻求突破', '规模化增长', '规模化',
        '年营收', '营收', 'GMV', '团队规模', '融资', '天使轮', '上市', 'IPO',
        '创始人', '董事长', 'CEO', '总监', '副总裁', 'VP', '拓客', '涨销量',
    )

    # C端业务类型下，特定维度用生活化语义覆盖（与 public_api.py 共享）
    _LOCAL_CONSUMER_DIM_OPTIONS: Dict[str, List[str]] = {
        'development_stage': ['刚起步', '小有规模', '成熟稳定', '转型探索'],
        'revenue_scale':     ['小本经营', '年入数十万', '年入百万级', '规模化运营'],
        'team_size':         ['个人/夫妻店', '3-10人', '10-50人', '50人以上'],
        'work_years':        ['1-3年', '3-5年', '5-10年', '10年以上'],
    }

    @classmethod
    def _c_end_pain_goal_has_b2b_leak(cls, text: str) -> bool:
        if not text or not str(text).strip():
            return False
        s = str(text).strip()
        return any(x in s for x in cls._C_END_FORBIDDEN_PAIN_GOAL_SUBSTR)

    # C 端痛点里若出现这些「具体状态/对象」锚点，则不再视为纯选品焦虑，避免被领域池首项覆盖
    _C_END_PAIN_STATE_ANCHORS: Tuple[str, ...] = (
        '宝宝', '婴儿', '幼儿', '新生儿', '乳糖', '转奶', '过敏', '湿疹', '拉肚子', '大便', '厌奶',
        '身高', '体重', '发育', '辅食', '宠物', '猫', '狗', '粮', '老人', '爸妈', '长辈', '三高',
        '血压', '血糖', '血脂', '腿脚', '学生', '孩子', '成绩', '注意力', '皮肤', '痘痘', '闭口',
    )

    @classmethod
    def _batch_pain_is_generic_choice_anxiety(cls, pain: str) -> bool:
        """纯「信息多/不会选/焦虑」类表述，且未落到使用者具体状态 → 与领域长尾池不对齐。"""
        p = (pain or '').strip()
        if not p:
            return True
        anxiety_markers = (
            '信息太多', '信息多', '不知道哪个', '不知道哪款', '选择焦虑', '比较焦虑', '陷入焦虑',
            '拿不准', '不敢下手', '不敢买', '多方比较',
        )
        if not any(m in p for m in anxiety_markers):
            return False
        return not any(a in p for a in cls._C_END_PAIN_STATE_ANCHORS)

    @classmethod
    def _batch_goal_is_generic_c_end(cls, goal: str) -> bool:
        """目标仍停留在「买得放心/省心」等抽象结果，未写使用者状态。"""
        g = (goal or '').strip()
        if not g:
            return True
        if g in ('买得更放心', '买得更值', '买得更方便', '买得更适合', '买得更省心', '省心', '更放心'):
            return True
        if any(a in g for a in cls._C_END_PAIN_STATE_ANCHORS):
            return False
        if len(g) <= 8 and ('买' in g or '放心' in g or '值' in g):
            return True
        return False

    @classmethod
    def _pain_goal_overlaps_domain_option(cls, text: str, domain_opts: List[str]) -> bool:
        """判断当前文案是否与领域细分选项足够接近（目标支持顿号拆分匹配）。"""
        if not text or not domain_opts:
            return False
        t = text.strip()
        for d in domain_opts:
            if not d:
                continue
            if t == d or t in d or d in t:
                return True
            if len(d) >= 8 and d[:12] in t:
                return True
            if len(t) >= 8 and t[:12] in d:
                return True
            # 「宝宝不拉肚子、大便正常」类：任一片段 ≥4 字互含即视为对齐
            for part in re.split(r'[、，,;；]+', d):
                part = part.strip()
                if len(part) >= 4 and (part in t or t in part):
                    return True
            for part in re.split(r'[、，,;；]+', t):
                part = part.strip()
                if len(part) >= 4 and part in d:
                    return True
        return False

    @classmethod
    def _align_batch_pain_goal_to_domain(
        cls,
        batch_pain: str,
        batch_goal: str,
        business_desc: str,
        user_goal_set: bool,
    ) -> tuple:
        """
        当业务描述能命中领域细分池时，若整批统一的痛点/目标仍偏抽象，
        用领域池首项（或更易切长尾的项）对齐顶部「本批共用」横幅与 5 条字段。
        user_goal 由用户显式指定时不改 goal。
        """
        domain = cls._detect_domain_hints(business_desc or '')
        pains = domain.get('pain_point_commonality') or []
        goals = domain.get('goal') or []
        if not pains and not goals:
            return batch_pain, batch_goal

        bp, bg = (batch_pain or '').strip(), (batch_goal or '').strip()
        # 痛点：纯选品焦虑且无状态锚点时，与领域池首项对齐（避免横幅长期「信息太多…」）
        if pains and cls._batch_pain_is_generic_choice_anxiety(bp):
            bp = pains[0]
        if not user_goal_set and goals:
            if not cls._pain_goal_overlaps_domain_option(bg, goals):
                if cls._batch_goal_is_generic_c_end(bg):
                    bg = goals[0]
        return bp, bg

    @classmethod
    def _clean_persona_description_after_batch_unify(
        cls,
        description: str,
        batch_pain: str,
        batch_goal: str,
    ) -> str:
        """
        顶部横幅已展示本批痛点+目标时，卡片正文不应再以同一短标签或 B2B 维度词开头，
        避免与横幅重复，并减少「遇到瓶颈/想要转型」等与瓶装水等 C 端场景不搭的贴标签式开头。
        """
        d = (description or '').strip()
        if not d:
            return d

        bp = (batch_pain or '').strip()
        bg = (batch_goal or '').strip()

        # 维度库中易误贴到 C 端描述开头的 B2B/抽象短词（prompt 已禁，模型仍可能照抄库内词）
        forbidden_opens = (
            '遇到瓶颈',
            '想要转型',
            '寻求突破',
            '想要增长',
            '想要变现',
            '花得值',
            '规模化',
        )

        for _ in range(8):
            matched = False
            # 与横幅完全重复的整句前缀
            for c in sorted([x for x in (bp, bg) if x], key=len, reverse=True):
                if d.startswith(c):
                    rest = d[len(c):].lstrip('，,。、；;：:\t\n ')
                    if rest:
                        d = rest
                        matched = True
                        break
            if matched:
                continue
            for c in forbidden_opens:
                if c and d.startswith(c):
                    rest = d[len(c):].lstrip('，,。、；;：:\t\n ')
                    if rest:
                        d = rest
                        matched = True
                        break
            if not matched:
                break

        # 「标签、标签、自然叙事」：去掉开头与横幅重复或与禁用词相同的段
        if '、' in d:
            parts = [p.strip() for p in d.split('、') if p.strip()]
            drop = set(forbidden_opens)
            if bp:
                drop.add(bp)
            if bg:
                drop.add(bg)
            while parts and parts[0] in drop:
                parts.pop(0)
            if parts:
                d = '、'.join(parts)

        return d.strip()

    @classmethod
    def _unify_c_end_batch_pain_goal(
        cls,
        targets: List[Dict[str, Any]],
        business_type: str,
        user_goal: str = '',
        business_description: str = '',
    ) -> tuple:
        """
        C 端（本地服务/消费品/个人品牌）：同一批 5 条画像共用同一组痛点状态 + 目标；
        过滤 B2B 泄露词；若阶段 1 传了 user_goal 则优先作为本批目标。
        若业务描述命中领域细分池，且模型仍给出抽象痛点/目标，则对齐到领域细分（与维度库一致）。
        返回 (batch_pain, batch_goal)。
        """
        if business_type not in ('local_service', 'product', 'personal') or not targets:
            return '', ''

        batch_pain = ''
        batch_goal = ''

        for t in targets:
            p = (t.get('pain_point_commonality') or '').strip()
            if p and not cls._c_end_pain_goal_has_b2b_leak(p):
                batch_pain = p
                break
        if not batch_pain:
            batch_pain = '选品信息多、不知道哪个更适合，比较焦虑'

        ug = (user_goal or '').strip()
        user_goal_set = bool(ug)
        if ug:
            batch_goal = ug[:120]
        else:
            for t in targets:
                g = (t.get('goal') or '').strip()
                if g and not cls._c_end_pain_goal_has_b2b_leak(g):
                    batch_goal = g
                    break
            if not batch_goal:
                batch_goal = '买得更放心'

        # 与领域细分池对齐（顶部「本批共用」与 LLM 维度库一致）
        batch_pain, batch_goal = cls._align_batch_pain_goal_to_domain(
            batch_pain, batch_goal, business_description, user_goal_set
        )

        unified_sentence = f'{batch_pain} → 希望{batch_goal}'

        for t in targets:
            t['pain_point_commonality'] = batch_pain
            t['goal'] = batch_goal
            t['pain_point'] = unified_sentence
            raw_desc = (t.get('description') or '').strip()
            if raw_desc:
                cleaned = cls._clean_persona_description_after_batch_unify(
                    raw_desc, batch_pain, batch_goal
                )
                t['description'] = cleaned if cleaned.strip() else raw_desc

        return batch_pain, batch_goal

    @classmethod
    def generate(cls, user: PublicUser, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成内容

        Args:
            user: 用户
            params: {
                'industry': str,           # 行业
                'target_customer': str,    # 目标客户（可选，会自动推断）
                'content_type': str,      # 图文/短视频
                'business_description': str, # 业务描述（可选）
                'customer_who': str,      # 客户是谁（可选）
                'customer_why': str,      # 为什么找到（可选）
                'customer_problem': str,   # 解决了什么问题（可选）
                'customer_story': str,     # 客户故事（可选）
                'structure_type': str,     # 结构类型（可选）
                'use_ai': bool,           # 是否使用AI增强
            }

        Returns:
            生成结果
        """
        start_time = time.time()

        industry = params.get('industry', 'general')
        content_type = params.get('content_type', 'graphic')
        business_description = params.get('business_description', '')
        structure_type = params.get('structure_type')
        use_ai = params.get('use_ai', user.is_paid_user())

        # 从新字段推断 target_customer
        target_customer = cls._infer_target_customer(params)

        # 检查配额
        can_generate, reason, quota_info = quota_manager.check_quota(user)
        if not can_generate:
            return {
                'success': False,
                'error': 'quota_exceeded',
                'message': cls._get_quota_message(reason, quota_info),
            }

        # 匹配模板资源
        is_premium = user.is_paid_user()
        resources = template_matcher.match_for_generation(industry, target_customer, is_premium)

        # 生成内容
        tokens_used = 0
        try:
            if use_ai and is_premium:
                # AI增强模式
                result = cls._generate_with_ai(params, resources)
                tokens_used = cls.TOKEN_ESTIMATE['with_ai']['total']
            else:
                # 模板模式（免费用户）
                result = cls._generate_from_template(params, resources)
                tokens_used = cls.TOKEN_ESTIMATE['keyword_only']['total']

            # 保存生成记录
            generation = PublicGeneration(
                user_id=user.id,
                industry=industry,
                target_customer=target_customer,
                content_type=content_type,
                titles=result['titles'],
                tags=result['tags'],
                content=result['content'],
                used_tokens=tokens_used,
            )
            db.session.add(generation)

            # 更新配额
            quota_manager.use_quota(user, tokens_used)

            db.session.commit()

            # 返回结果
            duration = time.time() - start_time
            return {
                'success': True,
                'data': result,
                'meta': {
                    'tokens_used': tokens_used,
                    'duration_ms': int(duration * 1000),
                    'is_ai_enhanced': use_ai and is_premium,
                }
            }

        except Exception as e:
            db.session.rollback()

            # 记录失败日志
            log = PublicLLMCallLog(
                user_id=user.id,
                call_type='content_generate',
                model='gpt-4o-mini',
                status='failed',
                error_message=str(e),
            )
            db.session.add(log)
            db.session.commit()

            return {
                'success': False,
                'error': 'generation_failed',
                'message': f'生成失败: {str(e)}',
            }

    @classmethod
    def identify_customer_identities(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        阶段1：轻量级识别目标客户身份列表

        根据业务描述快速识别可能的目标客户身份，按 ToB/ToC 分类返回。
        这个接口只做身份识别，不生成完整画像，LLM调用量小、速度快。

        Args:
            params: 包含 business_description, business_range, business_type

        Returns:
            {
                'success': True,
                'data': {
                    'to_b': [{'name': '身份名', 'description': '简短描述'}],
                    'to_c': [{'name': '身份名', 'description': '简短描述'}],
                }
            }
        """
        business_desc = (params.get('business_description') or '').strip()
        business_range = params.get('business_range', 'local')
        business_type = params.get('business_type', 'local_service')

        if not business_desc:
            return {
                'success': False,
                'error': 'missing_business_description',
                'message': '请描述您的业务',
            }

        # 构建轻量级 prompt
        prompt = f"""你是一个用户画像专家。根据以下业务信息，快速识别出最可能的目标客户身份类型。

业务描述：{business_desc}
经营范围：{'本地/同城' if business_range == 'local' else '跨区域'}
经营类型：{
    '本地服务（理发店/餐饮/家政等）' if business_type == 'local_service'
    else '消费品/零售（奶粉/饮料/食品等）' if business_type == 'product'
    else '个人品牌/自媒体' if business_type == 'personal'
    else '企业服务/B2B（软件/咨询/设备等）'
}

=== 身份推导 ===

**核心原则：识别购买/决策侧的稳定身份称呼**

【买用关系判断】
- 买即用（买的人=用的人）：餐饮、维修、理发、手机、自用食品 → 身份是「消费者/用户」
- 买用分离（买的人≠用的人）：奶粉、纸尿裤、老人用品、宠物用品 → 身份是「购买决策者（宝妈/子女/主人）」

【示例】
- 灌香肠 → 过年置办年货的家庭、办宴席的主家、早餐店/餐馆老板
- 矿泉水定制 → 企业行政、会议组织者、酒店餐厅、婚庆策划
- 婴儿奶粉 → 有宝宝的家庭（购买者是宝妈，使用者是宝宝）
- 手机维修 → 手机用户、上班族、学生（购买者即使用者）

请按 ToB（企业客户）和 ToC（个人消费者）两类分别列出最可能的身份类型。

【本阶段只做「身份标签」】用户点击后将进入下一步生成详细画像；**不要**在本阶段输出使用者年龄、转奶期、健康目标等细节，那些由下一步结合业务描述再生成。

规则：
- 只输出真实存在的身份，不要编造
- 名称简洁，2-8字以内（如「宝妈」「上班族」）
- buyer.description 一句话说明该身份即可（≤30字），不要写宝宝月龄、转奶、拉肚子等
- user 字段**必须恒为 null**（本阶段不用）
- 根据经营类型决定两类比例：
  * 本地服务/消费品：ToC为主(6-8个)，ToB可忽略或仅1-2个
  * 企业服务：ToB为主(6-8个)，ToC可忽略或仅1-2个
  * 个人品牌：ToC为主(6-8个)
- 多样化，覆盖不同人群细分
- 标注 "core": true 表示核心人群（气泡词云中会显示更大），一般2-3个最具代表性

输出格式（只返回JSON，不要其他文字）：
{{
    "to_b": [
        {{"buyer": {{"name": "【根据业务生成的B端身份，如：餐饮店老板/企业采购/连锁经理等】", "description": "【一句话描述该身份】"}}, "user": null, "core": true}},
        {{"buyer": {{"name": "【第二个B端身份】", "description": "【一句话描述】"}}, "user": null, "core": false}}
    ],
    "to_c": [
        {{"buyer": {{"name": "【根据业务生成的C端身份，如：家庭主妇/企业员工/附近居民等】", "description": "【一句话描述该身份】"}}, "user": null, "core": true}},
        {{"buyer": {{"name": "【第二个C端身份】", "description": "【一句话描述】"}}, "user": null, "core": false}},
        {{"buyer": {{"name": "【第三个C端身份】", "description": "【一句话描述】"}}, "user": null, "core": true}}
    ]
}}

【重要】以上只是格式示例。请根据上方的「业务描述」来生成真正适合的身份！
- 灌香肠/腊肉/腌制品 → 考虑：年节送礼者、置办年货的家庭、餐馆饭店、乡镇居民等
- 矿泉水定制 → 考虑：企业接待、会议用水、酒店餐厅、婚庆策划等
- 其他业务 → 根据实际产品和目标客户来推断
}}"""

        try:
            from services.llm import get_llm_service
            import json
            import re

            service = get_llm_service()
            if not service:
                raise Exception('LLM服务暂不可用')

            response = service.chat(
                prompt,
                temperature=0.5,  # 低温度，结果更稳定
                max_tokens=800,   # 只需要简短输出
            )

            # ========== [调试日志] ==========
            print(f"[identify_customer_identities] === 调试信息 ===")
            print(f"[identify_customer_identities] 业务描述: {business_desc}")
            print(f"[identify_customer_identities] 经营范围: {business_range}, 经营类型: {business_type}")
            print(f"[identify_customer_identities] LLM原始响应:\n{response[:2000] if response else 'None'}")
            # ========== [/调试日志] ==========

            if not response:
                raise Exception('LLM服务暂不可用')

            # 解析JSON响应
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if not match:
                raise Exception('LLM响应格式错误')

            raw = json.loads(match.group(0))

            to_b = raw.get('to_b', [])
            to_c = raw.get('to_c', [])

            # 清理空值（buyer.name 存在才算有效）
            to_b = [x for x in to_b if x.get('buyer', {}).get('name')]
            to_c = [x for x in to_c if x.get('buyer', {}).get('name')]

            # 确保至少有一类有身份
            if not to_b and not to_c:
                raise Exception('未识别到有效的目标客户身份')

            # 兼容旧格式（如果LLM仍返回旧格式）
            def normalize(item):
                # 新格式已有 buyer/user 结构
                if 'buyer' in item:
                    return item
                # 旧格式兼容：转换为新格式
                return {
                    'buyer': {'name': item.get('name', ''), 'description': item.get('description', '')},
                    'user': None,
                    'core': item.get('core', False)
                }

            to_b = [normalize(x) for x in to_b]
            to_c = [normalize(x) for x in to_c]

            # 阶段1 仅身份：丢弃 LLM 可能仍返回的 user，避免气泡出现「给0-1岁宝宝→目标」等冗余
            def strip_user_for_stage1(item: Dict[str, Any]) -> Dict[str, Any]:
                out = dict(item)
                out['user'] = None
                return out

            to_b = [strip_user_for_stage1(x) for x in to_b]
            to_c = [strip_user_for_stage1(x) for x in to_c]

            def dedupe_by_buyer_name(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                seen: set = set()
                out: List[Dict[str, Any]] = []
                # 先 core=true，再其余，减少重复名时丢掉非核心
                core_first = sorted(items, key=lambda x: (not x.get('core'), x.get('buyer', {}).get('name', '')))
                for it in core_first:
                    nm = (it.get('buyer') or {}).get('name', '').strip()
                    if not nm or nm in seen:
                        continue
                    seen.add(nm)
                    out.append(it)
                return out

            to_b = dedupe_by_buyer_name(to_b)[:8]
            to_c = dedupe_by_buyer_name(to_c)[:8]

            # ========== [调试日志] ==========
            print(f"[identify_customer_identities] ToB身份: {[x.get('buyer', {}).get('name', '') for x in to_b]}")
            print(f"[identify_customer_identities] ToC身份: {[x.get('buyer', {}).get('name', '') for x in to_c]}")
            print(f"[identify_customer_identities] === 调试结束 ===\n")
            # ========== [/调试日志] ==========

            return {
                'success': True,
                'data': {
                    'to_b': to_b,
                    'to_c': to_c,
                }
            }

        except Exception as e:
            import traceback
            print(f"[ContentGenerator] identify_customer_identities 异常: {e}")
            print(f"[ContentGenerator] 堆栈: {traceback.format_exc()}")
            return {
                'success': False,
                'error': 'llm_unavailable',
                'message': '服务暂时不可用，请稍后重试',
            }

    @classmethod
    def generate_target_customers(cls, user: PublicUser, params: Dict[str, Any],
                                  use_ai_enhancement: bool = False) -> Dict[str, Any]:
        """
        生成目标用户画像（身份 + 痛点 + 目标，全部由 LLM 结合业务场景自由推导）

        Args:
            user: 用户
            params: 包含业务描述和深度了解信息
            use_ai_enhancement: 是否使用AI增强（付费用户）

        Returns:
            5个目标用户画像
        """
        business_desc = params.get('business_description', '')
        business_range = params.get('business_range', '')
        business_type = params.get('business_type', '')
        customer_who = params.get('customer_who', '')
        customer_why = params.get('customer_why', '')
        customer_problem = params.get('customer_problem', '')
        customer_story = params.get('customer_story', '')
        customer_experiences = params.get('customer_experiences', [])

        targets: List[Dict] = []
        used_llm_primary = False

        # C 端业务：LLM 可用时优先直出画像
        if (
            cls._llm_available()
            and business_type in ('local_service', 'product', 'personal')
        ):
            try:
                llm_targets = cls._generate_targets_pure_llm(params)
                if llm_targets and len(llm_targets) >= 5:
                    targets = llm_targets[:5]
                    used_llm_primary = True
            except Exception as e:
                print(f"[ContentGenerator] LLM 画像直出失败，回退规则: {e}")

        if not targets:
            targets = cls._generate_targets_by_rules(params)

        # 付费套餐 AI 增强
        if use_ai_enhancement and cls._llm_available() and not used_llm_primary:
            try:
                enhanced_targets = cls._enhance_targets_with_ai(targets, params)
                if enhanced_targets:
                    targets = enhanced_targets
            except Exception as e:
                print(f"[ContentGenerator] AI增强失败，使用规则结果: {e}")

        # C 端：整批统一痛点状态 + 目标，供前端顶部一次展示
        batch_pain = ''
        batch_goal = ''
        if business_type in ('local_service', 'product', 'personal') and targets:
            batch_pain, batch_goal = cls._unify_c_end_batch_pain_goal(
                targets, business_type,
                user_goal=(params.get('user_goal') or '').strip(),
                business_description=params.get('business_description', '') or '',
            )

        return {
            'success': True,
            'data': {
                'targets': targets,
                'business_description': business_desc,
                'batch_pain_point_commonality': batch_pain,
                'batch_goal': batch_goal,
                'ai_enhanced': bool(
                    used_llm_primary
                    or (use_ai_enhancement and cls._llm_available())
                ),
            }
        }

    @classmethod
    def _llm_available(cls) -> bool:
        """检查 LLM 服务是否可用（实例存在且非 None）"""
        try:
            from services.llm import llm_service, get_llm_service
            # llm_service 可能是 None，换用 get_llm_service() 获取实例
            return llm_service is not None or get_llm_service() is not None
        except ImportError:
            return False

    @classmethod
    def _enhance_targets_with_ai(cls, base_targets: List[Dict], params: Dict) -> List[Dict]:
        """使用AI增强目标用户画像"""
        business_desc = params.get('business_description', '')
        customer_who = params.get('customer_who', '')
        customer_why = params.get('customer_why', '')
        customer_problem = params.get('customer_problem', '')
        customer_story = params.get('customer_story', '')

        business_range = params.get('business_range', '')
        business_type = params.get('business_type', '')

        # 构建prompt
        prompt = """你是一个用户画像分析专家。根据以下信息，生成5个精准的目标用户画像。

业务描述：{business_desc}
经营范围：{business_range}
经营类型：{business_type}

{filled_info}

硬性约束（必须遵守）：
- 画像必须与业务描述中的行业、地域、服务类型一致；可合理推断周边人群，禁止凭空套用无关行业。
- 若经营类型为「local_service」本地服务或「product」消费品，画像应是终端消费者、本地居民、店主/业主等 C 端或小微场景，禁止默认生成「互联网/科技公司」的董事长、VP、总监、经理等企业高管模板。
- 若经营类型为「enterprise」企业服务，才可使用 B2B 决策者角色（创始人/总监/采购等）。
- 若用户明确写了地名（如县城、区名），地域画像应贴近该范围。

请为每个目标用户生成：
1. name: 用户类型名称（如"写字楼行政负责人"）
2. description: 详细描述用户的特征、决策权、需求
3. age_range: 年龄段
4. occupation: 具体职业
5. pain_point: 核心痛点
6. needs: 具体需求（3-5个）
7. behaviors: 购买行为特征

请用JSON数组格式返回，例如：
[
  {{
    "name": "写字楼行政",
    "description": "负责整栋写字楼的行政后勤...",
    "age_range": "28-40岁",
    "occupation": "行政经理",
    "pain_point": "配送不及时，经常被投诉",
    "needs": "稳定供货、价格合理、服务响应快",
    "behaviors": "通过供应商名录和同行推荐寻找供应商"
  }}
]

只返回JSON数组，不要其他文字。""".format(
            business_desc=business_desc,
            business_range=business_range or '（未填）',
            business_type=business_type or '（未填）',
            filled_info=cls._build_filled_info(customer_who, customer_why, customer_problem, customer_story)
        )

        try:
            from services.llm import get_llm_service
            service = get_llm_service()
            if not service:
                return None
            response = service.chat(
                prompt,
                temperature=0.7,
                max_tokens=2000,
            )

            # 解析JSON响应
            import json
            import re

            # 提取JSON数组
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                enhanced = json.loads(match.group(0))
                if isinstance(enhanced, list) and len(enhanced) >= 5:
                    return enhanced[:5]

        except Exception as e:
            print(f"[ContentGenerator] AI增强解析失败: {e}")

        return None

    @classmethod
    def _generate_targets_pure_llm(cls, params: Dict[str, Any]) -> Optional[List[Dict]]:
        """
        面向 C 端（本地服务/消费品/个人品牌）直接用 LLM 生成 5 条画像，
        从数据库10维度池中挑选3-4个组合人群描述，而非凭空发挥。
        身份全部由 LLM 结合业务场景自由推导，不预设固定身份列表。
        """
        business_desc = (params.get('business_description') or '').strip()
        business_range = params.get('business_range', '') or '（未填）'
        business_type = params.get('business_type', '') or '（未填）'

        # 深度了解（可选）—— 辅助信息
        customer_who = (params.get('customer_who') or '').strip()
        customer_why = (params.get('customer_why') or '').strip()
        customer_problem = (params.get('customer_problem') or '').strip()
        customer_story = (params.get('customer_story') or '').strip()

        aux_parts = []
        if customer_who:
            aux_parts.append(f'- 目标客群是谁：{customer_who}')
        if customer_why:
            aux_parts.append(f'- 触达他们的动机：{customer_why}')
        if customer_problem:
            aux_parts.append(f'- 他们有什么问题：{customer_problem}')
        if customer_story:
            aux_parts.append(f'- 真实故事/经历：{customer_story}')
        aux_section = '\n'.join(aux_parts) if aux_parts else '（未填写辅助信息）'

        # 数码维修类：强约束，避免模型照抄提示词里的奶粉/转奶示例
        electronics_guard = ''
        if cls._desc_has_electronics_service(business_desc) and not cls._desc_has_baby_business(business_desc):
            electronics_guard = (
                '\n【本业务类型·强制】当前为**手机/数码维修或本地手机售卖**：决策者与使用者均为普通消费者，'
                '**禁止**编造奶粉、转奶、乳糖、纸尿裤、0-1岁宝宝、宝妈买奶粉等母婴场景；'
                '**禁止**在 consumption_stage、age_range、description、痛点、目标中写入婴幼童阶段。\n'
                '痛点/目标须围绕：**急用、怕资料丢失、怕偷换件、报价不透明、不知哪家靠谱、换机纠结**等；'
                'buyer_user_relation 以「买即用（自用）」为主；描述示例：「手机碎屏怕资料没了，想找报价清楚、当场能修的店」。\n'
            )

        # 地域约束：local → 本地同城；非 local → 全国，不组合地域维度
        if business_range == 'local':
            region_constraint = '【强制】经营范围为「本地/同城」，所有画像的地域维度必须限定在本县/本区/本镇/同城1小时配送圈内，禁止出现跨市、跨省、全国等范围标签。'
        else:
            region_constraint = '【强制】经营范围为「跨区域/全国」，不在维度库中组合地域维度，默认全国范围。'

        # 构建10维度池（按业务类型过滤），作为 LLM 的可选维度库
        dim_pool_str = cls._build_llm_dimension_pool(params)

        prompt = f"""你是用户画像专家。请根据业务信息，从维度库中组合生成5个精准目标用户画像。

=== 业务基本信息 ===
业务描述：{business_desc}
经营范围：{business_range}
经营类型：{business_type}
{electronics_guard}
=== 可用维度库 ===
{dim_pool_str}

=== 核心原则 ===

**【买用关系·强制判断】**

**买用分离业务（买的人≠用的人）：**
- 婴儿奶粉/辅食 → 宝宝是使用者 → buyer_user_relation = **「买给1-3岁宝宝」**
- 纸尿裤/婴儿推车 → 宝宝是使用者 → **「买给0-3岁宝宝」**
- 老人保健品/老花镜 → 老人是使用者 → **「买给长辈」**
- 宠物食品/用品 → 宠物是使用者 → **「买给宠物」**

**买即用业务（买的人=用的人）：**
- 餐饮/维修/理发 → 本人消费本人使用 → 「自用」
- 桶装水/自用食品 → 本人喝本人吃 → 「自用」

**【重要】业务描述里有「宝宝」「孩子」「老人」「宠物」相关需求 → 必为买用分离！**

**【禁止·买用分离时维度填使用者的】**
```
❌ 错误示例：
「35-45岁宝爸，担心宝宝喝奶粉拉肚子」
→ 身份是宝爸（35-45岁），但痛点是宝宝的！
→ age_range 填了「35-45岁」是错的，应该填「1-3岁」（宝宝的年龄段）

✅ 正确示例：
「有1-3岁宝宝的妈妈，宝宝正处于断奶期、喝普通奶粉容易拉肚子，担心成分不安全」
→ name：焦虑宝妈
→ age_range：「1-3岁」（宝宝的年龄段）
→ consumption_stage：「有1-3岁宝宝」
→ buyer_user_relation：「买给1-3岁宝宝」
```

**【维度填使用者的：】**
- age_range：使用者的年龄段（宝宝的年龄/老人的年龄）
- consumption_stage：使用者所处的阶段（「有0-1岁宝宝」「有60岁以上老人」）
- 痛点/目标：体现使用者的问题特征

=== 通用约束 ===

1. 【差异化·强制】5条之间**至少在3个维度上有明显不同**：
   - 身份细分（不同角色：宝妈 vs 宝爸 vs 家中长辈）
   - 年龄段（如1-3岁 vs 3-6岁 vs 备孕期）
   - 地域（如县城居民 vs 城区核心街道 vs 郊区住户）
   - 消费阶段（如备孕期 vs 有0-1岁宝宝 vs 空巢期）

2. 【痛点状态 + 目标·体现使用者特征】
   - pain_point_commonality = 使用者**当前正处于的问题状态**
     - 买即用：「急用手机但不知道哪家靠谱，怕被坑」
     - 买用分离：「2岁宝宝喝奶粉天天拉肚子」「70岁老人视力下降不会用智能机」
   - goal = **希望达成的结果**
     - 买即用：「当场修好、用得放心」
     - 买用分离：「找到安全可靠的奶粉、宝宝健康成长」

3. 【逐字来自维度库】所有维度标签必须**逐字**来自上方「可用维度库」，禁止自造。

4. 【语义一致】维度组合要语义通顺，禁止矛盾搭配。

5. 【C端禁用词】description/痛点/目标中禁止：融资、创始人、CEO、年营收、GMV 等卖家向词汇。

=== 输出格式（只返回JSON数组，5个对象，不要其他文字）===
{{
    "name": "细分人群简称（≤6字），由LLM根据业务推导，禁止空洞概括（如「消费者」「客户」），禁止与 occupation 重复",
    
    "description": "**【格式：使用者维度 + 使用者问题 + 购买者担忧 + 身份（最后）】**\n\n例（买即用）：\n「25-30岁县城居民，上班族白领，手机突然碎屏又怕资料丢失，想找报价透明、当场能修好的维修店，担心被坑的上班族」\n\n例（买用分离）：\n「有1-3岁宝宝的妈妈，宝宝正处于断奶期、喝普通奶粉容易拉肚子，担心成分不安全，希望找到适合宝宝的奶粉，焦虑的新手宝妈」",
    
    "pain_point_commonality": "来自维度库原文。使用者当前正处于的问题/焦虑状态，禁止填终点结果",
    "goal": "来自维度库原文。终点结果，禁止填过程状态",
    "buyer_user_relation": "买即用填「自用」；买用分离填「买给长辈」「买给0-3岁宝宝」等",
    "age_range": "来自维度库 age_group 原文（买用分离时填使用者的年龄段）",
    "geo_tag": "跨区域业务填写空字符串 \"\"；本地业务来自维度库 region 原文",
    "consumption_stage": "来自维度库 consumption_stage 原文（买用分离时填使用者所处的阶段）",
    "occupation": "来自维度库 job_role 原文",
    "pain_point": "使用者问题 → 达成的结果",
    "needs": "2-3条需求，分号分隔",
    "behaviors": "2-3条决策行为，分号分隔"
}}

只输出JSON数组，不要Markdown。"""

        try:
            from services.llm import get_llm_service
            import json
            import re

            service = get_llm_service()
            if not service:
                return None
            response = service.chat(
                prompt,
                temperature=0.85,
                max_tokens=3000,
            )
            if not response:
                return None
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if not match:
                return None
            raw = json.loads(match.group(0))
            if not isinstance(raw, list) or len(raw) < 5:
                return None

            out: List[Dict] = []
            for item in raw[:5]:
                if not isinstance(item, dict):
                    continue
                needs = item.get('needs', '')
                if isinstance(needs, list):
                    needs = '；'.join(str(x) for x in needs)
                beh = item.get('behaviors', '')
                if isinstance(beh, list):
                    beh = '；'.join(str(x) for x in beh)
                desc = (item.get('description') or '').strip()
                if not desc:
                    continue
                name = (item.get('name') or '').strip() or cls._derive_persona_display_name(desc)
                age_r = (item.get('age_range') or '').strip()
                occ = (item.get('occupation') or '').strip()
                pst = (item.get('pain_point_commonality') or '').strip()
                goal_val = (item.get('goal') or '').strip()
                buyer_rel = (item.get('buyer_user_relation') or '').strip()
                out.append({
                    'name': name[:12],
                    'description': desc,
                    'pain_point_commonality': pst,
                    'goal': goal_val,
                    'buyer_user_relation': buyer_rel,
                    'age_range': age_r or '不限',
                    'occupation': occ or '不限',
                    'geo_tag': (item.get('geo_tag') or '').strip(),
                    'consumption_stage': (item.get('consumption_stage') or '').strip(),
                    'pain_point': (item.get('pain_point') or '').strip(),
                    'needs': str(needs).strip(),
                    'behaviors': str(beh).strip(),
                    '_dims': {'source': 'llm_pure'},
                })
            return out if len(out) >= 5 else None
        except Exception as e:
            print(f"[ContentGenerator] _generate_targets_pure_llm: {e}")
            return None

    @classmethod
    def _build_llm_dimension_pool(cls, params: Dict[str, Any]) -> str:
        """
        为 LLM 构建可用维度库字符串，包含 code、name、options，
        按 business_type 过滤不适用维度，local_service/product/personal 用本地生活化选项。
        """
        business_desc = (params.get('business_description') or '').strip()
        business_range = params.get('business_range') or 'local'
        business_type = params.get('business_type') or 'local_service'

        dims_map = cls._get_persona_dimensions()
        if not dims_map:
            return '（维度库为空，使用默认人群描述）'

        # 推断行业（用于 occupation 拼接）
        inferred_industry = cls._infer_local_industry_from_desc(business_desc)

        # 客户角色池：从数据库 job_role 维度读取
        job_dim_code = 'job_role'
        if job_dim_code in dims_map:
            job_opts = cls._build_dimension_options(
                dims_map[job_dim_code], business_desc, business_range, business_type
            )
            job_label = dims_map[job_dim_code].name
        else:
            job_opts = ['目标客户']
            job_label = '客户角色'

        # 构建维度库列表（痛点状态单独置顶为【必选】）
        lines: List[str] = []
        added_job = False
        pain_point_commonality_line: Optional[str] = None
        goal_line: Optional[str] = None
        buyer_user_relation_line: Optional[str] = None

        for code, dim in sorted(dims_map.items(), key=lambda x: x[1].sort_order or 0):
            if not cls._dim_applicable_to_business(dim, business_type):
                continue

            if code == job_dim_code:
                # 客户角色维度单独处理
                if job_opts:
                    lines.append(f"- {job_label}（job_role）: {'、'.join(job_opts)}")
                    added_job = True
                continue

            opts = cls._build_dimension_options(dim, business_desc, business_range, business_type)
            if not opts:
                continue

            # 库内 code 多为 pain_status，与 prompt 中 pain_point_commonality 同义
            if code in ('pain_point_commonality', 'pain_status'):
                dim_desc_text = (dim.description or '').strip()
                dim_desc_part = (f'\n  维度含义：{dim_desc_text}' if dim_desc_text else
                                 f'\n  维度含义：此人当前正处于的焦虑/迷茫/恐惧状态（如「找不到方法的焦虑」「对未知信息的恐惧」「多选一的迷茫」），这是过程性状态，不是结果。')
                pain_point_commonality_line = (
                    f"- {dim.name}（输出字段名 pain_point_commonality，**须填下列原文之一**）{dim_desc_part}\n  选项: {'、'.join(opts)}"
                )
                continue
            if code == 'goal':
                goal_line = f"- {dim.name}（goal）: {'、'.join(opts)}"
                continue
            if code == 'buyer_user_relation':
                buyer_user_relation_line = f"- {dim.name}（buyer_user_relation）: {'、'.join(opts)}"
                continue

            lines.append(f"- {dim.name}（{code}）: {'、'.join(opts)}")

        # 如果 job_role 维度被过滤了但还没加过，补上客户角色
        if not added_job and job_opts:
            lines.insert(0, f"- {job_label}（job_role）: {'、'.join(job_opts)}")

        # 如果没有从数据库读到痛点共性/目标/买用关系，使用默认文本
        if not pain_point_commonality_line:
            # 痛点状态 = 过程性焦虑/迷茫/恐惧状态，不是结果
            if business_type in ('local_service', 'product', 'personal'):
                pain_point_commonality_line = (
                    '- 痛点状态（pain_point_commonality，**须填原文之一**）\n'
                    '  维度含义：此人当前正处于的**过程性焦虑/迷茫/恐惧状态**——\n'
                    '    - 「找不到方法的焦虑」：试了很多但没效果，不知道哪条路对\n'
                    '    - 「多选一的迷茫」：选择太多，越看越不知道哪个好\n'
                    '    - 「对未知信息的恐惧」：不知道成分/质量，不敢下手\n'
                    '    - 「时间紧迫的焦虑」：马上要用，来不及仔细比较\n'
                    '    - 「怕买贵的后悔」：担心买完发现买贵了\n'
                    '  选项: 拿不准怎么选、担心成分与安全、时间精力不够、怕买贵了不值、信息多不敢信'
                )
            else:
                pain_point_commonality_line = (
                    '- 痛点状态（pain_point_commonality，**须填原文之一**）\n'
                    '  维度含义：此人当前正处于的焦虑/迷茫/恐惧过程性状态\n'
                    '  选项: 遇到瓶颈、想要转型、寻求突破'
                )
        if not goal_line:
            if business_type in ('local_service', 'product', 'personal'):
                goal_line = (
                    '- 目标（goal，**须填原文之一**）\n'
                    '  维度含义：解决上述过程性痛点状态后，**希望达成的结果/终点状态**——\n'
                    '    - 「买得更值」：花同样的钱，买到品质更好的\n'
                    '    - 「买得更放心」：知道成分/来源，用起来安心\n'
                    '    - 「买得更适合」：选到真正适合自己/家人的\n'
                    '    - 「买得更省心」：不用再操心/比较，省精力\n'
                    '    - 「买得更方便」：不用跑远/等很久，用起来方便\n'
                    '  选项: 买得更值、买得更放心、买得更方便、买得更适合、买得更省心'
                )
            else:
                goal_line = (
                    '- 目标（goal，**须填原文之一**）\n'
                    '  维度含义：解决痛点状态后，企业/团队希望达成的经营结果\n'
                    '  选项: 想要增长、想要转型、想要变现'
                )
        if not buyer_user_relation_line:
            buyer_user_relation_line = (
                '- 买用关系（buyer_user_relation）\n'
                '  C端**必填**，B端可空\n'
                '  买即用（自用）：买的人就是用的人（如自己找家政服务）。\n'
                '  买给家人/长辈/孩子：买的人和用的人不同（如给老人请保姆）。\n'
                '  选项: 买即用（自用）、买给家人、买给长辈、买给孩子、送礼/代购'
            )

        prelude_head = (
            '【强制禁止】禁止出现与当前业务无关的示例内容，如：\n'
            '  - 手机/数码/维修相关：碎屏、偷换件、资料丢失、报价不清等\n'
            '  - 母婴/奶粉相关：宝宝、奶粉、转奶、备孕等\n'
            '  - 桶装水/配送相关：水质、送水、水站等\n'
            '请根据实际业务描述生成对应的客户痛点和目标。\n\n'
        )

        prelude = (
            prelude_head
            + '=== 【每条必选】痛点状态（pain_point_commonality）+ 目标（goal）===\n'
            '【概念区分·必须理解】\n'
            '  · 痛点状态（pain_point_commonality）= **过程性焦虑/迷茫/恐惧状态**——\n'
            '    例：「不知道哪家服务靠谱，怕选错了白花钱」\n'
            '    例：「商家太多，分不清哪家质量好，怕被骗」\n'
            '  · 目标（goal）= **解决状态后希望达成的终点结果**——\n'
            '    例：「找到靠谱的服务商，用得放心」\n'
            '    例：「花合理的钱，买到放心的服务」\n'
            '  两者是「过程状态」→「终点结果」的关系，语义必须能串联（如「多选一迷茫」→「买得更适合」）\n'
            '  【禁止】将目标写成「想涨销量/想拓客/想增长」（这是卖家视角，不是买家消费目标）\n\n'
            f'{pain_point_commonality_line}\n'
            f'{goal_line}\n\n'
            '=== 【C端必选】买用关系（buyer_user_relation）===\n'
            '**关键**：C端消费品/本地服务/个人品牌必须分析「买的人」和「用的人」是否相同，从库中选一个：\n'
            '  - 买即用（自用）：买的人就是用的人（如自己找家政服务）。\n'
            '  - 买给家人/长辈/孩子：买的人和用的人不同（如给老人请保姆）。\n'
            '  - 送礼/代购：买来送人，不自己用。\n'
            '请根据「业务描述」判断哪些关系适用，选最贴近的填入 description，使画像描述准确对应「谁买、谁用」。\n'
            f'{buyer_user_relation_line}\n\n'
            '=== 其他维度（每条再选 2 个，与上面维度组合成自然句）===\n'
        )
        return prelude + '\n'.join(lines)

    @classmethod
    def _derive_persona_display_name(cls, description: str) -> str:
        """
        从自然语言描述推导卡片标题（LLM 未返回 name 时使用）。
        优先取第一个分句/短语，避免整段贴到标题上。
        """
        if not (description or '').strip():
            return '客户画像'
        s = description.strip()
        for sep in ('，', ',', '、', '；', ';'):
            if sep in s:
                head = s.split(sep)[0].strip()
                if len(head) >= 2:
                    return head[:12] if len(head) > 12 else head
        if len(s) <= 12:
            return s
        return s[:8] + '…'

    @classmethod
    def _build_filled_info(cls, customer_who: str, customer_why: str,
                           customer_problem: str, customer_story: str) -> str:
        """构建已填写的深度了解信息"""
        parts = []
        if customer_who:
            parts.append(f"典型客户案例：{customer_who}")
        if customer_why:
            parts.append(f"当初为什么找到您：{customer_why}")
        if customer_problem:
            parts.append(f"帮他解决了什么问题：{customer_problem}")
        if customer_story:
            parts.append(f"印象深刻的客户故事：{customer_story[:100]}")

        return '\n'.join(parts) if parts else '（未填写深度了解信息）'

    @classmethod
    def _infer_local_industry_from_desc(cls, business_desc: str) -> str:
        """从业务描述推断本地服务细分场景（用于画像行业/场景标签）。"""
        if not (business_desc or '').strip():
            return '本地生活'
        pairs = [
            (('改衣', '改衣服', '裁缝', '拉链', '扦边', '裤脚', '裤边', '缝补', '熨烫', '锁边', '改裤腰', '改大小'), '裁缝改衣'),
            (('橱柜', '衣柜', '全屋定制', '装修', '翻新', '软装', '硬装', '瓷砖', '地板', '门窗'), '家居家装'),
            (('餐饮', '外卖', '堂食', '火锅', '奶茶', '烧烤'), '餐饮'),
            (('美容', '美发', '美甲', '护肤'), '美业服务'),
            # 数码维修优先于「培训」（避免「手机维修培训」误判教培）
            (('修手机', '手机维修', '手机店', '换屏', '手机贴膜', '数码维修', '电脑维修', '笔记本维修', '二手机'), '数码维修'),
            (('汽修', '洗车', '保养', '贴膜'), '汽车服务'),
            (('家政', '保洁', '月嫂', '保姆'), '家政服务'),
            (('培训', '补习', '早教', '舞蹈', '书法'), '教育培训'),
            (('律师', '法务'), '专业服务'),
            (('摄影', '婚庆', '司仪'), '生活服务'),
            (('宠物'), '宠物服务'),
            (('健身', '瑜伽', '普拉提'), '运动健康'),
            (('水站', '桶装水', '配送', '矿泉水'), '本地零售/配送'),
            (('奶粉', '母婴', '婴幼儿', '宝宝辅食', '纸尿裤'), '母婴零售'),
        ]
        for keys, label in pairs:
            if any(k in business_desc for k in keys):
                return label
        return '本地生活'

    # ---------------------------------------------------------------------------
    # 画像维度：从 AnalysisDimension 数据库配置中读取（人群画像 / super_positioning / persona）
    # ---------------------------------------------------------------------------

    # 内存缓存：避免每次请求都查库
    _persona_dim_cache: Optional[Dict[str, AnalysisDimension]] = None
    _persona_dim_cache_key: Optional[str] = None  # 用于判断缓存是否过期

    # 业务类型 → applicable_audience 匹配规则
    # 只保留「非 B2B 高管」的人群；企业服务才允许 B2B 高管角色
    _BUSINESS_TYPE_AUDIENCE_TAGS: Dict[str, List[str]] = {
        'local_service': ['本地服务商', '本地生活', '个人服务', '通用'],
        'product':       ['个人服务', '通用', '消费品', '本地生活'],
        'personal':       ['个人服务', '通用', '粉丝/学员'],
        'enterprise':     ['B2B服务', '企业服务', '企业家', '通用'],
    }

    @classmethod
    def _get_persona_dimensions(cls) -> Dict[str, AnalysisDimension]:
        """从数据库加载超级定位·人群画像维度配置，带内存缓存。"""
        try:
            dims = AnalysisDimension.query.filter_by(
                category='super_positioning',
                sub_category='persona',
                is_active=True
            ).order_by(AnalysisDimension.sort_order).all()

            return {d.code: d for d in dims}
        except Exception:
            return {}

    # 业务描述含下列词时视为「明确母婴/婴童零售」，才允许组合婴幼儿消费阶段等维度
    _BABY_BUSINESS_MARKERS: Tuple[str, ...] = (
        '奶粉', '母婴', '婴幼儿', '纸尿裤', '尿不湿', '婴儿', '宝宝辅食', '乳糖', '奶瓶', '妇婴',
    )
    # 手机/数码维修、售卖 — 买即用为主，禁止与奶粉示例混用
    _ELECTRONICS_SERVICE_MARKERS: Tuple[str, ...] = (
        '修手机', '手机维修', '维修手机', '手机店', '换屏', '换电池', '贴膜', '数码维修',
        '电脑维修', '笔记本维修', '手机回收', '二手机', 'iphone', '苹果维修', '安卓维修',
    )

    @classmethod
    def _desc_has_baby_business(cls, business_desc: str) -> bool:
        d = (business_desc or '').strip()
        if not d:
            return False
        if any(m in d for m in cls._BABY_BUSINESS_MARKERS):
            return True
        if '宝宝' in d and any(x in d for x in ('奶粉', '尿不湿', '辅食', '奶瓶', '母婴')):
            return True
        return False

    @classmethod
    def _desc_has_electronics_service(cls, business_desc: str) -> bool:
        d = (business_desc or '').strip()
        if not d:
            return False
        if any(m in d for m in cls._ELECTRONICS_SERVICE_MARKERS):
            return True
        dl = d.lower()
        if 'iphone' in dl or 'ipad' in dl:
            return True
        # 「手机」+ 店/修/卖/屏/配件 等本地常见表述
        if '手机' in d and any(x in d for x in ('维修', '修', '换屏', '贴膜', '专卖', '售卖', '销售', '店', '铺', '回收', '配件')):
            return True
        return False

    @classmethod
    def _filter_persona_opts_for_non_baby_business(cls, dim_code: str, opts: List[str],
                                                     business_desc: str) -> List[str]:
        """
        非母婴业务时，从维度选项中剔除明显婴童/母婴场景标签，
        避免 LLM 随机抽到「备孕」「新手爸妈」「宝宝0-1岁」等与业务无关的选项。
        适用于：consumer_lifecycle（消费阶段）、age_group（年龄段）、buyer_user_relation（买用关系）。
        """
        if not opts or cls._desc_has_baby_business(business_desc):
            return opts

        # 婴幼儿/母婴相关关键词（出现在选项中需要过滤）
        baby_substrings = (
            '备孕', '孕期', '孕妇', '产妇', '坐月子', '哺乳期',
            '宝宝', '婴儿', '婴幼', '新生儿', '乳糖', '转奶',
            '奶粉', '辅食', '纸尿裤', '尿不湿',
            '0-1岁', '0到1岁', '0至1岁', '1岁宝', '2岁宝', '3岁宝',
            '幼儿园', '学前班', '学龄前',
            '新手爸妈',  # 婴幼儿相关人群
            '宝爸', '宝妈', '宝爸宝妈',
        )
        filtered = [o for o in opts if not any(t in o for t in baby_substrings)]
        return filtered if filtered else opts

    @classmethod
    def _build_dimension_options(cls, dim: AnalysisDimension,
                                  business_desc: str,
                                  business_range: str,
                                  business_type: str = 'local_service') -> List[str]:
        """
        从数据库的 examples 字段构建选项池。
        特殊情况做智能覆盖：
          - 行业背景：从业务描述推断具体行业
          - 地域：本地服务细化到县城/乡镇粒度
        """
        base_opts = []
        if dim.examples:
            base_opts = [o.strip() for o in dim.examples.split('|') if o.strip()]

        # 非母婴 + 数码维修：去掉婴幼儿类消费阶段等，防止与业务无关标签混入
        # 注意：数据库中字段名是 consumer_lifecycle，代码中可能写为 consumption_stage
        if dim.code in ('consumption_stage', 'consumer_lifecycle', 'age_group', 'buyer_user_relation'):
            base_opts = cls._filter_persona_opts_for_non_baby_business(
                dim.code, base_opts, business_desc
            )

        # ---- 行业背景：优先从描述推断具体行业 ----
        if dim.code == 'industry_background':
            inferred = cls._infer_local_industry_from_desc(business_desc)
            if inferred != '本地生活':
                return [inferred]
            return base_opts if base_opts else ['本地生活']

        # ---- 地域：本地服务细化 ----
        if dim.code == 'region':
            if business_range == 'local':
                refined = ['县城及下辖乡镇', '同城1小时配送圈', '城区核心街道',
                           '城郊结合部', '郊区/工业园']
                return refined
            else:
                # 跨区域时返回空列表，不在维度库中显示地域维度
                return []

        # ---- 领域细分选项：检测到特定行业时，替换/优先使用该行业的具体选项 ----
        domain_opts = cls._detect_domain_hints(business_desc)
        if domain_opts and dim.code in ('pain_point_commonality', 'pain_status', 'goal'):
            domain_list = domain_opts.get(dim.code, [])
            if domain_list:
                # 领域细分选项优先靠前，通用抽象选项兜底（不去重，因为 base_opts 已去重）
                return domain_list + base_opts

        return base_opts

    @classmethod
    def _detect_domain_hints(cls, business_desc: str) -> Dict[str, List[str]]:
        """
        根据业务描述推断领域，返回该领域在 pain_point_commonality / goal 的具体选项。
        核心逻辑：痛点/目标 = 使用者遇到的具体问题 + 想达成的具体状态，
        而不是「拿不准怎么选」「买得更值」这类抽象焦虑。

        返回结构：Dict[code, List[str]]，无匹配行业时返回空 dict。
        """
        hints: Dict[str, List[str]] = {}
        desc_raw = business_desc or ''
        desc = desc_raw.lower()

        # ── 数码维修/手机店（优先于「小学」教育词误匹配、母婴示例污染）────────────────
        if cls._desc_has_electronics_service(desc_raw) and not cls._desc_has_baby_business(desc_raw):
            hints['pain_point_commonality'] = [
                '手机突然黑屏/碎屏/进水，急用但不知道哪家店修得靠谱',
                '担心维修偷换配件、报价不透明，不敢随便进店',
                '换机还是修机拿不准，怕多花冤枉钱',
                '长辈手机卡顿、不会用，想换机但怕买到不合适',
                '二手机、配件渠道多，不知道有没有暗病、怕踩坑',
            ]
            hints['goal'] = [
                '当场修好、报价清楚、用得放心',
                '配件可靠、售后有保障、不被坑',
                '换到合适机型，省心好用',
                '长辈用手机少折腾，有问题有人帮',
            ]
            return hints

        # ── 桶装水/本地配送服务 ──────────────────────────────────────────────
        if any(k in desc for k in ('桶装水', '矿泉水', '水站', '配送', '饮用水', '桶装配送')):
            hints['pain_point_commonality'] = [
                '不知道哪家水质好、安全可靠',
                '担心桶装水来源不明，怕喝到假水',
                '送水太慢，渴了等半天没人送',
                '价格不透明，怕被宰',
                '水站服务不稳定，今天送明天不送',
                '担心水桶不干净、二次污染',
            ]
            hints['goal'] = [
                '喝到放心水，水质有保障',
                '送水及时，随叫随到',
                '价格透明公道，不吃亏',
                '服务稳定，长期合作省心',
            ]
            return hints

        # ── 奶粉/母婴（数码维修/桶装水已在上方 return，不会误入）──────────────────────────
        if any(k in desc for k in ('奶粉', '母婴', '婴幼儿', '纸尿裤', '尿不湿', '婴儿', '宝宝辅食', '乳糖')):
            hints['pain_point_commonality'] = [
                '宝宝乳糖不耐受，喝普通奶粉拉肚子（大便不正常）',
                '宝宝过敏/长湿疹，不知道是不是奶粉的原因',
                '宝宝生长发育迟缓，身高体重不达标',
                '转奶期不知道怎么选，多方比较，非常焦虑',
                '宝宝厌奶/胃口差，担心营养不够',
                '不知道哪款奶粉成分更安全，不敢下手',
                '信息太多，不知道哪款更适合自家宝宝',
            ]
            hints['goal'] = [
                '宝宝不拉肚子、大便正常',
                '宝宝不过敏、湿疹好转',
                '宝宝健康成长、发育达标',
                '找到适合宝宝的奶粉，省心',
                '买得更放心，成分安全可靠',
            ]

        # ── 老人/健康/保健品 ──────────────────────────────────────────────────
        elif any(k in desc for k in ('老人', '老年', '爸妈', '长辈', '钙片', '保健', '血压', '血糖', '血脂', '养老', '护膝', '护腰带')):
            hints['pain_point_commonality'] = [
                '担心老人身体走下坡，不知道怎么补',
                '老人三高（血糖/血压/血脂）不稳定，很担心',
                '老人腿脚无力，行动不便',
                '不知道哪款保健品真的有效，不敢乱买',
                '老人不配合吃保健品，很难坚持',
                '信息太多，不知道给老人买什么合适',
            ]
            hints['goal'] = [
                '老人腿脚有力、精神好',
                '老人三高稳定、减少并发症',
                '老人少生病、生活能自理',
                '买得放心，让老人身体好起来',
            ]

        # ── 宠物 ──────────────────────────────────────────────────────────────
        elif any(k in desc for k in ('宠物', '猫粮', '狗粮', '猫砂', '宠物食品', '宠物用品')):
            hints['pain_point_commonality'] = [
                '宠物挑食/拉肚子，不知道换什么粮',
                '宠物皮肤掉毛，不知道是不是粮的原因',
                '不知道哪种宠物粮成分安全，不敢买',
                '宠物过敏/呕吐，不知道哪款合适',
                '想给宠物换粮，不知道怎么过渡',
            ]
            hints['goal'] = [
                '宠物健康、毛色好、不拉肚子',
                '宠物爱吃、挑食改善',
                '买得放心，成分安全可靠',
            ]

        # ── 儿童教育/培训 ────────────────────────────────────────────────────
        elif any(k in desc for k in ('培训', '补习', '早教', '教育', '幼儿园', '小学', '课外班', '学习')):
            hints['pain_point_commonality'] = [
                '不知道哪个机构好，怕选错耽误孩子',
                '孩子成绩上不去，不知道怎么补',
                '不知道孩子兴趣在哪，不知道报什么班',
                '孩子注意力不集中，学习效率低',
                '担心孩子输在起跑线，很焦虑',
            ]
            hints['goal'] = [
                '孩子成绩提升、进步明显',
                '找到孩子真正感兴趣的领域',
                '孩子注意力集中、学习效率提高',
            ]

        # ── 护肤品/化妆品 ────────────────────────────────────────────────────
        elif any(k in desc for k in ('护肤', '化妆', '美容', '面膜', '精华', '洗面奶', '彩妆')):
            hints['pain_point_commonality'] = [
                '不知道什么成分适合自己，怕过敏',
                '皮肤问题（痘痘/干燥/敏感）不知道用哪款',
                '产品太多，不知道哪个效果好',
                '想美白/抗衰，不知道哪款真的有效',
                '皮肤状态差，不知道怎么改善',
            ]
            hints['goal'] = [
                '皮肤变好、气色好',
                '不过敏、用起来安全',
                '美白/抗衰见效、皮肤状态改善',
            ]

        # ── 餐饮/外卖 ────────────────────────────────────────────────────────
        elif any(k in desc for k in ('餐饮', '外卖', '堂食', '快餐', '便当', '饭店', '餐厅')):
            hints['pain_point_commonality'] = [
                '不知道吃什么，选择困难',
                '担心食品安全，不知道哪家靠谱',
                '外卖吃腻了，想换口味',
                '工作忙，没时间做饭',
                '不知道哪家性价比高',
            ]
            hints['goal'] = [
                '吃得好、干净卫生',
                '省时省力，不用操心',
                '性价比高，花得值',
            ]

        # ── 家装/家具 ────────────────────────────────────────────────────────
        elif any(k in desc for k in ('装修', '家具', '家居', '橱柜', '衣柜', '定制', '软装', '硬装', '瓷砖', '地板', '门窗', '家电')):
            hints['pain_point_commonality'] = [
                '不知道什么风格适合自己，很迷茫',
                '担心装修质量，不知道怎么监工',
                '预算有限，不知道怎么分配',
                '信息太多，不知道哪家建材好',
                '怕被装修公司坑，很不放心',
            ]
            hints['goal'] = [
                '装修顺利，质量有保障',
                '花得值，预算不超支',
                '效果满意，住得舒服',
            ]

        # ── 美业/理发/美容服务 ──────────────────────────────────────────────
        elif any(k in desc for k in ('理发', '美发', '美容', '美甲', '护肤', '造型', '染发', '烫发')):
            hints['pain_point_commonality'] = [
                '不知道什么发型适合自己',
                '担心理发师水平，怕剪坏',
                '想变美但不知道怎么弄',
                '担心染发/烫发伤发质',
                '不知道哪家店技术好',
            ]
            hints['goal'] = [
                '变得更好看、更自信',
                '发型适合自己，气质提升',
                '不伤发，效果自然持久',
            ]

        return hints

    @classmethod
    def _dim_applicable_to_business(cls, dim: AnalysisDimension,
                                     business_type: str) -> bool:
        """
        判断某维度的 applicable_audience 是否与当前业务类型匹配。
        - 无标签 → 通用，保留
        - 含「通用」→ 保留
        - 含「本地服务商/个人服务/消费品」→ 保留
        - 本地服务/产品/个人业务：排除「仅限 B2B/企业服务」且不含通用的维度
        """
        if not dim.applicable_audience:
            return True

        tags = set(t.strip() for t in dim.applicable_audience.split('|') if t.strip())

        # 含通用标签，视为通用维度，保留
        if '通用' in tags:
            return True

        if business_type in ('local_service', 'product', 'personal'):
            # 仅限 B2B/企业服务的标签集合（不含通用）
            b2b_exclusive = {'B2B服务', '企业服务', 'B2B销售'}
            # 若全为 B2B 专有标签，排除；若有消费者标签则保留
            if tags & b2b_exclusive and not (tags - b2b_exclusive):
                return False

        return True

    @classmethod
    def _generate_targets_from_db_dimensions(cls, params: Dict[str, Any],
                                             rng) -> List[Dict]:
        """
        核心实现：从数据库 AnalysisDimension 读取配置，生成 5 个差异化画像。
        - 每个维度从 examples 抽取选项
        - 每人独立抽取各维度选项（差异化）
        - 职位角色放在描述末尾
        - applicable_audience 过滤不适用维度
        """
        business_desc = (params.get('business_description') or '').strip()
        business_range = params.get('business_range') or 'local'
        business_type = params.get('business_type') or 'local_service'
        customer_who = (params.get('customer_who') or '').strip()
        customer_why = (params.get('customer_why') or '').strip()
        customer_problem = (params.get('customer_problem') or '').strip()
        customer_story = (params.get('customer_story') or '').strip()

        dims_map = cls._get_persona_dimensions()

        # 构建每个维度的选项池（按 business_type 过滤）
        dim_options: Dict[str, List[str]] = {}
        dim_objects: Dict[str, AnalysisDimension] = {}
        dim_labels: Dict[str, str] = {}

        for code, dim in dims_map.items():
            opts = cls._build_dimension_options(dim, business_desc, business_range, business_type)
            if not cls._dim_applicable_to_business(dim, business_type):
                continue
            if opts:
                dim_options[code] = opts
                dim_objects[code] = dim
                dim_labels[code] = dim.name

        # 职位角色固定放末尾（已在过滤后保留）
        job_dim_code = 'job_role'

        # 展示顺序：去掉职位角色，其余按 sort_order
        display_order = [code for code in dim_objects.keys() if code != job_dim_code]

        # 推断行业（用于 occupation / name 拼接）
        inferred_industry = cls._infer_local_industry_from_desc(business_desc)

        # 若职位角色维度被过滤掉了，使用默认角色
        if job_dim_code not in dim_options or not dim_options.get(job_dim_code):
            dim_options[job_dim_code] = ['目标客户']
            dim_labels[job_dim_code] = '客户角色'

        # 准备非职位维度候选列表（在 for 循环外计算，避免引用未定义的 profile）
        non_job_candidates = [c for c in display_order if c in dim_options and dim_options[c]]
        if not non_job_candidates:
            non_job_candidates = [c for c in dim_options if c != job_dim_code]

        targets: List[Dict] = []
        for i in range(5):
            profile: Dict[str, str] = {}
            for code, opts in dim_options.items():
                profile[code] = rng.choice(opts)

            job_role = profile.get(job_dim_code, '目标客户')

            # ---- 描述：必选痛点共性 + 目标 + 买用关系（C端）+ 另选维度组合 ----
            # 库维度 code 为 pain_status 时与 pain_point_commonality 同义
            pain_point_commonality_val = (
                profile.get('pain_point_commonality')
                or profile.get('pain_status', '')
            )
            goal_val = profile.get('goal', '')
            buyer_rel = profile.get('buyer_user_relation', '')
            # goal 和 pain_point_commonality 进维度串；行业背景不进随机属性串
            char_candidates = [
                c for c in non_job_candidates
                if c not in {'pain_point_commonality', 'pain_status', 'goal', 'buyer_user_relation'}
                and c != 'industry_background'
            ]
            # C 端固定拉进 buyer_user_relation；其余业务可选
            extra_fixed = [buyer_rel] if business_type in ('local_service', 'product', 'personal') else []
            # 除痛点共性 + 目标外再抽 2 维（不够则全取）
            n_extra = min(2, len(char_candidates))
            selected_char = rng.sample(char_candidates, n_extra) if char_candidates else []

            if business_type in ('local_service', 'product', 'personal'):
                # C 端：痛点共性 + 目标 + 买用关系 + 两个人群属性 + 的 + 角色
                char_vals = [x for x in [pain_point_commonality_val, goal_val] + extra_fixed + [profile.get(c, '') for c in selected_char] if x]
                description = '、'.join(char_vals) + f'的{job_role}'
            else:
                # B2B：痛点共性 + 目标 + 阶段/团队/营收 + 行业 + 角色
                dev_val = profile.get('development_stage', '')
                team_val = profile.get('team_size', '')
                rev_val = profile.get('revenue_scale', '')
                ind_val = profile.get('industry_background', '')
                key_parts = [p for p in [dev_val, team_val, rev_val] if p]
                goal_label = {
                    '想要增长': '需要规模化增长路径',
                    '想要转型': '面临战略转型关键期',
                    '想要变现': '需要找到商业化出口',
                }.get(goal_val, '寻求突破')
                key_parts.append(goal_label)
                b2b_char = '、'.join(key_parts)
                head = f'{pain_point_commonality_val}、' if pain_point_commonality_val else ''
                if ind_val:
                    description = f'{head}{b2b_char}的{ind_val}{job_role}'
                else:
                    description = f'{head}{b2b_char}的{job_role}'

            # ---- 维度组合（含必选痛点共性 + 目标 + 买用关系）----
            combo_vals = [x for x in [pain_point_commonality_val, goal_val] + extra_fixed + [profile.get(c, '') for c in selected_char] if x]
            combo_vals.append(job_role)
            dimension_combo = ' × '.join([p for p in combo_vals if p])

            pain_desc_map = {
                # C 端（pain_status 覆盖项）
                '拿不准怎么选': '面对太多牌子和说法，不知道哪款适合自己家情况',
                '担心成分与安全': '最怕配方、奶源、渠道不靠谱，宁可多花也要买安心',
                '时间精力不够': '上班带娃忙，没空做功课对比，希望少踩坑',
                '怕买贵了不值': '预算有限，怕花冤枉钱又买不到合适段位',
                '信息多不敢信': '广告软文太多，分不清真假，更信口碑和实测',
                # B 端 / 库内原文
                '遇到瓶颈':   '当前选择不满意，正在货比三家、希望更靠谱省心',
                '想要转型':   '需求或阶段变了，想升级方案或换服务商',
                '寻求突破':   '希望少踩坑、一次做到位，更信真实案例与口碑',
            }
            goal_desc_map = {
                # B2B
                '想要增长':   '希望效果看得见、投入值得',
                '想要转型':   '想换更匹配自己阶段的服务方式',
                '想要变现':   '更看重性价比与实际回报',
                # C端（本地服务/消费品）
                '买得更值':   '希望花的钱值，想买到性价比高的',
                '买得更放心': '最担心质量、安全、口碑，宁可多花也不愿踩坑',
                '买得更方便': '懒得跑太远，最好能送货上门或随到随买',
                '买得更适合': '担心不适合自己，希望有专业建议',
                '买得更省心': '没时间细挑，希望有口碑保障不翻车',
            }
            pain_parts = []
            if customer_problem:
                pain_parts.append(customer_problem[:100])
            if pain_point_commonality_val:
                pain_parts.append(pain_desc_map.get(pain_point_commonality_val, pain_point_commonality_val))
            if goal_val:
                pain_parts.append(goal_desc_map.get(goal_val, goal_val))
            if not pain_parts:
                pain_parts = ['有明确需求，正在寻找合适的服务商']

            pain_point = '；'.join(pain_parts[:3])

            # ---- 需求 ----
            needs_parts = [
                f'与「{business_desc[:80]}」这类服务相匹配',
            ]
            if pain_point_commonality_val:
                needs_parts.append(f'当前痛点：{pain_point_commonality_val}')
            if goal_val:
                needs_parts.append(f'核心目标：{goal_val}')
            if customer_why:
                needs_parts.append(f'触达动机：{customer_why[:80]}')
            needs = '；'.join(needs_parts)

            # ---- 行为特征（按行业换话术）----
            # 默认行为特征池
            behavior_pool = [
                '习惯在抖音/美团/大众点评搜附近门店',
                '更看重离得近、口碑真实、能到店沟通',
                '朋友邻居推荐优先',
                '线上先看评价再线下体验',
                '货比三家后决策',
            ]
            beh_pool = behavior_pool[:]
            rng.shuffle(beh_pool)
            behaviors = '；'.join(beh_pool[:3])

            # ---- 最终字段 ----
            age_range = profile.get('age_group', '不限年龄')
            occupation = f'{inferred_industry} · {job_role}'

            targets.append({
                'name': job_role,
                'dimension_combo': dimension_combo,
                'description': description,
                'pain_point_commonality': pain_point_commonality_val,
                'goal': goal_val,
                'buyer_user_relation': buyer_rel,
                'age_range': age_range,
                'occupation': occupation,
                'pain_point': pain_point,
                'needs': needs,
                'behaviors': behaviors,
                '_dims': dict(profile),
            })

        return targets[:5]

    @classmethod
    def _generate_targets_by_rules(cls, params: Dict[str, Any]) -> List[Dict]:
        """
        使用规则生成目标用户画像（免费用户）。
        全部业务类型统一走数据库 AnalysisDimension 配置：
          - 从 examples 读选项池
          - 从 applicable_audience 过滤不适用维度
          - 身份由数据库 job_role 维度自由组合。
        """
        import random

        nonce = params.get('refresh_nonce')
        if nonce is not None:
            rng = random.Random(hash(str(nonce)) % (2 ** 32))
        else:
            rng = random.Random()

        return cls._generate_targets_from_db_dimensions(params, rng)

    @classmethod
    def _generate_from_template(cls, params: Dict, resources: Dict) -> Dict:
        """基于模板生成内容（免费用户）"""
        industry = params.get('industry', 'general')
        target_customer = cls._infer_target_customer(params)
        business_desc = params.get('business_description', '')

        # 获取选题
        topics = resources.get('topics', [])
        if topics:
            topic = topics[0]  # 选择第一个选题
        else:
            topic = {'title': '通用内容', 'description': business_desc or '产品推广'}

        # 提取关键词
        keywords_data = resources.get('keywords', {})
        core_keywords = [k['keyword'] for k in keywords_data.get('core', [])]
        pain_keywords = [k['keyword'] for k in keywords_data.get('pain_point', [])]
        scene_keywords = [k['keyword'] for k in keywords_data.get('scene', [])]

        # 生成标题
        titles = cls._generate_titles_from_keywords(
            core_keywords, pain_keywords, scene_keywords, count=2
        )

        # 生成标签
        tags = cls._generate_tags_from_keywords(
            core_keywords, pain_keywords, scene_keywords, count=6
        )

        # 生成图文内容
        content = cls._generate_graphic_content(
            title=titles[0],
            topic=topic,
            keywords={
                'core': core_keywords,
                'pain_point': pain_keywords,
                'scene': scene_keywords,
            },
            image_count=5,
            image_ratio='9:16'
        )

        return {
            'titles': titles,
            'tags': tags,
            'content': content,
            'selected_topic': topic,
            'keywords_used': {
                'core': core_keywords,
                'pain_point': pain_keywords,
                'scene': scene_keywords,
            }
        }

    @classmethod
    def _generate_with_ai(cls, params: Dict, resources: Dict) -> Dict:
        """AI增强模式生成内容（付费用户）"""
        industry = params.get('industry', 'general')
        target_customer = cls._infer_target_customer(params)
        business_desc = params.get('business_description', '')
        structure_type = params.get('structure_type')

        # 构建prompt
        prompt = cls._build_ai_prompt(params, resources)

        # 调用AI
        try:
            from services.llm import get_llm_service
            service = get_llm_service()
            if not service:
                raise RuntimeError("LLM service not available")
            response = service.chat(
                prompt,
                temperature=0.8,
                max_tokens=2000,
            )
            # 解析AI响应
            result = cls._parse_ai_response(response, resources)
        except Exception as e:
            # AI调用失败，降级到模板模式
            print(f"[ContentGenerator] AI调用失败，降级到模板模式: {e}")
            result = cls._generate_from_template(params, resources)
            result['ai_fallback'] = True

        return result

    @classmethod
    def _generate_titles_from_keywords(cls, core: List[str], pain: List[str],
                                     scene: List[str], count: int = 2) -> List[str]:
        """从关键词生成标题"""
        titles = []

        if core and pain:
            titles.append(f'为什么{scene[0] if scene else ""}都在用{core[0]}？')
        if core:
            titles.append(f'{core[0]}怎么选？看完这篇就懂了')
        if pain:
            titles.append(f'{pain[0]}的坑，你踩过几个？')
        if scene:
            titles.append(f'{scene[0]}人群都在用{core[0] if core else "这款"}')

        return titles[:count] if titles else ['标题1', '标题2']

    @classmethod
    def _generate_tags_from_keywords(cls, core: List[str], pain: List[str],
                                  scene: List[str], count: int = 6) -> List[str]:
        """从关键词生成标签"""
        tags = []

        # 核心词
        for k in core[:1]:
            tags.append(f'#{k}')
        # 痛点词
        for k in pain[:2]:
            tags.append(f'#{k}')
        # 场景词
        for k in scene[:2]:
            tags.append(f'#{k}')
        # 长尾词
        if len(tags) < count:
            tags.append('#好物推荐')
        if len(tags) < count:
            tags.append('#种草')

        return tags[:count]

    @classmethod
    def _generate_graphic_content(cls, title: str, topic: Dict, keywords: Dict,
                                image_count: int = 5,
                                image_ratio: str = '9:16') -> str:
        """生成图文内容Markdown"""
        lines = [
            f'# 图文内容模板',
            '',
            f'## 基本信息',
            '',
            f'- **行业**: {topic.get("industry", "未知")}',
            f'- **目标客户**: {topic.get("customer", "通用")}',
            f'- **选题**: {topic.get("title", "通用内容")}',
            f'- **核心卖点**: {", ".join(keywords.get("core", []))}',
            '',
            f'## 标题',
            f'{title}',
            '',
            f'## 图片内容',
        ]

        # 生成每张图片
        image_titles = [
            '封面',
            '痛点/问题',
            '原因/分析',
            '解决方案',
            '总结引导'
        ]

        for i in range(min(image_count, len(image_titles))):
            lines.extend([
                f'### 图片{i+1}：{image_titles[i]}',
                f'**比例**: {image_ratio} (1080x{1920 if image_ratio == "9:16" else 1080}px)',
                '',
                f'**标题**: [根据内容填写]',
                '',
                f'**内容**:',
                f'[根据选题和关键词填写内容]',
                '',
            ])

        lines.extend([
            '## 评论区首评',
            '[一条真实感的用户评论，激发互动]',
            '',
            '## 发布建议',
            f'- 发布时间：周三/周五 12:00-13:00 或 周六/周日 20:00-21:00',
            f'- 建议添加话题：{", ".join([k["keyword"] for k in keywords.get("core", [])][:3])}',
        ])

        return '\n'.join(lines)

    @classmethod
    def _build_ai_prompt(cls, params: Dict, resources: Dict) -> str:
        """构建AI增强prompt"""
        industry = params.get('industry', '通用')
        target_customer = cls._infer_target_customer(params)
        business_desc = params.get('business_description', '')

        # 获取深度了解信息
        customer_who = params.get('customer_who', '')
        customer_why = params.get('customer_why', '')
        customer_problem = params.get('customer_problem', '')
        customer_story = params.get('customer_story', '')
        customer_experiences = params.get('customer_experiences', [])

        keywords = resources.get('keywords', {})
        topics = resources.get('topics', [])

        # 构建深度了解信息
        deep_info_parts = []
        if customer_who:
            deep_info_parts.append(f"客户是谁：{customer_who}")
        if customer_why:
            deep_info_parts.append(f"为什么找到：{customer_why}")
        if customer_problem:
            deep_info_parts.append(f"解决了什么问题：{customer_problem}")
        if customer_experiences:
            deep_info_parts.append(f"合作体验：{', '.join(customer_experiences)}")
        if customer_story:
            deep_info_parts.append(f"客户故事：{customer_story[:100]}...")

        deep_info = '\n'.join(deep_info_parts) if deep_info_parts else '暂无'

        prompt = f"""你是一个专业的短视频文案专家。请为以下信息生成高质量的图文内容：

行业：{industry}
目标客户：{target_customer}
业务描述：{business_desc or "暂无"}

客户深度信息（帮助精准定位）：
{deep_info}

可用关键词：
- 核心词：{", ".join([k["keyword"] for k in keywords.get("core", [])]) if keywords.get("core") else "暂无"}
- 痛点词：{", ".join([k["keyword"] for k in keywords.get("pain_point", [])]) if keywords.get("pain_point") else "暂无"}
- 场景词：{", ".join([k["keyword"] for k in keywords.get("scene", [])]) if keywords.get("scene") else "暂无"}
- 长尾词：{", ".join([k["keyword"] for k in keywords.get("long_tail", [])]) if keywords.get("long_tail") else "暂无"}

请生成：
1. 5个吸引人的标题（爆款风格）
2. 6-10个标签
3. 5张图片的图文内容结构

输出格式为JSON：
{{
    "titles": ["标题1", "标题2", ...],
    "tags": ["#标签1", "#标签2", ...],
    "content": {{
        "topic": "选题标题",
        "images": [
            {{"index": 1, "title": "图片标题", "content": "图片内容描述"}},
            ...
        ]
    }}
}}
"""
        return prompt

    @classmethod
    def _parse_ai_response(cls, response: str, resources: Dict) -> Dict:
        """解析AI响应"""
        try:
            # 尝试解析JSON
            if isinstance(response, str):
                data = json.loads(response)
            else:
                data = response

            # 构建完整内容
            content = cls._generate_graphic_content(
                title=data.get('titles', [''])[0],
                topic={'title': data.get('content', {}).get('topic', '')},
                keywords=resources.get('keywords', {}),
                image_count=5,
                image_ratio='9:16'
            )

            return {
                'titles': data.get('titles', []),
                'tags': data.get('tags', []),
                'content': content,
                'ai_generated': True,
            }

        except (json.JSONDecodeError, KeyError):
            # 解析失败，返回原始响应
            return {
                'titles': ['标题1', '标题2'],
                'tags': ['#标签1', '#标签2'],
                'content': response,
                'ai_generated': False,
            }

    @classmethod
    def _infer_target_customer(cls, params: Dict[str, Any]) -> str:
        """
        从表单参数推断目标客户

        优先级：
        1. 选中的目标用户画像信息（selected_target_info）
        2. 显式的 target_customer 参数
        3. customer_who 字段
        4. customer_why + customer_problem 组合
        5. business_description 中的关键词
        6. 默认通用目标客户
        """
        # 1. 选中的目标用户画像优先
        selected_info = params.get('selected_target_info')
        if selected_info:
            if isinstance(selected_info, dict):
                return selected_info.get('name', '') or selected_info.get('description', '')
            return str(selected_info)

        # 2. 显式参数优先
        if params.get('target_customer'):
            return params['target_customer']

        # 2. customer_who 字段
        customer_who = params.get('customer_who', '').strip()
        if customer_who:
            return customer_who

        # 3. 从 customer_why 和 customer_problem 组合推断
        customer_why = params.get('customer_why', '').strip()
        customer_problem = params.get('customer_problem', '').strip()
        customer_story = params.get('customer_story', '').strip()

        if customer_why or customer_problem or customer_story:
            parts = []
            if customer_why:
                parts.append(f"找您原因：{customer_why}")
            if customer_problem:
                parts.append(f"痛点：{customer_problem}")
            if customer_story:
                # 截取故事的前50字
                story_preview = customer_story[:50] + ('...' if len(customer_story) > 50 else '')
                parts.append(f"故事：{story_preview}")
            return ' | '.join(parts)

        # 4. 从业务描述推断
        business_desc = params.get('business_description', '')
        if business_desc:
            # 提取业务描述中的关键信息作为目标客户
            desc = business_desc.lower()
            if any(k in desc for k in ['写字楼', '企业', '公司', ' office']):
                return '企业客户/写字楼'
            elif any(k in desc for k in ['餐厅', '饭店', '酒店', '餐饮']):
                return '餐饮商家'
            elif any(k in desc for k in ['个人', '家庭', '居民']):
                return '个人/家庭用户'
            elif any(k in desc for k in ['批发', '代理', '经销商']):
                return '批发商/代理商'

        # 5. 从经营类型推断
        business_type = params.get('business_type', '')
        if business_type == 'enterprise':
            return '企业客户'
        elif business_type == 'local_service':
            return '本地居民/商户'
        elif business_type == 'product':
            return '消费者'
        elif business_type == 'personal':
            return '个人粉丝/追随者'

        # 6. 默认值
        return '普通消费者'

    @classmethod
    def _get_quota_message(cls, reason: str, quota_info: Dict) -> str:
        """获取配额提示消息"""
        messages = {
            'daily_limit_exceeded': f'今日免费次数已用完，明天 {quota_info.get("reset_at", "00:00")} 重置',
            'monthly_limit_exceeded': f'本月生成次数已用完，超量需支付 {quota_info.get("overage_price", 3)} 元/次',
        }
        return messages.get(reason, '配额不足')

    @classmethod
    def get_generation_history(cls, user: PublicUser, page: int = 1,
                              per_page: int = 20) -> Dict:
        """获取生成历史"""
        query = PublicGeneration.query.filter_by(user_id=user.id).order_by(
            PublicGeneration.created_at.desc()
        )
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            'items': [{
                'id': g.id,
                'industry': g.industry,
                'target_customer': g.target_customer,
                'titles': g.titles,
                'tags': g.tags,
                'created_at': g.created_at.isoformat(),
            } for g in pagination.items],
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages,
        }


# 全局实例
content_generator = ContentGenerator()
