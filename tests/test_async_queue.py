"""Unit tests for BoundedAsyncQueue and Backpressure Overload Protection."""

from __future__ import annotations

import pytest

from voicebridge.config import Config
from voicebridge.pipeline.async_queue import BoundedAsyncQueue
from voicebridge.pipeline.contracts.schemas import SttResponse, generate_trace_id


@pytest.fixture
def sample_config() -> Config:
    return Config({
        "feature_flags": {
            "enable_backpressure": True,
        }
    })


def test_async_queue_basic_put_get(sample_config: Config):
    q = BoundedAsyncQueue[str]("test_q", maxsize=3, config=sample_config)
    assert q.is_empty is True
    assert q.qsize == 0

    assert q.put("item1") is True
    assert q.put("item2") is True
    assert q.qsize == 2

    wait_ms, item = q.get(timeout=0.1)
    assert item == "item1"
    assert wait_ms >= 0.0
    assert q.qsize == 1


def test_async_queue_compaction_on_overload(sample_config: Config):
    q = BoundedAsyncQueue[SttResponse]("stt_q", maxsize=2, config=sample_config)

    p1 = SttResponse(trace_id="t1", text="partial 1", confidence=0.5)
    f2 = SttResponse(trace_id="t2", text="final 2", confidence=1.0)
    p3 = SttResponse(trace_id="t3", text="partial 3", confidence=0.6)

    assert q.put(p1) is True
    assert q.put(f2) is True
    assert q.is_full is True

    # Put 3rd item: queue should compact partial transcript p1
    assert q.put(p3) is True
    assert q.compacted_count == 1
    assert q.overload_count == 1

    # Remaining items should be f2 and p3
    _, first = q.get(timeout=0.1)
    assert first.trace_id == "t2"
    _, second = q.get(timeout=0.1)
    assert second.trace_id == "t3"


def test_async_queue_eviction_when_no_partial_to_compact(sample_config: Config):
    q = BoundedAsyncQueue[str]("item_q", maxsize=2, config=sample_config)

    assert q.put("A") is True
    assert q.put("B") is True

    # Put C: queue is full, no SttResponse to compact -> pops oldest item A
    assert q.put("C") is True
    assert q.dropped_count == 1

    _, item1 = q.get(timeout=0.1)
    assert item1 == "B"
    _, item2 = q.get(timeout=0.1)
    assert item2 == "C"
