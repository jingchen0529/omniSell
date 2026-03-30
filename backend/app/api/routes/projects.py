import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.models import User, VideoProject
from app.db.session import get_db
from app.schemas.project import (
    EcommerceAnalysisResponse,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectListItemResponse,
    ProjectRefreshRequest,
    ProjectSourceAnalysisResponse,
    ProjectSourceVisualFeaturesResponse,
    ProjectRenameRequest,
    ProjectScriptOverviewResponse,
    ProjectTaskStepResponse,
    ProjectVideoGenerationResponse,
    TimelineSegmentResponse,
)
from app.services.ai_analysis import analyze_video_script, build_ai_analysis_transcript
from app.services.system_settings import resolve_video_provider_settings
from app.services.video_sources import (
    build_url_source_descriptor,
    derive_source_type,
    extract_source_name,
    is_upload_source,
    resolve_absolute_upload_url,
    resolve_public_upload_url,
    store_reference_asset_file,
    store_reference_audio_file,
    store_upload_file,
)
from app.tasks.queue import queue_project_processing, queue_video_generation
from app.workflows.registry import (
    PROJECT_WORKFLOW_ANALYSIS,
    PROJECT_WORKFLOW_REMAKE,
    build_task_steps,
    normalize_project_workflow_type,
)

router = APIRouter(prefix="/projects")


@router.get("", response_model=list[ProjectListItemResponse], summary="List projects")
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProjectListItemResponse]:
    projects = db.scalars(
        select(VideoProject)
        .where(VideoProject.user_id == current_user.id)
        .order_by(VideoProject.updated_at.desc())
    ).all()
    return [serialize_project_list_item(project) for project in projects]


