"""In-process streaming events for agent execution."""
from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SECRET_KEY_PATTERN = re.compile(r"password|token|secret|api[_-]?key|auth", re.IGNORECASE)

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """A single execution event emitted while a goal runs."""

    type: str
    timestamp: datetime
    goal_id: str
    sub_agent_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


SyncCallback = Callable[[StreamEvent], None]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def redact_secrets(value: Any) -> Any:
    """Return a copy with secret-looking dict keys redacted."""
    if isinstance(value, dict):
        return {
            key: "***" if SECRET_KEY_PATTERN.search(str(key)) else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value


class EventBus:
    """Synchronous in-process event bus."""

    def __init__(self) -> None:
        self._sync_subs: dict[int, SyncCallback] = {}
        self._next_id = 0
        self._lock = threading.Lock()

    def emit(self, event: StreamEvent) -> None:
        """Emit an event to all current subscribers."""
        safe_event = StreamEvent(
            type=event.type,
            timestamp=event.timestamp or _now(),
            goal_id=event.goal_id,
            sub_agent_id=event.sub_agent_id,
            data=redact_secrets(event.data),
        )
        with self._lock:
            callbacks = list(self._sync_subs.values())

        for callback in callbacks:
            try:
                callback(safe_event)
            except Exception:
                logger.warning("stream event subscriber raised", exc_info=True)

    def subscribe_sync(self, callback: SyncCallback) -> int:
        """Subscribe a synchronous callback and return its subscription id."""
        with self._lock:
            sub_id = self._next_id
            self._next_id += 1
            self._sync_subs[sub_id] = callback
        return sub_id

    def unsubscribe(self, sub_id: int) -> None:
        """Remove a synchronous subscriber if it exists."""
        with self._lock:
            self._sync_subs.pop(sub_id, None)

    def emit_typed(
        self,
        type_: str,
        goal_id: str,
        sub_agent_id: str | None = None,
        **data: Any,
    ) -> None:
        """Convenience helper for emitting a typed event with current timestamp."""
        self.emit(StreamEvent(type_, _now(), goal_id, sub_agent_id, data))


_INSTANCE: EventBus | None = None
_INSTANCE_LOCK = threading.Lock()


def get_event_bus() -> EventBus:
    """Return the process-wide event bus singleton."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = EventBus()
        return _INSTANCE
