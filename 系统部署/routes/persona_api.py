"""
人群画像生成 API

功能：
1. 问题挖掘：使用方问题 + 付费方顾虑
2. 人群画像生成：按问题分批生成
3. 会话管理：保存/加载分析结果
4. 分级模型支持：免费=turbo(快速)，付费=plus(精准)
5. V2版本：集成画像维度上下文，生成更精准的人群画像
"""
import json
import logging
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from models.models import (
    db, PersonaSession, PersonaUserProblem,
    PersonaBuyerConcern, PersonaPortrait
)
from models.public_models import PublicUser
from services.llm import get_llm_service
from services.persona_llm_manager import PersonaLLMManager, GenerationLimits
from services.portrait_dimension_service import (
    build_portrait_generation_context,
    get_barrier_mapping_for_ai,
    generate_portrait_prompt
)
from datetime import datetime

logger = logging.getLogger(__name__)

persona_api = Blueprint('persona_api', __name__)


# ========== 提示词模板 ==========

PROBLEM_MINING_PROMPT = """## 角色
你是一位专业的用户研究专家，擅长从业务场景中挖掘用户问题和购买顾虑。

## 任务
分析以下业务场景，帮我挖掘：
1. **使用方问题**：产品/服务要解决的核心问题
2. **付费方顾虑**：购买决策时的心理障碍

## 业务信息
- 行业/品类：{industry}
- 业务类型：{business_type}
- 产品/服务描述：{description}
- 经营模式：{business_model}
- 目标用户画像：{target_users}
- 购买方与使用方关系：{buyer_relationship}

## 分析要求
请结合以上业务信息，站在用户（购买方和使用方）的角度思考：
- 用户在什么场景下会需要这个产品/服务？
- 用户购买时最担心什么？
- 用户使用过程中会遇到什么问题？
- 用户的顾虑和痛点是什么？

请尽可能多地挖掘问题，覆盖用户从产生需求到购买再到使用的全流程问题。

## 输出要求

### 1. 使用方问题清单
请列出使用该产品/服务时要解决的核心问题，**至少列出10个问题**，每个问题需要包含：
- 问题名称（如：乳糖不耐受、过敏体质）
- 具体表现（如：喝奶后腹泻、湿疹反复）
- 严重程度（高/中/低）
- 用户意识（有意识/无意识）

### 2. 付费方顾虑清单
请列出购买该产品/服务时的顾虑，**至少列出10个顾虑**：
- 真假顾虑：会不会买到假货/不靠谱？
- 价格顾虑：值不值这个价？
- 选择顾虑：哪个更适合我？
- 信任顾虑：商家说的是真的吗？

### 3. 购买方与使用方关系
- 如果购买方≠使用方，请分别描述两方特征

请用 JSON 格式输出：
```json
{{
  "user_problems": [
    {{
      "name": "问题名称",
      "description": "问题描述",
      "specific_symptoms": "具体表现",
      "severity": "高/中/低",
      "user_awareness": "有意识/无意识",
      "trigger_scenario": "触发场景"
    }}
  ],
  "buyer_concerns": [
    {{
      "concern_type": "真假/价格/选择/信任",
      "name": "顾虑名称",
      "description": "具体描述",
      "estimated_ratio": "预估占比"
    }}
  ],
  "buyer_user_relationship": {{
    "buyer_equals_user": true/false,
    "buyer_description": "购买方特征（如果分开）",
    "user_description": "使用方特征（如果分开）"
  }}
}}
```"""


PORTRAIT_GENERATION_PROMPT = """## 角色
你是一位精准营销专家，擅长基于用户问题生成精准的长尾细分人群画像。

## 任务
基于以下问题，生成一批精准人群画像。

## 业务背景
- 行业/品类：{industry}
- 业务类型：{business_type}
- 经营模式：{business_model}
- 目标用户：{target_users}

## 使用方问题
{user_problem}

## 付费方顾虑（参考）
{buyer_concerns}

## 购买方与使用方关系
{buyer_relationship}

## 输出要求

请为这个问题生成一批（至少10个）精准人群画像，每个画像需要包含：

```json
{{
  "portraits": [
    {{
      "name": "画像名称（如：乳糖不耐受宝宝妈妈）",
      "user_description": "使用方特征描述",
      "user_core_problem": "使用方核心问题",
      "user_specific_symptoms": "具体表现",
      "user_pain_level": "痛点程度（非常急迫/急迫/一般）",
      "buyer_description": "购买方特征描述（如果与使用方分开）",
      "buyer_core_problem": "购买方核心问题",
      "buyer_concerns": {{
        "真假": "具体顾虑",
        "价格": "具体顾虑",
        "选择": "具体顾虑",
        "信任": "具体顾虑"
      }},
      "user_journey": "问题产生 → 搜索/咨询 → 评估 → 购买 → 使用 → 反馈",
      "content_topics": [
        {{"type": "种草", "topic": "选题方向", "keywords": "关键词"}},
        {{"type": "科普", "topic": "选题方向", "keywords": "关键词"}}
      ],
      "search_keywords": ["用户会搜索的关键词1", "用户会搜索的关键词2"]
    }}
  ]
}}
```

**重要**：每个画像要聚焦在一个具体问题上，不要泛泛而谈。画像之间要有差异化。

**失败情况**：如果无法生成有效的画像，请返回空的 portraits 数组，不要生成假数据！"""


# ========== 分步生成提示词（精简版，快速响应）==========

STEP1_PROBLEM_TYPES_PROMPT = """## 角色
你是一位用户研究专家。

## 任务
快速识别该业务的主要问题类型和目标人群身份，组合成卡片标题。

## 业务信息
- 行业：{industry}
- 产品/服务：{description}
- 买用关系：{buyer_relationship}

## 输出要求
用 JSON 格式输出：

```json
{{
  "is_buyer_user_same": true/false,
  "problem_types": [
    {{
      "display_name": "精致白领→担心清洁效果",
      "severity": "高"
    }},
    {{
      "display_name": "价格敏感用户→怕被宰",
      "severity": "中"
    }}
  ]
}}
```

## 格式说明
- `display_name`: 格式为【身份】→【关心的问题】，简洁好记
- `severity`: 问题重要程度（高/中/低）

**简洁为王！保持简短！**"""


# ========== 分级模板生成提示词 ==========

