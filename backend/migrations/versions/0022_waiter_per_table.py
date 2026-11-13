"""waiter per table

Revision ID: 0022_waiter_per_table
Revises: 0021_tips
Create Date: 2026-11-13 10:00:00

Purely additive: floor zones, the waiter (an employee) of a zone / table / open tab, the sale's snapshot
(`table_id`, `waiter_employee_id`) and the employee's tip group. Every new column is nullable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0022_waiter_per_table'
down_revision: Union[str, Sequence[str], None] = '0021_tips'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'floor_zones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=40), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('waiter_employee_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['waiter_employee_id'], ['employees.id'], name=op.f('fk_floor_zones_waiter_employee_id_employees')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_floor_zones')),
    )
    with op.batch_alter_table('dining_tables', schema=None) as batch_op:
        batch_op.add_column(sa.Column('zone_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('waiter_employee_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_dining_tables_zone_id_floor_zones'), 'floor_zones', ['zone_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('fk_dining_tables_waiter_employee_id_employees'), 'employees', ['waiter_employee_id'], ['id'])
    with op.batch_alter_table('table_tabs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('waiter_employee_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_table_tabs_waiter_employee_id_employees'), 'employees', ['waiter_employee_id'], ['id'])
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('table_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('waiter_employee_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_sales_table_id'), ['table_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sales_waiter_employee_id'), ['waiter_employee_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_sales_table_id_dining_tables'), 'dining_tables', ['table_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('fk_sales_waiter_employee_id_employees'), 'employees', ['waiter_employee_id'], ['id'])
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tip_group', sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.drop_column('tip_group')
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_sales_waiter_employee_id_employees'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_sales_table_id_dining_tables'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_sales_waiter_employee_id'))
        batch_op.drop_index(batch_op.f('ix_sales_table_id'))
        batch_op.drop_column('waiter_employee_id')
        batch_op.drop_column('table_id')
    with op.batch_alter_table('table_tabs', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_table_tabs_waiter_employee_id_employees'), type_='foreignkey')
        batch_op.drop_column('waiter_employee_id')
    with op.batch_alter_table('dining_tables', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_dining_tables_waiter_employee_id_employees'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_dining_tables_zone_id_floor_zones'), type_='foreignkey')
        batch_op.drop_column('waiter_employee_id')
        batch_op.drop_column('zone_id')
    op.drop_table('floor_zones')