@router.post("", response_model=ProjectDetailResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectDetailResponse:
    source = build_url_source_descriptor(str(payload.source_url))
    workflow_type = payload.workflow_type
    project = create_project_record(
        db=db,
        user_id=current_user.id,
        title=payload.title,
        objective=payload.objective,
        source_url=source.source_url,
        source_platform=source.source_platform,
        source_name=source.source_name,
        workflow_type=workflow_type,
    )
    queue_project_processing(project.id, workflow_type=workflow_type)
    db.expire_all()
    hydrated_project = get_owned_project(db, current_user.id, project.id)
    return serialize_project_detail(hydrated_project)


@router.post(
    "/upload",
    response_model=ProjectDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project from uploaded video",
)
def create_project_from_upload(
    title: Annotated[str, Form(..., min_length=3, max_length=120)],
    objective: Annotated[str, Form(..., min_length=8, max_length=500)],
    workflow_type: Annotated[str, Form()] = PROJECT_WORKFLOW_ANALYSIS,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectDetailResponse:
    source = store_upload_file(file)
    validated_workflow_type = parse_project_workflow_type(workflow_type)
    project = create_project_record(
        db=db,
        user_id=current_user.id,
        title=title,
        objective=objective,
        source_url=source.source_url,
        source_platform=source.source_platform,
        source_name=source.source_name,
        workflow_type=validated_workflow_type,
    )
    queue_project_processing(project.id, workflow_type=validated_workflow_type)
    db.expire_all()
    hydrated_project = get_owned_project(db, current_user.id, project.id)
    return serialize_project_detail(hydrated_project)


def create_project_record(
    db: Session,
    user_id: int,
    title: str,
    objective: str,
    source_url: str,
    source_platform: str,
    source_name: str,
    workflow_type: str,
) -> VideoProject:
    project = VideoProject(
        user_id=user_id,
        title=title,
        source_url=source_url,
        source_platform=source_platform,
        workflow_type=workflow_type,
        status="processing",
        objective=objective,
        summary="任务已创建，等待后台处理。",
        task_steps=build_task_steps(workflow_type),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectDetailResponse, summary="Get project detail")
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectDetailResponse:
    project = get_owned_project(db, current_user.id, project_id)
    return serialize_project_detail(project)


@router.post("/{project_id}/refresh", response_model=ProjectDetailResponse, summary="Refresh analysis")
def refresh_project(
    project_id: int,
    payload: ProjectRefreshRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectDetailResponse:
    project = get_owned_project(db, current_user.id, project_id)
    objective = payload.objective or project.objective
    workflow_type = payload.workflow_type or project.workflow_type
    workflow_type = parse_project_workflow_type(workflow_type)

    project.objective = objective
    project.workflow_type = workflow_type
    project.status = "processing"
    project.summary = "任务已重新提交，等待后台处理。"
    project.task_steps = build_task_steps(workflow_type)
    db.add(project)
    db.commit()
    queue_project_processing(project.id, workflow_type=workflow_type)
    db.expire_all()
    hydrated_project = get_owned_project(db, current_user.id, project.id)
    return serialize_project_detail(hydrated_project)


@router.post(
    "/{project_id}/retry-ai-analysis",
    response_model=ProjectDetailResponse,
    summary="Retry AI analysis only",
)
def retry_project_ai_analysis(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectDetailResponse:
    project = get_owned_project(db, current_user.id, project_id)
    transcript = build_ai_analysis_transcript(
        project.transcript_segments,
        fallback_text=project.full_text,
    )
    if not transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Project has no transcript content available for AI analysis.",
        )

    project.ai_analysis = analyze_video_script(
        transcript,
        project.objective,
        workflow_type=project.workflow_type,
    )
    db.add(project)
    db.commit()
    hydrated_project = get_owned_project(db, current_user.id, project.id)
    return serialize_project_detail(hydrated_project)


def build_project_processing_detail(
    project: VideoProject,
    *,
    action_label: str,
) -> str:
    pending_step = next(
        (step for step in project.task_steps if step.status == "in_progress"),
        None,
    ) or next(
        (step for step in project.task_steps if step.status == "pending"),
        None,
    )

    message_parts = ["请先等待当前项目处理完成后，再" + action_label + "。"]
    if pending_step is not None:
        message_parts.append(f"未完成步骤：{pending_step.title}。")
        step_detail = (pending_step.detail or "").strip()
        if step_detail:
            message_parts.append(step_detail)

    summary = (project.summary or "").strip()
    if summary and not any(summary in item for item in message_parts):
        message_parts.append(f"当前进度：{summary}")

    return " ".join(message_parts).strip()


@router.post(
    "/{project_id}/remake-video",
    response_model=ProjectDetailResponse,
    summary="Generate remake video",
)
def generate_project_remake_video(
    project_id: int,
    request: Request,
    objective: Annotated[str | None, Form()] = None,
    asset: UploadFile | None = File(default=None),
    audio: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectDetailResponse:
    project = get_owned_project(db, current_user.id, project_id)
    if project.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_project_processing_detail(
                project,
                action_label="执行视频复刻生成",
            ),
        )

    provider_settings = resolve_video_provider_settings()
    if not provider_settings.is_ready:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="视频模型配置未完成，请先到系统设置中配置视频生成服务。",
        )

    if asset is not None:
        stored_asset = store_reference_asset_file(asset)
        project.remake_generation_asset_type = stored_asset.asset_type
        project.remake_generation_asset_name = stored_asset.source_name
        project.remake_generation_asset_url = stored_asset.source_url

    if audio is not None:
        stored_audio = store_reference_audio_file(audio)
        public_base_url = get_settings().public_base_url or str(request.base_url)
        project.remake_generation_audio_name = stored_audio.source_name
        project.remake_generation_audio_url = resolve_absolute_upload_url(
            stored_audio.source_url,
            public_base_url,
        )

    if objective is not None:
        project.remake_generation_objective = objective.strip() or None

    db.add(project)
    db.commit()
    queue_video_generation(project.id)
    db.expire_all()
    hydrated_project = get_owned_project(db, current_user.id, project.id)
    return serialize_project_detail(hydrated_project)


@router.patch("/{project_id}", response_model=ProjectDetailResponse, summary="Rename project")
def rename_project(
    project_id: int,
    payload: ProjectRenameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectDetailResponse:
    project = get_owned_project(db, current_user.id, project_id)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Title cannot be empty.")

    project.title = title
    db.add(project)
    db.commit()
    hydrated_project = get_owned_project(db, current_user.id, project.id)
    return serialize_project_detail(hydrated_project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete project")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    project = get_owned_project(db, current_user.id, project_id)
    db.delete(project)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def get_owned_project(db: Session, user_id: int, project_id: int) -> VideoProject:
    project = db.scalar(
        select(VideoProject)
        .where(VideoProject.id == project_id, VideoProject.user_id == user_id)
        .options(
            selectinload(VideoProject.transcript_segments),
            selectinload(VideoProject.task_steps),
        )
        .limit(1)
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def serialize_project_list_item(project: VideoProject) -> ProjectListItemResponse:
    workflow_type = normalize_project_workflow_type(project.workflow_type)
    return ProjectListItemResponse(
        id=project.id,
        title=project.title,
        source_url=project.source_url,
        source_platform=project.source_platform,
        workflow_type=workflow_type,
        source_type=derive_source_type(project.source_url),
        source_name=extract_source_name(project.source_url),
        status=project.status,
        media_url=project.media_url,
        objective=project.objective,
        summary=project.summary,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def serialize_project_detail(project: VideoProject) -> ProjectDetailResponse:
    analysis_reference_frames = []
    if project.analysis_reference_frames:
        try:
            parsed_frames = json.loads(project.analysis_reference_frames)
            if isinstance(parsed_frames, list):
                analysis_reference_frames = [
                    str(item) for item in parsed_frames if isinstance(item, str)
                ]
        except json.JSONDecodeError:
            analysis_reference_frames = []

    visual_features = None
    if project.analysis_visual_features:
        try:
            parsed_visual_features = json.loads(project.analysis_visual_features)
            if isinstance(parsed_visual_features, dict):
                visual_features = ProjectSourceVisualFeaturesResponse(
                    orientation=parsed_visual_features.get("orientation"),
                    resolution=parsed_visual_features.get("resolution"),
                    frame_rate=parsed_visual_features.get("frame_rate"),
                    keyframe_count=int(parsed_visual_features.get("keyframe_count") or 0),
                    shot_density=parsed_visual_features.get("shot_density"),
                    scene_pace=parsed_visual_features.get("scene_pace"),
                    lighting=parsed_visual_features.get("lighting"),
                    contrast=parsed_visual_features.get("contrast"),
                    saturation=parsed_visual_features.get("saturation"),
                    color_temperature=parsed_visual_features.get("color_temperature"),
                    framing_focus=parsed_visual_features.get("framing_focus"),
                    camera_motion=parsed_visual_features.get("camera_motion"),
                    dominant_palette=[
                        str(item)
                        for item in parsed_visual_features.get("dominant_palette", [])
                        if isinstance(item, str)
                    ],
                    summary=parsed_visual_features.get("summary"),
                )
        except (ValueError, TypeError, json.JSONDecodeError):
            visual_features = None

    reference_frames = []
    if project.remake_generation_reference_frames:
        try:
            parsed_frames = json.loads(project.remake_generation_reference_frames)
            if isinstance(parsed_frames, list):
                reference_frames = [str(item) for item in parsed_frames if isinstance(item, str)]
        except json.JSONDecodeError:
            reference_frames = []

    return ProjectDetailResponse(
        **serialize_project_list_item(project).model_dump(),
        script_overview=ProjectScriptOverviewResponse(
            full_text=project.full_text,
            dialogue_text=project.dialogue_text,
            narration_text=project.narration_text,
            caption_text=project.caption_text,
        ),
        ecommerce_analysis=EcommerceAnalysisResponse(
            title=build_project_analysis_title(project.workflow_type),
            content=project.ai_analysis,
        ),
        source_analysis=ProjectSourceAnalysisResponse(
            reference_frames=analysis_reference_frames,
            visual_features=visual_features,
        ),
        timeline_segments=[
            TimelineSegmentResponse(
                id=segment.id,
                segment_type=segment.segment_type,
                speaker=segment.speaker,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                content=segment.content,
            )
            for segment in project.transcript_segments
        ],
        video_generation=ProjectVideoGenerationResponse(
            status=project.remake_generation_status,
            provider=project.remake_generation_provider,
            model=project.remake_generation_model,
            objective=project.remake_generation_objective,
            asset_type=project.remake_generation_asset_type,
            asset_name=project.remake_generation_asset_name,
            asset_url=(
                resolve_public_upload_url(project.remake_generation_asset_url)
                if project.remake_generation_asset_url
                and is_upload_source(project.remake_generation_asset_url)
                else project.remake_generation_asset_url
            ),
            audio_name=project.remake_generation_audio_name,
            audio_url=project.remake_generation_audio_url,
            reference_frames=reference_frames,
            script=project.remake_generation_script,
            storyboard=project.remake_generation_storyboard,
            prompt=project.remake_generation_prompt,
            provider_task_id=project.remake_generation_task_id,
            result_video_url=project.remake_generation_result_url,
            error_detail=project.remake_generation_error,
            updated_at=project.remake_generation_updated_at,
        ),
        task_steps=[
            ProjectTaskStepResponse(
                id=step.id,
                step_key=step.step_key,
                title=step.title,
                detail=step.detail,
                status=step.status,
                error_detail=step.error_detail,
                display_order=step.display_order,
                updated_at=step.updated_at,
            )
            for step in project.task_steps
        ],
    )


def parse_project_workflow_type(workflow_type: str | None) -> str:
    try:
        return normalize_project_workflow_type(workflow_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="workflow_type 仅支持 analysis、create 或 remake。",
        ) from exc


def build_project_analysis_title(workflow_type: str) -> str:
    normalized = normalize_project_workflow_type(workflow_type)
    if normalized == PROJECT_WORKFLOW_REMAKE:
        return "TikTok Remake Engine 复刻方案"
    return "TikTok 电商效果深度分析"
