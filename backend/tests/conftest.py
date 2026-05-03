import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.models import Base
from app.config import Settings

@pytest.fixture
def engine():
    e = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)
    e.dispose()

@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)

@pytest.fixture
def session(session_factory):
    s = session_factory()
    yield s
    s.close()

@pytest.fixture
def settings():
    return Settings()
