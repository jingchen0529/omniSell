from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request
from urllib.parse import urlsplit, urlunsplit

from app.core.config import get_settings
from app.services.system_settings import ResolvedVideoProviderSettings


class VideoGenerationError(RuntimeError):
    def __init__(self, detail: str, status_code: int = 500) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class VideoGenerationBlueprint:
    objective: str
    script: str
    storyboard: str
    prompt: str


@dataclass(frozen=True)
class VideoGenerationResult:
    task_id: str
    status: str
    video_url: str | None = None
    error_detail: str | None = None


@dataclass(frozen=True)
class VideoGenerationTaskSubmission:
    task_id: str
    status: str


class VideoGenerationStrategy(Protocol):
    def generate(
        self,
        *,
        provider_settings: ResolvedVideoProviderSettings,
        prompt: str,
        reference_images: list[str],
        audio_url: str | None = None,
    ) -> VideoGenerationResult: ...


def build_video_generation_blueprint(
    project,
    *,
    objective: str | None,
    reference_asset_type: str,
    reference_asset_name: str,
    reference_frame_count: int,
) -> VideoGenerationBlueprint:
    effective_objective = (objective or "").strip() or "复刻对标视频节奏并生成可投放的带货短视频"
    generation_mode = "image-to-video" if reference_frame_count > 0 else "text-to-video"
    visual_features = load_project_visual_features(project)
    source_reference_frames = load_project_reference_frames(project)
    palette = ", ".join(
        str(item)
        for item in visual_features.get("dominant_palette", [])
        if isinstance(item, str) and item.strip()
    )
    visual_summary = str(visual_features.get("summary") or project.summary or "").strip()
    scene_pace = str(visual_features.get("scene_pace") or "中快节奏")
    lighting = str(visual_features.get("lighting") or "明亮均衡布光")
    camera_motion = str(visual_features.get("camera_motion") or "稳镜与切镜交替")
    framing_focus = str(
        visual_features.get("framing_focus") or "主体与背景分配均衡，适合口播和演示混合构图"
    )

    scene_lines: list[str] = []
    script_blocks: list[str] = []
    section_titles = ["Hook", "产品展示", "信任证明", "CTA"]
    for index, scene in enumerate(project.remake_scenes[:4]):
        section_label = section_titles[index] if index < len(section_titles) else f"段落 {index + 1}"
        scene_lines.append(
            (
                f"{section_label} / 镜头 {scene.scene_index}：画面 {scene.visual_direction}；"
                f"拍摄提示 {scene.shot_prompt}；"
                f"旁白 {scene.voiceover or '无'}；"
                f"字幕 {scene.on_screen_text or '无'}；"
                f"剪辑 {scene.editing_notes or '无'}。"
            )
        )
        script_blocks.append(
            (
                f"{index + 1}. {section_label}\n"
                f"口播：{scene.voiceover or scene.on_screen_text or scene.visual_direction}\n"
                f"字幕：{scene.on_screen_text or '无'}\n"
                f"画面：{scene.visual_direction}\n"
                f"动作：{scene.shot_prompt}\n"
                f"剪辑：{scene.editing_notes or '无'}"
            )
        )

    script_intro = [
        f"目标：{effective_objective}",
        (
            "素材模式："
            + (
                f"{reference_asset_type} / {reference_asset_name}"
                if reference_frame_count > 0
                else "未上传产品素材，直接按对标视频脚本生成"
            )
        ),
    ]
    if visual_summary:
        script_intro.append(
            f"视觉基调：{visual_summary}{f' 主色参考 {palette}。' if palette else ''}"
        )
    script_outro = (
        f"执行要点：整体保持{scene_pace}，布光偏{lighting}，运镜参考“{camera_motion}”，构图重点为“{framing_focus}”。"
    )
    script = (
        "\n\n".join([*script_intro, "AI 复刻文案脚本：", *script_blocks, script_outro])
        if script_blocks
        else (project.full_text.strip() or "围绕产品卖点输出竖版带货视频。")
    )
    storyboard_header = (
        f"源片视觉摘要：{visual_summary}"
        if visual_summary
        else "源片视觉摘要：使用 3-4 个镜头快速展示产品、卖点和行动引导。"
    )
    storyboard = "\n".join([storyboard_header, *scene_lines]).strip()
    prompt = (
        "Create a vertical 9:16 TikTok ecommerce video. "
        "Use the uploaded product reference as the primary subject and keep the product appearance consistent. "
        "Maintain natural motion, realistic lighting, stable hands/objects, clean product focus, and a fast TikTok pacing. "
        "Avoid unrelated objects, broken anatomy, duplicated products, deformed packaging, unreadable text, flicker, and camera shake. "
        f"User objective: {effective_objective}. "
        f"Generation mode: {generation_mode}. "
        f"Reference asset: {reference_asset_type} / {reference_asset_name}. "
        f"Reference frames extracted: {reference_frame_count}. "
        f"Reference source title: {project.title}. "
        f"Ecommerce analysis summary: {project.summary}. "
        f"Source visual summary: {visual_summary or 'Keep the original fast ecommerce visual rhythm.'} "
        f"Source scene pace: {scene_pace}. "
        f"Source lighting: {lighting}. "
        f"Source framing: {framing_focus}. "
        f"Source camera motion: {camera_motion}. "
        f"Source reference frames available: {len(source_reference_frames)}. "
        f"{f'Source dominant palette: {palette}. ' if palette else ''}"
        f"Storyboard: {storyboard}"
    )

    return VideoGenerationBlueprint(
        objective=effective_objective,
        script=script,
        storyboard=storyboard,
        prompt=prompt,
    )


