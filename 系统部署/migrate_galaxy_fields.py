"""
数据库迁移脚本：添加星系关联字段到 public_generations 表

运行方式：python migrate_galaxy_fields.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.models import db
from sqlalchemy import text


def migrate():
    with app.app_context():
        conn = db.engine.connect()

        # 检查 portrait_id 列是否存在
        result = conn.execute(text("PRAGMA table_info(public_generations)"))
        columns = [row[1] for row in result.fetchall()]

        print(f"[迁移] 当前 public_generations 表字段: {columns}")

        # 添加 portrait_id 列
        if 'portrait_id' not in columns:
            conn.execute(text(
                "ALTER TABLE public_generations ADD COLUMN portrait_id INTEGER"
            ))
            conn.commit()
            print("[迁移] ✓ 已添加 portrait_id 列")
        else:
            print("[迁移] portrait_id 列已存在，跳过")

        # 再次检查（确保 portrait_id 已被添加）
        result = conn.execute(text("PRAGMA table_info(public_generations)"))
        columns = [row[1] for row in result.fetchall()]

        # 添加 problem_id 列
        if 'problem_id' not in columns:
            conn.execute(text(
                "ALTER TABLE public_generations ADD COLUMN problem_id INTEGER"
            ))
            conn.commit()
            print("[迁移] ✓ 已添加 problem_id 列")
        else:
            print("[迁移] problem_id 列已存在，跳过")

        # 验证最终字段
        result = conn.execute(text("PRAGMA table_info(public_generations)"))
        final_columns = [row[1] for row in result.fetchall()]
        print(f"[迁移] 最终字段: {final_columns}")

        # 添加索引
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_generation_portrait "
                "ON public_generations(user_id, portrait_id)"
            ))
            conn.commit()
            print("[迁移] ✓ 索引 idx_generation_portrait 已创建")
        except Exception as e:
            print(f"[迁移] 索引创建跳过: {e}")

        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_generation_problem "
                "ON public_generations(user_id, problem_id)"
            ))
            conn.commit()
            print("[迁移] ✓ 索引 idx_generation_problem 已创建")
        except Exception as e:
            print(f"[迁移] 索引创建跳过: {e}")

        conn.close()
        print("[迁移] ✓ 迁移完成！")


if __name__ == '__main__':
    migrate()
