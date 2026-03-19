"""重置 admin 密码"""
from app import app, db
from models.models import User
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

with app.app_context():
    user = User.query.filter_by(username='admin').first()
    if user:
        # 设置新密码
        new_password = 'admin123'
        user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        db.session.commit()
        print(f"✓ 用户 {user.username} 的密码已重置为: {new_password}")
    else:
        print("用户不存在")
