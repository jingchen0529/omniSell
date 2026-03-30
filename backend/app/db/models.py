from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TABLE_PREFIX


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = f"{TABLE_PREFIX}user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    projects: Mapped[list[VideoProject]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    auth_tokens: Mapped[list[AuthToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class AuthToken(Base):
    __tablename__ = f"{TABLE_PREFIX}auth_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey(f"{User.__tablename__}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    user: Mapped[User] = relationship(back_populates="auth_tokens")


class PasswordResetToken(Base):
    __tablename__ = f"{TABLE_PREFIX}password_reset_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey(f"{User.__tablename__}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    user: Mapped[User] = relationship(back_populates="password_reset_tokens")


class SystemSetting(Base):
    __tablename__ = f"{TABLE_PREFIX}system_setting"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proxy_ip: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proxy_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="openai")
    ai_api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_api_base: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_chat_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    video_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="qwen")
    video_api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    video_api_base: Mapped[str | None] = mapped_column(String(255), nullable=True)
    video_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    video_image_to_video_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    video_text_to_video_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class VideoProject(Base):
    __tablename__ = f"{TABLE_PREFIX}video_project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey(f"{User.__tablename__}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_platform: Mapped[str] = mapped_column(String(32), nullable=False, default="tiktok")
    workflow_type: Mapped[str] = mapped_column(String(32), nullable=False, default="analysis")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ai_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    full_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    dialogue_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    narration_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    caption_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    analysis_reference_frames: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_visual_features: Mapped[str | None] = mapped_column(Text, nullable=True)
    remake_generation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    remake_generation_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    remake_generation_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    remake_generation_objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    remake_generation_asset_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    remake_generation_asset_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remake_generation_asset_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    remake_generation_audio_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remake_generation_audio_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    remake_generation_reference_frames: Mapped[str | None] = mapped_column(Text, nullable=True)
    remake_generation_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    remake_generation_storyboard: Mapped[str | None] = mapped_column(Text, nullable=True)
    remake_generation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    remake_generation_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remake_generation_result_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    remake_generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    remake_generation_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
    user: Mapped[User] = relationship(back_populates="projects")
    transcript_segments: Mapped[list[VideoTranscriptSegment]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by=lambda: VideoTranscriptSegment.display_order,
    )
    remake_scenes: Mapped[list[VideoRemakeScene]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by=lambda: VideoRemakeScene.scene_index,
    )
    task_steps: Mapped[list[VideoProjectTaskStep]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by=lambda: VideoProjectTaskStep.display_order,
    )
    jobs: Mapped[list[VideoProjectJob]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by=lambda: VideoProjectJob.created_at.desc(),
    )

class VideoTranscriptSegment(Base):
    __tablename__ = f"{TABLE_PREFIX}video_transcript_segment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey(f"{VideoProject.__tablename__}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(80), nullable=True)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    project: Mapped[VideoProject] = relationship(back_populates="transcript_segments")


class VideoRemakeScene(Base):
    __tablename__ = f"{TABLE_PREFIX}video_remake_scene"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey(f"{VideoProject.__tablename__}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scene_index: Mapped[int] = mapped_column(Integer, nullable=False)
    visual_direction: Mapped[str] = mapped_column(Text, nullable=False)
    shot_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    voiceover: Mapped[str] = mapped_column(Text, nullable=False)
    on_screen_text: Mapped[str] = mapped_column(Text, nullable=False)
    editing_notes: Mapped[str] = mapped_column(Text, nullable=False)
    project: Mapped[VideoProject] = relationship(back_populates="remake_scenes")


class VideoProjectTaskStep(Base):
    __tablename__ = f"{TABLE_PREFIX}video_project_task_step"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey(f"{VideoProject.__tablename__}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    detail: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
    project: Mapped[VideoProject] = relationship(back_populates="task_steps")


class VideoProjectJob(Base):
    __tablename__ = f"{TABLE_PREFIX}video_project_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey(f"{VideoProject.__tablename__}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, default="project_analysis")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    worker_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
    project: Mapped[VideoProject] = relationship(back_populates="jobs")
