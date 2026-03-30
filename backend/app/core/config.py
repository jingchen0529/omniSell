from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OmniSell Video Lab API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:3000"]
    database_scheme: str = "mysql+pymysql"
    database_host: str = "127.0.0.1"
    database_port: int = 3306
    database_user: str = "root"
    database_password: str = ""
    database_name: str = "omni-sell"
    database_url: str | None = None
    database_echo: bool = False
    auth_token_expire_hours: int = 168
    password_reset_token_expire_hours: int = 1
    demo_user_email: str = "demo@omnisell.local"
    demo_user_password: str = "demo123456"
    demo_user_display_name: str = "Demo Creator"
    public_base_url: str | None = None
    uploads_dir: str = "storage/uploads"
    media_work_dir: str = "storage/runtime"
    video_analysis_provider: str = "real"
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    yt_dlp_binary: str = "yt-dlp"
    media_command_timeout_seconds: int = 300
    video_transcription_provider: str = "faster_whisper"
    video_transcription_language: str | None = None
    openai_api_key: str | None = None
    openai_api_base: str | None = None
    openai_audio_model: str = "whisper-1"
    openai_transcription_language: str | None = None
    openai_chat_model: str = "gpt-4o"
    openai_request_timeout_seconds: int = 120
    enable_ai_analysis: bool = True
    video_generation_poll_interval_seconds: float = 8.0
    video_generation_result_timeout_seconds: int = 900
    faster_whisper_model_size: str = "small"
    faster_whisper_device: str = "auto"
    faster_whisper_compute_type: str = "int8"
    faster_whisper_cpu_threads: int = 0
    faster_whisper_num_workers: int = 1
    faster_whisper_beam_size: int = 5
    faster_whisper_vad_filter: bool = True
    faster_whisper_download_root: str = "storage/models"
    project_job_max_attempts: int = 1
    project_job_poll_interval_seconds: float = 2.0
    project_job_lease_seconds: int = 1800
    project_job_worker_id: str | None = None
    project_job_run_embedded_worker: bool | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url

        user = quote(self.database_user)
        password = quote(self.database_password)
        host = self.database_host
        port = self.database_port
        database_name = quote(self.database_name)
        return (
            f"{self.database_scheme}://{user}:{password}@{host}:{port}/{database_name}"
            "?charset=utf8mb4"
        )

    @property
    def uploads_root(self) -> Path:
        uploads_path = Path(self.uploads_dir)
        if uploads_path.is_absolute():
            return uploads_path
        return Path(__file__).resolve().parents[2] / uploads_path

    @property
    def media_work_root(self) -> Path:
        media_path = Path(self.media_work_dir)
        if media_path.is_absolute():
            return media_path
        return Path(__file__).resolve().parents[2] / media_path

    @property
    def faster_whisper_model_root(self) -> Path:
        model_path = Path(self.faster_whisper_download_root)
        if model_path.is_absolute():
            return model_path
        return Path(__file__).resolve().parents[2] / model_path

    @property
    def transcription_language(self) -> str | None:
        return self.video_transcription_language or self.openai_transcription_language

    @property
    def run_embedded_project_worker(self) -> bool:
        if self.project_job_run_embedded_worker is not None:
            return self.project_job_run_embedded_worker
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
