import json
from pathlib import Path

from app.core.config import get_settings
from app.services import ai_analysis
from app.services.ai_analysis import analyze_video_script, normalize_ai_analysis_error
from app.services import media_tools
from app.services.media_tools import (
    MediaAnalysisData,
    RawTranscriptSegment,
    VideoMediaMetadata,
    VisualFeatureAnalysis,
)
from app.services.system_settings import (
    ResolvedAiProviderSettings,
    ResolvedVideoProviderSettings,
    normalize_openai_compatible_api_base,
    normalize_video_generation_api_base,
)
from app.services.video_generation import (
    DoubaoVideoGenerationStrategy,
    OpenAIVideoGenerationStrategy,
    QwenVideoGenerationStrategy,
    build_doubao_generation_payload,
    build_openai_video_generation_payload,
    build_qwen_video_generation_payload,
    build_qwen_video_submission_url,
    build_qwen_video_task_url,
    build_video_generation_blueprint,
    build_video_generation_strategy,
    normalize_doubao_video_error_detail,
    normalize_openai_video_error_detail,
    normalize_qwen_video_error_detail,
)
from app.services.video_pipeline import build_project_analysis


def test_build_project_analysis_uses_real_media_analysis(
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIDEO_ANALYSIS_PROVIDER", "real")
    get_settings.cache_clear()

    media_analysis = MediaAnalysisData(
        metadata=VideoMediaMetadata(
            duration_ms=12800,
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
                end_ms=4200,
                content="第一句真实转写内容。",
            ),
            RawTranscriptSegment(
                segment_type="dialogue",
                speaker="主讲人",
                start_ms=4200,
                end_ms=9600,
                content="第二句真实转写内容。",
            ),
        ],
        transcript_provider="openai",
    )

    monkeypatch.setattr(
        "app.services.video_pipeline.collect_media_analysis",
        lambda _: media_analysis,
    )

    result = build_project_analysis(
        source_url="https://www.youtube.com/shorts/abc123xyz",
        title="真实解析测试",
        objective="提取真实脚本并生成复刻方案",
        source_platform="youtube",
        source_name="abc123xyz",
    )

    assert result.summary.startswith("已基于真实视频解析")
    assert result.transcript_segments[0].content == "第一句真实转写内容。"
    assert result.dialogue_text.startswith("第一句真实转写内容。")
    assert result.remake_scenes

    get_settings.cache_clear()


def test_build_project_analysis_returns_structured_remake_json(
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIDEO_ANALYSIS_PROVIDER", "real")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    media_analysis = MediaAnalysisData(
        metadata=VideoMediaMetadata(
            duration_ms=12800,
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
                end_ms=4200,
                content="3 秒看懂为什么这条视频能留住人。",
            ),
            RawTranscriptSegment(
                segment_type="dialogue",
                speaker="主讲人",
                start_ms=4200,
                end_ms=9600,
                content="中段用产品细节和对比画面证明结果。",
            ),
        ],
        transcript_provider="openai",
    )

    monkeypatch.setattr(
        "app.services.video_pipeline.collect_media_analysis",
        lambda _: media_analysis,
    )

    result = build_project_analysis(
        source_url="https://www.youtube.com/shorts/abc123xyz",
        title="复刻 JSON 测试",
        objective="输出复刻执行 JSON 方案",
        source_platform="youtube",
        source_name="abc123xyz",
        workflow_type="remake",
    )

    payload = json.loads(result.ai_analysis)
    assert payload["visual"]["aspect_ratio"] == "9:16"
    assert len(payload["timeline"]) == 4
    assert payload["viral_logic"]["hook_type"]
    assert len(payload["variations"]) == 3

    get_settings.cache_clear()


