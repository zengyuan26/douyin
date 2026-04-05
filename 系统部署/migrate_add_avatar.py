#!/usr/bin/env python3
"""迁移脚本：为 public_users 表添加头像字段"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db


def run_migration():
    """执行迁移"""
    with app.app_context():
        conn = db.engine.raw_connection()
        cursor = conn.cursor()

        try:
            # 检查 avatar 字段是否已存在
            cursor.execute("PRAGMA table_info(public_users)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'avatar' not in columns:
                cursor.execute("ALTER TABLE public_users ADD COLUMN avatar VARCHAR(500) DEFAULT ''")
                conn.commit()
                print("✓ avatar 字段添加成功")
            else:
                print("✓ avatar 字段已存在，跳过")

        except Exception as e:
            conn.rollback()
            print(f"✗ 迁移失败: {e}")
            raise
        finally:
            cursor.close()
            conn.close()


if __name__ == '__main__':
    run_migration()
