#!/usr/bin/env python3
"""
删除重复的公式要素：product_word 和 persona_word
（已合并到 identity_tag）
"""
import sys
import os

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

def delete_duplicate_elements():
    with app.app_context():
        # 删除 product_word
        deleted = FormulaElementType.query.filter_by(
            sub_category='nickname_analysis',
            code='product_word'
        ).all()
        for e in deleted:
            print(f"删除: [{e.sub_category}] {e.name} ({e.code})")
            db.session.delete(e)
        
        # 删除 persona_word
        deleted = FormulaElementType.query.filter_by(
            sub_category='nickname_analysis',
            code='persona_word'
        ).all()
        for e in deleted:
            print(f"删除: [{e.sub_category}] {e.name} ({e.code})")
            db.session.delete(e)
        
        db.session.commit()
        print("\n✅ 删除完成")

if __name__ == '__main__':
    delete_duplicate_elements()
