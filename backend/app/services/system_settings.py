from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import SystemSetting
from app.db.session import get_session_factory

SYSTEM_SETTINGS_SINGLETON_ID = 1


@dataclass(frozen=True)
class AiProviderPreset:
    provider: str
    label: str
    default_api_base: str | None = None
    default_chat_model: str | None = None


@dataclass(frozen=True)
class ResolvedAiProviderSettings:
    provider: str
    provider_label: str
    api_key: str | None
    api_key_source: str
    api_base: str | None
    chat_model: str | None
    config_source: str

    @property
    def is_ready(self) -> bool:
        return bool(self.api_key and self.chat_model)


@dataclass(frozen=True)
class VideoProviderPreset:
    provider: str
    label: str
    default_api_base: str | None = None
    default_model: str | None = None
    default_image_to_video_model: str | None = None
    default_text_to_video_model: str | None = None


@dataclass(frozen=True)
class ResolvedVideoProviderSettings:
    provider: str
    provider_label: str
    api_key: str | None
    api_key_source: str
    api_base: str | None
    model: str | None
    image_to_video_model: str | None
    text_to_video_model: str | None

    @property
    def is_ready(self) -> bool:
        return bool(
            self.api_key
            and self.api_base
            and (self.image_to_video_model or self.text_to_video_model or self.model)
        )


AI_PROVIDER_PRESETS: dict[str, AiProviderPreset] = {
    "openai": AiProviderPreset(
        provider="openai",
        label="ChatGPT / OpenAI",
        default_api_base=None,
        default_chat_model="gpt-4o",
    ),
    "doubao": AiProviderPreset(
        provider="doubao",
        label="豆包 / 火山方舟",
        default_api_base="https://ark.cn-beijing.volces.com/api/v3",
        default_chat_model=None,
    ),
    "qwen": AiProviderPreset(
        provider="qwen",
        label="千问 / DashScope",
        default_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_chat_model="qwen-plus",
    ),
    "grok": AiProviderPreset(
        provider="grok",
        label="Grok / xAI",
        default_api_base="https://api.x.ai/v1",
        default_chat_model="grok-4",
    ),
    "custom": AiProviderPreset(
        provider="custom",
        label="自定义 OpenAI 兼容服务",
    ),
}

VIDEO_PROVIDER_PRESETS: dict[str, VideoProviderPreset] = {
    "openai": VideoProviderPreset(
        provider="openai",
        label="OpenAI 兼容视频接口（/v1/videos）",
    ),
    "doubao": VideoProviderPreset(
        provider="doubao",
        label="豆包视频 / 火山方舟",
        default_api_base="https://ark.cn-beijing.volces.com/api/v3",
        default_model="doubao-seedance-1-5-pro-251215",
        default_image_to_video_model="doubao-seedance-1-5-pro-251215",
        default_text_to_video_model="doubao-seedance-1-5-pro-251215",
    ),
    "qwen": VideoProviderPreset(
        provider="qwen",
        label="通义万相 / DashScope",
        default_api_base="https://dashscope.aliyuncs.com/api/v1",
        default_model="wan2.6-i2v",
        default_image_to_video_model="wan2.6-i2v",
        default_text_to_video_model="wan2.6-t2v",
    ),
    "kling": VideoProviderPreset(
        provider="kling",
        label="可灵视频 / Kling",
    ),
    "veo": VideoProviderPreset(
        provider="veo",
        label="Google Veo",
    ),
    "custom": VideoProviderPreset(
        provider="custom",
        label="自定义 OpenAI 兼容视频服务",
    ),
}

OPENAI_COMPATIBLE_ENDPOINT_SUFFIXES = (
    "/chat/completions",
    "/completions",
    "/audio/transcriptions",
    "/audio/translations",
)

VIDEO_GENERATION_ENDPOINT_SUFFIXES = (
    "/services/aigc/video-generation/video-synthesis",
    "/services/aigc/video-generation",
    "/videos",
    "/contents/generations/tasks",
    "/contents/generations",
    "/tasks",
)


def get_or_create_system_setting(db: Session) -> SystemSetting:
    system_setting = get_existing_system_setting(db)
    if system_setting is not None:
        return system_setting

    system_setting = SystemSetting(id=SYSTEM_SETTINGS_SINGLETON_ID)
    db.add(system_setting)
    db.commit()
    db.refresh(system_setting)
    return system_setting


