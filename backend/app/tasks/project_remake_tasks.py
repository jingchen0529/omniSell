from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import VideoProject, VideoProjectJob
from app.services.media_tools import collect_media_analysis
from app.services.video_pipeline import build_mock_project_analysis, build_real_project_analysis
from app.services.video_sources import extract_source_name
from app.tasks.analysis_tasks import validate_project_source
from app.tasks.state import (
    apply_analysis_to_project,
    complete_step,
    load_project_for_processing,
    load_project_job_for_processing,
    mark_step_in_progress,
    prepare_project_for_processing,
    update_project_summary,
)
from app.workflows.remake_project_workflow import PROJECT_WORKFLOW_REMAKE

REMAKE_STEP_MESSAGES = {
    "visual_breakdown": "正在执行视觉拆解。",
    "timing_and_structure": "正在整理节奏与结构。",
    "viral_logic_extraction": "正在提取爆点逻辑。",
    "content_carrier_analysis": "正在分析商品承载方式。",
    "remake_plan_generation": "正在生成复刻执行方案。",
    "variation_strategy_generation": "正在生成变体策略。",
}


def process_project_remake_job(
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

    validate_project_source(project)

    renew_job_lease(db, job, worker_id=worker_id)
    mark_step_in_progress(db, project, "visual_breakdown")
    update_project_summary(db, project, REMAKE_STEP_MESSAGES["visual_breakdown"])

    settings = settings_provider()
    if settings.video_analysis_provider.strip().lower() == "mock":
        analysis = build_mock_project_analysis(
            source_url=project.source_url,
            title=project.title,
            objective=project.objective,
            source_platform=project.source_platform,
            source_name=extract_source_name(project.source_url),
            workflow_type=PROJECT_WORKFLOW_REMAKE,
        )
    else:
        media_analysis = collect_media_analysis(project.source_url)
        renew_job_lease(db, job, worker_id=worker_id)
        analysis = build_real_project_analysis(
            title=project.title,
            objective=project.objective,
            source_platform=project.source_platform,
            source_name=extract_source_name(project.source_url),
            media_analysis=media_analysis,
            workflow_type=PROJECT_WORKFLOW_REMAKE,
        )

    complete_step(db, project, "visual_breakdown")
    advance_remake_step(db, project, "timing_and_structure")
    advance_remake_step(db, project, "viral_logic_extraction")
    advance_remake_step(db, project, "content_carrier_analysis")

    mark_step_in_progress(db, project, "remake_plan_generation")
    update_project_summary(db, project, REMAKE_STEP_MESSAGES["remake_plan_generation"])
    apply_analysis_to_project(project, analysis)
    db.add(project)
    db.commit()
    db.refresh(project)
    complete_step(db, project, "remake_plan_generation")

    advance_remake_step(db, project, "variation_strategy_generation")
    complete_step(db, project, "finish")

    project.status = "ready"
    project.summary = analysis.summary
    db.add(project)
    db.commit()


def advance_remake_step(db: Session, project: VideoProject, step_key: str) -> None:
    mark_step_in_progress(db, project, step_key)
    update_project_summary(db, project, REMAKE_STEP_MESSAGES[step_key])
    complete_step(db, project, step_key)


__all__ = ["process_project_remake_job"]
