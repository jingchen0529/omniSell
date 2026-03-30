from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.models import SystemSetting, VideoProject
from app.db.session import get_session_factory
from app.db.session import reset_database_state
from app.main import create_app
from app.services.video_generation import VideoGenerationResult


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("VIDEO_ANALYSIS_PROVIDER", "mock")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_NAME", "OmniSell Video Lab API")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_BASE", "")
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "gpt-4o")
    get_settings.cache_clear()
    reset_database_state()

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    reset_database_state()
    get_settings.cache_clear()


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["product"] == "OmniSell Video Lab API"


def test_register_login_and_project_flow(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "creator@example.com",
            "password": "verysecure123",
            "display_name": "Creator",
        },
    )
    assert register_response.status_code == 201
    register_body = register_response.json()
    assert register_body["user"]["email"] == "creator@example.com"
    token = register_body["access_token"]

    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["display_name"] == "Creator"

    create_project_response = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "source_url": "https://www.tiktok.com/@creator/video/7499999999999999999",
            "title": "爆款拆解",
            "objective": "提取完整脚本、字幕并生成一版可复刻的视频方案",
        },
    )
    assert create_project_response.status_code == 201
    project_body = create_project_response.json()
    assert project_body["status"] == "ready"
    assert project_body["source_platform"] == "tiktok"
    assert project_body["workflow_type"] == "analysis"
    assert project_body["source_type"] == "url"
    assert len(project_body["timeline_segments"]) >= 4
    assert project_body["script_overview"]["full_text"]
    assert project_body["ecommerce_analysis"]["title"] == "TikTok 电商效果深度分析"
    assert "source_analysis" in project_body
    assert "remake_scenes" not in project_body

    list_projects_response = client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_projects_response.status_code == 200
    list_body = list_projects_response.json()
    assert len(list_body) == 1
    assert list_body[0]["title"] == "爆款拆解"
    assert list_body[0]["workflow_type"] == "analysis"


def test_create_project_from_youtube_url(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "youtube@example.com",
            "password": "verysecure123",
            "display_name": "YouTube Creator",
        },
    )
    token = register_response.json()["access_token"]

    create_project_response = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "source_url": "https://www.youtube.com/shorts/abc123xyz",
            "title": "Shorts 拆解",
            "objective": "提取节奏结构并生成复刻方案",
        },
    )
    assert create_project_response.status_code == 201
    body = create_project_response.json()
    assert body["source_platform"] == "youtube"
    assert body["workflow_type"] == "analysis"
    assert body["source_type"] == "url"
    assert body["summary"].startswith("围绕 YouTube Shorts")


def test_create_project_from_uploaded_video(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "upload@example.com",
            "password": "verysecure123",
            "display_name": "Upload Creator",
        },
    )
    token = register_response.json()["access_token"]

    create_project_response = client.post(
        "/api/projects/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "title": "本地视频拆解",
            "objective": "提取关键字幕并整理成可复拍的结构化方案",
        },
        files={
            "file": ("sample-video.mp4", b"fake-video-binary", "video/mp4"),
        },
    )
    assert create_project_response.status_code == 201
    body = create_project_response.json()
    assert body["source_platform"] == "local_upload"
    assert body["workflow_type"] == "analysis"
    assert body["source_type"] == "upload"
    assert body["source_name"] == "sample-video.mp4"
    assert body["source_url"].startswith("upload://")


def test_create_project_with_create_workflow_returns_dedicated_steps(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "creative@example.com",
            "password": "verysecure123",
            "display_name": "Creative User",
        },
    )
    token = register_response.json()["access_token"]

    create_project_response = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "source_url": "https://www.tiktok.com/@creator/video/7499999999999999999",
            "title": "创作爆款测试",
            "objective": "基于这个对标视频生成创作方案和优化建议",
            "workflow_type": "create",
        },
    )

    assert create_project_response.status_code == 201
    body = create_project_response.json()
    assert body["workflow_type"] == "create"
    assert [step["step_key"] for step in body["task_steps"]] == [
        "extract_video_link",
        "validate_video_link",
        "analyze_video_content",
        "identify_audio_content",
        "generate_response",
        "generate_suggestions",
        "finish",
    ]
    assert body["task_steps"][0]["title"] == "提取创作参考链接"
    assert body["task_steps"][4]["title"] == "生成创作方案"


