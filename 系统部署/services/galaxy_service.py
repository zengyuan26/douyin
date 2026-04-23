"""
星系图谱数据聚合服务

职责（方案A — 仅做数据聚合，不侵入路由层）：
- 查询结果的数据聚合和格式化
- 供 routes/galaxy_api.py 调用，不直接处理 HTTP 请求
- 路由层保持不变，新增逻辑下沉到服务层

调用关系：
  galaxy_api.py（路由层）
      ↓ 调用
  galaxy_service.py（数据聚合层）
      ↓ 查询
  models.py / public_models.py（数据层）
"""

from sqlalchemy import text
import uuid
from models.models import db, PersonaUserProblem
from models.public_models import SavedPortrait, PublicGeneration, PublicIndustryTopic

# 导入通用场景生成器
from services.scene_generator import scene_generator


def get_star_geo_info(portrait_id: int, user_id: int) -> dict:
    """
    获取恒星（画像）的 GEO 信息。

    Args:
        portrait_id: 画像ID
        user_id: 用户ID（权限校验用）

    Returns:
        dict，包含 geo_province / geo_city / geo_level / geo_coverages / geo_tags / cover_thumb
    """
    portrait = SavedPortrait.query.filter_by(id=portrait_id, user_id=user_id).first()
    if not portrait:
        return {}

    return {
        'geo_province': portrait.geo_province or '',
        'geo_city': portrait.geo_city or '',
        'geo_level': portrait.geo_level or 'city',
        'geo_coverages': portrait.geo_coverages or [],
        'geo_tags': portrait.geo_tags or [],
        'cover_thumb': portrait.cover_thumb or '',
    }


def get_planet_geo_info(problem_id: int) -> dict:
    """
    获取行星（问题）的 GEO 信息。

    Args:
        problem_id: 问题ID

    Returns:
        dict，包含 geo_trigger_regions / geo_seasonal_factor
    """
    problem = PersonaUserProblem.query.get(problem_id)
    if not problem:
        return {}

    return {
        'geo_trigger_regions': problem.geo_trigger_regions or [],
        'geo_seasonal_factor': problem.geo_seasonal_factor or '',
    }


def get_satellite_geo_info(generation_id: int, user_id: int) -> dict:
    """
    获取卫星（生成记录）的 GEO 信息。
    卫星的 GEO 信息从关联的恒星和行星继承。

    Args:
        generation_id: 生成记录ID
        user_id: 用户ID

    Returns:
        dict，包含 geo_target_regions / geo_adaptation_level
    """
    gen = PublicGeneration.query.filter_by(id=generation_id, user_id=user_id).first()
    if not gen:
        return {}

    # 从关联画像继承地域信息
    regions = []
    adaptation = 'medium'

    if gen.portrait_id:
        portrait = SavedPortrait.query.filter_by(
            id=gen.portrait_id, user_id=user_id
        ).first()
        if portrait:
            if portrait.geo_city:
                regions.append(portrait.geo_city)
            elif portrait.geo_province:
                regions.append(portrait.geo_province)
            regions.extend(portrait.geo_coverages or [])
            # 地域完全匹配时，适配度为 high
            if portrait.geo_level == 'city':
                adaptation = 'high'
            elif portrait.geo_level == 'nationwide':
                adaptation = 'low'

    # 去重
    regions = list(dict.fromkeys(regions))

    return {
        'geo_target_regions': regions,
        'geo_adaptation_level': adaptation,
    }