def load_project_visual_features(project) -> dict[str, object]:
    raw_value = getattr(project, "analysis_visual_features", None)
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_project_reference_frames(project) -> list[str]:
    raw_value = getattr(project, "analysis_reference_frames", None)
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str)]


def generate_video_with_provider(
    *,
    provider_settings: ResolvedVideoProviderSettings,
    prompt: str,
    reference_images: list[str],
    audio_url: str | None = None,
) -> VideoGenerationResult:
    strategy = build_video_generation_strategy(provider_settings)
    return strategy.generate(
        provider_settings=provider_settings,
        prompt=prompt,
        reference_images=reference_images,
        audio_url=audio_url,
    )


class UnsupportedVideoGenerationStrategy:
    def generate(
        self,
        *,
        provider_settings: ResolvedVideoProviderSettings,
        prompt: str,
        reference_images: list[str],
        audio_url: str | None = None,
    ) -> VideoGenerationResult:
        raise VideoGenerationError(
            f"当前暂不支持 {provider_settings.provider_label} 的真实视频生成接入。",
            status_code=501,
        )


class DoubaoVideoGenerationStrategy:
    def generate(
        self,
        *,
        provider_settings: ResolvedVideoProviderSettings,
        prompt: str,
        reference_images: list[str],
        audio_url: str | None = None,
    ) -> VideoGenerationResult:
        if not provider_settings.api_key:
            raise VideoGenerationError("未配置豆包视频生成 API Key。", status_code=503)
        if not provider_settings.api_base:
            raise VideoGenerationError("未配置豆包视频生成 API Base。", status_code=503)

        model = resolve_video_generation_model(
            provider_settings=provider_settings,
            reference_images=reference_images,
        )
        payload = build_doubao_generation_payload(
            model=model,
            prompt=prompt,
            reference_images=reference_images,
        )
        submission = submit_doubao_generation_task(
            provider_settings=provider_settings,
            payload=payload,
        )
        return poll_doubao_video_result(
            provider_settings=provider_settings,
            task_id=submission.task_id,
            initial_status=submission.status,
        )


class QwenVideoGenerationStrategy:
    def generate(
        self,
        *,
        provider_settings: ResolvedVideoProviderSettings,
        prompt: str,
        reference_images: list[str],
        audio_url: str | None = None,
    ) -> VideoGenerationResult:
        if not provider_settings.api_key:
            raise VideoGenerationError("未配置 DashScope 视频生成 API Key。", status_code=503)
        if not provider_settings.api_base:
            raise VideoGenerationError("未配置 DashScope 视频生成 API Base。", status_code=503)

        model = resolve_video_generation_model(
            provider_settings=provider_settings,
            reference_images=reference_images,
        )
        payload = build_qwen_video_generation_payload(
            model=model,
            prompt=prompt,
            reference_images=reference_images,
            audio_url=audio_url,
        )
        response = qwen_video_request_json(
            method="POST",
            url=build_qwen_video_submission_url(provider_settings.api_base),
            api_key=provider_settings.api_key or "",
            payload=payload,
        )
        immediate_result = build_qwen_video_result_from_response(response)
        if immediate_result is not None:
            return immediate_result

        task_id = extract_nested_value(
            response,
            ("output", "task_id"),
            ("task_id",),
            ("data", "task_id"),
            ("id",),
        )
        if not task_id:
            raise VideoGenerationError("DashScope 视频生成返回中缺少任务 ID。", status_code=502)

        status = extract_qwen_generation_status(response, default="submitted")
        return poll_qwen_video_result(
            provider_settings=provider_settings,
            task_id=str(task_id),
            initial_status=status,
        )


