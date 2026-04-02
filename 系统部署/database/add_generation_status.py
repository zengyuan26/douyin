"""
添加词库生成状态字段

执行命令：cd 系统部署 && python add_indexes.py  # 或单独执行 python add_generation_status.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db


def run():
    with app.app_context():
        conn = db.engine.connect()

        # 检查 generation_status 列是否存在
        result = conn.execute(db.text("PRAGMA table_info(saved_portraits)")).fetchall()
        column_names = [r[1] for r in result]
        print(f"[迁移] 当前 saved_portraits 列: {column_names}")

        # 添加 generation_status 列
        if 'generation_status' not in column_names:
            try:
                conn.execute(db.text(
                    "ALTER TABLE saved_portraits ADD COLUMN generation_status VARCHAR(20) DEFAULT 'pending'"
                ))
                conn.commit()
                print("[迁移] ✓ generation_status 列已添加")
            except Exception as e:
                print(f"[迁移] ✗ generation_status 添加失败: {e}")

        # 添加 generation_error 列
        if 'generation_error' not in column_names:
            try:
                conn.execute(db.text(
                    "ALTER TABLE saved_portraits ADD COLUMN generation_error TEXT"
                ))
                conn.commit()
                print("[迁移] ✓ generation_error 列已添加")
            except Exception as e:
                print(f"[迁移] ✗ generation_error 添加失败: {e}")

        print("\n[迁移] 字段迁移完成")


if __name__ == '__main__':
    run()