# 免费用户 - 极简4字段模板
FREE_PORTRAIT_TEMPLATE = """## 任务
基于问题类型和目标身份，生成精准人群画像。

## 问题类型
{problem_type}

## 目标身份
{target_identity}

## 输出格式（每行一个，用 | 分隔）
名称|年龄段|核心痛点|目标

示例：
{target_identity}|25-35岁|担心效果不好|找到靠谱的服务

直接输出 {count} 行，格式正确，不要其他文字。"""

# 付费用户 - 丰富8字段模板
PAID_PORTRAIT_TEMPLATE = """## 任务
基于问题类型和目标身份，生成精准人群画像。

## 问题类型
{problem_type}

## 目标身份
{target_identity}

## 输出格式（每行一个，用 | 分隔）
名称|年龄段|职业|核心痛点|购买目标|购买顾虑|使用场景|搜索关键词

示例：
{target_identity}|28-35岁|都市白领|担心效果|找到放心的服务|怕被坑|工作日下班后|附近洗鞋店推荐

直接输出 {count} 行，格式正确，不要其他文字。"""

STEP2_PORTRAIT_PROMPT = """## 任务
基于以下问题，生成精准人群画像。

## 业务：{industry}

## 问题类型
{problem_type}

## 输出格式（每行一个，用 | 分隔）
{fields}

直接输出 {count} 行，格式正确，不要其他文字。"""


# ========== 一键完成：问题挖掘+画像生成 ==========

"""## 任务
基于以下问题，生成精简画像。

## 业务：{industry}

## 问题类型
{problem_type}

## 生成要求
生成 {count} 个画像，每个只需 4 个核心字段：

```json
{{
  "portraits": [
    {{
      "name": "画像名称",
      "user_description": "用户特征",
      "user_core_problem": "核心问题",
      "search_keywords": ["关键词1", "关键词2"]
    }}
  ]
}}
```

**简洁为王！每个画像不超过50字！**"""


# ========== 分步生成 API（快速响应）==========

@persona_api.route('/persona/step1_identify_problem_types', methods=['POST'])
@login_required
def step1_identify_problem_types():
    """
    步骤1：快速识别问题类型（轻量级，~10秒）
    免费用户：最多 2 个问题类型
    付费用户：最多 6 个问题类型
    """
    data = request.get_json()
    session_id = data.get('session_id')

    public_user = PublicUser.query.filter_by(email=current_user.email).first()
    limits = PersonaLLMManager.get_user_limits(public_user)

    session_obj = PersonaSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first()

    if not session_obj:
        return jsonify({'code': 404, 'message': '会话不存在', 'data': None})

    session_obj.status = 'processing'
    db.session.commit()

    input_data = session_obj.input_data or {}

    # 判断买用关系
    business_type = input_data.get('business_type', 'local_service')
    if business_type == 'product':
        buyer_relationship = "买的人不用（如宝妈买奶粉给宝宝喝）"
    elif business_type == 'enterprise':
        buyer_relationship = "买的人不用（如老板买软件给员工用）"
    else:
        buyer_relationship = "自己用自己买（如洗鞋、理发等个人服务）"

    prompt = STEP1_PROBLEM_TYPES_PROMPT.format(
        industry=session_obj.industry,
        description=input_data.get('description', ''),
        buyer_relationship=buyer_relationship
    )

    try:
        response, stats = PersonaLLMManager.call_llm(
            user=public_user,
            prompt=prompt,
            call_type='step1_problem_types',
            temperature=0.5,
            max_tokens=1000
        )

        if not response:
            session_obj.status = 'failed'
            db.session.commit()
            return jsonify({'code': 500, 'message': 'LLM 调用失败', 'data': None})

        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        result = json.loads(json_match.group()) if json_match else json.loads(response)

        is_buyer_user_same = result.get('is_buyer_user_same', False)
        problem_types = result.get('problem_types', [])[:limits.max_problem_types]

        # 标准化字段名：确保有 display_name
        for pt in problem_types:
            # 优先用 display_name，如果没有则尝试其他字段组合
            if not pt.get('display_name'):
                identity = pt.get('target_identity', '')
                type_name = pt.get('type_name', '')
                if identity and type_name:
                    pt['display_name'] = f"{identity}→{type_name}"
                elif type_name:
                    pt['display_name'] = type_name

        session_obj.problem_types_data = problem_types
        session_obj.buyer_concerns = []  # 简化版不输出 buyer_concerns
        session_obj.status = 'completed'
        db.session.commit()

        return jsonify({
            'code': 200,
            'message': '问题类型识别完成',
            'data': {
                'is_buyer_user_same': is_buyer_user_same,
                'problem_types': problem_types,
                'limits': {
                    'max_problem_types': limits.max_problem_types,
                    'portraits_per_type': limits.portraits_per_type,
                    'is_paid': public_user.is_paid_user() if public_user else False
                },
                'stats': stats
            }
        })

    except Exception as e:
        logger.error(f"步骤1失败: {e}")
        session_obj.status = 'failed'
        db.session.commit()
        return jsonify({'code': 500, 'message': f'处理失败: {str(e)}', 'data': None})


@persona_api.route('/persona/step2_generate_portraits', methods=['POST'])
@login_required
def step2_generate_portraits():
    """
    步骤2：为指定问题类型生成人群画像
    免费用户：每类型 2 个画像
    付费用户：每类型 5 个画像
    """
    data = request.get_json()
    session_id = data.get('session_id')
    problem_type_name = data.get('problem_type_name', '')

    public_user = PublicUser.query.filter_by(email=current_user.email).first()
    limits = PersonaLLMManager.get_user_limits(public_user)

    session_obj = PersonaSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first()

    if not session_obj:
        return jsonify({'code': 404, 'message': '会话不存在', 'data': None})

    problem_types_data = session_obj.problem_types_data or []

    # display_name 格式为 "身份→问题"，需要拆分
    identity = ""
    problem_type = problem_type_name
    if "→" in problem_type_name:
        parts = problem_type_name.split("→")
        identity = parts[0].strip()
        problem_type = parts[1].strip() if len(parts) > 1 else problem_type_name

    # 根据用户等级选择模板
    is_paid = public_user and public_user.is_paid_user()

    if is_paid:
        # 付费用户 - 丰富8字段
        template = PAID_PORTRAIT_TEMPLATE
    else:
        # 免费用户 - 极简4字段
        template = FREE_PORTRAIT_TEMPLATE

    # 传入问题类型和身份，让 LLM 更精准生成
    prompt = template.format(
        problem_type=problem_type,
        target_identity=identity,
        count=limits.portraits_per_type
    )

    try:
        response, stats = PersonaLLMManager.call_llm(
            user=public_user,
            prompt=prompt,
            call_type='step2_portraits',
            temperature=0.7,
            max_tokens=800
        )

        if not response:
            return jsonify({'code': 500, 'message': 'LLM 调用失败', 'data': None})

        # 解析模板格式响应
        portraits = parse_template_response(response, is_paid)

        return jsonify({
            'code': 200,
            'message': '画像生成完成',
            'data': {
                'problem_type_name': problem_type_name,
                'identity': identity,
                'problem_type': problem_type,
                'portraits': portraits,
                'is_paid': is_paid,
                'stats': stats
            }
        })

    except Exception as e:
        logger.error(f"步骤2失败: {e}")
        return jsonify({'code': 500, 'message': f'处理失败: {str(e)}', 'data': None})


