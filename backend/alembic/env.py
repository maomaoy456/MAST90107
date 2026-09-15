from alembic import context

from app.config import Settings
from app.db import Base, build_engine
from app import models  # noqa: F401
from app.logging import configure_logging

configure_logging()
target_metadata = Base.metadata


def offline():
    context.configure(
        dialect_name="mysql", target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def online():
    engine = build_engine(Settings())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    offline()
else:
    online()
