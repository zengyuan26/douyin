"""
迁移脚本：创建客户管理表 (customers)

此迁移将创建客户管理表，并将现有的 SavedPortrait 和 PublicGeneration 表关联到客户。
"""

from models.models import db
from models.customer_models import Customer


def upgrade():
    """执行迁移"""
    print("[Migration] 创建 customers 表...")

    # 创建 customers 表
    db.create_all(Customer.__table__)

    print("[Migration] customers 表创建成功")
    print("[Migration] 迁移完成！")


def downgrade():
    """回滚迁移"""
    print("[Migration] 删除 customers 表...")

    db.drop_table('customers')

    print("[Migration] customers 表已删除")
    print("[Migration] 回滚完成！")


if __name__ == '__main__':
    # 导入 app 以获取 db 实例
    import sys
    import os

    # 添加项目根目录到 Python 路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from app import app

    with app.app_context():
        upgrade()
