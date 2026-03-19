#!/usr/bin/env python3
"""
查看当前公式要素
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
    priority = db.Column(db.Integer)

def list_elements():
    with app.app_context():
        elements = FormulaElementType.query.order_by(
            FormulaElementType.sub_category,
            FormulaElementType.priority
        ).all()
        
        current_cat = None
        for e in elements:
            if e.sub_category != current_cat:
                current_cat = e.sub_category
                print(f"\n=== {e.sub_category} ===")
            print(f"  [{e.priority}] {e.name} ({e.code})")

if __name__ == '__main__':
    list_elements()