def test_create_project_with_remake_workflow_returns_dedicated_steps(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "remake-flow@example.com",
            "password": "verysecure123",
            "display_name": "Remake User",
        },
    )
    token = register_response.json()["access_token"]

    create_project_response = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "source_url": "https://www.tiktok.com/@creator/video/7499999999999999999",
            "title": "复刻爆款测试",
            "objective": "把这个视频拆成可执行的复刻方案 JSON",
            "workflow_type": "remake",
        },
    )

    assert create_project_response.status_code == 201
    body = create_project_response.json()
    assert body["workflow_type"] == "remake"
    assert body["ecommerce_analysis"]["title"] == "TikTok Remake Engine 复刻方案"
    assert body["source_analysis"]["visual_features"]["scene_pace"] == "快切"
    assert body["source_analysis"]["visual_features"]["dominant_palette"]
    assert [step["step_key"] for step in body["task_steps"]] == [
        "visual_breakdown",
        "timing_and_structure",
        "viral_logic_extraction",
        "content_carrier_analysis",
        "remake_plan_generation",
        "variation_strategy_generation",
        "finish",
    ]
    assert body["task_steps"][0]["title"] == "视觉拆解"
    assert body["task_steps"][4]["title"] == "复刻执行方案"


def test_login_with_seeded_demo_user(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "email": "demo@omnisell.local",
            "password": "demo123456",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "demo@omnisell.local"
    assert body["access_token"]


def test_system_proxy_settings_roundtrip(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "settings@example.com",
            "password": "verysecure123",
            "display_name": "Settings User",
        },
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    initial_response = client.get("/api/system-settings/proxy", headers=headers)
    assert initial_response.status_code == 200
    assert initial_response.json()["proxy_ip"] is None
    assert initial_response.json()["tiktok_proxy_enabled"] is False

    update_response = client.put(
        "/api/system-settings/proxy",
        headers=headers,
        json={
            "proxy_ip": "127.0.0.1",
            "proxy_port": 7890,
        },
    )
    assert update_response.status_code == 200
    update_body = update_response.json()
    assert update_body["proxy_ip"] == "127.0.0.1"
    assert update_body["proxy_port"] == 7890
    assert update_body["proxy_url"] == "http://127.0.0.1:7890"
    assert update_body["tiktok_proxy_enabled"] is True

    reload_response = client.get("/api/system-settings/proxy", headers=headers)
    assert reload_response.status_code == 200
    reload_body = reload_response.json()
    assert reload_body["proxy_ip"] == "127.0.0.1"
    assert reload_body["proxy_port"] == 7890


def test_system_ai_settings_roundtrip(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "ai-settings@example.com",
            "password": "verysecure123",
            "display_name": "AI Settings User",
        },
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    initial_response = client.get("/api/system-settings/ai", headers=headers)
    assert initial_response.status_code == 200
    initial_body = initial_response.json()
    assert initial_body["ai_provider"] == "openai"
    assert initial_body["ai_chat_model"] == "gpt-4o"
    assert initial_body["ai_config_source"] == "environment"
    assert initial_body["ai_api_key_configured"] is False

    update_response = client.put(
        "/api/system-settings/ai",
        headers=headers,
        json={
            "ai_provider": "qwen",
            "ai_api_key": "dashscope-test-key",
            "ai_api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "ai_chat_model": "qwen-plus",
        },
    )
    assert update_response.status_code == 200
    update_body = update_response.json()
    assert update_body["ai_provider"] == "qwen"
    assert update_body["ai_provider_label"] == "千问 / DashScope"
    assert update_body["ai_api_key"] == "dashscope-test-key"
    assert update_body["ai_api_key_configured"] is True
    assert update_body["ai_api_key_source"] == "database"
    assert update_body["ai_api_base"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert update_body["ai_chat_model"] == "qwen-plus"
    assert update_body["ai_config_source"] == "database"
    assert update_body["is_ready"] is True

    reload_response = client.get("/api/system-settings/ai", headers=headers)
    assert reload_response.status_code == 200
    reload_body = reload_response.json()
    assert reload_body["ai_provider"] == "qwen"
    assert reload_body["ai_api_base"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert reload_body["ai_chat_model"] == "qwen-plus"


def test_system_ai_settings_normalize_full_endpoint_base(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "doubao-settings@example.com",
            "password": "verysecure123",
            "display_name": "Doubao Settings User",
        },
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    update_response = client.put(
        "/api/system-settings/ai",
        headers=headers,
        json={
            "ai_provider": "doubao",
            "ai_api_key": "ark-test-key",
            "ai_api_base": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            "ai_chat_model": "doubao-seed-1-6-250615",
        },
    )
    assert update_response.status_code == 200
    update_body = update_response.json()
    assert update_body["ai_api_base"] == "https://ark.cn-beijing.volces.com/api/v3"

    reload_response = client.get("/api/system-settings/ai", headers=headers)
    assert reload_response.status_code == 200
    reload_body = reload_response.json()
    assert reload_body["ai_api_base"] == "https://ark.cn-beijing.volces.com/api/v3"


def test_system_video_settings_roundtrip(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "video-settings@example.com",
            "password": "verysecure123",
            "display_name": "Video Settings User",
        },
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    initial_response = client.get("/api/system-settings/video", headers=headers)
    assert initial_response.status_code == 200
    initial_body = initial_response.json()
    assert initial_body["video_provider"] == "qwen"
    assert initial_body["video_provider_label"] == "通义万相 / DashScope"
    assert initial_body["video_api_base"] == "https://dashscope.aliyuncs.com/api/v1"
    assert initial_body["video_model"] == "wan2.6-i2v"
    assert initial_body["video_image_to_video_model"] == "wan2.6-i2v"
    assert initial_body["video_text_to_video_model"] == "wan2.6-t2v"
    assert initial_body["video_api_key_configured"] is False

    update_response = client.put(
        "/api/system-settings/video",
        headers=headers,
        json={
            "video_provider": "doubao",
            "video_api_key": "seedance-test-key",
            "video_api_base": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
            "video_model": "doubao-seedance-1-5-pro-251215",
            "video_image_to_video_model": "doubao-seedance-1-5-pro-251215",
            "video_text_to_video_model": "doubao-seedance-1-5-pro-251215",
        },
    )
    assert update_response.status_code == 200
    update_body = update_response.json()
    assert update_body["video_provider"] == "doubao"
    assert update_body["video_provider_label"] == "豆包视频 / 火山方舟"
    assert update_body["video_api_key"] == "seedance-test-key"
    assert update_body["video_api_base"] == "https://ark.cn-beijing.volces.com/api/v3"
    assert update_body["video_image_to_video_model"] == "doubao-seedance-1-5-pro-251215"
    assert update_body["video_text_to_video_model"] == "doubao-seedance-1-5-pro-251215"
    assert update_body["is_ready"] is True

    reload_response = client.get("/api/system-settings/video", headers=headers)
    assert reload_response.status_code == 200
    reload_body = reload_response.json()
    assert reload_body["video_api_base"] == "https://ark.cn-beijing.volces.com/api/v3"
    assert reload_body["video_api_key_configured"] is True


def test_system_openai_video_settings_roundtrip(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "openai-video-settings@example.com",
            "password": "verysecure123",
            "display_name": "OpenAI Video Settings User",
        },
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    update_response = client.put(
        "/api/system-settings/video",
        headers=headers,
        json={
            "video_provider": "openai",
            "video_api_key": "openai-video-key",
            "video_api_base": "https://example.com/v1/videos",
            "video_model": "wan2.2-i2v-plus",
            "video_image_to_video_model": "wan2.2-i2v-plus",
            "video_text_to_video_model": "wan2.2-t2v",
        },
    )
    assert update_response.status_code == 200
    update_body = update_response.json()
    assert update_body["video_provider"] == "openai"
    assert update_body["video_provider_label"] == "OpenAI 兼容视频接口（/v1/videos）"
    assert update_body["video_api_base"] == "https://example.com/v1"
    assert update_body["video_model"] == "wan2.2-i2v-plus"
    assert update_body["is_ready"] is True


def test_system_qwen_video_settings_roundtrip(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "qwen-video-settings@example.com",
            "password": "verysecure123",
            "display_name": "Qwen Video Settings User",
        },
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    update_response = client.put(
        "/api/system-settings/video",
        headers=headers,
        json={
            "video_provider": "qwen",
            "video_api_key": "dashscope-video-key",
            "video_api_base": "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis",
            "video_model": "wan2.6-i2v",
            "video_image_to_video_model": "wan2.6-i2v",
            "video_text_to_video_model": "wan2.6-t2v",
        },
    )
    assert update_response.status_code == 200
    update_body = update_response.json()
    assert update_body["video_provider"] == "qwen"
    assert update_body["video_provider_label"] == "通义万相 / DashScope"
    assert update_body["video_api_base"] == "https://dashscope.aliyuncs.com/api/v1"
    assert update_body["video_model"] == "wan2.6-i2v"
    assert update_body["video_image_to_video_model"] == "wan2.6-i2v"
    assert update_body["video_text_to_video_model"] == "wan2.6-t2v"
    assert update_body["is_ready"] is True


def test_system_settings_use_existing_row_when_singleton_id_missing(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "existing-settings@example.com",
            "password": "verysecure123",
            "display_name": "Existing Settings User",
        },
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with get_session_factory()() as session:
        session.add(
            SystemSetting(
                id=2,
                proxy_ip="127.0.0.9",
                proxy_port=8899,
                ai_provider="custom",
                ai_api_key="existing-ai-key",
                ai_api_base="https://example.com/v1",
                ai_chat_model="gpt-4o-mini",
                video_provider="openai",
                video_api_key="existing-video-key",
                video_api_base="https://video.example.com/v1",
                video_model="wan2.2-i2v-plus",
                video_image_to_video_model="wan2.2-i2v-plus",
                video_text_to_video_model="wan2.2-t2v",
            )
        )
        session.commit()

    proxy_response = client.get("/api/system-settings/proxy", headers=headers)
    assert proxy_response.status_code == 200
    proxy_body = proxy_response.json()
    assert proxy_body["proxy_ip"] == "127.0.0.9"
    assert proxy_body["proxy_port"] == 8899

    ai_response = client.get("/api/system-settings/ai", headers=headers)
    assert ai_response.status_code == 200
    ai_body = ai_response.json()
    assert ai_body["ai_provider"] == "custom"
    assert ai_body["ai_api_base"] == "https://example.com/v1"
    assert ai_body["ai_chat_model"] == "gpt-4o-mini"
    assert ai_body["ai_api_key"] == "existing-ai-key"
    assert ai_body["ai_config_source"] == "database"

    video_response = client.get("/api/system-settings/video", headers=headers)
    assert video_response.status_code == 200
    video_body = video_response.json()
    assert video_body["video_provider"] == "openai"
    assert video_body["video_api_base"] == "https://video.example.com/v1"
    assert video_body["video_model"] == "wan2.2-i2v-plus"
    assert video_body["video_image_to_video_model"] == "wan2.2-i2v-plus"
    assert video_body["video_text_to_video_model"] == "wan2.2-t2v"


def test_generate_project_remake_video_with_uploaded_image(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.tasks.remake_tasks.generate_video_with_provider",
        lambda **kwargs: VideoGenerationResult(
            task_id="task_seedance_123",
            status="succeeded",
            video_url="https://example.com/generated-video.mp4",
        ),
    )

    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "remake@example.com",
            "password": "verysecure123",
            "display_name": "Remake User",
        },
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    video_settings_response = client.put(
        "/api/system-settings/video",
        headers=headers,
        json={
            "video_provider": "doubao",
            "video_api_key": "seedance-test-key",
            "video_api_base": "https://ark.cn-beijing.volces.com/api/v3",
            "video_model": "doubao-seedance-1-5-pro-251215",
            "video_image_to_video_model": "doubao-seedance-1-5-pro-251215",
            "video_text_to_video_model": "doubao-seedance-1-5-pro-251215",
        },
    )
    assert video_settings_response.status_code == 200

    create_project_response = client.post(
        "/api/projects",
        headers=headers,
        json={
            "source_url": "https://www.tiktok.com/@creator/video/7499999999999999999",
            "title": "复刻测试",
            "objective": "先完成电商分析，再生成可复刻脚本",
        },
    )
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    remake_response = client.post(
        f"/api/projects/{project_id}/remake-video",
        headers=headers,
        data={
            "objective": "请基于对标视频生成适合我产品的 TikTok 带货短片",
        },
        files={
            "asset": ("product.png", b"fake-image-binary", "image/png"),
        },
    )

    assert remake_response.status_code == 200
    body = remake_response.json()
    assert body["status"] == "ready"
    assert body["summary"] == "视频复刻已生成完成。"

    video_generation = body["video_generation"]
    assert video_generation["status"] == "ready"
    assert video_generation["provider"] == "doubao"
    assert video_generation["model"] == "doubao-seedance-1-5-pro-251215"
    assert video_generation["objective"] == "请基于对标视频生成适合我产品的 TikTok 带货短片"
    assert video_generation["asset_type"] == "image"
    assert video_generation["asset_name"] == "product.png"
    assert video_generation["asset_url"].startswith("/uploads/reference-assets/")
    assert len(video_generation["reference_frames"]) == 1
    assert video_generation["reference_frames"][0].startswith("/uploads/reference-assets/")
    assert video_generation["script"]
    assert video_generation["storyboard"]
    assert video_generation["prompt"]
    assert video_generation["provider_task_id"] == "task_seedance_123"
    assert video_generation["result_video_url"] == "https://example.com/generated-video.mp4"
    assert video_generation["error_detail"] is None


def test_generate_project_remake_video_without_uploaded_asset_uses_text_mode(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.tasks.remake_tasks.generate_video_with_provider",
        lambda **kwargs: VideoGenerationResult(
            task_id="task_wan_text_123",
            status="succeeded",
            video_url="https://example.com/generated-wan-text-video.mp4",
        ),
    )

    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "remake-text@example.com",
            "password": "verysecure123",
            "display_name": "Remake Text User",
        },
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    video_settings_response = client.put(
        "/api/system-settings/video",
        headers=headers,
        json={
            "video_provider": "qwen",
            "video_api_key": "dashscope-video-key",
            "video_api_base": "https://dashscope.aliyuncs.com/api/v1",
            "video_model": "wan2.6-i2v",
            "video_image_to_video_model": "wan2.6-i2v",
            "video_text_to_video_model": "wan2.6-t2v",
        },
    )
    assert video_settings_response.status_code == 200

    create_project_response = client.post(
        "/api/projects",
        headers=headers,
        json={
            "source_url": "https://www.tiktok.com/@creator/video/7499999999999999999",
            "title": "万相直出测试",
            "objective": "直接输出一条可用的复刻视频",
            "workflow_type": "remake",
        },
    )
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    remake_response = client.post(
        f"/api/projects/{project_id}/remake-video",
        headers=headers,
        data={
            "objective": "不上传产品素材，直接走万相生成复刻视频",
        },
    )

    assert remake_response.status_code == 200
    body = remake_response.json()
    video_generation = body["video_generation"]
    assert video_generation["status"] == "ready"
    assert video_generation["provider"] == "qwen"
    assert video_generation["model"] == "wan2.6-t2v"
    assert video_generation["asset_type"] == "text"
    assert video_generation["asset_name"] == "未上传产品素材，按复刻脚本直接生成"
    assert video_generation["reference_frames"] == []
    assert video_generation["script"]
    assert video_generation["prompt"]
    assert video_generation["provider_task_id"] == "task_wan_text_123"
    assert (
        video_generation["result_video_url"]
        == "https://example.com/generated-wan-text-video.mp4"
    )


def test_generate_project_remake_video_returns_pending_step_detail(
    client: TestClient,
) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "remake-pending@example.com",
            "password": "verysecure123",
            "display_name": "Remake Pending User",
        },
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_project_response = client.post(
        "/api/projects",
        headers=headers,
        json={
            "source_url": "https://www.tiktok.com/@creator/video/7499999999999999999",
            "title": "复刻处理中测试",
            "objective": "生成复刻方案并准备出片",
            "workflow_type": "remake",
        },
    )
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    session_factory = get_session_factory()
    with session_factory() as session:
        project = session.get(VideoProject, project_id)
        assert project is not None
        project.status = "processing"
        project.summary = "正在生成复刻执行方案。"
        for step in project.task_steps:
            step.status = "completed"
        project.task_steps[4].status = "in_progress"
        session.add(project)
        session.commit()

    remake_response = client.post(
        f"/api/projects/{project_id}/remake-video",
        headers=headers,
        data={
            "objective": "继续执行视频复刻",
        },
    )

    assert remake_response.status_code == 409
    assert "复刻执行方案" in remake_response.json()["detail"]
    assert "正在生成复刻执行方案" in remake_response.json()["detail"]


