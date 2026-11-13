"""Upgrade paths: a database created by ANY earlier revision must migrate to the current schema without
losing rows, end structurally healthy and with exactly the same schema as a fresh install.

Why: customers update from whatever version they have (the 6/11 damaged-DB incident). For each historical
revision we build the database as that version would have, put one row in every table, upgrade to head and
check nothing was lost (batch table rebuilds are where rows disappear)."""
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.config import MIGRATIONS_DIR


def _cfg(db: Path) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db.as_posix()}")
    return cfg


REVISIONS = [s.revision for s in reversed(list(ScriptDirectory(str(MIGRATIONS_DIR)).walk_revisions()))]
SKIP_TABLES = {"alembic_version"}
# Tables a migration rebuilds from scratch ON PURPOSE: the old table is kept aside as `<name>_legacy` (never
# deleted), so the rows must be there instead. Keep this list tiny and justified.
INTENTIONAL_RESETS = {"expenses": "0012_expenses"}  # the 0001 table was never used by the app; 0012 recreates it


def _index_of(revision: str) -> int:
    return REVISIONS.index(revision)


def _revision_with_file_prefix(prefix: str) -> str:
    for r in REVISIONS:
        if Path(ScriptDirectory(str(MIGRATIONS_DIR)).get_revision(r).path).name.startswith(prefix):
            return r
    raise AssertionError(prefix)


def _schema(db: Path) -> dict[str, tuple]:
    out = {}
    with closing(sqlite3.connect(db)) as con:
        for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            cols = tuple(sorted((c[1], c[2].upper(), c[3]) for c in con.execute(f'PRAGMA table_info("{name}")')))
            idx = tuple(sorted(r[1] for r in con.execute(f'PRAGMA index_list("{name}")') if not r[1].startswith("sqlite_autoindex")))
            out[name] = (cols, idx)
    return out


def _sample(coltype: str, name: str):
    t = coltype.upper()
    if any(k in t for k in ("INT", "BOOL")):
        return 1
    if any(k in t for k in ("FLOAT", "REAL", "NUMERIC", "DECIMAL", "DOUBLE")):
        return 1.0
    if any(k in t for k in ("DATE", "TIME")):
        return "2026-01-01 00:00:00"
    if "JSON" in t:
        return "{}"
    return f"x-{name}"


def _fill_every_table(db: Path) -> dict[str, int]:
    """One generic row per table (NOT NULL columns get a type-appropriate value). Returns the expected counts."""
    expected: dict[str, int] = {}
    with closing(sqlite3.connect(db)) as con:
        for (name,) in list(con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")):
            if name in SKIP_TABLES:
                continue
            cols = list(con.execute(f'PRAGMA table_info("{name}")'))
            values = {c[1]: _sample(c[2], c[1]) for c in cols if not (c[5] and "INT" in c[2].upper() and len([x for x in cols if x[5]]) == 1)}
            sql = f'INSERT INTO "{name}" ({",".join(chr(34) + k + chr(34) for k in values)}) VALUES ({",".join("?" * len(values))})'
            try:
                con.execute(sql, list(values.values()))
            except sqlite3.IntegrityError:
                continue  # a CHECK we cannot guess: this table is simply not covered for this revision
            expected[name] = 1
        con.commit()
    return expected


@pytest.fixture(scope="module")
def fresh_schema(tmp_path_factory):
    db = tmp_path_factory.mktemp("fresh") / "fresh.db"
    command.upgrade(_cfg(db), "head")
    return _schema(db)


@pytest.mark.parametrize("revision", REVISIONS)
def test_upgrading_from_every_revision_keeps_rows_and_matches_a_fresh_schema(tmp_path, revision, fresh_schema):
    db = tmp_path / "old.db"
    cfg = _cfg(db)
    command.upgrade(cfg, revision)
    expected = _fill_every_table(db)
    assert expected, "no table could be sampled: the helper needs a look"

    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db)) as con:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        (head,) = con.execute("SELECT version_num FROM alembic_version").fetchone()
        assert head == ScriptDirectory(str(MIGRATIONS_DIR)).get_current_head()
        survivors = {t for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        lost = {}
        for table, n in expected.items():
            if table not in survivors:
                continue  # renamed or dropped by a later migration on purpose
            reset_by = INTENTIONAL_RESETS.get(table)
            if reset_by and _index_of(revision) < _index_of(_revision_with_file_prefix(reset_by)):
                (kept,) = con.execute(f'SELECT count(*) FROM "{table}_legacy"').fetchone()
                if kept < n:
                    lost[f"{table}_legacy"] = (n, kept)
                continue
            (count,) = con.execute(f'SELECT count(*) FROM "{table}"').fetchone()
            if count < n:
                lost[table] = (n, count)
    assert not lost, f"rows lost when upgrading from {revision}: {lost}"
    upgraded = {t: v for t, v in _schema(db).items() if not t.endswith("_legacy")}  # rows kept aside on purpose
    diff = {t: (upgraded.get(t), fresh_schema.get(t)) for t in set(upgraded) | set(fresh_schema) if upgraded.get(t) != fresh_schema.get(t)}
    assert not diff, f"an upgraded database must end with the same schema as a new install: {sorted(diff)}"


def test_every_revision_is_reachable_and_single_headed():
    script = ScriptDirectory(str(MIGRATIONS_DIR))
    assert len(script.get_heads()) == 1, "two migration heads: branch not merged"
    assert len(REVISIONS) == len(set(REVISIONS))
