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
from models.models import db, PersonaUserProblem
from models.public_models import SavedPortrait, PublicGeneration, PublicIndustryTopic


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
    若来自 JSON 库（portrait.topic_library），智能生成默认场景选项。

    Args:
        topics: 选题列表（字典）

    Returns:
        补充后的选题列表
    """
    enriched = []
    for topic in topics:
        t = dict(topic)

        if isinstance(t.get('scene_options'), list) and len(t.get('scene_options', [])) > 0:
            # 已有 scene_options，保持不变
            pass
        elif 'industry' in t and 'title' in t:
            # 从数据库查询 scene_options
            db_topic = PublicIndustryTopic.query.filter_by(title=t['title']).first()
            if db_topic and db_topic.scene_options:
                t['scene_options'] = db_topic.scene_options
                t['content_style'] = db_topic.content_style or ''
            else:
                # 数据库查询不到，智能生成默认场景选项
                t['scene_options'] = _generate_default_scene_options(t)
                t['content_style'] = t.get('content_style', '') or (t['scene_options'][0]['风格'] if t['scene_options'] else '')
        else:
            # 其他情况，智能生成默认场景选项
            t['scene_options'] = _generate_default_scene_options(t)
            t['content_style'] = t.get('content_style', '') or (t['scene_options'][0]['风格'] if t['scene_options'] else '')

        enriched.append(t)

    return enriched


def _generate_default_scene_options(topic: dict) -> list:
    """
    为单个选题智能生成默认的场景选项。

    场景选项结构：[{"id": "...", "组合": "...", "标签": "...", "风格": "..."}]

    Args:
        topic: 选题字典

    Returns:
        场景选项列表（3-5个选项）
    """
    import uuid as uuid_module
    import re

    scene_options = []

    # 从选题中提取信息
    title = topic.get('title', '')
    type_key = topic.get('type_key', '')
    type_name = topic.get('type_name', '')
    keywords = topic.get('keywords', [])
    content_direction = topic.get('content_direction', '')

    # 从标题中提取人群和时间
    user_patterns = [
        r'([\u4e00-\u9fa5]{2,6}家长)', r'([\u4e00-\u9fa5]{2,6}学生)',
        r'([\u4e00-\u9fa5]{2,6}人群)', r'([\u4e00-\u9fa5]{2,6}用户)',
        r'([\u4e00-\u9fa5]{2,6}业主)', r'([\u4e00-\u9fa5]{2,6}老板)',
    ]

    users = []
    for pattern in user_patterns:
        match = re.search(pattern, title)
        if match:
            users.append(match.group(1))

    if not users:
        # 从 keywords 提取
        for kw in keywords:
            for pattern in user_patterns:
                match = re.search(pattern, str(kw))
                if match:
                    users.append(match.group(1))
                    break
            if users:
                break

    if not users:
        # 从 type_name 推断
        if '学生' in type_name or '家长' in type_name:
            users = ['高三家长', '高三学生', '复读生家长']
        elif '业主' in type_name:
            users = ['业主', '装修业主']
        else:
            users = ['目标用户', '消费者', '相关人群']

    # 从标题中提取时间/情境
    time_patterns = [
        (r'出分[前后]?', '出分后'),
        (r'填报[期间]?', '填报期间'),
        (r'截止[前夕]?', '截止前夕'),
        (r'高考', '高考季'),
        (r'毕业', '毕业季'),
        (r'开学', '开学季'),
    ]

    times = []
    for pattern, result in time_patterns:
        if re.search(pattern, title):
            times.append(result)

    if not times:
        times = ['关键时刻', '决策前', '选择困难时']

    # 基于 type_key 确定默认情绪
    type_emotions = {
        'compare': ('选择困难', '对比纠结'),
        'cause': ('疑惑不解', '想找原因'),
        'pain_point': ('焦虑担心', '急需解决'),
        'decision_encourage': ('犹豫不决', '担心风险'),
        'pitfall': ('怕踩坑', '担心被骗'),
        'effect_proof': ('效果怀疑', '担心无效'),
        'seasonal': ('时间紧迫', '时机担忧'),
        'rethink': ('认知误区', '误解纠正'),
        'default': ('焦虑迷茫', '信息不足'),
    }

    emotions = type_emotions.get(type_key, type_emotions['default'])

    user = users[0] if users else '目标用户'

    # 生成5个场景选项
    # 场景1：情绪共鸣型
    scene_options.append({
        'id': f'scene_{uuid_module.uuid4().hex[:8]}',
        '组合': f'{user} + {times[0]} + {emotions[0]}',
        '标签': f'{user} - {emotions[0]}型',
        '风格': '情绪共鸣',
    })

    # 场景2：干货科普型
    scene_options.append({
        'id': f'scene_{uuid_module.uuid4().hex[:8]}',
        '组合': f'{users[1] if len(users) > 1 else user} + {times[1] if len(times) > 1 else times[0]} + 信息不足',
        '标签': f'{users[1] if len(users) > 1 else user} - 理性型',
        '风格': '干货科普',
    })

    # 场景3：犀利吐槽型
    scene_options.append({
        'id': f'scene_{uuid_module.uuid4().hex[:8]}',
        '组合': f'{user} + {times[0]} + 常见误区',
        '标签': f'{user} - 吐槽型',
        '风格': '犀利吐槽',
    })

    # 场景4：故事叙述型
    scene_options.append({
        'id': f'scene_{uuid_module.uuid4().hex[:8]}',
        '组合': f'{user} + 经历分享 + 真实案例',
        '标签': f'{user} - 故事型',
        '风格': '故事叙述',
    })

    # 场景5：权威背书型
    scene_options.append({
        'id': f'scene_{uuid_module.uuid4().hex[:8]}',
        '组合': f'{user} + {times[0]} + 选择困难',
        '标签': f'{user} - 决策型',
        '风格': '权威背书',
    })

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

    if topic:
        result['scene_options'] = topic.scene_options or []
        result['content_style'] = topic.content_style or ''

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
