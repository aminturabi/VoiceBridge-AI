"""Thread-safe and asyncio-compatible Bounded Queue with Backpressure & Compaction.

Manages inter-stage items between pipeline workers with overload protection.
"""

from __future__ import annotations

import asyncio
import queue
import time
from typing import Any, Generic, List, Optional, TypeVar

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.pipeline.contracts.schemas import SttResponse, generate_trace_id

logger = get_logger(__name__)

T = TypeVar("T")


class BoundedAsyncQueue(Generic[T]):
    """Bounded, thread-safe queue supporting backpressure overload protection."""

    def __init__(self, name: str, maxsize: int = 10, config: Optional[Config] = None):
        self.name = name
        self.maxsize = maxsize
        self._config = config
        self._queue: queue.Queue[tuple[float, T]] = queue.Queue(maxsize=maxsize)
        self._backpressure_enabled = config.enable_backpressure if config else True

        # Telemetry counters
        self.overload_count: int = 0
        self.dropped_count: int = 0
        self.compacted_count: int = 0

    @property
    def qsize(self) -> int:
        return self._queue.qsize()

    @property
    def is_full(self) -> bool:
        return self._queue.full()

    @property
    def is_empty(self) -> bool:
        return self._queue.empty()

    def put(self, item: T, block: bool = True, timeout: Optional[float] = 0.5) -> bool:
        """Put item into queue with backpressure handling if full."""
        put_time = time.perf_counter()

        if self._queue.full() and self._backpressure_enabled:
            self._handle_overload(item)

        try:
            self._queue.put((put_time, item), block=block, timeout=timeout)
            return True
        except queue.Full:
            self.overload_count += 1
            self.dropped_count += 1
            trace_id = getattr(item, "trace_id", "unknown_trace")
            logger.warning(
                "[%s Queue Overload] Queue full (maxsize=%d). Dropped item for trace_id=%s",
                self.name, self.maxsize, trace_id
            )
            return False

    def get(self, block: bool = True, timeout: Optional[float] = 0.5) -> tuple[float, T]:
        """Get (wait_time_ms, item) tuple from queue."""
        put_time, item = self._queue.get(block=block, timeout=timeout)
        wait_time_ms = (time.perf_counter() - put_time) * 1000.0
        return wait_time_ms, item

    def task_done(self) -> None:
        self._queue.task_done()

    def _handle_overload(self, new_item: T) -> None:
        """Compact queue items or drop obsolete partial transcripts when full."""
        self.overload_count += 1
        trace_id = getattr(new_item, "trace_id", generate_trace_id())

        # Attempt compaction: search for partial STT transcripts or obsolete messages
        with self._queue.mutex:
            items = list(self._queue.queue)
            # Find any partial STT response to drop (where confidence < 1.0 or reliable < total)
            idx_to_remove = -1
            for idx, (t, item) in enumerate(items):
                if isinstance(item, SttResponse) and item.confidence < 1.0:
                    idx_to_remove = idx
                    break

            if idx_to_remove != -1:
                del items[idx_to_remove]
                self._queue.queue.clear()
                self._queue.queue.extend(items)
                self.compacted_count += 1
                logger.info(
                    "[%s Backpressure] Compacted partial transcript for trace_id=%s. Remaining queue size=%d",
                    self.name, trace_id, len(items)
                )
            else:
                # If no partial transcript to compact, pop oldest item (head of queue)
                if items:
                    old_time, old_item = items.pop(0)
                    self._queue.queue.clear()
                    self._queue.queue.extend(items)
                    self.dropped_count += 1
                    old_trace = getattr(old_item, "trace_id", "unknown")
                    logger.warning(
                        "[%s Backpressure] Queue full. Evicted oldest item (trace_id=%s) to accept trace_id=%s",
                        self.name, old_trace, trace_id
                    )
