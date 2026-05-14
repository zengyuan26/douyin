"""
客户管理模块 - 数据迁移脚本

将现有的 SavedPortrait 和 PublicGeneration 数据迁移到新的客户系统

使用方法：
    python migrations/migrate_existing_portraits_to_customers.py
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from app import create_app, db
from models.models import User
from models.customer_models import Customer, CustomerActivityLog
from models.public_models import SavedPortrait, PublicGeneration


def migrate_existing_portraits_to_customers():
    """
    将现有的 SavedPortrait 数据迁移到新的客户系统

    策略：
    1. 为每个有画像但没有关联客户的用户创建一个默认客户
    2. 将用户的画像关联到新客户
    3. 将用户的生成记录关联到新客户
    4. 记录迁移日志
    """
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("开始数据迁移...")
        print("=" * 60)

        # 1. 统计现有数据
        print("\n[1] 统计现有数据...")

        # 获取所有有画像的用户
        users_with_portraits = db.session.query(SavedPortrait.user_id).distinct().all()
        user_ids = [u[0] for u in users_with_portraits]

        print(f"  - 有画像的用户数: {len(user_ids)}")

        # 获取已关联客户的用户数
        portraits_with_customer = SavedPortrait.query.filter(
            SavedPortrait.customer_id.isnot(None)
        ).count()
        print(f"  - 已关联客户的画像数: {portraits_with_customer}")

        # 获取未关联客户的画像数
        portraits_without_customer = SavedPortrait.query.filter(
            SavedPortrait.customer_id.is(None)
        ).count()
        print(f"  - 未关联客户的画像数: {portraits_without_customer}")

        # 获取未关联客户的生成记录数
        generations_without_customer = PublicGeneration.query.filter(
            PublicGeneration.customer_id.is(None)
        ).count()
        print(f"  - 未关联客户的生成记录数: {generations_without_customer}")

        # 2. 为未关联客户的用户创建默认客户
        print("\n[2] 为未关联客户的用户创建默认客户...")

        customers_created = 0
        customers_skipped = 0

        for user_id in user_ids:
            # 检查用户是否已有画像关联客户
            has_customer = SavedPortrait.query.filter(
                SavedPortrait.user_id == user_id,
                SavedPortrait.customer_id.isnot(None)
            ).first()

            if has_customer:
                customers_skipped += 1
                continue

            # 获取用户的第一个画像信息
            first_portrait = SavedPortrait.query.filter_by(user_id=user_id).first()

            if not first_portrait:
                continue

            # 获取用户信息
            user = User.query.get(user_id)
            user_name = user.username if user else f"用户{user_id}"

            # 创建默认客户
            customer = Customer(
                customer_name=f"{user_name}_默认客户",
                customer_code=f"AUTO-{user_id:06d}",
                admin_id=None,  # 系统自动创建，无管理员关联
                client_type="both",
                industry=first_portrait.industry or "未分类",
                business_description=first_portrait.business_description or "",
                geographic_scope="regional",
                status="active",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            db.session.add(customer)
            db.session.flush()  # 获取 customer.id

            # 记录活动日志
            log = CustomerActivityLog(
                customer_id=customer.id,
                activity_type="profile_created",
                activity_detail=f"系统自动创建（迁移自用户 {user_name}）",
                operator_id=None
            )
            db.session.add(log)

            customers_created += 1
            print(f"  - 创建客户: {customer.customer_name} (ID: {customer.id})")

            # 3. 更新用户的画像关联客户ID
            print(f"  - 关联画像到客户 {customer.id}...")

            db.session.execute(
                db.text("""
                    UPDATE saved_portraits
                    SET customer_id = :customer_id
                    WHERE user_id = :user_id AND customer_id IS NULL
                """),
                {'customer_id': customer.id, 'user_id': user_id}
            )

            # 4. 更新用户的生成记录关联客户ID
            db.session.execute(
                db.text("""
                    UPDATE public_generations
                    SET customer_id = :customer_id
                    WHERE user_id = :user_id AND customer_id IS NULL
                """),
                {'customer_id': customer.id, 'user_id': user_id}
            )

            # 记录活动日志
            portrait_count = SavedPortrait.query.filter_by(user_id=user_id).count()
            log = CustomerActivityLog(
                customer_id=customer.id,
                activity_type="profile_updated",
                activity_detail=f"关联 {portrait_count} 个画像到客户",
                operator_id=None
            )
            db.session.add(log)

        db.session.commit()

        print(f"\n迁移完成！")
        print(f"  - 新建客户数: {customers_created}")
        print(f"  - 跳过（已有客户关联）: {customers_skipped}")

        # 5. 验证迁移结果
        print("\n[3] 验证迁移结果...")

        portraits_with_customer_after = SavedPortrait.query.filter(
            SavedPortrait.customer_id.isnot(None)
        ).count()
        print(f"  - 已关联客户的画像数: {portraits_with_customer_after}")

        portraits_without_customer_after = SavedPortrait.query.filter(
            SavedPortrait.customer_id.is(None)
        ).count()
        print(f"  - 未关联客户的画像数: {portraits_without_customer_after}")

        generations_with_customer = PublicGeneration.query.filter(
            PublicGeneration.customer_id.isnot(None)
        ).count()
        print(f"  - 已关联客户的生成记录数: {generations_with_customer}")

        total_customers = Customer.query.count()
        print(f"  - 总客户数: {total_customers}")

        print("\n" + "=" * 60)
        print("迁移完成！")
        print("=" * 60)

        return {
            'customers_created': customers_created,
            'customers_skipped': customers_skipped,
            'portraits_with_customer': portraits_with_customer_after,
            'total_customers': total_customers
        }


def rollback_migration():
    """
    回滚迁移（将所有 customer_id 设为 NULL）

    警告：这将移除所有迁移的数据关联，请谨慎使用！
    """
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("警告：即将回滚迁移！")
        print("这将移除所有画像和生成记录的 customer_id 关联！")
        print("=" * 60)

        confirm = input("确认继续？(yes/no): ")
        if confirm.lower() != 'yes':
            print("回滚已取消")
            return

        print("\n[1] 移除画像的 customer_id 关联...")
        result1 = db.session.execute(
            db.text("UPDATE saved_portraits SET customer_id = NULL")
        )
        print(f"  - 更新 {result1.rowcount} 条记录")

        print("\n[2] 移除生成记录的 customer_id 关联...")
        result2 = db.session.execute(
            db.text("UPDATE public_generations SET customer_id = NULL")
        )
        print(f"  - 更新 {result2.rowcount} 条记录")

        print("\n[3] 删除系统自动创建的客户...")
        system_customers = Customer.query.filter(
            Customer.customer_code.like('AUTO-%')
        ).all()
        for c in system_customers:
            print(f"  - 删除客户: {c.customer_name} (ID: {c.id})")
            db.session.delete(c)

        db.session.commit()
        print("\n回滚完成！")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='客户管理数据迁移工具')
    parser.add_argument('--rollback', action='store_true', help='回滚迁移')
    args = parser.parse_args()

    if args.rollback:
        rollback_migration()
    else:
        migrate_existing_portraits_to_customers()
