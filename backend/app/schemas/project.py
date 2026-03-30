from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

ProjectWorkflowType = Literal["analysis", "create", "remake"]


class ProjectScriptOverviewResponse(BaseModel):
    full_text: str
    dialogue_text: str
    narration_text: str
    caption_text: str


class TimelineSegmentResponse(BaseModel):
    id: int
    segment_type: str
    speaker: str | None
    start_ms: int
    end_ms: int
    content: str


class EcommerceAnalysisResponse(BaseModel):
    title: str
    content: str | None


class ProjectSourceVisualFeaturesResponse(BaseModel):
    orientation: str | None
    resolution: str | None
    frame_rate: str | None
    keyframe_count: int = 0
    shot_density: str | None
    scene_pace: str | None
    lighting: str | None
    contrast: str | None
    saturation: str | None
    color_temperature: str | None
    framing_focus: str | None
    camera_motion: str | None
    dominant_palette: list[str] = Field(default_factory=list)
    summary: str | None


class ProjectSourceAnalysisResponse(BaseModel):
    reference_frames: list[str] = Field(default_factory=list)
    visual_features: ProjectSourceVisualFeaturesResponse | None


class ProjectVideoGenerationResponse(BaseModel):
    status: str
    provider: str | None
    model: str | None
    objective: str | None
    asset_type: str | None
    asset_name: str | None
    asset_url: str | None
    audio_name: str | None
    audio_url: str | None
    reference_frames: list[str]
    script: str | None
    storyboard: str | None
    prompt: str | None
    provider_task_id: str | None
    result_video_url: str | None
    error_detail: str | None
    updated_at: datetime | None


class ProjectTaskStepResponse(BaseModel):
    id: int
    step_key: str
    title: str
    detail: str
    status: str
    error_detail: str | None
    display_order: int
    updated_at: datetime


class ProjectListItemResponse(BaseModel):
    id: int
    title: str
    source_url: str
    source_platform: str
    workflow_type: ProjectWorkflowType
    source_type: str
    source_name: str
    status: str
    media_url: str | None = None
    objective: str
    summary: str
    created_at: datetime
    updated_at: datetime


class ProjectDetailResponse(ProjectListItemResponse):
    script_overview: ProjectScriptOverviewResponse
    ecommerce_analysis: EcommerceAnalysisResponse
    source_analysis: ProjectSourceAnalysisResponse
    timeline_segments: list[TimelineSegmentResponse]
    video_generation: ProjectVideoGenerationResponse
    task_steps: list[ProjectTaskStepResponse]


class ProjectCreateRequest(BaseModel):
    source_url: HttpUrl
    title: str = Field(..., min_length=3, max_length=120)
    objective: str = Field(..., min_length=8, max_length=500)
    workflow_type: ProjectWorkflowType = "analysis"


class ProjectRefreshRequest(BaseModel):
    objective: str | None = Field(default=None, min_length=8, max_length=500)
    workflow_type: ProjectWorkflowType | None = None


class ProjectRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
