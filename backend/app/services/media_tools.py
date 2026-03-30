from __future__ import annotations

import base64
import json
import math
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from html import unescape
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.core.config import get_settings
from app.services.system_settings import (
    get_system_proxy_url,
    normalize_openai_compatible_api_base,
)
from app.services.video_sources import (
    SUPPORTED_UPLOAD_EXTENSIONS,
    decode_upload_relative_path,
    extract_source_name,
    is_upload_source,
    resolve_public_upload_url,
    store_generated_public_file,
)

try:
    import openai
except ImportError:  # pragma: no cover - exercised only when the dependency is missing at runtime
    openai = None

try:
    import faster_whisper
except ImportError:  # pragma: no cover - exercised only when the dependency is missing at runtime
    faster_whisper = None


class VideoAnalysisError(RuntimeError):
    def __init__(self, detail: str, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class VideoMediaMetadata:
    duration_ms: int
    width: int | None
    height: int | None
    frame_rate: float | None
    has_audio: bool
    subtitle_streams: int

    @property
    def orientation(self) -> str:
        if self.width and self.height:
            if self.height > self.width:
                return "portrait"
            if self.width > self.height:
                return "landscape"
        return "square"


@dataclass(frozen=True)
class RawTranscriptSegment:
    segment_type: str
    speaker: str | None
    start_ms: int
    end_ms: int
    content: str


@dataclass(frozen=True)
class VisualFeatureAnalysis:
    orientation: str
    resolution: str
    frame_rate: str
    keyframe_count: int
    shot_density: str
    scene_pace: str
    lighting: str
    contrast: str
    saturation: str
    color_temperature: str
    framing_focus: str
    camera_motion: str
    dominant_palette: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass(frozen=True)
class MediaAnalysisData:
    metadata: VideoMediaMetadata
    transcript_segments: list[RawTranscriptSegment]
    transcript_provider: str
    media_url: str | None = None
    reference_frame_urls: list[str] = field(default_factory=list)
    visual_feature_analysis: VisualFeatureAnalysis | None = None


@dataclass(frozen=True)
class FrameVisualMetrics:
    average_r: float
    average_g: float
    average_b: float
    brightness_mean: float
    brightness_std: float
    saturation_mean: float
    center_detail_ratio: float


MediaAnalysisProgressCallback = Callable[[str], None]


def collect_media_analysis(
    source_url: str,
    *,
    progress_callback: MediaAnalysisProgressCallback | None = None,
) -> MediaAnalysisData:
    settings = get_settings()
    settings.media_work_root.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(dir=settings.media_work_root) as temp_dir_name:
        temp_dir = Path(temp_dir_name)

        if is_upload_source(source_url):
            video_path = resolve_uploaded_video_path(source_url)
            metadata = probe_video_metadata(video_path)
            subtitle_segments = extract_embedded_subtitle_segments(
                video_path=video_path,
                workdir=temp_dir,
            )
        else:
            video_path, subtitle_segments = download_remote_video_and_subtitles(
                source_url=source_url,
                workdir=temp_dir,
            )
            metadata = probe_video_metadata(video_path)

        media_url: str | None = None
        if is_upload_source(source_url):
            media_url = resolve_public_upload_url(source_url)
        else:
            import shutil
            import uuid
            
            downloads_dir = settings.uploads_root / "downloads"
            downloads_dir.mkdir(parents=True, exist_ok=True)
            new_filename = f"{uuid.uuid4().hex}{video_path.suffix}"
            dest_path = downloads_dir / new_filename
            shutil.copy2(video_path, dest_path)
            media_url = f"/uploads/downloads/{new_filename}"

        if subtitle_segments:
            transcript_segments = subtitle_segments
            transcript_provider = "subtitles"
        else:
            if not metadata.has_audio:
                raise VideoAnalysisError(
                    "Video has no usable subtitle track and no audio stream available for transcription.",
                )

            if progress_callback is not None:
                progress_callback("identify_audio_content")

            audio_path = extract_audio_track(video_path=video_path, workdir=temp_dir)
            transcript_segments, transcript_provider = transcribe_audio(
                audio_path=audio_path,
                duration_ms=metadata.duration_ms,
            )

        reference_frame_urls, visual_feature_analysis = build_visual_analysis_bundle(
            video_path=video_path,
            workdir=temp_dir,
            metadata=metadata,
            source_name=extract_source_name(source_url),
        )
        return MediaAnalysisData(
            metadata=metadata,
            transcript_segments=transcript_segments,
            transcript_provider=transcript_provider,
            media_url=media_url,
            reference_frame_urls=reference_frame_urls,
            visual_feature_analysis=visual_feature_analysis,
        )


def resolve_uploaded_video_path(source_url: str) -> Path:
    settings = get_settings()
    relative_path = Path(decode_upload_relative_path(source_url))
    local_path = settings.uploads_root / relative_path
    if not local_path.is_file():
        raise VideoAnalysisError("Uploaded video file no longer exists.", status_code=404)
    return local_path


def download_remote_video_and_subtitles(source_url: str, workdir: Path) -> tuple[Path, list[RawTranscriptSegment]]:
    output_template = str(workdir / "source.%(ext)s")
    command = build_remote_download_command(source_url=source_url, output_template=output_template)
    run_command(command)

    subtitle_segments: list[RawTranscriptSegment] = []
    subtitle_file = select_preferred_subtitle_file(workdir)
    if subtitle_file is not None:
        subtitle_segments = parse_subtitle_file(subtitle_file)

    video_candidates = [
        path
        for path in workdir.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_UPLOAD_EXTENSIONS
    ]
    if not video_candidates:
        raise VideoAnalysisError("Failed to download a playable video file from the provided URL.")

    video_path = max(video_candidates, key=lambda path: path.stat().st_size)
    return video_path, subtitle_segments


def build_remote_download_command(source_url: str, output_template: str) -> list[str]:
    settings = get_settings()
    command = [
        settings.yt_dlp_binary,
        "--no-playlist",
        "--no-progress",
        "--no-warnings",
        "--restrict-filenames",
        "--write-auto-subs",
        "--write-subs",
        "--sub-langs",
        "all,-live_chat",
        "--sub-format",
        "best",
        "--convert-subs",
        "vtt",
    ]

    proxy_url = get_system_proxy_url()
    if proxy_url:
        command.extend(["--proxy", proxy_url])

    command.extend(
        [
            "--output",
            output_template,
            source_url,
        ]
    )
    return command


def probe_video_metadata(video_path: Path) -> VideoMediaMetadata:
    settings = get_settings()
    command = [
        settings.ffprobe_binary,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    result = run_command(command)
    payload = json.loads(result.stdout or "{}")

    streams = payload.get("streams", [])
    format_info = payload.get("format", {})
    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        {},
    )
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    subtitle_streams = [stream for stream in streams if stream.get("codec_type") == "subtitle"]

    duration_raw = (
        format_info.get("duration")
        or video_stream.get("duration")
        or next((stream.get("duration") for stream in audio_streams if stream.get("duration")), None)
    )
    duration_ms = int(float(duration_raw or 0) * 1000)

    return VideoMediaMetadata(
        duration_ms=max(duration_ms, 0),
        width=coerce_int(video_stream.get("width")),
        height=coerce_int(video_stream.get("height")),
        frame_rate=parse_frame_rate(video_stream.get("avg_frame_rate")),
        has_audio=bool(audio_streams),
        subtitle_streams=len(subtitle_streams),
    )


def extract_embedded_subtitle_segments(video_path: Path, workdir: Path) -> list[RawTranscriptSegment]:
    metadata = probe_video_metadata(video_path)
    if metadata.subtitle_streams <= 0:
        return []

    settings = get_settings()
    subtitle_path = workdir / "embedded.vtt"
    command = [
        settings.ffmpeg_binary,
        "-y",
        "-i",
        str(video_path),
        "-map",
        "0:s:0",
        str(subtitle_path),
    ]
    try:
        run_command(command)
    except VideoAnalysisError:
        return []

    return parse_subtitle_file(subtitle_path)


def extract_audio_track(video_path: Path, workdir: Path) -> Path:
    settings = get_settings()
    audio_path = workdir / "audio.mp3"
    command = [
        settings.ffmpeg_binary,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "64k",
        str(audio_path),
    ]
    run_command(command)

    if not audio_path.is_file() or audio_path.stat().st_size <= 0:
        raise VideoAnalysisError("Failed to extract an audio track for transcription.")

    if audio_path.stat().st_size > 24 * 1024 * 1024:
        raise VideoAnalysisError(
            "Extracted audio is larger than 24MB. Split the source video or lower the bitrate before retrying.",
        )

    return audio_path


def build_visual_analysis_bundle(
    *,
    video_path: Path,
    workdir: Path,
    metadata: VideoMediaMetadata,
    source_name: str,
) -> tuple[list[str], VisualFeatureAnalysis | None]:
    try:
        frame_paths = extract_scene_reference_frames(video_path, workdir)
    except VideoAnalysisError:
        return [], None

    if not frame_paths:
        return [], None

    reference_frame_urls = [
        store_generated_public_file(
            frame_path,
            category="analysis-frames",
            source_name=f"{Path(source_name).stem}-analysis-frame-{index + 1}{frame_path.suffix.lower()}",
        )
        for index, frame_path in enumerate(frame_paths)
    ]
    visual_feature_analysis = analyze_reference_frames(
        frame_paths=frame_paths,
        metadata=metadata,
    )
    return reference_frame_urls, visual_feature_analysis


def analyze_reference_frames(
    *,
    frame_paths: list[Path],
    metadata: VideoMediaMetadata,
) -> VisualFeatureAnalysis | None:
    metrics: list[FrameVisualMetrics] = []
    for frame_path in frame_paths:
        try:
            raw_rgb = load_scaled_frame_rgb(frame_path)
        except VideoAnalysisError:
            continue
        metrics.append(build_frame_visual_metrics(raw_rgb, width=48, height=48))

    if not metrics:
        return None

    frame_count = len(metrics)
    average_r = sum(metric.average_r for metric in metrics) / frame_count
    average_g = sum(metric.average_g for metric in metrics) / frame_count
    average_b = sum(metric.average_b for metric in metrics) / frame_count
    brightness_mean = sum(metric.brightness_mean for metric in metrics) / frame_count
    contrast_value = sum(metric.brightness_std for metric in metrics) / frame_count
    saturation_value = sum(metric.saturation_mean for metric in metrics) / frame_count
    focus_ratio = sum(metric.center_detail_ratio for metric in metrics) / frame_count

    duration_seconds = max((metadata.duration_ms or 0) / 1000, 1.0)
    scene_density = len(frame_paths) / duration_seconds * 10

    scene_pace = classify_scene_pace(scene_density)
    lighting = classify_lighting(brightness_mean, contrast_value)
    contrast = classify_contrast(contrast_value)
    saturation = classify_saturation(saturation_value)
    color_temperature = classify_color_temperature(average_r, average_b)
    framing_focus = classify_framing_focus(focus_ratio)
    camera_motion = classify_camera_motion(scene_density, focus_ratio)
    orientation = format_orientation_label(metadata.orientation)
    resolution = (
        f"{metadata.width}x{metadata.height}"
        if metadata.width and metadata.height
        else "unknown"
    )
    frame_rate = f"{metadata.frame_rate:.2f}fps" if metadata.frame_rate else "unknown"
    dominant_palette = build_dominant_palette(metrics)
    shot_density = f"每 10 秒约 {scene_density:.1f} 次明显场景切换"
    summary = (
        f"素材整体为{orientation}，节奏{scene_pace}，画面{lighting}、{contrast}、{saturation}，"
        f"色温{color_temperature}，{framing_focus}，建议复刻时延续这种镜头密度与光色关系。"
    )

    return VisualFeatureAnalysis(
        orientation=orientation,
        resolution=resolution,
        frame_rate=frame_rate,
        keyframe_count=len(frame_paths),
        shot_density=shot_density,
        scene_pace=scene_pace,
        lighting=lighting,
        contrast=contrast,
        saturation=saturation,
        color_temperature=color_temperature,
        framing_focus=framing_focus,
        camera_motion=camera_motion,
        dominant_palette=dominant_palette,
        summary=summary,
    )


def load_scaled_frame_rgb(frame_path: Path, *, width: int = 48, height: int = 48) -> bytes:
    settings = get_settings()
    command = [
        settings.ffmpeg_binary,
        "-v",
        "error",
        "-i",
        str(frame_path),
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,format=rgb24",
        "-frames:v",
        "1",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    result = run_command(command, text=False)
    return bytes(result.stdout or b"")


def build_frame_visual_metrics(raw_rgb: bytes, *, width: int, height: int) -> FrameVisualMetrics:
    expected_size = width * height * 3
    if len(raw_rgb) < expected_size:
        raise VideoAnalysisError("Failed to decode extracted keyframe for visual analysis.")

    total_pixels = width * height
    center_x_start = width // 4
    center_x_end = width - center_x_start
    center_y_start = height // 4
    center_y_end = height - center_y_start

    brightness_values: list[float] = []
    center_values: list[float] = []
    edge_values: list[float] = []
    sum_r = 0.0
    sum_g = 0.0
    sum_b = 0.0
    saturation_sum = 0.0

    for y in range(height):
        for x in range(width):
            offset = (y * width + x) * 3
            r = raw_rgb[offset]
            g = raw_rgb[offset + 1]
            b = raw_rgb[offset + 2]
            luma = 0.2126 * r + 0.7152 * g + 0.0722 * b

            sum_r += r
            sum_g += g
            sum_b += b
            saturation_sum += (max(r, g, b) - min(r, g, b)) / 255
            brightness_values.append(luma)

            if center_x_start <= x < center_x_end and center_y_start <= y < center_y_end:
                center_values.append(luma)
            else:
                edge_values.append(luma)

    brightness_mean = sum(brightness_values) / total_pixels
    brightness_variance = (
        sum((value - brightness_mean) ** 2 for value in brightness_values) / total_pixels
    )
    brightness_std = math.sqrt(brightness_variance)
    center_detail = mean_absolute_deviation(center_values)
    edge_detail = mean_absolute_deviation(edge_values)

    return FrameVisualMetrics(
        average_r=sum_r / total_pixels,
        average_g=sum_g / total_pixels,
        average_b=sum_b / total_pixels,
        brightness_mean=brightness_mean,
        brightness_std=brightness_std,
        saturation_mean=saturation_sum / total_pixels,
        center_detail_ratio=center_detail / edge_detail if edge_detail > 0 else 1.0,
    )


def mean_absolute_deviation(values: list[float]) -> float:
    if not values:
        return 0.0
    mean_value = sum(values) / len(values)
    return sum(abs(value - mean_value) for value in values) / len(values)


def classify_scene_pace(scene_density: float) -> str:
    if scene_density >= 2.5:
        return "快切"
    if scene_density >= 1.5:
        return "中快节奏"
    if scene_density >= 0.8:
        return "中节奏"
    return "慢节奏"


def classify_lighting(brightness_mean: float, contrast_value: float) -> str:
    if brightness_mean >= 170:
        return "高亮硬光" if contrast_value >= 45 else "高亮柔光"
    if brightness_mean >= 130:
        return "明亮均衡布光"
    if brightness_mean >= 95:
        return "中性偏暗布光"
    return "低照度氛围光"


def classify_contrast(contrast_value: float) -> str:
    if contrast_value >= 60:
        return "高对比"
    if contrast_value >= 35:
        return "中对比"
    return "低对比"


def classify_saturation(saturation_value: float) -> str:
    if saturation_value >= 0.45:
        return "高饱和"
    if saturation_value >= 0.25:
        return "中饱和"
    return "低饱和"


def classify_color_temperature(average_r: float, average_b: float) -> str:
    delta = average_r - average_b
    if delta >= 12:
        return "偏暖"
    if delta <= -12:
        return "偏冷"
    return "中性"


def classify_framing_focus(focus_ratio: float) -> str:
    if focus_ratio >= 1.1:
        return "主体更集中在画面中心，偏中近景或产品特写"
    if focus_ratio <= 0.92:
        return "画面信息分布更满，偏环境展示或操作过程"
    return "主体与背景分配均衡，适合口播和演示混合构图"


def classify_camera_motion(scene_density: float, focus_ratio: float) -> str:
    if scene_density >= 2.5:
        return "频繁切镜，适合保留轻推镜或手持接近感"
    if scene_density >= 1.5 and focus_ratio >= 1.05:
        return "稳镜与中近景推进交替，适合做节奏型展示"
    if scene_density >= 1.0:
        return "切镜与稳镜交替，整体更偏常规短视频节奏"
    return "稳定机位为主，转场和运动都相对克制"


def format_orientation_label(value: str) -> str:
    return {
        "portrait": "竖屏",
        "landscape": "横屏",
        "square": "方屏",
    }.get(value, "未知画幅")


def build_dominant_palette(metrics: list[FrameVisualMetrics]) -> list[str]:
    palette: list[str] = []
    seen: set[str] = set()
    for metric in metrics:
        swatch = rgb_to_quantized_hex(metric.average_r, metric.average_g, metric.average_b)
        if swatch in seen:
            continue
        palette.append(swatch)
        seen.add(swatch)
        if len(palette) >= 4:
            break
    return palette


def rgb_to_quantized_hex(red: float, green: float, blue: float, *, step: int = 32) -> str:
    def quantize(value: float) -> int:
        return max(0, min(255, int(round(value / step) * step)))

    return f"#{quantize(red):02X}{quantize(green):02X}{quantize(blue):02X}"


def extract_scene_reference_frames(
    video_path: Path,
    workdir: Path,
    *,
    max_frames: int = 6,
) -> list[Path]:
    frames_dir = workdir / "reference-frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = frames_dir / "scene-%03d.jpg"

    settings = get_settings()
    scene_command = [
        settings.ffmpeg_binary,
        "-y",
        "-i",
        str(video_path),
        "-vf",
        "select='gt(scene,0.28)',scale='min(1280,iw)':-2",
        "-vsync",
        "vfr",
        "-q:v",
        "3",
        str(output_pattern),
    ]
    try:
        run_command(scene_command)
    except VideoAnalysisError:
        pass

    scene_frames = sorted(frames_dir.glob("scene-*.jpg"))
    if scene_frames:
        return limit_evenly_spaced_paths(scene_frames, max_frames)

    metadata = probe_video_metadata(video_path)
    duration_seconds = max((metadata.duration_ms or 0) / 1000, 1)
    fps_value = min(max_frames / duration_seconds, 1)
    fallback_pattern = frames_dir / "fallback-%03d.jpg"
    fallback_command = [
        settings.ffmpeg_binary,
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps_value:.4f},scale='min(1280,iw)':-2",
        "-q:v",
        "3",
        str(fallback_pattern),
    ]
    run_command(fallback_command)
    fallback_frames = sorted(frames_dir.glob("fallback-*.jpg"))
    if not fallback_frames:
        raise VideoAnalysisError("Failed to extract reference frames from the uploaded product video.")
    return limit_evenly_spaced_paths(fallback_frames, max_frames)


def limit_evenly_spaced_paths(paths: list[Path], max_items: int) -> list[Path]:
    if len(paths) <= max_items:
        return paths
    selected: list[Path] = []
    step = (len(paths) - 1) / max(max_items - 1, 1)
    for index in range(max_items):
        selected.append(paths[round(index * step)])
    return selected


def encode_image_file_as_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    mime_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "image/jpeg")
    payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{payload}"