class OpenAIVideoGenerationStrategy:
    def generate(
        self,
        *,
        provider_settings: ResolvedVideoProviderSettings,
        prompt: str,
        reference_images: list[str],
        audio_url: str | None = None,
    ) -> VideoGenerationResult:
        if not provider_settings.api_key:
            raise VideoGenerationError("未配置 OpenAI 兼容视频生成 API Key。", status_code=503)
        if not provider_settings.api_base:
            raise VideoGenerationError("未配置 OpenAI 兼容视频生成 API Base。", status_code=503)

        model = resolve_video_generation_model(
            provider_settings=provider_settings,
            reference_images=reference_images,
        )
        payload = build_openai_video_generation_payload(
            model=model,
            prompt=prompt,
            reference_images=reference_images,
        )
        response = openai_video_request_json(
            method="POST",
            url=f"{provider_settings.api_base.rstrip('/')}/videos",
            api_key=provider_settings.api_key or "",
            payload=payload,
        )
        immediate_result = build_openai_video_result_from_response(response)
        if immediate_result is not None:
            return immediate_result

        task_id = extract_nested_value(
            response,
            ("id",),
            ("data", "id"),
            ("result", "id"),
            ("video", "id"),
        )
        if not task_id:
            raise VideoGenerationError("OpenAI 兼容视频生成返回中缺少任务 ID。", status_code=502)

        status = extract_generation_status(response, default="submitted")
        return poll_openai_video_result(
            provider_settings=provider_settings,
            task_id=str(task_id),
            initial_status=status,
        )


VIDEO_GENERATION_STRATEGY_FACTORIES: dict[str, type[VideoGenerationStrategy]] = {
    "openai": OpenAIVideoGenerationStrategy,
    "custom": OpenAIVideoGenerationStrategy,
    "doubao": DoubaoVideoGenerationStrategy,
    "qwen": QwenVideoGenerationStrategy,
}


def build_video_generation_strategy(
    provider_settings: ResolvedVideoProviderSettings,
) -> VideoGenerationStrategy:
    provider = provider_settings.provider.strip().lower()
    strategy_factory = VIDEO_GENERATION_STRATEGY_FACTORIES.get(provider)
    if strategy_factory is None:
        return UnsupportedVideoGenerationStrategy()
    return strategy_factory()


def resolve_video_generation_model(
    *,
    provider_settings: ResolvedVideoProviderSettings,
    reference_images: list[str],
) -> str:
    model = (
        provider_settings.image_to_video_model
        if reference_images
        else provider_settings.text_to_video_model
        or provider_settings.model
    )
    if not model:
        raise VideoGenerationError(
            f"未配置 {provider_settings.provider_label} 的视频生成模型。",
            status_code=503,
        )
    return model


def build_doubao_generation_payload(
    *,
    model: str,
    prompt: str,
    reference_images: list[str],
) -> dict[str, object]:
    content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
    for image_url in select_reference_images_for_provider(reference_images):
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                },
            }
        )
    return {
        "model": model,
        "content": content,
    }


def build_openai_video_generation_payload(
    *,
    model: str,
    prompt: str,
    reference_images: list[str],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "prompt": prompt,
    }
    selected_images = select_reference_images_for_provider(reference_images)
    if selected_images:
        # Most OpenAI-compatible /v1/videos gateways accept a single image field
        # for image-to-video generation. We send the first canonical reference.
        payload["image"] = selected_images[0]
    return payload