def parse_template_response(response: str, is_paid: bool) -> list:
    """
    解析模板格式响应

    免费用户格式：名称|年龄段|核心痛点|目标
    付费用户格式：名称|年龄段|职业|核心痛点|购买目标|购买顾虑|使用场景|搜索关键词
    """
    portraits = []
    lines = response.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('{'):
            continue

        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 4:
            continue

        if is_paid:
            # 付费用户 - 8字段
            portrait = {
                "name": parts[0],
                "age_range": parts[1],
                "occupation": parts[2] if len(parts) > 2 else "",
                "pain_point": parts[3] if len(parts) > 3 else "",
                "goal": parts[4] if len(parts) > 4 else "",
                "concern": parts[5] if len(parts) > 5 else "",
                "scenario": parts[6] if len(parts) > 6 else "",
                "search_keywords": [parts[7]] if len(parts) > 7 else [],
            }
        else:
            # 免费用户 - 4字段
            portrait = {
                "name": parts[0],
                "age_range": parts[1],
                "pain_point": parts[2] if len(parts) > 2 else "",
                "goal": parts[3] if len(parts) > 3 else "",
            }

        portraits.append(portrait)

    return portraits


@persona_api.route('/persona/step2_generate_all_portraits', methods=['POST'])
@login_required
def step2_generate_all_portraits():
    """
    步骤2（批量）：为所有问题类型生成画像
    仅限付费用户调用
    """
    data = request.get_json()
    session_id = data.get('session_id')

    public_user = PublicUser.query.filter_by(email=current_user.email).first()
    limits = PersonaLLMManager.get_user_limits(public_user)

    session_obj = PersonaSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first()

    if not session_obj:
        return jsonify({'code': 404, 'message': '会话不存在', 'data': None})

    if not public_user or not public_user.is_paid_user():
        return jsonify({
            'code': 403,
            'message': '免费用户请逐个类型生成画像',
            'data': {'upgrade_required': True, 'limits': {
                'max_problem_types': limits.max_problem_types,
                'portraits_per_type': limits.portraits_per_type
            }}
        })

    problem_types_data = session_obj.problem_types_data or []
    all_portraits = {}

    for pt in problem_types_data:
        problem_type_name = pt.get('type_name', '')
        problems = pt.get('problems', [])
        problem_desc = '\n'.join([f"- {p.get('name', '')}: {p.get('description', '')}" for p in problems[:5]])

        # 使用付费模板
        prompt = PAID_PORTRAIT_TEMPLATE.format(
            problem_type=problem_desc,
            count=limits.portraits_per_type
        )

        try:
            response, _ = PersonaLLMManager.call_llm(
                user=public_user,
                prompt=prompt,
                call_type='step2_portraits_batch',
                temperature=0.7,
                max_tokens=800
            )

            if response:
                portraits = parse_template_response(response, is_paid=True)
                all_portraits[problem_type_name] = portraits

        except Exception as e:
            logger.error(f"批量生成失败 ({problem_type_name}): {e}")
            continue

    session_obj.portraits_by_type = all_portraits
    db.session.commit()

    return jsonify({
        'code': 200,
        'message': '全部画像生成完成',
        'data': {'portraits_by_type': all_portraits, 'is_paid': True}
    })


# ========== 一键完成：问题挖掘+画像生成 ==========

COMBINED_MINING_PROMPT = """## 角色
你是一位用户研究专家。

## 任务
分析业务，挖掘问题并生成人群画像。

## 业务信息
- 行业：{industry}
- 产品/服务：{description}
- 经营模式：{business_model}

## 输出要求

### 问题分类
```json
{{
  "problem_types": [
    {{
      "type_name": "问题类型名称",
      "severity": "⭐数量",
      "problems": [
        {{"name": "问题名称", "description": "问题描述"}}
      ]
    }}
  ],
  "buyer_concerns": [
    {{"concern_type": "真假/价格/选择/信任", "name": "顾虑名称"}}
  ]
}}
```

### 人群画像（精简版，每个问题类型 {portrait_count} 个）
```json
{{
  "portraits_by_type": {{
    "类型名称": [
      {{
        "name": "画像名称",
        "user_description": "用户特征",
        "user_core_problem": "核心问题",
        "search_keywords": ["关键词1", "关键词2"]
      }}
    ]
  }}
}}
```

**简洁为王！每个画像不超过50字！**"""




# ========== V2 画像生成：集成画像维度上下文 ==========

PORTRAIT_V2_PROMPT = """你是精准营销专家。基于以下业务信息，生成精准人群画像。

=== 业务信息 ===
{business_info}

=== 问题卡片（识别阶段产出） ===
- 问题名称：{problem_name}
- 问题描述：{problem_description}
- 具体表现：{specific_symptoms}
- 严重程度：{severity}

=== 画像维度上下文 ===
从以下维度中选择适用项，生成精准画像：

【矛盾类型】
{conflict_types}
说明：缺失型=没有/不足，替代型=有但不好，冲突型=想要但有顾虑

【障碍维度】
{barrier_dimensions}
说明：影响用户转变的因素，选择1-2个主要障碍即可

【障碍含义】
{barrier_descriptions}

【障碍→内容方向映射】
{barrier_mapping}

【情感维度】
{emotional_dims}

【社交维度】
{social_dims}

【风险维度】
{risk_dims}

【成本维度】
{cost_dims}

【效率维度】
{efficiency_dims}

=== 画像要求 ===
1. 【矛盾类型】选择一个主要矛盾
2. 【障碍】选择1-2个主要障碍（过多会让画像模糊）
3. 【内容方向】根据障碍→内容映射确定内容方向
4. 【情感/社交/风险/成本/效率】选择匹配的

=== 输出格式 ===
只输出JSON，不要其他文字：
```json
{{
  "portraits": [
    {{
      "name": "【矛盾】使用人状态+障碍+情感特征",
      "conflict_type": "矛盾类型",
      "barriers": ["障碍1", "障碍2"],
      "emotion": "情感类型",
      "social": "社交类型",
      "risk": "风险类型",
      "cost": "成本类型",
      "efficiency": "效率类型",
      "content_directions": ["内容方向1", "内容方向2"],
      "search_keywords": ["关键词1", "关键词2"]
    }}
  ]
}}
```"""


