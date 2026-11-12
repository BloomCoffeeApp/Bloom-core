"""online orders (take away / delivery from the online menu): customer, address, payment and timeline
columns on orders; address on customers

Revision ID: 0009_online_orders
Revises: 0008_drink_guide_extras
Create Date: 2026-11-06 12:00:00

Purely additive. The order statuses are not renamed (the existing codes keep their meaning, see
services/orders.py FLOWS): the new codes (accepted, awaiting_pay, paid, dispatched, rejected,
expired) are only used by online orders, and table orders become `paid` when their tab is charged.
Existing rows get NULL / 0 / false, so every current flow behaves exactly as before.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0009_online_orders'
down_revision: Union[str, Sequence[str], None] = '0008_drink_guide_extras'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('customer_name', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('customer_phone', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('address', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('address_ref', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('delivery_zone', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('delivery_fee_cents', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('total_cents', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('payment_method', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('payment_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('refunded_cents', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('eta_minutes', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('accepted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('paid_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('dispatched_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('refunded_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('online_ref', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('tracking_url', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('sync_pending', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_foreign_key(batch_op.f('fk_orders_customer_id_customers'), 'customers', ['customer_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_orders_customer_id'), ['customer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_online_ref'), ['online_ref'], unique=True)
        batch_op.create_index(batch_op.f('ix_orders_expires_at'), ['expires_at'], unique=False)

    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('address', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('address_ref', sa.String(length=200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_column('address_ref')
        batch_op.drop_column('address')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_orders_expires_at'))
        batch_op.drop_index(batch_op.f('ix_orders_online_ref'))
        batch_op.drop_index(batch_op.f('ix_orders_customer_id'))
        batch_op.drop_constraint(batch_op.f('fk_orders_customer_id_customers'), type_='foreignkey')
        for col in ('sync_pending', 'tracking_url', 'online_ref', 'refunded_at', 'expires_at', 'dispatched_at',
                    'paid_at', 'accepted_at', 'eta_minutes', 'refunded_cents', 'payment_url', 'payment_method',
                    'total_cents', 'delivery_fee_cents', 'delivery_zone', 'address_ref', 'address',
                    'customer_phone', 'customer_name', 'customer_id'):
            batch_op.drop_column(col)
