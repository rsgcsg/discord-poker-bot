from __future__ import annotations

from .config import AppConfig
from .game import PokerTable


def table_url(config: AppConfig, table: PokerTable) -> str:
    return f"{config.public_base_url}/table/{table.channel_id}"