def build_v2_portrait_context() -> dict:
    """
    构建V2画像生成的完整上下文
    从画像维度服务获取精简维度信息
    """
    from services.portrait_dimension_service import (
        build_portrait_generation_context,
        get_barrier_mapping_for_ai,
        get_barrier_descriptions_for_ai
    )
    
    context = build_portrait_generation_context()
    barrier_mapping = get_barrier_mapping_for_ai()
    barrier_desc = get_barrier_descriptions_for_ai()
    
    # 格式化障碍映射
    barrier_mapping_str = "\n".join([
        f"{k}→{v}" for k, v in barrier_mapping.items()
    ]) if isinstance(barrier_mapping, dict) else str(barrier_mapping)
    
    return {
        'conflict_types': context.get('矛盾类型', ''),
        'barrier_dimensions': context.get('障碍维度', ''),
        'barrier_descriptions': barrier_desc,
        'barrier_mapping': barrier_mapping_str,
        'emotional_dims': context.get('情感维度', ''),
        'social_dims': context.get('社交维度', ''),
        'risk_dims': context.get('风险维度', ''),
        'cost_dims': context.get('成本维度', ''),
        'efficiency_dims': context.get('效率维度', '')
    }



# ========== API 路由 ==========

@persona_api.route('/persona/generate_portraits_v2', methods=['POST'])
@login_required
def generate_portraits_v2():
    """
    V2画像生成：集成画像维度上下文
    基于问题卡片信息 + 画像维度 → 生成精准人群画像
    """
    data = request.get_json()
    session_id = data.get('session_id')
    problem_id = data.get('problem_id')

    session_obj = PersonaSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first()

    if not session_obj:
        return jsonify({'code': 404, 'message': '会话不存在', 'data': None})

    # 获取问题
    if problem_id:
        problems = PersonaUserProblem.query.filter_by(
            session_id=session_id, id=problem_id
        ).all()
    else:
        problems = PersonaUserProblem.query.filter_by(
            session_id=session_id
        ).order_by(PersonaUserProblem.sort_order).all()

    if not problems:
        return jsonify({'code': 400, 'message': '没有可用的使用方问题', 'data': None})

    # 获取业务信息
    input_data = session_obj.input_data or {}
    
    # 构建业务信息
    business_info = f"""行业：{session_obj.industry}
产品/服务：{input_data.get('description', '')}
业务类型：{session_obj.business_type}
目标用户：{input_data.get('target_users', '')}"""

    # 获取画像维度上下文
    portrait_context = build_v2_portrait_context()

    # 获取已有批次号
    last_batch = db.session.query(db.func.max(PersonaPortrait.batch_number)).filter_by(
        session_id=session_id
    ).scalar() or 0
    new_batch = last_batch + 1

    all_portraits = []
    failed_count = 0

    # 为每个问题生成画像
    for problem in problems:
        prompt = PORTRAIT_V2_PROMPT.format(
            business_info=business_info,
            problem_name=problem.name,
            problem_description=problem.description or '无',
            specific_symptoms=problem.specific_symptoms or '无',
            severity=problem.severity or '一般',
            conflict_types=portrait_context['conflict_types'],
            barrier_dimensions=portrait_context['barrier_dimensions'],
            barrier_descriptions=portrait_context['barrier_descriptions'],
            barrier_mapping=portrait_context['barrier_mapping'],
            emotional_dims=portrait_context['emotional_dims'],
            social_dims=portrait_context['social_dims'],
            risk_dims=portrait_context['risk_dims'],
            cost_dims=portrait_context['cost_dims'],
            efficiency_dims=portrait_context['efficiency_dims']
        )

        try:
            llm_service = get_llm_service()
            response = llm_service.chat([{"role": "user", "content": prompt}])

            # 解析 JSON 响应
            try:
                result_data = json.loads(response)
                if isinstance(result_data, list):
                    portraits_data = result_data
                elif isinstance(result_data, dict):
                    portraits_data = result_data.get('portraits', [])
                else:
                    portraits_data = []
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'\[[\s\S]*\]', response)
                if json_match:
                    try:
                        portraits_data = json.loads(json_match.group())
                    except:
                        portraits_data = []
                else:
                    json_match = re.search(r'\{[\s\S]*\}', response)
                    if json_match:
                        try:
                            result_data = json.loads(json_match.group())
                            portraits_data = result_data.get('portraits', []) if isinstance(result_data, dict) else []
                        except:
                            portraits_data = []
                    else:
                        portraits_data = []
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            portraits_data = []
            failed_count += 1

        # 保存画像
        for i, portrait in enumerate(portraits_data):
            if not isinstance(portrait, dict):
                continue

            portrait_obj = PersonaPortrait(
                session_id=session_id,
                problem_id=problem.id,
                name=portrait.get('name', ''),
                batch_number=new_batch,
                user_description=portrait.get('identity', '') or portrait.get('user_description', ''),
                user_core_problem=portrait.get('core_problem', '') or portrait.get('user_core_problem', ''),
                user_specific_symptoms=portrait.get('specific_symptoms', '') or portrait.get('user_specific_symptoms', ''),
                buyer_concerns=portrait.get('buyer_concerns', {}),
                content_topics=[{'type': d, 'topic': '', 'keywords': ''} for d in (portrait.get('content_directions', []) or [])],
                search_keywords=portrait.get('search_keywords', []) or [],
                sort_order=i
            )
            db.session.add(portrait_obj)
            all_portraits.append({
                'problem_id': problem.id,
                'problem_name': problem.name,
                **portrait
            })

    # 更新会话统计
    session_obj.portrait_count = PersonaPortrait.query.filter_by(
        session_id=session_id
    ).count()
    db.session.commit()

    return jsonify({
        'code': 200,
        'message': f'成功生成 {len(all_portraits)} 个人群画像' + (f'，{failed_count} 个问题生成失败' if failed_count else ''),
        'data': {
            'batch_number': new_batch,
            'portraits': all_portraits,
            'total_count': session_obj.portrait_count,
            'context_used': {
                'conflict_types_count': len(portrait_context['conflict_types'].split(',')) if portrait_context['conflict_types'] else 0,
                'barrier_types_count': portrait_context['barrier_dimensions'].count(':') + 1 if portrait_context['barrier_dimensions'] else 0
            }
        }
    })