def test_generate_project_remake_video_with_uploaded_audio_for_qwen(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, object] = {}

    def fake_generate_video_with_provider(**kwargs):
        captured_kwargs.update(kwargs)
        return VideoGenerationResult(
            task_id="task_wan_123",
            status="succeeded",
            video_url="https://example.com/generated-wan-video.mp4",
        )

    monkeypatch.setattr(
        "app.tasks.remake_tasks.generate_video_with_provider",
        fake_generate_video_with_provider,
    )

    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "remake-audio@example.com",
            "password": "verysecure123",
            "display_name": "Remake Audio User",
        },
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    video_settings_response = client.put(
        "/api/system-settings/video",
        headers=headers,
        json={
            "video_provider": "qwen",
            "video_api_key": "dashscope-video-key",
            "video_api_base": "https://dashscope.aliyuncs.com/api/v1",
            "video_model": "wan2.6-i2v",
            "video_image_to_video_model": "wan2.6-i2v",
            "video_text_to_video_model": "wan2.6-t2v",
        },
    )
    assert video_settings_response.status_code == 200

    create_project_response = client.post(
        "/api/projects",
        headers=headers,
        json={
            "source_url": "https://www.tiktok.com/@creator/video/7499999999999999999",
            "title": "复刻音频测试",
            "objective": "先完成电商分析，再生成可复刻脚本",
        },
    )
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    remake_response = client.post(
        f"/api/projects/{project_id}/remake-video",
        headers=headers,
        data={
            "objective": "请给这条复刻视频加上配音节奏",
        },
        files={
            "asset": ("product.png", b"fake-image-binary", "image/png"),
            "audio": ("voiceover.mp3", b"fake-audio-binary", "audio/mpeg"),
        },
    )

    assert remake_response.status_code == 200
    body = remake_response.json()
    video_generation = body["video_generation"]
    assert video_generation["audio_name"] == "voiceover.mp3"
    assert video_generation["audio_url"].startswith("http://testserver/uploads/reference-audio/")
    assert captured_kwargs["audio_url"] == video_generation["audio_url"]


