"""Skeleton for Phase 8: agent/event_stream.py — in-process event bus.

Two consumer styles:
  - subscribe_sync(callback): blocking, per-event callback
  - subscribe() (async iterator): yields events as they arrive

Backpressure: per-subscriber asyncio.Queue with maxsize; on overflow the
OLDEST event is dropped (queue.put_nowait + discard if full).

Redaction: tool_call inputs / model_call messages are scanned for keys
matching the secret pattern; values replaced with "***".
"""
from __future__ import annotations

import asyncio
import logging
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Optional


SECRET_KEY_PATTERN = re.compile(r"(?i)(password|token|secret|api[_-]?key|auth|credential)")

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    type: str
    timestamp: str
    goal_id: str
    sub_agent_id: Optional[str] = None
    data: dict = field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("***" if SECRET_KEY_PATTERN.search(k) else _redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


# --- sync subscriber type alias ---
SyncCallback = Callable[[StreamEvent], None]


class EventBus:
    def __init__(self, max_queue: int = 1000):
        self.max_queue = max_queue
        self._sync_subs: dict[int, SyncCallback] = {}
        self._async_queues: dict[int, asyncio.Queue] = {}
        self._next_id = 0
        self._lock = threading.Lock()
        self._dropped_since_last: dict[int, int] = {}

    # ---- subscription ----

    def subscribe_sync(self, callback: SyncCallback) -> int:
        with self._lock:
            sub_id = self._next_id
            self._next_id += 1
            self._sync_subs[sub_id] = callback
        return sub_id

    async def subscribe(self) -> AsyncIterator[StreamEvent]:
        loop = asyncio.get_event_loop()
        q: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue)
        with self._lock:
            sub_id = self._next_id
            self._next_id += 1
            self._async_queues[sub_id] = q
            self._dropped_since_last[sub_id] = 0
        try:
            while True:
                ev: StreamEvent = await q.get()
                # if drops have happened, emit a synthetic notice first
                with self._lock:
                    dropped = self._dropped_since_last.get(sub_id, 0)
                    if dropped:
                        self._dropped_since_last[sub_id] = 0
                        notice = StreamEvent(
                            type="bus.events_dropped",
                            timestamp=_now(),
                            goal_id=ev.goal_id,
                            data={"dropped_count": dropped},
                        )
                        yield notice
                yield ev
                if ev.type in ("goal.completed", "goal.halted", "bus.stream_end"):
                    break
        finally:
            with self._lock:
                self._async_queues.pop(sub_id, None)
                self._dropped_since_last.pop(sub_id, None)

    def unsubscribe(self, sub_id: int) -> None:
        with self._lock:
            self._sync_subs.pop(sub_id, None)
            self._async_queues.pop(sub_id, None)
            self._dropped_since_last.pop(sub_id, None)

    # ---- emit ----

    def emit(self, event: StreamEvent) -> None:
        # redact secrets in known fields
        event = StreamEvent(
            type=event.type,
            timestamp=event.timestamp or _now(),
            goal_id=event.goal_id,
            sub_agent_id=event.sub_agent_id,
            data=_redact(event.data),
        )
        with self._lock:
            sync_callbacks = list(self._sync_subs.values())
            queue_pairs = list(self._async_queues.items())

        for cb in sync_callbacks:
            try:
                cb(event)
            except Exception:
                logger.warning("sync subscriber raised", exc_info=True)

        for sub_id, q in queue_pairs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # drop oldest, count it
                try:
                    q.get_nowait()
                    with self._lock:
                        self._dropped_since_last[sub_id] = self._dropped_since_last.get(sub_id, 0) + 1
                    q.put_nowait(event)
                except Exception:
                    pass

    # ---- convenience emitters ----

    def emit_typed(
        self,
        type_: str,
        goal_id: str,
        sub_agent_id: str | None = None,
        **data: Any,
    ) -> None:
        self.emit(StreamEvent(
            type=type_,
            timestamp=_now(),
            goal_id=goal_id,
            sub_agent_id=sub_agent_id,
            data=data,
        ))


# ---- module-wide accessor ----

_INSTANCE: EventBus | None = None
_INSTANCE_LOCK = threading.Lock()


def get_event_bus() -> EventBus:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = EventBus()
        return _INSTANCE
