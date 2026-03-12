# -*- coding: utf-8 -*-
"""
迁移脚本：为 knowledge_accounts 表添加内容布局字段
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db

def migrate_add_content_layout():
    """添加内容布局字段"""
    with app.app_context():
        # 检查列是否存在，不存在则添加
        conn = db.engine.connect()
        
        # MySQL 语法
        try:
            # content_persona
            conn.execute(db.text(
                "ALTER TABLE knowledge_accounts ADD COLUMN content_persona INTEGER DEFAULT 0"
            ))
            print("✓ 添加 content_persona 列")
        except Exception as e:
            if 'Duplicate column' in str(e) or '已存在' in str(e):
                print("- content_persona 列已存在")
            else:
                print(f"! content_persona: {e}")
        
        try:
            # content_topic
            conn.execute(db.text(
                "ALTER TABLE knowledge_accounts ADD COLUMN content_topic INTEGER DEFAULT 0"
            ))
            print("✓ 添加 content_topic 列")
        except Exception as e:
            if 'Duplicate column' in str(e) or '已存在' in str(e):
                print("- content_topic 列已存在")
            else:
                print(f"! content_topic: {e}")
        
        try:
            # content_daily
            conn.execute(db.text(
                "ALTER TABLE knowledge_accounts ADD COLUMN content_daily INTEGER DEFAULT 0"
            ))
            print("✓ 添加 content_daily 列")
        except Exception as e:
            if 'Duplicate column' in str(e) or '已存在' in str(e):
                print("- content_daily 列已存在")
            else:
                print(f"! content_daily: {e}")
        
        conn.commit()
        conn.close()
        print("✓ 迁移完成")

if __name__ == '__main__':
    migrate_add_content_layout()