def test_build_project_analysis_preserves_visual_feature_analysis(
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIDEO_ANALYSIS_PROVIDER", "real")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    media_analysis = MediaAnalysisData(
        metadata=VideoMediaMetadata(
            duration_ms=9600,
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
                content="前三秒先给结果。",
            ),
            RawTranscriptSegment(
                segment_type="dialogue",
                speaker="主讲人",
                start_ms=3200,
                end_ms=9600,
                content="中段用细节和对比证明卖点。",
            ),
        ],
        transcript_provider="openai",
        reference_frame_urls=["/uploads/analysis-frames/mock-frame-1.jpg"],
        visual_feature_analysis=VisualFeatureAnalysis(
            orientation="竖屏",
            resolution="1080x1920",
            frame_rate="30.00fps",
            keyframe_count=1,
            shot_density="每 10 秒约 1.0 次明显场景切换",
            scene_pace="中节奏",
            lighting="明亮均衡布光",
            contrast="中对比",
            saturation="中饱和",
            color_temperature="偏暖",
            framing_focus="主体更集中在画面中心，偏中近景或产品特写",
            camera_motion="切镜与稳镜交替，整体更偏常规短视频节奏",
            dominant_palette=["#E0A060"],
            summary="整体镜头更偏电商展示式构图。",
        ),
    )

    monkeypatch.setattr(
        "app.services.video_pipeline.collect_media_analysis",
        lambda _: media_analysis,
    )

    result = build_project_analysis(
        source_url="https://www.youtube.com/shorts/abc123xyz",
        title="视觉分析保留测试",
        objective="输出带视觉特征的复刻方案",
        source_platform="youtube",
        source_name="abc123xyz",
        workflow_type="remake",
    )

    assert result.reference_frame_urls == ["/uploads/analysis-frames/mock-frame-1.jpg"]
    assert result.visual_feature_analysis is not None
    assert result.visual_feature_analysis.scene_pace == "中节奏"

    get_settings.cache_clear()


def test_build_video_generation_blueprint_uses_visual_feature_context() -> None:
    class DummyScene:
        def __init__(
            self,
            scene_index: int,
            visual_direction: str,
            shot_prompt: str,
            voiceover: str,
            on_screen_text: str,
            editing_notes: str,
        ) -> None:
            self.scene_index = scene_index
            self.visual_direction = visual_direction
            self.shot_prompt = shot_prompt
            self.voiceover = voiceover
            self.on_screen_text = on_screen_text
            self.editing_notes = editing_notes

    class DummyProject:
        def __init__(self) -> None:
            self.title = "复刻脚本测试"
            self.summary = "需要按原片节奏生成成片。"
            self.full_text = ""
            self.analysis_reference_frames = json.dumps(
                ["/uploads/analysis-frames/mock-frame-1.jpg"],
                ensure_ascii=False,
            )
            self.analysis_visual_features = json.dumps(
                {
                    "scene_pace": "快切",
                    "lighting": "明亮均衡布光",
                    "camera_motion": "频繁切镜，适合保留轻推镜或手持接近感",
                    "framing_focus": "主体更集中在画面中心，偏中近景或产品特写",
                    "dominant_palette": ["#E0A060", "#806040"],
                    "summary": "整体镜头节奏快，适合电商型展示和强 CTA。",
                },
                ensure_ascii=False,
            )
            self.remake_scenes = [
                DummyScene(
                    1,
                    "近景口播快速点题",
                    "镜头快速推进到产品",
                    "先说结果",
                    "3 秒看懂",
                    "前 1 秒出大字幕",
                )
            ]

    blueprint = build_video_generation_blueprint(
        DummyProject(),
        objective="按原片风格生成产品视频",
        reference_asset_type="image",
        reference_asset_name="product.png",
        reference_frame_count=1,
    )

    assert "视觉基调：" in blueprint.script
    assert "#E0A060" in blueprint.prompt
    assert "Source visual summary" in blueprint.prompt


class _FakeWhisperSegment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


class _FakeWhisperModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def transcribe(self, audio_path: str, **kwargs):
        self.calls.append((audio_path, kwargs))
        return iter(
            [
                _FakeWhisperSegment(0.0, 1.2, "第一句本地转写。"),
                _FakeWhisperSegment(1.2, 2.8, "第二句本地转写。"),
            ]
        ), object()


