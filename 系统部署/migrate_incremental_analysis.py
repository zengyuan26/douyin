"""
数据库迁移脚本 - 添加增量分析控制字段
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "instance", "douyin_system.db")

def migrate():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查字段是否已存在
    cursor.execute("PRAGMA table_info(knowledge_accounts)")
    columns = [col[1] for col in cursor.fetchall()]
    
    new_fields = [
        ("last_nickname", "VARCHAR(100)"),
        ("nickname_analyzed_at", "DATETIME"),
        ("last_bio", "TEXT"),
        ("bio_analyzed_at", "DATETIME"),
        ("other_analyzed_at", "DATETIME")
    ]
    
    for field_name, field_type in new_fields:
        if field_name not in columns:
            try:
                cursor.execute(f"ALTER TABLE knowledge_accounts ADD COLUMN {field_name} {field_type}")
                print(f"✅ 添加字段: {field_name}")
            except Exception as e:
                print(f"❌ 添加字段失败 {field_name}: {e}")
        else:
            print(f"⏭️  字段已存在: {field_name}")
    
    conn.commit()
    conn.close()
    print("\n✅ 迁移完成!")

if __name__ == "__main__":
    migrate()