def enrich_topics_with_scene_options(topics: list) -> list:
    """
    为选题列表补充 scene_options 和 content_style 字段。
    若选题来自数据库（PublicIndustryTopic），直接从模型获取；
    若来自 JSON 库（portrait.topic_library），使用通用场景生成器生成。

    Args:
        topics: 选题列表（字典）

    Returns:
        补充后的选题列表
    """
    enriched = []
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        t = dict(topic)

        if isinstance(t.get('scene_options'), list) and len(t.get('scene_options', [])) > 0:
            # 已有 scene_options，转换为新格式
            t['scene_options'] = _normalize_scene_options(t['scene_options'])
            t['scene_options'] = _fill_scene_options_to_min(t['scene_options'], t.get('title', ''))
            t['content_style'] = t.get('content_style', '') or (
                t['scene_options'][0]['style'] if t['scene_options'] else ''
            )
        elif 'industry' in t and 'title' in t:
            # 从数据库查询 scene_options
            db_topic = PublicIndustryTopic.query.filter_by(title=t['title']).first()
            if db_topic and db_topic.scene_options:
                t['scene_options'] = _normalize_scene_options(db_topic.scene_options)
                t['scene_options'] = _fill_scene_options_to_min(t['scene_options'], t.get('title', ''))
                t['content_style'] = db_topic.content_style or (
                    t['scene_options'][0]['style'] if t['scene_options'] else ''
                )
            else:
                # 数据库查询不到，使用通用场景生成器
                t['scene_options'] = scene_generator.generate_scenes(t)
                t['scene_options'] = _fill_scene_options_to_min(t['scene_options'], t.get('title', ''))
                t['content_style'] = t.get('content_style', '') or (
                    t['scene_options'][0]['style'] if t['scene_options'] else ''
                )
        else:
            # 其他情况，使用通用场景生成器
            t['scene_options'] = scene_generator.generate_scenes(t)
            t['scene_options'] = _fill_scene_options_to_min(t['scene_options'], t.get('title', ''))
            t['content_style'] = t.get('content_style', '') or (
                t['scene_options'][0]['style'] if t['scene_options'] else ''
            )

        enriched.append(t)

    return enriched


def _normalize_scene_options(scene_options: list) -> list:
    """
    将旧格式场景选项转换为新格式。

    旧格式：[{ "id": "...", "标签": "...", "组合": "...", "风格": "..." }]
    新格式：[{ "id": "...", "pain_name": "...", "group": "...", "style": "..." }]
    """
    if not scene_options:
        return []

    normalized = []
    for scene in scene_options:
        # 如果已经是新格式，直接返回
        if 'pain_name' in scene or 'label' in scene:
            normalized.append(scene)
            continue

        # 转换为新格式
        new_scene = {
            'id': scene.get('id', f'scene_{uuid.uuid4().hex[:8]}'),
            'pain_type': _infer_pain_type_from_style(scene.get('风格', '')),
            'pain_name': scene.get('标签', '通用场景').replace('型', ''),
            'pain_desc': scene.get('组合', ''),
            'label': scene.get('标签', '通用场景'),
            'group': scene.get('组合', ''),
            'question': scene.get('组合', '怎么办'),
            'style': scene.get('风格', '情绪共鸣'),
            'priority': _infer_priority_from_style(scene.get('风格', '')),
            'urgency': 'medium',
            'keywords': [],
            'audience': _extract_audience_from_label(scene.get('标签', '')),
        }
        normalized.append(new_scene)

    # 按优先级排序
    normalized.sort(key=lambda x: x.get('priority', 99))
    return normalized[:5]  # 最多5个


def _infer_pain_type_from_style(style: str) -> str:
    """根据风格推断痛点类型"""
    style_pain_map = {
        '情绪共鸣': 'risk',
        '干货科普': 'info',
        '故事叙述': 'effect',
        '权威背书': 'choice',
        '犀利吐槽': 'cost',
    }
    return style_pain_map.get(style, 'info')


def _infer_priority_from_style(style: str) -> int:
    """根据风格推断优先级"""
    style_priority_map = {
        '情绪共鸣': 1,  # 风险担忧
        '干货科普': 5,  # 信息恐慌
        '故事叙述': 2,  # 效果怀疑
        '权威背书': 4,  # 选择困难
        '犀利吐槽': 3,  # 成本焦虑
    }
    return style_priority_map.get(style, 5)