def test_retry_project_ai_analysis(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.projects.analyze_video_script",
        lambda transcript, objective, **kwargs: f"AI重试成功：{objective}",
    )

    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "retry-ai@example.com",
            "password": "verysecure123",
            "display_name": "Retry AI User",
        },
    )
    token = register_response.json()["access_token"]

    create_project_response = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "source_url": "https://www.tiktok.com/@creator/video/7499999999999999999",
            "title": "AI 重试测试",
            "objective": "提取完整脚本并生成分析",
        },
    )
    project_id = create_project_response.json()["id"]

    retry_response = client.post(
        f"/api/projects/{project_id}/retry-ai-analysis",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert retry_response.status_code == 200
    assert (
        retry_response.json()["ecommerce_analysis"]["content"]
        == "AI重试成功：提取完整脚本并生成分析"
    )


def test_forgot_password_and_reset_flow(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "reset@example.com",
            "password": "verysecure123",
            "display_name": "Reset User",
        },
    )
    assert register_response.status_code == 201

    forgot_response = client.post(
        "/api/auth/forgot-password",
        json={
            "email": "reset@example.com",
        },
    )
    assert forgot_response.status_code == 200
    forgot_body = forgot_response.json()
    assert forgot_body["reset_token"]

    reset_response = client.post(
        "/api/auth/reset-password",
        json={
            "token": forgot_body["reset_token"],
            "new_password": "newpassword456",
        },
    )
    assert reset_response.status_code == 204

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "reset@example.com",
            "password": "newpassword456",
        },
    )
    assert login_response.status_code == 200
