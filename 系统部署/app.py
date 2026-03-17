"""
抖音营销专家系统 - 主应用
"""
import logging
import os
from flask import Flask
from flask_login import LoginManager
from config import config
from models.models import db, User, Expert, Skill, KnowledgeCategory, KnowledgeArticle, KnowledgeAnalysis, KnowledgeRule, KnowledgeAccount, KnowledgeAccountHistory

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
    
    # 注册备份 API
    from routes.backup_api import backup_api as backup_api_blueprint
    app.register_blueprint(backup_api_blueprint, url_prefix='/api')
    
    # 注册专家对话 API（基于 Skills 按需加载）
    from routes.expert_api import expert_api as expert_api_blueprint
    app.register_blueprint(expert_api_blueprint, url_prefix='/api/expert')
    
    # 注册知识库分析 API
    from routes.knowledge_api import knowledge_api as knowledge_api_blueprint
    app.register_blueprint(knowledge_api_blueprint)

    # 注册公式要素 API
    from routes.knowledge_api import register_formula_elements_routes
    register_formula_elements_routes(knowledge_api_blueprint)
    
    # 创建上传目录
    import os
    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # 初始化定时备份服务
    if os.environ.get('FLASK_RUN') or os.environ.get('WERKZEUG_RUN_MAIN'):
        try:
            from services.scheduler_service import scheduler_service
            scheduler_service.start()
            # 默认添加每日凌晨2点备份
            scheduler_service.add_daily_backup(hour=2, minute=0)
            logging.info("定时备份服务已启动")
        except Exception as e:
            logging.warning(f"定时备份服务启动失败: {e}")
    
    return app


# 创建应用实例
app = create_app('development')

# 自动创建缺失的数据库表
with app.app_context():
    db.create_all()
    print("✓ 数据库表检查完成")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
