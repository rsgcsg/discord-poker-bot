from __future__ import annotations

from dataclasses import dataclass

import discord

from .bot import create_bot
from .config import AppConfig
from .registry import TableRegistry
from .storage import StatsStore
from .sync import sync_backend_from_config
from .web_server import PokerWebServer


@dataclass
class PokerRuntime:
    config: AppConfig
    registry: TableRegistry
    web_server: PokerWebServer


def create_runtime(config: AppConfig | None = None) -> PokerRuntime:
    app_config = config or AppConfig.from_env()
    registry = TableRegistry(
        StatsStore(app_config.db_path),
        sync_backend_from_config(app_config),
    )
    web_server = PokerWebServer(registry, app_config)
    return PokerRuntime(app_config, registry, web_server)


def run() -> None:
    runtime = create_runtime()
    if not runtime.config.discord_token:
        raise SystemExit(
            "DISCORD_TOKEN is missing.\n"
            "Set DISCORD_TOKEN in .env or your cloud environment, then run: python main.py"
        )
    try:
        create_bot(runtime).run(runtime.config.discord_token)
    except discord.LoginFailure as exc:
        raise SystemExit(
            "Discord rejected DISCORD_TOKEN.\n"
            "Reset the bot token in Discord Developer Portal, update DISCORD_TOKEN in your cloud environment, "
            "then redeploy. Do not include quotes, spaces, or the word 'Bot'."
        ) from exc
