"""
公开用户管理后台 - 路由

功能：
1. 公开用户列表（分页、搜索）
2. 用户详情查看
3. 用户权限管理（升级/降级）
4. 配额管理（token余额、有效期）
5. 批量操作
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from datetime import datetime, timedelta
from functools import wraps

from models.models import db
from models.public_models import PublicUser, PublicGeneration, PublicLLMCallLog, PublicPricingPlan

admin_public = Blueprint('admin_public', __name__, url_prefix='/admin/public-users')


def super_admin_required(f):
    """超级管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'super_admin':
            wants_json = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                or request.is_json
            )
            if wants_json:
                return jsonify({'code': 403, 'message': '需要超级管理员权限', 'success': False}), 403
            flash('需要超级管理员权限', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@admin_public.route('/')
@login_required
@super_admin_required
def list():
    """公开用户列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()
    plan_filter = request.args.get('plan', '')
    status_filter = request.args.get('status', '')

    query = PublicUser.query

    # 搜索条件
    if search:
        query = query.filter(
            or_(
                PublicUser.email.ilike(f'%{search}%'),
                PublicUser.nickname.ilike(f'%{search}%')
            )
        )

    # 套餐筛选
    if plan_filter:
        if plan_filter == 'free':
            query = query.filter(PublicUser.is_premium == False)
        elif plan_filter == 'paid':
            query = query.filter(
                and_(
                    PublicUser.is_premium == True,
                    or_(
                        PublicUser.premium_expires == None,
                        PublicUser.premium_expires > datetime.utcnow()
                    )
                )
            )
        elif plan_filter == 'expired':
            query = query.filter(
                and_(
                    PublicUser.is_premium == True,
                    PublicUser.premium_expires != None,
                    PublicUser.premium_expires < datetime.utcnow()
                )
            )
        else:
            query = query.filter(PublicUser.premium_plan == plan_filter)

    # 状态筛选
    if status_filter == 'active':
        query = query.filter(PublicUser.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(PublicUser.is_active == False)
    elif status_filter == 'unverified':
        query = query.filter(PublicUser.is_verified == False)

    # 按创建时间倒序
    query = query.order_by(PublicUser.created_at.desc())

    # 分页
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    users = pagination.items

    # 统计数据
    stats = {
        'total': PublicUser.query.count(),
        'total_verified': PublicUser.query.filter_by(is_verified=True).count(),
        'total_premium': PublicUser.query.filter_by(is_premium=True).count(),
        'total_free': PublicUser.query.filter_by(is_premium=False).count(),
        'total_generations': PublicGeneration.query.count(),
    }

    # 获取可用套餐列表
    plans = PublicPricingPlan.query.filter_by(is_visible=True).order_by(PublicPricingPlan.sort_order).all()

    return render_template('admin/public_users.html',
                         users=users,
                         pagination=pagination,
                         stats=stats,
                         plans=plans,
                         search=search,
                         plan_filter=plan_filter,
                         status_filter=status_filter,
                         now=datetime.utcnow())


@admin_public.route('/<int:user_id>')
@login_required
@super_admin_required
def detail(user_id):
    """用户详情"""
    user = PublicUser.query.get_or_404(user_id)

    # 获取生成记录统计
    generation_stats = {
        'total': PublicGeneration.query.filter_by(user_id=user_id).count(),
        'today': PublicGeneration.query.filter_by(user_id=user_id).filter(
            PublicGeneration.created_at >= datetime.utcnow().date()
        ).count(),
        'this_month': PublicGeneration.query.filter_by(user_id=user_id).filter(
            PublicGeneration.created_at >= datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        ).count(),
    }

    # 获取 LLM 调用统计
    llm_stats = db.session.query(
        db.func.sum(PublicLLMCallLog.input_tokens).label('input_tokens'),
        db.func.sum(PublicLLMCallLog.output_tokens).label('output_tokens'),
        db.func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
        db.func.sum(PublicLLMCallLog.cost).label('total_cost'),
    ).filter_by(user_id=user_id).first()

    # 最近生成记录
    recent_generations = PublicGeneration.query.filter_by(user_id=user_id)\
        .order_by(PublicGeneration.created_at.desc()).limit(10).all()

    # 最近 LLM 调用
    recent_llm_calls = PublicLLMCallLog.query.filter_by(user_id=user_id)\
        .order_by(PublicLLMCallLog.created_at.desc()).limit(20).all()

    return render_template('admin/public_user_detail.html',
                         user=user,
                         generation_stats=generation_stats,
                         llm_stats=llm_stats,
                         recent_generations=recent_generations,
                         recent_llm_calls=recent_llm_calls,
                         now=datetime.utcnow())


@admin_public.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit(user_id):
    """编辑用户"""
    user = PublicUser.query.get_or_404(user_id)

    if request.method == 'POST':
        # 更新基本资料
        nickname = request.form.get('nickname', '').strip()
        if nickname:
            user.nickname = nickname

        # 更新验证状态
        is_verified = request.form.get('is_verified')
        user.is_verified = (is_verified == '1')

        # 更新活跃状态
        is_active = request.form.get('is_active')
        user.is_active = (is_active == '1')

        # 更新套餐
        plan = request.form.get('plan', 'free')
        if plan == 'free':
            user.is_premium = False
            user.premium_plan = 'free'
            user.premium_expires = None
        elif plan == 'enterprise':
            user.is_premium = True
            user.premium_plan = 'enterprise'
            expires_days = request.form.get('expires_days', type=int, default=0)
            if expires_days > 0:
                user.premium_expires = datetime.utcnow() + timedelta(days=expires_days)
            else:
                user.premium_expires = None  # 永不过期
        else:
            user.is_premium = True
            user.premium_plan = plan
            expires_days = request.form.get('expires_days', type=int, default=30)
            user.premium_expires = datetime.utcnow() + timedelta(days=expires_days)

        # 更新 token 余额
        token_balance = request.form.get('token_balance', type=int, default=0)
        user.token_balance = token_balance

        # 添加 token（增量）
        add_tokens = request.form.get('add_tokens', type=int, default=0)
        if add_tokens > 0:
            user.token_balance = (user.token_balance or 0) + add_tokens

        db.session.commit()
        flash(f'用户 {user.email} 已更新', 'success')
        return redirect(url_for('admin_public.detail', user_id=user_id))

    plans = PublicPricingPlan.query.filter_by(is_visible=True).order_by(PublicPricingPlan.sort_order).all()
    return render_template('admin/public_user_edit.html', user=user, plans=plans)


@admin_public.route('/<int:user_id>/upgrade', methods=['POST'])
@login_required
@super_admin_required
def upgrade(user_id):
    """快速升级用户"""
    user = PublicUser.query.get_or_404(user_id)

    data = request.get_json() or {}
    plan = data.get('plan', 'professional')
    days = data.get('days', 30)

    user.is_premium = True
    user.premium_plan = plan

    if days > 0:
        if user.premium_expires and user.premium_expires > datetime.utcnow():
            user.premium_expires = user.premium_expires + timedelta(days=days)
        else:
            user.premium_expires = datetime.utcnow() + timedelta(days=days)

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'用户已升级为 {plan}，有效期至 {user.premium_expires.strftime("%Y-%m-%d") if user.premium_expires else "永不过期"}'
    })


@admin_public.route('/<int:user_id>/downgrade', methods=['POST'])
@login_required
@super_admin_required
def downgrade(user_id):
    """降级用户为免费版"""
    user = PublicUser.query.get_or_404(user_id)

    user.is_premium = False
    user.premium_plan = 'free'
    user.premium_expires = None

    db.session.commit()

    return jsonify({
        'success': True,
        'message': '用户已降级为免费版'
    })


@admin_public.route('/<int:user_id>/add-tokens', methods=['POST'])
@login_required
@super_admin_required
def add_tokens(user_id):
    """为用户添加 token"""
    user = PublicUser.query.get_or_404(user_id)

    data = request.get_json() or {}
    tokens = data.get('tokens', 0)

    if tokens <= 0:
        return jsonify({'success': False, 'message': 'Token 数量必须大于 0'}), 400

    user.token_balance = (user.token_balance or 0) + tokens
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'已添加 {tokens} tokens，当前余额: {user.token_balance}'
    })


@admin_public.route('/<int:user_id>/reset-password', methods=['POST'])
@login_required
@super_admin_required
def reset_password(user_id):
    """重置用户密码"""
    from werkzeug.security import generate_password_hash

    user = PublicUser.query.get_or_404(user_id)

    data = request.get_json() or {}
    new_password = data.get('password', '').strip()

    if len(new_password) < 6:
        return jsonify({'success': False, 'message': '密码至少6位'}), 400

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '密码已重置'
    })


@admin_public.route('/<int:user_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete(user_id):
    """删除用户"""
    user = PublicUser.query.get_or_404(user_id)

    # 软删除：只禁用账号
    user.is_active = False
    user.email = f'deleted_{user.id}_{user.email}'  # 避免邮箱重复
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '用户已删除'
    })


@admin_public.route('/batch-upgrade', methods=['POST'])
@login_required
@super_admin_required
def batch_upgrade():
    """批量升级用户"""
    data = request.get_json() or {}
    user_ids = data.get('user_ids', [])
    plan = data.get('plan', 'professional')
    days = data.get('days', 30)

    if not user_ids:
        return jsonify({'success': False, 'message': '请选择用户'}), 400

    count = 0
    for user_id in user_ids:
        user = PublicUser.query.get(user_id)
        if user:
            user.is_premium = True
            user.premium_plan = plan
            if days > 0:
                if user.premium_expires and user.premium_expires > datetime.utcnow():
                    user.premium_expires = user.premium_expires + timedelta(days=days)
                else:
                    user.premium_expires = datetime.utcnow() + timedelta(days=days)
            else:
                user.premium_expires = None
            count += 1

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'已升级 {count} 个用户'
    })


@admin_public.route('/stats')
@login_required
@super_admin_required
def stats():
    """统计数据"""
    # 用户统计
    total_users = PublicUser.query.count()
    verified_users = PublicUser.query.filter_by(is_verified=True).count()
    premium_users = PublicUser.query.filter_by(is_premium=True).count()
    free_users = PublicUser.query.filter_by(is_premium=False).count()

    # 过期用户
    expired_users = PublicUser.query.filter(
        and_(
            PublicUser.is_premium == True,
            PublicUser.premium_expires != None,
            PublicUser.premium_expires < datetime.utcnow()
        )
    ).count()

    # 生成统计
    total_generations = PublicGeneration.query.count()
    today_generations = PublicGeneration.query.filter(
        PublicGeneration.created_at >= datetime.utcnow().date()
    ).count()

    # 成本统计
    cost_stats = db.session.query(
        db.func.sum(PublicLLMCallLog.cost).label('total_cost'),
        db.func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
    ).first()

    return jsonify({
        'success': True,
        'data': {
            'users': {
                'total': total_users,
                'verified': verified_users,
                'premium': premium_users,
                'free': free_users,
                'expired': expired_users
            },
            'generations': {
                'total': total_generations,
                'today': today_generations
            },
            'cost': {
                'total': float(cost_stats.total_cost or 0),
                'total_tokens': cost_stats.total_tokens or 0
            }
        }
    })
