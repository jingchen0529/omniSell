"""AI-powered video analysis service using OpenAI."""

from __future__ import annotations

import json
import re
from typing import Any

try:
    import openai
except ImportError:  # pragma: no cover - exercised only when dependency is missing at runtime
    openai = None

from app.core.config import get_settings
from app.services.system_settings import (
    normalize_openai_compatible_api_base,
    resolve_ai_provider_settings,
)


def format_timestamp(ms: int) -> str:
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def build_ai_analysis_transcript(
    segments: list[object],
    fallback_text: str = "",
) -> str:
    formatted_segments = [
        f"[{format_timestamp(int(segment.start_ms))} - {format_timestamp(int(segment.end_ms))}]: {str(segment.content).strip()}"
        for segment in segments
        if str(getattr(segment, "content", "")).strip()
    ]
    if formatted_segments:
        return "\n".join(formatted_segments)
    return fallback_text.strip()


def normalize_ai_analysis_error(error_message: str, provider_label: str = "AI 分析服务") -> str:
    normalized = error_message.strip()
    lowered = normalized.lower()

    if "overloaded or not ready yet" in lowered:
        return f"{provider_label}当前繁忙，请稍后重试或更换模型服务。"
    if "rate limit" in lowered:
        return f"{provider_label}请求过于频繁，已触发频率限制，请稍后再试。"
    if "incorrect api key" in lowered or "invalid api key" in lowered:
        return f"{provider_label}鉴权失败，请检查 API Key 是否有效。"
    if "authentication" in lowered:
        return f"{provider_label}认证失败，请检查模型服务配置。"

    return normalized


def analyze_video_script(
    transcript: str,
    objective: str,
    *,
    workflow_type: str = "analysis",
    context: dict[str, Any] | None = None,
) -> str:
    if workflow_type == "remake":
        return analyze_remake_script(transcript, objective, context=context)
    return analyze_standard_video_script(transcript, objective)


