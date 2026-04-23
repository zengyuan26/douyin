"""
数据库迁移：蓝海机会快照表

功能：
1. opportunity_snapshots - 用户收藏的蓝海机会快照表
   - 存储用户收藏的蓝海机会完整数据
   - 关联用户ID、业务描述快照、来源分析时间
   - 记录是否已用于生成画像
   - 重置业务描述时清空所有快照
"""

from models.models import db


def upgrade():
    """执行迁移 - 创建蓝海机会快照表"""

    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS opportunity_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            snapshot_data TEXT NOT NULL,
            note VARCHAR(200),
            source_business_desc VARCHAR(500),
            source_business_type VARCHAR(50),
            source_analyzed_at TIMESTAMP,
            used_for_portrait_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES public_users(id),
            FOREIGN KEY (used_for_portrait_id) REFERENCES saved_portraits(id)
        )
    """))

    db.session.execute(db.text(
        "CREATE INDEX IF NOT EXISTS idx_snapshot_user ON opportunity_snapshots(user_id)"
    ))
    db.session.execute(db.text(
        "CREATE INDEX IF NOT EXISTS idx_snapshot_user_created ON opportunity_snapshots(user_id, created_at DESC)"
    ))

    db.session.commit()
    print("迁移完成：opportunity_snapshots 表已创建")


def downgrade():
    """回滚迁移"""
    db.session.execute(db.text("DROP TABLE IF EXISTS opportunity_snapshots"))
    db.session.commit()
    print("回滚完成：opportunity_snapshots 表已删除")


if __name__ == '__main__':
    from app import app
    with app.app_context():
        upgrade()
