from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.config import get_settings
from app.services.ai_analysis import analyze_video_script
from app.services.media_tools import (
    MediaAnalysisData,
    VisualFeatureAnalysis,
    collect_media_analysis,
)
from app.services.video_sources import extract_source_slug, platform_label
from app.workflows.remake_project_workflow import PROJECT_WORKFLOW_REMAKE


@dataclass
class GeneratedTranscriptSegment:
    segment_type: str
    speaker: str | None
    start_ms: int
    end_ms: int
    content: str
    display_order: int


@dataclass
class GeneratedRemakeScene:
    scene_index: int
    visual_direction: str
    shot_prompt: str
    voiceover: str
    on_screen_text: str
    editing_notes: str


@dataclass
class GeneratedProjectAnalysis:
    title: str
    summary: str
    status: str
    full_text: str
    dialogue_text: str
    narration_text: str
    caption_text: str
    ai_analysis: str
    transcript_segments: list[GeneratedTranscriptSegment]
    remake_scenes: list[GeneratedRemakeScene]
    media_url: str | None = None
    reference_frame_urls: list[str] = field(default_factory=list)
    visual_feature_analysis: VisualFeatureAnalysis | None = None


def build_mock_project_analysis(
    source_url: str,
    title: str,
    objective: str,
    source_platform: str = "generic",
    source_name: str | None = None,
    workflow_type: str = "analysis",
) -> GeneratedProjectAnalysis:
    video_slug = extract_source_slug(source_url, source_name)
    source_label = platform_label(source_platform)
    source_subject = source_name or video_slug

    transcript_segments = [
        GeneratedTranscriptSegment(
            segment_type="narration",
            speaker="旁白",
            start_ms=0,
            end_ms=3200,
            content=f"先用一个强钩子开场，直接点出 {objective} 的核心结果。",
            display_order=1,
        ),
        GeneratedTranscriptSegment(
            segment_type="caption",
            speaker=None,
            start_ms=200,
            end_ms=3000,
            content=f"3 秒看懂 {source_label} 素材 {source_subject} 的内容抓手",
            display_order=2,
        ),
        GeneratedTranscriptSegment(
            segment_type="dialogue",
            speaker="主讲人",
            start_ms=3200,
            end_ms=8200,
            content=f"如果你也想复刻这条 {source_label} 视频的节奏，先把镜头重点放在 {objective}。",
            display_order=3,
        ),
        GeneratedTranscriptSegment(
            segment_type="caption",
            speaker=None,
            start_ms=4300,
            end_ms=7600,
            content="Hook / Value / CTA",
            display_order=4,
        ),
        GeneratedTranscriptSegment(
            segment_type="narration",
            speaker="旁白",
            start_ms=8200,
            end_ms=12500,
            content="中段补充案例、数字或对比画面，让观众快速接受结论。",
            display_order=5,
        ),
        GeneratedTranscriptSegment(
            segment_type="dialogue",
            speaker="主讲人",
            start_ms=12500,
            end_ms=16000,
            content="最后给出一个明确行动建议，引导评论、私信或点击主页链接。",
            display_order=6,
        ),
    ]

    remake_scenes = [
        GeneratedRemakeScene(
            scene_index=1,
            visual_direction="近景人像 + 强对比背景，第一秒就把人和标题都顶出来。",
            shot_prompt=f"竖屏 9:16，创作者正对镜头，快速切入主题 {objective}。",
            voiceover="先说结果，不铺垫。",
            on_screen_text=f"{title} 核心钩子",
            editing_notes="前 1.5 秒必须有大字幕和轻微推镜。",
        ),
        GeneratedRemakeScene(
            scene_index=2,
            visual_direction="切入原视频同类场景的替代素材，保持快节奏。",
            shot_prompt="插入 2 到 3 个 B-roll，展示痛点、结果或前后对比。",
            voiceover="解释为什么这条内容能抓住停留。",
            on_screen_text="观众停留点",
            editing_notes="每镜头 0.8 到 1.2 秒，配合节拍切换。",
        ),
        GeneratedRemakeScene(
            scene_index=3,
            visual_direction="回到主讲人，加一个白板、手机界面或评论截图增强可信度。",
            shot_prompt="主讲人边说边指向画面中的关键要点。",
            voiceover="拆解脚本结构：钩子、价值、行动。",
            on_screen_text="Hook / Value / CTA",
            editing_notes="字幕逐词高亮，关键词加粗放大。",
        ),
        GeneratedRemakeScene(
            scene_index=4,
            visual_direction="结尾拉近镜头，形成强 CTA。",
            shot_prompt="主讲人收束结论并给出一个下一步动作。",
            voiceover="如果你要复刻，先照这个节奏拍第一版。",
            on_screen_text="保存这套脚本模板",
            editing_notes="结尾保留 0.5 秒静止画面，利于观众看清 CTA。",
        ),
    ]
    visual_feature_analysis = build_mock_visual_feature_analysis()

    dialogue_lines = [
        segment.content for segment in transcript_segments if segment.segment_type == "dialogue"
    ]
    narration_lines = [
        segment.content for segment in transcript_segments if segment.segment_type == "narration"
    ]
    caption_lines = [
        segment.content for segment in transcript_segments if segment.segment_type == "caption"
    ]
    full_text = "\n".join(
        f"[{segment.segment_type}] {segment.speaker + '：' if segment.speaker else ''}{segment.content}"
        for segment in transcript_segments
    )
    ai_analysis = ""
    if workflow_type == PROJECT_WORKFLOW_REMAKE:
        formatted_transcript = "\n".join(
            f"[{format_timestamp(seg.start_ms)} - {format_timestamp(seg.end_ms)}]: {seg.content}"
            for seg in transcript_segments
        )
        ai_analysis = analyze_video_script(
            formatted_transcript,
            objective,
            workflow_type=workflow_type,
            context=build_analysis_context(
                title=title,
                objective=objective,
                source_platform=source_platform,
                source_name=source_name or source_subject,
                transcript_segments=transcript_segments,
                remake_scenes=remake_scenes,
                duration_seconds=16.0,
                frame_rate=30.0,
                width=1080,
                height=1920,
                transcript_provider="mock",
                reference_frame_urls=[],
                visual_feature_analysis=visual_feature_analysis,
            ),
        )

    return GeneratedProjectAnalysis(
        title=title,
        summary=(
            (
                f"已基于 {source_label} 来源 {source_subject} 生成可执行复刻方案，"
                "覆盖视觉拆解、时间轴、爆点逻辑和执行策略。"
            )
            if workflow_type == PROJECT_WORKFLOW_REMAKE
            else (
                f"围绕 {source_label} 来源 {source_subject} 生成的第一版拆解结果，"
                "覆盖对话、旁白、字幕和复刻镜头建议。"
            )
        ),
        status="ready",
        full_text=full_text,
        dialogue_text="\n".join(dialogue_lines),
        narration_text="\n".join(narration_lines),
        caption_text="\n".join(caption_lines),
        ai_analysis=ai_analysis,
        transcript_segments=transcript_segments,
        remake_scenes=remake_scenes,
        media_url=None,
        reference_frame_urls=[],
        visual_feature_analysis=visual_feature_analysis,
    )


