"""planned shifts and public holidays

Revision ID: 0029_shifts_and_holidays
Revises: 0028_partial_receipts
Create Date: 2026-11-15 10:00:00

Purely additive: `shifts` (the weekly grid of who works when) and `holidays` (days paid with the holiday
surcharge; the bundled national list is seeded per year by the Pro staff module, never here).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0029_shifts_and_holidays'
down_revision: Union[str, Sequence[str], None] = '0028_partial_receipts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'shifts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.String(length=5), nullable=False),
        sa.Column('end_time', sa.String(length=5), nullable=False),
        sa.Column('break_minutes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_shifts_created_by_users')),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name=op.f('fk_shifts_employee_id_employees'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_shifts')),
    )
    with op.batch_alter_table('shifts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_shifts_date'), ['date'], unique=False)
        batch_op.create_index('ix_shifts_employee_date', ['employee_id', 'date'], unique=False)

    op.create_table(
        'holidays',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('source', sa.String(length=10), nullable=False),
        sa.Column('active', sa.Boolean(), server_default='1', nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_holidays')),
        sa.UniqueConstraint('date', name=op.f('uq_holidays_date')),
    )


def downgrade() -> None:
    op.drop_table('holidays')
    with op.batch_alter_table('shifts', schema=None) as batch_op:
        batch_op.drop_index('ix_shifts_employee_date')
        batch_op.drop_index(batch_op.f('ix_shifts_date'))
    op.drop_table('shifts')