def transcribe_audio(audio_path: Path, duration_ms: int) -> tuple[list[RawTranscriptSegment], str]:
    settings = get_settings()
    provider = settings.video_transcription_provider.strip().lower()

    if provider == "faster_whisper":
        return transcribe_audio_with_faster_whisper(audio_path), "faster_whisper"
    if provider == "openai":
        return transcribe_audio_with_openai(audio_path, duration_ms), "openai"
    if provider == "auto":
        failures: list[str] = []

        try:
            return transcribe_audio_with_faster_whisper(audio_path), "faster_whisper"
        except VideoAnalysisError as exc:
            failures.append(exc.detail)

        try:
            return transcribe_audio_with_openai(audio_path, duration_ms), "openai"
        except VideoAnalysisError as exc:
            failures.append(exc.detail)

        raise VideoAnalysisError(
            "Auto transcription failed. " + " | ".join(failures),
            status_code=503,
        )

    raise VideoAnalysisError(
        f"Unsupported transcription provider `{settings.video_transcription_provider}`.",
        status_code=500,
    )


def transcribe_audio_with_faster_whisper(audio_path: Path) -> list[RawTranscriptSegment]:
    settings = get_settings()
    model = get_faster_whisper_model()

    try:
        segments_iter, _info = model.transcribe(
            str(audio_path),
            beam_size=settings.faster_whisper_beam_size,
            vad_filter=settings.faster_whisper_vad_filter,
            language=settings.transcription_language,
        )
        segments = list(segments_iter)
    except Exception as exc:  # noqa: BLE001 - faster-whisper raises backend-specific runtime exceptions
        raise VideoAnalysisError(
            f"faster-whisper transcription failed: {str(exc).strip() or exc.__class__.__name__}",
            status_code=503,
        ) from exc

    parsed_segments = [
        RawTranscriptSegment(
            segment_type="dialogue",
            speaker="主讲人",
            start_ms=int(float(segment.start) * 1000),
            end_ms=max(int(float(segment.end) * 1000), int(float(segment.start) * 1000) + 1),
            content=str(segment.text or "").strip(),
        )
        for segment in segments
        if str(segment.text or "").strip()
    ]
    if parsed_segments:
        return parsed_segments

    raise VideoAnalysisError(
        "faster-whisper returned no usable text. Try a clearer audio track or disable local transcription.",
        status_code=503,
    )