def build_qwen_video_generation_payload(
    *,
    model: str,
    prompt: str,
    reference_images: list[str],
    audio_url: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "input": {
            "prompt": prompt,
        },
        "parameters": {
            "prompt_extend": True,
            "duration": 10,
        },
    }
    selected_images = select_reference_images_for_provider(reference_images)
    if selected_images:
        payload["input"]["img_url"] = selected_images[0]
        payload["parameters"]["resolution"] = "720P"
        payload["parameters"]["shot_type"] = "multi"
    else:
        payload["parameters"]["size"] = "1280*720"
    if audio_url:
        payload["input"]["audio_url"] = audio_url
        payload["parameters"]["audio"] = True
    return payload


def submit_doubao_generation_task(
    *,
    provider_settings: ResolvedVideoProviderSettings,
    payload: dict[str, object],
) -> VideoGenerationTaskSubmission:
    task_response = doubao_request_json(
        method="POST",
        url=f"{provider_settings.api_base.rstrip('/')}/contents/generations/tasks",
        api_key=provider_settings.api_key or "",
        payload=payload,
    )
    task_id = extract_nested_value(
        task_response,
        ("id",),
        ("task_id",),
        ("data", "id"),
        ("data", "task_id"),
    )
    if not task_id:
        raise VideoGenerationError("豆包视频生成返回中缺少任务 ID。", status_code=502)

    status = str(extract_nested_value(task_response, ("status",), ("data", "status")) or "submitted")
    return VideoGenerationTaskSubmission(task_id=str(task_id), status=status)


def select_reference_images_for_provider(reference_images: list[str]) -> list[str]:
    if len(reference_images) <= 2:
        return reference_images
    return [reference_images[0], reference_images[-1]]


def poll_doubao_video_result(
    *,
    provider_settings: ResolvedVideoProviderSettings,
    task_id: str,
    initial_status: str,
) -> VideoGenerationResult:
    settings = get_settings()
    deadline = settings.video_generation_result_timeout_seconds
    waited = 0.0
    status = initial_status

    while waited <= deadline:
        response = doubao_request_json(
            method="GET",
            url=f"{provider_settings.api_base.rstrip('/')}/contents/generations/tasks/{task_id}",
            api_key=provider_settings.api_key or "",
        )
        status = str(extract_nested_value(response, ("status",), ("data", "status")) or status)
        normalized_status = status.strip().lower()
        if normalized_status in {"succeeded", "success", "completed"}:
            video_url = extract_nested_value(
                response,
                ("content", "video_url"),
                ("data", "content", "video_url"),
                ("result", "video_url"),
                ("data", "result", "video_url"),
            )
            if not video_url:
                raise VideoGenerationError("豆包视频生成已完成，但未返回视频链接。", status_code=502)
            return VideoGenerationResult(task_id=task_id, status=status, video_url=str(video_url))

        if normalized_status in {"failed", "error", "cancelled", "canceled", "expired"}:
            detail = (
                extract_nested_value(
                    response,
                    ("error", "message"),
                    ("message",),
                    ("data", "message"),
                    ("data", "error", "message"),
                )
                or "豆包视频生成任务失败。"
            )
            raise VideoGenerationError(str(detail), status_code=502)

        sleep_seconds = max(settings.video_generation_poll_interval_seconds, 1.0)
        waited += sleep_seconds
        import time

        time.sleep(sleep_seconds)

    raise VideoGenerationError("等待豆包视频生成结果超时，请稍后重试。", status_code=504)


def poll_qwen_video_result(
    *,
    provider_settings: ResolvedVideoProviderSettings,
    task_id: str,
    initial_status: str,
) -> VideoGenerationResult:
    settings = get_settings()
    deadline = settings.video_generation_result_timeout_seconds
    waited = 0.0
    status = initial_status

    while waited <= deadline:
        response = qwen_video_request_json(
            method="GET",
            url=build_qwen_video_task_url(provider_settings.api_base or "", task_id),
            api_key=provider_settings.api_key or "",
        )
        immediate_result = build_qwen_video_result_from_response(response, fallback_task_id=task_id)
        if immediate_result is not None:
            return immediate_result

        status = extract_qwen_generation_status(response, default=status)
        normalized_status = status.strip().lower()
        if normalized_status in {"succeeded", "success", "completed"}:
            raise VideoGenerationError("DashScope 视频生成已完成，但未返回视频链接。", status_code=502)

        if normalized_status in {"failed", "error", "cancelled", "canceled"}:
            detail = extract_qwen_generation_error_detail(response) or "DashScope 视频生成任务失败。"
            raise VideoGenerationError(str(detail), status_code=502)

        sleep_seconds = max(settings.video_generation_poll_interval_seconds, 1.0)
        waited += sleep_seconds
        import time

        time.sleep(sleep_seconds)

    raise VideoGenerationError("等待 DashScope 视频生成结果超时，请稍后重试。", status_code=504)