def build_project_analysis(
    source_url: str,
    title: str,
    objective: str,
    source_platform: str = "generic",
    source_name: str | None = None,
    workflow_type: str = "analysis",
) -> GeneratedProjectAnalysis:
    settings = get_settings()
    if settings.video_analysis_provider.strip().lower() == "mock":
        return build_mock_project_analysis(
            source_url=source_url,
            title=title,
            objective=objective,
            source_platform=source_platform,
            source_name=source_name,
            workflow_type=workflow_type,
        )

    media_analysis = collect_media_analysis(source_url)
    return build_real_project_analysis(
        title=title,
        objective=objective,
        source_platform=source_platform,
        source_name=source_name,
        media_analysis=media_analysis,
        workflow_type=workflow_type,
    )


def build_real_project_analysis(
    title: str,
    objective: str,
    source_platform: str,
    source_name: str | None,
    media_analysis: MediaAnalysisData,
    workflow_type: str = "analysis",
) -> GeneratedProjectAnalysis:
    source_label = platform_label(source_platform)
    source_subject = source_name or "source-video"
    duration_seconds = media_analysis.metadata.duration_ms / 1000 if media_analysis.metadata.duration_ms else 0
    orientation_label = {
        "portrait": "竖屏",
        "landscape": "横屏",
        "square": "方屏",
    }[media_analysis.metadata.orientation]

    transcript_segments = [
        GeneratedTranscriptSegment(
            segment_type=segment.segment_type,
            speaker=segment.speaker,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms if segment.end_ms > segment.start_ms else segment.start_ms + 1,
            content=segment.content,
            display_order=index,
        )
        for index, segment in enumerate(media_analysis.transcript_segments, start=1)
    ]

    dialogue_lines = [
        segment.content for segment in transcript_segments if segment.segment_type == "dialogue"
    ]
    caption_lines = [
        segment.content for segment in transcript_segments if segment.segment_type == "caption"
    ]
    if not dialogue_lines:
        dialogue_lines = [segment.content for segment in transcript_segments]
    if not caption_lines:
        caption_lines = [build_caption_candidate(segment.content) for segment in transcript_segments[:4]]

    full_text = "\n".join(
        f"[{segment.segment_type}] {segment.speaker + '：' if segment.speaker else ''}{segment.content}"
        for segment in transcript_segments
    )
    remake_scenes = build_real_remake_scenes(
        title=title,
        objective=objective,
        transcript_segments=transcript_segments,
        source_platform=source_platform,
        orientation_label=orientation_label,
        duration_seconds=duration_seconds,
        frame_rate=media_analysis.metadata.frame_rate,
        width=media_analysis.metadata.width,
        height=media_analysis.metadata.height,
        visual_feature_analysis=media_analysis.visual_feature_analysis,
    )

    summary = build_project_summary(
        workflow_type=workflow_type,
        source_label=source_label,
        source_subject=source_subject,
        transcript_count=len(transcript_segments),
        transcript_provider=media_analysis.transcript_provider,
        duration_seconds=duration_seconds,
    )

    settings = get_settings()
    ai_analysis = ""
    formatted_transcript = "\n".join(
        f"[{format_timestamp(seg.start_ms)} - {format_timestamp(seg.end_ms)}]: {seg.content}"
        for seg in transcript_segments
    )
    if workflow_type == PROJECT_WORKFLOW_REMAKE or settings.enable_ai_analysis:
        ai_analysis = analyze_video_script(
            formatted_transcript,
            objective,
            workflow_type=workflow_type,
            context=build_analysis_context(
                title=title,
                objective=objective,
                source_platform=source_platform,
                source_name=source_subject,
                transcript_segments=transcript_segments,
                remake_scenes=remake_scenes,
                duration_seconds=duration_seconds,
                frame_rate=media_analysis.metadata.frame_rate,
                width=media_analysis.metadata.width,
                height=media_analysis.metadata.height,
                transcript_provider=media_analysis.transcript_provider,
                reference_frame_urls=media_analysis.reference_frame_urls,
                visual_feature_analysis=media_analysis.visual_feature_analysis,
            ),
        )

    return GeneratedProjectAnalysis(
        title=title,
        summary=summary,
        status="ready",
        full_text=full_text,
        dialogue_text="\n".join(dialogue_lines),
        narration_text="",
        caption_text="\n".join(caption_lines),
        ai_analysis=ai_analysis,
        transcript_segments=transcript_segments,
        remake_scenes=remake_scenes,
        media_url=media_analysis.media_url,
        reference_frame_urls=media_analysis.reference_frame_urls,
        visual_feature_analysis=media_analysis.visual_feature_analysis,
    )