def transcribe_audio_with_openai(audio_path: Path, duration_ms: int) -> list[RawTranscriptSegment]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise VideoAnalysisError(
            "OPENAI_API_KEY is not configured. Link videos with subtitles can still be parsed, but audio transcription requires an API key.",
            status_code=503,
        )
    if openai is None:
        raise VideoAnalysisError(
            "The `openai` package is not installed in the backend environment.",
            status_code=503,
        )

    openai.api_key = settings.openai_api_key
    normalized_api_base = normalize_openai_compatible_api_base(settings.openai_api_base)
    if normalized_api_base:
        openai.api_base = normalized_api_base

    try:
        with audio_path.open("rb") as audio_file:
            request_kwargs: dict[str, Any] = {
                "model": settings.openai_audio_model,
                "file": audio_file,
                "response_format": "verbose_json",
            }
            if settings.openai_request_timeout_seconds > 0:
                request_kwargs["request_timeout"] = settings.openai_request_timeout_seconds
            if settings.transcription_language:
                request_kwargs["language"] = settings.transcription_language
            response = openai.Audio.transcribe(**request_kwargs)
    except Exception as exc:  # noqa: BLE001 - OpenAI client raises multiple runtime exception types
        raise VideoAnalysisError(
            f"OpenAI transcription failed: {str(exc).strip() or exc.__class__.__name__}",
            status_code=503,
        ) from exc

    payload = (
        response.to_dict_recursive()
        if hasattr(response, "to_dict_recursive")
        else dict(response)
        if isinstance(response, dict)
        else {}
    )
    text = str(payload.get("text") or "").strip()
    segments = payload.get("segments") or []
    if segments:
        parsed_segments = [
            RawTranscriptSegment(
                segment_type="dialogue",
                speaker="主讲人",
                start_ms=int(float(segment.get("start", 0)) * 1000),
                end_ms=int(float(segment.get("end", 0)) * 1000),
                content=str(segment.get("text") or "").strip(),
            )
            for segment in segments
            if str(segment.get("text") or "").strip()
        ]
        if parsed_segments:
            return parsed_segments

    if not text:
        raise VideoAnalysisError("Audio transcription returned no usable text.", status_code=503)

    return [
        RawTranscriptSegment(
            segment_type="dialogue",
            speaker="主讲人",
            start_ms=0,
            end_ms=max(duration_ms, 1),
            content=text,
        )
    ]


