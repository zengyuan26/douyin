"""
迁移脚本：为 public_target_customers 表添加批次相关字段

使用方法：
cd /Volumes/增元/项目/douyin/系统部署
python migrations/add_batch_columns.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db


def add_batch_columns():
    """为 public_target_customers 表添加批次相关字段"""
    with app.app_context():
        # 检查表是否存在
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('public_target_customers')]
        print(f"当前表字段: {columns}")

        # 要添加的字段
        new_columns = [
            ('batch_id', 'VARCHAR(50)'),
            ('batch_goal', 'VARCHAR(100)'),
            ('batch_display_order', 'INTEGER DEFAULT 0'),
            ('pain_point', 'TEXT'),
            ('pain_point_detail', 'TEXT'),
            ('action_motivation', 'TEXT'),
        ]

        # 使用 SQLite ALTER TABLE 添加字段
        for col_name, col_type in new_columns:
            if col_name not in columns:
                try:
                    sql = f"ALTER TABLE public_target_customers ADD COLUMN {col_name} {col_type}"
                    db.session.execute(db.text(sql))
                    print(f"[OK] 添加字段: {col_name}")
                except Exception as e:
                    print(f"[ERROR] 添加字段 {col_name} 失败: {e}")
            else:
                print(f"[SKIP] 字段已存在: {col_name}")

        db.session.commit()
        print("\n迁移完成！")


if __name__ == '__main__':
    add_batch_columns()
