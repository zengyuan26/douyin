# -*- coding: utf-8 -*-
"""
迁移：为 public_generations 表添加 topic_id 字段

运行方式：
python migrations/add_generation_topic_id.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db


def run_migration():
    """执行数据库迁移"""
    print("[Migration] 开始添加 topic_id 字段...")

    with app.app_context():
        conn = db.engine.connect()
        try:
            # 检查 public_generations 表是否存在
            result = conn.execute(db.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='public_generations'"
            ))
            if not result.fetchone():
                print("[Migration] public_generations 表不存在，跳过迁移")
                return False

            # 检查 topic_id 字段是否存在
            result = conn.execute(db.text("PRAGMA table_info(public_generations)"))
            columns = [row[1] for row in result.fetchall()]

            if 'topic_id' not in columns:
                conn.execute(db.text(
                    "ALTER TABLE public_generations ADD COLUMN topic_id VARCHAR(36)"
                ))
                conn.commit()
                print("[Migration] public_generations.topic_id 字段已添加")
            else:
                print("[Migration] public_generations.topic_id 字段已存在，跳过")

            print("[Migration] 迁移完成!")
            return True

        except Exception as e:
            print(f"[Migration] 迁移失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()


if __name__ == '__main__':
    run_migration()
