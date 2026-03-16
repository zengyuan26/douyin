#!/usr/bin/env python3
"""检查入库的昵称分析规则"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models.models import db, KnowledgeRule

def check_rules():
    app = create_app()
    with app.app_context():
        # 查看所有规则
        rules = KnowledgeRule.query.order_by(KnowledgeRule.id.desc()).limit(10).all()
        
        print(f"共 {KnowledgeRule.query.count()} 条规则\n")
        
        for r in rules:
            print(f"ID: {r.id}")
            print(f"  rule_title: {r.rule_title}")
            print(f"  source_category: {r.source_category}")
            print(f"  source_sub_category: {r.source_sub_category}")
            print(f"  source_dimension: {r.source_dimension}")
            print(f"  dimension_name: {r.dimension_name}")
            print(f"  rule_type: {r.rule_type}")
            print()

if __name__ == '__main__':
    check_rules()
