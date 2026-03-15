"""
迁移脚本：为 knowledge_accounts 表添加人设定位、商业定位、变现类型字段
"""
import sqlite3
import os

# 数据库路径
db_path = os.path.join(os.path.dirname(__file__), 'instance', 'douyin_system.db')

# 要添加的列
new_columns = [
    ('persona_role', 'VARCHAR(50)'),  # 陪伴者-我懂你/教导者-我教你/崇拜者-秀自己/陪衬者-不如你/搞笑者-逗笑你
    ('commercial_positioning', 'VARCHAR(50)'),  # 引流/卖货
    ('monetization_type', 'VARCHAR(50)')  # 单品/赛道级
]

def migrate():
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_accounts'")
    if not cursor.fetchone():
        print("表 knowledge_accounts 不存在")
        conn.close()
        return

    # 检查并添加列
    cursor.execute("PRAGMA table_info(knowledge_accounts)")
    existing_columns = [col[1] for col in cursor.fetchall()]

    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE knowledge_accounts ADD COLUMN {col_name} {col_type}")
                print(f"已添加列: {col_name}")
            except Exception as e:
                print(f"添加列 {col_name} 失败: {e}")
        else:
            print(f"列 {col_name} 已存在，跳过")

    conn.commit()
    conn.close()
    print("迁移完成")

if __name__ == '__main__':
    migrate()