def test_transcribe_audio_with_faster_whisper(
    monkeypatch,
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    fake_model = _FakeWhisperModel()
    monkeypatch.setenv("VIDEO_TRANSCRIPTION_PROVIDER", "faster_whisper")
    monkeypatch.setenv("VIDEO_TRANSCRIPTION_LANGUAGE", "zh")
    monkeypatch.setenv("FASTER_WHISPER_BEAM_SIZE", "3")
    monkeypatch.setenv("FASTER_WHISPER_VAD_FILTER", "false")
    get_settings.cache_clear()
    media_tools.get_faster_whisper_model.cache_clear()
    monkeypatch.setattr(media_tools, "faster_whisper", object())
    monkeypatch.setattr(media_tools, "get_faster_whisper_model", lambda: fake_model)

    segments, provider = media_tools.transcribe_audio(audio_path, duration_ms=2800)

    assert provider == "faster_whisper"
    assert len(segments) == 2
    assert segments[0].content == "第一句本地转写。"
    assert fake_model.calls[0][1]["beam_size"] == 3
    assert fake_model.calls[0][1]["language"] == "zh"
    assert fake_model.calls[0][1]["vad_filter"] is False

    get_settings.cache_clear()


def test_transcribe_audio_with_openai_includes_request_timeout(
    monkeypatch,
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    class FakeOpenAI:
        api_key = None
        api_base = None

        class Audio:
            captured_kwargs: dict[str, object] | None = None

            @staticmethod
            def transcribe(**kwargs):
                FakeOpenAI.Audio.captured_kwargs = kwargs
                return {"text": "转写完成"}

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_API_BASE", "https://example.com/v1/")
    monkeypatch.setenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "17")
    get_settings.cache_clear()
    monkeypatch.setattr(media_tools, "openai", FakeOpenAI)

    segments = media_tools.transcribe_audio_with_openai(audio_path, duration_ms=3200)

    assert len(segments) == 1
    assert FakeOpenAI.Audio.captured_kwargs is not None
    assert FakeOpenAI.Audio.captured_kwargs["request_timeout"] == 17
    assert FakeOpenAI.api_base == "https://example.com/v1"

    get_settings.cache_clear()


def test_build_remote_download_command_uses_system_proxy(monkeypatch) -> None:
    monkeypatch.setenv("YT_DLP_BINARY", "yt-dlp-custom")
    get_settings.cache_clear()
    monkeypatch.setattr(media_tools, "get_system_proxy_url", lambda: "http://127.0.0.1:7890")

    command = media_tools.build_remote_download_command(
        source_url="https://www.tiktok.com/@creator/video/7499999999999999999",
        output_template="/tmp/source.%(ext)s",
    )

    assert command[0] == "yt-dlp-custom"
    assert "--proxy" in command
    assert command[command.index("--proxy") + 1] == "http://127.0.0.1:7890"

    get_settings.cache_clear()


def test_normalize_media_command_error_for_tiktok_ip_block() -> None:
    detail = "ERROR: [TikTok] 7490000000000000000: Your IP address is blocked from accessing this post"

    normalized = media_tools.normalize_media_command_error(detail)

    assert "TikTok 拒绝了当前出口 IP" in normalized
    assert "系统设置" in normalized


def test_normalize_ai_analysis_error_for_overloaded_server() -> None:
    normalized = normalize_ai_analysis_error("The server is overloaded or not ready yet.")

    assert normalized == "AI 分析服务当前繁忙，请稍后重试或更换模型服务。"


def test_normalize_doubao_video_error_for_invalid_api_key() -> None:
    normalized = normalize_doubao_video_error_detail(
        "Unauthorized",
        status_code=401,
        payload={"status": 401, "error": "Unauthorized"},
    )

    assert "方舟视频生成接口" in normalized


def test_normalize_openai_video_error_for_missing_endpoint() -> None:
    normalized = normalize_openai_video_error_detail(
        "Not Found",
        status_code=404,
        payload={"error": {"message": "Not Found"}},
    )

    assert "/v1/videos" in normalized


def test_build_video_generation_strategy_returns_doubao_strategy() -> None:
    strategy = build_video_generation_strategy(
        ResolvedVideoProviderSettings(
            provider="doubao",
            provider_label="豆包视频 / 火山方舟",
            api_key="test-key",
            api_key_source="database",
            api_base="https://ark.cn-beijing.volces.com/api/v3",
            model="doubao-seedance-1-5-pro-251215",
            image_to_video_model="doubao-seedance-1-5-pro-251215",
            text_to_video_model="doubao-seedance-1-5-pro-251215",
        )
    )

    assert isinstance(strategy, DoubaoVideoGenerationStrategy)


def test_build_video_generation_strategy_returns_openai_strategy() -> None:
    strategy = build_video_generation_strategy(
        ResolvedVideoProviderSettings(
            provider="openai",
            provider_label="OpenAI 兼容视频接口（/v1/videos）",
            api_key="test-key",
            api_key_source="database",
            api_base="https://example.com/v1",
            model="wan2.2-i2v-plus",
            image_to_video_model="wan2.2-i2v-plus",
            text_to_video_model="wan2.2-t2v",
        )
    )

    assert isinstance(strategy, OpenAIVideoGenerationStrategy)


def test_build_video_generation_strategy_returns_qwen_strategy() -> None:
    strategy = build_video_generation_strategy(
        ResolvedVideoProviderSettings(
            provider="qwen",
            provider_label="通义万相 / DashScope",
            api_key="dashscope-key",
            api_key_source="database",
            api_base="https://dashscope.aliyuncs.com/api/v1",
            model="wan2.6-i2v",
            image_to_video_model="wan2.6-i2v",
            text_to_video_model="wan2.6-t2v",
        )
    )

    assert isinstance(strategy, QwenVideoGenerationStrategy)


def test_build_doubao_generation_payload_matches_ark_content_shape() -> None:
    payload = build_doubao_generation_payload(
        model="doubao-seedance-1-5-pro-251215",
        prompt="生成一条 5 秒带货短视频",
        reference_images=["https://example.com/product.png"],
    )

    assert payload["model"] == "doubao-seedance-1-5-pro-251215"
    assert payload["content"] == [
        {"type": "text", "text": "生成一条 5 秒带货短视频"},
        {
            "type": "image_url",
            "image_url": {"url": "https://example.com/product.png"},
        },
    ]


def test_build_openai_video_generation_payload_matches_videos_shape() -> None:
    payload = build_openai_video_generation_payload(
        model="wan2.2-i2v-plus",
        prompt="生成一条 5 秒带货短视频",
        reference_images=["data:image/png;base64,ZmFrZQ==", "data:image/png;base64,bW9yZQ=="],
    )

    assert payload == {
        "model": "wan2.2-i2v-plus",
        "prompt": "生成一条 5 秒带货短视频",
        "image": "data:image/png;base64,ZmFrZQ==",
    }


def test_build_qwen_video_generation_payload_matches_dashscope_shape() -> None:
    payload = build_qwen_video_generation_payload(
        model="wan2.6-i2v",
        prompt="生成一条 10 秒带货短视频",
        reference_images=["data:image/png;base64,ZmFrZQ==", "data:image/png;base64,bW9yZQ=="],
    )

    assert payload == {
        "model": "wan2.6-i2v",
        "input": {
            "prompt": "生成一条 10 秒带货短视频",
            "img_url": "data:image/png;base64,ZmFrZQ==",
        },
        "parameters": {
            "prompt_extend": True,
            "duration": 10,
            "resolution": "720P",
            "shot_type": "multi",
        },
    }


def test_build_qwen_video_generation_payload_includes_audio_url() -> None:
    payload = build_qwen_video_generation_payload(
        model="wan2.6-i2v",
        prompt="生成一条 10 秒带货短视频",
        reference_images=["data:image/png;base64,ZmFrZQ=="],
        audio_url="https://example.com/voiceover.mp3",
    )

    assert payload["input"]["audio_url"] == "https://example.com/voiceover.mp3"
    assert payload["parameters"]["audio"] is True


def test_normalize_openai_compatible_api_base_strips_endpoint_suffix() -> None:
    normalized = normalize_openai_compatible_api_base(
        "https://ark.cn-beijing.volces.com/api/v3/chat/completions/",
    )

    assert normalized == "https://ark.cn-beijing.volces.com/api/v3"


def test_normalize_video_generation_api_base_strips_openai_videos_suffix() -> None:
    normalized = normalize_video_generation_api_base(
        "https://example.com/v1/videos/",
    )

    assert normalized == "https://example.com/v1"


def test_normalize_video_generation_api_base_strips_dashscope_video_synthesis_suffix() -> None:
    normalized = normalize_video_generation_api_base(
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis/",
    )

    assert normalized == "https://dashscope.aliyuncs.com/api/v1"


def test_build_qwen_video_urls_accept_api_v1_base() -> None:
    submission_url = build_qwen_video_submission_url("https://dashscope.aliyuncs.com/api/v1")
    task_url = build_qwen_video_task_url("https://dashscope.aliyuncs.com/api/v1", "task_123")

    assert submission_url == "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
    assert task_url == "https://dashscope.aliyuncs.com/api/v1/tasks/task_123"


def test_normalize_qwen_video_error_for_auth_failure() -> None:
    normalized = normalize_qwen_video_error_detail(
        "Forbidden",
        status_code=403,
        payload={"code": "AccessDenied"},
    )

    assert "DashScope 视频生成鉴权失败" in normalized


def test_analyze_video_script_uses_selected_provider_settings(monkeypatch) -> None:
    class FakeChoice:
        def __init__(self, content: str) -> None:
            self.message = type("Message", (), {"content": content})()

    class FakeResponse:
        def __init__(self, content: str) -> None:
            self.choices = [FakeChoice(content)]

    class FakeOpenAI:
        api_key = None
        api_base = None

        class ChatCompletion:
            captured_kwargs: dict[str, object] | None = None

            @staticmethod
            def create(**kwargs):
                FakeOpenAI.ChatCompletion.captured_kwargs = kwargs
                return FakeResponse("千问分析结果")

    monkeypatch.setenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "19")
    get_settings.cache_clear()
    monkeypatch.setattr(ai_analysis, "openai", FakeOpenAI)
    monkeypatch.setattr(
        ai_analysis,
        "resolve_ai_provider_settings",
        lambda: ResolvedAiProviderSettings(
            provider="qwen",
            provider_label="千问 / DashScope",
            api_key="dashscope-key",
            api_key_source="database",
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1/completions",
            chat_model="qwen-plus",
            config_source="database",
        ),
    )

    result = analyze_video_script("测试转录文本", "生成分析")

    assert result == "千问分析结果"
    assert FakeOpenAI.api_key == "dashscope-key"
    assert FakeOpenAI.api_base == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert FakeOpenAI.ChatCompletion.captured_kwargs is not None
    assert FakeOpenAI.ChatCompletion.captured_kwargs["model"] == "qwen-plus"
    assert FakeOpenAI.ChatCompletion.captured_kwargs["request_timeout"] == 19

    get_settings.cache_clear()


