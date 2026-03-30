from __future__ import annotations

from app.workflows.base import TaskStepDefinition

PROJECT_WORKFLOW_ANALYSIS = "analysis"
PROJECT_ANALYSIS_JOB_TYPE = "project_analysis"

ANALYSIS_TASK_STEP_DEFINITIONS = [
    TaskStepDefinition("extract_video_link", "提取视频链接", "从用户输入中提取对标视频链接或上传素材地址。"),
    TaskStepDefinition("validate_video_link", "验证视频链接", "校验链接协议、来源平台和基础可访问性。"),
    TaskStepDefinition("analyze_video_content", "分析视频内容", "解析视频画面、节奏、镜头结构和内容主题。"),
    TaskStepDefinition("identify_audio_content", "识别音频内容", "提取音轨、转写口播，并识别字幕文本。"),
    TaskStepDefinition("generate_response", "生成分析回复", "生成 TikTok 电商效果深度分析主内容。"),
    TaskStepDefinition("generate_suggestions", "生成优化建议", "输出 3-5 条可执行的优化建议。"),
    TaskStepDefinition("finish", "全部完成", "视频分析工作流全部步骤已完成。"),
]


__all__ = [
    "ANALYSIS_TASK_STEP_DEFINITIONS",
    "PROJECT_ANALYSIS_JOB_TYPE",
    "PROJECT_WORKFLOW_ANALYSIS",
]
