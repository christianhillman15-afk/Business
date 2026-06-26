"""client CRM fields + contacts

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-26 18:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('city', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('state', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('service_radius_miles', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('client_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('bot_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('claimed_by', sa.String(length=120), nullable=True))
        batch_op.add_column(
            sa.Column('client_status', sa.String(length=16), nullable=False, server_default='enabled')
        )

    op.create_table(
        'client_contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=True),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_client_contacts_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_client_contacts')),
    )


def downgrade() -> None:
    op.drop_table('client_contacts')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('client_status')
        batch_op.drop_column('claimed_by')
        batch_op.drop_column('bot_notes')
        batch_op.drop_column('client_notes')
        batch_op.drop_column('service_radius_miles')
        batch_op.drop_column('state')
        batch_op.drop_column('city')