def poll_openai_video_result(
    *,
    provider_settings: ResolvedVideoProviderSettings,
    task_id: str,
    initial_status: str,
) -> VideoGenerationResult:
    settings = get_settings()
    deadline = settings.video_generation_result_timeout_seconds
    waited = 0.0
    status = initial_status

    while waited <= deadline:
        response = openai_video_request_json(
            method="GET",
            url=f"{provider_settings.api_base.rstrip('/')}/videos/{task_id}",
            api_key=provider_settings.api_key or "",
        )
        immediate_result = build_openai_video_result_from_response(response, fallback_task_id=task_id)
        if immediate_result is not None:
            return immediate_result

        status = extract_generation_status(response, default=status)
        normalized_status = status.strip().lower()
        if normalized_status in {"failed", "error", "cancelled", "canceled", "expired"}:
            detail = extract_generation_error_detail(response) or "OpenAI 兼容视频生成任务失败。"
            raise VideoGenerationError(str(detail), status_code=502)

        sleep_seconds = max(settings.video_generation_poll_interval_seconds, 1.0)
        waited += sleep_seconds
        import time

        time.sleep(sleep_seconds)

    raise VideoGenerationError("等待 OpenAI 兼容视频生成结果超时，请稍后重试。", status_code=504)


def build_openai_video_result_from_response(
    response: dict[str, object],
    *,
    fallback_task_id: str | None = None,
) -> VideoGenerationResult | None:
    video_url = extract_openai_video_url(response)
    if not video_url:
        return None

    status = extract_generation_status(response, default="completed")
    task_id = str(
        extract_nested_value(
            response,
            ("id",),
            ("data", "id"),
            ("result", "id"),
            ("video", "id"),
        )
        or fallback_task_id
        or "openai-video"
    )
    return VideoGenerationResult(task_id=task_id, status=status, video_url=video_url)


def build_qwen_video_result_from_response(
    response: dict[str, object],
    *,
    fallback_task_id: str | None = None,
) -> VideoGenerationResult | None:
    video_url = extract_qwen_video_url(response)
    if not video_url:
        return None

    status = extract_qwen_generation_status(response, default="completed")
    task_id = str(
        extract_nested_value(
            response,
            ("output", "task_id"),
            ("task_id",),
            ("id",),
        )
        or fallback_task_id
        or "dashscope-video"
    )
    return VideoGenerationResult(task_id=task_id, status=status, video_url=video_url)


def extract_openai_video_url(response: dict[str, object]) -> str | None:
    direct_url = extract_nested_value(
        response,
        ("url",),
        ("video_url",),
        ("data", "url"),
        ("data", "video_url"),
        ("result", "url"),
        ("result", "video_url"),
        ("video", "url"),
        ("video", "video_url"),
        ("output", "url"),
        ("output", "video_url"),
    )
    if isinstance(direct_url, str) and direct_url.strip():
        return direct_url.strip()

    for list_key in ("data", "output", "result", "videos"):
        collection = response.get(list_key)
        if not isinstance(collection, list):
            continue
        for item in collection:
            if not isinstance(item, dict):
                continue
            for field in ("url", "video_url", "download_url", "file_url"):
                candidate = item.get(field)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
            nested_video = item.get("video")
            if isinstance(nested_video, dict):
                for field in ("url", "video_url", "download_url", "file_url"):
                    candidate = nested_video.get(field)
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip()
    return None


def extract_qwen_video_url(response: dict[str, object]) -> str | None:
    direct_url = extract_nested_value(
        response,
        ("output", "video_url"),
        ("output", "url"),
        ("result", "video_url"),
    )
    if isinstance(direct_url, str) and direct_url.strip():
        return direct_url.strip()

    output = response.get("output")
    if isinstance(output, dict):
        results = output.get("results")
        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue
                for field in ("video_url", "url", "file_url"):
                    candidate = item.get(field)
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip()
        elif isinstance(results, dict):
            for field in ("video_url", "url", "file_url"):
                candidate = results.get(field)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
    return None


