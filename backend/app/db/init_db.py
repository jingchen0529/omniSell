import json
from dataclasses import asdict

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import User, VideoProject, VideoProjectTaskStep, VideoRemakeScene, VideoTranscriptSegment
from app.db.session import get_engine, get_session_factory
from app.services.video_pipeline import build_mock_project_analysis
from app.workflows.registry import build_task_steps

LEGACY_COLUMN_UPDATES: dict[str, dict[str, str]] = {
    "os_system_setting": {
        "ai_provider": "VARCHAR(32) NOT NULL DEFAULT 'openai'",
        "ai_api_key": "VARCHAR(255) NULL",
        "ai_api_base": "VARCHAR(255) NULL",
        "ai_chat_model": "VARCHAR(120) NULL",
        "video_provider": "VARCHAR(32) NOT NULL DEFAULT 'qwen'",
        "video_api_key": "VARCHAR(255) NULL",
        "video_api_base": "VARCHAR(255) NULL",
        "video_model": "VARCHAR(120) NULL",
        "video_image_to_video_model": "VARCHAR(120) NULL",
        "video_text_to_video_model": "VARCHAR(120) NULL",
    },
    "os_video_project": {
        "workflow_type": "VARCHAR(32) NOT NULL DEFAULT 'analysis'",
        "ai_analysis": "TEXT NULL",
        "analysis_reference_frames": "TEXT NULL",
        "analysis_visual_features": "TEXT NULL",
        "remake_generation_status": "VARCHAR(32) NOT NULL DEFAULT 'idle'",
        "remake_generation_provider": "VARCHAR(32) NULL",
        "remake_generation_model": "VARCHAR(120) NULL",
        "remake_generation_objective": "TEXT NULL",
        "remake_generation_asset_type": "VARCHAR(16) NULL",
        "remake_generation_asset_name": "VARCHAR(255) NULL",
        "remake_generation_asset_url": "VARCHAR(500) NULL",
        "remake_generation_audio_name": "VARCHAR(255) NULL",
        "remake_generation_audio_url": "VARCHAR(1000) NULL",
        "remake_generation_reference_frames": "TEXT NULL",
        "remake_generation_script": "TEXT NULL",
        "remake_generation_storyboard": "TEXT NULL",
        "remake_generation_prompt": "TEXT NULL",
        "remake_generation_task_id": "VARCHAR(255) NULL",
        "remake_generation_result_url": "VARCHAR(1000) NULL",
        "remake_generation_error": "TEXT NULL",
        "remake_generation_updated_at": "DATETIME NULL",
    },
}


def initialize_database() -> None:
    ensure_database_exists()
    Base.metadata.create_all(bind=get_engine())
    apply_legacy_schema_updates()
    seed_demo_data()


def ensure_database_exists() -> None:
    settings = get_settings()
    database_url = make_url(settings.sqlalchemy_database_uri)

    if database_url.get_backend_name() != "mysql":
        return

    admin_engine = create_engine(
        database_url.set(database="mysql"),
        echo=settings.database_echo,
        pool_pre_ping=True,
    )

    database_name = (database_url.database or settings.database_name).replace("`", "``")
    create_database_sql = text(
        f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )

    try:
        with admin_engine.connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.execute(create_database_sql)
    finally:
        admin_engine.dispose()


def seed_demo_data() -> None:
    session_factory = get_session_factory()

    with session_factory() as session:
        settings = get_settings()
        user = session.scalar(select(User).where(User.email == settings.demo_user_email).limit(1))
        if user is None:
            user = User(
                email=settings.demo_user_email,
                display_name=settings.demo_user_display_name,
                password_hash=hash_password(settings.demo_user_password),
            )
            session.add(user)
            session.flush()

        existing_project = session.scalar(
            select(VideoProject).where(VideoProject.user_id == user.id).limit(1)
        )
        if existing_project is not None:
            session.commit()
            return

        analysis = build_mock_project_analysis(
            source_url="https://www.tiktok.com/@demo/video/7490000000000000000",
            title="TikTok 钩子拆解示例",
            objective="提取完整口播、字幕并生成一版可复刻的短视频方案",
        )
        project = VideoProject(
            user_id=user.id,
            title=analysis.title,
            source_url="https://www.tiktok.com/@demo/video/7490000000000000000",
            source_platform="tiktok",
            workflow_type="analysis",
            status=analysis.status,
            objective="提取完整口播、字幕并生成一版可复刻的短视频方案",
            summary=analysis.summary,
            full_text=analysis.full_text,
            dialogue_text=analysis.dialogue_text,
            narration_text=analysis.narration_text,
            caption_text=analysis.caption_text,
            analysis_reference_frames=(
                json.dumps(analysis.reference_frame_urls, ensure_ascii=False)
                if analysis.reference_frame_urls
                else None
            ),
            analysis_visual_features=(
                json.dumps(asdict(analysis.visual_feature_analysis), ensure_ascii=False)
                if analysis.visual_feature_analysis is not None
                else None
            ),
            transcript_segments=[
                VideoTranscriptSegment(
                    segment_type=segment.segment_type,
                    speaker=segment.speaker,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    content=segment.content,
                    display_order=segment.display_order,
                )
                for segment in analysis.transcript_segments
            ],
            remake_scenes=[
                VideoRemakeScene(
                    scene_index=scene.scene_index,
                    visual_direction=scene.visual_direction,
                    shot_prompt=scene.shot_prompt,
                    voiceover=scene.voiceover,
                    on_screen_text=scene.on_screen_text,
                    editing_notes=scene.editing_notes,
                )
                for scene in analysis.remake_scenes
            ],
            task_steps=[
                VideoProjectTaskStep(
                    step_key=step.step_key,
                    title=step.title,
                    detail=step.detail,
                    status="completed",
                    display_order=step.display_order,
                )
                for step in build_task_steps()
            ],
        )
        session.add(project)
        session.commit()


def apply_legacy_schema_updates() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table_name, pending_columns in LEGACY_COLUMN_UPDATES.items():
            if table_name not in existing_tables:
                continue

            existing_columns = {column["name"] for column in inspect(engine).get_columns(table_name)}
            for column_name, column_definition in pending_columns.items():
                if column_name in existing_columns:
                    continue

                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
                )
                existing_columns.add(column_name)
