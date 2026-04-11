"""添加 quality_report 字段到 public_generations 表"""

import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'douyin_system.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查列是否存在
cursor.execute("PRAGMA table_info(public_generations)")
columns = [col[1] for col in cursor.fetchall()]

if 'quality_report' not in columns:
    cursor.execute("ALTER TABLE public_generations ADD COLUMN quality_report JSON")
    print("✓ 已添加 quality_report 字段")
else:
    print("✓ quality_report 字段已存在")

conn.commit()
conn.close()
print("✓ 迁移完成")
