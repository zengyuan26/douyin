"""
数据迁移脚本：将现有 SavedPortrait 和 PublicGeneration 数据迁移到客户系统

此脚本用于将现有的画像和生成记录迁移到新的客户管理架构中。
"""

from models.models import db
from models.customer_models import Customer
from models.public_models import SavedPortrait, PublicGeneration
from datetime import datetime


def get_or_create_default_customer(admin_id=None):
    """
    获取或创建默认客户（用于迁移没有客户归属的数据）

    Args:
        admin_id: 管理员ID（可选）

    Returns:
        Customer: 默认客户对象
    """
    # 尝试查找已有的默认客户
    default_customer = Customer.query.filter_by(customer_name='默认客户').first()

    if default_customer:
        return default_customer

    # 创建默认客户
    import uuid
    default_customer = Customer(
        customer_name='默认客户',
        customer_code=f"C{uuid.uuid4().hex[:8].upper()}",
        admin_id=admin_id,
        client_type='product',
        industry='通用',
        business_description='通过数据迁移自动创建的客户档案',
        status='active',
        geographic_scope='global',
        brand_priority='both',
        primary_language='mandarin',
        primary_goal='traffic',
    )

    db.session.add(default_customer)
    db.session.commit()

    return default_customer


def migrate_existing_portraits():
    """
    将现有的 SavedPortrait 数据迁移到客户系统

    迁移策略：
    1. 为每个有画像但没有 customer_id 的记录创建默认客户
    2. 将画像关联到对应的默认客户
    """
    print("[Migration] 开始迁移 SavedPortrait 数据...")

    # 查找所有没有 customer_id 的画像
    portraits_without_customer = SavedPortrait.query.filter(
        SavedPortrait.customer_id == None
    ).all()

    print(f"[Migration] 找到 {len(portraits_without_customer)} 条没有关联客户的画像")

    if not portraits_without_customer:
        print("[Migration] 没有需要迁移的画像数据")
        return

    # 按用户分组
    from collections import defaultdict
    portraits_by_user = defaultdict(list)
    for portrait in portraits_without_customer:
        portraits_by_user[portrait.user_id].append(portrait)

    # 为每个用户创建或获取一个客户档案
    for user_id, portraits in portraits_by_user.items():
        # 获取第一个画像的行业信息作为客户的行业
        first_portrait = portraits[0]
        industry = first_portrait.industry or '通用'

        # 创建客户档案
        import uuid
        customer = Customer(
            customer_name=f"用户{user_id}_客户",
            customer_code=f"C{uuid.uuid4().hex[:8].upper()}",
            admin_id=None,  # 管理员ID待定
            industry=industry,
            business_description=first_portrait.business_description or '',
            status='active',
        )

        db.session.add(customer)
        db.session.commit()

        # 将该用户的所有画像关联到新客户
        for portrait in portraits:
            portrait.customer_id = customer.id

        db.session.commit()
        print(f"[Migration] 用户 {user_id}: 创建客户 {customer.customer_name}，迁移 {len(portraits)} 条画像")

    print("[Migration] SavedPortrait 数据迁移完成")


def migrate_existing_generations():
    """
    将现有的 PublicGeneration 数据迁移到客户系统

    迁移策略：
    1. 为每个有生成记录但没有 customer_id 的记录关联到对应画像的客户
    2. 如果画像也没有客户，则使用默认客户
    """
    print("[Migration] 开始迁移 PublicGeneration 数据...")

    # 查找所有没有 customer_id 的生成记录
    generations_without_customer = PublicGeneration.query.filter(
        PublicGeneration.customer_id == None
    ).all()

    print(f"[Migration] 找到 {len(generations_without_customer)} 条没有关联客户的生成记录")

    if not generations_without_customer:
        print("[Migration] 没有需要迁移的生成记录数据")
        return

    # 获取默认客户（如果需要）
    default_customer = None

    migrated_count = 0
    for gen in generations_without_customer:
        # 优先从关联的画像获取客户ID
        if gen.portrait_id:
            portrait = SavedPortrait.query.get(gen.portrait_id)
            if portrait and portrait.customer_id:
                gen.customer_id = portrait.customer_id
                migrated_count += 1
                continue

        # 如果画像也没有客户，使用默认客户
        if not default_customer:
            default_customer = get_or_create_default_customer()
            print(f"[Migration] 创建/获取默认客户: {default_customer.customer_name}")

        gen.customer_id = default_customer.id
        migrated_count += 1

    db.session.commit()
    print(f"[Migration] 迁移了 {migrated_count} 条生成记录")
    print("[Migration] PublicGeneration 数据迁移完成")


def migrate_existing_data():
    """执行所有迁移"""
    print("=" * 60)
    print("[Migration] 开始客户系统数据迁移")
    print("=" * 60)

    try:
        migrate_existing_portraits()
        migrate_existing_generations()

        print("=" * 60)
        print("[Migration] 所有迁移完成！")
        print("=" * 60)

        # 输出统计信息
        customer_count = Customer.query.count()
        portrait_with_customer = SavedPortrait.query.filter(
            SavedPortrait.customer_id != None
        ).count()
        portrait_total = SavedPortrait.query.count()
        generation_with_customer = PublicGeneration.query.filter(
            PublicGeneration.customer_id != None
        ).count()
        generation_total = PublicGeneration.query.count()

        print(f"\n[Migration] 统计信息:")
        print(f"  - 客户总数: {customer_count}")
        print(f"  - 画像关联客户: {portrait_with_customer}/{portrait_total}")
        print(f"  - 生成记录关联客户: {generation_with_customer}/{generation_total}")

    except Exception as e:
        print(f"[Migration] 迁移失败: {e}")
        db.session.rollback()
        raise


def rollback_migration():
    """回滚迁移（清除 customer_id 关联）"""
    print("[Migration] 开始回滚迁移...")

    # 清除所有 customer_id
    SavedPortrait.query.update({SavedPortrait.customer_id: None})
    PublicGeneration.query.update({PublicGeneration.customer_id: None})
    db.session.commit()

    # 删除默认客户
    Customer.query.filter_by(customer_name='默认客户').delete()
    db.session.commit()

    print("[Migration] 回滚完成")


if __name__ == '__main__':
    import sys
    import os

    # 添加项目根目录到 Python 路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from app import app

    with app.app_context():
        # 确保表已创建
        db.create_all()

        if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
            rollback_migration()
        else:
            migrate_existing_data()
