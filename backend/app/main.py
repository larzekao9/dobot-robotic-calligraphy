import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.db import SessionLocal
from app.errors import register_error_handlers
from app.routers import admin, glyphs, jobs, names, requests, robot
from app.services.jobs import fail_interrupted_jobs

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        with SessionLocal() as db:
            n = fail_interrupted_jobs(db)
        if n:
            log.warning("interrupted_jobs_marked_failed", extra={"count": n})
    except OperationalError:
        log.warning("db_not_ready: ejecuta `alembic upgrade head`")
    yield


app = FastAPI(title="Nombres Pincel", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)
app.include_router(names.router)
app.include_router(glyphs.router)
app.include_router(jobs.router)
app.include_router(requests.router)
app.include_router(admin.router)
app.include_router(robot.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
