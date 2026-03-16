#!/usr/bin/env python3
"""修复已入库的规则，添加 source_category"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models.models import db, KnowledgeRule

def fix_rules():
    app = create_app()
    with app.app_context():
        # 修复 source_category 为空的规则
        rules = KnowledgeRule.query.filter(
            KnowledgeRule.source_category.is_(None)
        ).all()
        
        print(f"找到 {len(rules)} 条需要修复的规则")
        
        for r in rules:
            # 根据 source_sub_category 判断一级分类
            if r.source_sub_category in ['nickname_analysis', 'bio_analysis', 'account_positioning', 'market_analysis']:
                r.source_category = 'account'
            elif r.source_sub_category in ['title', 'hook', 'ending', 'visual_design', 'content_body', 'topic', 'structure', 'commercial', 'psychology', 'emotion']:
                r.source_category = 'content'
            else:
                r.source_category = 'methodology'
            
            print(f"  修复 ID {r.id}: source_category = {r.source_category}")
        
        db.session.commit()
        print("\n✅ 修复完成！")

if __name__ == '__main__':
    fix_rules()
