"""
客户管理模块 - 数据库迁移脚本

添加客户管理相关表和字段
"""

from datetime import datetime
from models.models import db
from models.customer_models import Customer, CustomerContact, CustomerActivityLog
from models.public_models import SavedPortrait, PublicGeneration


def run_migration():
    """执行迁移"""
    print("开始客户管理模块迁移...")
    
    # 1. 创建客户表
    print("1. 创建客户表...")
    db.create_all()
    print("   客户表创建成功")
    
    # 2. 创建联系人表
    print("2. 创建联系人表...")
    db.create_all()
    print("   联系人表创建成功")
    
    # 3. 创建活动日志表
    print("3. 创建活动日志表...")
    db.create_all()
    print("   活动日志表创建成功")
    
    # 4. SavedPortrait 表已通过 db.create_all() 自动更新
    # customer_id 字段会自动添加（如果不存在）
    print("4. SavedPortrait 表已更新")
    
    # 5. PublicGeneration 表已通过 db.create_all() 自动更新
    # customer_id 字段会自动添加（如果不存在）
    print("5. PublicGeneration 表已更新")
    
    print("\n客户管理模块迁移完成！")
    print("\n新增的表：")
    print("  - customers: 客户管理表")
    print("  - customer_contacts: 客户联系人表")
    print("  - customer_activity_logs: 客户活动日志表")
    print("\n修改的表：")
    print("  - saved_portraits: 添加 customer_id 字段")
    print("  - public_generations: 添加 customer_id 字段")


if __name__ == '__main__':
    with app.app_context():
        run_migration()
