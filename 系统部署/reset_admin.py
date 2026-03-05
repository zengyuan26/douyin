"""
重置管理员密码脚本
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db, User
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

def reset_admin():
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if admin:
            admin.password_hash = bcrypt.generate_password_hash('aaa111').decode('utf-8')
            admin.is_active = True
            db.session.commit()
            print("✅ 管理员密码已重置为: aaa111")
        else:
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=bcrypt.generate_password_hash('aaa111').decode('utf-8'),
                role='super_admin',
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ 管理员账号已创建: admin / aaa111")

if __name__ == '__main__':
    reset_admin()
