"""
数据库迁移：画像专属关键词库 + 选题库字段

功能：
1. saved_portraits 新增专属库字段
2. user_portrait_quota 新增库更新配额字段
3. template_version_history 模板版本历史表
"""

from models.models import db


def upgrade():
    """执行迁移"""

    # ============================================
    # 1. saved_portraits 新增字段
    # ============================================
    migrations = [
        # 画像专属关键词库/选题库
        ("ALTER TABLE saved_portraits ADD COLUMN keyword_library TEXT", "专属关键词库"),
        ("ALTER TABLE saved_portraits ADD COLUMN topic_library TEXT", "专属选题库"),
        ("ALTER TABLE saved_portraits ADD COLUMN keyword_updated_at TIMESTAMP", "关键词库更新时间"),
        ("ALTER TABLE saved_portraits ADD COLUMN topic_updated_at TIMESTAMP", "选题库更新时间"),
        ("ALTER TABLE saved_portraits ADD COLUMN keyword_update_count INTEGER DEFAULT 0", "关键词库更新次数"),
        ("ALTER TABLE saved_portraits ADD COLUMN topic_update_count INTEGER DEFAULT 0", "选题库更新次数"),
        ("ALTER TABLE saved_portraits ADD COLUMN keyword_cache_expires_at TIMESTAMP", "关键词库过期时间"),
        ("ALTER TABLE saved_portraits ADD COLUMN topic_cache_expires_at TIMESTAMP", "选题库过期时间"),
        # 关联画像ID（用于关联问题识别会话）
        ("ALTER TABLE saved_portraits ADD COLUMN session_id INTEGER", "来源会话ID"),
    ]

    for sql, desc in migrations:
        try:
            db.session.execute(db.text(sql))
            print(f"  ✅ {desc}")
        except Exception as e:
            # SQLite 不支持 IF NOT EXISTS，需要先检查列是否存在
            if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                print(f"  ⏭️  {desc}（已存在，跳过）")
            else:
                print(f"  ⚠️  {desc}：{e}")

    # ============================================
    # 2. user_portrait_quota 新增字段
    # ============================================
    quota_migrations = [
        ("ALTER TABLE user_portrait_quota ADD COLUMN keyword_update_limit INTEGER DEFAULT 2", "关键词库更新月限制"),
        ("ALTER TABLE user_portrait_quota ADD COLUMN keyword_updates_used INTEGER DEFAULT 0", "关键词库已更新次数"),
        ("ALTER TABLE user_portrait_quota ADD COLUMN topic_update_limit INTEGER DEFAULT 2", "选题库更新月限制"),
        ("ALTER TABLE user_portrait_quota ADD COLUMN topic_updates_used INTEGER DEFAULT 0", "选题库已更新次数"),
        ("ALTER TABLE user_portrait_quota ADD COLUMN keyword_quota_start DATE", "关键词库配额起始日"),
        ("ALTER TABLE user_portrait_quota ADD COLUMN topic_quota_start DATE", "选题库配额起始日"),
    ]

    for sql, desc in quota_migrations:
        try:
            db.session.execute(db.text(sql))
            print(f"  ✅ {desc}")
        except Exception as e:
            if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                print(f"  ⏭️  {desc}（已存在，跳过）")
            else:
                print(f"  ⚠️  {desc}：{e}")

    # ============================================
    # 3. 模板版本历史表
    # ============================================
    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS template_version_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_type VARCHAR(50) NOT NULL,
            template_id INTEGER NOT NULL,
            version VARCHAR(20) NOT NULL,
            content_snapshot TEXT,
            variables_snapshot TEXT,
            change_summary TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    print("  ✅ 模板版本历史表")

    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS template_variable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_type VARCHAR(50) NOT NULL,
            variable_name VARCHAR(100) NOT NULL,
            variable_label VARCHAR(200),
            variable_type VARCHAR(20) DEFAULT 'text',
            default_value TEXT,
            description TEXT,
            is_required INTEGER DEFAULT 0,
            options TEXT,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    print("  ✅ 模板变量配置表")

    db.session.commit()
    print("\n✅ 迁移完成")


def downgrade():
    """回滚迁移"""
    # 注意：SQLite 不支持 DROP COLUMN，这里仅作记录
    print("SQLite 不支持 DROP COLUMN，如需回滚请手动处理")


if __name__ == '__main__':
    from app import app
    with app.app_context():
        upgrade()
