"""
抖音营销专家系统 - 主应用
"""
import logging
import os

# 加载 .env 环境变量
from dotenv import load_dotenv
load_dotenv()

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
    app.register_blueprint(auth_blueprint)
    
    from routes.admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')
    
    # 注册备份 API
    from routes.backup_api import backup_api as backup_api_blueprint
    app.register_blueprint(backup_api_blueprint, url_prefix='/api')
    
    # 注册知识库分析 API
    from routes.knowledge_api import knowledge_api as knowledge_api_blueprint
    app.register_blueprint(knowledge_api_blueprint)

    # 注册公式要素 blueprint（独立模块，避免 blueprint 重复注册问题）
    from routes.formula_elements_routes import formula_elements_bp
    app.register_blueprint(formula_elements_bp)

    # 注册内容分析 API（独立模块）
    from routes.content_analysis_api import content_analysis_api as content_analysis_api_blueprint
    app.register_blueprint(content_analysis_api_blueprint)

    # 注册公开内容生成平台
    from routes.public_api import public_bp as public_api_blueprint
    app.register_blueprint(public_api_blueprint)

    # 注册公开用户管理后台
    try:
        from routes.admin_public_users import admin_public as admin_public_users_bp
        app.register_blueprint(admin_public_users_bp)
        logging.info("公开用户管理后台已注册")
    except Exception as e:
        logging.warning(f"公开用户管理后台注册失败: {e}")

    # 注册公开平台管理 API（待处理行业 + 成本统计）
    try:
        from routes.admin_pending_industries import admin_pending_industries_bp
        app.register_blueprint(admin_pending_industries_bp)
        logging.info("待处理行业管理 API 已注册")
    except Exception as e:
        logging.warning(f"待处理行业管理 API 注册失败: {e}")

    try:
        from routes.admin_cost_stats import admin_cost_stats_bp
        app.register_blueprint(admin_cost_stats_bp)
        logging.info("成本统计 API 已注册")
    except Exception as e:
        logging.warning(f"成本统计 API 注册失败: {e}")

    # 注册人群画像生成 API
    try:
        from routes.persona_api import persona_api as persona_api_blueprint
        app.register_blueprint(persona_api_blueprint)
        logging.info("人群画像生成 API 已注册")
    except Exception as e:
        logging.warning(f"人群画像 API 注册失败: {e}")

    # 初始化公开平台缓存预热
    try:
        from services.public_cache import public_cache
        public_cache.warm_up(app)
        logging.info("公开平台缓存预热完成")
    except Exception as e:
        logging.warning(f"公开平台缓存预热失败: {e}")
    
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
