"""
迁移：为 saved_portraits 表添加 seasonal_config 字段（淡旺季配置）

功能：支持用户配置内容淡旺季周期，日历视图据此标注旺/淡月
运行方式：cd /Volumes/增元/项目/douyin/系统部署 && python3 -c "from migrations.add_seasonal_config import run_migration; run_migration()"
"""

import logging
from sqlalchemy import text
from models.models import db

logger = logging.getLogger(__name__)


def upgrade():
    """添加 seasonal_config 字段"""
    try:
        result = db.session.execute(text("PRAGMA table_info(saved_portraits)"))
        columns = [row[1] for row in result.fetchall()]

        if 'seasonal_config' not in columns:
            db.session.execute(text(
                "ALTER TABLE saved_portraits ADD COLUMN seasonal_config JSON"
            ))
            db.session.commit()
            logger.info("[迁移] seasonal_config 字段添加成功")
        else:
            logger.info("[迁移] seasonal_config 字段已存在，跳过")

    except Exception as e:
        logger.error(f"[迁移] 添加 seasonal_config 字段失败: {e}")
        db.session.rollback()
        raise


def downgrade():
    """回滚：移除 seasonal_config 字段"""
    try:
        db.session.execute(text("UPDATE saved_portraits SET seasonal_config = NULL"))
        db.session.commit()
        logger.info("[迁移回滚] seasonal_config 字段已置空")
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


def run_migration():
    upgrade()
