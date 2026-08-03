"""Unit tests for VoiceBridge AI modular architecture & pluggable components."""

from __future__ import annotations

from pathlib import Path
import pytest

from voicebridge.avatar.manager import AvatarManager
from voicebridge.cache.manager import AudioCache, CacheManager, TranslationCache
from voicebridge.config import Config, load_config
from voicebridge.lipsync.base import LipSyncResult
from voicebridge.lipsync.manager import LipSyncManager
from voicebridge.lipsync.wav2lip_backend import Wav2LipBackend
from voicebridge.stt.base import Transcription
from voicebridge.stt.manager import SttManager
from voicebridge.translation.manager import TranslationManager
from voicebridge.translation.nllb_backend import NllbBackend
from voicebridge.tts.manager import TtsManager


@pytest.fixture
def sample_config(tmp_path: Path) -> Config:
    cache_dir = tmp_path / "cache"
    models_dir = tmp_path / "models"
    avatar_dir = tmp_path / "avatar"

    return Config({
        "app": {"output_dir": str(tmp_path / "output")},
        "models": {
            "root_dir": str(models_dir),
            "whisper_dir": str(models_dir / "whisper"),
            "nllb_dir": str(models_dir / "nllb"),
            "wav2lip_dir": str(models_dir / "wav2lip"),
        },
        "cache": {
            "enabled": True,
            "dir": str(cache_dir),
            "translation_dir": str(cache_dir / "translation"),
            "audio_dir": str(cache_dir / "audio"),
        },
        "avatar": {
            "dir": str(avatar_dir),
            "images_dir": str(avatar_dir / "images"),
            "videos_dir": str(avatar_dir / "videos"),
            "default_avatar": "speaker",
            "source_face": str(tmp_path / "face.mp4"),
        },
        "stt": {"provider": "faster-whisper", "device_preference": ["cpu"], "cpu": {"model_size": "tiny"}},
        "translation": {"provider": "google", "backends": ["google", "argos", "nllb"]},
        "tts": {"provider": "edge-tts", "output_format": "mp3"},
        "lipsync": {"provider": "demo", "backend": "demo"},
        "languages": {
            "en": {"display_name": "English", "edge_voice": "en-US-JennyNeural", "nllb_code": "eng_Latn"},
            "ar": {"display_name": "Arabic", "edge_voice": "ar-SA-ZariyahNeural", "nllb_code": "arb_Arab"},
        },
    })


def test_avatar_manager(sample_config: Config, tmp_path: Path):
    avatar_mgr = AvatarManager(sample_config)
    avatars = avatar_mgr.list_avatars()
    assert "speaker" in avatars

    face_path = avatar_mgr.get_source_face("speaker")
    assert face_path is not None


def test_translation_cache(sample_config: Config):
    cache = TranslationCache(sample_config)
    assert cache.get("Hello", "en", "ar") is None

    cache.set("Hello", "en", "ar", "مرحبا")
    assert cache.get("Hello", "en", "ar") == "مرحبا"


def test_audio_cache(sample_config: Config, tmp_path: Path):
    cache = AudioCache(sample_config)
    src_file = tmp_path / "test.mp3"
    src_file.write_bytes(b"1234567890")

    dest_file = tmp_path / "cached_dest.mp3"
    assert cache.get("Hello world", "en-US-JennyNeural", "mp3", dest_file) is False

    cache.store("Hello world", "en-US-JennyNeural", "mp3", src_file)
    assert cache.get("Hello world", "en-US-JennyNeural", "mp3", dest_file) is True
    assert dest_file.exists()
    assert dest_file.read_bytes() == b"1234567890"


def test_translation_manager_structure(sample_config: Config):
    trans_mgr = TranslationManager(sample_config)
    assert isinstance(trans_mgr.backend_names, list)


def test_tts_manager_structure(sample_config: Config):
    tts_mgr = TtsManager(sample_config)
    assert tts_mgr.backend_name in ("edge-tts", "coqui")


def test_lipsync_manager_structure(sample_config: Config):
    lipsync_mgr = LipSyncManager(sample_config)
    assert lipsync_mgr.backend_name in ("demo", "null", "wav2lip", "buffered")


def test_nllb_backend_code_mapping(sample_config: Config):
    nllb = NllbBackend(sample_config)
    assert nllb._get_nllb_code("en") == "eng_Latn"
    assert nllb._get_nllb_code("ar") == "arb_Arab"
