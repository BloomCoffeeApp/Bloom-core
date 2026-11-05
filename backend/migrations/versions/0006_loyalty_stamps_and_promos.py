"""loyalty stamp cards and promotions (Pro), promo/reward snapshots on sales

Revision ID: 0006_loyalty_stamps_and_promos
Revises: 0005_orders_and_tables
Create Date: 2026-11-01 12:00:00

Purely additive: `loyalty_programs`, `loyalty_stamps`, `promos`; `sales.reward_program_id`,
`sales.reward_discount_cents`; `sale_items.promo_id`, `.promo_name`, `.promo_discount_cents`,
`.reward_program_id`, `.courtesy_reason`. Old sales keep NULL/0 (no promo, no reward).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006_loyalty_stamps_and_promos'
down_revision: Union[str, Sequence[str], None] = '0005_orders_and_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('loyalty_programs',
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('starts_on', sa.Date(), nullable=True),
    sa.Column('ends_on', sa.Date(), nullable=True),
    sa.Column('count_type', sa.String(length=12), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=True),
    sa.Column('min_amount_cents', sa.Integer(), nullable=False),
    sa.Column('stamps_required', sa.Integer(), nullable=False),
    sa.Column('reward_type', sa.String(length=10), nullable=False),
    sa.Column('reward_product_id', sa.Integer(), nullable=True),
    sa.Column('reward_size_id', sa.Integer(), nullable=True),
    sa.Column('reward_value', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_loyalty_programs'))
    )
    op.create_table('loyalty_stamps',
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('program_id', sa.Integer(), nullable=False),
    sa.Column('stamps', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=120), nullable=False),
    sa.Column('sale_id', sa.Integer(), nullable=True),
    sa.Column('ts', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name=op.f('fk_loyalty_stamps_customer_id_customers'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['program_id'], ['loyalty_programs.id'], name=op.f('fk_loyalty_stamps_program_id_loyalty_programs'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], name=op.f('fk_loyalty_stamps_sale_id_sales')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_loyalty_stamps'))
    )
    with op.batch_alter_table('loyalty_stamps', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_loyalty_stamps_customer_id'), ['customer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_loyalty_stamps_program_id'), ['program_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_loyalty_stamps_sale_id'), ['sale_id'], unique=False)
    op.create_table('promos',
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('starts_on', sa.Date(), nullable=True),
    sa.Column('ends_on', sa.Date(), nullable=True),
    sa.Column('weekdays', sa.JSON(), nullable=True),
    sa.Column('time_from', sa.String(length=5), nullable=True),
    sa.Column('time_to', sa.String(length=5), nullable=True),
    sa.Column('discount_type', sa.String(length=6), nullable=False),
    sa.Column('discount_value', sa.Integer(), nullable=False),
    sa.Column('target_type', sa.String(length=10), nullable=False),
    sa.Column('target_ids', sa.JSON(), nullable=True),
    sa.Column('combo_price_cents', sa.Integer(), nullable=False),
    sa.Column('combo_items', sa.JSON(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_promos'))
    )
    op.add_column('sales', sa.Column('reward_program_id', sa.Integer(), nullable=True))
    op.add_column('sales', sa.Column('reward_discount_cents', sa.Integer(), server_default='0', nullable=False))
    op.add_column('sale_items', sa.Column('promo_id', sa.Integer(), nullable=True))
    op.add_column('sale_items', sa.Column('promo_name', sa.String(length=120), nullable=True))
    op.add_column('sale_items', sa.Column('promo_discount_cents', sa.Integer(), server_default='0', nullable=False))
    op.add_column('sale_items', sa.Column('reward_program_id', sa.Integer(), nullable=True))
    op.add_column('sale_items', sa.Column('courtesy_reason', sa.String(length=60), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('sale_items', schema=None) as batch_op:
        batch_op.drop_column('courtesy_reason')
        batch_op.drop_column('reward_program_id')
        batch_op.drop_column('promo_discount_cents')
        batch_op.drop_column('promo_name')
        batch_op.drop_column('promo_id')
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.drop_column('reward_discount_cents')
        batch_op.drop_column('reward_program_id')
    op.drop_table('promos')
    with op.batch_alter_table('loyalty_stamps', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_loyalty_stamps_sale_id'))
        batch_op.drop_index(batch_op.f('ix_loyalty_stamps_program_id'))
        batch_op.drop_index(batch_op.f('ix_loyalty_stamps_customer_id'))
    op.drop_table('loyalty_stamps')
    op.drop_table('loyalty_programs')
