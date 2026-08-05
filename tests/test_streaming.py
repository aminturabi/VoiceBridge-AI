"""Unit tests for partial STT transcript streaming & LLM worker sentence chunking."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock
import pytest

from voicebridge.config import Config
from voicebridge.pipeline.async_queue import BoundedAsyncQueue
from voicebridge.pipeline.contracts.schemas import SttResponse
from voicebridge.pipeline.events import EventType, PipelineEvent
from voicebridge.pipeline.workers.llm_worker import LlmWorker


@pytest.fixture
def streaming_config() -> Config:
    return Config({
        "buffer": {
            "word_limit": 3,
            "timeout_seconds": 1.0,
            "sentence_endings": [".", "?"],
            "noise_phrases": [],
        },
        "cache": {"enabled": False},
        "translation": {"provider": "google", "backends": ["google"]},
    })


def test_llm_worker_streaming_sentence_chunks(streaming_config: Config):
    in_q = BoundedAsyncQueue[SttResponse]("stt_in", maxsize=5, config=streaming_config)
    out_q = BoundedAsyncQueue("llm_out", maxsize=5, config=streaming_config)
    stop_evt = threading.Event()
    events: list[PipelineEvent] = []

    mock_llm_adapter = MagicMock()
    mock_llm_adapter.process_text.side_effect = lambda req: MagicMock(
        trace_id=req.trace_id, text=req.text, translated_text=f"translated_{req.text}"
    )

    worker = LlmWorker(
        config=streaming_config,
        source_lang="en",
        target_lang="ar",
        in_queue=in_q,
        out_queue=out_q,
        stop_event=stop_evt,
        emit_event=events.append,
        adapter=mock_llm_adapter,
    )

    stt_item = SttResponse(trace_id="str-1", text="Hello world testing.")
    worker.process_item(stt_item)

    assert len(events) == 1
    assert events[0].type == EventType.TRANSLATION
    assert events[0].translated_text == "translated_Hello world testing."
    assert out_q.qsize == 1
