from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings
from app.db.init_db import initialize_database
from app.db.models import User, VideoProject, VideoProjectJob
from app.db.session import get_session_factory, reset_database_state
from app.tasks import analysis_tasks
from app.tasks.queue import (
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
    process_next_project_job,
    queue_project_processing,
    utcnow,
)
from app.workflows.registry import (
    PROJECT_CREATE_JOB_TYPE,
    PROJECT_REMAKE_JOB_TYPE,
    PROJECT_WORKFLOW_CREATE,
    PROJECT_WORKFLOW_REMAKE,
    build_task_steps,
)
from app.services.media_tools import MediaAnalysisData, RawTranscriptSegment, VideoMediaMetadata
from app.services.video_pipeline import build_mock_project_analysis


@pytest.fixture
def worker_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = tmp_path / "worker.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("VIDEO_ANALYSIS_PROVIDER", "mock")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_NAME", "OmniSell Worker Test API")
    get_settings.cache_clear()
    reset_database_state()
    initialize_database()
    yield
    reset_database_state()
    get_settings.cache_clear()


def create_project(workflow_type: str = "analysis") -> int:
    session_factory = get_session_factory()
    with session_factory() as session:
        user = User(
            email=f"worker-{utcnow().timestamp()}@example.com",
            display_name="Worker User",
            password_hash="not-used-in-test",
        )
        session.add(user)
        session.flush()

        project = VideoProject(
            user_id=user.id,
            title="Worker Queue Test",
            source_url="https://www.tiktok.com/@creator/video/7499999999999999999",
            source_platform="tiktok",
            workflow_type=workflow_type,
            status="processing",
            objective="提取完整脚本、字幕并生成复刻方案",
            summary="任务已创建，等待后台处理。",
            task_steps=build_task_steps(workflow_type),
        )
        session.add(project)
        session.commit()
        session.refresh(project)
        return project.id


def test_queue_project_processing_enqueues_job_outside_test_env(worker_env: None) -> None:
    project_id = create_project()

    job_id = queue_project_processing(project_id)

    session_factory = get_session_factory()
    with session_factory() as session:
        job = session.get(VideoProjectJob, job_id)
        project = session.get(VideoProject, project_id)

        assert job is not None
        assert job.status == JOB_STATUS_QUEUED
        assert job.attempt == 0
        assert project is not None
        assert project.status == "processing"


def test_queue_project_processing_uses_create_job_type(worker_env: None) -> None:
    project_id = create_project()

    job_id = queue_project_processing(project_id, workflow_type=PROJECT_WORKFLOW_CREATE)

    session_factory = get_session_factory()
    with session_factory() as session:
        job = session.get(VideoProjectJob, job_id)

        assert job is not None
        assert job.job_type == PROJECT_CREATE_JOB_TYPE


def test_queue_project_processing_uses_remake_job_type(worker_env: None) -> None:
    project_id = create_project()

    job_id = queue_project_processing(project_id, workflow_type=PROJECT_WORKFLOW_REMAKE)

    session_factory = get_session_factory()
    with session_factory() as session:
        job = session.get(VideoProjectJob, job_id)

        assert job is not None
        assert job.job_type == PROJECT_REMAKE_JOB_TYPE


def test_process_next_project_job_completes_remake_workflow(worker_env: None) -> None:
    project_id = create_project(workflow_type=PROJECT_WORKFLOW_REMAKE)
    queue_project_processing(project_id, workflow_type=PROJECT_WORKFLOW_REMAKE)
    session_factory = get_session_factory()

    processed = process_next_project_job(worker_id="remake-worker")

    assert processed is True

    with session_factory() as session:
        project = session.get(VideoProject, project_id)
        assert project is not None
        assert project.workflow_type == PROJECT_WORKFLOW_REMAKE
        assert project.status == "ready"
        assert project.ai_analysis
        assert all(step.status == "completed" for step in project.task_steps)


def test_process_next_project_job_recovers_expired_running_job(worker_env: None) -> None:
    project_id = create_project()
    job_id = queue_project_processing(project_id)

    session_factory = get_session_factory()
    with session_factory() as session:
        job = session.get(VideoProjectJob, job_id)
        assert job is not None
        job.status = JOB_STATUS_RUNNING
        job.worker_id = "dead-worker"
        job.lease_expires_at = utcnow() - timedelta(seconds=30)
        session.add(job)
        session.commit()

    processed = process_next_project_job(worker_id="replacement-worker")

    assert processed is True

    with session_factory() as session:
        job = session.get(VideoProjectJob, job_id)
        project = session.get(VideoProject, project_id)

        assert job is not None
        assert job.status == JOB_STATUS_SUCCEEDED
        assert job.worker_id == "replacement-worker"
        assert project is not None
        assert project.status == "ready"


