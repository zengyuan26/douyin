"""
迁移：为 saved_portraits 表添加 content_stage 字段

功能：支持管理员配置内容阶段（起号阶段/成长阶段/成熟阶段）
仅内部管理员可见，普通客户前端不展示

版本：1.0
日期：2026-04-02
"""

import logging
from sqlalchemy import text
from models.models import db

logger = logging.getLogger(__name__)


def upgrade():
    """添加 content_stage 字段"""
    try:
        # 检查字段是否已存在
        result = db.session.execute(text("PRAGMA table_info(saved_portraits)"))
        columns = [row[1] for row in result.fetchall()]

        if 'content_stage' not in columns:
            db.session.execute(text(
                "ALTER TABLE saved_portraits ADD COLUMN content_stage VARCHAR(20) DEFAULT '成长阶段'"
            ))
            db.session.commit()
            logger.info("[迁移] content_stage 字段添加成功")
        else:
            logger.info("[迁移] content_stage 字段已存在，跳过")

    except Exception as e:
        logger.error(f"[迁移] 添加 content_stage 字段失败: {e}")
        db.session.rollback()
        raise


def downgrade():
    """回滚：移除 content_stage 字段（SQLite 不支持 DROP COLUMN，简化为置空）"""
    try:
        db.session.execute(text(
            "UPDATE saved_portraits SET content_stage = NULL"
        ))
        db.session.commit()
        logger.info("[迁移回滚] content_stage 字段已置空")
    except Exception as e:
        logger.error(f"[迁移回滚] 失败: {e}")
        db.session.rollback()
        raise


if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        upgrade()
        print("迁移完成")