@lru_cache
def get_faster_whisper_model() -> Any:
    settings = get_settings()
    if faster_whisper is None:
        raise VideoAnalysisError(
            "The `faster-whisper` package is not installed in the backend environment.",
            status_code=503,
        )

    settings.faster_whisper_model_root.mkdir(parents=True, exist_ok=True)
    init_kwargs: dict[str, Any] = {
        "device": settings.faster_whisper_device,
        "compute_type": settings.faster_whisper_compute_type,
        "download_root": str(settings.faster_whisper_model_root),
        "num_workers": settings.faster_whisper_num_workers,
    }
    if settings.faster_whisper_cpu_threads > 0:
        init_kwargs["cpu_threads"] = settings.faster_whisper_cpu_threads

    try:
        return faster_whisper.WhisperModel(
            settings.faster_whisper_model_size,
            **init_kwargs,
        )
    except Exception as exc:  # noqa: BLE001 - ctranslate2 / faster-whisper raise multiple runtime exceptions
        raise VideoAnalysisError(
            f"Failed to initialize faster-whisper model `{settings.faster_whisper_model_size}`: {str(exc).strip() or exc.__class__.__name__}",
            status_code=503,
        ) from exc


def parse_subtitle_file(subtitle_path: Path) -> list[RawTranscriptSegment]:
    if subtitle_path.suffix.lower() == ".srt":
        return parse_srt_text(subtitle_path.read_text(encoding="utf-8", errors="ignore"))
    return parse_webvtt_text(subtitle_path.read_text(encoding="utf-8", errors="ignore"))


