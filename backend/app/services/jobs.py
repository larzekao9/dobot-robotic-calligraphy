"""Creación de rutas y ejecución de trabajos (cola de un solo robot)."""

import logging
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.models import Glyph, GlyphScript, Job, JobStatus, Request, Script
from app.schemas.jobs import Layout, PathPreview
from app.services.robot.base import Command, RobotDriver, RobotStopped
from app.services.robot.config import load_config
from app.services.robot.dobot_driver import DobotDriver
from app.services.robot.mock_driver import MockDriver
from app.services.strokes import (
    air_path,
    build_commands,
    estimate_seconds,
    fit_char_size,
    place_text,
    preview_strokes,
    split_words,
)

log = logging.getLogger(__name__)


def resolve_text(db: Session, request_id: uuid.UUID, script: Script, rank: int) -> str:
    req = db.get(Request, request_id)
    if req is None:
        raise AppError("request_not_found", "No existe esa consulta.", 404)
    options = req.result_json.get(script.value, [])
    if not 1 <= rank <= len(options):
        raise AppError("invalid_rank", f"No existe la opción {rank} para {script.value}.", 422)
    return str(options[rank - 1]["text"])


def _glyph_lookup(db: Session, script: Script) -> Callable[[str], list[list[list[float]]]]:
    glyph_script = GlyphScript.zh if script == Script.zh else GlyphScript.ja_kana

    def lookup(char: str) -> list[list[list[float]]]:
        glyph = db.scalar(select(Glyph).where(Glyph.script == glyph_script, Glyph.char == char))
        if glyph is None:
            raise AppError("glyph_not_found", f"No hay trazos para «{char}».", 422)
        return glyph.strokes_json  # type: ignore[no-any-return]

    return lookup


def compute_path(db: Session, text: str, script: Script, layout: Layout) -> list[Command]:
    return build_commands(place_text(text, _glyph_lookup(db, script), layout), layout)


def make_preview(text: str, script: Script, layout: Layout, path: list[Command]) -> PathPreview:
    width, height = layout.paper_size()
    strokes = preview_strokes(path)
    return PathPreview(
        text=text,
        script=script,
        layout=layout,
        paper_width_mm=width,
        paper_height_mm=height,
        char_size_mm=fit_char_size(split_words(text), layout),
        strokes=strokes,
        stroke_count=len(strokes),
        char_count=len("".join(split_words(text))),
        estimated_seconds=round(estimate_seconds(path), 1),
    )


def make_driver() -> RobotDriver:
    """Lee la configuración en cada trabajo: cambiar de simulador a robot no requiere reiniciar."""
    cfg = load_config()
    if cfg.driver == "dobot":
        return DobotDriver(cfg)
    return MockDriver(time_scale=settings.mock_time_scale)


class JobRunner:
    """Cola serie (un robot, un trabajo a la vez). El progreso vive en memoria."""

    def __init__(
        self, session_factory: Callable[[], Session], driver_factory: Callable[[], RobotDriver]
    ) -> None:
        self._session_factory = session_factory
        self._driver_factory = driver_factory
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="robot")
        self._futures: dict[uuid.UUID, Future[None]] = {}
        self._drivers: dict[uuid.UUID, RobotDriver] = {}
        self.progress: dict[uuid.UUID, float] = {}

    def submit(self, job_id: uuid.UUID, *, dry_run: bool = False) -> None:
        self._futures[job_id] = self._executor.submit(self._run, job_id, dry_run)

    def stop(self, job_id: uuid.UUID) -> None:
        driver = self._drivers.get(job_id)
        if driver is not None:
            driver.stop()

    def wait(self, job_id: uuid.UUID, timeout: float | None = 10.0) -> None:
        future = self._futures.get(job_id)
        if future is not None:
            future.result(timeout=timeout)

    def _run(self, job_id: uuid.UUID, dry_run: bool = False) -> None:
        with self._session_factory() as db:
            job = db.get(Job, job_id)
            if job is None or job.status != JobStatus.queued:
                return  # cancelado mientras esperaba en la cola
            job.status = JobStatus.running
            job.started_at = datetime.now(UTC)
            db.commit()
            driver = self._driver_factory()
            self._drivers[job_id] = driver
            outcome, error = JobStatus.done, None
            try:
                driver.connect()
                driver.home()
                path = air_path(job.path_json or []) if dry_run else job.path_json or []
                driver.execute(path, lambda p: self.progress.__setitem__(job_id, p))
            except RobotStopped:
                outcome = JobStatus.cancelled
            except Exception as exc:
                log.exception("job_failed", extra={"job_id": str(job_id)})
                outcome, error = JobStatus.failed, str(exc) or exc.__class__.__name__
            finally:
                try:
                    driver.disconnect()
                finally:
                    self._drivers.pop(job_id, None)
            db.refresh(job)
            if job.status == JobStatus.running:  # si ya está cancelado, se respeta
                job.status, job.error = outcome, error
            if job.status == JobStatus.done:
                self.progress[job_id] = 1.0
            job.finished_at = job.finished_at or datetime.now(UTC)
            db.commit()


@lru_cache
def get_runner() -> JobRunner:
    from app.db import SessionLocal

    return JobRunner(SessionLocal, make_driver)


def fail_interrupted_jobs(db: Session) -> int:
    """Al arrancar: lo que estaba en cola o escribiendo ya no se puede reanudar."""
    jobs = db.scalars(select(Job).where(Job.status.in_([JobStatus.queued, JobStatus.running])))
    n = 0
    for job in jobs:
        job.status, job.error = JobStatus.failed, "Interrumpido por el reinicio del servidor."
        job.finished_at = datetime.now(UTC)
        n += 1
    db.commit()
    return n
