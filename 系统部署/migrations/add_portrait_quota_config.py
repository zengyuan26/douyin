"""
添加画像保存配额配置表

用于后台管理员配置各方案的画像保存数量限制

运行方式：
    cd 系统部署
    PYTHONPATH=. python3 migrations/add_portrait_quota_config.py
"""

from models.models import db


def upgrade():
    """添加配置表"""
    # 创建画像配额配置表
    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS portrait_quota_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_name VARCHAR(50) NOT NULL UNIQUE,
            max_saved INTEGER NOT NULL DEFAULT 1,
            description VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    # 插入默认配置
    default_configs = [
        ('free', 1, '免费用户可保存画像数量'),
        ('basic', 5, '基础版用户可保存画像数量'),
        ('professional', 20, '专业版用户可保存画像数量'),
        ('enterprise', 100, '企业版用户可保存画像数量'),
    ]
    
    for plan, max_saved, desc in default_configs:
        db.session.execute(
            db.text("""
                INSERT OR IGNORE INTO portrait_quota_config (plan_name, max_saved, description)
                VALUES (:plan, :max_saved, :desc)
            """),
            {'plan': plan, 'max_saved': max_saved, 'desc': desc}
        )
    
    db.session.commit()
    print("画像配额配置表创建成功")


def downgrade():
    """删除配置表"""
    db.session.execute(db.text("DROP TABLE IF EXISTS portrait_quota_config"))
    db.session.commit()
    print("画像配额配置表已删除")


if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        upgrade()
