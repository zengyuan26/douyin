#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
迁移：为 analysis_dimensions 表添加 applicable_audience 列

使用方法：
cd /Volumes/增元/项目/douyin/系统部署
python migrations/add_applicable_audience_column.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db


def migrate():
    with app.app_context():
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('analysis_dimensions')]
        print(f"当前 analysis_dimensions 表字段: {columns}")

        new_columns = [
            ('examples', 'TEXT'),
            ('usage_tips', 'TEXT'),
            ('applicable_audience', 'TEXT'),
        ]

        for col_name, col_type in new_columns:
            if col_name not in columns:
                try:
                    sql = f"ALTER TABLE analysis_dimensions ADD COLUMN {col_name} {col_type}"
                    db.session.execute(db.text(sql))
                    print(f"[OK] 添加字段: {col_name}")
                except Exception as e:
                    print(f"[ERROR] 添加字段 {col_name} 失败: {e}")
            else:
                print(f"[SKIP] 字段已存在: {col_name}")

        db.session.commit()
        print("\n迁移完成！")


if __name__ == '__main__':
    migrate()
