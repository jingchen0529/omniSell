from __future__ import annotations

import os
import socket
import time
from datetime import timedelta
from threading import Event

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import VideoProjectJob
from app.db.session import get_session_factory
from app.services.media_tools import VideoAnalysisError
from app.services.video_generation import VideoGenerationError
from app.tasks.analysis_tasks import process_project_content_job
from app.tasks.project_remake_tasks import process_project_remake_job
from app.tasks.remake_tasks import process_video_generation_job
from app.tasks.state import (
    load_project_for_processing,
    load_project_job_for_processing,
    mark_project_failed,
    mark_project_video_generation_failed,
    utcnow,
)
from app.workflows.registry import (
    PROJECT_ANALYSIS_JOB_TYPE,
    PROJECT_CREATE_JOB_TYPE,
    PROJECT_REMAKE_JOB_TYPE,
    PROJECT_WORKFLOW_ANALYSIS,
    VIDEO_GENERATION_JOB_TYPE,
    get_project_job_type,
)

JOB_STATUS_QUEUED = "queued"
JOB_STATUS_LEASED = "leased"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_SUCCEEDED = "succeeded"
JOB_STATUS_FAILED = "failed"


def build_worker_id() -> str:
    settings = get_settings()
    configured_worker_id = (settings.project_job_worker_id or "").strip()
    if configured_worker_id:
        return configured_worker_id
    return f"{socket.gethostname()}:{os.getpid()}"


def queue_project_processing(project_id: int, *, workflow_type: str = PROJECT_WORKFLOW_ANALYSIS) -> int:
    return queue_project_job(project_id, job_type=get_project_job_type(workflow_type))


def queue_video_generation(project_id: int) -> int:
    return queue_project_job(project_id, job_type=VIDEO_GENERATION_JOB_TYPE)


