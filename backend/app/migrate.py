from alembic import command
from alembic.config import Config

from app.config import DATABASE_URL, MIGRATIONS_DIR


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    return cfg


def upgrade_db() -> None:
    from app.services.backup import backup_before_migration

    backup_before_migration()
    command.upgrade(alembic_config(), "head")
