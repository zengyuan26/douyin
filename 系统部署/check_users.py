"""查看数据库中的用户"""
from app import app, db
from models.models import User

with app.app_context():
    users = User.query.all()
    print(f"数据库中共有 {len(users)} 个用户:")
    for u in users:
        print(f"  - id={u.id}, username={u.username}, email={u.email}, role={u.role}, is_active={u.is_active}")
