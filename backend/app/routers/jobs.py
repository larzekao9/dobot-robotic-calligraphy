import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import Job, JobStatus
from app.schemas.jobs import JobCreate, JobDetail, JobOut, Layout, PathPreview
from app.services.jobs import (
    JobRunner,
    compute_path,
    get_runner,
    make_preview,
    resolve_text,
)
from app.services.strokes import estimate_seconds

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
DB = Annotated[Session, Depends(get_db)]
Runner = Annotated[JobRunner, Depends(get_runner)]
_CANCELLABLE = {JobStatus.draft, JobStatus.queued, JobStatus.running}


def _get(db: Session, job_id: uuid.UUID) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise AppError("job_not_found", "No existe ese trabajo.", 404)
    return job


def _progress(job: Job, runner: JobRunner) -> float:
    if job.status == JobStatus.done:
        return 1.0
    return runner.progress.get(job.id, 0.0) if job.status == JobStatus.running else 0.0


def _out(job: Job, runner: JobRunner, *, detail: bool = False) -> JobOut:
    base = JobOut(
        id=job.id,
        request_id=job.request_id,
        script=job.script,
        text=job.text,
        status=job.status,
        progress=_progress(job, runner),
        layout=Layout.model_validate(job.layout_json),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
    )
    if not detail:
        return base
    path = job.path_json or []
    return JobDetail(
        **{**base.model_dump(), "path": path, "estimated_seconds": round(estimate_seconds(path), 1)}
    )


@router.post("/preview")
def preview_layout(body: JobCreate, db: DB) -> PathPreview:
    """Vista previa sin guardar nada: para ajustar la disposición antes de crear el trabajo."""
    text = resolve_text(db, body.request_id, body.script, body.rank)
    path = compute_path(db, text, body.script, body.layout)
    return make_preview(text, body.script, body.layout, path)


@router.post("", status_code=201)
def create_job(body: JobCreate, db: DB, runner: Runner) -> JobDetail:
    text = resolve_text(db, body.request_id, body.script, body.rank)
    path = compute_path(db, text, body.script, body.layout)
    job = Job(
        request_id=body.request_id,
        script=body.script,
        text=text,
        layout_json=body.layout.model_dump(mode="json"),
        path_json=path,
        status=JobStatus.draft,
    )
    db.add(job)
    db.commit()
    out = _out(job, runner, detail=True)
    assert isinstance(out, JobDetail)
    return out


@router.get("")
def list_jobs(db: DB, runner: Runner, limit: int = 50) -> list[JobOut]:
    stmt = select(Job).order_by(Job.created_at.desc()).limit(max(1, min(limit, 200)))
    return [_out(j, runner) for j in db.scalars(stmt)]


@router.get("/{job_id}")
def get_job(job_id: uuid.UUID, db: DB, runner: Runner) -> JobDetail:
    out = _out(_get(db, job_id), runner, detail=True)
    assert isinstance(out, JobDetail)
    return out


@router.post("/{job_id}/preview")
def preview_job(job_id: uuid.UUID, db: DB) -> PathPreview:
    job = _get(db, job_id)
    return make_preview(
        job.text, job.script, Layout.model_validate(job.layout_json), job.path_json or []
    )


@router.post("/{job_id}/start")
def start_job(job_id: uuid.UUID, db: DB, runner: Runner, dry_run: bool = False) -> JobOut:
    """Lo ejecuta el driver configurado (simulador o MG400). `dry_run`: recorre todo con la pluma arriba."""
    job = _get(db, job_id)
    if job.status != JobStatus.draft:
        raise AppError("invalid_state", "Solo se pueden iniciar trabajos en borrador.", 409)
    job.status = JobStatus.queued
    db.commit()
    runner.submit(job.id, dry_run=dry_run)
    return _out(job, runner)


@router.post("/{job_id}/cancel")
def cancel_job(job_id: uuid.UUID, db: DB, runner: Runner) -> JobOut:
    job = _get(db, job_id)
    if job.status not in _CANCELLABLE:
        raise AppError("invalid_state", "Este trabajo ya terminó y no se puede cancelar.", 409)
    was_running = job.status == JobStatus.running
    job.status = JobStatus.cancelled
    job.finished_at = datetime.now(UTC)
    db.commit()
    if was_running:
        runner.stop(job.id)
    return _out(job, runner)
