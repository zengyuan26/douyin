"""
主路由 - 首页跳转（工作台已移除）
"""
from flask import Blueprint, redirect, url_for
from flask_login import current_user

main = Blueprint('main', __name__)


@main.route('/')
def index():
    """首页 - 根据角色跳转"""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    # 根据角色跳转
    if current_user.role in ('super_admin', 'admin'):
        return redirect(url_for('admin.dashboard'))

    # 其他用户跳转到公开平台
    return redirect(url_for('public.index'))
