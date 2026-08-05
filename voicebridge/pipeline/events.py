"""Pipeline event types.

The orchestrator publishes these as an utterance moves through the stages. The
API layer serializes them to JSON and pushes them over a WebSocket to the
meeting UI. Keeping them as plain dataclasses (not dicts) makes the pipeline
self-documenting and keeps the UI contract in one place.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum


class EventType(str, Enum):
    TRANSCRIPT = "transcript"      # recognized source text
    PARTIAL_TRANSCRIPT = "partial_transcript"  # partial transcript
    TRANSLATION = "translation"    # translated target text
    SPEECH_READY = "speech_ready"  # TTS + lip-sync clip ready to play
    STATUS = "status"              # pipeline lifecycle / status message
    ERROR = "error"


@dataclass
class PipelineEvent:
    """A single event emitted by one direction of the pipeline."""

    type: EventType
    direction: str          # e.g. "EN->AR"
    speaker: str            # participant id, e.g. "me" / "other"
    text: str = ""
    translated_text: str = ""
    source_lang: str = ""
    target_lang: str = ""
    audio_url: str = ""
    video_url: str = ""
    is_synced: bool = False
    latency_ms: float = 0.0
    note: str = ""
    sentence_id: int = 0
    trace_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["type"] = self.type.value
        return data
