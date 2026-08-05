"""Base class for independent pipeline workers."""

from __future__ import annotations

import queue
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, TypeVar

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.pipeline.async_queue import BoundedAsyncQueue

logger = get_logger(__name__)

InT = TypeVar("InT")
OutT = TypeVar("OutT")


class BaseWorker(Generic[InT, OutT], ABC):
    """Abstract worker thread with non-blocking producer/consumer loops & utilization tracking."""

    def __init__(
        self,
        name: str,
        config: Config,
        in_queue: Optional[BoundedAsyncQueue[InT]],
        out_queue: Optional[BoundedAsyncQueue[OutT]],
        stop_event: threading.Event,
    ):
        self.name = name
        self.config = config
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.stop_event = stop_event

        self._thread: Optional[threading.Thread] = None
        self._active_time_s: float = 0.0
        self._total_time_s: float = 0.0
        self._items_processed: int = 0
        self._start_time: float = 0.0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def utilization_percent(self) -> float:
        total = time.perf_counter() - self._start_time if self._start_time > 0 else 1.0
        return (self._active_time_s / total * 100.0) if total > 0 else 0.0

    @property
    def items_processed(self) -> int:
        return self._items_processed

    def start(self) -> None:
        """Start worker thread."""
        self._start_time = time.perf_counter()
        self._thread = threading.Thread(
            target=self._run_loop, name=f"worker-{self.name}", daemon=True
        )
        self._thread.start()
        logger.info("[%s Worker] Started.", self.name)

    def cancel(self) -> None:
        """Signal worker cancellation."""
        self.stop_event.set()

    def join(self, timeout: Optional[float] = 2.0) -> None:
        """Wait for worker thread to stop."""
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run_loop(self) -> None:
        while not self.stop_event.is_set():
            if self.in_queue is None:
                # Producer-only worker
                t0 = time.perf_counter()
                try:
                    self.produce_step()
                except Exception as err:
                    logger.error("[%s Worker] Producer error: %s", self.name, err, exc_info=True)
                finally:
                    self._active_time_s += time.perf_counter() - t0
                continue

            try:
                wait_ms, item = self.in_queue.get(block=True, timeout=0.2)
                t0 = time.perf_counter()
                try:
                    self.process_item(item, wait_ms=wait_ms)
                    self._items_processed += 1
                except Exception as err:
                    logger.error("[%s Worker] Processing error: %s", self.name, err, exc_info=True)
                finally:
                    self._active_time_s += time.perf_counter() - t0
                    self.in_queue.task_done()
            except queue.Empty:
                continue

        logger.info("[%s Worker] Stopped. Processed %d items.", self.name, self._items_processed)

    def produce_step(self) -> None:
        """Overridden by producer-only workers (e.g. VAD / capture)."""
        time.sleep(0.05)

    @abstractmethod
    def process_item(self, item: InT, wait_ms: float = 0.0) -> None:
        """Process incoming item from in_queue and produce to out_queue."""
        pass
