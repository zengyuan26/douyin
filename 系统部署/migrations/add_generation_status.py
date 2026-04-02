"""
添加词库生成状态字段

Revision ID: add_generation_status
Revises: add_portrait_save_and_quota
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_generation_status'
down_revision = 'add_portrait_save_and_quota'
branch_labels = None
depends_on = None


def upgrade():
    # 检查列是否已存在
    conn = op.get_bind()
    inspector = sa.inspector.from_engine(conn)
    columns = [c['name'] for c in inspector.get_columns('saved_portraits')]

    if 'generation_status' not in columns:
        op.add_column('saved_portraits',
            sa.Column('generation_status', sa.String(20), nullable=True, server_default='pending'))

    if 'generation_error' not in columns:
        op.add_column('saved_portraits',
            sa.Column('generation_error', sa.Text, nullable=True))


def downgrade():
    if op.get_context().bind.dialect.name == 'sqlite':
        # SQLite 不支持 DROP COLUMN，改用替代方式
        pass
    else:
        op.drop_column('saved_portraits', 'generation_error')
        op.drop_column('saved_portraits', 'generation_status')
