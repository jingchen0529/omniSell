from __future__ import annotations

from app.workflows.base import TaskStepDefinition

VIDEO_GENERATION_JOB_TYPE = "video_generation"

REMAKE_TASK_STEP_DEFINITIONS = [
    TaskStepDefinition(
        "prepare_reference_asset",
        "准备复刻素材",
        "读取上传的产品素材，或在无素材时切换到脚本直出模式。",
    ),
    TaskStepDefinition(
        "analyze_reference_asset",
        "分析参考素材",
        "抽取关键帧或整理脚本直出所需的参考信息。",
    ),
    TaskStepDefinition("build_video_prompt", "生成脚本与提示词", "生成视频脚本、分镜和最终提示词。"),
    TaskStepDefinition("submit_video_generation", "提交生成任务", "向视频模型服务提交生成任务。"),
    TaskStepDefinition("poll_video_generation", "等待生成结果", "轮询任务状态并获取结果视频地址。"),
    TaskStepDefinition("finish", "全部完成", "视频复刻工作流全部步骤已完成。"),
]


__all__ = ["REMAKE_TASK_STEP_DEFINITIONS", "VIDEO_GENERATION_JOB_TYPE"]
