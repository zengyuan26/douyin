#!/usr/bin/env python3
"""
更新 identity_tag 要素，添加更多组合例子
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
    examples = db.Column(db.Text)

def update_identity_tag():
    with app.app_context():
        elements = FormulaElementType.query.filter_by(
            sub_category='nickname_analysis',
            code='identity_tag'
        ).all()
        
        # 添加更多组合例子
        new_examples = [
            # 姓氏+称呼组合
            "芬哥|黄姐|王哥|张姐|李哥|赵姐|刘哥|陈姐|杨哥|周姐",
            "吴姐|郑姐|孙哥|马姐|朱哥|胡姐|郭哥|林姐|何哥|高姐",
            # 常见昵称
            "妈|姐|哥|姑娘|美女|帅哥|大叔|阿姨|老师|医生|师傅",
            # 虚拟人设
            "魔女|西施|侠客|公主|王子|将军|仙女|仙子|女王|男神",
            # 网名后缀
            "先生|酱|阿X|小X|老X|阿X|小X|老X|帝|仙|神|侠|圣"
        ]
        
        combined = "|".join(new_examples)
        
        for e in elements:
            print(f"更新: {e.name}")
            print(f"旧: {e.examples[:100]}...")
            e.examples = combined
            print(f"新: {e.examples[:100]}...")
        
        db.session.commit()
        print("\n✅ 更新完成")

if __name__ == '__main__':
    update_identity_tag()
