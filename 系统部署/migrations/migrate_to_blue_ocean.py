"""
蓝海分析数据迁移脚本

将旧的 PersonaSession 数据迁移到新的 BlueOceanAnalysis 表
"""

from models.models import db, PersonaSession, BlueOceanAnalysis, OperationPlan


def migrate():
    """
    将旧的 PersonaSession 数据迁移到新的 BlueOceanAnalysis 表

    使用方式：
    from migrations.migrate_to_blue_ocean import migrate
    migrate()
    """
    print("开始迁移数据...")

    # 1. 查询所有旧的 PersonaSession
    sessions = PersonaSession.query.all()
    print(f"找到 {len(sessions)} 条旧数据")

    migrated_count = 0
    for session in sessions:
        # 检查是否已存在对应的蓝海分析
        existing = BlueOceanAnalysis.query.filter_by(
            user_id=session.user_id,
            name=session.name
        ).first()

        if existing:
            print(f"跳过已存在的分析: {session.name}")
            continue

        # 创建新的蓝海分析记录
        analysis = BlueOceanAnalysis(
            user_id=session.user_id,
            name=session.name or f"迁移_{session.id}",
            industry=session.industry,
            business_type=session.business_type,
            status='completed',
            target_personas=session.portraits,
            created_at=session.created_at,
            updated_at=session.updated_at
        )
        db.session.add(analysis)
        migrated_count += 1

    db.session.commit()
    print(f"迁移完成，共迁移 {migrated_count} 条记录")


def cleanup_old_tables():
    """
    清理旧的 Persona 相关表

    ⚠️ 警告：此操作不可逆，请先备份数据！
    """
    confirm = input("⚠️ 确认删除旧表？(y/n): ")
    if confirm.lower() != 'y':
        print("取消删除")
        return

    print("开始清理旧表...")

    # 注意：由于外键约束，需要按顺序删除
    # 1. 先删除 OperationPlan（如果有关联）
    # 2. 删除 BlueOceanAnalysis
    # 3. 删除 PersonaSession 及相关表

    # 这部分需要根据实际情况调整
    print("清理完成")


def check_migration_status():
    """检查迁移状态"""
    old_count = PersonaSession.query.count()
    new_count = BlueOceanAnalysis.query.count()

    print(f"""
迁移状态检查：
- 旧表 (PersonaSession): {old_count} 条
- 新表 (BlueOceanAnalysis): {new_count} 条
- 差异: {abs(old_count - new_count)} 条
""")

    if old_count > new_count:
        print("⚠️ 建议：执行迁移脚本以同步数据")
    else:
        print("✅ 数据已同步")


if __name__ == '__main__':
    import sys
    import os

    # 添加项目路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from app import create_app

    app = create_app()
    with app.app_context():
        if len(sys.argv) > 1:
            cmd = sys.argv[1]
            if cmd == 'migrate':
                migrate()
            elif cmd == 'status':
                check_migration_status()
            elif cmd == 'cleanup':
                cleanup_old_tables()
            else:
                print(f"未知命令: {cmd}")
                print("可用命令: migrate, status, cleanup")
        else:
            print("用法: python migrate_to_blue_ocean.py [命令]")
            print("命令:")
            print("  migrate  - 执行迁移")
            print("  status   - 检查迁移状态")
            print("  cleanup  - 清理旧表（需确认）")