def analyze_standard_video_script(transcript: str, objective: str) -> str:
    """
    使用当前配置的 AI 服务商输出 TikTok 电商效果深度分析。
    """
    settings = get_settings()
    provider_settings = resolve_ai_provider_settings()

    if not provider_settings.api_key:
        return f"未配置 {provider_settings.provider_label} API Key，无法进行 AI 分析。"
    if not provider_settings.chat_model:
        return f"未配置 {provider_settings.provider_label} 模型，无法进行 AI 分析。"
    if openai is None:
        return "后端环境未安装 openai 依赖，无法进行 AI 分析。"

    openai.api_key = provider_settings.api_key
    openai.api_base = normalize_openai_compatible_api_base(provider_settings.api_base)

    prompt = f"""# Role
你是一位资深 TikTok 电商增长顾问，擅长短视频带货结构拆解、B2B/B2C 转化分析和优化建议输出。

# Objective
用户目标：
{objective}

# Input
以下是从视频中提取的字幕/转写（含时间戳）：
{transcript}

# Task
请基于以上内容，输出一份适合运营和投放团队直接使用的《TikTok 电商效果深度分析》。

# Output
请严格按照下面结构输出，标题保持不变，不要额外发挥：

TikTok 电商效果深度分析
先用 1-2 句总结该视频的核心营销打法。

1. Hook（钩子）
时间：
内容：
分析：
- 策略：
- 效果：

2. Product Demo（产品展示）
时间：
内容：
分析：
- 策略：
- 效果：

3. Value Proposition（价值主张）
时间：
内容：
分析：
- 策略：
- 效果：

4. Call-to-Action（行动呼吁）
时间：
内容：
分析：
- 策略：
- 效果：

5. 字幕整理
- 按时间顺序整理关键字幕/口播
- 保留时间戳
- 优先输出 5-12 条；如果原始内容不足，就输出全部有效内容
格式：
- 00:00 - 00:03 | xxx

6. 转化评分
- 信任建立：X/10
- 产品展示：X/10
- 卖点清晰：X/10
- 行动引导：X/10
- 综合评分：X/10
- 总评：一句话

7. 爆款潜力
- 结论：高 / 中 / 低
- 原因：
- 适合市场 / 人群：

8. 专家建议
必须给出 3-5 条具体、可执行的优化建议，优先覆盖：
- 字幕优化
- 产品细节展示
- 卖点强化
- CTA 文案
- 私信/询盘转化动作

# Rules
1. 所有判断都必须结合视频内容，不要空泛结论。
2. 如果某一项素材不足，请明确写“当前素材未体现”。
3. 专家建议必须具体到能直接执行，必要时给出替换文案。
4. 用中文输出，但保留 Hook / Product Demo / Value Proposition / Call-to-Action 英文小标题。
5. 不要输出“分镜脚本”“复刻镜头”“拍摄分镜”等内容。"""

    try:
        response = openai.ChatCompletion.create(
            model=provider_settings.chat_model,
            messages=[
                {"role": "system", "content": "你是一位专业的 TikTok 电商视频分析专家。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
            request_timeout=settings.openai_request_timeout_seconds,
        )

        return response.choices[0].message.content or "分析失败：未返回内容"
    except Exception as exc:  # noqa: BLE001
        return f"AI 分析失败：{normalize_ai_analysis_error(str(exc), provider_settings.provider_label)}"


def analyze_remake_script(
    transcript: str,
    objective: str,
    *,
    context: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    provider_settings = resolve_ai_provider_settings()
    fallback_payload = build_default_remake_analysis_payload(
        transcript,
        objective,
        context=context,
    )

    if not provider_settings.api_key or not provider_settings.chat_model or openai is None:
        return format_remake_analysis_payload(fallback_payload)

    openai.api_key = provider_settings.api_key
    openai.api_base = normalize_openai_compatible_api_base(provider_settings.api_base)
    serialized_context = json.dumps(context or {}, ensure_ascii=False, indent=2)

    prompt = f"""# Role
你是一个短视频复刻专家系统（TikTok Remake Engine），任务是将输入的视频分析结果转化为一套可执行的视频复刻方案。

# Objective
用户目标：
{objective}

# Context
{serialized_context}

# Input
以下是视频转录文本（含时间戳）：
{transcript}

# Workflow
请严格按照以下工作流执行：
1. Visual Breakdown
2. Timing & Structure
3. Viral Logic Extraction
4. Content Carrier
5. Remake Plan
6. Variation Strategy

# Output Rules
1. 必须只输出合法 JSON。
2. 不能输出 Markdown、解释、前后缀说明。
3. 顶层必须严格包含以下键：
{{
  "visual": {{}},
  "timeline": [],
  "viral_logic": {{}},
  "content_strategy": {{}},
  "execution_plan": {{}},
  "variations": []
}}
4. 视觉参数必须具体，不能只写“高级感”“干净”等抽象词。
5. timeline 中每一段都要标注用户心理目的。
6. variations 必须给出 3 个不同风格的变体。"""

    try:
        response = openai.ChatCompletion.create(
            model=provider_settings.chat_model,
            messages=[
                {
                    "role": "system",
                    "content": "你是专业的 TikTok Remake Engine，只输出严格合法的 JSON。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=4000,
            request_timeout=settings.openai_request_timeout_seconds,
        )
        raw_content = response.choices[0].message.content or ""
        return normalize_remake_analysis_output(raw_content, fallback_payload)
    except Exception:
        return format_remake_analysis_payload(fallback_payload)


def normalize_remake_analysis_output(raw_content: str, fallback_payload: dict[str, Any]) -> str:
    candidate = extract_json_candidate(raw_content)
    if candidate is None:
        return format_remake_analysis_payload(fallback_payload)

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return format_remake_analysis_payload(fallback_payload)

    payload = ensure_remake_analysis_shape(parsed, fallback_payload)
    return format_remake_analysis_payload(payload)


def extract_json_candidate(raw_content: str) -> str | None:
    text = raw_content.strip()
    if not text:
        return None

    fenced_match = re.search(r"```json\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1).strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1].strip()


def ensure_remake_analysis_shape(
    payload: Any,
    fallback_payload: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return fallback_payload

    normalized = dict(fallback_payload)
    for key in ("visual", "viral_logic", "content_strategy", "execution_plan"):
        if isinstance(payload.get(key), dict):
            normalized[key] = payload[key]

    for key in ("timeline", "variations"):
        if isinstance(payload.get(key), list):
            normalized[key] = payload[key]

    return normalized


def format_remake_analysis_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_default_remake_analysis_payload(
    transcript: str,
    objective: str,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_context = context or {}
    segments = extract_remake_segments(transcript, safe_context)
    duration_seconds = resolve_duration_seconds(safe_context, segments)
    resolution = str(safe_context.get("resolution") or "1080x1920")
    aspect_ratio = str(safe_context.get("aspect_ratio") or "9:16")
    frame_rate = safe_context.get("frame_rate") or 30
    frame_rate_text = f"{float(frame_rate):.2f}fps" if isinstance(frame_rate, (int, float)) else "30.00fps"
    source_platform = str(safe_context.get("source_platform") or "short_video")
    source_name = str(safe_context.get("source_name") or "reference-video")
    title = str(safe_context.get("title") or "复刻方案")
    scenes = safe_context.get("remake_scenes") or []
    visual_features = safe_context.get("visual_features") or {}
    dominant_palette = [
        str(item)
        for item in visual_features.get("dominant_palette", [])
        if isinstance(item, str) and item.strip()
    ]
    palette_text = " / ".join(dominant_palette) if dominant_palette else "高对比暖中性色 + 1 个强调色"
    scene_pace_text = str(visual_features.get("scene_pace") or "中快节奏")
    lighting_text = str(visual_features.get("lighting") or "明亮均衡布光")
    contrast_text = str(visual_features.get("contrast") or "中对比")
    saturation_text = str(visual_features.get("saturation") or "中饱和")
    color_temperature_text = str(visual_features.get("color_temperature") or "中性")
    framing_focus_text = str(
        visual_features.get("framing_focus") or "主体保持在画面中上 40% 区域，镜头以中近景或胸像近景为主。"
    )
    camera_motion_text = str(
        visual_features.get("camera_motion") or "稳镜与切镜交替，整体更偏常规短视频节奏"
    )
    shot_density_text = str(
        visual_features.get("shot_density") or "每 10 秒约 1.5-2.0 次明显场景切换"
    )
    visual_summary_text = str(
        visual_features.get("summary") or "保持原片的光色、镜头密度和主体构图关系。"
    )

    hook_content = segments[0]["content"] if segments else objective
    hook_type = detect_hook_type(hook_content)
    timeline = build_remake_timeline(segments, duration_seconds)
    reusable_methods = build_reusable_display_methods(segments, scenes)

    visual = {
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "frame_rate": frame_rate_text,
        "composition": {
            "subject_position": framing_focus_text,
            "subtitle_safe_area": "顶部预留约 12% 字幕安全区，左右各预留 5% 画面边距。",
            "product_focus": "商品或核心动作必须占据画面宽度的 35%-55%，避免被字幕遮挡。",
        },
        "background": {
            "layout": "背景主元素控制在 1-2 个，优先使用桌面、货架或居家功能位场景。",
            "depth": "主体与背景建议拉开 0.8-1.5 米，避免画面扁平。",
            "brand_elements": f"背景可放 1 个与 {source_name} 同类的使用场景元素，避免杂物堆叠。",
        },
        "lighting": {
            "key_light": f"原片更接近 {lighting_text}，复刻时主光从人物或产品前方 45° 打入。",
            "fill_light_ratio": f"保持 {contrast_text} 的层次关系，补光控制在主光的 35%-45%。",
            "back_light": "背光或轮廓光控制在主光的 15%-20%，只负责拉开主体边缘。",
        },
        "color": {
            "palette": f"主色参考 {palette_text}，色温整体{color_temperature_text}。",
            "contrast": f"复刻时保持 {contrast_text}，主体与背景亮度差至少拉开 20%。",
            "saturation": f"整体建议维持 {saturation_text}，不要为了吸睛牺牲产品细节。",
        },
        "camera_motion": {
            "opening": "前 1.5 秒轻推镜 3%-5%，或者使用手持前移半步制造接近感。",
            "body": f"展示段整体参考 {scene_pace_text}，{camera_motion_text}。",
            "turning_point": "转折段加入 1 次 cut-in 特写或前后对比画面，时长控制在 0.5-0.9 秒。",
            "ending": "结尾保留 0.3-0.5 秒定镜，让 CTA 字幕完整停留。",
        },
        "replicable_parameters": [
            shot_density_text,
            "字幕字号建议占画面高度的 6%-8%，前 3 秒至少出现一次大字幕强化。",
            "口播镜头优先用 24-35mm 等效焦段，避免广角拉扯脸型或产品形变。",
            f"输出视频保持 {aspect_ratio}，优先导出 {resolution}，剪辑节奏按 {frame_rate_text} 处理。",
            visual_summary_text,
        ],
    }

    viral_logic = {
        "hook_type": hook_type,
        "hook_reason": f"开头内容“{hook_content[:48]}”更适合用 {hook_type} 型开场来抢停留。",
        "retention_mechanisms": [
            {
                "type": "节奏",
                "execution": "前三秒必须完成问题抛出或结果展示，镜头切换间隔控制在 0.8-1.2 秒。",
            },
            {
                "type": "情绪",
                "execution": "转折段加入结果强化、对比或反应镜头，拉高用户继续看的理由。",
            },
            {
                "type": "信息密度",
                "execution": "每一段只讲 1 个重点，字幕与画面同步，避免同屏堆 3 个以上信息点。",
            },
        ],
        "interaction_mechanisms": [
            {
                "type": "评论引导",
                "execution": "结尾字幕使用“要模板打 1 / 要清单打 2”这类低门槛评论引导。",
            },
            {
                "type": "二选一",
                "execution": "在结尾或置顶评论中加入“你更想看 A 版本还是 B 版本”的二选一问题。",
            },
        ],
    }

    content_strategy = {
        "visualized_selling_points": reusable_methods[:3],
        "reusable_display_methods": reusable_methods,
        "carrier_summary": (
            f"{title} 这类素材更适合用“强钩子口播 + 快节奏特写 + 结果画面/对比画面 + 明确 CTA”的承载结构。"
        ),
    }

    execution_plan = {
        "shooting_preparation": [
            f"先按 {aspect_ratio} 搭好竖屏机位，准备 1 个主讲人口播位和 1 个产品特写位。",
            "提前写好 4 段式提词卡：Hook、展示、转折、结尾 CTA，避免现场口播发散。",
            "准备 1 组干净背景、1 组功能演示道具、1 组对比素材，确保中段有切镜素材。",
        ],
        "shooting_actions": [
            "第一条先拍 3 个版本的开场，每个版本控制在 1.5-2.5 秒，用来测试停留。",
            "展示段至少拍 3 组镜头：主讲人口播、中近景产品演示、特写细节操作。",
            "转折段必须补一条前后对比或结果镜头，时长控制在 0.5-0.9 秒。",
        ],
        "post_production": [
            "首屏大字幕在 0.3 秒内进场，关键词放大 110%-125%，不要整句同时出现。",
            "剪辑按 Hook-展示-转折-结尾四段排布，每段只保留最强信息点。",
            "背景音乐只做节拍辅助，口播频段优先清晰，结尾 CTA 保留 0.3-0.5 秒完整停留。",
        ],
        "publishing_strategy": [
            f"发布时标题直接复用 {hook_type} 型钩子结构，避免平铺直叙式命名。",
            f"首发优先投放在 {source_platform} 的高活跃时段，并首小时盯完播率与 3 秒留存。",
            "置顶评论使用“回复关键词领取模板/清单”的动作，承接评论和私信转化。",
        ],
    }

    variations = [
        {
            "name": "强口播压迫感版",
            "style": "更强的镜头压迫感和更快的停留刺激。",
            "changes": [
                "开头 1 秒内直接给结果，不铺垫背景信息。",
                "全片口播镜头比例提高到 60% 以上，字幕更大、更短。",
                "结尾 CTA 更直接，鼓励评论领取模板。",
            ],
        },
        {
            "name": "产品演示可信度版",
            "style": "降低喊话感，强化产品细节和使用过程。",
            "changes": [
                "中段增加 2-3 个细节特写，减少正面怼脸镜头比例。",
                "转折段改用前后对比或结果验证素材，建立信任。",
                "发布文案突出真实体验、适用场景和人群。",
            ],
        },
        {
            "name": "UGC 生活方式版",
            "style": "更像用户自发分享，减少广告痕迹。",
            "changes": [
                "背景换成真实生活环境，保留一点环境噪声和轻微手持感。",
                "口播改成第一人称体验式表达，字幕更像随手记录。",
                "结尾用提问或二选一方式引导评论，而不是直接硬 CTA。",
            ],
        },
    ]

    return {
        "visual": visual,
        "timeline": timeline,
        "viral_logic": viral_logic,
        "content_strategy": content_strategy,
        "execution_plan": execution_plan,
        "variations": variations,
    }


def extract_remake_segments(transcript: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    context_segments = context.get("transcript_segments")
    if isinstance(context_segments, list) and context_segments:
        extracted: list[dict[str, Any]] = []
        for segment in context_segments:
            if not isinstance(segment, dict):
                continue
            content = str(segment.get("content") or "").strip()
            if not content:
                continue
            start_ms = int(segment.get("start_ms") or 0)
            end_ms = int(segment.get("end_ms") or start_ms + 1000)
            extracted.append(
                {
                    "start_s": round(start_ms / 1000, 2),
                    "end_s": round(max(end_ms, start_ms + 1) / 1000, 2),
                    "content": content,
                }
            )
        if extracted:
            return extracted

    parsed: list[dict[str, Any]] = []
    for line in transcript.splitlines():
        match = re.match(r"\[(\d{2}:\d{2}) - (\d{2}:\d{2})\]:\s*(.+)", line.strip())
        if not match:
            continue
        parsed.append(
            {
                "start_s": timestamp_to_seconds(match.group(1)),
                "end_s": timestamp_to_seconds(match.group(2)),
                "content": match.group(3).strip(),
            }
        )
    if parsed:
        return parsed

    plain_lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    if not plain_lines:
        return []
    return [
        {
            "start_s": float(index * 3),
            "end_s": float(index * 3 + 3),
            "content": line,
        }
        for index, line in enumerate(plain_lines[:6])
    ]


def build_remake_timeline(
    segments: list[dict[str, Any]],
    duration_seconds: float,
) -> list[dict[str, Any]]:
    phases = [
        ("Hook", "先在 1-3 秒内抢停留，让用户决定不划走。"),
        ("展示", "用最短路径证明内容或商品值得继续看。"),
        ("转折", "制造结果强化、反差或证据，避免用户在中段流失。"),
        ("结尾", "把兴趣转成评论、私信、收藏或点击动作。"),
    ]
    if duration_seconds <= 0:
        duration_seconds = max((segment["end_s"] for segment in segments), default=12.0)

    hook_end = min(duration_seconds * 0.2, duration_seconds)
    display_end = min(duration_seconds * 0.6, duration_seconds)
    turning_end = min(duration_seconds * 0.85, duration_seconds)
    boundaries = [0.0, hook_end, display_end, turning_end, duration_seconds]
    for index in range(1, len(boundaries)):
        boundaries[index] = round(max(boundaries[index], boundaries[index - 1] + 0.1), 2)
    boundaries[-1] = round(max(duration_seconds, boundaries[-2] + 0.1), 2)

    timeline: list[dict[str, Any]] = []
    for index, (stage, psychology_goal) in enumerate(phases):
        start_s = boundaries[index]
        end_s = boundaries[index + 1]
        related_text = [
            segment["content"]
            for segment in segments
            if segment["start_s"] < end_s and segment["end_s"] > start_s
        ]
        if not related_text and segments:
            related_text = [segments[min(index, len(segments) - 1)]["content"]]
        summary = " / ".join(text[:42] for text in related_text[:2]) or "当前素材可复用该阶段的镜头节奏，但口播需自行补足。"
        timeline.append(
            {
                "stage": stage,
                "start_s": round(start_s, 2),
                "end_s": round(max(end_s, start_s + 0.5), 2),
                "key_content": summary,
                "user_psychology_goal": psychology_goal,
                "editing_direction": build_timeline_editing_direction(stage),
            }
        )
    return timeline


def build_timeline_editing_direction(stage: str) -> str:
    if stage == "Hook":
        return "镜头长度控制在 0.8-1.5 秒，首屏大字幕必须同步出现。"
    if stage == "展示":
        return "插入口播和产品/动作特写，保证 1-2 秒内就看到核心展示。"
    if stage == "转折":
        return "使用对比、结果或第三方证据镜头，做一次明显的节奏抬升。"
    return "结尾 CTA 保留 0.3-0.5 秒完整停留，并配合评论引导。"


def build_reusable_display_methods(
    segments: list[dict[str, Any]],
    scenes: Any,
) -> list[dict[str, str]]:
    methods: list[dict[str, str]] = []
    for segment in segments[:3]:
        excerpt = segment["content"][:36]
        methods.append(
            {
                "selling_point": excerpt or "核心卖点",
                "visual_expression": "用中近景口播先点题，再切产品或结果特写强化理解。",
                "reusable_pattern": "口播一句 + 特写一镜 + 大字幕一句，三连击完成一次卖点表达。",
            }
        )

    if isinstance(scenes, list):
        for scene in scenes[:2]:
            if not isinstance(scene, dict):
                continue
            methods.append(
                {
                    "selling_point": str(scene.get("on_screen_text") or "关键字幕"),
                    "visual_expression": str(scene.get("visual_direction") or "镜头快速推进"),
                    "reusable_pattern": str(scene.get("editing_notes") or "每镜头 0.8-1.2 秒切换"),
                }
            )

    if not methods:
        methods.append(
            {
                "selling_point": "结果/收益点",
                "visual_expression": "开头直接抛结果，中段给过程，结尾再给动作。",
                "reusable_pattern": "结果先行 + 过程证据 + CTA 收口。",
            }
        )
    return methods[:5]


def resolve_duration_seconds(context: dict[str, Any], segments: list[dict[str, Any]]) -> float:
    raw_duration = context.get("duration_seconds")
    if isinstance(raw_duration, (int, float)) and raw_duration > 0:
        return float(raw_duration)
    return max((segment["end_s"] for segment in segments), default=12.0)


def detect_hook_type(content: str) -> str:
    lowered = content.lower()
    if "?" in content or "？" in content:
        return "提问"
    if any(token in lowered for token in ("before", "after", "vs", "但是", "却", "反而", "对比")):
        return "反差"
    return "悬念"


def timestamp_to_seconds(value: str) -> float:
    minutes, seconds = value.split(":", 1)
    return int(minutes) * 60 + int(seconds)