def parse_webvtt_text(content: str) -> list[RawTranscriptSegment]:
    segments: list[RawTranscriptSegment] = []
    start_ms: int | None = None
    end_ms: int | None = None
    text_lines: list[str] = []

    def flush() -> None:
        nonlocal start_ms, end_ms, text_lines
        if start_ms is None or end_ms is None:
            text_lines = []
            return

        text = clean_caption_text(" ".join(text_lines))
        if text and (not segments or segments[-1].content != text):
            segments.append(
                RawTranscriptSegment(
                    segment_type="caption",
                    speaker=None,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    content=text,
                )
            )
        start_ms = None
        end_ms = None
        text_lines = []

    for raw_line in content.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            flush()
            continue
        if line in {"WEBVTT", "STYLE", "REGION"} or line.startswith("NOTE"):
            continue
        if "-->" in line:
            flush()
            start_token, end_token = [part.strip() for part in line.split("-->", 1)]
            start_ms = parse_timestamp_to_ms(start_token)
            end_ms = parse_timestamp_to_ms(end_token.split()[0])
            continue
        if start_ms is None:
            continue
        text_lines.append(line)

    flush()
    return segments


def parse_srt_text(content: str) -> list[RawTranscriptSegment]:
    segments: list[RawTranscriptSegment] = []
    blocks = re.split(r"\n\s*\n", content.strip(), flags=re.MULTILINE)
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        time_line_index = 1 if re.fullmatch(r"\d+", lines[0]) else 0
        if "-->" not in lines[time_line_index]:
            continue
        start_token, end_token = [part.strip() for part in lines[time_line_index].split("-->", 1)]
        text = clean_caption_text(" ".join(lines[time_line_index + 1 :]))
        if not text:
            continue
        segments.append(
            RawTranscriptSegment(
                segment_type="caption",
                speaker=None,
                start_ms=parse_timestamp_to_ms(start_token),
                end_ms=parse_timestamp_to_ms(end_token),
                content=text,
            )
        )
    return segments


