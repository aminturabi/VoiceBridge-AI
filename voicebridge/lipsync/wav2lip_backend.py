"""Wav2Lip backend implementation — real lip sync on short segments."""

from __future__ import annotations

import subprocess
import sys
import time
import uuid
from pathlib import Path

from voicebridge.avatar.manager import AvatarManager
from voicebridge.config import Config
from voicebridge.lipsync.base import LipSyncBackend, LipSyncError, LipSyncResult
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)


class Wav2LipBackend(LipSyncBackend):
    """Wav2Lip AI lip-synchronization provider backend."""

    name = "wav2lip"

    def __init__(self, config: Config):
        self._config = config
        wav2lip_cfg = config.get("lipsync.wav2lip", config.get("lipsync.buffered", {}))

        # Check models directory first, then config path, then legacy asset path
        model_dir = config.path("models.wav2lip_dir", "models/wav2lip")
        default_ckpt = model_dir / "wav2lip_gan.pth"
        if default_ckpt.exists():
            self._checkpoint = default_ckpt
        else:
            self._checkpoint = config.path(
                "lipsync.wav2lip.checkpoint",
                config.path("lipsync.buffered.checkpoint", "assets/wav2lip/wav2lip_gan.pth")
            )

        # Source face resolution via AvatarManager
        self._avatar_mgr = AvatarManager(config)
        self._source_face = self._avatar_mgr.get_source_face()

        # Location of Wav2Lip repository script
        repo = wav2lip_cfg.get("repo_dir", "third_party/Wav2Lip")
        self._repo_dir = config.path("lipsync.wav2lip.repo_dir", repo)
        self._batch_size = int(wav2lip_cfg.get("batch_size", 16))
        self._output_root = config.path("app.output_dir")

    def _inference_script(self) -> Path:
        return self._repo_dir / "inference.py"

    def is_available(self) -> bool:
        checks = {
            "Wav2Lip inference.py": self._inference_script().exists(),
            "checkpoint": self._checkpoint.exists(),
            "source face": self._source_face.exists(),
        }
        missing = [name for name, ok in checks.items() if not ok]
        if missing:
            logger.info("Wav2Lip unavailable; missing: %s", ", ".join(missing))
            return False
        return True

    def sync(self, audio_path: Path, direction: str, sentence_id: int) -> LipSyncResult:
        if not self.is_available():
            raise LipSyncError("Wav2Lip backend is not available")

        start = time.perf_counter()
        safe = direction.lower().replace(" ", "_").replace("->", "to")
        out_dir = self._output_root / safe / "lipsync"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"lip_{sentence_id}_{uuid.uuid4().hex}.mp4"

        cmd = [
            sys.executable, str(self._inference_script()),
            "--checkpoint_path", str(self._checkpoint),
            "--face", str(self._source_face),
            "--audio", str(audio_path),
            "--outfile", str(out_path),
            "--wav2lip_batch_size", str(self._batch_size),
        ]
        logger.info("[%s] Running Wav2Lip on %s...", direction, audio_path.name)
        try:
            proc = subprocess.run(
                cmd, cwd=str(self._repo_dir), capture_output=True, text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired as error:
            raise LipSyncError(f"Wav2Lip timed out: {error}") from error

        if proc.returncode != 0 or not out_path.exists():
            raise LipSyncError(
                f"Wav2Lip failed (rc={proc.returncode}): {proc.stderr[-500:]}"
            )

        latency = time.perf_counter() - start
        logger.info("[%s] Wav2Lip done in %.1fs -> %s", direction, latency, out_path.name)
        return LipSyncResult(
            video_path=out_path,
            audio_path=audio_path,
            backend=self.name,
            latency_seconds=latency,
            is_synced=True,
            note="Wav2Lip lip synchronization",
        )
