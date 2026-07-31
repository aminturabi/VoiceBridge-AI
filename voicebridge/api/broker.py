"""Event broker bridging pipeline threads to async WebSocket clients.

Pipeline workers run in plain threads and call ``publish`` (sync). WebSocket
handlers run on the asyncio event loop and ``subscribe`` to an async queue.
The broker captures the running loop at startup and uses
``call_soon_threadsafe`` to hand events across the thread/async boundary safely.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from voicebridge.logging_conf import get_logger
from voicebridge.pipeline.events import PipelineEvent

logger = get_logger(__name__)


class EventBroker:
    """Fan out pipeline events to any number of async subscribers."""

    def __init__(self, max_queue: int = 256):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._subscribers: set[asyncio.Queue] = set()
        self._max_queue = max_queue
        # Ring buffer of recent events so a late-joining UI shows history.
        self._history: list[dict] = []
        self._history_limit = 100

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Record the asyncio loop that WebSocket handlers run on."""
        self._loop = loop

    def publish(self, event: PipelineEvent) -> None:
        """Called from pipeline threads. Schedules delivery on the loop."""
        payload = event.to_dict()
        if self._loop is None:
            # No UI attached yet; just keep history.
            self._remember(payload)
            return
        self._loop.call_soon_threadsafe(self._deliver, payload)

    def _remember(self, payload: dict) -> None:
        self._history.append(payload)
        if len(self._history) > self._history_limit:
            self._history.pop(0)

    def _deliver(self, payload: dict) -> None:
        """Runs on the event loop thread."""
        self._remember(payload)
        for queue_ in list(self._subscribers):
            try:
                queue_.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue full; dropping event")

    async def subscribe(self) -> asyncio.Queue:
        queue_ = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers.add(queue_)
        return queue_

    def unsubscribe(self, queue_: asyncio.Queue) -> None:
        self._subscribers.discard(queue_)

    @property
    def history(self) -> list[dict]:
        return list(self._history)