def select_preferred_subtitle_file(workdir: Path) -> Path | None:
    candidates = sorted(
        [
            path
            for path in workdir.iterdir()
            if path.is_file() and path.suffix.lower() in {".vtt", ".srt"}
        ]
    )
    if not candidates:
        return None

    language_order = [
        ".zh-hans.",
        ".zh-cn.",
        ".zh-hant.",
        ".zh-tw.",
        ".zh.",
        ".en.",
    ]

    def score(path: Path) -> tuple[int, str]:
        lower_name = path.name.lower()
        for index, marker in enumerate(language_order):
            if marker in lower_name:
                return index, lower_name
        return len(language_order), lower_name

    return sorted(candidates, key=score)[0]


def parse_timestamp_to_ms(value: str) -> int:
    cleaned = value.strip().replace(",", ".")
    match = re.search(r"(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})", cleaned)
    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    milliseconds = int(match.group(4))
    total_ms = ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds
    return total_ms


def clean_caption_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\{[^}]+\}", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_frame_rate(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    if "/" not in value:
        try:
            return float(value)
        except ValueError:
            return None
    numerator, denominator = value.split("/", 1)
    try:
        numerator_value = float(numerator)
        denominator_value = float(denominator)
    except ValueError:
        return None
    if denominator_value == 0:
        return None
    return round(numerator_value / denominator_value, 2)


