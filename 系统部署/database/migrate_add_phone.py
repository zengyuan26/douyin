"""
数据库迁移脚本 - 添加 phone 字段到 users 表
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.models import db

def migrate():
    with app.app_context():
        # 检查 phone 列是否存在
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('users')]
        
        if 'phone' not in columns:
            # 添加 phone 列
            db.engine.execute('ALTER TABLE users ADD COLUMN phone VARCHAR(20)')
            print("✅ phone 字段已添加到 users 表")
        else:
            print("ℹ️ phone 字段已存在，无需迁移")

if __name__ == '__main__':
    migrate()
