"""expenses: categories, monthly recurring expenses and the expenses table rebuilt

Revision ID: 0012_expenses
Revises: 0011_packaging_by_channel
Create Date: 2026-11-06 12:00:00

The `expenses` table from 0001 was never written by any code path (no API/UI), so it is rebuilt with
the new shape. If an install somehow has rows there, the old table is kept as `expenses_legacy`.
Default categories are inserted so existing installs get them too (editable afterwards).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0012_expenses'
down_revision: Union[str, Sequence[str], None] = '0011_packaging_by_channel'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_CATEGORIES = [
    ("Alquiler", "fixed"),
    ("Servicios (luz, gas, agua, internet)", "fixed"),
    ("Sueldos y cargas sociales", "fixed"),
    ("Impuestos y tasas", "fixed"),
    ("Abonos y suscripciones", "fixed"),
    ("Mantenimiento y reparaciones", "variable"),
    ("Limpieza y descartables", "variable"),
    ("Publicidad", "variable"),
    ("Comisiones y gastos bancarios", "variable"),
    ("Otros", "variable"),
]


def upgrade() -> None:
    bind = op.get_bind()
    old_rows = bind.execute(sa.text("SELECT count(*) FROM expenses")).scalar() or 0
    if old_rows:
        op.rename_table('expenses', 'expenses_legacy')
    else:
        op.drop_table('expenses')

    categories = op.create_table('expense_categories',
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False, server_default='variable'),
    sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_expense_categories')),
    sa.UniqueConstraint('name', name=op.f('uq_expense_categories_name')),
    )
    op.create_table('recurring_expenses',
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(length=200), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('day_of_month', sa.Integer(), nullable=False, server_default='10'),
    sa.Column('payment_method', sa.String(length=30), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column('start_period', sa.String(length=7), nullable=False),
    sa.Column('last_period', sa.String(length=7), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['expense_categories.id'], name=op.f('fk_recurring_expenses_category_id_expense_categories')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_recurring_expenses_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recurring_expenses')),
    )
    op.create_table('expenses',
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('description', sa.String(length=200), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('paid_at', sa.DateTime(), nullable=True),
    sa.Column('payment_method', sa.String(length=30), nullable=True),
    sa.Column('cash_movement_id', sa.Integer(), nullable=True),
    sa.Column('recurring_id', sa.Integer(), nullable=True),
    sa.Column('period', sa.String(length=7), nullable=True),
    sa.Column('receipt_path', sa.String(length=200), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['cash_movement_id'], ['cash_movements.id'], name=op.f('fk_expenses_cash_movement_id_cash_movements'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['category_id'], ['expense_categories.id'], name=op.f('fk_expenses_category_id_expense_categories')),
    sa.ForeignKeyConstraint(['recurring_id'], ['recurring_expenses.id'], name=op.f('fk_expenses_recurring_id_recurring_expenses'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_expenses_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_expenses')),
    sa.UniqueConstraint('recurring_id', 'period', name='uq_expenses_recurring_period'),
    )
    op.create_index('ix_expenses_date', 'expenses', ['date'], unique=False)
    op.create_index('ix_expenses_status_due', 'expenses', ['status', 'due_date'], unique=False)

    op.bulk_insert(categories, [
        {"name": name, "kind": kind, "active": True, "sort_order": i}
        for i, (name, kind) in enumerate(DEFAULT_CATEGORIES, start=1)
    ])


def downgrade() -> None:
    op.drop_index('ix_expenses_status_due', table_name='expenses')
    op.drop_index('ix_expenses_date', table_name='expenses')
    op.drop_table('expenses')
    op.drop_table('recurring_expenses')
    op.drop_table('expense_categories')
    insp = sa.inspect(op.get_bind())
    if 'expenses_legacy' in insp.get_table_names():
        op.rename_table('expenses_legacy', 'expenses')
    else:
        op.create_table('expenses',
        sa.Column('category', sa.String(length=60), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_expenses_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_expenses')),
        )
