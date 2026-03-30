from datetime import datetime
from ipaddress import ip_address
from typing import Literal

from pydantic import BaseModel, Field, model_validator

AiProvider = Literal["openai", "doubao", "qwen", "grok", "custom"]
VideoProvider = Literal["openai", "doubao", "qwen", "kling", "veo", "custom"]


class SystemProxySettingsResponse(BaseModel):
    proxy_ip: str | None
    proxy_port: int | None
    proxy_url: str | None
    tiktok_proxy_enabled: bool
    updated_at: datetime


class SystemProxySettingsUpdateRequest(BaseModel):
    proxy_ip: str | None = Field(default=None, max_length=255)
    proxy_port: int | None = Field(default=None, ge=1, le=65535)

    @model_validator(mode="after")
    def validate_proxy_pair(self) -> "SystemProxySettingsUpdateRequest":
        normalized_ip = (self.proxy_ip or "").strip() or None
        if normalized_ip is None and self.proxy_port is None:
            self.proxy_ip = None
            return self

        if normalized_ip is None or self.proxy_port is None:
            raise ValueError("Proxy IP and port must be provided together.")

        try:
            ip_address(normalized_ip)
        except ValueError as exc:
            raise ValueError("Proxy IP must be a valid IPv4 or IPv6 address.") from exc

        self.proxy_ip = normalized_ip
        return self


class SystemAiSettingsResponse(BaseModel):
    ai_provider: AiProvider
    ai_provider_label: str
    ai_api_key: str | None
    ai_api_key_configured: bool
    ai_api_key_source: Literal["database", "environment", "unset"]
    ai_api_base: str | None
    ai_chat_model: str | None
    ai_config_source: Literal["database", "environment"]
    is_ready: bool
    updated_at: datetime


class SystemAiSettingsUpdateRequest(BaseModel):
    ai_provider: AiProvider = "openai"
    ai_api_key: str | None = Field(default=None, max_length=255)
    ai_api_base: str | None = Field(default=None, max_length=255)
    ai_chat_model: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def normalize_fields(self) -> "SystemAiSettingsUpdateRequest":
        self.ai_api_key = (self.ai_api_key or "").strip() or None
        self.ai_api_base = (self.ai_api_base or "").strip() or None
        self.ai_chat_model = (self.ai_chat_model or "").strip() or None

        if self.ai_api_base is not None and not self.ai_api_base.startswith(("http://", "https://")):
            raise ValueError("AI API base must start with http:// or https://.")

        return self


class SystemVideoSettingsResponse(BaseModel):
    video_provider: VideoProvider
    video_provider_label: str
    video_api_key: str | None
    video_api_key_configured: bool
    video_api_key_source: Literal["database", "unset"]
    video_api_base: str | None
    video_model: str | None
    video_image_to_video_model: str | None
    video_text_to_video_model: str | None
    is_ready: bool
    updated_at: datetime


class SystemVideoSettingsUpdateRequest(BaseModel):
    video_provider: VideoProvider = "qwen"
    video_api_key: str | None = Field(default=None, max_length=255)
    video_api_base: str | None = Field(default=None, max_length=255)
    video_model: str | None = Field(default=None, max_length=120)
    video_image_to_video_model: str | None = Field(default=None, max_length=120)
    video_text_to_video_model: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def normalize_fields(self) -> "SystemVideoSettingsUpdateRequest":
        self.video_api_key = (self.video_api_key or "").strip() or None
        self.video_api_base = (self.video_api_base or "").strip() or None
        self.video_model = (self.video_model or "").strip() or None
        self.video_image_to_video_model = (self.video_image_to_video_model or "").strip() or None
        self.video_text_to_video_model = (self.video_text_to_video_model or "").strip() or None

        if self.video_api_base is not None and not self.video_api_base.startswith(("http://", "https://")):
            raise ValueError("Video API base must start with http:// or https://.")

        return self
