#!/usr/bin/env python3
"""
查看 bio_analysis 的 identity_tag 要素
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

def show_bio_identity_tag():
    with app.app_context():
        elements = FormulaElementType.query.filter_by(
            sub_category='bio_analysis',
            code='identity_tag'
        ).all()
        
        for e in elements:
            print(f"名称: {e.name}")
            print(f"code: {e.code}")
            print(f"examples: {e.examples}")

if __name__ == '__main__':
    show_bio_identity_tag()