def test_process_next_project_job_reports_real_pipeline_progress(
    worker_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEO_ANALYSIS_PROVIDER", "real")
    monkeypatch.setenv("ENABLE_AI_ANALYSIS", "false")
    get_settings.cache_clear()

    project_id = create_project()
    queue_project_processing(project_id)
    session_factory = get_session_factory()

    def fake_collect_media_analysis(_source_url: str, *, progress_callback=None) -> MediaAnalysisData:
        with session_factory() as session:
            project = session.get(VideoProject, project_id)
            assert project is not None
            steps = {step.step_key: step.status for step in project.task_steps}
            assert steps["analyze_video_content"] == "in_progress"
            assert steps["identify_audio_content"] == "pending"

        if progress_callback is not None:
            progress_callback("identify_audio_content")

        with session_factory() as session:
            project = session.get(VideoProject, project_id)
            assert project is not None
            steps = {step.step_key: step.status for step in project.task_steps}
            assert steps["analyze_video_content"] == "completed"
            assert steps["identify_audio_content"] == "in_progress"

        return MediaAnalysisData(
            metadata=VideoMediaMetadata(
                duration_ms=3200,
                width=1080,
                height=1920,
                frame_rate=30.0,
                has_audio=True,
                subtitle_streams=0,
            ),
            transcript_segments=[
                RawTranscriptSegment(
                    segment_type="dialogue",
                    speaker="主讲人",
                    start_ms=0,
                    end_ms=3200,
                    content="真实任务阶段测试文本。",
                )
            ],
            transcript_provider="faster_whisper",
        )

    def fake_build_real_project_analysis(**kwargs):
        with session_factory() as session:
            project = session.get(VideoProject, project_id)
            assert project is not None
            steps = {step.step_key: step.status for step in project.task_steps}
            assert steps["identify_audio_content"] == "completed"
            assert steps["generate_response"] == "in_progress"

        return build_mock_project_analysis(
            source_url="https://www.tiktok.com/@creator/video/7499999999999999999",
            title=kwargs["title"],
            objective=kwargs["objective"],
            source_platform=kwargs["source_platform"],
            source_name=kwargs["source_name"],
        )

    monkeypatch.setattr(analysis_tasks, "collect_media_analysis", fake_collect_media_analysis)
    monkeypatch.setattr(analysis_tasks, "build_real_project_analysis", fake_build_real_project_analysis)

    processed = process_next_project_job(worker_id="real-progress-worker")

    assert processed is True

    with session_factory() as session:
        project = session.get(VideoProject, project_id)
        assert project is not None
        assert project.status == "ready"
        assert all(step.status == "completed" for step in project.task_steps)

    get_settings.cache_clear()


def test_initialize_database_backfills_legacy_system_setting_columns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "legacy.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("VIDEO_ANALYSIS_PROVIDER", "mock")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_NAME", "OmniSell Legacy Schema Test API")
    get_settings.cache_clear()
    reset_database_state()

    legacy_engine = create_engine(f"sqlite:///{database_path}")
    try:
        with legacy_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE os_system_setting (
                        id INTEGER PRIMARY KEY,
                        proxy_ip VARCHAR(255),
                        proxy_port INTEGER,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE os_video_project (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        title VARCHAR(120) NOT NULL,
                        source_url VARCHAR(500) NOT NULL,
                        source_platform VARCHAR(32) NOT NULL DEFAULT 'tiktok',
                        status VARCHAR(32) NOT NULL DEFAULT 'draft',
                        objective TEXT NOT NULL,
                        summary TEXT NOT NULL DEFAULT '',
                        media_url VARCHAR(500),
                        full_text TEXT NOT NULL DEFAULT '',
                        dialogue_text TEXT NOT NULL DEFAULT '',
                        narration_text TEXT NOT NULL DEFAULT '',
                        caption_text TEXT NOT NULL DEFAULT '',
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
    finally:
        legacy_engine.dispose()

    initialize_database()

    inspector = inspect(create_engine(f"sqlite:///{database_path}"))
    system_setting_columns = {column["name"] for column in inspector.get_columns("os_system_setting")}
    video_project_columns = {column["name"] for column in inspector.get_columns("os_video_project")}

    assert {"ai_provider", "ai_api_key", "ai_api_base", "ai_chat_model"}.issubset(system_setting_columns)
    assert {"ai_analysis", "workflow_type"}.issubset(video_project_columns)

    reset_database_state()
    get_settings.cache_clear()
