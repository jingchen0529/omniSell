from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

UPLOAD_URI_SCHEME = "upload://"
SUPPORTED_UPLOAD_EXTENSIONS = {
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".webm",
}
SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpeg",
    ".jpg",
    ".png",
    ".webp",
}
SUPPORTED_AUDIO_EXTENSIONS = {
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".wav",
    ".webm",
}
SUPPORTED_REFERENCE_ASSET_EXTENSIONS = SUPPORTED_UPLOAD_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS
PLATFORM_LABELS = {
    "bilibili": "Bilibili",
    "douyin": "Douyin",
    "generic": "Web Video",
    "instagram": "Instagram Reels",
    "local_upload": "Local Upload",
    "tiktok": "TikTok",
    "xiaohongshu": "Xiaohongshu",
    "youtube": "YouTube Shorts",
}


@dataclass(frozen=True)
class VideoSourceDescriptor:
    source_type: str
    source_platform: str
    source_url: str
    source_name: str


@dataclass(frozen=True)
class StoredReferenceAsset:
    asset_type: str
    source_url: str
    source_name: str


@dataclass(frozen=True)
class StoredAudioAsset:
    source_url: str
    source_name: str


def build_url_source_descriptor(source_url: str) -> VideoSourceDescriptor:
    return VideoSourceDescriptor(
        source_type="url",
        source_platform=detect_platform_from_url(source_url),
        source_url=source_url,
        source_name=extract_source_name(source_url),
    )


def store_upload_file(upload_file: UploadFile) -> VideoSourceDescriptor:
    filename = sanitize_filename(upload_file.filename or "uploaded-video.mp4")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported video format. Use mp4, mov, mkv, webm, avi, m4v, mpeg or mpg.",
        )

    uploads_root = get_settings().uploads_root
    relative_dir = Path(datetime.now(timezone.utc).strftime("%Y/%m/%d"))
    target_dir = uploads_root / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid4().hex}-{filename}"
    relative_path = relative_dir / stored_filename
    target_path = uploads_root / relative_path

    with target_path.open("wb") as destination:
        shutil.copyfileobj(upload_file.file, destination)

    if target_path.stat().st_size <= 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded video is empty.",
        )

    return VideoSourceDescriptor(
        source_type="upload",
        source_platform="local_upload",
        source_url=build_upload_source_url(relative_path),
        source_name=filename,
    )


def store_reference_asset_file(upload_file: UploadFile) -> StoredReferenceAsset:
    filename = sanitize_filename(upload_file.filename or "reference-asset")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_REFERENCE_ASSET_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported asset format. Use jpg, jpeg, png, webp, mp4, mov, mkv, webm, avi, m4v, mpeg or mpg.",
        )

    uploads_root = get_settings().uploads_root
    relative_dir = Path(datetime.now(timezone.utc).strftime("reference-assets/%Y/%m/%d"))
    target_dir = uploads_root / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid4().hex}-{filename}"
    relative_path = relative_dir / stored_filename
    target_path = uploads_root / relative_path

    with target_path.open("wb") as destination:
        shutil.copyfileobj(upload_file.file, destination)

    if target_path.stat().st_size <= 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded asset is empty.",
        )

    return StoredReferenceAsset(
        asset_type="image" if suffix in SUPPORTED_IMAGE_EXTENSIONS else "video",
        source_url=build_upload_source_url(relative_path),
        source_name=filename,
    )


def store_reference_audio_file(upload_file: UploadFile) -> StoredAudioAsset:
    filename = sanitize_filename(upload_file.filename or "reference-audio.mp3", default_suffix=".mp3")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio format. Use mp3, wav, m4a, aac, flac, ogg or webm.",
        )

    uploads_root = get_settings().uploads_root
    relative_dir = Path(datetime.now(timezone.utc).strftime("reference-audio/%Y/%m/%d"))
    target_dir = uploads_root / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid4().hex}-{filename}"
    relative_path = relative_dir / stored_filename
    target_path = uploads_root / relative_path

    with target_path.open("wb") as destination:
        shutil.copyfileobj(upload_file.file, destination)

    if target_path.stat().st_size <= 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio is empty.",
        )

    return StoredAudioAsset(
        source_url=build_upload_source_url(relative_path),
        source_name=filename,
    )


def derive_source_type(source_url: str) -> str:
    return "upload" if is_upload_source(source_url) else "url"


