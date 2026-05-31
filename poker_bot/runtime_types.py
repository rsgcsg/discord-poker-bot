from __future__ import annotations

from typing import Protocol

from .config import AppConfig
from .registry import TableRegistry


class WebServerRuntime(Protocol):
    def set_launch_target(self, user_id: int, table_id: int) -> None:
        ...

    async def start(self) -> None:
        ...

    async def stop(self) -> None:
        ...


class PokerRuntimeProtocol(Protocol):
    config: AppConfig
    registry: TableRegistry
    web_server: WebServerRuntime
