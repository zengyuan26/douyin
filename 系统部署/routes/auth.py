"""
认证路由 - 登录、注册、登出
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models.models import db, User
from flask_bcrypt import Bcrypt
from datetime import datetime

auth = Blueprint('auth', __name__)
bcrypt = Bcrypt()


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            # 如果用户是渠道用户且渠道已激活，则自动激活用户账号
            if user.role == 'channel' and not user.is_active:
                from models.models import Channel
                channel = Channel.query.filter_by(user_id=user.id).first()
                if channel and channel.is_active:
                    user.is_active = True
                    db.session.commit()
            
            if user.is_active:
                login_user(user)
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                next_page = request.args.get('next')
                if not next_page:
                    next_page = url_for('main.index')
                return redirect(next_page)
            else:
                if user.role == 'channel':
                    flash('您的账号正在审核中，请联系管理员', 'warning')
                else:
                    flash('账号已被禁用', 'danger')
        else:
            flash('用户名或密码错误', 'danger')
    
    return render_template('login.html')


@auth.route('/logout')
@login_required
def logout():
    """登出"""
    logout_user()
    flash('已成功登出', 'success')
    return redirect(url_for('auth.login'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    """注册页面"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # 检查用户名和邮箱是否已存在
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('邮箱已被注册', 'danger')
            return render_template('register.html')
        
        # 创建新用户
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            role='user'  # 普通用户
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功，请登录', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')


@auth.route('/channel-register', methods=['GET', 'POST'])
def channel_register():
    """渠道商注册页面"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        nickname = request.form.get('nickname')
        id_card = request.form.get('id_card')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # 检查密码是否一致
        if password != confirm_password:
            flash('两次输入的密码不一致', 'danger')
            return render_template('channel_register.html')
        
        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            flash('账号已存在', 'danger')
            return render_template('channel_register.html')
        
        # 检查身份证是否已被使用
        if id_card and User.query.filter_by(id_card=id_card).first():
            flash('该身份证号已被注册', 'danger')
            return render_template('channel_register.html')
        
        # 创建渠道用户 (需要超级管理员审核通过后才能使用)
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            username=username,
            email=f'{username}@pending.com',  # 临时邮箱
            password_hash=hashed_password,
            id_card=id_card,  # 保存身份证号
            nickname=nickname,  # 保存昵称
            role='channel',
            is_active=False  # 默认禁用，需要审核
        )
        
        db.session.add(user)
        db.session.flush()
        
        # 创建渠道记录
        from models.models import Channel
        channel = Channel(
            user_id=user.id,
            name=nickname,  # 使用昵称作为渠道名称
            company='',
            contact='',
            description='待审核',
            is_active=False  # 默认待审核
        )
        db.session.add(channel)
        db.session.commit()
        
        flash('申请提交成功！请等待管理员审核后登录', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('channel_register.html')


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
