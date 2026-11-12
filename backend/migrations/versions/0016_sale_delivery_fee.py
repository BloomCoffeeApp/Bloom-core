"""sale delivery fee

Revision ID: 0016_sale_delivery_fee
Revises: 0015_collect_payments
Create Date: 2026-11-12 12:00:00

Purely additive: `sales.delivery_fee_cents` (delivery charge, adds to total_cents), default 0.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0016_sale_delivery_fee'
down_revision: Union[str, Sequence[str], None] = '0015_collect_payments'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('delivery_fee_cents', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.drop_column('delivery_fee_cents')
