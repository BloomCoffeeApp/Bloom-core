"""editable roles (roles) + employees, time clock and advances (Pro "staff")

Revision ID: 0010_roles_and_staff
Revises: 0009_online_orders
Create Date: 2026-11-06 15:00:00

Purely additive. No role rows are created: built-in roles keep their default permissions
(app/permissions.py) until the owner edits them, so existing installs behave exactly as before.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0010_roles_and_staff'
down_revision: Union[str, Sequence[str], None] = '0009_online_orders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'roles',
        sa.Column('key', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=40), nullable=False),
        sa.Column('permissions', sa.JSON(), nullable=False),
        sa.Column('builtin', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
        sa.UniqueConstraint('key', name=op.f('uq_roles_key')),
    )
    op.create_table(
        'employees',
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('clock_pin_hash', sa.String(length=255), nullable=True),
        sa.Column('position', sa.String(length=60), nullable=True),
        sa.Column('pay_type', sa.String(length=10), nullable=False),
        sa.Column('hourly_rate_cents', sa.Integer(), nullable=False),
        sa.Column('monthly_salary_cents', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_employees_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_employees')),
        sa.UniqueConstraint('user_id', name=op.f('uq_employees_user_id')),
    )
    op.create_table(
        'time_entries',
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('clock_in', sa.DateTime(), nullable=False),
        sa.Column('clock_out', sa.DateTime(), nullable=True),
        sa.Column('break_minutes', sa.Integer(), nullable=False),
        sa.Column('break_started_at', sa.DateTime(), nullable=True),
        sa.Column('source', sa.String(length=10), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('edited_by', sa.Integer(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['edited_by'], ['users.id'], name=op.f('fk_time_entries_edited_by_users')),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name=op.f('fk_time_entries_employee_id_employees'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_time_entries')),
    )
    op.create_index('ix_time_entries_employee_in', 'time_entries', ['employee_id', 'clock_in'], unique=False)
    op.create_table(
        'staff_advances',
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name=op.f('fk_staff_advances_employee_id_employees'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_staff_advances_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_staff_advances')),
    )
    op.create_index(op.f('ix_staff_advances_employee_id'), 'staff_advances', ['employee_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_staff_advances_employee_id'), table_name='staff_advances')
    op.drop_table('staff_advances')
    op.drop_index('ix_time_entries_employee_in', table_name='time_entries')
    op.drop_table('time_entries')
    op.drop_table('employees')
    op.drop_table('roles')
