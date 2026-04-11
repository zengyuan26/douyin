# -*- coding: utf-8 -*-
"""
迁移：创建内容展示区块配置表

运行方式：
python migrations/add_section_display_config.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db


def run_migration():
    """执行数据库迁移"""
    print("[Migration] 开始迁移：创建内容展示区块配置表...")

    with app.app_context():
        try:
            # 导入模型以确保表被注册
            from models.public_models import ContentSectionDisplayConfig
            db.create_all()
            print("[Migration] content_section_display_config 表创建完成")

            print("[Migration] 迁移完成!")
            return True
        except Exception as e:
            print(f"[Migration] 迁移失败: {e}")
            return False


if __name__ == '__main__':
    run_migration()
