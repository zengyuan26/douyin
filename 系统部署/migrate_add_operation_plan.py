#!/usr/bin/env python3
"""
数据库迁移脚本：为 saved_portraits 表添加 selected_opportunity 和 client_profile 字段
运行方式：python migrate_add_operation_plan.py
"""

import sys
import os

# 添加系统部署目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db


def run_migration():
    """执行迁移"""
    with app.app_context():
        # 检查表是否存在
        from sqlalchemy import inspect
        inspector = inspect(db.engine)

        # 获取 saved_portraits 表的现有列
        columns = [col['name'] for col in inspector.get_columns('saved_portraits')]
        print(f"当前 saved_portraits 表的列: {columns}")

        # 需要添加的新列
        new_columns = {
            'selected_opportunity': 'JSON',
            'client_profile': 'JSON'
        }

        with db.engine.connect() as conn:
            for column_name, column_type in new_columns.items():
                if column_name not in columns:
                    print(f"添加列: {column_name} ({column_type})...")
                    try:
                        # SQLite 语法
                        sql = f"ALTER TABLE saved_portraits ADD COLUMN {column_name} {column_type}"
                        conn.execute(db.text(sql))
                        conn.commit()
                        print(f"✓ 成功添加列: {column_name}")
                    except Exception as e:
                        print(f"✗ 添加列失败 {column_name}: {e}")
                else:
                    print(f"列已存在: {column_name}")

        # 验证迁移结果
        print("\n迁移后检查:")
        inspector = inspect(db.engine)
        new_columns_check = [col['name'] for col in inspector.get_columns('saved_portraits')]
        print(f"更新后的列: {new_columns_check}")

        for col in ['selected_opportunity', 'client_profile']:
            if col in new_columns_check:
                print(f"✓ {col} 列已存在")
            else:
                print(f"✗ {col} 列仍然缺失")


if __name__ == '__main__':
    print("=" * 50)
    print("数据库迁移：添加 selected_opportunity 和 client_profile 字段")
    print("=" * 50)
    run_migration()
    print("\n迁移完成!")
