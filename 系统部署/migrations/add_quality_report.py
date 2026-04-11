"""添加 quality_report 字段到 public_generations 表

Revision ID: add_quality_report
Revises: 
Create Date: 2026-04-11 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_quality_report'
down_revision = None  # 请根据实际版本调整
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('public_generations', sa.Column('quality_report', sa.JSON, nullable=True))


def downgrade():
    op.drop_column('public_generations', 'quality_report')
