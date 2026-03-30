from __future__ import annotations

from app.workflows.base import TaskStepDefinition

PROJECT_WORKFLOW_CREATE = "create"
PROJECT_CREATE_JOB_TYPE = "project_create"

CREATE_TASK_STEP_DEFINITIONS = [
    TaskStepDefinition("extract_video_link", "提取创作参考链接", "从输入中提取创作参考视频链接或上传素材地址。"),
    TaskStepDefinition("validate_video_link", "验证创作参考链接", "校验创作参考视频的链接格式和访问条件。"),
    TaskStepDefinition("analyze_video_content", "分析参考视频内容", "拆解参考视频的镜头、节奏和表达结构。"),
    TaskStepDefinition("identify_audio_content", "识别参考音频内容", "识别参考视频中的口播、字幕和音频重点。"),
    TaskStepDefinition("generate_response", "生成创作方案", "生成适合当前商品/客群的创作方向和脚本回复。"),
    TaskStepDefinition("generate_suggestions", "生成创作建议", "补充 3-5 条创作优化建议和调整方向。"),
    TaskStepDefinition("finish", "全部完成", "创作爆款工作流全部步骤已完成。"),
]


__all__ = [
    "CREATE_TASK_STEP_DEFINITIONS",
    "PROJECT_CREATE_JOB_TYPE",
    "PROJECT_WORKFLOW_CREATE",
]
