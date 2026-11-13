"""orders: invoice request from the tracking page

Revision ID: 0019_order_invoice_request
Revises: 0018_collect_operation_id
Create Date: 2026-11-12 21:30:00

Purely additive: `orders.invoice_request` (JSON text {name, cuit, email}; NULL = not requested).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0019_order_invoice_request'
down_revision: Union[str, Sequence[str], None] = '0018_collect_operation_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('invoice_request', sa.String(length=400), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('invoice_request')
