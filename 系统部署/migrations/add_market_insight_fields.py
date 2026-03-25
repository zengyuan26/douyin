#!/usr/bin/env python3
"""
迁移脚本：为 analysis_dimensions 表添加市场洞察专用字段
新增字段：
- trigger_conditions: JSON格式触发条件
- content_template: 内容模板
- importance: 重要性
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models.models import AnalysisDimension


def run_migration():
    """执行迁移"""
    with app.app_context():
        # 检查字段是否已存在
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('analysis_dimensions')]

        print("当前 analysis_dimensions 表字段:", columns)

        # 添加新字段
        new_fields = {
            'trigger_conditions': 'JSON',
            'content_template': 'Text',
            'importance': 'Integer'
        }

        with db.engine.connect() as conn:
            for field, field_type in new_fields.items():
                if field not in columns:
                    print(f"添加字段: {field} ({field_type})")
                    if field_type == 'JSON':
                        conn.execute(db.text(f"ALTER TABLE analysis_dimensions ADD COLUMN {field} JSON DEFAULT '{{}}'"))
                    elif field_type == 'Text':
                        conn.execute(db.text(f"ALTER TABLE analysis_dimensions ADD COLUMN {field} TEXT"))
                    elif field_type == 'Integer':
                        conn.execute(db.text(f"ALTER TABLE analysis_dimensions ADD COLUMN {field} INTEGER DEFAULT 1"))
                    conn.commit()
                else:
                    print(f"字段已存在: {field}")

        # 更新 importance 字段的默认值（如果有老数据）
        existing_dims = AnalysisDimension.query.filter(
            (AnalysisDimension.importance == None) | (AnalysisDimension.importance == 0)
        ).all()
        for dim in existing_dims:
            dim.importance = 1
        db.session.commit()

        print("迁移完成!")


def rollback_migration():
    """回滚迁移"""
    with app.app_context():
        with db.engine.connect() as conn:
            conn.execute(db.text("ALTER TABLE analysis_dimensions DROP COLUMN IF EXISTS trigger_conditions"))
            conn.execute(db.text("ALTER TABLE analysis_dimensions DROP COLUMN IF EXISTS content_template"))
            conn.execute(db.text("ALTER TABLE analysis_dimensions DROP COLUMN IF EXISTS importance"))
            conn.commit()
        print("回滚完成!")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        rollback_migration()
    else:
        run_migration()
