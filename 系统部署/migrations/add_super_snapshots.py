"""
数据库迁移：超级定位快照表

功能：
1. super_snapshots - 超级定位快照表（用户级别，每次问题挖掘+画像生成后保存一份快照）
   - 支持每次操作生成新快照版本
   - 保存完整的表单数据 + 问题列表 + 画像数据
   - 换一批时更新同一会话的最新快照
   - 页面加载时恢复最新快照
"""

from models.models import db


def upgrade():
    """执行迁移 - 创建超级定位快照表"""

    # ============================================
    # 超级定位快照表
    # ============================================
    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS super_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id VARCHAR(64),
            version INTEGER DEFAULT 1,
            form_data TEXT NOT NULL,
            problems_data TEXT NOT NULL,
            portraits_data TEXT,
            selected_problem_id INTEGER,
            selected_portrait_index INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # 创建索引
    db.session.execute(db.text("CREATE INDEX IF NOT EXISTS idx_super_snapshots_user ON super_snapshots(user_id)"))
    db.session.execute(db.text("CREATE INDEX IF NOT EXISTS idx_super_snapshots_session ON super_snapshots(user_id, session_id)"))
    db.session.execute(db.text("CREATE INDEX IF NOT EXISTS idx_super_snapshots_updated ON super_snapshots(user_id, updated_at DESC)"))

    db.session.commit()
    print("迁移完成：超级定位快照表已创建")


def downgrade():
    """回滚迁移"""
    db.session.execute(db.text("DROP TABLE IF EXISTS super_snapshots"))
    db.session.commit()
    print("回滚完成：super_snapshots 表已删除")


if __name__ == '__main__':
    from app import app
    with app.app_context():
        upgrade()
