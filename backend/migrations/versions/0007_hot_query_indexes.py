"""indexes for the hot queries of the local database

Revision ID: 0007_hot_query_indexes
Revises: 0006_loyalty_stamps_and_promos
Create Date: 2026-11-05 15:30:00

Only indexes (no data changes). Chosen with EXPLAIN QUERY PLAN and timings on a synthetic DB with
~200k sales / 640k stock movements (see PLAN.md section 9):
- sales (status, ts, is_courtesy, total_cents, cost_cents): dashboard/report aggregates by date become
  index-only scans, and "anuladas" no longer scans the table.
- sales (cash_session_id, status) replaces ix_sales_cash_session_id: with the index above the planner
  preferred `status` for the cash-session history; the composite keeps it on the session.
  (A per-customer covering index was tried and dropped: without ANALYZE stats SQLite either ignored
  it or, with status/is_courtesy first, used it for the cash-session queries and made them 8x slower.)
- stock_movements (stock_item_id, ts) replaces ix_stock_movements_stock_item_id (no sort for an item's
  history); (ref_type, ref_id) for voiding a sale; (type, ts) for consumption/purchase suggestions.
- loyalty_transactions / customer_account_movements (customer_id, ts): customer detail.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '0007_hot_query_indexes'
down_revision: Union[str, Sequence[str], None] = '0006_loyalty_stamps_and_promos'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW = [
    ("ix_sales_status_ts", "sales", ["status", "ts", "is_courtesy", "total_cents", "cost_cents"]),
    ("ix_sales_cash_session_status", "sales", ["cash_session_id", "status"]),
    ("ix_stock_movements_item_ts", "stock_movements", ["stock_item_id", "ts"]),
    ("ix_stock_movements_ref", "stock_movements", ["ref_type", "ref_id"]),
    ("ix_stock_movements_type_ts", "stock_movements", ["type", "ts"]),
    ("ix_loyalty_transactions_customer_ts", "loyalty_transactions", ["customer_id", "ts"]),
    ("ix_customer_account_movements_customer_ts", "customer_account_movements", ["customer_id", "ts"]),
]
# Single-column indexes made redundant by a composite one that starts with the same column.
REPLACED = [
    ("ix_sales_cash_session_id", "sales", ["cash_session_id"]),
    ("ix_stock_movements_stock_item_id", "stock_movements", ["stock_item_id"]),
]


def upgrade() -> None:
    for name, table, cols in NEW:
        op.create_index(name, table, cols, if_not_exists=True)
    for name, table, _ in REPLACED:
        op.drop_index(name, table_name=table, if_exists=True)


def downgrade() -> None:
    for name, table, cols in REPLACED:
        op.create_index(name, table, cols, if_not_exists=True)
    for name, table, _ in NEW:
        op.drop_index(name, table_name=table, if_exists=True)
