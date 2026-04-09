"""
数据库迁移脚本：星系图谱增强功能 - 新增字段

添加以下表的增强字段：
1. public_industry_topics    → scene_options、content_style
2. public_generations       → selected_scenes
3. saved_portraits          → cover_thumb、geo_province、geo_city、geo_level、geo_coverages、geo_tags
4. persona_user_problems    → geo_trigger_regions、geo_seasonal_factor

同时创建推荐索引：
- idx_portrait_geo     (saved_portraits.user_id, geo_province, geo_city)
- idx_topic_scene      (public_industry_topics.industry, is_active)

运行方式：python migrate_galaxy_enhancement.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.models import db
from sqlalchemy import text


def get_table_columns(conn, table_name):
    """获取表的所有列名"""
    result = conn.execute(text(f"PRAGMA table_info({table_name})"))
    return [row[1] for row in result.fetchall()]


def add_column_if_not_exists(conn, table, column, definition):
    """安全添加列（不存在才添加）"""
    columns = get_table_columns(conn, table)
    if column in columns:
        print(f"  · {table}.{column} 列已存在，跳过")
        return False
    else:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        conn.commit()
        print(f"  ✓ {table}.{column} 列已添加")
        return True


def create_index_if_not_exists(conn, index_name, table, columns):
    """安全创建索引（不存在才创建）"""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=:name"
    ), {'name': index_name})
    if result.fetchone():
        print(f"  · 索引 {index_name} 已存在，跳过")
        return False
    else:
        conn.execute(text(f"CREATE INDEX {index_name} ON {table}({columns})"))
        conn.commit()
        print(f"  ✓ 索引 {index_name} 已创建")
        return True


def migrate():
    with app.app_context():
        conn = db.engine.connect()

        print("=" * 60)
        print("星系图谱增强功能 - 数据库迁移")
        print("=" * 60)

        # =========================================================================
        # 1. public_industry_topics 新增字段
        # =========================================================================
        print("\n[1/4] public_industry_topics 表")
        added = add_column_if_not_exists(
            conn, 'public_industry_topics', 'scene_options',
            "JSON DEFAULT '[]'"
        )
        if added:
            print("  ℹ scene_options：AI 生成的场景组合列表（内容策略维度）")

        added = add_column_if_not_exists(
            conn, 'public_industry_topics', 'content_style',
            "VARCHAR(50)"
        )
        if added:
            print("  ℹ content_style：内容风格（情绪共鸣/干货科普/犀利吐槽/故事叙述/权威背书）")

        # =========================================================================
        # 2. public_generations 新增字段
        # =========================================================================
        print("\n[2/4] public_generations 表")
        added = add_column_if_not_exists(
            conn, 'public_generations', 'selected_scenes',
            "JSON"
        )
        if added:
            print("  ℹ selected_scenes：客户选择的具体场景组合")

        # =========================================================================
        # 3. saved_portraits 新增字段（恒星节点）
        # =========================================================================
        print("\n[3/4] saved_portraits 表（恒星节点）")
        add_column_if_not_exists(
            conn, 'saved_portraits', 'cover_thumb',
            "VARCHAR(255) DEFAULT ''"
        )
        add_column_if_not_exists(
            conn, 'saved_portraits', 'geo_province',
            "VARCHAR(50)"
        )
        add_column_if_not_exists(
            conn, 'saved_portraits', 'geo_city',
            "VARCHAR(50)"
        )
        add_column_if_not_exists(
            conn, 'saved_portraits', 'geo_level',
            "VARCHAR(20) DEFAULT 'city'"
        )
        add_column_if_not_exists(
            conn, 'saved_portraits', 'geo_coverages',
            "JSON DEFAULT '[]'"
        )
        add_column_if_not_exists(
            conn, 'saved_portraits', 'geo_tags',
            "JSON DEFAULT '[]'"
        )

        # =========================================================================
        # 4. persona_user_problems 新增字段（行星节点）
        # =========================================================================
        print("\n[4/4] persona_user_problems 表（行星节点）")
        add_column_if_not_exists(
            conn, 'persona_user_problems', 'geo_trigger_regions',
            "JSON DEFAULT '[]'"
        )
        add_column_if_not_exists(
            conn, 'persona_user_problems', 'geo_seasonal_factor',
            "VARCHAR(100)"
        )

        # =========================================================================
        # 5. 创建推荐索引
        # =========================================================================
        print("\n[5/5] 创建推荐索引")
        create_index_if_not_exists(
            conn, 'idx_portrait_geo',
            'saved_portraits', 'user_id, geo_province, geo_city'
        )
        create_index_if_not_exists(
            conn, 'idx_topic_scene',
            'public_industry_topics', 'industry, is_active'
        )

        # =========================================================================
        # 验证最终状态
        # =========================================================================
        print("\n[验证] 各表最终字段")

        tables = [
            ('public_industry_topics', [
                'scene_options', 'content_style', 'applicable_scenarios'
            ]),
            ('public_generations', [
                'portrait_id', 'problem_id', 'selected_scenes'
            ]),
            ('saved_portraits', [
                'cover_thumb', 'geo_province', 'geo_city',
                'geo_level', 'geo_coverages', 'geo_tags'
            ]),
            ('persona_user_problems', [
                'geo_trigger_regions', 'geo_seasonal_factor'
            ]),
        ]

        for table_name, expected_fields in tables:
            cols = get_table_columns(conn, table_name)
            found = [f for f in expected_fields if f in cols]
            missing = [f for f in expected_fields if f not in cols]
            status = "✓" if not missing else "✗"
            print(f"  {status} {table_name}: {found}" +
                  (f" | 缺失: {missing}" if missing else ""))

        conn.close()

        print("\n" + "=" * 60)
        print("✓ 迁移完成！")
        print("=" * 60)
        print("""
后续步骤：
1. 运行测试验证：python test_galaxy_enhancement.py
2. 检查 API 代码是否已更新（models、routes、services）
3. 新增字段的默认值策略：
   - geo_* 字段：历史数据默认为 null（前端展示"全国"）
   - scene_options：历史数据默认为 []（空数组）
   - cover_thumb：历史数据默认为 ''（前端显示占位图）
        """)


if __name__ == '__main__':
    migrate()
