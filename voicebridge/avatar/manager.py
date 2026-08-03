"""Avatar management module for VoiceBridge AI.

Manages avatars independently from lip synchronization algorithms, handling static avatar
images, source face videos, avatar registration, and asset lookup.
"""

from __future__ import annotations

from pathlib import Path

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)


class AvatarManager:
    """Manages avatar assets (images and videos) for talking heads."""

    def __init__(self, config: Config):
        self._config = config
        self._avatar_dir = config.path("avatar.dir", "voicebridge/avatar")
        self._images_dir = config.path("avatar.images_dir", "voicebridge/avatar/images")
        self._videos_dir = config.path("avatar.videos_dir", "voicebridge/avatar/videos")
        self._default_avatar = config.get("avatar.default_avatar", "speaker")
        self._source_face_setting = config.get("avatar.source_face", "assets/faces/speaker.mp4")

        self._images_dir.mkdir(parents=True, exist_ok=True)
        self._videos_dir.mkdir(parents=True, exist_ok=True)

    @property
    def default_avatar_name(self) -> str:
        return self._default_avatar

    def get_source_face(self, avatar_name: str | None = None) -> Path:
        """Resolve the source face image or video file path for a given avatar."""
        name = avatar_name or self._default_avatar

        # 1. Check inside avatar videos directory
        for ext in (".mp4", ".avi", ".mov", ".mkv"):
            video_path = self._videos_dir / f"{name}{ext}"
            if video_path.exists():
                return video_path

        # 2. Check inside avatar images directory
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            image_path = self._images_dir / f"{name}{ext}"
            if image_path.exists():
                return image_path

        # 3. Fall back to config source_face path or project root assets
        fallback = self._config.path("avatar.source_face", self._source_face_setting)
        if fallback.exists():
            return fallback

        # 4. Return default fallback path
        return self._config.project_root / self._source_face_setting

    def list_avatars(self) -> list[str]:
        """Return a list of available registered avatar names."""
        avatars = set()

        for path in self._videos_dir.glob("*"):
            if path.is_file() and path.suffix in (".mp4", ".avi", ".mov", ".mkv"):
                avatars.add(path.stem)

        for path in self._images_dir.glob("*"):
            if path.is_file() and path.suffix in (".jpg", ".jpeg", ".png", ".webp"):
                avatars.add(path.stem)

        if not avatars:
            avatars.add(self._default_avatar)

        return sorted(list(avatars))
