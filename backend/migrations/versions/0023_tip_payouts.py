"""tip payouts

Revision ID: 0023_tip_payouts
Revises: 0022_waiter_per_table
Create Date: 2026-11-13 11:00:00

Purely additive: the frozen result of sharing a period's tips (`tip_payouts` + one line per person) and the
mark on each settled sale (`sales.tip_payout_id`), so a sale's tip is never shared twice.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0023_tip_payouts'
down_revision: Union[str, Sequence[str], None] = '0022_waiter_per_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tip_payouts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('rule_snapshot', sa.JSON(), nullable=False),
        sa.Column('total_cents', sa.Integer(), nullable=False),
        sa.Column('unassigned_cents', sa.Integer(), server_default='0', nullable=False),
        sa.Column('sales_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_tip_payouts_created_by_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tip_payouts')),
    )
    op.create_table(
        'tip_payout_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payout_id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('direct_cents', sa.Integer(), nullable=False),
        sa.Column('pool_cents', sa.Integer(), nullable=False),
        sa.Column('total_cents', sa.Integer(), nullable=False),
        sa.Column('minutes', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name=op.f('fk_tip_payout_lines_employee_id_employees')),
        sa.ForeignKeyConstraint(['payout_id'], ['tip_payouts.id'], name=op.f('fk_tip_payout_lines_payout_id_tip_payouts'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tip_payout_lines')),
    )
    with op.batch_alter_table('tip_payout_lines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tip_payout_lines_payout_id'), ['payout_id'], unique=False)
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tip_payout_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_sales_tip_payout_id'), ['tip_payout_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_sales_tip_payout_id_tip_payouts'), 'tip_payouts', ['tip_payout_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_sales_tip_payout_id_tip_payouts'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_sales_tip_payout_id'))
        batch_op.drop_column('tip_payout_id')
    with op.batch_alter_table('tip_payout_lines', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tip_payout_lines_payout_id'))
    op.drop_table('tip_payout_lines')
    op.drop_table('tip_payouts')
