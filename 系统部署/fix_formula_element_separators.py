#!/usr/bin/env python3
"""
修复公式要素 examples 字段的分隔符统一问题
将各种分隔符（｜ 、 ， 换行）统一为 |
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'douyin_system.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class FormulaElementType(db.Model):
    __tablename__ = 'formula_element_types'
    id = db.Column(db.Integer, primary_key=True)
    sub_category = db.Column(db.String(50))
    name = db.Column(db.String(50))
    code = db.Column(db.String(50))
    description = db.Column(db.Text)
    examples = db.Column(db.Text)
    priority = db.Column(db.Integer)
    is_active = db.Column(db.Boolean)
    usage_tips = db.Column(db.Text)

def fix_formula_element_separators():
    with app.app_context():
        elements = FormulaElementType.query.all()
        fixed_count = 0
        
        for element in elements:
            if not element.examples:
                continue
            
            original = element.examples
            
            # 统一分隔符
            normalized = original
            normalized = normalized.replace('｜', '|')  # 全角竖线
            normalized = normalized.replace('，', '|')  # 全角逗号
            normalized = normalized.replace(',', '|')  # 半角逗号
            normalized = normalized.replace('\n', '|')  # 换行
            normalized = normalized.replace('、', '|')  # 顿号
            normalized = normalized.replace(' ', '')     # 空格
            normalized = normalized.replace('\r', '')   # 回车
            normalized = normalized.replace('\t', '|')  # 制表符
            
            # 合并多个连续的 |
            while '||' in normalized:
                normalized = normalized.replace('||', '|')
            
            # 去除首尾的 |
            normalized = normalized.strip('|')
            
            if normalized != original:
                element.examples = normalized
                fixed_count += 1
                print(f"  修复 [{element.sub_category}] {element.name}:")
                print(f"    原: {original[:80]}...")
                print(f"    新: {normalized[:80]}...")
        
        if fixed_count > 0:
            db.session.commit()
            print(f"\n✅ 成功修复 {fixed_count} 条记录")
        else:
            print("\n✅ 无需修复，数据已是统一格式")

if __name__ == '__main__':
    print("开始修复公式要素分隔符...")
    fix_formula_element_separators()
