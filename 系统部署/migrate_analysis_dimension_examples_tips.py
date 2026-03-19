#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
方案A 迁移：为 analysis_dimensions 表增加 examples、usage_tips 字段
与公式要素一致，供 LLM 按「定义+示例+识别技巧」打分。
运行：在系统部署目录下执行 python migrate_analysis_dimension_examples_tips.py
"""
import os
import sys

# 确保能导入 app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_db_path():
    from app import app
    with app.app_context():
        url = app.config.get('SQLALCHEMY_DATABASE_URI') or ''
        if url.startswith('sqlite:///'):
            p = url.replace('sqlite:///', '')
            if not os.path.isabs(p):
                p = os.path.join(os.path.dirname(__file__), p)
            return p
    return None

def run_sqlite_migration():
    db_path = get_db_path()
    if not db_path or not os.path.exists(db_path):
        print('未找到 SQLite 数据库路径或文件不存在')
        return False
    import sqlite3
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(analysis_dimensions)")
    cols = [row[1] for row in cur.fetchall()]
    if 'examples' not in cols:
        cur.execute("ALTER TABLE analysis_dimensions ADD COLUMN examples TEXT")
        print('已添加列: examples')
    else:
        print('列 examples 已存在，跳过')
    if 'usage_tips' not in cols:
        cur.execute("ALTER TABLE analysis_dimensions ADD COLUMN usage_tips TEXT")
        print('已添加列: usage_tips')
    else:
        print('列 usage_tips 已存在，跳过')
    conn.commit()
    conn.close()
    print('迁移完成')
    return True

def run_mysql_migration():
    from app import app
    from models.models import db
    with app.app_context():
        conn = db.engine.connect()
        try:
            for col, label in [('examples', 'examples'), ('usage_tips', 'usage_tips')]:
                try:
                    conn.execute(db.text(f"ALTER TABLE analysis_dimensions ADD COLUMN {col} TEXT"))
                    conn.commit()
                    print(f'已添加列: {label}')
                except Exception as e:
                    if 'Duplicate column' in str(e) or '已存在' in str(e):
                        print(f'列 {label} 已存在，跳过')
                    else:
                        print(f'添加列 {label} 失败: {e}')
        finally:
            conn.close()
    print('迁移完成')
    return True

if __name__ == '__main__':
    from app import app
    with app.app_context():
        url = app.config.get('SQLALCHEMY_DATABASE_URI') or ''
        if 'sqlite' in url:
            run_sqlite_migration()
        elif 'mysql' in url:
            run_mysql_migration()
        else:
            print('请手动在 analysis_dimensions 表中添加列: examples TEXT, usage_tips TEXT')
