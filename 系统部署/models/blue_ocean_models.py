"""
数据库模型更新
新增 BlueOceanAnalysis 和 OperationPlan 表
"""

from datetime import datetime


def init_blue_ocean_models(db):
    """
    初始化蓝海分析相关模型

    使用方式：
    from models.models import db
    from models.blue_ocean_models import init_blue_ocean_models

    init_blue_ocean_models(db)  # 在 app 初始化时调用
    """

    # 动态创建表（如果不存在）
    db.create_all()
