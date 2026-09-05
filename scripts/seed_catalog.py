from backend.app.db import models  # noqa: F401
from backend.app.db.session import Base, SessionLocal, engine
from backend.app.repositories.catalog import seed_catalog


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        count = seed_catalog(session)
    print(f"Seeded {count} deterministic JANUS demo products.")

