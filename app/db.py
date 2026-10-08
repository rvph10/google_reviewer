from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(expire_on_commit=False)


def normalize_url(url: str) -> str:
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def init_db(url: str) -> None:
    from app import models  # noqa: F401

    engine = create_engine(normalize_url(url), pool_pre_ping=True)
    SessionLocal.configure(bind=engine)
    Base.metadata.create_all(engine)
