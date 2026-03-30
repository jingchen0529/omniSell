from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import VideoProject, VideoProjectJob
from app.services.media_tools import encode_image_file_as_data_url, extract_scene_reference_frames
from app.services.system_settings import resolve_video_provider_settings
from app.services.video_generation import (
    VideoGenerationError,
    build_video_generation_blueprint,
    generate_video_with_provider,
)
from app.services.video_sources import (
    is_image_filename,
    is_video_filename,
    resolve_public_upload_url,
    resolve_upload_path,
    store_generated_public_file,
)
from app.tasks.state import (
    complete_step,
    load_project_for_processing,
    load_project_job_for_processing,
    mark_step_in_progress,
    prepare_project_for_video_generation,
    update_project_summary,
    utcnow,
)


def process_video_generation_job(
    db: Session,
    project: VideoProject,
    job: VideoProjectJob,
    *,
    worker_id: str,
    renew_job_lease,
) -> None:
    prepare_project_for_video_generation(db, project)
    project = load_project_for_processing(db, project.id)
    job = load_project_job_for_processing(db, job.id)
    if project is None or job is None:
        return

    asset_type, asset_name, reference_images, reference_frame_urls = run_prepare_reference_asset_step(
        db,
        project,
        job,
        worker_id=worker_id,
        renew_job_lease=renew_job_lease,
    )
    blueprint = run_build_video_prompt_step(
        db,
        project,
        job,
        worker_id=worker_id,
        renew_job_lease=renew_job_lease,
        asset_type=asset_type,
        asset_name=asset_name,
        reference_images=reference_images,
    )
    result = run_submit_video_generation_step(
        db,
        project,
        job,
        worker_id=worker_id,
        renew_job_lease=renew_job_lease,
        blueprint_prompt=blueprint.prompt,
        reference_images=reference_images,
        audio_url=(project.remake_generation_audio_url or "").strip() or None,
    )
    run_poll_video_generation_step(
        db,
        project,
        job,
        worker_id=worker_id,
        renew_job_lease=renew_job_lease,
        result=result,
    )
    complete_step(db, project, "finish")


def run_prepare_reference_asset_step(
    db: Session,
    project: VideoProject,
    job: VideoProjectJob,
    *,
    worker_id: str,
    renew_job_lease,
) -> tuple[str, str, list[str], list[str]]:
    renew_job_lease(db, job, worker_id=worker_id)
    mark_step_in_progress(db, project, "prepare_reference_asset")
    update_project_summary(db, project, "正在准备复刻素材。")
    asset_type, asset_name, reference_images, reference_frame_urls = build_reference_images_for_project(project)
    complete_step(db, project, "prepare_reference_asset")

    mark_step_in_progress(db, project, "analyze_reference_asset")
    update_project_summary(
        db,
        project,
        "正在分析参考素材并整理生成输入。"
        if asset_type == "text"
        else "正在分析参考素材并抽帧。",
    )
    project.remake_generation_asset_type = asset_type
    project.remake_generation_asset_name = asset_name
    project.remake_generation_reference_frames = json.dumps(reference_frame_urls, ensure_ascii=False)
    project.remake_generation_updated_at = utcnow()
    db.add(project)
    db.commit()
    complete_step(db, project, "analyze_reference_asset")
    return asset_type, asset_name, reference_images, reference_frame_urls


def run_build_video_prompt_step(
    db: Session,
    project: VideoProject,
    job: VideoProjectJob,
    *,
    worker_id: str,
    renew_job_lease,
    asset_type: str,
    asset_name: str,
    reference_images: list[str],
):
    renew_job_lease(db, job, worker_id=worker_id)
    mark_step_in_progress(db, project, "build_video_prompt")
    update_project_summary(db, project, "正在生成脚本、分镜和提示词。")
    blueprint = build_video_generation_blueprint(
        project,
        objective=project.remake_generation_objective,
        reference_asset_type=asset_type,
        reference_asset_name=asset_name,
        reference_frame_count=len(reference_images),
    )
    project.remake_generation_script = blueprint.script
    project.remake_generation_storyboard = blueprint.storyboard
    project.remake_generation_prompt = blueprint.prompt
    db.add(project)
    db.commit()
    complete_step(db, project, "build_video_prompt")
    return blueprint


