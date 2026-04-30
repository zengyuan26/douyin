"""
数据库迁移脚本 - 添加内容计划相关表

执行方式：
python -m flask db upgrade
或
python migrate_add_content_plan.py
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models.models import User
from models.public_models import PublicUser


def upgrade():
    """创建内容计划相关表"""
    with app.app_context():
        # 1. 创建 topic_libraries 表
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS topic_libraries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                portrait_id INTEGER,
                title VARCHAR(500) NOT NULL,
                type VARCHAR(50) NOT NULL,
                priority VARCHAR(10) NOT NULL,
                stage VARCHAR(50) NOT NULL,
                content_type VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'draft',
                metadata JSON,
                sort_order INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                deleted_at DATETIME,
                FOREIGN KEY (user_id) REFERENCES public_users(id)
            )
        """))

        # 创建索引
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_topic_library_user
            ON topic_libraries(user_id)
        """))
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_topic_library_portrait
            ON topic_libraries(portrait_id)
        """))
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_topic_library_priority
            ON topic_libraries(priority)
        """))
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_topic_library_content_type
            ON topic_libraries(content_type)
        """))

        # 2. 创建 content_plans 表
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS content_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER NOT NULL,
                content_type VARCHAR(20) NOT NULL,

                -- 标题相关
                recommended_title VARCHAR(200),
                title_options TEXT DEFAULT '[]',
                title_pattern VARCHAR(50),
                hvf_analysis TEXT,

                -- 标签相关
                l1_tags TEXT DEFAULT '[]',
                l2_tags TEXT DEFAULT '[]',
                l3_tags TEXT DEFAULT '[]',
                final_tags TEXT DEFAULT '[]',

                -- 情绪动线
                emotional_curve TEXT,
                topic_type VARCHAR(50),

                -- 版式相关
                layouts TEXT DEFAULT '[]',
                colors TEXT,
                visual_requirements TEXT,

                -- 长文特有
                article_structure TEXT,
                writing_style TEXT,

                -- 短视频特有
                hook TEXT,
                script_outline TEXT,
                visual_notes TEXT,

                status VARCHAR(20) DEFAULT 'draft',
                version INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                deleted_at DATETIME,
                FOREIGN KEY (topic_id) REFERENCES topic_libraries(id) ON DELETE CASCADE
            )
        """))

        # 创建索引
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_content_plan_topic
            ON content_plans(topic_id)
        """))
        db.session.execute(db.text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_content_plan_topic_type
            ON content_plans(topic_id, content_type)
        """))

        # 3. 创建 tasks 表
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_type VARCHAR(50) NOT NULL,
                status VARCHAR(20) DEFAULT 'queued',
                progress INTEGER DEFAULT 0,
                current_step VARCHAR(50),
                input_data TEXT NOT NULL,
                result_data TEXT,
                error_message TEXT,
                estimated_time INTEGER,
                started_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES public_users(id)
            )
        """))

        # 创建索引
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_task_user
            ON tasks(user_id)
        """))
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_task_status
            ON tasks(status)
        """))

        # 4. 创建 task_steps 表
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS task_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                step_id VARCHAR(50) NOT NULL,
                step_name VARCHAR(100),
                status VARCHAR(20) DEFAULT 'pending',
                started_at DATETIME,
                completed_at DATETIME,
                duration_ms INTEGER,
                input_data TEXT,
                output_data TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """))

        # 创建索引
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_task_step_task
            ON task_steps(task_id)
        """))

        db.session.commit()
        print("✓ 内容计划相关表创建成功")


def downgrade():
    """删除内容计划相关表"""
    with app.app_context():
        db.session.execute(db.text("DROP TABLE IF EXISTS task_steps"))
        db.session.execute(db.text("DROP TABLE IF EXISTS tasks"))
        db.session.execute(db.text("DROP TABLE IF EXISTS content_plans"))
        db.session.execute(db.text("DROP TABLE IF EXISTS topic_libraries"))
        db.session.commit()
        print("✓ 内容计划相关表删除成功")


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
        downgrade()
    else:
        upgrade()
