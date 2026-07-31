"""Buffered Wav2Lip backend — real lip sync on short segments.

Runs genuine Wav2Lip inference on each TTS clip, driving a source face
video/image. On CPU this is not real-time: a few seconds of audio take longer
than their duration to render, so we call this *buffered* (near-real-time) and
report the extra latency honestly in :class:`LipSyncResult`.

Wav2Lip ships as a standalone repo with an ``inference.py`` CLI, so rather than
vendoring its model code we invoke that script as a subprocess. Configure its
location + checkpoint in ``config.yaml``. If the repo, checkpoint, or source
face is missing, :meth:`is_available` returns False and the manager falls back.
"""

from __future__ import annotations

import subprocess
import sys
import time
import uuid
from pathlib import Path

from voicebridge.config import Config
from voicebridge.lipsync.base import LipSyncBackend, LipSyncError, LipSyncResult
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)


class BufferedWav2LipBackend(LipSyncBackend):
    name = "buffered"

    def __init__(self, config: Config):
        buffered = config.get("lipsync.buffered", {})
        self._checkpoint = config.path(
            "lipsync.buffered.checkpoint", "assets/wav2lip/wav2lip_gan.pth"
        )
        self._source_face = config.path(
            "lipsync.source_face", "assets/faces/speaker.mp4"
        )
        # Location of a cloned Wav2Lip repo (contains inference.py).
        repo = buffered.get("repo_dir", "third_party/Wav2Lip")
        self._repo_dir = config.path("lipsync.buffered.repo_dir", repo)
        self._batch_size = int(buffered.get("batch_size", 16))
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
            logger.info("Buffered Wav2Lip unavailable; missing: %s", ", ".join(missing))
            return False
        return True

    def sync(self, audio_path: Path, direction: str, sentence_id: int) -> LipSyncResult:
        if not self.is_available():
            raise LipSyncError("Buffered Wav2Lip backend is not available")

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
            note="buffered Wav2Lip (near-real-time on CPU)",
        )