def run_submit_video_generation_step(
    db: Session,
    project: VideoProject,
    job: VideoProjectJob,
    *,
    worker_id: str,
    renew_job_lease,
    blueprint_prompt: str,
    reference_images: list[str],
    audio_url: str | None,
):
    renew_job_lease(db, job, worker_id=worker_id)
    mark_step_in_progress(db, project, "submit_video_generation")
    update_project_summary(db, project, "正在提交视频生成任务。")
    provider_settings = resolve_video_provider_settings()
    if not provider_settings.is_ready:
        raise VideoGenerationError("视频生成配置未完成，请先在系统设置中补全视频模型配置。", status_code=503)

    result = generate_video_with_provider(
        provider_settings=provider_settings,
        prompt=blueprint_prompt,
        reference_images=reference_images,
        audio_url=audio_url,
    )
    project.remake_generation_provider = provider_settings.provider
    project.remake_generation_model = (
        provider_settings.image_to_video_model
        if reference_images
        else provider_settings.text_to_video_model
        or provider_settings.model
    )
    project.remake_generation_task_id = result.task_id
    project.remake_generation_status = "processing"
    db.add(project)
    db.commit()
    complete_step(db, project, "submit_video_generation")
    return result


def run_poll_video_generation_step(
    db: Session,
    project: VideoProject,
    job: VideoProjectJob,
    *,
    worker_id: str,
    renew_job_lease,
    result,
) -> None:
    renew_job_lease(db, job, worker_id=worker_id)
    mark_step_in_progress(db, project, "poll_video_generation")
    update_project_summary(db, project, "正在等待视频生成结果。")
    project.remake_generation_status = "ready"
    project.remake_generation_result_url = result.video_url
    project.remake_generation_error = result.error_detail
    project.remake_generation_updated_at = utcnow()
    project.status = "ready"
    project.summary = "视频复刻已生成完成。"
    db.add(project)
    db.commit()
    complete_step(db, project, "poll_video_generation")


def build_reference_images_for_project(project: VideoProject) -> tuple[str, str, list[str], list[str]]:
    asset_url = (project.remake_generation_asset_url or "").strip()
    if not asset_url:
        return (
            "text",
            "未上传产品素材，按复刻脚本直接生成",
            [],
            [],
        )

    asset_path = resolve_upload_path(asset_url)
    asset_name = project.remake_generation_asset_name or asset_path.name
    if is_image_filename(asset_name):
        return "image", asset_name, [encode_image_file_as_data_url(asset_path)], [resolve_public_upload_url(asset_url)]

    if not is_video_filename(asset_name):
        raise VideoGenerationError("当前仅支持图片或视频类型的产品素材。", status_code=422)

    settings = get_settings()
    settings.media_work_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=settings.media_work_root) as temp_dir_name:
        frame_paths = extract_scene_reference_frames(asset_path, Path(temp_dir_name))
        reference_images = [encode_image_file_as_data_url(frame_path) for frame_path in frame_paths]
        reference_frame_urls = [
            store_generated_public_file(
                frame_path,
                category="reference-frames",
                source_name=f"{Path(asset_name).stem}-frame-{index + 1}{frame_path.suffix.lower()}",
            )
            for index, frame_path in enumerate(frame_paths)
        ]
    if not reference_images:
        raise VideoGenerationError("未能从上传的视频中抽取到有效关键帧。", status_code=422)
    return "video", asset_name, reference_images, reference_frame_urls


__all__ = [
    "build_reference_images_for_project",
    "generate_video_with_provider",
    "process_video_generation_job",
]
