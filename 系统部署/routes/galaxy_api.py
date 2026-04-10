"""
星系内容宇宙 API 路由

提供 ECharts Graph 力导向图可视化所需的全部数据接口。

数据模型映射：
- 星系 = 当前登录用户（按 user_id 完全隔离）
- 恒星 = 用户画像（saved_portraits）
- 行星 = 核心问题（persona_user_problems）
- 卫星 = 历史生成的选题/内容（public_generations）

关系与连线规则：
- 恒星 → 行星：通过 portrait.problem_id 关联
- 行星 → 卫星：通过 public_generations.problem_id 关联
- 连线粗细 = 同一 problem_id 内容生成次数
"""

import logging
from flask import Blueprint, request, jsonify, session
from functools import wraps
from sqlalchemy import text, func, distinct
from models.models import db, PersonaUserProblem, PersonaPortrait
from models.public_models import PublicUser, SavedPortrait, PublicGeneration

logger = logging.getLogger(__name__)

galaxy_bp = Blueprint('galaxy', __name__, url_prefix='/public/api/galaxy')


def get_current_user():
    """获取当前登录用户"""
    user_id = session.get('public_user_id')
    if user_id:
        return PublicUser.query.get(user_id)
    return None


def login_required(f):
    """登录装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'message': '请先登录'}), 401
        return f(user, *args, **kwargs)
    return decorated_function


# =============================================================================
# 一、星系概览数据（ECharts Graph 数据）
# =============================================================================

@galaxy_bp.route('/graph', methods=['GET'])
@login_required
def get_galaxy_graph(user):
    """
    获取星系的完整 Graph 数据（恒星 + 行星 + 卫星 + 连线）
    用于 ECharts 力导向图渲染
    """
    user_id = user.id

    # ── 1. 收集所有画像（恒星） ──
    portraits = SavedPortrait.query.filter_by(user_id=user_id).all()
    stars = []
    for p in portraits:
        # 提取画像名称
        name = p.portrait_name or '未命名画像'
        if p.portrait_data and isinstance(p.portrait_data, dict):
            pd = p.portrait_data
            name = pd.get('name') or pd.get('portrait_name') or name

        stars.append({
            'id': f'star_{p.id}',
            'type': 'star',
            'portrait_id': p.id,
            'name': name,
            'portrait_name': p.portrait_name or name,
            'industry': p.industry or '',
            'target_customer': p.target_customer or '',
            'business_description': p.business_description or '',
            'portrait_data': p.portrait_data,
            'generation_status': p.generation_status or 'pending',
            'created_at': _dt_str(p.created_at),
            # ── 星系增强：恒星缩略图与地域 ──
            'cover_thumb': p.cover_thumb or '',
            'geo_province': p.geo_province or '',
            'geo_city': p.geo_city or '',
            'geo_level': p.geo_level or 'city',
            'geo_coverages': p.geo_coverages or [],
            'geo_tags': p.geo_tags or [],
        })

    # ── 2. 收集所有行星（核心问题） ──
    # 行星来自两个方面：
    # A) 画像关联的 session → 问题（from models.models PersonaPortrait + PersonaUserProblem）
    # B) 用户历史上所有 generation 关联的问题（通过 industry/target_customer 模糊匹配）

    planets = []
    planet_ids_seen = set()

    # 方案A：通过 session_id 找问题
    for star in stars:
        portrait_id = star['portrait_id']
        # 从 portrait_data 里找 session_id
        session_id = None
        pd = star.get('portrait_data', {})
        if isinstance(pd, dict):
            session_id = pd.get('session_id') or pd.get('source_session_id')

        if session_id:
            problems = PersonaUserProblem.query.filter_by(session_id=session_id).all()
            for prob in problems:
                if prob.id in planet_ids_seen:
                    continue
                planet_ids_seen.add(prob.id)
                planets.append({
                    'id': f'planet_{prob.id}',
                    'type': 'planet',
                    'problem_id': prob.id,
                    'name': prob.name or '未命名问题',
                    'description': prob.description or '',
                    'specific_symptoms': prob.specific_symptoms or '',
                    'severity': prob.severity or '中',
                    'user_awareness': prob.user_awareness or '',
                    'trigger_scenario': prob.trigger_scenario or '',
                    'created_at': _dt_str(prob.created_at),
                    'star_portrait_id': portrait_id,
                    # ── 星系增强：行星地域信息 ──
                    'geo_trigger_regions': prob.geo_trigger_regions or [],
                    'geo_seasonal_factor': prob.geo_seasonal_factor or '',
                })

    # 方案B：从历史 generation 反推行星（仅用于展示，不创建 DB 记录）
    # 按 industry + target_customer 分组，推断隐式问题
    gen_stats = db.session.execute(
        text("""
            SELECT
                industry,
                target_customer,
                COUNT(*) as gen_count
            FROM public_generations
            WHERE user_id = :uid
              AND industry IS NOT NULL
              AND industry != ''
            GROUP BY industry, target_customer
            ORDER BY gen_count DESC
            LIMIT 20
        """),
        {'uid': user_id}
    ).fetchall()

    for row in gen_stats:
        industry, target_customer, gen_count = row
        planet_name = f"{industry or '通用'}"
        if target_customer:
            planet_name += f" · {target_customer}"

        # 检查是否已存在同名行星
        existing = [pl for pl in planets if pl['name'] == planet_name]
        if existing:
            # 更新现有行星的生成次数
            existing[0]['generation_count'] = existing[0].get('generation_count', 0) + gen_count
        else:
            # 创建一个"推断行星"（没有真实 problem_id）
            planets.append({
                'id': f'planet_infer_{industry}_{target_customer}',
                'type': 'planet',
                'problem_id': None,
                'name': planet_name,
                'description': f"{target_customer or '通用用户'} 在 {industry or '相关领域'} 的内容需求",
                'specific_symptoms': '',
                'severity': '中',
                'user_awareness': '',
                'trigger_scenario': '',
                'created_at': '',
                'star_portrait_id': None,
                'generation_count': gen_count,
                'is_inferred': True,
            })

    # ── 3. 收集卫星（选题/内容） ──
    # 按 problem_id 和 portrait_id 分组，取每组最新一条作为代表
    satellites_raw = db.session.execute(
        text("""
            SELECT
                g.id,
                g.portrait_id,
                g.problem_id,
                g.industry,
                g.target_customer,
                g.titles,
                g.content,
                g.created_at,
                -- 同 problem_id 的生成次数
                (SELECT COUNT(*) FROM public_generations g2
                 WHERE g2.user_id = g.user_id
                   AND g2.problem_id IS NOT DISTINCT FROM g.problem_id) as same_problem_count,
                -- 同 portrait_id 的生成次数
                (SELECT COUNT(*) FROM public_generations g3
                 WHERE g3.user_id = g.user_id
                   AND g3.portrait_id IS NOT DISTINCT FROM g.portrait_id) as same_portrait_count
            FROM public_generations g
            WHERE g.user_id = :uid
            ORDER BY g.created_at DESC
            LIMIT 200
        """),
        {'uid': user_id}
    ).fetchall()

    # 按 (problem_id, portrait_id) 去重，每组只保留最新一条
    seen_keys = set()
    satellites = []
    for row in satellites_raw:
        gid, portrait_id, problem_id, industry, target_customer, titles, content, created_at, sp_count, spc_count = row
        key = (problem_id, portrait_id)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        # 提取标题
        title_text = ''
        if titles:
            if isinstance(titles, list) and titles:
                title_text = titles[0] if isinstance(titles[0], str) else str(titles[0])
            elif isinstance(titles, dict):
                title_text = titles.get('title', '') or titles.get('main_title', '')
            elif isinstance(titles, str):
                try:
                    parsed = __import__('json').loads(titles)
                    title_text = parsed[0] if isinstance(parsed, list) and parsed else str(parsed)
                except:
                    title_text = str(titles)

        # 截取内容摘要
        content_snippet = ''
        if content:
            content_snippet = content[:120].replace('\n', ' ').strip()

        satellites.append({
            'id': f'satellite_{gid}',
            'type': 'satellite',
            'generation_id': gid,
            'portrait_id': portrait_id,
            'problem_id': problem_id,
            'name': title_text or f"内容 #{gid}",
            'title': title_text or '',
            'content_snippet': content_snippet,
            'content_full': content or '',
            'industry': industry or '',
            'target_customer': target_customer or '',
            'created_at': _dt_str(created_at),
            'same_problem_count': sp_count or 1,
            'same_portrait_count': spc_count or 1,
        })

    # ── 4. 构建连线（links） ──
    links = []

    # 4a. 恒星 → 行星连线
    for planet in planets:
        star_portrait_id = planet.get('star_portrait_id')
        if star_portrait_id:
            links.append({
                'source': f'star_{star_portrait_id}',
                'target': planet['id'],
                'relation': 'owns',
                'weight': 1,
            })

    # 4b. 行星 → 卫星连线
    for sat in satellites:
        pid = sat.get('problem_id')
        portrait_id = sat.get('portrait_id')

        # 优先用 problem_id 找行星
        if pid:
            # 精确匹配真实行星
            matching_planets = [p for p in planets if p.get('problem_id') == pid]
            if matching_planets:
                links.append({
                    'source': matching_planets[0]['id'],
                    'target': sat['id'],
                    'relation': 'generated',
                    'weight': sat.get('same_problem_count', 1),
                })
            else:
                # 用推断行星匹配
                inferred_planets = [p for p in planets if p.get('is_inferred') and p['name'].startswith(str(pid))]
                if inferred_planets:
                    links.append({
                        'source': inferred_planets[0]['id'],
                        'target': sat['id'],
                        'relation': 'generated',
                        'weight': sat.get('same_problem_count', 1),
                    })
        elif portrait_id:
            # 没有 problem_id 时，通过 portrait_id 连到恒星
            links.append({
                'source': f'star_{portrait_id}',
                'target': sat['id'],
                'relation': 'generated',
                'weight': sat.get('same_portrait_count', 1),
            })

    # 去除重复连线
    seen_links = set()
    unique_links = []
    for link in links:
        key = (link['source'], link['target'])
        if key not in seen_links:
            seen_links.add(key)
            unique_links.append(link)

    # ── 5. 统计摘要 ──
    total_generations = PublicGeneration.query.filter_by(user_id=user_id).count()
    total_stars = len(stars)
    total_planets = len(planets)
    total_satellites = len(satellites)

    return jsonify({
        'success': True,
        'data': {
            'nodes': stars + planets + satellites,
            'links': unique_links,
            'stats': {
                'total_portraits': total_stars,
                'total_problems': total_planets,
                'total_generations': total_generations,
                'total_satellites': total_satellites,
            }
        }
    })


# =============================================================================
# 二、节点详情查询
# =============================================================================

@galaxy_bp.route('/node/star/<int:portrait_id>', methods=['GET'])
@login_required
def get_star_detail(user, portrait_id):
    """
    点击恒星（画像）获取详情面板数据
    返回：画像缩略图 + portrait_summary 五要素
    """
    portrait = SavedPortrait.query.filter_by(id=portrait_id, user_id=user.id).first()
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    pd = portrait.portrait_data or {}
    if isinstance(pd, str):
        try:
            import json
            pd = json.loads(pd)
        except:
            pd = {}

    # 提取五要素
    portrait_summary = pd.get('portrait_summary', '') or pd.get('summary', '')
    buyer_perspective = pd.get('buyer_perspective', {})
    user_perspective = pd.get('user_perspective', {})

    # 深层心理
    psychology = ''
    if isinstance(buyer_perspective, dict):
        psychology = buyer_perspective.get('psychology', '')

    # 用户画像名称
    name = pd.get('name') or portrait.portrait_name or '未命名画像'

    # 身份标签
    identity_tags = {}
    if isinstance(buyer_perspective, dict):
        identity_tags = buyer_perspective.get('identity_tags', {})
    elif isinstance(pd.get('identity_tags'), dict):
        identity_tags = pd.get('identity_tags')

    # 问题痛点
    pain_points = pd.get('pain_points', pd.get('core_pain_points', []))
    if isinstance(pain_points, str):
        pain_points = [pain_points]

    # 使用场景
    scenes = pd.get('使用场景', pd.get('usage_scenes', []))
    if isinstance(scenes, str):
        scenes = [scenes]

    # 生成次数统计
    gen_count = PublicGeneration.query.filter_by(
        user_id=user.id, portrait_id=portrait_id
    ).count()

    return jsonify({
        'success': True,
        'data': {
            'portrait_id': portrait_id,
            'name': name,
            'portrait_summary': portrait_summary,
            'portrait_name': portrait.portrait_name or name,
            'industry': portrait.industry or '',
            'target_customer': portrait.target_customer or '',
            'business_description': portrait.business_description or '',
            'identity_tags': identity_tags,
            'pain_points': pain_points,
            'scenes': scenes,
            'psychology': psychology,
            'buyer_perspective': buyer_perspective,
            'user_perspective': user_perspective,
            'portrait_data': pd,
            'generation_count': gen_count,
            'generation_status': portrait.generation_status or 'pending',
            'created_at': _dt_str(portrait.created_at),
            # ── 星系增强：恒星缩略图与地域 ──
            'cover_thumb': portrait.cover_thumb or '',
            'geo_province': portrait.geo_province or '',
            'geo_city': portrait.geo_city or '',
            'geo_level': portrait.geo_level or 'city',
            'geo_coverages': portrait.geo_coverages or [],
            'geo_tags': portrait.geo_tags or [],
        }
    })


@galaxy_bp.route('/node/planet/<int:problem_id>', methods=['GET'])
@login_required
def get_planet_detail(user, problem_id):
    """
    点击行星（核心问题）获取详情面板数据
    返回：问题名称、具体症状、触发场景、严重程度、归属画像
    """
    # 查找问题
    problem = PersonaUserProblem.query.get(problem_id)
    if not problem:
        return jsonify({'success': False, 'message': '问题不存在'}), 404

    # 获取该问题关联的画像
    related_portraits = []
    portraits = SavedPortrait.query.filter_by(user_id=user.id).all()
    for p in portraits:
        pd = p.portrait_data or {}
        session_id = pd.get('session_id') or pd.get('source_session_id')
        if session_id and problem.session_id == session_id:
            related_portraits.append({
                'portrait_id': p.id,
                'name': p.portrait_name or '未命名画像',
                'industry': p.industry or '',
            })

    # 生成次数
    gen_count = PublicGeneration.query.filter_by(
        user_id=user.id, problem_id=problem_id
    ).count()

    return jsonify({
        'success': True,
        'data': {
            'problem_id': problem_id,
            'name': problem.name or '未命名问题',
            'description': problem.description or '',
            'specific_symptoms': problem.specific_symptoms or '',
            'severity': problem.severity or '中',
            'user_awareness': problem.user_awareness or '',
            'trigger_scenario': problem.trigger_scenario or '',
            'created_at': _dt_str(problem.created_at),
            'related_portraits': related_portraits,
            'generation_count': gen_count,
            # ── 星系增强：行星地域信息 ──
            'geo_trigger_regions': problem.geo_trigger_regions or [],
            'geo_seasonal_factor': problem.geo_seasonal_factor or '',
        }
    })


@galaxy_bp.route('/node/satellite/<int:generation_id>', methods=['GET'])
@login_required
def get_satellite_detail(user, generation_id):
    """
    点击卫星（选题/内容）获取历史记录面板数据
    返回：累计生成次数 + 历史选题列表 + 完整内容
    """
    # 查询该 generation 记录
    gen = PublicGeneration.query.filter_by(id=generation_id, user_id=user.id).first()
    if not gen:
        return jsonify({'success': False, 'message': '记录不存在或无权访问'}), 404

    # 提取标题
    titles = []
    if gen.titles:
        if isinstance(gen.titles, list):
            titles = [t for t in gen.titles if isinstance(t, str)]
        elif isinstance(gen.titles, str):
            try:
                titles = __import__('json').loads(gen.titles)
                titles = [t for t in titles if isinstance(t, str)]
            except:
                titles = [gen.titles]

    # 查询同 problem_id 或同 portrait_id 的历史记录
    history_query = PublicGeneration.query.filter(
        PublicGeneration.user_id == user.id
    )
    if gen.problem_id:
        history_query = history_query.filter(
            PublicGeneration.problem_id == gen.problem_id
        )
    elif gen.portrait_id:
        history_query = history_query.filter(
            PublicGeneration.portrait_id == gen.portrait_id
        )
    else:
        history_query = history_query.filter(
            PublicGeneration.industry == gen.industry
        )

    total_count = history_query.count()
    history_records = history_query.order_by(
        PublicGeneration.created_at.desc()
    ).limit(50).all()

    history_list = []
    for rec in history_records:
        rec_titles = []
        if rec.titles:
            if isinstance(rec.titles, list):
                rec_titles = [t for t in rec.titles if isinstance(t, str)]
            elif isinstance(rec.titles, str):
                try:
                    rec_titles = __import__('json').loads(rec.titles)
                except:
                    rec_titles = [rec.titles]
        main_title = rec_titles[0] if rec_titles else f"内容 #{rec.id}"

        history_list.append({
            'generation_id': rec.id,
            'title': main_title,
            'titles': rec_titles,
            'content': rec.content or '',
            'content_snippet': (rec.content or '')[:150].replace('\n', ' '),
            'created_at': _dt_str(rec.created_at),
        })

    return jsonify({
        'success': True,
        'data': {
            'generation_id': generation_id,
            'link_id': gen.link_id,
            'version_number': gen.version_number,
            'content_type': gen.content_type or 'graphic',
            'content_style': gen.content_style or '',
            'geo_mode': gen.geo_mode_used or '',
            'titles': titles,
            'content': (gen.content_data or {}).get('body', '') if gen.content_data else '',
            'industry': gen.industry or '',
            'target_customer': gen.target_customer or '',
            'created_at': _dt_str(gen.created_at),
            'used_tokens': gen.used_tokens or 0,
            'total_count': total_count,
            'history': history_list,
            'portrait_id': gen.portrait_id,
            'problem_id': gen.problem_id,
        }
    })


# =============================================================================
# 三、回填接口（用于内容生成时自动关联）
# =============================================================================

@galaxy_bp.route('/generation/link', methods=['POST'])
@login_required
def link_generation(user):
    """
    内容生成完成后，关联 generation 记录到画像和问题

    请求体：
    {
        "generation_id": 123,
        "portrait_id": 1,          # 可选
        "problem_id": 2,           # 可选
        "industry": "美妆",
        "target_customer": "20-30岁女性",
        "selected_scenes": {...}  # 星系增强：客户选择的场景组合
    }
    """
    data = request.get_json() or {}
    generation_id = data.get('generation_id')
    portrait_id = data.get('portrait_id')
    problem_id = data.get('problem_id')
    industry = data.get('industry', '')
    target_customer = data.get('target_customer', '')
    selected_scenes = data.get('selected_scenes')  # 星系增强

    if not generation_id:
        return jsonify({'success': False, 'message': '缺少 generation_id'}), 400

    gen = PublicGeneration.query.filter_by(id=generation_id, user_id=user.id).first()
    if not gen:
        return jsonify({'success': False, 'message': '记录不存在'}), 404

    # 更新关联字段
    if portrait_id is not None:
        gen.portrait_id = portrait_id
    if problem_id is not None:
        gen.problem_id = problem_id
    if industry:
        gen.industry = industry
    if target_customer:
        gen.target_customer = target_customer
    if selected_scenes is not None:
        gen.selected_scenes = selected_scenes  # 星系增强：保存场景选择

    db.session.commit()

    return jsonify({
        'success': True,
        'message': '关联成功',
        'data': {
            'generation_id': gen.id,
            'portrait_id': gen.portrait_id,
            'problem_id': gen.problem_id,
        }
    })


# =============================================================================
# 四、数据回填（管理员用 - 修复历史数据）
# =============================================================================

@galaxy_bp.route('/backfill', methods=['POST'])
@login_required
def backfill_relations(user):
    """
    批量回填历史 generation 记录的 portrait_id 和 problem_id

    策略：
    1. 遍历所有 generation 记录
    2. 按 industry + target_customer 匹配到最近的画像
    3. 如果画像有关联的 session_id，从 session 找到对应的问题
    """
    user_id = user.id

    # 获取用户的画像
    portraits = SavedPortrait.query.filter_by(user_id=user_id).order_by(
        SavedPortrait.created_at.desc()
    ).all()

    portrait_map = {}  # (industry, target_customer) -> portrait
    for p in portraits:
        key = (p.industry or '', p.target_customer or '')
        if key not in portrait_map:
            portrait_map[key] = p

    # 遍历 generation 记录
    updated = 0
    generations = PublicGeneration.query.filter_by(user_id=user_id).all()
    for gen in generations:
        changed = False

        # 自动关联 portrait_id
        if gen.portrait_id is None:
            key = (gen.industry or '', gen.target_customer or '')
            matched_portrait = portrait_map.get(key)
            if matched_portrait:
                gen.portrait_id = matched_portrait.id
                changed = True

        # 自动关联 problem_id（通过画像的 session_id）
        if gen.problem_id is None and gen.portrait_id:
            matched_p = SavedPortrait.query.get(gen.portrait_id)
            if matched_p and matched_p.portrait_data:
                pd = matched_p.portrait_data
                if isinstance(pd, dict):
                    session_id = pd.get('session_id') or pd.get('source_session_id')
                    if session_id:
                        # 找到该 session 最近的问题
                        prob = PersonaUserProblem.query.filter_by(
                            session_id=session_id
                        ).order_by(PersonaUserProblem.sort_order.asc()).first()
                        if prob:
                            gen.problem_id = prob.id
                            changed = True

        if changed:
            updated += 1

    if updated > 0:
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'回填完成，共更新 {updated} 条记录',
        'data': {'updated_count': updated}
    })


# =============================================================================
# 五、星系统计面板
# =============================================================================

@galaxy_bp.route('/stats', methods=['GET'])
@login_required
def get_galaxy_stats(user):
    """
    获取星系统计信息
    """
    user_id = user.id

    total_portraits = SavedPortrait.query.filter_by(user_id=user_id).count()
    total_generations = PublicGeneration.query.filter_by(user_id=user_id).count()

    # 按月统计生成量
    monthly_stats = db.session.execute(
        text("""
            SELECT
                strftime('%Y-%m', created_at) as month,
                COUNT(*) as count
            FROM public_generations
            WHERE user_id = :uid
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """),
        {'uid': user_id}
    ).fetchall()

    # 按行业统计
    industry_stats = db.session.execute(
        text("""
            SELECT industry, COUNT(*) as count
            FROM public_generations
            WHERE user_id = :uid AND industry IS NOT NULL AND industry != ''
            GROUP BY industry
            ORDER BY count DESC
            LIMIT 10
        """),
        {'uid': user_id}
    ).fetchall()

    return jsonify({
        'success': True,
        'data': {
            'total_portraits': total_portraits,
            'total_generations': total_generations,
            'monthly_stats': [{'month': r[0], 'count': r[1]} for r in monthly_stats],
            'industry_stats': [{'industry': r[0], 'count': r[1]} for r in industry_stats],
        }
    })


# =============================================================================
# 辅助函数
# =============================================================================

def _dt_str(value):
    """将 datetime 转为字符串"""
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d %H:%M')
    return str(value)
