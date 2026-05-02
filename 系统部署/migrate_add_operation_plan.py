"""
迁移脚本：为 saved_portraits 表添加运营规划字段

执行方式：python migrate_add_operation_plan.py
"""

from models.models import db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """添加运营规划相关字段"""
    conn = db.session.connection()
    
    # 检查字段是否已存在
    result = conn.execute(text("PRAGMA table_info(saved_portraits)"))
    columns = [row[1] for row in result.fetchall()]
    
    if 'operation_plan' in columns:
        logger.info("字段 operation_plan 已存在，跳过")
        return True
    
    try:
        # 添加 operation_plan 字段
        conn.execute(text("ALTER TABLE saved_portraits ADD COLUMN operation_plan JSON"))
        logger.info("已添加 operation_plan 字段")
        
        # 添加 operation_plan_updated_at 字段
        conn.execute(text("ALTER TABLE saved_portraits ADD COLUMN operation_plan_updated_at DATETIME"))
        logger.info("已添加 operation_plan_updated_at 字段")
        
        db.session.commit()
        logger.info("迁移完成")
        return True
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"迁移失败: {e}")
        return False


if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        migrate()
