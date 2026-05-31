from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    discord_token: str
    db_path: str
    sync_event_log: str | None = None
    web_host: str = "127.0.0.1"
    web_port: int = 8765
    public_base_url: str = "http://127.0.0.1:8765"
    discord_guild_id: int | None = None
    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_redirect_uri: str = ""
    session_secret: str = ""

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv()
        platform_port = os.getenv("PORT")
        web_host = "0.0.0.0" if platform_port else os.getenv("POKER_WEB_HOST", "127.0.0.1")
        web_port = int(platform_port or os.getenv("POKER_WEB_PORT", "8765"))
        public_base_url = os.getenv("POKER_PUBLIC_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
        return cls(
            discord_token=_clean_secret(os.getenv("DISCORD_TOKEN", "")),
            db_path=os.getenv("POKER_DB_PATH", "poker_stats.sqlite3"),
            sync_event_log=os.getenv("POKER_SYNC_EVENT_LOG") or None,
            web_host=web_host,
            web_port=web_port,
            public_base_url=public_base_url,
            discord_guild_id=_optional_int(os.getenv("DISCORD_GUILD_ID")),
            discord_client_id=_clean_secret(os.getenv("DISCORD_CLIENT_ID", "")),
            discord_client_secret=_clean_secret(os.getenv("DISCORD_CLIENT_SECRET", "")),
            discord_redirect_uri=os.getenv("DISCORD_REDIRECT_URI", f"{public_base_url}/oauth/callback").strip(),
            session_secret=_clean_secret(os.getenv("POKER_SESSION_SECRET", "")),
        )


def _clean_secret(value: str) -> str:
    return value.strip().strip('"').strip("'")


def _optional_int(value: str | None) -> int | None:
    if not value:
        return None
    return int(value.strip())
