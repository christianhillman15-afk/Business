"""custom responses (response generator)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-26 19:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'custom_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('post_content', sa.Text(), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=True),
        sa.Column('reply', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_custom_responses_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_custom_responses')),
    )
    op.create_index(
        op.f('ix_custom_responses_user_id'), 'custom_responses', ['user_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_custom_responses_user_id'), table_name='custom_responses')
    op.drop_table('custom_responses')