def _extract_audience_from_label(label: str) -> str:
    """从标签中提取人群描述"""
    if not label:
        return '目标用户'
    # 去掉"型"后缀
    label = label.replace('型', '')
    # 如果包含"-"，取前面的部分
    if '-' in label:
        return label.split('-')[0].strip()
    return label


DEFAULT_SCENE_TEMPLATES = [
    {'pain_type': 'info',     'pain_name': '信息恐慌',       'style': '干货科普',   'label': '信息恐慌型'},
    {'pain_type': 'cost',    'pain_name': '成本焦虑',       'style': '犀利吐槽',   'label': '成本焦虑型'},
    {'pain_type': 'risk',    'pain_name': '风险担忧',       'style': '情绪共鸣',   'label': '风险担忧型'},
    {'pain_type': 'effect',  'pain_name': '效果怀疑',       'style': '故事叙述',   'label': '效果怀疑型'},
    {'pain_type': 'choice',  'pain_name': '选择困难',       'style': '权威背书',   'label': '选择困难型'},
]


def _fill_scene_options_to_min(scene_options: list, topic_title: str = '') -> list:
    """
    如果场景数量少于3个，补充默认场景到至少3个。

    Args:
        scene_options: 现有场景列表
        topic_title: 选题标题（用于 group 字段）

    Returns:
        至少3个场景的列表
    """
    if not scene_options:
        scene_options = []

    # 已有的 pain_type，避免重复
    existing_types = set(s.get('pain_type', 'info') for s in scene_options)

    # 补充默认场景
    count = len(scene_options)
    next_id = count
    for tmpl in DEFAULT_SCENE_TEMPLATES:
        if count >= 3:
            break
        if tmpl['pain_type'] in existing_types:
            continue

        scene_options.append({
            'id': f'scene_default_{next_id}',
            'pain_type': tmpl['pain_type'],
            'pain_name': tmpl['pain_name'],
            'pain_desc': '',
            'label': tmpl['label'],
            'group': topic_title,
            'question': tmpl['pain_name'].replace('型', '') + '怎么办',
            'style': tmpl['style'],
            'priority': count + 1,
            'urgency': 'medium',
            'keywords': [],
            'audience': '目标用户',
        })
        existing_types.add(tmpl['pain_type'])
        next_id += 1
        count += 1

    return scene_options


def get_scene_options_for_topic(topic_id_or_title) -> dict:
    """
    获取单个选题的场景选项。

    Args:
        topic_id_or_title: 选题ID或标题

    Returns:
        dict，包含 scene_options 列表和 content_style
    """
    result = {
        'scene_options': [],
        'content_style': '',
    }

    if isinstance(topic_id_or_title, int):
        topic = PublicIndustryTopic.query.get(topic_id_or_title)
    else:
        topic = PublicIndustryTopic.query.filter_by(title=str(topic_id_or_title)).first()

    if topic and topic.scene_options:
        # 转换为新格式
        result['scene_options'] = _normalize_scene_options(topic.scene_options)
        result['scene_options'] = _fill_scene_options_to_min(result['scene_options'], topic.title or '')
        result['content_style'] = topic.content_style or (
            result['scene_options'][0]['style'] if result['scene_options'] else ''
        )

    return result


def count_generations_by_geo(user_id: int, geo_province: str = None) -> dict:
    """
    按地域统计用户的生成记录数量。

    Args:
        user_id: 用户ID
        geo_province: 省份筛选（可选）

    Returns:
        dict，key 为地域，value 为生成数量
    """
    query = db.session.execute(
        text("""
            SELECT
                COALESCE(sp.geo_province, '全国') as geo,
                COUNT(g.id) as cnt
            FROM public_generations g
            LEFT JOIN saved_portraits sp ON g.portrait_id = sp.id AND g.user_id = sp.user_id
            WHERE g.user_id = :uid
        """),
        {'uid': user_id}
    )

    result = {}
    for row in query.fetchall():
        geo, cnt = row
        result[geo] = cnt

    return result
