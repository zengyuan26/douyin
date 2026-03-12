#!/usr/bin/env python3
"""导入模板数据到数据库"""

import os
import sys
import sqlite3

# 设置路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 数据库路径
DB_PATH = os.path.join(BASE_DIR, 'instance', 'douyin_system.db')

# 模板文件路径
TEMPLATE_FILES = {
    'market_analysis': 'skills/insights-analyst/输出/行业分析/行业分析报告_模板.md',
    'keyword': 'skills/geo-seo/输出/关键词库/关键词库_模板.md',
    'topic': 'skills/geo-seo/输出/选题推荐/选题库_模板.md',
    'operation': 'skills/operations-expert/输出/运营规划/运营规划方案_模板.md',
}

# 模板配置
TEMPLATES = [
    {
        'name': '市场分析报告模板',
        'type': 'market_analysis',
        'category': 'universal',
        'file': 'market_analysis',
    },
    {
        'name': '关键词库模板',
        'type': 'keyword',
        'category': 'universal',
        'file': 'keyword',
    },
    {
        'name': '选题库模板',
        'type': 'topic',
        'category': 'universal',
        'file': 'topic',
    },
    {
        'name': '运营规划方案模板',
        'type': 'operation',
        'category': 'universal',
        'file': 'operation',
    },
]


def read_template_file(filepath):
    """读取模板文件内容"""
    full_path = os.path.join(BASE_DIR, filepath)
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''


def import_templates():
    """导入模板到数据库"""
    if not os.path.exists(DB_PATH):
        print(f"数据库不存在: {DB_PATH}")
        print("请先运行 init_db.py 初始化数据库")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查是否已有模板数据
    cursor.execute("SELECT COUNT(*) FROM report_templates")
    count = cursor.fetchone()[0]

    if count > 0:
        print(f"数据库中已有 {count} 个报告模板，跳过导入")
        conn.close()
        return True

    print("开始导入模板...")

    for template in TEMPLATES:
        # 读取模板文件内容
        content = read_template_file(TEMPLATE_FILES.get(template['file'], ''))

        if not content:
            print(f"警告: 模板文件不存在 - {template['file']}")
            content = f"# {template['name']}\n\n请在此处编辑模板内容"

        # 插入数据库
        cursor.execute("""
            INSERT INTO report_templates (
                template_name, template_type, template_category,
                template_content, version, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (
            template['name'],
            template['type'],
            template['category'],
            content,
            '1.0',
            1
        ))

        print(f"✓ 已导入: {template['name']} ({template['type']})")

    conn.commit()
    conn.close()

    print("\n模板导入完成！")
    return True


if __name__ == '__main__':
    import_templates()
