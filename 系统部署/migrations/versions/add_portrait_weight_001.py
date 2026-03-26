# -*- coding: utf-8 -*-
"""
迁移：为画像维度添加权重字段

此迁移为 analysis_dimensions 表添加 weight 字段，
用于 LLM 画像分析时的权重配置（满分10分）。

使用方法：
cd /Volumes/增元/项目/douyin/系统部署
flask db upgrade
或者
python -m flask db upgrade
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_portrait_weight_001'
down_revision = 'persona_module_001'  # 假设上一个迁移是 persona_module_001
branch_labels = None
depends_on = None


def upgrade():
    # 添加 weight 列，默认值为 1.0
    op.add_column(
        'analysis_dimensions',
        sa.Column('weight', sa.Float(), nullable=True, server_default='1.0')
    )
    
    # 为超级定位维度的子分类设置默认权重
    # 注意：这些权重会在迁移脚本运行后通过 init_portrait_dimensions.py 更新
    # 这里只是确保新列被添加


def downgrade():
    op.drop_column('analysis_dimensions', 'weight')
