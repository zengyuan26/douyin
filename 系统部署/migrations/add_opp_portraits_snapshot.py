"""
数据库迁移：为 super_snapshots 表添加 opp_portraits_data 列
"""
from models.models import db


def upgrade():
    """添加 opp_portraits_data 列"""
    db.session.execute(db.text(
        "ALTER TABLE super_snapshots ADD COLUMN opp_portraits_data TEXT"
    ))
    db.session.commit()
    print("迁移完成：super_snapshots 表已添加 opp_portraits_data 列")


def downgrade():
    """回滚（SQLite 不支持 DROP COLUMN，这里仅做占位）"""
    print("回滚：SQLite 不支持 DROP COLUMN，请手动处理")


if __name__ == '__main__':
    from app import app
    with app.app_context():
        upgrade()
