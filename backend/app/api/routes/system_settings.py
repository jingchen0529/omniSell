from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.system_settings import (
    SystemAiSettingsResponse,
    SystemAiSettingsUpdateRequest,
    SystemProxySettingsResponse,
    SystemProxySettingsUpdateRequest,
    SystemVideoSettingsResponse,
    SystemVideoSettingsUpdateRequest,
)
from app.services.system_settings import (
    build_proxy_url,
    get_or_create_system_setting,
    resolve_ai_provider_settings,
    resolve_video_provider_settings,
    update_system_ai_settings,
    update_system_proxy_settings,
    update_system_video_settings,
)

router = APIRouter(prefix="/system-settings")


@router.get("/proxy", response_model=SystemProxySettingsResponse, summary="Get proxy settings")
def get_proxy_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SystemProxySettingsResponse:
    system_setting = get_or_create_system_setting(db)
    return serialize_proxy_settings(system_setting.proxy_ip, system_setting.proxy_port, system_setting.updated_at)


@router.put("/proxy", response_model=SystemProxySettingsResponse, summary="Update proxy settings")
def update_proxy_settings(
    payload: SystemProxySettingsUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SystemProxySettingsResponse:
    system_setting = update_system_proxy_settings(
        db=db,
        proxy_ip=payload.proxy_ip,
        proxy_port=payload.proxy_port,
    )
    return serialize_proxy_settings(system_setting.proxy_ip, system_setting.proxy_port, system_setting.updated_at)


@router.get("/ai", response_model=SystemAiSettingsResponse, summary="Get AI provider settings")
def get_ai_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SystemAiSettingsResponse:
    system_setting = get_or_create_system_setting(db)
    return serialize_ai_settings(system_setting)


@router.put("/ai", response_model=SystemAiSettingsResponse, summary="Update AI provider settings")
def update_ai_settings(
    payload: SystemAiSettingsUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SystemAiSettingsResponse:
    system_setting = update_system_ai_settings(
        db=db,
        ai_provider=payload.ai_provider,
        ai_api_key=payload.ai_api_key,
        ai_api_base=payload.ai_api_base,
        ai_chat_model=payload.ai_chat_model,
    )
    return serialize_ai_settings(system_setting)


@router.get("/video", response_model=SystemVideoSettingsResponse, summary="Get video provider settings")
def get_video_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SystemVideoSettingsResponse:
    system_setting = get_or_create_system_setting(db)
    return serialize_video_settings(system_setting)


@router.put("/video", response_model=SystemVideoSettingsResponse, summary="Update video provider settings")
def update_video_settings(
    payload: SystemVideoSettingsUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SystemVideoSettingsResponse:
    system_setting = update_system_video_settings(
        db=db,
        video_provider=payload.video_provider,
        video_api_key=payload.video_api_key,
        video_api_base=payload.video_api_base,
        video_model=payload.video_model,
        video_image_to_video_model=payload.video_image_to_video_model,
        video_text_to_video_model=payload.video_text_to_video_model,
    )
    return serialize_video_settings(system_setting)


def serialize_proxy_settings(
    proxy_ip: str | None,
    proxy_port: int | None,
    updated_at,
) -> SystemProxySettingsResponse:
    proxy_url = build_proxy_url(proxy_ip, proxy_port)
    return SystemProxySettingsResponse(
        proxy_ip=proxy_ip,
        proxy_port=proxy_port,
        proxy_url=proxy_url,
        tiktok_proxy_enabled=proxy_url is not None,
        updated_at=updated_at,
    )


def serialize_ai_settings(system_setting) -> SystemAiSettingsResponse:
    resolved = resolve_ai_provider_settings(system_setting)
    return SystemAiSettingsResponse(
        ai_provider=resolved.provider,
        ai_provider_label=resolved.provider_label,
        ai_api_key=system_setting.ai_api_key if resolved.config_source == "database" else None,
        ai_api_key_configured=bool(resolved.api_key),
        ai_api_key_source=resolved.api_key_source,
        ai_api_base=resolved.api_base,
        ai_chat_model=resolved.chat_model,
        ai_config_source=resolved.config_source,
        is_ready=resolved.is_ready,
        updated_at=system_setting.updated_at,
    )


def serialize_video_settings(system_setting) -> SystemVideoSettingsResponse:
    resolved = resolve_video_provider_settings(system_setting)
    return SystemVideoSettingsResponse(
        video_provider=resolved.provider,
        video_provider_label=resolved.provider_label,
        video_api_key=system_setting.video_api_key,
        video_api_key_configured=bool(resolved.api_key),
        video_api_key_source=resolved.api_key_source,
        video_api_base=resolved.api_base,
        video_model=resolved.model,
        video_image_to_video_model=resolved.image_to_video_model,
        video_text_to_video_model=resolved.text_to_video_model,
        is_ready=resolved.is_ready,
        updated_at=system_setting.updated_at,
    )