def get_existing_system_setting(db: Session) -> SystemSetting | None:
    system_setting = db.get(SystemSetting, SYSTEM_SETTINGS_SINGLETON_ID)
    if system_setting is not None:
        return system_setting

    statement = select(SystemSetting).order_by(SystemSetting.id.asc()).limit(1)
    return db.execute(statement).scalars().first()


def normalize_ai_provider(provider: str | None) -> str:
    normalized = (provider or "").strip().lower()
    if normalized in AI_PROVIDER_PRESETS:
        return normalized
    return "openai"


def normalize_optional_value(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def normalize_openai_compatible_api_base(api_base: str | None) -> str | None:
    normalized = normalize_optional_value(api_base)
    if normalized is None:
        return None

    parts = urlsplit(normalized)
    path = parts.path.rstrip("/")
    lowered_path = path.lower()

    for suffix in OPENAI_COMPATIBLE_ENDPOINT_SUFFIXES:
        if lowered_path.endswith(suffix):
            path = path[: -len(suffix)]
            break

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            path.rstrip("/"),
            parts.query,
            parts.fragment,
        )
    )


def normalize_video_provider(provider: str | None) -> str:
    normalized = (provider or "").strip().lower()
    if normalized in VIDEO_PROVIDER_PRESETS:
        return normalized
    return "qwen"


def normalize_video_generation_api_base(api_base: str | None) -> str | None:
    normalized = normalize_optional_value(api_base)
    if normalized is None:
        return None

    parts = urlsplit(normalized)
    path = parts.path.rstrip("/")
    lowered_path = path.lower()

    for suffix in VIDEO_GENERATION_ENDPOINT_SUFFIXES:
        if lowered_path.endswith(suffix):
            path = path[: -len(suffix)]
            break

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            path.rstrip("/"),
            parts.query,
            parts.fragment,
        )
    )


def build_proxy_url(proxy_ip: str | None, proxy_port: int | None) -> str | None:
    if not proxy_ip or proxy_port is None:
        return None

    host = proxy_ip.strip()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{proxy_port}"


def update_system_proxy_settings(
    db: Session,
    proxy_ip: str | None,
    proxy_port: int | None,
) -> SystemSetting:
    system_setting = get_or_create_system_setting(db)
    system_setting.proxy_ip = proxy_ip
    system_setting.proxy_port = proxy_port
    db.add(system_setting)
    db.commit()
    db.refresh(system_setting)
    return system_setting


def update_system_ai_settings(
    db: Session,
    ai_provider: str,
    ai_api_key: str | None,
    ai_api_base: str | None,
    ai_chat_model: str | None,
) -> SystemSetting:
    system_setting = get_or_create_system_setting(db)
    system_setting.ai_provider = normalize_ai_provider(ai_provider)
    system_setting.ai_api_key = normalize_optional_value(ai_api_key)
    system_setting.ai_api_base = normalize_openai_compatible_api_base(ai_api_base)
    system_setting.ai_chat_model = normalize_optional_value(ai_chat_model)
    db.add(system_setting)
    db.commit()
    db.refresh(system_setting)
    return system_setting


def update_system_video_settings(
    db: Session,
    video_provider: str,
    video_api_key: str | None,
    video_api_base: str | None,
    video_model: str | None,
    video_image_to_video_model: str | None,
    video_text_to_video_model: str | None,
) -> SystemSetting:
    system_setting = get_or_create_system_setting(db)
    system_setting.video_provider = normalize_video_provider(video_provider)
    system_setting.video_api_key = normalize_optional_value(video_api_key)
    system_setting.video_api_base = normalize_video_generation_api_base(video_api_base)
    system_setting.video_model = normalize_optional_value(video_model)
    system_setting.video_image_to_video_model = normalize_optional_value(video_image_to_video_model)
    system_setting.video_text_to_video_model = normalize_optional_value(video_text_to_video_model)
    db.add(system_setting)
    db.commit()
    db.refresh(system_setting)
    return system_setting


def has_custom_ai_settings(system_setting: SystemSetting | None) -> bool:
    if system_setting is None:
        return False

    return any(
        [
            normalize_ai_provider(system_setting.ai_provider) != "openai",
            normalize_optional_value(system_setting.ai_api_key) is not None,
            normalize_optional_value(system_setting.ai_api_base) is not None,
            normalize_optional_value(system_setting.ai_chat_model) is not None,
        ]
    )