def queue_project_job(project_id: int, *, job_type: str) -> int:
    settings = get_settings()
    session_factory = get_session_factory()

    with session_factory() as db:
        job = db.scalar(
            select(VideoProjectJob)
            .where(
                VideoProjectJob.project_id == project_id,
                VideoProjectJob.job_type == job_type,
                VideoProjectJob.status.in_(
                    (
                        JOB_STATUS_QUEUED,
                        JOB_STATUS_LEASED,
                        JOB_STATUS_RUNNING,
                    )
                ),
            )
            .order_by(VideoProjectJob.created_at.desc())
            .limit(1)
        )
        if job is None:
            job = VideoProjectJob(
                project_id=project_id,
                job_type=job_type,
                status=JOB_STATUS_QUEUED,
                max_attempts=settings.project_job_max_attempts,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
        job_id = job.id

    if settings.app_env == "test":
        process_project_job(job_id, worker_id=f"inline-test:{os.getpid()}")

    return job_id


def claim_next_project_job(worker_id: str | None = None) -> int | None:
    worker_id = worker_id or build_worker_id()
    settings = get_settings()
    session_factory = get_session_factory()
    now = utcnow()
    lease_expires_at = now + timedelta(seconds=settings.project_job_lease_seconds)

    with session_factory() as db:
        candidate_ids = db.scalars(
            select(VideoProjectJob.id)
            .where(
                VideoProjectJob.job_type.in_(
                    (
                        PROJECT_ANALYSIS_JOB_TYPE,
                        PROJECT_CREATE_JOB_TYPE,
                        PROJECT_REMAKE_JOB_TYPE,
                        VIDEO_GENERATION_JOB_TYPE,
                    )
                ),
                or_(
                    VideoProjectJob.status == JOB_STATUS_QUEUED,
                    and_(
                        VideoProjectJob.status.in_((JOB_STATUS_LEASED, JOB_STATUS_RUNNING)),
                        VideoProjectJob.lease_expires_at.is_not(None),
                        VideoProjectJob.lease_expires_at <= now,
                    ),
                ),
            )
            .order_by(VideoProjectJob.created_at.asc(), VideoProjectJob.id.asc())
        ).all()

        for candidate_id in candidate_ids:
            result = db.execute(
                update(VideoProjectJob)
                .where(VideoProjectJob.id == candidate_id)
                .where(
                    or_(
                        VideoProjectJob.status == JOB_STATUS_QUEUED,
                        and_(
                            VideoProjectJob.status.in_((JOB_STATUS_LEASED, JOB_STATUS_RUNNING)),
                            VideoProjectJob.lease_expires_at.is_not(None),
                            VideoProjectJob.lease_expires_at <= now,
                        ),
                    )
                )
                .values(
                    status=JOB_STATUS_LEASED,
                    worker_id=worker_id,
                    lease_expires_at=lease_expires_at,
                    error_detail=None,
                    updated_at=now,
                )
            )
            if result.rowcount:
                db.commit()
                return candidate_id
            db.rollback()

    return None


def renew_project_job_lease(
    db: Session,
    job: VideoProjectJob,
    *,
    worker_id: str,
) -> None:
    job.worker_id = worker_id
    job.lease_expires_at = utcnow() + timedelta(seconds=get_settings().project_job_lease_seconds)
    db.add(job)
    db.commit()
    db.refresh(job)


def mark_project_job_running(
    db: Session,
    job: VideoProjectJob,
    *,
    worker_id: str,
) -> None:
    job.status = JOB_STATUS_RUNNING
    job.worker_id = worker_id
    job.attempt += 1
    job.started_at = utcnow()
    job.finished_at = None
    job.error_detail = None
    job.lease_expires_at = utcnow() + timedelta(seconds=get_settings().project_job_lease_seconds)
    db.add(job)
    db.commit()
    db.refresh(job)


def mark_project_job_succeeded(db: Session, job: VideoProjectJob, *, worker_id: str) -> None:
    job.status = JOB_STATUS_SUCCEEDED
    job.worker_id = worker_id
    job.finished_at = utcnow()
    job.error_detail = None
    job.lease_expires_at = None
    db.add(job)
    db.commit()


def mark_project_job_failed(
    db: Session,
    job: VideoProjectJob,
    detail: str,
    *,
    worker_id: str,
) -> None:
    job.status = JOB_STATUS_FAILED
    job.worker_id = worker_id
    job.finished_at = utcnow()
    job.error_detail = detail
    job.lease_expires_at = None
    db.add(job)
    db.commit()


def process_next_project_job(worker_id: str | None = None) -> bool:
    job_id = claim_next_project_job(worker_id=worker_id)
    if job_id is None:
        return False

    process_project_job(job_id, worker_id=worker_id)
    return True


def run_project_worker(
    *,
    worker_id: str | None = None,
    max_jobs: int | None = None,
    poll_interval: float | None = None,
    stop_event: Event | None = None,
) -> None:
    worker_id = worker_id or build_worker_id()
    poll_interval = (
        get_settings().project_job_poll_interval_seconds if poll_interval is None else poll_interval
    )
    processed_jobs = 0

    while True:
        if stop_event is not None and stop_event.is_set():
            break
        if max_jobs is not None and processed_jobs >= max_jobs:
            break
        processed = process_next_project_job(worker_id=worker_id)
        if processed:
            processed_jobs += 1
            continue
        sleep_seconds = max(poll_interval, 0.1)
        if stop_event is not None:
            if stop_event.wait(sleep_seconds):
                break
            continue
        time.sleep(sleep_seconds)


def process_project_job(job_id: int, worker_id: str | None = None) -> None:
    worker_id = worker_id or build_worker_id()
    session_factory = get_session_factory()

    with session_factory() as db:
        job = load_project_job_for_processing(db, job_id)
        if job is None:
            return

        project = job.project
        if project is None:
            mark_project_job_failed(db, job, "任务对应的项目不存在。", worker_id=worker_id)
            return

        mark_project_job_running(db, job, worker_id=worker_id)
        project_id = project.id
        stored_job_id = job.id
        job_type = job.job_type

        try:
            if job_type in (PROJECT_ANALYSIS_JOB_TYPE, PROJECT_CREATE_JOB_TYPE):
                process_project_content_job(
                    db,
                    project,
                    job,
                    worker_id=worker_id,
                    renew_job_lease=renew_project_job_lease,
                    settings_provider=get_settings,
                )
            elif job_type == PROJECT_REMAKE_JOB_TYPE:
                process_project_remake_job(
                    db,
                    project,
                    job,
                    worker_id=worker_id,
                    renew_job_lease=renew_project_job_lease,
                    settings_provider=get_settings,
                )
            elif job_type == VIDEO_GENERATION_JOB_TYPE:
                process_video_generation_job(
                    db,
                    project,
                    job,
                    worker_id=worker_id,
                    renew_job_lease=renew_project_job_lease,
                )
            else:
                raise VideoAnalysisError(f"未知任务类型：{job_type}")
            job = load_project_job_for_processing(db, stored_job_id)
            if job is None:
                return
            mark_project_job_succeeded(db, job, worker_id=worker_id)
        except VideoAnalysisError as exc:
            db.rollback()
            job = load_project_job_for_processing(db, stored_job_id)
            project = load_project_for_processing(db, project_id)
            if project is None or job is None:
                return
            mark_project_failed(db, project, exc.detail)
            mark_project_job_failed(db, job, exc.detail, worker_id=worker_id)
        except VideoGenerationError as exc:
            db.rollback()
            job = load_project_job_for_processing(db, stored_job_id)
            project = load_project_for_processing(db, project_id)
            if project is None or job is None:
                return
            mark_project_video_generation_failed(db, project, exc.detail)
            mark_project_job_failed(db, job, exc.detail, worker_id=worker_id)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            detail = f"任务处理失败：{str(exc).strip() or exc.__class__.__name__}"
            job = load_project_job_for_processing(db, stored_job_id)
            project = load_project_for_processing(db, project_id)
            if project is None or job is None:
                return
            if job_type == VIDEO_GENERATION_JOB_TYPE:
                mark_project_video_generation_failed(db, project, detail)
            else:
                mark_project_failed(db, project, detail)
            mark_project_job_failed(db, job, detail, worker_id=worker_id)


__all__ = [
    "JOB_STATUS_FAILED",
    "JOB_STATUS_LEASED",
    "JOB_STATUS_QUEUED",
    "JOB_STATUS_RUNNING",
    "JOB_STATUS_SUCCEEDED",
    "build_worker_id",
    "process_next_project_job",
    "process_project_job",
    "queue_project_processing",
    "queue_video_generation",
    "renew_project_job_lease",
    "run_project_worker",
    "utcnow",
]
