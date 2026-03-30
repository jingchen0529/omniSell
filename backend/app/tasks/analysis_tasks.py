from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.db.models import VideoProject, VideoProjectJob
from app.services.media_tools import VideoAnalysisError, collect_media_analysis
from app.services.video_pipeline import build_mock_project_analysis, build_real_project_analysis
from app.services.video_sources import extract_source_name, is_upload_source
from app.tasks.state import (
    apply_analysis_to_project,
    complete_step,
    load_project_for_processing,
    load_project_job_for_processing,
    mark_step_in_progress,
    prepare_project_for_processing,
    update_project_summary,
)


def process_project_content_job(
    db: Session,
    project: VideoProject,
    job: VideoProjectJob,
    *,
    worker_id: str,
    renew_job_lease,
    settings_provider,
) -> None:
    prepare_project_for_processing(db, project)
    project = load_project_for_processing(db, project.id)
    job = load_project_job_for_processing(db, job.id)
    if project is None or job is None:
        return

    run_extract_video_link_step(db, project)
    run_validate_video_link_step(db, project)

    settings = settings_provider()
    if settings.video_analysis_provider.strip().lower() == "mock":
        analysis = run_mock_analysis_steps(db, project)
    else:
        analysis = run_real_analysis_steps(
            db,
            project,
            job,
            worker_id=worker_id,
            renew_job_lease=renew_job_lease,
        )

    run_generate_suggestions_step(db, project, analysis)
    complete_step(db, project, "finish")


def run_extract_video_link_step(db: Session, project: VideoProject) -> None:
    complete_step(db, project, "extract_video_link")


def run_validate_video_link_step(db: Session, project: VideoProject) -> None:
    validate_project_source(project)
    complete_step(db, project, "validate_video_link")


def run_mock_analysis_steps(db: Session, project: VideoProject):
    complete_step(db, project, "analyze_video_content")
    complete_step(db, project, "identify_audio_content")
    complete_step(db, project, "generate_response")
    update_project_summary(db, project, "正在整理建议内容。")
    return build_mock_project_analysis(
        source_url=project.source_url,
        title=project.title,
        objective=project.objective,
        source_platform=project.source_platform,
        source_name=extract_source_name(project.source_url),
        workflow_type=project.workflow_type,
    )


def run_real_analysis_steps(
    db: Session,
    project: VideoProject,
    job: VideoProjectJob,
    *,
    worker_id: str,
    renew_job_lease,
):
    renew_job_lease(db, job, worker_id=worker_id)
    mark_step_in_progress(db, project, "analyze_video_content")
    update_project_summary(db, project, "正在分析视频内容。")

    def handle_media_progress(stage_key: str) -> None:
        if stage_key != "identify_audio_content":
            return
        complete_step(db, project, "analyze_video_content")
        mark_step_in_progress(db, project, "identify_audio_content")
        update_project_summary(db, project, "正在识别音频内容。")
        renew_job_lease(db, job, worker_id=worker_id)

    media_analysis = collect_media_analysis(
        project.source_url,
        progress_callback=handle_media_progress,
    )
    complete_step(db, project, "analyze_video_content")
    complete_step(db, project, "identify_audio_content")

    renew_job_lease(db, job, worker_id=worker_id)
    mark_step_in_progress(db, project, "generate_response")
    update_project_summary(db, project, "正在生成结构化回复。")
    analysis = build_real_project_analysis(
        title=project.title,
        objective=project.objective,
        source_platform=project.source_platform,
        source_name=extract_source_name(project.source_url),
        media_analysis=media_analysis,
        workflow_type=project.workflow_type,
    )
    complete_step(db, project, "generate_response")
    return analysis


def run_generate_suggestions_step(db: Session, project: VideoProject, analysis) -> None:
    mark_step_in_progress(db, project, "generate_suggestions")
    update_project_summary(db, project, "正在整理建议内容。")
    apply_analysis_to_project(project, analysis)
    db.add(project)
    db.commit()
    db.refresh(project)

    complete_step(db, project, "generate_suggestions")
    project.status = "ready"
    project.summary = analysis.summary
    db.add(project)
    db.commit()


def validate_project_source(project: VideoProject) -> None:
    if is_upload_source(project.source_url):
        return

    parsed = urlparse(project.source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise VideoAnalysisError("视频链接无效，请提供可访问的 http 或 https 地址。")


__all__ = [
    "build_mock_project_analysis",
    "build_real_project_analysis",
    "collect_media_analysis",
    "process_project_content_job",
    "validate_project_source",
]
