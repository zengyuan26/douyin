"""人群画像模块数据库迁移

Revision ID: persona_module_001
Revises: 
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'persona_module_001'
down_revision = None  # 根据实际情况调整
branch_labels = None
depends_on = None


def upgrade():
    # ========== 人群画像会话表 ==========
    op.create_table('persona_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100)),
        sa.Column('industry', sa.String(length=50)),
        sa.Column('business_type', sa.String(length=20)),
        sa.Column('buyer_equals_user', sa.Boolean(), default=True),
        sa.Column('status', sa.String(length=20), default='draft'),
        sa.Column('input_data', sa.JSON()),
        sa.Column('user_problems', sa.JSON()),
        sa.Column('buyer_concerns', sa.JSON()),
        sa.Column('portraits', sa.JSON()),
        sa.Column('portrait_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # ========== 使用方问题表 ==========
    op.create_table('persona_user_problems',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('specific_symptoms', sa.Text()),
        sa.Column('severity', sa.String(length=20)),
        sa.Column('user_awareness', sa.String(length=20)),
        sa.Column('trigger_scenario', sa.Text()),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.ForeignKeyConstraint(['session_id'], ['persona_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # ========== 付费方顾虑表 ==========
    op.create_table('persona_buyer_concerns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('concern_type', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('estimated_ratio', sa.String(length=20)),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.ForeignKeyConstraint(['session_id'], ['persona_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # ========== 人群画像表 ==========
    op.create_table('persona_portraits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('problem_id', sa.Integer()),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('batch_number', sa.Integer(), default=1),
        sa.Column('user_description', sa.Text()),
        sa.Column('user_core_problem', sa.Text()),
        sa.Column('user_specific_symptoms', sa.Text()),
        sa.Column('user_pain_level', sa.String(length=20)),
        sa.Column('buyer_description', sa.Text()),
        sa.Column('buyer_core_problem', sa.Text()),
        sa.Column('buyer_concerns', sa.JSON()),
        sa.Column('user_journey', sa.Text()),
        sa.Column('content_topics', sa.JSON()),
        sa.Column('search_keywords', sa.JSON()),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow),
        sa.ForeignKeyConstraint(['session_id'], ['persona_sessions.id'], ),
        sa.ForeignKeyConstraint(['problem_id'], ['persona_user_problems.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('persona_portraits')
    op.drop_table('persona_buyer_concerns')
    op.drop_table('persona_user_problems')
    op.drop_table('persona_sessions')