def extract_source_name(source_url: str) -> str:
    if is_upload_source(source_url):
        relative_path = decode_upload_relative_path(source_url)
        return Path(relative_path).name.split("-", 1)[-1]

    parsed = urlparse(source_url)
    path_bits = [bit for bit in parsed.path.split("/") if bit]
    if "youtube" in parsed.netloc.lower() and parsed.query:
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        if video_id:
            return video_id
    if path_bits:
        return path_bits[-1]
    return parsed.netloc or "video-source"


def extract_source_slug(source_url: str, source_name: str | None = None) -> str:
    if is_upload_source(source_url):
        return Path(source_name or extract_source_name(source_url)).stem or "uploaded-video"

    parsed = urlparse(source_url)
    if "youtube" in parsed.netloc.lower() and parsed.query:
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        if video_id:
            return video_id

    path_bits = [bit for bit in parsed.path.split("/") if bit]
    return path_bits[-1] if path_bits else parsed.netloc or "web-video"


def platform_label(platform: str) -> str:
    return PLATFORM_LABELS.get(platform, platform.replace("_", " ").title())


def detect_platform_from_url(source_url: str) -> str:
    host = urlparse(source_url).netloc.lower()
    if not host:
        return "generic"
    if any(domain in host for domain in ("tiktok.com", "vm.tiktok.com")):
        return "tiktok"
    if any(domain in host for domain in ("douyin.com", "iesdouyin.com")):
        return "douyin"
    if any(domain in host for domain in ("youtube.com", "youtu.be")):
        return "youtube"
    if "instagram.com" in host:
        return "instagram"
    if any(domain in host for domain in ("xiaohongshu.com", "xhslink.com")):
        return "xiaohongshu"
    if any(domain in host for domain in ("bilibili.com", "b23.tv")):
        return "bilibili"
    return "generic"


def is_upload_source(source_url: str) -> bool:
    return source_url.startswith(UPLOAD_URI_SCHEME)


def is_image_filename(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def is_video_filename(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_UPLOAD_EXTENSIONS


def build_upload_source_url(relative_path: Path) -> str:
    return f"{UPLOAD_URI_SCHEME}{quote(relative_path.as_posix())}"


def build_public_upload_url(relative_path: Path) -> str:
    return f"/uploads/{quote(relative_path.as_posix())}"


def build_absolute_public_upload_url(relative_path: Path, base_url: str) -> str:
    if not base_url.strip():
        return build_public_upload_url(relative_path)
    return urljoin(base_url.rstrip("/") + "/", build_public_upload_url(relative_path).lstrip("/"))


def decode_upload_relative_path(source_url: str) -> str:
    if not is_upload_source(source_url):
        raise ValueError("Not an upload source URL.")
    return unquote(source_url[len(UPLOAD_URI_SCHEME) :])


def resolve_upload_path(source_url: str) -> Path:
    relative_path = Path(decode_upload_relative_path(source_url))
    local_path = get_settings().uploads_root / relative_path
    if not local_path.is_file():
        raise FileNotFoundError(f"Uploaded asset not found for {source_url}.")
    return local_path


def resolve_public_upload_url(source_url: str) -> str:
    relative_path = Path(decode_upload_relative_path(source_url))
    return build_public_upload_url(relative_path)


def resolve_absolute_upload_url(source_url: str, base_url: str) -> str:
    relative_path = Path(decode_upload_relative_path(source_url))
    return build_absolute_public_upload_url(relative_path, base_url)


def store_generated_public_file(
    file_path: Path,
    *,
    category: str,
    source_name: str | None = None,
) -> str:
    uploads_root = get_settings().uploads_root
    relative_dir = Path(category) / Path(datetime.now(timezone.utc).strftime("%Y/%m/%d"))
    target_dir = uploads_root / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = sanitize_filename(source_name or file_path.name)
    stored_filename = f"{uuid4().hex}-{filename}"
    relative_path = relative_dir / stored_filename
    target_path = uploads_root / relative_path
    shutil.copy2(file_path, target_path)
    return build_public_upload_url(relative_path)


def sanitize_filename(filename: str, default_suffix: str = ".mp4") -> str:
    base_name = Path(filename).name.strip()
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", base_name).strip("._-")
    stem = Path(normalized).stem[:80] or "uploaded-video"
    suffix = Path(normalized).suffix.lower()[:10]
    return f"{stem}{suffix or default_suffix}"
