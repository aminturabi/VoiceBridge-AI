"""Caching layer for VoiceBridge AI to reduce translation and TTS latency.

Provides thread-safe in-memory caching backed by disk persistence for:
1. Translation results (text -> text)
2. Audio synthesis results (text + voice -> audio file)
"""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
from pathlib import Path
from typing import Any

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)


class TranslationCache:
    """Thread-safe translation cache."""

    def __init__(self, config: Config):
        self._enabled = bool(config.get("cache.enabled", True))
        self._dir = config.path("cache.translation_dir", "cache/translation")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "translations.json"
        self._lock = threading.Lock()
        self._memory_cache: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self._enabled or not self._file.exists():
            return
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._memory_cache = data
        except Exception as error:
            logger.warning("Failed to load translation cache: %s", error)

    def _save(self) -> None:
        if not self._enabled:
            return
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(self._memory_cache, f, ensure_ascii=False, indent=2)
        except Exception as error:
            logger.warning("Failed to save translation cache: %s", error)

    def get(self, text: str, source: str, target: str) -> str | None:
        if not self._enabled or not text:
            return None
        key = f"{source}:{target}:{text.strip()}"
        with self._lock:
            val = self._memory_cache.get(key)
            if val:
                logger.debug("Translation cache hit for key %r", key)
            return val

    def set(self, text: str, source: str, target: str, translation: str) -> None:
        if not self._enabled or not text or not translation:
            return
        key = f"{source}:{target}:{text.strip()}"
        with self._lock:
            self._memory_cache[key] = translation
            self._save()


class AudioCache:
    """Thread-safe TTS audio synthesis cache."""

    def __init__(self, config: Config):
        self._enabled = bool(config.get("cache.enabled", True))
        self._dir = config.path("cache.audio_dir", "cache/audio")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _hash_key(self, text: str, voice: str, fmt: str) -> str:
        raw = f"{voice}:{fmt}:{text.strip()}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def get(self, text: str, voice: str, fmt: str, destination_path: Path) -> bool:
        """If a cached audio file exists, copy it to destination_path and return True."""
        if not self._enabled:
            return False

        key = self._hash_key(text, voice, fmt)
        cached_file = self._dir / f"{key}.{fmt}"

        with self._lock:
            if cached_file.exists() and cached_file.stat().st_size > 0:
                try:
                    shutil.copyfile(cached_file, destination_path)
                    logger.debug("Audio cache hit for key %r -> %s", key, destination_path.name)
                    return True
                except Exception as error:
                    logger.warning("Failed to copy cached audio file: %s", error)

        return False

    def store(self, text: str, voice: str, fmt: str, source_path: Path) -> None:
        """Store synthesized audio file into the cache."""
        if not self._enabled or not source_path.exists() or source_path.stat().st_size == 0:
            return

        key = self._hash_key(text, voice, fmt)
        cached_file = self._dir / f"{key}.{fmt}"

        with self._lock:
            try:
                shutil.copyfile(source_path, cached_file)
                logger.debug("Stored audio cache for key %r", key)
            except Exception as error:
                logger.warning("Failed to store audio in cache: %s", error)


class CacheManager:
    """Unified access to translation and audio caches."""

    def __init__(self, config: Config):
        self.config = config
        self.translation = TranslationCache(config)
        self.audio = AudioCache(config)