def format_timestamp(ms: int) -> str:
    """将毫秒转换为 MM:SS 格式"""
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def build_real_remake_scenes(
    title: str,
    objective: str,
    transcript_segments: list[GeneratedTranscriptSegment],
    source_platform: str,
    orientation_label: str,
    duration_seconds: float,
    frame_rate: float | None,
    width: int | None,
    height: int | None,
    visual_feature_analysis: VisualFeatureAnalysis | None = None,
) -> list[GeneratedRemakeScene]:
    scene_count = min(4, max(1, len(transcript_segments)))
    chunk_size = max(1, math.ceil(len(transcript_segments) / scene_count))
    frame_rate_text = f"{frame_rate:.2f}fps" if frame_rate else "原视频帧率"
    resolution_text = (
        f"{width}x{height}"
        if width and height
        else "原视频分辨率"
    )
    visual_feature_notes = ""
    if visual_feature_analysis is not None:
        palette = ", ".join(visual_feature_analysis.dominant_palette[:3])
        visual_feature_notes = (
            f"参考原片的{visual_feature_analysis.scene_pace}、{visual_feature_analysis.lighting}、"
            f"{visual_feature_analysis.color_temperature}风格。"
        )
        if palette:
            visual_feature_notes += f" 主色可参考 {palette}。"

    scenes: list[GeneratedRemakeScene] = []
    for scene_index in range(scene_count):
        start = scene_index * chunk_size
        end = start + chunk_size
        chunk = transcript_segments[start:end]
        if not chunk:
            continue

        combined_text = " ".join(segment.content for segment in chunk)
        time_start = chunk[0].start_ms / 1000
        time_end = chunk[-1].end_ms / 1000
        text_excerpt = combined_text[:160]

        scenes.append(
            GeneratedRemakeScene(
                scene_index=scene_index + 1,
                visual_direction=(
                    f"{orientation_label}镜头，参考 {time_start:.1f}s - {time_end:.1f}s 的原视频节奏。"
                    f" 当前任务目标：{objective}。{visual_feature_notes}"
                ),
                shot_prompt=(
                    f"围绕这段真实内容复刻画面与镜头推进：{text_excerpt}"
                ),
                voiceover=text_excerpt,
                on_screen_text=build_caption_candidate(chunk[0].content) or f"{title} 片段 {scene_index + 1}",
                editing_notes=(
                    f"保持 {platform_label(source_platform)} 的剪辑速度，"
                    f"参考 {frame_rate_text} 与 {resolution_text}，整条视频时长约 {duration_seconds:.1f} 秒。"
                    f"{f' 建议保留{visual_feature_analysis.camera_motion}。' if visual_feature_analysis else ''}"
                ),
            )
        )

    return scenes