def coerce_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def normalize_media_command_error(detail: str) -> str:
    normalized = detail.strip()
    lowered = normalized.lower()

    if "blocked from accessing this post" in lowered or "your ip address is blocked" in lowered:
        return (
            "TikTok 拒绝了当前出口 IP 对该视频的访问。"
            "这通常表示服务器 IP 或你配置的代理 IP 已被 TikTok 限制。"
            "请到系统设置里更换可用代理 IP/端口后重试。"
        )

    return normalized


def run_command(
    command: list[str],
    *,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    settings = get_settings()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=text,
            check=False,
            timeout=settings.media_command_timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise VideoAnalysisError(
            f"Required media tool `{command[0]}` is not installed on the server.",
            status_code=503,
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoAnalysisError(
            f"Media command timed out after {settings.media_command_timeout_seconds} seconds: {command[0]}",
            status_code=504,
        ) from exc

    if result.returncode != 0:
        stderr = (
            result.stderr.decode("utf-8", errors="ignore")
            if isinstance(result.stderr, bytes)
            else result.stderr
        )
        stdout = (
            result.stdout.decode("utf-8", errors="ignore")
            if isinstance(result.stdout, bytes)
            else result.stdout
        )
        detail = (stderr or "").strip() or (stdout or "").strip() or "Unknown media command failure."
        raise VideoAnalysisError(normalize_media_command_error(detail))

    return result
