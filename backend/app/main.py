from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from alembic.migration import MigrationContext
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.api import audit, catalog, mandates, proposals, stepups
from app.config import get_settings, validate_production_settings
from app.db import models  # noqa: F401
from app.db.session import Base, SessionLocal, engine
from app.db.models import Product
from app.repositories.catalog import seed_catalog


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_production_settings(settings)
    if settings.app_env == "production":
        config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
        expected = ScriptDirectory.from_config(config).get_current_head()
        with engine.connect() as connection:
            actual = MigrationContext.configure(connection).get_current_revision()
        if actual != expected:
            raise RuntimeError(f"Database migration required: expected {expected}, found {actual or 'none'}")
    else:
        Base.metadata.create_all(engine)
    if settings.seed_demo_catalog:
        with SessionLocal() as db:
            if db.query(Product).count() == 0:
                seed_catalog(db)
    yield


settings = get_settings()
allowed_origins = {settings.frontend_url}
if "localhost" in settings.frontend_url:
    allowed_origins.add(settings.frontend_url.replace("localhost", "127.0.0.1"))
app = FastAPI(
    title="JANUS Authorization Gateway",
    version="0.1.0",
    description="Merchant-side authorization boundary for agentic commerce.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(mandates.router)
app.include_router(proposals.router)
app.include_router(audit.router)
app.include_router(catalog.router)
app.include_router(stepups.router)


@app.exception_handler(Exception)
async def fail_closed(_, exc: Exception):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"detail": {"reason_code": "INTERNAL_AUTHORIZATION_ERROR", "message": "Authorization state uncertain; request blocked."}})


@app.get("/health")
def health() -> dict[str, str]:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "janus"}


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="console")
