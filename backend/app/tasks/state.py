from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    VideoProject,
    VideoProjectJob,
    VideoProjectTaskStep,
    VideoRemakeScene,
    VideoTranscriptSegment,
)
from app.services.video_pipeline import GeneratedProjectAnalysis
from app.workflows.registry import (
    PROJECT_WORKFLOW_STEP_DEFINITIONS,
    build_task_steps,
    build_video_generation_task_steps,
    normalize_project_workflow_type,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def prepare_project_for_processing(db: Session, project: VideoProject) -> None:
    workflow_type = normalize_project_workflow_type(project.workflow_type)
    project.workflow_type = workflow_type
    project.status = "processing"
    project.summary = "任务已创建，正在处理中。"
    project.ai_analysis = None
    project.full_text = ""
    project.dialogue_text = ""
    project.narration_text = ""
    project.caption_text = ""
    project.analysis_reference_frames = None
    project.analysis_visual_features = None
    project.transcript_segments = []
    project.remake_scenes = []

    expected_step_keys = [definition.key for definition in PROJECT_WORKFLOW_STEP_DEFINITIONS[workflow_type]]
    current_step_keys = [step.step_key for step in project.task_steps]
    if not project.task_steps or current_step_keys != expected_step_keys:
        project.task_steps = build_task_steps(workflow_type)

    for step in project.task_steps:
        step.status = "pending"
        step.error_detail = None

    db.add(project)
    db.commit()
    db.refresh(project)


def prepare_project_for_video_generation(db: Session, project: VideoProject) -> None:
    project.status = "processing"
    project.summary = "视频复刻任务已创建，正在处理中。"
    project.remake_generation_status = "processing"
    project.remake_generation_provider = None
    project.remake_generation_model = None
    project.remake_generation_reference_frames = None
    project.remake_generation_script = None
    project.remake_generation_storyboard = None
    project.remake_generation_prompt = None
    project.remake_generation_task_id = None
    project.remake_generation_result_url = None
    project.remake_generation_error = None
    project.remake_generation_updated_at = utcnow()
    project.task_steps = build_video_generation_task_steps()
    db.add(project)
    db.commit()
    db.refresh(project)


def load_project_job_for_processing(db: Session, job_id: int) -> VideoProjectJob | None:
    return db.scalar(
        select(VideoProjectJob)
        .where(VideoProjectJob.id == job_id)
        .options(
            selectinload(VideoProjectJob.project).selectinload(VideoProject.transcript_segments),
            selectinload(VideoProjectJob.project).selectinload(VideoProject.remake_scenes),
            selectinload(VideoProjectJob.project).selectinload(VideoProject.task_steps),
        )
        .limit(1)
    )


def load_project_for_processing(db: Session, project_id: int) -> VideoProject | None:
    return db.scalar(
        select(VideoProject)
        .where(VideoProject.id == project_id)
        .options(
            selectinload(VideoProject.transcript_segments),
            selectinload(VideoProject.remake_scenes),
            selectinload(VideoProject.task_steps),
        )
        .limit(1)
    )


def find_step(project: VideoProject, step_key: str) -> VideoProjectTaskStep:
    for step in project.task_steps:
        if step.step_key == step_key:
            return step
    raise LookupError(f"Task step `{step_key}` not found for project {project.id}.")


def mark_step_in_progress(db: Session, project: VideoProject, step_key: str) -> None:
    step = find_step(project, step_key)
    step.status = "in_progress"
    step.error_detail = None
    db.add(step)
    db.commit()


def complete_step(db: Session, project: VideoProject, step_key: str) -> None:
    step = find_step(project, step_key)
    step.status = "completed"
    step.error_detail = None
    db.add(step)
    db.commit()


def update_project_summary(db: Session, project: VideoProject, summary: str) -> None:
    project.summary = summary
    db.add(project)
    db.commit()


def mark_project_failed(db: Session, project: VideoProject, detail: str) -> None:
    active_step = next(
        (step for step in project.task_steps if step.status == "in_progress"),
        None,
    )
    if active_step is None:
        active_step = next(
            (step for step in project.task_steps if step.status == "pending"),
            None,
        )
    if active_step is not None:
        active_step.status = "failed"
        active_step.error_detail = detail
        db.add(active_step)

    project.status = "failed"
    project.summary = detail
    db.add(project)
    db.commit()


def mark_project_video_generation_failed(db: Session, project: VideoProject, detail: str) -> None:
    active_step = next(
        (step for step in project.task_steps if step.status == "in_progress"),
        None,
    )
    if active_step is None:
        active_step = next(
            (step for step in project.task_steps if step.status == "pending"),
            None,
        )
    if active_step is not None:
        active_step.status = "failed"
        active_step.error_detail = detail
        db.add(active_step)

    project.status = "ready"
    project.summary = detail
    project.remake_generation_status = "failed"
    project.remake_generation_error = detail
    project.remake_generation_updated_at = utcnow()
    db.add(project)
    db.commit()


def apply_analysis_to_project(project: VideoProject, analysis: GeneratedProjectAnalysis) -> None:
    project.title = analysis.title
    project.summary = analysis.summary
    project.ai_analysis = analysis.ai_analysis
    project.full_text = analysis.full_text
    project.dialogue_text = analysis.dialogue_text
    project.narration_text = analysis.narration_text
    project.caption_text = analysis.caption_text
    project.media_url = analysis.media_url
    project.analysis_reference_frames = (
        json.dumps(analysis.reference_frame_urls, ensure_ascii=False)
        if analysis.reference_frame_urls
        else None
    )
    project.analysis_visual_features = (
        json.dumps(asdict(analysis.visual_feature_analysis), ensure_ascii=False)
        if analysis.visual_feature_analysis is not None
        else None
    )
    project.transcript_segments = [
        VideoTranscriptSegment(
            segment_type=segment.segment_type,
            speaker=segment.speaker,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            content=segment.content,
            display_order=segment.display_order,
        )
        for segment in analysis.transcript_segments
    ]
    project.remake_scenes = [
        VideoRemakeScene(
            scene_index=scene.scene_index,
            visual_direction=scene.visual_direction,
            shot_prompt=scene.shot_prompt,
            voiceover=scene.voiceover,
            on_screen_text=scene.on_screen_text,
            editing_notes=scene.editing_notes,
        )
        for scene in analysis.remake_scenes
    ]


__all__ = [
    "apply_analysis_to_project",
    "complete_step",
    "find_step",
    "load_project_for_processing",
    "load_project_job_for_processing",
    "mark_project_failed",
    "mark_project_video_generation_failed",
    "mark_step_in_progress",
    "prepare_project_for_processing",
    "prepare_project_for_video_generation",
    "update_project_summary",
    "utcnow",
]
