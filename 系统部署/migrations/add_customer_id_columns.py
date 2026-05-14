"""
迁移脚本：为 saved_portraits 和 public_generations 表添加 customer_id 列
"""

from app import app, db


def run_migration():
    """执行迁移"""
    with app.app_context():
        print("开始迁移：添加 customer_id 列...")

        # 1. 为 saved_portraits 表添加 customer_id 列
        print("1. 检查 saved_portraits 表...")
        result = db.session.execute(
            db.text("PRAGMA table_info(saved_portraits)")
        ).fetchall()
        existing_columns = [row[1] for row in result]

        if 'customer_id' not in existing_columns:
            print("   添加 customer_id 列到 saved_portraits...")
            db.session.execute(
                db.text("ALTER TABLE saved_portraits ADD COLUMN customer_id INTEGER REFERENCES customers(id)")
            )
            db.session.commit()
            print("   ✓ saved_portraits.customer_id 添加成功")
        else:
            print("   ✓ saved_portraits.customer_id 已存在")

        # 2. 为 public_generations 表添加 customer_id 列
        print("2. 检查 public_generations 表...")
        result = db.session.execute(
            db.text("PRAGMA table_info(public_generations)")
        ).fetchall()
        existing_columns = [row[1] for row in result]

        if 'customer_id' not in existing_columns:
            print("   添加 customer_id 列到 public_generations...")
            db.session.execute(
                db.text("ALTER TABLE public_generations ADD COLUMN customer_id INTEGER REFERENCES customers(id)")
            )
            db.session.commit()
            print("   ✓ public_generations.customer_id 添加成功")
        else:
            print("   ✓ public_generations.customer_id 已存在")

        print("\n迁移完成！")


if __name__ == '__main__':
    run_migration()
