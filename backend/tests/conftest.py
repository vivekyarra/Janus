import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./janus_test.db")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401, E402
from app.db.session import Base  # noqa: E402


@pytest.fixture
def db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()

