"""
数据库迁移：画像保存与频率控制

功能：
1. saved_portraits - 画像保存表
2. portrait_change_logs - 画像更换记录表
3. user_portrait_quota - 用户画像配额表
4. keyword_cache - 关键词库缓存表
5. topic_cache - 选题库缓存表
"""

from models.models import db


def upgrade():
    """执行迁移 - SQLite 兼容版本"""
    
    # ============================================
    # 1. 画像保存表
    # ============================================
    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS saved_portraits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            portrait_name VARCHAR(100) NOT NULL,
            portrait_data TEXT NOT NULL,
            business_description TEXT,
            industry VARCHAR(50),
            target_customer VARCHAR(50),
            is_default INTEGER DEFAULT 0,
            used_count INTEGER DEFAULT 0,
            last_used_at TIMESTAMP,
            source_session_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    # 创建索引
    db.session.execute(db.text("CREATE INDEX IF NOT EXISTS idx_saved_portraits_user ON saved_portraits(user_id)"))
    
    # ============================================
    # 2. 画像更换记录表
    # ============================================
    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS portrait_change_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            old_portrait_id INTEGER,
            new_portrait_id INTEGER,
            change_type VARCHAR(20) DEFAULT 'generate_new',
            change_reason VARCHAR(100),
            quota_remaining INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    db.session.execute(db.text("CREATE INDEX IF NOT EXISTS idx_change_logs_user ON portrait_change_logs(user_id)"))
    
    # ============================================
    # 3. 用户画像配额表
    # ============================================
    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS user_portrait_quota (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            plan_type VARCHAR(20) DEFAULT 'free',
            weekly_change_limit INTEGER DEFAULT 3,
            weekly_changes_used INTEGER DEFAULT 0,
            quota_week_start DATE,
            monthly_change_limit INTEGER DEFAULT 10,
            monthly_changes_used INTEGER DEFAULT 0,
            quota_month_start DATE,
            total_changes INTEGER DEFAULT 0,
            total_generations INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            keyword_update_limit INTEGER DEFAULT 1,
            keyword_updates_used INTEGER DEFAULT 0,
            keyword_quota_start DATE,
            topic_update_limit INTEGER DEFAULT 1,
            topic_updates_used INTEGER DEFAULT 0,
            topic_quota_start DATE
        )
    """))

    # 为已存在的表添加库配额列（如果不存在）
    for col_def in [
        "ALTER TABLE user_portrait_quota ADD COLUMN keyword_update_limit INTEGER DEFAULT 1",
        "ALTER TABLE user_portrait_quota ADD COLUMN keyword_updates_used INTEGER DEFAULT 0",
        "ALTER TABLE user_portrait_quota ADD COLUMN keyword_quota_start DATE",
        "ALTER TABLE user_portrait_quota ADD COLUMN topic_update_limit INTEGER DEFAULT 1",
        "ALTER TABLE user_portrait_quota ADD COLUMN topic_updates_used INTEGER DEFAULT 0",
        "ALTER TABLE user_portrait_quota ADD COLUMN topic_quota_start DATE",
        "ALTER TABLE saved_portraits ADD COLUMN keyword_library TEXT",
        "ALTER TABLE saved_portraits ADD COLUMN topic_library TEXT",
        "ALTER TABLE saved_portraits ADD COLUMN keyword_updated_at TIMESTAMP",
        "ALTER TABLE saved_portraits ADD COLUMN keyword_update_count INTEGER DEFAULT 0",
        "ALTER TABLE saved_portraits ADD COLUMN keyword_cache_expires_at TIMESTAMP",
        "ALTER TABLE saved_portraits ADD COLUMN topic_updated_at TIMESTAMP",
        "ALTER TABLE saved_portraits ADD COLUMN topic_update_count INTEGER DEFAULT 0",
        "ALTER TABLE saved_portraits ADD COLUMN topic_cache_expires_at TIMESTAMP",
    ]:
        try:
            db.session.execute(db.text(col_def))
        except Exception:
            pass  # 列已存在则忽略
    
    # ============================================
    # 4. 关键词库缓存表
    # ============================================
    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS keyword_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key VARCHAR(200) NOT NULL,
            industry VARCHAR(50),
            portrait_hash VARCHAR(64),
            keywords TEXT NOT NULL,
            keyword_types TEXT,
            cache_level VARCHAR(20) DEFAULT 'industry',
            user_id INTEGER,
            expires_at TIMESTAMP,
            is_stale INTEGER DEFAULT 0,
            hit_count INTEGER DEFAULT 0,
            last_hit_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    db.session.execute(db.text("CREATE INDEX IF NOT EXISTS idx_keyword_cache_key ON keyword_cache(cache_key)"))
    db.session.execute(db.text("CREATE INDEX IF NOT EXISTS idx_keyword_cache_industry ON keyword_cache(industry)"))
    
    # ============================================
    # 5. 选题库缓存表
    # ============================================
    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS topic_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key VARCHAR(200) NOT NULL,
            keyword_cache_id INTEGER,
            topics TEXT NOT NULL,
            topic_types TEXT,
            cache_level VARCHAR(20) DEFAULT 'industry',
            user_id INTEGER,
            expires_at TIMESTAMP,
            hit_count INTEGER DEFAULT 0,
            last_hit_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    db.session.execute(db.text("CREATE INDEX IF NOT EXISTS idx_topic_cache_key ON topic_cache(cache_key)"))
    
    db.session.commit()
    print("迁移完成：画像保存与频率控制表已创建")


def downgrade():
    """回滚迁移"""
    db.session.execute(db.text("DROP TABLE IF EXISTS topic_cache"))
    db.session.execute(db.text("DROP TABLE IF EXISTS keyword_cache"))
    db.session.execute(db.text("DROP TABLE IF EXISTS user_portrait_quota"))
    db.session.execute(db.text("DROP TABLE IF EXISTS portrait_change_logs"))
    db.session.execute(db.text("DROP TABLE IF EXISTS saved_portraits"))
    db.session.commit()
    print("回滚完成：相关表已删除")


if __name__ == '__main__':
    from app import app
    with app.app_context():
        upgrade()
