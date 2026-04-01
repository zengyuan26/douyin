"""
数据库索引迁移脚本

执行命令：cd 系统部署 && python add_indexes.py

新增索引：
1. public_industry_keywords: idx_keyword_industry_type(industry, keyword_type, is_active)
2. public_industry_topics: idx_topic_industry(industry, is_active)
3. saved_portraits: idx_portrait_user_created(user_id, created_at)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db


MIGRATIONS = [
    # 关键词库：(industry, keyword_type, is_active) — 替代旧的 (industry, keyword_type)
    ("public_industry_keywords", "idx_keyword_industry_type_v2",
     "CREATE INDEX IF NOT EXISTS idx_keyword_industry_type_v2 ON public_industry_keywords (industry, keyword_type, is_active)"),

    # 选题库：(industry, is_active) — 替代旧的 (industry,)
    ("public_industry_topics", "idx_topic_industry_v2",
     "CREATE INDEX IF NOT EXISTS idx_topic_industry_v2 ON public_industry_topics (industry, is_active)"),

    # 画像列表：(user_id, created_at) — 替代单列 user_id
    ("saved_portraits", "idx_portrait_user_created",
     "CREATE INDEX IF NOT EXISTS idx_portrait_user_created ON saved_portraits (user_id, created_at)"),
]

OLD_INDEXES = [
    ("public_industry_keywords", "idx_keyword_industry_type"),
    ("public_industry_topics", "idx_topic_industry"),
]


def run():
    with app.app_context():
        conn = db.engine.connect()

        for table, index_name, sql in MIGRATIONS:
            try:
                print(f"[迁移] 创建索引 {index_name} on {table}...")
                conn.execute(db.text(sql))
                conn.commit()
                print(f"[迁移] ✓ {index_name} 创建成功")
            except Exception as e:
                print(f"[迁移] ✗ {index_name} 失败: {e}")

        print("\n[迁移] 是否删除旧索引（确认无误后设为 True）: ")
        drop_old = os.environ.get("DROP_OLD_INDEXES", "false").lower() == "true"

        if drop_old:
            for table, index_name in OLD_INDEXES:
                try:
                    print(f"[迁移] 删除旧索引 {index_name}...")
                    conn.execute(db.text(f"DROP INDEX IF EXISTS {index_name}"))
                    conn.commit()
                    print(f"[迁移] ✓ {index_name} 已删除")
                except Exception as e:
                    print(f"[迁移] ✗ 删除 {index_name} 失败: {e}")
        else:
            print("[迁移] 跳过删除旧索引（设置 DROP_OLD_INDEXES=true 手动删除）")

        print("\n[迁移] 索引迁移完成")
        conn.close()


if __name__ == '__main__':
    run()
