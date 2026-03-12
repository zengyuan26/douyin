#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
规则库迁移脚本
将 Markdown 文件中的规则迁移到数据库的统一规则表中
"""
import os
import sys
import re

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db, KnowledgeRule


# Markdown 规则文件配置
RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'skills', 'knowledge-base', '规则'
)

RULE_FILES = {
    'keywords': '关键词库_规则模板.md',
    'topic': '选题库_规则模板.md',
    'template': '内容模板_规则模板.md',
    'operation': '运营规划_规则模板.md',
    'market': '市场分析_规则模板.md'
}

CATEGORY_NAMES = {
    'keywords': '关键词库',
    'topic': '选题库',
    'template': '内容模板',
    'operation': '运营规划',
    'market': '市场分析'
}


def parse_markdown_file(filepath, category):
    """解析 Markdown 文件，提取规则"""
    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    rules = []

    # 使用正则表达式分割章节
    # 匹配 ## 或 ### 标题
    sections = re.split(r'^(#{2,3})\s+(.+)$', content, flags=re.MULTILINE)

    current_rule = None

    for i, section in enumerate(sections):
        if not section.strip():
            continue

        # 检查是否是标题行
        if section.startswith('##') or section.startswith('###'):
            # 保存前一个规则
            if current_rule and current_rule.get('content'):
                rules.append(current_rule)

            # 提取标题作为规则标题
            title = section.replace('#', '').strip()
            current_rule = {
                'title': title,
                'content': '',
                'category': category
            }
        else:
            # 内容行
            if current_rule:
                current_rule['content'] += section + '\n'

    # 保存最后一个规则
    if current_rule and current_rule.get('content'):
        rules.append(current_rule)

    # 清理内容
    for rule in rules:
        # 生成摘要
        content = rule['content'].strip()
        # 移除表格符号，简化内容
        content = re.sub(r'\|', ' ', content)
        content = re.sub(r'[-]+', '', content)
        content = re.sub(r'\n{3,}', '\n\n', content)
        rule['content'] = content.strip()

        # 生成摘要
        summary = content[:200] + '...' if len(content) > 200 else content
        rule['summary'] = summary.replace('\n', ' ').strip()

    return rules


def migrate_rules():
    """执行迁移"""
    with app.app_context():
        # 检查是否已有数据
        existing_count = KnowledgeRule.query.count()
        if existing_count > 0:
            print(f"数据库中已有 {existing_count} 条规则。")
            confirm = input("是否清空现有数据并重新导入？(y/n): ")
            if confirm.lower() != 'y':
                print("取消迁移。")
                return

            # 清空现有规则
            KnowledgeRule.query.delete()
            db.session.commit()
            print("已清空现有规则。")

        total_migrated = 0

        for category, filename in RULE_FILES.items():
            filepath = os.path.join(RULES_DIR, filename)
            print(f"\n处理文件: {filename}")

            rules = parse_markdown_file(filepath, category)

            for rule in rules:
                if not rule.get('content'):
                    continue

                knowledge_rule = KnowledgeRule(
                    category=category,
                    rule_title=rule['title'],
                    rule_content=rule['content'],
                    rule_type='dimension',
                    source_dimension='',
                    status='active'
                )
                db.session.add(knowledge_rule)
                total_migrated += 1

            print(f"  - 导入 {len(rules)} 条规则到分类: {CATEGORY_NAMES.get(category, category)}")

        db.session.commit()
        print(f"\n迁移完成！共导入 {total_migrated} 条规则。")


def backup_markdown_files():
    """备份 Markdown 文件"""
    backup_dir = os.path.join(RULES_DIR, 'backup')
    os.makedirs(backup_dir, exist_ok=True)

    import shutil
    from datetime import datetime

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    for category, filename in RULE_FILES.items():
        src = os.path.join(RULES_DIR, filename)
        if os.path.exists(src):
            dst = os.path.join(backup_dir, f"{filename}.{timestamp}")
            shutil.copy2(src, dst)
            print(f"已备份: {filename} -> {os.path.basename(dst)}")


def delete_markdown_files():
    """删除 Markdown 规则文件"""
    confirm = input("\n确定要删除 Markdown 规则文件吗？此操作不可恢复！(y/n): ")
    if confirm.lower() != 'y':
        print("取消删除。")
        return

    for category, filename in RULE_FILES.items():
        filepath = os.path.join(RULES_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"已删除: {filename}")

    print("\nMarkdown 规则文件已删除。")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='规则库迁移脚本')
    parser.add_argument('--migrate', action='store_true', help='执行迁移')
    parser.add_argument('--backup', action='store_true', help='备份 Markdown 文件')
    parser.add_argument('--delete', action='store_true', help='删除 Markdown 文件')

    args = parser.parse_args()

    if args.migrate:
        migrate_rules()

    if args.backup:
        backup_markdown_files()

    if args.delete:
        delete_markdown_files()

    if not (args.migrate or args.backup or args.delete):
        print("请指定操作：")
        print("  --migrate  : 执行迁移（Markdown -> 数据库）")
        print("  --backup   : 备份 Markdown 文件")
        print("  --delete   : 删除 Markdown 文件")
        print("\n示例：")
        print("  python migrate_rules.py --migrate  # 执行迁移")
        print("  python migrate_rules.py --backup   # 备份文件")