@persona_api.route('/persona/create_session', methods=['POST'])
@login_required
def create_session():
    """创建新的分析会话"""
    data = request.get_json()

    industry = data.get('industry', '').strip()
    description = data.get('description', '').strip()
    business_type = data.get('business_type', 'toc')  # toc/tob/both

    if not industry:
        return jsonify({'code': 400, 'message': '请输入行业/品类', 'data': None})

    session_obj = PersonaSession(
        user_id=current_user.id,
        name=f'{industry}人群分析',
        industry=industry,
        business_type=business_type,
        buyer_equals_user=(business_type == 'toc'),
        input_data=data,
        status='draft'
    )
    db.session.add(session_obj)
    db.session.commit()

    return jsonify({
        'code': 200,
        'message': '会话创建成功',
        'data': {
            'session_id': session_obj.id,
            'industry': session_obj.industry,
            'business_type': session_obj.business_type
        }
    })


@persona_api.route('/persona/session/<int:session_id>', methods=['GET'])
@login_required
def get_session(session_id):
    """获取会话详情"""
    session_obj = PersonaSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first()

    if not session_obj:
        return jsonify({'code': 404, 'message': '会话不存在', 'data': None})

    # 获取关联数据
    user_problems = PersonaUserProblem.query.filter_by(
        session_id=session_id
    ).order_by(PersonaUserProblem.sort_order).all()

    buyer_concerns = PersonaBuyerConcern.query.filter_by(
        session_id=session_id
    ).order_by(PersonaBuyerConcern.sort_order).all()

    portraits = PersonaPortrait.query.filter_by(
        session_id=session_id
    ).order_by(PersonaPortrait.batch_number, PersonaPortrait.sort_order).all()

    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'session': {
                'id': session_obj.id,
                'name': session_obj.name,
                'industry': session_obj.industry,
                'business_type': session_obj.business_type,
                'buyer_equals_user': session_obj.buyer_equals_user,
                'status': session_obj.status,
                'portrait_count': session_obj.portrait_count,
                'created_at': session_obj.created_at.isoformat()
            },
            'user_problems': [
                {
                    'id': p.id,
                    'name': p.name,
                    'description': p.description,
                    'specific_symptoms': p.specific_symptoms,
                    'severity': p.severity,
                    'user_awareness': p.user_awareness,
                    'trigger_scenario': p.trigger_scenario,
                    'portrait_count': len(p.problem_portraits.all()) if hasattr(p, 'problem_portraits') else 0
                } for p in user_problems
            ],
            'buyer_concerns': [
                {
                    'id': c.id,
                    'concern_type': c.concern_type,
                    'name': c.name,
                    'description': c.description,
                    'estimated_ratio': c.estimated_ratio
                } for c in buyer_concerns
            ],
            'portraits': [
                {
                    'id': p.id,
                    'problem_id': p.problem_id,
                    'name': p.name,
                    'batch_number': p.batch_number,
                    'user_description': p.user_description,
                    'user_core_problem': p.user_core_problem,
                    'user_specific_symptoms': p.user_specific_symptoms,
                    'user_pain_level': p.user_pain_level,
                    'buyer_description': p.buyer_description,
                    'buyer_core_problem': p.buyer_core_problem,
                    'buyer_concerns': p.buyer_concerns,
                    'user_journey': p.user_journey,
                    'content_topics': p.content_topics,
                    'search_keywords': p.search_keywords
                } for p in portraits
            ]
        }
    })


@persona_api.route('/persona/sessions', methods=['GET'])
@login_required
def list_sessions():
    """获取用户的会话列表"""
    sessions = PersonaSession.query.filter_by(
        user_id=current_user.id
    ).order_by(PersonaSession.created_at.desc()).limit(20).all()

    return jsonify({
        'code': 200,
        'message': 'success',
        'data': [
            {
                'id': s.id,
                'name': s.name,
                'industry': s.industry,
                'status': s.status,
                'portrait_count': s.portrait_count,
                'created_at': s.created_at.isoformat()
            } for s in sessions
        ]
    })


@persona_api.route('/persona/mine_problems', methods=['POST'])
@login_required
def mine_problems():
    """挖掘使用方问题和付费方顾虑"""
    data = request.get_json()
    session_id = data.get('session_id')

    session_obj = PersonaSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first()

    if not session_obj:
        return jsonify({'code': 404, 'message': '会话不存在', 'data': None})

    # 更新会话状态
    session_obj.status = 'processing'
    db.session.commit()

    # 构建提示词
    input_data = session_obj.input_data or {}
    industry = session_obj.industry
    business_type = session_obj.business_type
    business_model = input_data.get('business_model', '')
    target_users = input_data.get('target_users', '')

    # 判断购买方与使用方关系
    buyer_relationship = "购买方 = 使用方（本人使用，本人购买）"
    if business_type in ['tob', 'both']:
        buyer_relationship = "请分析购买方和使用方是否分开（如：B端客户买给终端用户使用、家长买给宝宝、子女买给老人等）"

    # 业务类型描述
    business_type_desc = {
        'toc': 'TOC - 面向个人消费者',
        'tob': 'TOB - 面向企业客户',
        'both': '两者都有'
    }.get(business_type, 'TOC')

    prompt = PROBLEM_MINING_PROMPT.format(
        industry=industry,
        business_type=business_type_desc,
        description=input_data.get('description', ''),
        buyer_relationship=buyer_relationship,
        business_model=business_model,
        target_users=target_users
    )

    # 调用 LLM
    try:
        llm_service = get_llm_service()
        response = llm_service.chat([{"role": "user", "content": prompt}])

        # 解析 JSON 响应
        result = json.loads(response)
    except json.JSONDecodeError:
        # 尝试从响应中提取 JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            result = json.loads(json_match.group())
        else:
            session_obj.status = 'failed'
            db.session.commit()
            return jsonify({
                'code': 500,
                'message': 'LLM 响应解析失败',
                'data': None
            })
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        session_obj.status = 'failed'
        db.session.commit()
        return jsonify({
            'code': 500,
            'message': f'LLM 调用失败: {str(e)}',
            'data': None
        })

    # 保存使用方问题
    user_problems_data = result.get('user_problems', [])
    for i, problem in enumerate(user_problems_data):
        problem_obj = PersonaUserProblem(
            session_id=session_id,
            name=problem.get('name', ''),
            description=problem.get('description', ''),
            specific_symptoms=problem.get('specific_symptoms', ''),
            severity=problem.get('severity', ''),
            user_awareness=problem.get('user_awareness', ''),
            trigger_scenario=problem.get('trigger_scenario', ''),
            sort_order=i
        )
        db.session.add(problem_obj)

    # 保存付费方顾虑
    buyer_concerns_data = result.get('buyer_concerns', [])
    for i, concern in enumerate(buyer_concerns_data):
        concern_obj = PersonaBuyerConcern(
            session_id=session_id,
            concern_type=concern.get('concern_type', '其他'),
            name=concern.get('name', ''),
            description=concern.get('description', ''),
            estimated_ratio=concern.get('estimated_ratio', ''),
            sort_order=i
        )
        db.session.add(concern_obj)

    # 更新购买方与使用方关系
    buyer_user_rel = result.get('buyer_user_relationship', {})
    if buyer_user_rel:
        session_obj.buyer_equals_user = buyer_user_rel.get('buyer_equals_user', True)

    # 保存原始数据
    session_obj.user_problems_data = user_problems_data
    session_obj.buyer_concerns = buyer_concerns_data
    session_obj.status = 'completed'
    db.session.commit()

    # 返回结果
    return jsonify({
        'code': 200,
        'message': '问题挖掘完成',
        'data': {
            'user_problems': user_problems_data,
            'buyer_concerns': buyer_concerns_data,
            'buyer_equals_user': session_obj.buyer_equals_user
        }
    })


