"""optional tips

Revision ID: 0021_tips
Revises: 0020_collect_diner
Create Date: 2026-11-12 22:30:00

Purely additive: `sales.tip_cents` and `collect_charges.tip_cents` (optional tip on top of the total), default 0.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0021_tips'
down_revision: Union[str, Sequence[str], None] = '0020_collect_diner'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tip_cents', sa.Integer(), server_default='0', nullable=False))
    with op.batch_alter_table('collect_charges', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tip_cents', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('collect_charges', schema=None) as batch_op:
        batch_op.drop_column('tip_cents')
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.drop_column('tip_cents')
