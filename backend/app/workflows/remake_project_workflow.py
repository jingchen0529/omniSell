from __future__ import annotations

from app.workflows.base import TaskStepDefinition

PROJECT_WORKFLOW_REMAKE = "remake"
PROJECT_REMAKE_JOB_TYPE = "project_remake"

REMAKE_PROJECT_TASK_STEP_DEFINITIONS = [
    TaskStepDefinition(
        "visual_breakdown",
        "视觉拆解",
        "提取画面构图、背景、光影、色彩和运镜，并输出可复刻参数。",
    ),
    TaskStepDefinition(
        "timing_and_structure",
        "节奏与结构分析",
        "拆解 Hook、展示、转折和结尾的时间轴，并标注用户心理目的。",
    ),
    TaskStepDefinition(
        "viral_logic_extraction",
        "爆点逻辑提取",
        "提取钩子类型、留存机制和互动机制。",
    ),
    TaskStepDefinition(
        "content_carrier_analysis",
        "商品承载分析",
        "分析卖点如何被视觉化表达，并整理可复用展示方式。",
    ),
    TaskStepDefinition(
        "remake_plan_generation",
        "复刻执行方案",
        "输出拍摄准备、拍摄动作、后期剪辑和发布策略。",
    ),
    TaskStepDefinition(
        "variation_strategy_generation",
        "可变策略生成",
        "生成 3 个不同风格的变体方案，降低内容同质化风险。",
    ),
    TaskStepDefinition(
        "finish",
        "全部完成",
        "复刻爆款工作流全部步骤已完成。",
    ),
]


__all__ = [
    "PROJECT_REMAKE_JOB_TYPE",
    "PROJECT_WORKFLOW_REMAKE",
    "REMAKE_PROJECT_TASK_STEP_DEFINITIONS",
]