@persona_api.route('/persona/mine_and_generate', methods=['POST'])
@login_required
def mine_and_generate():
    """一键完成：问题挖掘 + 画像生成（按问题类型分组）"""
    data = request.get_json()
    session_id = data.get('session_id')

    session_obj = PersonaSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first()

    if not session_obj:
        return jsonify({'code': 404, 'message': '会话不存在', 'data': None})

    # 更新会话状态
    session_obj.status = 'processing'
    db.session.commit()

    # 构建提示词
    input_data = session_obj.input_data or {}
    industry = session_obj.industry
    business_type = session_obj.business_type
    business_model = input_data.get('business_model', '')
    target_users = input_data.get('target_users', '')

    # 判断购买方与使用方关系
    buyer_relationship = "购买方 = 使用方（本人使用，本人购买）"
    if business_type in ['tob', 'both']:
        buyer_relationship = "请分析购买方和使用方是否分开（如：B端客户买给终端用户使用、家长买给宝宝、子女买给老人等）"

    # 业务类型描述
    business_type_desc = {
        'toc': 'TOC - 面向个人消费者',
        'tob': 'TOB - 面向企业客户',
        'both': '两者都有'
    }.get(business_type, 'TOC')

    prompt = COMBINED_MINING_PROMPT.format(
        industry=industry,
        business_type=business_type_desc,
        description=input_data.get('description', ''),
        buyer_relationship=buyer_relationship,
        business_model=business_model,
        target_users=target_users
    )

    # 调用 LLM
    try:
        llm_service = get_llm_service()
        response = llm_service.chat([{"role": "user", "content": prompt}])

        # 解析 JSON 响应
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
            else:
                session_obj.status = 'failed'
                db.session.commit()
                return jsonify({
                    'code': 500,
                    'message': 'LLM 响应解析失败',
                    'data': None
                })
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        session_obj.status = 'failed'
        db.session.commit()
        return jsonify({
            'code': 500,
            'message': f'LLM 调用失败: {str(e)}',
            'data': None
        })

    # ========== 解析并保存结果 ==========

    # 1. 保存问题类型和具体问题
    problem_types_data = result.get('problem_types', [])
    all_user_problems = []
    problem_type_map = {}  # type_name -> problem_type_obj

    for type_idx, type_data in enumerate(problem_types_data):
        type_name = type_data.get('type_name', f'问题类型{type_idx + 1}')
        severity = type_data.get('severity', '')
        problems = type_data.get('problems', [])

        # 为该类型下的每个问题创建数据库记录
        for prob_idx, problem in enumerate(problems):
            problem_obj = PersonaUserProblem(
                session_id=session_id,
                name=problem.get('name', ''),
                description=problem.get('description', ''),
                specific_symptoms=problem.get('specific_symptoms', ''),
                severity=problem.get('severity', ''),
                user_awareness=problem.get('user_awareness', ''),
                trigger_scenario=problem.get('trigger_scenario', ''),
                sort_order=type_idx * 100 + prob_idx  # 按类型分组排序
            )
            db.session.add(problem_obj)
            db.session.flush()  # 获取 ID

            all_user_problems.append({
                'id': problem_obj.id,
                'type_name': type_name,
                'type_severity': severity,
                'name': problem.get('name', ''),
                'description': problem.get('description', ''),
                'specific_symptoms': problem.get('specific_symptoms', ''),
                'severity': problem.get('severity', ''),
                'user_awareness': problem.get('user_awareness', ''),
                'trigger_scenario': problem.get('trigger_scenario', ''),
                'portraits': []  # 初始化空画像
            })

    # 2. 保存付费方顾虑
    buyer_concerns_data = result.get('buyer_concerns', [])
    for i, concern in enumerate(buyer_concerns_data):
        concern_obj = PersonaBuyerConcern(
            session_id=session_id,
            concern_type=concern.get('concern_type', '其他'),
            name=concern.get('name', ''),
            description=concern.get('description', ''),
            estimated_ratio=concern.get('estimated_ratio', ''),
            sort_order=i
        )
        db.session.add(concern_obj)

    # 3. 更新购买方与使用方关系
    buyer_user_rel = result.get('buyer_user_relationship', {})
    if buyer_user_rel:
        session_obj.buyer_equals_user = buyer_user_rel.get('buyer_equals_user', True)

    # 4. 保存画像（按问题类型分组）
    portraits_by_type = result.get('portraits_by_type', {})
    all_portraits = []
    batch_number = 1

    # 建立类型名到问题ID的映射
    for prob_data in all_user_problems:
        type_name = prob_data['type_name']
        if type_name not in problem_type_map:
            problem_type_map[type_name] = []
        problem_type_map[type_name].append(prob_data['id'])

    # 按类型处理画像
    for type_name, portraits_list in portraits_by_type.items():
        if not isinstance(portraits_list, list):
            continue

        for i, portrait in enumerate(portraits_list):
            if not isinstance(portrait, dict):
                continue

            # 跳过无效画像
            if not portrait.get('name'):
                continue

            # 找到该类型下的第一个问题作为关联
            problem_ids = problem_type_map.get(type_name, [])
            problem_id = problem_ids[0] if problem_ids else all_user_problems[0]['id'] if all_user_problems else None

            if problem_id:
                portrait_obj = PersonaPortrait(
                    session_id=session_id,
                    problem_id=problem_id,
                    name=portrait.get('name', ''),
                    batch_number=batch_number,
                    user_description=portrait.get('user_description', ''),
                    user_core_problem=portrait.get('user_core_problem', ''),
                    user_specific_symptoms=portrait.get('user_specific_symptoms', ''),
                    user_pain_level=portrait.get('user_pain_level', ''),
                    buyer_description=portrait.get('buyer_description', ''),
                    buyer_core_problem=portrait.get('buyer_core_problem', ''),
                    buyer_concerns=portrait.get('buyer_concerns', {}),
                    user_journey=portrait.get('user_journey', ''),
                    content_topics=portrait.get('content_topics', []),
                    search_keywords=portrait.get('search_keywords', []),
                    sort_order=i
                )
                db.session.add(portrait_obj)

                portrait_data = {
                    'id': portrait_obj.id if portrait_obj.id else i,
                    'name': portrait.get('name', ''),
                    'user_description': portrait.get('user_description', ''),
                    'user_core_problem': portrait.get('user_core_problem', ''),
                    'user_specific_symptoms': portrait.get('user_specific_symptoms', ''),
                    'user_pain_level': portrait.get('user_pain_level', ''),
                    'buyer_description': portrait.get('buyer_description', ''),
                    'buyer_core_problem': portrait.get('buyer_core_problem', ''),
                    'buyer_concerns': portrait.get('buyer_concerns', {}),
                    'search_keywords': portrait.get('search_keywords', []),
                    'type_name': type_name
                }
                all_portraits.append(portrait_data)

                # 更新对应问题的画像列表
                for prob_data in all_user_problems:
                    if prob_data['type_name'] == type_name:
                        prob_data['portraits'].append(portrait_data)

        batch_number += 1

    # 5. 更新会话状态
    session_obj.portrait_count = len(all_portraits)
    session_obj.status = 'completed'
    db.session.commit()

    # 6. 统计
    type_summary = {}
    for prob in all_user_problems:
        type_name = prob['type_name']
        if type_name not in type_summary:
            type_summary[type_name] = {
                'type_name': type_name,
                'type_severity': prob['type_severity'],
                'problem_count': 0,
                'portrait_count': 0
            }
        type_summary[type_name]['problem_count'] += 1
        type_summary[type_name]['portrait_count'] = len(prob['portraits'])

    return jsonify({
        'code': 200,
        'message': f'完成！共生成 {len(all_user_problems)} 个问题，{len(all_portraits)} 个画像',
        'data': {
            'problem_types': list(type_summary.values()),
            'user_problems': all_user_problems,
            'buyer_concerns': buyer_concerns_data,
            'portraits': all_portraits,
            'buyer_equals_user': session_obj.buyer_equals_user
        }
    })