def extract_generation_status(response: dict[str, object], *, default: str) -> str:
    value = extract_nested_value(
        response,
        ("status",),
        ("data", "status"),
        ("result", "status"),
        ("video", "status"),
    )
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def extract_generation_error_detail(response: dict[str, object]) -> str | None:
    value = extract_nested_value(
        response,
        ("error", "message"),
        ("message",),
        ("data", "message"),
        ("data", "error", "message"),
        ("result", "message"),
    )
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def extract_qwen_generation_status(response: dict[str, object], *, default: str) -> str:
    value = extract_nested_value(
        response,
        ("output", "task_status"),
        ("task_status",),
        ("status",),
        ("data", "status"),
    )
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def extract_qwen_generation_error_detail(response: dict[str, object]) -> str | None:
    value = extract_nested_value(
        response,
        ("output", "message"),
        ("message",),
        ("error", "message"),
        ("data", "message"),
    )
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def doubao_request_json(
    *,
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = request.Request(
        url=url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    timeout_seconds = max(get_settings().openai_request_timeout_seconds, 30)

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw or "{}")
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        payload = {}
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            payload = {}
        detail = (
            extract_nested_value(payload, ("error", "message"), ("message",))
            or raw.strip()
            or exc.reason
            or "豆包视频生成请求失败。"
        )
        raise VideoGenerationError(
            normalize_doubao_video_error_detail(
                str(detail),
                status_code=exc.code,
                payload=payload,
            ),
            status_code=exc.code,
        ) from exc
    except error.URLError as exc:
        raise VideoGenerationError(
            f"豆包视频生成网络请求失败：{str(exc.reason).strip() or exc.__class__.__name__}",
            status_code=503,
        ) from exc


def qwen_video_request_json(
    *,
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if method.upper() == "POST":
        headers["X-DashScope-Async"] = "enable"
    req = request.Request(
        url=url,
        data=body,
        method=method,
        headers=headers,
    )
    timeout_seconds = max(get_settings().openai_request_timeout_seconds, 30)

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw or "{}")
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        payload = {}
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            payload = {}
        detail = (
            extract_qwen_generation_error_detail(payload)
            or raw.strip()
            or exc.reason
            or "DashScope 视频生成请求失败。"
        )
        raise VideoGenerationError(
            normalize_qwen_video_error_detail(
                str(detail),
                status_code=exc.code,
                payload=payload,
            ),
            status_code=exc.code,
        ) from exc
    except error.URLError as exc:
        raise VideoGenerationError(
            f"DashScope 视频生成网络请求失败：{str(exc.reason).strip() or exc.__class__.__name__}",
            status_code=503,
        ) from exc


def openai_video_request_json(
    *,
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = request.Request(
        url=url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    timeout_seconds = max(get_settings().openai_request_timeout_seconds, 30)

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw or "{}")
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        payload = {}
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            payload = {}
        detail = (
            extract_generation_error_detail(payload)
            or raw.strip()
            or exc.reason
            or "OpenAI 兼容视频生成请求失败。"
        )
        raise VideoGenerationError(
            normalize_openai_video_error_detail(
                str(detail),
                status_code=exc.code,
                payload=payload,
            ),
            status_code=exc.code,
        ) from exc
    except error.URLError as exc:
        raise VideoGenerationError(
            f"OpenAI 兼容视频生成网络请求失败：{str(exc.reason).strip() or exc.__class__.__name__}",
            status_code=503,
        ) from exc


def normalize_doubao_video_error_detail(
    detail: str,
    *,
    status_code: int,
    payload: dict[str, object],
) -> str:
    error_code = str(extract_nested_value(payload, ("error", "code"), ("code",)) or "").strip()
    normalized_detail = detail.strip()

    if status_code == 401 or error_code == "ApiKey.Invalid":
        return (
            "豆包视频生成鉴权失败：当前 API Key 无法调用方舟视频生成接口。"
            "请在火山方舟控制台确认该 Key 已开通内容生成能力，并重新保存到系统设置的视频生成服务。"
        )

    return normalized_detail or "豆包视频生成请求失败。"


def normalize_qwen_video_error_detail(
    detail: str,
    *,
    status_code: int,
    payload: dict[str, object],
) -> str:
    error_code = str(extract_nested_value(payload, ("code",), ("error", "code")) or "").strip()
    normalized_detail = detail.strip()

    if status_code in {401, 403} or error_code in {"InvalidApiKey", "AccessDenied"}:
        return (
            "DashScope 视频生成鉴权失败：请检查 API Key 是否有效，"
            "并确认当前百炼账号已开通万相视频生成权限。"
        )
    if status_code == 404:
        return (
            "未找到 DashScope 视频生成接口：请确认服务地址可访问 "
            "/api/v1/services/aigc/video-generation/video-synthesis。"
        )

    return normalized_detail or "DashScope 视频生成请求失败。"


def normalize_openai_video_error_detail(
    detail: str,
    *,
    status_code: int,
    payload: dict[str, object],
) -> str:
    error_code = str(extract_nested_value(payload, ("error", "code"), ("code",)) or "").strip()
    normalized_detail = detail.strip()
    lowered_detail = normalized_detail.lower()

    if status_code in {401, 403} or error_code in {"invalid_api_key", "authentication_error"}:
        return (
            "OpenAI 兼容视频生成鉴权失败：请检查 API Key 是否有效，"
            "并确认当前第三方平台已开通 /v1/videos 接口权限。"
        )
    if status_code == 404:
        return (
            "未找到 OpenAI 兼容视频生成接口：请确认服务地址支持 /v1/videos。"
            "你可以在系统设置里填写到 /v1，或直接填写完整的 /v1/videos 地址。"
        )
    if "model" in lowered_detail and "not found" in lowered_detail:
        return "OpenAI 兼容视频生成模型不存在：请检查模型名称是否正确。"

    return normalized_detail or "OpenAI 兼容视频生成请求失败。"


def extract_nested_value(payload: object, *paths: tuple[str, ...]) -> object | None:
    if not isinstance(payload, dict):
        return None
    for path in paths:
        current: object = payload
        for key in path:
            if not isinstance(current, dict) or key not in current:
                current = None
                break
            current = current[key]
        if current is not None:
            return current
    return None


DASHSCOPE_VIDEO_SYNTHESIS_SUFFIX = "/api/v1/services/aigc/video-generation/video-synthesis"
DASHSCOPE_VIDEO_SERVICE_SUFFIX = "/api/v1/services/aigc/video-generation"
DASHSCOPE_TASKS_SUFFIX = "/api/v1/tasks"


def build_qwen_video_submission_url(api_base: str) -> str:
    parts = urlsplit(api_base)
    path = parts.path.rstrip("/")
    lowered_path = path.lower()

    if lowered_path.endswith(DASHSCOPE_VIDEO_SYNTHESIS_SUFFIX):
        target_path = path
    elif lowered_path.endswith(DASHSCOPE_VIDEO_SERVICE_SUFFIX):
        target_path = f"{path}/video-synthesis"
    elif lowered_path.endswith(DASHSCOPE_TASKS_SUFFIX):
        target_path = f"{path[: -len(DASHSCOPE_TASKS_SUFFIX)]}/services/aigc/video-generation/video-synthesis"
    elif lowered_path.endswith("/api/v1"):
        target_path = f"{path}/services/aigc/video-generation/video-synthesis"
    else:
        target_path = f"{path}/api/v1/services/aigc/video-generation/video-synthesis"

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            normalize_joined_url_path(target_path),
            parts.query,
            parts.fragment,
        )
    )


def build_qwen_video_task_url(api_base: str, task_id: str) -> str:
    parts = urlsplit(api_base)
    path = parts.path.rstrip("/")
    lowered_path = path.lower()

    if lowered_path.endswith(DASHSCOPE_VIDEO_SYNTHESIS_SUFFIX):
        base_path = path[: -len("/services/aigc/video-generation/video-synthesis")]
    elif lowered_path.endswith(DASHSCOPE_VIDEO_SERVICE_SUFFIX):
        base_path = path[: -len("/services/aigc/video-generation")]
    elif lowered_path.endswith(DASHSCOPE_TASKS_SUFFIX):
        base_path = path
    elif lowered_path.endswith("/api/v1"):
        base_path = path
    else:
        base_path = f"{path}/api/v1"

    target_path = f"{base_path}/tasks/{task_id}"
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            normalize_joined_url_path(target_path),
            parts.query,
            parts.fragment,
        )
    )


def normalize_joined_url_path(path: str) -> str:
    normalized = "/" + "/".join(segment for segment in path.split("/") if segment)
    return normalized or "/"
