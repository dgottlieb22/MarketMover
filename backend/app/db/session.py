from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base


def get_engine(url: str) -> Engine:
    return create_engine(url)


def get_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
