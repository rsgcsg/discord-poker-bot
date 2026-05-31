from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Protocol

from .config import AppConfig


@dataclass(frozen=True)
class SyncEvent:
    type: str
    channel_id: int
    payload: dict[str, Any]
    created_at: str

    @classmethod
    def create(cls, event_type: str, channel_id: int, payload: dict[str, Any]) -> "SyncEvent":
        return cls(
            type=event_type,
            channel_id=channel_id,
            payload=payload,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "channel_id": self.channel_id,
            "payload": self.payload,
            "created_at": self.created_at,
        }


class SyncBackend(Protocol):
    async def publish(self, event: SyncEvent) -> None:
        ...


class NoopSyncBackend:
    async def publish(self, event: SyncEvent) -> None:
        return None


class JsonlSyncBackend:
    """Simple append-only event sink for future multi-bot synchronization."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def publish(self, event: SyncEvent) -> None:
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")


def sync_backend_from_config(config: AppConfig) -> SyncBackend:
    if config.sync_event_log:
        return JsonlSyncBackend(config.sync_event_log)
    return NoopSyncBackend()
