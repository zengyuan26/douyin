"""
数据库迁移：选题方法论增强字段

功能：
1. topic_libraries 表新增方法论字段
2. content_plans 表新增方法论字段
3. 添加索引

运行方式：
python migrations/add_topic_methodology_fields.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db


def upgrade():
    """执行迁移"""
    print("[Migration] 开始选题方法论字段迁移...")

    with app.app_context():
        try:
            # ============================================
            # 1. topic_libraries 表新增字段
            # ============================================
            topic_libraries_migrations = [
                # L1: 营销目的分类
                ("ALTER TABLE topic_libraries ADD COLUMN marketing_purpose VARCHAR(20)", "L1营销目的"),
                ("ALTER TABLE topic_libraries ADD COLUMN marketing_purpose_name VARCHAR(50)", "L1营销目的名称"),

                # 选题核心洞察
                ("ALTER TABLE topic_libraries ADD COLUMN core_insight TEXT", "选题核心洞察"),
                ("ALTER TABLE topic_libraries ADD COLUMN target_audience VARCHAR(200)", "精准目标人群"),
                ("ALTER TABLE topic_libraries ADD COLUMN differentiation_angle VARCHAR(200)", "差异化切入角度"),

                # 内容创作指导（JSON）
                ("ALTER TABLE topic_libraries ADD COLUMN content_guidance TEXT", "内容创作指导"),

                # 三种内容形式的创作要点（JSON）
                ("ALTER TABLE topic_libraries ADD COLUMN format_guidance TEXT", "格式指导"),

                # 场景元素（JSON）
                ("ALTER TABLE topic_libraries ADD COLUMN scene_elements TEXT", "场景元素"),

                # 选题来源追溯（JSON）
                ("ALTER TABLE topic_libraries ADD COLUMN source_trace TEXT", "选题来源追溯"),
            ]

            print("\n[1] topic_libraries 表字段：")
            for sql, desc in topic_libraries_migrations:
                try:
                    db.session.execute(db.text(sql))
                    print(f"  ✅ {desc}")
                except Exception as e:
                    if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                        print(f"  ⏭️  {desc}（已存在，跳过）")
                    else:
                        print(f"  ⚠️  {desc}：{e}")

            # ============================================
            # 2. content_plans 表新增字段
            # ============================================
            content_plans_migrations = [
                # 方法论指导引用（JSON）
                ("ALTER TABLE content_plans ADD COLUMN methodology_ref TEXT", "方法论指导引用"),

                # 情绪动线（JSON）
                ("ALTER TABLE content_plans ADD COLUMN emotion_arc TEXT", "情绪动线"),

                # 人设表达元素（JSON）
                ("ALTER TABLE content_plans ADD COLUMN persona_elements TEXT", "人设表达元素"),

                # 标题设计指导（JSON）
                ("ALTER TABLE content_plans ADD COLUMN title_guidance TEXT", "标题设计指导"),

                # 内容版式指导（JSON）
                ("ALTER TABLE content_plans ADD COLUMN layout_guidance TEXT", "内容版式指导"),
            ]

            print("\n[2] content_plans 表字段：")
            for sql, desc in content_plans_migrations:
                try:
                    db.session.execute(db.text(sql))
                    print(f"  ✅ {desc}")
                except Exception as e:
                    if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                        print(f"  ⏭️  {desc}（已存在，跳过）")
                    else:
                        print(f"  ⚠️  {desc}：{e}")

            # ============================================
            # 3. 添加索引
            # ============================================
            print("\n[3] 添加索引：")

            indexes = [
                ("CREATE INDEX IF NOT EXISTS idx_topic_library_marketing ON topic_libraries(marketing_purpose)", "topic_libraries.marketing_purpose索引"),
                ("CREATE INDEX IF NOT EXISTS idx_content_plan_methodology ON content_plans(methodology_ref)", "content_plans.methodology_ref索引"),
            ]

            for sql, desc in indexes:
                try:
                    db.session.execute(db.text(sql))
                    print(f"  ✅ {desc}")
                except Exception as e:
                    if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
                        print(f"  ⏭️  {desc}（已存在，跳过）")
                    else:
                        print(f"  ⚠️  {desc}：{e}")

            # 提交事务
            db.session.commit()
            print("\n[Migration] ✅ 迁移完成!")

            # 打印验证SQL
            print("\n" + "="*60)
            print("验证SQL（可选执行）：")
            print("="*60)
            print("""
