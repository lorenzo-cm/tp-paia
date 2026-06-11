import logging
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, make_url, pool

from app.alembic.utils import color
from app.db.base import metadata  # import all models
from app.core.config import get_settings

settings = get_settings()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url() -> str:
    return str(settings.DATABASE_URL)


def mask_url() -> str:
    url_str = get_url()
    url = make_url(url_str)
    return url.render_as_string(hide_password=True)


def _log_runtime_info() -> None:
    log = logging.getLogger("alembic.env")

    log.info(color("🚀 Starting Alembic migrations...", fg="bold"))
    log.info("🔧 Alembic environment: %s", color(settings.ENVIRONMENT, "cyan"))
    log.info("🔗 DATABASE_URL: %s", color(mask_url(), "cyan"))

    # Skip the interactive ENTER-to-confirm prompt when ALEMBIC_NO_CONFIRM is set
    # (used by the testcontainers-backed db test fixture; without this the
    # alembic subprocess blocks on input() with EOFError because pytest closes stdin).
    if os.environ.get("ALEMBIC_NO_CONFIRM"):
        log.info(color("✅ ALEMBIC_NO_CONFIRM set — skipping confirmation.", fg="green"))
        return

    log.info(color("⚠️  If sure, press ENTER to continue the migration...", fg="yellow"))

    try:
        user_input = input()
    except KeyboardInterrupt:
        user_input = "abort"

    if user_input != "":
        log.info(color("❌ Migration aborted by user.", fg="red"))
        exit(0)
    else:
        log.info(color("✅ Proceeding with the migration...", fg="green"))


_log_runtime_info()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)

    if configuration is None:
        raise RuntimeError("Config section not found in alembic.ini")

    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
