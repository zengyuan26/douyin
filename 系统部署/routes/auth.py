"""
认证路由 - 登录、注册、登出
"""
import hashlib
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from models.models import db, User
from models.public_models import PublicUser
from flask_bcrypt import Bcrypt
from datetime import datetime

auth = Blueprint('auth', __name__)
bcrypt = Bcrypt()


def _verify_password_sha256(password: str, password_hash: str) -> bool:
    """验证 SHA256 哈希的密码（PublicUser 使用）"""
    return hashlib.sha256(password.encode()).hexdigest() == password_hash


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    import logging
    logger = logging.getLogger('app')
    logger.debug(f"=== LOGIN DEBUG ===")
    logger.debug(f"Method: {request.method}")
    logger.debug(f"current_user.is_authenticated: {current_user.is_authenticated}")
    if current_user.is_authenticated:
        logger.debug(f"current_user.role: {current_user.role}")
        logger.debug(f"Redirecting to: main.index")
        # 已登录用户根据角色跳转
        if current_user.role in ('super_admin', 'admin'):
            return redirect(url_for('main.index'))
        else:
            return redirect(url_for('public.index'))
    
    # URL参数决定默认登录类型
    url_login_type = request.args.get('type', 'public')
    
    if request.method == 'POST':
        login_type = request.form.get('login_type', 'public')  # admin 或 public
        logger.debug(f"POST login_type: {login_type}")
        
        if login_type == 'public':
            # 公开平台用户：使用邮箱登录，查询 PublicUser 表
            # 兼容两种表单：public/login.html 用 email，login.html 用 username
            email = request.form.get('email') or request.form.get('username')
            password = request.form.get('password', '')
            user = PublicUser.query.filter_by(email=email).first() if email else None
            
            # PublicUser 使用 SHA256 验证密码
            if user and _verify_password_sha256(password, user.password_hash):
                if user.is_active:
                    # 公开用户使用 session 记录，不使用 Flask-Login 的 login_user
                    session['public_user_id'] = user.id
                    session.permanent = True
                    flash('登录成功！', 'success')
                    return redirect(url_for('public.index'))
                else:
                    flash('账号已被禁用', 'danger')
            else:
                flash('用户名或密码错误', 'danger')
        else:
            # 管理员账号：使用用户名登录，查询 User 表
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()
            
            if user and bcrypt.check_password_hash(user.password_hash, password):
                if user.is_active:
                    login_user(user)
                    user.last_login = datetime.utcnow()
                    db.session.commit()

                    # type=admin 登录直接跳转到管理中心
                    return redirect(url_for('admin.dashboard'))
                else:
                    flash('账号已被禁用', 'danger')
            else:
                flash('用户名或密码错误', 'danger')
        
        # 登录失败后保留当前登录模式
        if login_type not in ('public', 'admin'):
            login_type = 'public'
    else:
        login_type = url_login_type

    # 统一使用 login.html 作为登录入口模板（支持公开用户和管理员两种模式）
    return render_template('login.html', url_login_type=url_login_type)


@auth.route('/logout')
@login_required
def logout():
    """登出"""
    # 如果是公开用户，清除 session 中的 public_user_id
    session.pop('public_user_id', None)
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/public-register', methods=['GET', 'POST'])
def public_register():
    """公开用户注册"""
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        nickname = request.form.get('nickname')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # 检查密码是否一致
        if password != confirm_password:
            flash('两次输入的密码不一致', 'danger')
            return redirect(url_for('auth.login'))
        
        # 检查邮箱是否已存在于 PublicUser 表
        if PublicUser.query.filter_by(email=email).first():
            flash('该邮箱已被注册', 'danger')
            return redirect(url_for('auth.login'))
        
        # 检查昵称是否已被使用（PublicUser 表）
        if nickname and PublicUser.query.filter_by(nickname=nickname).first():
            flash('该昵称已被使用', 'danger')
            return redirect(url_for('auth.login'))
        
        # 创建公开用户到 PublicUser 表（使用 SHA256 哈希密码）
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        user = PublicUser(
            email=email,
            nickname=nickname or email.split('@')[0],
            password_hash=password_hash,
            is_active=True  # 公开用户默认激活
        )
        
        db.session.add(user)
        db.session.commit()
        
        # 使用 session 记录公开用户登录
        session['public_user_id'] = user.id
        session.permanent = True
        flash('注册成功！', 'success')
        return redirect(url_for('public.index'))
    
    return redirect(url_for('auth.login'))


@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """忘记密码 - 填写账号和身份证"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        id_card = request.form.get('id_card')
        
        user = User.query.filter_by(username=username).first()
        
        if not user:
            flash('账号不存在', 'danger')
            return render_template('forgot_password.html')
        
        # 检查是否设置了身份证号
        if not user.id_card:
            flash('该账号未设置身份证号，请联系管理员重置密码', 'warning')
            return render_template('forgot_password.html')
        
        if user.id_card != id_card:
            flash('身份证号不匹配', 'danger')
            return render_template('forgot_password.html')
        
        # 验证通过，跳转到重置密码页面
        return redirect(url_for('auth.reset_password', user_id=user.id))
    
    return render_template('forgot_password.html')


@auth.route('/reset-password/<int:user_id>', methods=['GET', 'POST'])
def reset_password(user_id):
    """重置密码"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('两次输入的密码不一致', 'danger')
            return render_template('reset_password.html', user_id=user_id)
        
        # 更新密码
        user.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        db.session.commit()
        
        flash('密码重置成功！请使用新密码登录', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('reset_password.html', user_id=user_id)
