"""order screen (orders + items), dining tables, open tabs per table and waiter calls

Revision ID: 0005_orders_and_tables
Revises: 0004_product_sizes_and_details
Create Date: 2026-11-01 00:07:11

Purely additive: new tables (incl. `order_stations`, Pro), `product_categories.station_id`, `product_categories.send_to_orders` (default true: every category goes
to the order screen until configured) and `products.prep_minutes` (NULL = the channel's default).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005_orders_and_tables'
down_revision: Union[str, Sequence[str], None] = '0004_product_sizes_and_details'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('order_stations',
    sa.Column('name', sa.String(length=40), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('print_tickets', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_order_stations'))
    )
    op.create_table('dining_tables',
    sa.Column('label', sa.String(length=20), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('token', sa.String(length=32), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_dining_tables')),
    sa.UniqueConstraint('token', name=op.f('uq_dining_tables_token'))
    )
    op.create_table('waiter_calls',
    sa.Column('table_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('resolved_by', sa.Integer(), nullable=True),
    sa.Column('client_ip', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], name=op.f('fk_waiter_calls_resolved_by_users')),
    sa.ForeignKeyConstraint(['table_id'], ['dining_tables.id'], name=op.f('fk_waiter_calls_table_id_dining_tables')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_waiter_calls'))
    )
    with op.batch_alter_table('waiter_calls', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_waiter_calls_table_id'), ['table_id'], unique=False)

    op.create_table('table_tabs',
    sa.Column('table_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('opened_at', sa.DateTime(), nullable=False),
    sa.Column('closed_at', sa.DateTime(), nullable=True),
    sa.Column('sale_id', sa.Integer(), nullable=True),
    sa.Column('payment_ref', sa.String(length=80), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], name=op.f('fk_table_tabs_sale_id_sales')),
    sa.ForeignKeyConstraint(['table_id'], ['dining_tables.id'], name=op.f('fk_table_tabs_table_id_dining_tables')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_table_tabs'))
    )
    with op.batch_alter_table('table_tabs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_table_tabs_table_id'), ['table_id'], unique=False)

    op.create_table('orders',
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('channel', sa.String(length=10), nullable=False),
    sa.Column('table_id', sa.Integer(), nullable=True),
    sa.Column('table_label', sa.String(length=20), nullable=True),
    sa.Column('tab_id', sa.Integer(), nullable=True),
    sa.Column('station_id', sa.Integer(), nullable=True),
    sa.Column('sale_id', sa.Integer(), nullable=True),
    sa.Column('note', sa.String(length=200), nullable=True),
    sa.Column('target_minutes', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('received_at', sa.DateTime(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('ready_at', sa.DateTime(), nullable=True),
    sa.Column('delivered_at', sa.DateTime(), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(), nullable=True),
    sa.Column('cancel_reason', sa.String(length=200), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('confirmed_by', sa.Integer(), nullable=True),
    sa.Column('prepared_by', sa.Integer(), nullable=True),
    sa.Column('client_ip', sa.String(length=64), nullable=True),
    sa.Column('public_key', sa.String(length=32), nullable=True),
    sa.Column('payment_status', sa.String(length=10), server_default='unpaid', nullable=False),
    sa.Column('payment_ref', sa.String(length=80), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['confirmed_by'], ['users.id'], name=op.f('fk_orders_confirmed_by_users')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_orders_created_by_users')),
    sa.ForeignKeyConstraint(['prepared_by'], ['users.id'], name=op.f('fk_orders_prepared_by_users')),
    sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], name=op.f('fk_orders_sale_id_sales')),
    sa.ForeignKeyConstraint(['tab_id'], ['table_tabs.id'], name=op.f('fk_orders_tab_id_table_tabs')),
    sa.ForeignKeyConstraint(['station_id'], ['order_stations.id'], name=op.f('fk_orders_station_id_order_stations')),
    sa.ForeignKeyConstraint(['table_id'], ['dining_tables.id'], name=op.f('fk_orders_table_id_dining_tables')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_orders'))
    )
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_orders_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_received_at'), ['received_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_sale_id'), ['sale_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_tab_id'), ['tab_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_station_id'), ['station_id'], unique=False)

    op.create_table('order_items',
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=True),
    sa.Column('name_snapshot', sa.String(length=160), nullable=False),
    sa.Column('size_id', sa.Integer(), nullable=True),
    sa.Column('size_name', sa.String(length=60), nullable=True),
    sa.Column('qty', sa.Float(), nullable=False),
    sa.Column('unit_price_cents', sa.Integer(), nullable=False),
    sa.Column('modifiers', sa.JSON(), nullable=True),
    sa.Column('notes', sa.String(length=200), nullable=True),
    sa.Column('prep_minutes', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_order_items_order_id_orders'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_order_items_product_id_products')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_order_items'))
    )
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_order_items_order_id'), ['order_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_order_items_product_id'), ['product_id'], unique=False)

    # Plain ADD COLUMNs (no table rebuild): existing rows are untouched.
    op.add_column('product_categories', sa.Column('send_to_orders', sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column('products', sa.Column('prep_minutes', sa.Integer(), nullable=True))
    # SQLite can't add a FK constraint with ALTER: a batch rebuild of the (small) categories table.
    with op.batch_alter_table('product_categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('station_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_product_categories_station_id_order_stations'), 'order_stations', ['station_id'], ['id'], ondelete='SET NULL')



def downgrade() -> None:
    with op.batch_alter_table('product_categories', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_product_categories_station_id_order_stations'), type_='foreignkey')
        batch_op.drop_column('station_id')
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('prep_minutes')

    with op.batch_alter_table('product_categories', schema=None) as batch_op:
        batch_op.drop_column('send_to_orders')

    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_order_items_product_id'))
        batch_op.drop_index(batch_op.f('ix_order_items_order_id'))

    op.drop_table('order_items')
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_orders_station_id'))
        batch_op.drop_index(batch_op.f('ix_orders_tab_id'))
        batch_op.drop_index(batch_op.f('ix_orders_status'))
        batch_op.drop_index(batch_op.f('ix_orders_sale_id'))
        batch_op.drop_index(batch_op.f('ix_orders_received_at'))
        batch_op.drop_index(batch_op.f('ix_orders_created_at'))

    op.drop_table('orders')
    with op.batch_alter_table('table_tabs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_table_tabs_table_id'))

    op.drop_table('table_tabs')
    with op.batch_alter_table('waiter_calls', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_waiter_calls_table_id'))

    op.drop_table('waiter_calls')
    op.drop_table('dining_tables')
    op.drop_table('order_stations')