def test_analyze_video_script_includes_request_timeout(monkeypatch) -> None:
    class FakeChoice:
        def __init__(self, content: str) -> None:
            self.message = type("Message", (), {"content": content})()

    class FakeResponse:
        def __init__(self, content: str) -> None:
            self.choices = [FakeChoice(content)]

    class FakeOpenAI:
        api_key = None
        api_base = None

        class ChatCompletion:
            captured_kwargs: dict[str, object] | None = None

            @staticmethod
            def create(**kwargs):
                FakeOpenAI.ChatCompletion.captured_kwargs = kwargs
                return FakeResponse("结构化分析结果")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "27")
    get_settings.cache_clear()
    monkeypatch.setattr(ai_analysis, "openai", FakeOpenAI)

    result = analyze_video_script("测试转录文本", "生成分析")

    assert result == "结构化分析结果"
    assert FakeOpenAI.ChatCompletion.captured_kwargs is not None
    assert FakeOpenAI.ChatCompletion.captured_kwargs["request_timeout"] == 27

    get_settings.cache_clear()


def test_analyze_video_script_returns_valid_json_for_remake_without_api_key() -> None:
    payload = json.loads(
        analyze_video_script(
            "[00:00 - 00:03]: 先给你看结果\n[00:03 - 00:08]: 中段展示细节",
            "输出复刻 JSON 方案",
            workflow_type="remake",
        )
    )

    assert sorted(payload.keys()) == [
        "content_strategy",
        "execution_plan",
        "timeline",
        "variations",
        "viral_logic",
        "visual",
    ]
    assert len(payload["variations"]) == 3


def test_transcribe_audio_with_openai_normalizes_api_base(monkeypatch, tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    class FakeOpenAI:
        api_key = None
        api_base = None

        class Audio:
            @staticmethod
            def transcribe(**kwargs):
                return {"text": "转写完成"}

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_API_BASE", "https://example.com/v1/audio/transcriptions")
    get_settings.cache_clear()
    monkeypatch.setattr(media_tools, "openai", FakeOpenAI)

    media_tools.transcribe_audio_with_openai(audio_path, duration_ms=3200)

    assert FakeOpenAI.api_base == "https://example.com/v1"

    get_settings.cache_clear()