@persona_api.route('/persona/generate_portraits', methods=['POST'])
@login_required
def generate_portraits():
    """为指定问题生成人群画像"""
    data = request.get_json()
    session_id = data.get('session_id')
    problem_id = data.get('problem_id')  # 可选，不传则生成默认批次

    session_obj = PersonaSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first()

    if not session_obj:
        return jsonify({'code': 404, 'message': '会话不存在', 'data': None})

    # 获取问题
    if problem_id:
        problems = PersonaUserProblem.query.filter_by(
            session_id=session_id, id=problem_id
        ).all()
    else:
        # 获取所有问题
        problems = PersonaUserProblem.query.filter_by(
            session_id=session_id
        ).order_by(PersonaUserProblem.sort_order).all()

    if not problems:
        return jsonify({'code': 400, 'message': '没有可用的使用方问题', 'data': None})

    # 获取业务信息
    input_data = session_obj.input_data or {}
    business_model = input_data.get('business_model', '')
    target_users = input_data.get('target_users', '')

    # 获取付费方顾虑
    buyer_concerns = PersonaBuyerConcern.query.filter_by(
        session_id=session_id
    ).all()
    buyer_concerns_text = "\n".join([
        f"- {c.concern_type}：{c.name} - {c.description}"
        for c in buyer_concerns
    ]) if buyer_concerns else "暂无明确顾虑，请根据问题自行推断"

    # 获取已有批次号
    last_batch = db.session.query(db.func.max(PersonaPortrait.batch_number)).filter_by(
        session_id=session_id
    ).scalar() or 0
    new_batch = last_batch + 1

    all_portraits = []

    # 为每个问题生成画像
    for problem in problems:
        prompt = PORTRAIT_GENERATION_PROMPT.format(
            industry=session_obj.industry,
            business_type=session_obj.business_type,
            business_model=business_model,
            target_users=target_users,
            user_problem=f"""问题名称：{problem.name}
问题描述：{problem.description}
具体表现：{problem.specific_symptoms}
严重程度：{problem.severity}
用户意识：{problem.user_awareness}
触发场景：{problem.trigger_scenario}""",
            buyer_concerns=buyer_concerns_text,
            buyer_relationship="购买方 = 使用方" if session_obj.buyer_equals_user else "购买方 ≠ 使用方（请分别描述）"
        )

        try:
            llm_service = get_llm_service()
            response = llm_service.chat([{"role": "user", "content": prompt}])

            # 解析 JSON 响应
            try:
                result_data = json.loads(response)
                # 兼容返回列表或字典的情况
                if isinstance(result_data, list):
                    portraits_data = result_data
                elif isinstance(result_data, dict):
                    portraits_data = result_data.get('portraits', [])
                else:
                    portraits_data = []
            except json.JSONDecodeError:
                # 尝试从响应中提取 JSON
                import re
                json_match = re.search(r'\[[\s\S]*\]', response)
                if json_match:
                    try:
                        portraits_data = json.loads(json_match.group())
                    except:
                        portraits_data = []
                else:
                    json_match = re.search(r'\{[\s\S]*\}', response)
                    if json_match:
                        try:
                            result_data = json.loads(json_match.group())
                            portraits_data = result_data.get('portraits', []) if isinstance(result_data, dict) else []
                        except:
                            portraits_data = []
                    else:
                        portraits_data = []
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            portraits_data = []

        # 保存画像
        for i, portrait in enumerate(portraits_data):
            # 兼容 portrait 可能是字典或其他格式
            if not isinstance(portrait, dict):
                continue

            portrait_obj = PersonaPortrait(
                session_id=session_id,
                problem_id=problem.id,
                name=portrait.get('name', ''),
                batch_number=new_batch,
                user_description=portrait.get('user_description', ''),
                user_core_problem=portrait.get('user_core_problem', ''),
                user_specific_symptoms=portrait.get('user_specific_symptoms', ''),
                user_pain_level=portrait.get('user_pain_level', ''),
                buyer_description=portrait.get('buyer_description', ''),
                buyer_core_problem=portrait.get('buyer_core_problem', ''),
                buyer_concerns=portrait.get('buyer_concerns', {}),
                user_journey=portrait.get('user_journey', ''),
                content_topics=portrait.get('content_topics', []),
                search_keywords=portrait.get('search_keywords', []),
                sort_order=i
            )
            db.session.add(portrait_obj)
            all_portraits.append({
                'problem_name': problem.name,
                **portrait
            })

    # 更新会话统计
    session_obj.portrait_count = PersonaPortrait.query.filter_by(
        session_id=session_id
    ).count()
    session_obj.portraits = [p for p in (session_obj.portraits or [])] + all_portraits
    db.session.commit()

    return jsonify({
        'code': 200,
        'message': f'成功生成 {len(all_portraits)} 个人群画像',
        'data': {
            'batch_number': new_batch,
            'portraits': all_portraits,
            'total_count': session_obj.portrait_count
        }
    })


