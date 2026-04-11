# -*- coding: utf-8 -*-
"""
迁移：创建内容展示区块配置表

创建 content_section_display_config 表，
用于控制内容详情页各区块的可见性和可复制性。

使用方法：
cd /Volumes/增元/项目/douyin/系统部署
python -m flask db upgrade
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_section_display_config_001'
down_revision = 'add_portrait_weight_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'content_section_display_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('content_type', sa.String(50), nullable=False),
        sa.Column('section_key', sa.String(50), nullable=False),
        sa.Column('section_label', sa.String(200), nullable=False),
        sa.Column('visible_to_client', sa.Boolean(), default=True),
        sa.Column('copyable', sa.Boolean(), default=True),
        sa.Column('client_label', sa.String(200)),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('is_core_section', sa.Boolean(), default=False),
        sa.Column('description', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    # 创建复合索引
    op.create_index(
        'idx_display_type_section',
        'content_section_display_config',
        ['content_type', 'section_key'],
        unique=False
    )


def downgrade():
    op.drop_index('idx_display_type_section', 'content_section_display_config')
    op.drop_table('content_section_display_config')
