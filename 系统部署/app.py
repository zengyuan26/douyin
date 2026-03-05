"""
抖音营销专家系统 - 主应用
"""
import logging
from flask import Flask
from flask_login import LoginManager
from config import config
from models.models import db, User

# 配置日志
logging.basicConfig(level=logging.DEBUG)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = '请先登录系统'
login_manager.login_message_category = 'warning'


def create_app(config_name='default'):
    """应用工厂"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    
    # 注册蓝图
    from routes.main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    from routes.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    
    from routes.admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')
    
    from routes.api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')
    
    # 注册专家对话 API（基于 Skills 按需加载）
    from routes.expert_api import expert_api as expert_api_blueprint
    app.register_blueprint(expert_api_blueprint, url_prefix='/api/expert')
    
    # 创建上传目录
    import os
    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    return app


# 创建应用实例
app = create_app('development')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
