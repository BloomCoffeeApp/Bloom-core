"""collect payments: charges (QR / Point / links / transfer), refunds, customer screens

Revision ID: 0015_collect_payments
Revises: 0014_barista_tasting
Create Date: 2026-11-06 12:00:00

Purely additive. Adds the payment methods `mp_qr` ("QR Mercado Pago") and `mp_point`
("Point (posnet)") turned OFF: connecting Mercado Pago turns them on (services/collect.py).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0015_collect_payments'
down_revision: Union[str, Sequence[str], None] = '0014_barista_tasting'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_METHODS = (("mp_qr", "QR Mercado Pago"), ("mp_point", "Point (posnet)"))


def upgrade() -> None:
    op.create_table(
        'customer_screens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('current_charge_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_customer_screens')),
    )
    op.create_index(op.f('ix_customer_screens_token'), 'customer_screens', ['token'], unique=True)

    op.create_table(
        'collect_charges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('ref', sa.String(length=64), nullable=False),
        sa.Column('ref_type', sa.String(length=30), nullable=False),
        sa.Column('ref_id', sa.Integer(), nullable=True),
        sa.Column('provider_id', sa.String(length=80), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('status_detail', sa.String(length=60), nullable=True),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('refunded_cents', sa.Integer(), server_default='0', nullable=False),
        sa.Column('description', sa.String(length=150), nullable=False),
        sa.Column('qr_data', sa.Text(), nullable=True),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('device_id', sa.String(length=80), nullable=True),
        sa.Column('items', sa.JSON(), nullable=True),
        sa.Column('sale_payload', sa.JSON(), nullable=True),
        sa.Column('sale_id', sa.Integer(), nullable=True),
        sa.Column('screen_id', sa.Integer(), nullable=True),
        sa.Column('error', sa.String(length=300), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('confirmed_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('next_poll_at', sa.DateTime(), nullable=True),
        sa.Column('poll_failures', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], name=op.f('fk_collect_charges_sale_id_sales')),
        sa.ForeignKeyConstraint(['screen_id'], ['customer_screens.id'], name=op.f('fk_collect_charges_screen_id_customer_screens'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_collect_charges_created_by_users')),
        sa.ForeignKeyConstraint(['confirmed_by'], ['users.id'], name=op.f('fk_collect_charges_confirmed_by_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_collect_charges')),
        sa.UniqueConstraint('ref', name=op.f('uq_collect_charges_ref')),
    )
    op.create_index(op.f('ix_collect_charges_provider_id'), 'collect_charges', ['provider_id'], unique=False)
    op.create_index(op.f('ix_collect_charges_sale_id'), 'collect_charges', ['sale_id'], unique=False)
    op.create_index('ix_collect_charges_status_next_poll', 'collect_charges', ['status', 'next_poll_at'], unique=False)

    op.create_table(
        'collect_refunds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('charge_id', sa.Integer(), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('provider_refund_id', sa.String(length=80), nullable=True),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('ts', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['charge_id'], ['collect_charges.id'], name=op.f('fk_collect_refunds_charge_id_collect_charges'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_collect_refunds_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_collect_refunds')),
    )
    op.create_index(op.f('ix_collect_refunds_charge_id'), 'collect_refunds', ['charge_id'], unique=False)

    # New payment methods, off until Mercado Pago is connected (only on databases that already have methods:
    # a brand-new install gets them from the seed).
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT COUNT(*) FROM payment_methods")).scalar():
        order = conn.execute(sa.text("SELECT COALESCE(MAX(sort_order), 0) FROM payment_methods")).scalar() or 0
        for i, (code, name) in enumerate(NEW_METHODS, start=1):
            exists = conn.execute(sa.text("SELECT 1 FROM payment_methods WHERE code = :c"), {"c": code}).first()
            if not exists:
                conn.execute(
                    sa.text("INSERT INTO payment_methods (code, name, active, surcharge_pct, sort_order) VALUES (:c, :n, 0, 0, :o)"),
                    {"c": code, "n": name, "o": order + i},
                )


def downgrade() -> None:
    op.execute("DELETE FROM payment_methods WHERE code IN ('mp_qr', 'mp_point')")
    op.drop_index(op.f('ix_collect_refunds_charge_id'), table_name='collect_refunds')
    op.drop_table('collect_refunds')
    op.drop_index('ix_collect_charges_status_next_poll', table_name='collect_charges')
    op.drop_index(op.f('ix_collect_charges_sale_id'), table_name='collect_charges')
    op.drop_index(op.f('ix_collect_charges_provider_id'), table_name='collect_charges')
    op.drop_table('collect_charges')
    op.drop_index(op.f('ix_customer_screens_token'), table_name='customer_screens')
    op.drop_table('customer_screens')
