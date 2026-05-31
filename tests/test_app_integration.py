import os
import tempfile
import unittest
from unittest.mock import patch

from poker_bot.config import AppConfig
from poker_bot.registry import TableRegistry
from poker_bot.storage import StatsStore
from poker_bot.sync import NoopSyncBackend
from poker_bot.web_server import serialize_public_table


class AppIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_table_snapshot_does_not_expose_hole_cards(self):
        registry = TableRegistry(StatsStore(":memory:"), NoopSyncBackend())
        table = await registry.create_table(123, "online", 10, 20, 1000)
        table.add_player(1, "Alice")
        table.add_player(2, "Bob")
        table.start_hand()

        snapshot = serialize_public_table(registry, "123")
        snapshot_text = repr(snapshot)

        self.assertNotIn("hole", snapshot_text)
        for player in table.players.values():
            for card in player.hole:
                self.assertNotIn(card.label(), snapshot_text)

    def test_stats_store_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "nested", "stats.sqlite3")
            StatsStore(db_path)
            self.assertTrue(os.path.exists(db_path))

    def test_config_prefers_platform_port(self):
        with patch("poker_bot.config.load_dotenv"), patch.dict(
            os.environ,
            {
                "PORT": "9999",
                "POKER_WEB_HOST": "127.0.0.1",
                "POKER_WEB_PORT": "1111",
                "POKER_PUBLIC_BASE_URL": "https://example.com/",
            },
            clear=True,
        ):
            config = AppConfig.from_env()
        self.assertEqual(config.web_host, "0.0.0.0")
        self.assertEqual(config.web_port, 9999)
        self.assertEqual(config.public_base_url, "https://example.com")


if __name__ == "__main__":
    unittest.main()