def has_custom_video_settings(system_setting: SystemSetting | None) -> bool:
    if system_setting is None:
        return False

    return any(
        [
            normalize_video_provider(system_setting.video_provider) != "qwen",
            normalize_optional_value(system_setting.video_api_key) is not None,
            normalize_optional_value(system_setting.video_api_base) is not None,
            normalize_optional_value(system_setting.video_model) is not None,
            normalize_optional_value(system_setting.video_image_to_video_model) is not None,
            normalize_optional_value(system_setting.video_text_to_video_model) is not None,
        ]
    )


def resolve_ai_provider_settings(system_setting: SystemSetting | None = None) -> ResolvedAiProviderSettings:
    settings = get_settings()

    if system_setting is None:
        try:
            session_factory = get_session_factory()
            with session_factory() as session:
                system_setting = get_existing_system_setting(session)
        except Exception:  # noqa: BLE001
            system_setting = None

    if has_custom_ai_settings(system_setting):
        provider = normalize_ai_provider(system_setting.ai_provider if system_setting else None)
        preset = AI_PROVIDER_PRESETS[provider]
        api_key = normalize_optional_value(system_setting.ai_api_key if system_setting else None)
        api_base = normalize_openai_compatible_api_base(system_setting.ai_api_base if system_setting else None)
        chat_model = normalize_optional_value(system_setting.ai_chat_model if system_setting else None)

        return ResolvedAiProviderSettings(
            provider=provider,
            provider_label=preset.label,
            api_key=api_key,
            api_key_source="database" if api_key else "unset",
            api_base=api_base if api_base is not None else preset.default_api_base,
            chat_model=chat_model if chat_model is not None else preset.default_chat_model,
            config_source="database",
        )

    preset = AI_PROVIDER_PRESETS["openai"]
    api_key = normalize_optional_value(settings.openai_api_key)
    api_base = normalize_openai_compatible_api_base(settings.openai_api_base)
    chat_model = normalize_optional_value(settings.openai_chat_model) or preset.default_chat_model

    return ResolvedAiProviderSettings(
        provider="openai",
        provider_label=preset.label,
        api_key=api_key,
        api_key_source="environment" if api_key else "unset",
        api_base=api_base,
        chat_model=chat_model,
        config_source="environment",
    )


def resolve_video_provider_settings(system_setting: SystemSetting | None = None) -> ResolvedVideoProviderSettings:
    if system_setting is None:
        try:
            session_factory = get_session_factory()
            with session_factory() as session:
                system_setting = get_existing_system_setting(session)
        except Exception:  # noqa: BLE001
            system_setting = None

    provider = normalize_video_provider(system_setting.video_provider if system_setting else None)
    preset = VIDEO_PROVIDER_PRESETS[provider]

    api_key = normalize_optional_value(system_setting.video_api_key if system_setting else None)
    api_base = normalize_video_generation_api_base(system_setting.video_api_base if system_setting else None)
    model = normalize_optional_value(system_setting.video_model if system_setting else None)
    image_to_video_model = normalize_optional_value(
        system_setting.video_image_to_video_model if system_setting else None
    )
    text_to_video_model = normalize_optional_value(
        system_setting.video_text_to_video_model if system_setting else None
    )

    return ResolvedVideoProviderSettings(
        provider=provider,
        provider_label=preset.label,
        api_key=api_key,
        api_key_source="database" if api_key else "unset",
        api_base=api_base if api_base is not None else preset.default_api_base,
        model=model if model is not None else preset.default_model,
        image_to_video_model=(
            image_to_video_model
            if image_to_video_model is not None
            else preset.default_image_to_video_model
            or model
            or preset.default_model
        ),
        text_to_video_model=(
            text_to_video_model
            if text_to_video_model is not None
            else preset.default_text_to_video_model
            or model
            or preset.default_model
        ),
    )


def get_system_proxy_url() -> str | None:
    session_factory = get_session_factory()
    with session_factory() as session:
        system_setting = get_existing_system_setting(session)
        if system_setting is None:
            return None
        return build_proxy_url(system_setting.proxy_ip, system_setting.proxy_port)
