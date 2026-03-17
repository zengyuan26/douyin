"""
数据库迁移脚本：为 knowledge_accounts 表添加 auto_analysis_config 字段

用途：为已有账号添加默认的自动分析配置，新字段默认为 JSON 格式
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import db
from app import create_app


def migrate():
    """执行迁移"""
    app = create_app()
    
    with app.app_context():
        # 检查字段是否存在
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('knowledge_accounts')]
        
        if 'auto_analysis_config' in columns:
            print("字段 auto_analysis_config 已存在，无需迁移")
            return
        
        # 添加字段
        print("正在添加 auto_analysis_config 字段...")
        db.session.execute(db.text("""
            ALTER TABLE knowledge_accounts 
            ADD COLUMN auto_analysis_config JSON DEFAULT '{"on_create": {"nickname": true, "bio": true, "account_positioning": true, "keyword_library": false, "market_analysis": false, "operation_planning": false}, "on_update": {"nickname": true, "bio": true, "account_positioning": true, "keyword_library": false, "market_analysis": false, "operation_planning": false}}'
        """))
        db.session.commit()
        print("迁移完成！")


if __name__ == '__main__':
    migrate()
