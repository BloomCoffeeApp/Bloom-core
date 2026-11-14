"""partial receipts of purchase orders and the delivery-note photo

Revision ID: 0028_partial_receipts
Revises: 0027_session_devices
Create Date: 2026-11-14 16:00:00

Purely additive: `purchase_order_items.received_qty` (what already arrived of each ordered line; the order stays
«partial» until nothing is pending) and `purchases.remito_path` (photo of the remito, outside the public uploads).
Existing orders keep working: a received order is treated as fully received (see the UPDATE below).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0028_partial_receipts'
down_revision: Union[str, Sequence[str], None] = '0027_session_devices'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('purchase_order_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('received_qty', sa.Float(), server_default='0', nullable=False))
    with op.batch_alter_table('purchases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('remito_path', sa.String(length=40), nullable=True))
    # Orders already received before this migration arrived in full (the old behaviour closed them on one receipt).
    op.execute(
        "UPDATE purchase_order_items SET received_qty = qty "
        "WHERE order_id IN (SELECT id FROM purchase_orders WHERE status = 'received')"
    )


def downgrade() -> None:
    with op.batch_alter_table('purchases', schema=None) as batch_op:
        batch_op.drop_column('remito_path')
    with op.batch_alter_table('purchase_order_items', schema=None) as batch_op:
        batch_op.drop_column('received_qty')
