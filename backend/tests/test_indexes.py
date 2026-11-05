"""Migration 0007 (hot-query indexes): up/down on a copy of the demo DB, and the hot queries use them."""

import sqlite3
from pathlib import Path

import pytest

NEW = {
    "ix_sales_status_ts", "ix_sales_cash_session_status",
    "ix_stock_movements_item_ts", "ix_stock_movements_ref", "ix_stock_movements_type_ts",
    "ix_loyalty_transactions_customer_ts", "ix_customer_account_movements_customer_ts",
}
REPLACED = {"ix_sales_cash_session_id", "ix_stock_movements_stock_item_id"}


def _indexes(path: Path) -> set[str]:
    con = sqlite3.connect(path)
    try:
        return {r[0] for r in con.execute("select name from sqlite_master where type='index' and sql is not null")}
    finally:
        con.close()


@pytest.fixture()
def demo_copy(seeded, tmp_path) -> Path:
    from app.config import DB_PATH
    from app.db import engine

    engine.dispose()
    copy = tmp_path / "demo.db"
    src, dst = sqlite3.connect(DB_PATH), sqlite3.connect(copy)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return copy


def test_migration_0007_up_and_down(demo_copy):
    from alembic import command

    from app.migrate import alembic_config

    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{demo_copy.as_posix()}")
    command.stamp(cfg, "head")
    assert NEW <= _indexes(demo_copy) and not REPLACED & _indexes(demo_copy)  # models == migrations

    command.downgrade(cfg, "0006_loyalty_stamps_and_promos")
    after_down = _indexes(demo_copy)
    assert REPLACED <= after_down and not NEW & after_down
    assert {"ix_sales_ts", "ix_stock_movements_ts"} <= after_down

    command.upgrade(cfg, "head")
    after_up = _indexes(demo_copy)
    assert NEW <= after_up and not REPLACED & after_up
    con = sqlite3.connect(demo_copy)
    try:
        assert con.execute("pragma integrity_check").fetchone()[0] == "ok"
        assert con.execute("select count(*) from sales").fetchone()[0] > 1000  # data untouched
    finally:
        con.close()


@pytest.mark.parametrize(
    ("sql", "index"),
    [
        ("select count(id) from sales where status='voided'", "ix_sales_status_ts"),
        ("select count(id), sum(total_cents), sum(cost_cents) from sales where status='completed' "
         "and is_courtesy is 0 and ts >= '2026-01-01' and ts < '2026-02-01'", "ix_sales_status_ts"),
        ("select si.product_id, sum(si.qty) from sale_items si join sales s on s.id = si.sale_id "
         "where s.status='completed' and s.is_courtesy is 0 and s.ts >= '2026-01-01' and s.ts < '2026-02-01' "
         "and si.product_id in (1, 2, 3) group by si.product_id", "ix_sales_status_ts"),
        ("select cash_session_id, count(id) from sales where cash_session_id in (1, 2) and status='completed' "
         "group by cash_session_id", "ix_sales_cash_session_status"),
        ("select customer_id, max(ts), count(id), sum(total_cents) from sales where status='completed' "
         "and is_courtesy is 0 and customer_id is not null group by customer_id", "ix_sales_status_ts"),
        ("select cash_session_id, count(id), sum(total_cents) from sales where cash_session_id in (1, 2) "
         "and status='completed' and is_courtesy is 0 group by cash_session_id", "ix_sales_cash_session_status"),
        ("select * from stock_movements where stock_item_id = 1 order by ts desc limit 200", "ix_stock_movements_item_ts"),
        ("select * from stock_movements where ref_type='sale' and ref_id=10 and type='sale'", "ix_stock_movements_ref"),
        ("select stock_item_id, sum(qty) from stock_movements where ts >= '2026-01-01' "
         "and type in ('sale', 'waste', 'internal') group by stock_item_id", "ix_stock_movements_type_ts"),
        ("select * from loyalty_transactions where customer_id = 1 order by ts desc", "ix_loyalty_transactions_customer_ts"),
    ],
)
def test_hot_queries_use_the_indexes(demo_copy, sql, index):
    con = sqlite3.connect(demo_copy)
    try:
        plan = " | ".join(r[-1] for r in con.execute("explain query plan " + sql))
    finally:
        con.close()
    assert index in plan, plan
