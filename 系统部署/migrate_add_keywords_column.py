#!/usr/bin/env python3
"""
迁移脚本：为 knowledge_rules 表添加 keywords 列
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models.models import db

def migrate():
    app = create_app()
    with app.app_context():
        # 检查列是否存在
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('knowledge_rules')]
        
        if 'keywords' not in columns:
            print("添加 keywords 列到 knowledge_rules 表...")
            db.session.execute(db.text(
                "ALTER TABLE knowledge_rules ADD COLUMN keywords JSON"
            ))
            db.session.commit()
            print("✅ keywords 列添加成功！")
        else:
            print("keywords 列已存在，无需迁移")

if __name__ == '__main__':
    migrate()
