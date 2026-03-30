from __future__ import annotations

from app.db.models import VideoProjectTaskStep
from app.workflows.analysis_workflow import (
    ANALYSIS_TASK_STEP_DEFINITIONS,
    PROJECT_ANALYSIS_JOB_TYPE,
    PROJECT_WORKFLOW_ANALYSIS,
)
from app.workflows.base import build_steps_from_definitions
from app.workflows.create_workflow import (
    CREATE_TASK_STEP_DEFINITIONS,
    PROJECT_CREATE_JOB_TYPE,
    PROJECT_WORKFLOW_CREATE,
)
from app.workflows.remake_project_workflow import (
    PROJECT_REMAKE_JOB_TYPE,
    PROJECT_WORKFLOW_REMAKE,
    REMAKE_PROJECT_TASK_STEP_DEFINITIONS,
)
from app.workflows.remake_workflow import (
    REMAKE_TASK_STEP_DEFINITIONS,
    VIDEO_GENERATION_JOB_TYPE,
)

SUPPORTED_PROJECT_WORKFLOW_TYPES = (
    PROJECT_WORKFLOW_ANALYSIS,
    PROJECT_WORKFLOW_CREATE,
    PROJECT_WORKFLOW_REMAKE,
)

PROJECT_WORKFLOW_STEP_DEFINITIONS = {
    PROJECT_WORKFLOW_ANALYSIS: ANALYSIS_TASK_STEP_DEFINITIONS,
    PROJECT_WORKFLOW_CREATE: CREATE_TASK_STEP_DEFINITIONS,
    PROJECT_WORKFLOW_REMAKE: REMAKE_PROJECT_TASK_STEP_DEFINITIONS,
}


def normalize_project_workflow_type(workflow_type: str | None) -> str:
    normalized = (workflow_type or PROJECT_WORKFLOW_ANALYSIS).strip().lower()
    if normalized not in SUPPORTED_PROJECT_WORKFLOW_TYPES:
        raise ValueError(f"Unsupported project workflow type: {workflow_type}")
    return normalized


def get_project_job_type(workflow_type: str | None) -> str:
    normalized = normalize_project_workflow_type(workflow_type)
    if normalized == PROJECT_WORKFLOW_CREATE:
        return PROJECT_CREATE_JOB_TYPE
    if normalized == PROJECT_WORKFLOW_REMAKE:
        return PROJECT_REMAKE_JOB_TYPE
    return PROJECT_ANALYSIS_JOB_TYPE


def build_task_steps(workflow_type: str = PROJECT_WORKFLOW_ANALYSIS) -> list[VideoProjectTaskStep]:
    definitions = PROJECT_WORKFLOW_STEP_DEFINITIONS[normalize_project_workflow_type(workflow_type)]
    return build_steps_from_definitions(definitions)


def build_video_generation_task_steps() -> list[VideoProjectTaskStep]:
    return build_steps_from_definitions(REMAKE_TASK_STEP_DEFINITIONS)


__all__ = [
    "PROJECT_ANALYSIS_JOB_TYPE",
    "PROJECT_CREATE_JOB_TYPE",
    "PROJECT_REMAKE_JOB_TYPE",
    "PROJECT_WORKFLOW_ANALYSIS",
    "PROJECT_WORKFLOW_CREATE",
    "PROJECT_WORKFLOW_REMAKE",
    "PROJECT_WORKFLOW_STEP_DEFINITIONS",
    "REMAKE_TASK_STEP_DEFINITIONS",
    "SUPPORTED_PROJECT_WORKFLOW_TYPES",
    "VIDEO_GENERATION_JOB_TYPE",
    "build_task_steps",
    "build_video_generation_task_steps",
    "get_project_job_type",
    "normalize_project_workflow_type",
]