@persona_api.route('/persona/problem/<int:problem_id>/generate', methods=['POST'])
@login_required
def generate_portraits_for_problem(problem_id):
    """为单个问题生成人群画像"""
    problem = PersonaUserProblem.query.get(problem_id)

    if not problem:
        return jsonify({'code': 404, 'message': '问题不存在', 'data': None})

    session_obj = problem.session
    if session_obj.user_id != current_user.id:
        return jsonify({'code': 403, 'message': '无权访问', 'data': None})

    # 获取业务信息
    input_data = session_obj.input_data or {}
    business_model = input_data.get('business_model', '')
    target_users = input_data.get('target_users', '')

    # 获取付费方顾虑
    buyer_concerns = PersonaBuyerConcern.query.filter_by(
        session_id=session_obj.id
    ).all()
    buyer_concerns_text = "\n".join([
        f"- {c.concern_type}：{c.name} - {c.description}"
        for c in buyer_concerns
    ]) if buyer_concerns else "暂无明确顾虑，请根据问题自行推断"

    # 获取已有批次号（针对该问题）
    last_batch = db.session.query(db.func.max(PersonaPortrait.batch_number)).filter_by(
        session_id=session_obj.id,
        problem_id=problem_id
    ).scalar() or 0
    new_batch = last_batch + 1

    prompt = PORTRAIT_GENERATION_PROMPT.format(
        industry=session_obj.industry,
        business_type=session_obj.business_type,
        business_model=business_model,
        target_users=target_users,
        user_problem=f"""问题名称：{problem.name}
问题描述：{problem.description}
具体表现：{problem.specific_symptoms}
严重程度：{problem.severity}
用户意识：{problem.user_awareness}
触发场景：{problem.trigger_scenario}""",
        buyer_concerns=buyer_concerns_text,
        buyer_relationship="购买方 = 使用方" if session_obj.buyer_equals_user else "购买方 ≠ 使用方（请分别描述）"
    )

    try:
        llm_service = get_llm_service()
        response = llm_service.chat([{"role": "user", "content": prompt}])

        # 解析 JSON 响应
        try:
            result_data = json.loads(response)
            # 兼容返回列表或字典的情况
            if isinstance(result_data, list):
                portraits_data = result_data
            elif isinstance(result_data, dict):
                portraits_data = result_data.get('portraits', [])
            else:
                portraits_data = []
        except json.JSONDecodeError:
            # 尝试从响应中提取 JSON
            import re
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                try:
                    portraits_data = json.loads(json_match.group())
                except:
                    portraits_data = []
            else:
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    try:
                        result_data = json.loads(json_match.group())
                        portraits_data = result_data.get('portraits', []) if isinstance(result_data, dict) else []
                    except:
                        portraits_data = []
                else:
                    portraits_data = []
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'LLM 调用失败: {str(e)}',
            'data': None
        })

    # 保存画像
    saved_portraits = []
    for i, portrait in enumerate(portraits_data):
        # 兼容 portrait 可能是字典或其他格式
        if not isinstance(portrait, dict):
            continue

        portrait_obj = PersonaPortrait(
            session_id=session_obj.id,
            problem_id=problem_id,
            name=portrait.get('name', ''),
            batch_number=new_batch,
            user_description=portrait.get('user_description', ''),
            user_core_problem=portrait.get('user_core_problem', ''),
            user_specific_symptoms=portrait.get('user_specific_symptoms', ''),
            user_pain_level=portrait.get('user_pain_level', ''),
            buyer_description=portrait.get('buyer_description', ''),
            buyer_core_problem=portrait.get('buyer_core_problem', ''),
            buyer_concerns=portrait.get('buyer_concerns', {}),
            user_journey=portrait.get('user_journey', ''),
            content_topics=portrait.get('content_topics', []),
            search_keywords=portrait.get('search_keywords', []),
            sort_order=i
        )
        db.session.add(portrait_obj)
        saved_portraits.append(portrait)

    # 更新统计
    session_obj.portrait_count = PersonaPortrait.query.filter_by(
        session_id=session_obj.id
    ).count()
    db.session.commit()

    return jsonify({
        'code': 200,
        'message': f'成功生成 {len(saved_portraits)} 个人群画像',
        'data': {
            'problem_id': problem_id,
            'problem_name': problem.name,
            'batch_number': new_batch,
            'portraits': saved_portraits
        }
    })


@persona_api.route('/persona/delete_session/<int:session_id>', methods=['DELETE'])
@login_required
def delete_session(session_id):
    """删除会话"""
    session_obj = PersonaSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first()

    if not session_obj:
        return jsonify({'code': 404, 'message': '会话不存在', 'data': None})

    # 删除关联数据
    PersonaPortrait.query.filter_by(session_id=session_id).delete()
    PersonaBuyerConcern.query.filter_by(session_id=session_id).delete()
    PersonaUserProblem.query.filter_by(session_id=session_id).delete()
    PersonaSession.query.filter_by(id=session_id).delete()
    db.session.commit()

    return jsonify({
        'code': 200,
        'message': '会话已删除',
        'data': None
    })