def build_caption_candidate(value: str) -> str:
    compact = " ".join(value.split())
    return compact[:24]


def build_project_summary(
    *,
    workflow_type: str,
    source_label: str,
    source_subject: str,
    transcript_count: int,
    transcript_provider: str,
    duration_seconds: float,
) -> str:
    if workflow_type == PROJECT_WORKFLOW_REMAKE:
        summary = (
            f"已基于 {source_label} 来源 {source_subject} 生成可执行复刻方案，"
            f"包含视觉拆解、节奏结构、爆点逻辑、商品承载和变体策略。"
        )
    else:
        summary = (
            f"已基于真实视频解析完成 {source_label} 来源 {source_subject} 的拆解，"
            f"通过 {transcript_provider} 提取了 {transcript_count} 段文本。"
        )
    if duration_seconds:
        summary += f" 视频时长约 {duration_seconds:.1f} 秒。"
    return summary


def build_analysis_context(
    *,
    title: str,
    objective: str,
    source_platform: str,
    source_name: str,
    transcript_segments: list[GeneratedTranscriptSegment],
    remake_scenes: list[GeneratedRemakeScene],
    duration_seconds: float,
    frame_rate: float | None,
    width: int | None,
    height: int | None,
    transcript_provider: str,
    reference_frame_urls: list[str],
    visual_feature_analysis: VisualFeatureAnalysis | None,
) -> dict[str, Any]:
    return {
        "title": title,
        "objective": objective,
        "source_platform": source_platform,
        "source_name": source_name,
        "duration_seconds": round(duration_seconds, 2) if duration_seconds else 0,
        "frame_rate": round(frame_rate, 2) if frame_rate else None,
        "resolution": (
            f"{width}x{height}"
            if width and height
            else None
        ),
        "aspect_ratio": (
            "9:16"
            if width and height and height > width
            else "16:9"
            if width and height and width > height
            else "1:1"
        ),
        "transcript_provider": transcript_provider,
        "reference_frames": reference_frame_urls,
        "visual_features": (
            asdict(visual_feature_analysis) if visual_feature_analysis is not None else None
        ),
        "transcript_segments": [
            {
                "segment_type": segment.segment_type,
                "speaker": segment.speaker,
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "content": segment.content,
            }
            for segment in transcript_segments
        ],
        "remake_scenes": [
            {
                "scene_index": scene.scene_index,
                "visual_direction": scene.visual_direction,
                "shot_prompt": scene.shot_prompt,
                "voiceover": scene.voiceover,
                "on_screen_text": scene.on_screen_text,
                "editing_notes": scene.editing_notes,
            }
            for scene in remake_scenes
        ],
    }


def build_mock_visual_feature_analysis() -> VisualFeatureAnalysis:
    return VisualFeatureAnalysis(
        orientation="竖屏",
        resolution="1080x1920",
        frame_rate="30.00fps",
        keyframe_count=4,
        shot_density="每 10 秒约 2.5 次明显场景切换",
        scene_pace="快切",
        lighting="明亮均衡布光",
        contrast="中对比",
        saturation="中饱和",
        color_temperature="偏暖",
        framing_focus="主体更集中在画面中心，偏中近景或产品特写",
        camera_motion="频繁切镜，适合保留轻推镜或手持接近感",
        dominant_palette=["#E0A060", "#806040", "#F0D0A0"],
        summary=(
            "整体是典型的竖屏电商短视频视觉：前段快切、中段特写补信息、"
            "结尾留 CTA，适合按同样的构图和镜头密度去复刻。"
        ),
    )
