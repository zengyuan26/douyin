"""
添加质量评分字段迁移脚本

为 public_generations 表添加 quality_score 字段

运行方式：
    python migrations/add_quality_score_to_generations.py
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.models import db
from sqlalchemy import text


def upgrade():
    """添加 quality_score 字段"""
    try:
        # SQLite/MariaDB/MySQL 语法
        db.session.execute(text("""
            ALTER TABLE public_generations
            ADD COLUMN quality_score INTEGER NULL
        """))
        db.session.commit()
        print("✅ 迁移成功：已添加 quality_score 字段")
    except Exception as e:
        db.session.rollback()
        # 如果字段已存在，忽略错误
        if 'Duplicate column' in str(e) or 'already exists' in str(e):
            print("ℹ️ 字段已存在，跳过迁移")
        else:
            print(f"❌ 迁移失败：{e}")
            raise


def downgrade():
    """删除 quality_score 字段"""
    try:
        db.session.execute(text("""
            ALTER TABLE public_generations
            DROP COLUMN quality_score
        """))
        db.session.commit()
        print("✅ 回滚成功：已删除 quality_score 字段")
    except Exception as e:
        db.session.rollback()
        print(f"❌ 回滚失败：{e}")
        raise


if __name__ == '__main__':
    # 导入Flask应用上下文
    from app import app

    with app.app_context():
        upgrade()