-- 验证 topic_libraries 表结构
PRAGMA table_info(topic_libraries);

-- 验证 content_plans 表结构
PRAGMA table_info(content_plans);

-- 验证索引
PRAGMA index_list(topic_libraries);
PRAGMA index_list(content_plans);
            """)

            return True

        except Exception as e:
            print(f"\n[Migration] ❌ 迁移失败: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return False


def downgrade():
    """回滚迁移"""
    print("[Migration] 开始回滚...")

    with app.app_context():
        try:
            # 回滚索引
            db.session.execute(db.text("DROP INDEX IF EXISTS idx_topic_library_marketing"))
            db.session.execute(db.text("DROP INDEX IF EXISTS idx_content_plan_methodology"))
            print("  ✅ 索引已删除")

            # 注意：SQLite 不支持 DROP COLUMN，需要重建表
            # 如果需要回滚，可以：
            # 1. 备份数据
            # 2. 删除表
            # 3. 重新创建表（不包含新字段）
            # 这里仅提示，不执行危险操作
            print("\n⚠️  SQLite 不支持直接删除列。如需回滚，请：")
            print("   1. 备份数据库")
            print("   2. 手动删除新增的列（需要重建表）")

            db.session.commit()
            return True

        except Exception as e:
            print(f"[Migration] ❌ 回滚失败: {e}")
            db.session.rollback()
            return False


def verify():
    """验证迁移结果"""
    print("\n[Migration] 验证迁移结果...")

    with app.app_context():
        try:
            # 检查表是否存在
            result = db.session.execute(db.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='topic_libraries'"
            ))
            if not result.fetchone():
                print("  ❌ topic_libraries 表不存在")
                return False

            result = db.session.execute(db.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='content_plans'"
            ))
            if not result.fetchone():
                print("  ❌ content_plans 表不存在")
                return False

            # 检查字段
            print("\n[topic_libraries] 字段：")
            result = db.session.execute(db.text("PRAGMA table_info(topic_libraries)"))
            columns = {row[1]: row for row in result.fetchall()}
            for field in ['marketing_purpose', 'marketing_purpose_name', 'core_insight',
                         'target_audience', 'differentiation_angle', 'content_guidance',
                         'format_guidance', 'scene_elements', 'source_trace']:
                if field in columns:
                    print(f"  ✅ {field}")
                else:
                    print(f"  ❌ {field}（缺失）")

            print("\n[content_plans] 字段：")
            result = db.session.execute(db.text("PRAGMA table_info(content_plans)"))
            columns = {row[1]: row for row in result.fetchall()}
            for field in ['methodology_ref', 'emotion_arc', 'persona_elements',
                         'title_guidance', 'layout_guidance']:
                if field in columns:
                    print(f"  ✅ {field}")
                else:
                    print(f"  ❌ {field}（缺失）")

            print("\n[索引]：")
            result = db.session.execute(db.text("PRAGMA index_list(topic_libraries)"))
            indexes = [row[1] for row in result.fetchall()]
            if 'idx_topic_library_marketing' in indexes:
                print("  ✅ idx_topic_library_marketing")
            else:
                print("  ❌ idx_topic_library_marketing（缺失）")

            result = db.session.execute(db.text("PRAGMA index_list(content_plans)"))
            indexes = [row[1] for row in result.fetchall()]
            if 'idx_content_plan_methodology' in indexes:
                print("  ✅ idx_content_plan_methodology")
            else:
                print("  ❌ idx_content_plan_methodology（缺失）")

            print("\n[Migration] ✅ 验证完成!")
            return True

        except Exception as e:
            print(f"[Migration] ❌ 验证失败: {e}")
            return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='选题方法论字段迁移')
    parser.add_argument('--verify', action='store_true', help='仅验证，不执行迁移')
    parser.add_argument('--downgrade', action='store_true', help='回滚迁移')
    args = parser.parse_args()

    if args.verify:
        verify()
    elif args.downgrade:
        downgrade()
    else:
        upgrade()
        print()
        verify()
