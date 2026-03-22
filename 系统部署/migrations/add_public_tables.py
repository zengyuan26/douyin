# -*- coding: utf-8 -*-
"""
公开平台数据库迁移脚本

运行方式：
python migrations/add_public_tables.py

或从应用目录运行：
python -c "from migrations.add_public_tables import run_migration; run_migration()"
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db


def run_migration():
    """执行数据库迁移"""
    print("[Migration] 开始数据库迁移...")

    with app.app_context():
        try:
            # 创建所有表
            db.create_all()
            print("[Migration] 数据库表创建完成")

            # 初始化预设数据
            try:
                from services.init_public_data import init_preset_data
                init_preset_data()
                print("[Migration] 预设数据初始化完成")
            except Exception as e:
                print(f"[Migration] 预设数据初始化失败: {e}")

            print("[Migration] 迁移完成!")
            return True

        except Exception as e:
            print(f"[Migration] 迁移失败: {e}")
            db.session.rollback()
            return False


def add_pending_industry_table():
    """添加待处理行业表（如果模型已定义但表不存在）"""
    try:
        from models.public_models import PendingIndustry
        db.create_all(PendingIndustry.__table__)
        print("[Migration] 待处理行业表已添加")
    except ImportError:
        print("[Migration] PendingIndustry 模型未定义，跳过")


def add_llm_call_log_indexes():
    """为 LLM 调用日志表添加索引"""
    from models.public_models import PublicLLMCallLog

    # 检查表是否存在
    conn = db.engine.connect()
    try:
        result = conn.execute(db.text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='public_llm_call_logs'"
        ))
        if not result.fetchone():
            db.create_all(PublicLLMCallLog.__table__)
            print("[Migration] LLM 调用日志表已创建")
    except Exception:
        pass
    finally:
        conn.close()


def add_clients_source_fields():
    """为 clients 表添加 source_type 和 public_user_id 字段"""
    conn = db.engine.connect()

    try:
        # 检查 source_type 字段是否存在
        result = conn.execute(db.text("PRAGMA table_info(clients)"))
        columns = [row[1] for row in result.fetchall()]

        if 'source_type' not in columns:
            conn.execute(db.text(
                "ALTER TABLE clients ADD COLUMN source_type VARCHAR(20) DEFAULT 'channel'"
            ))
            print("[Migration] clients.source_type 字段已添加")

        if 'public_user_id' not in columns:
            conn.execute(db.text(
                "ALTER TABLE clients ADD COLUMN public_user_id INTEGER"
            ))
            print("[Migration] clients.public_user_id 字段已添加")

    except Exception as e:
        print(f"[Migration] 添加 clients 表字段失败: {e}")
    finally:
        conn.close()


def add_pending_industry_model():
    """添加 PendingIndustry 模型到 public_models.py"""

    # 检查模型是否已存在
    try:
        from models.public_models import PendingIndustry
        print("[Migration] PendingIndustry 模型已存在")
        return
    except ImportError:
        pass

    # 读取现有文件
    models_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'models', 'public_models.py'
    )

    with open(models_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否已添加 PendingIndustry
    if 'class PendingIndustry' in content:
        print("[Migration] PendingIndustry 类已存在")
        return

    # 添加 PendingIndustry 模型代码
    model_code = '''

# =============================================================================
# 四、待处理行业队列
# =============================================================================

class PendingIndustry(db.Model):
    """待处理行业队列"""
    __tablename__ = 'pending_industries'
    __table_args__ = (
        db.Index('idx_pending_status', 'status'),
        db.Index('idx_pending_created', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    industry_name = db.Column(db.String(50), nullable=False)  # 用户输入的行业名称
    matched_industry = db.Column(db.String(50))  # AI 匹配到的行业

    # 统计信息
    source_count = db.Column(db.Integer, default=1)  # 来源数量
    profile_summary = db.Column(db.Text)  # 业务摘要（AI 提取）
    sample_descriptions = db.Column(db.JSON)  # 样本描述列表

    # 状态：pending/approved/queued/processing/completed/rejected
    status = db.Column(db.String(20), default='pending')
    priority = db.Column(db.Integer, default=0)

    # 审核信息
    approved_by = db.Column(db.Integer)
    approved_at = db.Column(db.DateTime)
    reject_reason = db.Column(db.Text)

    # 处理信息
    processed_at = db.Column(db.DateTime)
    processing_result = db.Column(db.JSON)  # 处理结果（关键词、选题等）

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

'''

    # 在文件末尾添加模型代码
    with open(models_file, 'a', encoding='utf-8') as f:
        f.write(model_code)

    print("[Migration] PendingIndustry 模型已添加")


if __name__ == '__main__':
    run_migration()
