from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from starlette.requests import Request

from app.config import Settings


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


def build_engine(settings: Settings):
    return create_engine(
        settings.database_url.get_secret_value(), pool_pre_ping=True,
        echo=False, hide_parameters=True,
        connect_args={"connect_timeout": 3, "read_timeout": 10, "write_timeout": 10,
                      "charset": "utf8mb4", "init_command": "SET time_zone = '+00:00'"},
    )


def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session
