"""
迁移脚本：为 persona_methods 表添加 methodology_category 列（知识库方法论归类）
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'douyin_system.db')


def migrate():
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='persona_methods'")
    if not cursor.fetchone():
        print("表 persona_methods 不存在")
        conn.close()
        return

    cursor.execute("PRAGMA table_info(persona_methods)")
    existing_columns = [col[1] for col in cursor.fetchall()]

    if 'methodology_category' not in existing_columns:
        try:
            cursor.execute("ALTER TABLE persona_methods ADD COLUMN methodology_category VARCHAR(50) DEFAULT 'general'")
            conn.commit()
            print("已添加列: methodology_category")
        except Exception as e:
            print(f"添加列失败: {e}")
    else:
        print("列 methodology_category 已存在，跳过")

    conn.close()


if __name__ == '__main__':
    migrate()
