"""
更新知识库专家昵称脚本
将"百科博士"改为"伊森·亨特"
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db, Expert


def update_knowledge_expert():
    """更新知识库专家配置"""
    with app.app_context():
        # 查找知识库专家
        expert = Expert.query.filter_by(slug='knowledge').first()
        
        if expert:
            old_nickname = expert.nickname
            expert.nickname = '伊森·亨特'
            expert.avatar_url = '/static/images/avatars/expert_ethan_avatar.png'
            db.session.commit()
            print(f"✓ 已将知识库专家昵称从'{old_nickname}'更新为'{expert.nickname}'")
            print(f"✓ 已更新头像URL为: {expert.avatar_url}")
        else:
            print("✗ 未找到知识库专家")


if __name__ == '__main__':
    update_knowledge_expert()
