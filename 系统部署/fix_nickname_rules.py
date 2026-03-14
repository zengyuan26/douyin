#!/usr/bin/env python3
"""
修复规则库中的昵称公式问题：
1. 清理包含通用模板公式的垃圾数据
2. 修复 source_category 为空的记录
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from models.models import KnowledgeRule

app = create_app()

# 通用模板公式关键词（用于识别垃圾数据）
GARBAGE_KEYWORDS = [
    '{人设标签}',
    '{业务词}',
    '{情感词}',
    '根据该昵称的实际构成元素',
    '总结出一个可复用的昵称设计公式',
    '例如：',
    '{标签1}+{标签2}',
    # 看起来像模板的公式
    'AI(前沿科技)',  # 模板示例，不是真实昵称
    '红发(视觉特征)',  # 模板示例
    '魔女(角色定位)',  # 模板示例
]

# 二级分类到一级分类的映射
SUB_CAT_TO_CATEGORY = {
    'nickname_analysis': 'account',
    'bio_analysis': 'account',
    'account_positioning': 'account',
    'market_analysis': 'account',
    'keyword_library': 'account',
    'operation_planning': 'account',
    'title': 'content',
    'hook': 'content',
    'ending': 'content',
    'visual_design': 'content',
    'content_body': 'content',
    'topic': 'content',
    'structure': 'content',
    'commercial': 'content',
    'psychology': 'content',
    'emotion': 'content',
    'applicable_audience': 'methodology',
    'applicable_scenario': 'methodology',
}


def is_garbage_rule(rule):
    """检查是否是垃圾规则（包含通用模板）"""
    if not rule.rule_content:
        return False
    
    content = rule.rule_content.lower()
    title = (rule.rule_title or '').lower()
    
    # 检查是否包含通用模板关键词
    for keyword in GARBAGE_KEYWORDS:
        if keyword.lower() in content or keyword.lower() in title:
            return True
    
    # 检查标题是否只包含"昵称："而没有具体内容
    if rule.rule_title:
        title = rule.rule_title.strip()
        if title.startswith('昵称：') and len(title) < 20:
            return True
    
    # 检查是否是第一条模板数据（AI+红发+魔女）
    if rule.rule_title and 'AI(前沿科技)' in rule.rule_title:
        return True
    
    return False


def fix_rules():
    """修复规则数据"""
    with app.app_context():
        # 1. 查找并删除垃圾规则
        print("=" * 50)
        print("步骤1: 清理垃圾数据")
        print("=" * 50)
        
        all_rules = KnowledgeRule.query.all()
        garbage_rules = []
        
        for rule in all_rules:
            if is_garbage_rule(rule):
                garbage_rules.append(rule)
        
        print(f"找到 {len(garbage_rules)} 条垃圾规则")
        
        for rule in garbage_rules:
            print(f"  - 删除: {rule.rule_title}")
            db.session.delete(rule)
        
        if garbage_rules:
            db.session.commit()
            print(f"已删除 {len(garbage_rules)} 条垃圾规则")
        
        # 2. 修复 source_category 为空的记录
        print("\n" + "=" * 50)
        print("步骤2: 修复 source_category")
        print("=" * 50)
        
        # 查找 source_category 为空的记录
        null_category_rules = KnowledgeRule.query.filter(
            KnowledgeRule.source_category.is_(None)
        ).all()
        
        print(f"找到 {len(null_category_rules)} 条 source_category 为空的规则")
        
        fixed_count = 0
        for rule in null_category_rules:
            sub_cat = rule.source_sub_category
            if sub_cat and sub_cat in SUB_CAT_TO_CATEGORY:
                old_category = rule.source_category
                rule.source_category = SUB_CAT_TO_CATEGORY[sub_cat]
                fixed_count += 1
                print(f"  - 修复: {rule.rule_title} (source_category: {old_category} -> {rule.source_category})")
        
        if fixed_count > 0:
            db.session.commit()
            print(f"\n已修复 {fixed_count} 条规则的 source_category")
        
        # 3. 显示修复后的统计
        print("\n" + "=" * 50)
        print("步骤3: 修复后的统计")
        print("=" * 50)
        
        # 按 source_sub_category 统计
        from sqlalchemy import func
        stats = db.session.query(
            KnowledgeRule.source_sub_category,
            func.count(KnowledgeRule.id).label('count')
        ).filter(
            KnowledgeRule.status == 'active'
        ).group_by(KnowledgeRule.source_sub_category).all()
        
        print("\n按二级分类统计:")
        for sub_cat, count in stats:
            print(f"  - {sub_cat}: {count} 条")
        
        # 按 source_category 统计
        cat_stats = db.session.query(
            KnowledgeRule.source_category,
            func.count(KnowledgeRule.id).label('count')
        ).filter(
            KnowledgeRule.status == 'active'
        ).group_by(KnowledgeRule.source_category).all()
        
        print("\n按一级分类统计:")
        for cat, count in cat_stats:
            print(f"  - {cat}: {count} 条")
        
        # 检查还有多少 nickname_analysis 的规则
        nickname_rules = KnowledgeRule.query.filter(
            KnowledgeRule.source_sub_category == 'nickname_analysis',
            KnowledgeRule.status == 'active'
        ).all()
        
        print(f"\n昵称公式总数: {len(nickname_rules)} 条")
        if nickname_rules:
            print("最新入库的5条:")
            for rule in nickname_rules[:5]:
                print(f"  - {rule.rule_title}")
        
        print("\n" + "=" * 50)
        print("修复完成!")
        print("=" * 50)


if __name__ == '__main__':
    fix_rules()
