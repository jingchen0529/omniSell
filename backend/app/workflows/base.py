from __future__ import annotations

from dataclasses import dataclass

from app.db.models import VideoProjectTaskStep


@dataclass(frozen=True)
class TaskStepDefinition:
    key: str
    title: str
    detail: str


def build_steps_from_definitions(
    definitions: list[TaskStepDefinition],
) -> list[VideoProjectTaskStep]:
    return [
        VideoProjectTaskStep(
            step_key=definition.key,
            title=definition.title,
            detail=definition.detail,
            status="pending",
            display_order=index,
        )
        for index, definition in enumerate(definitions, start=1)
    ]


__all__ = ["TaskStepDefinition", "build_steps_from_definitions"]
