import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import models  # noqa: F401
from app.db.session import Base, SessionLocal, engine
from app.repositories.catalog import seed_catalog


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        count = seed_catalog(session)
    print(f"Seeded {count} deterministic JANUS demo products.")

