import os
import tempfile
import unittest
from unittest.mock import patch

from poker_bot.config import AppConfig
from poker_bot.registry import TableRegistry
from poker_bot.storage import StatsStore
from poker_bot.sync import NoopSyncBackend
from poker_bot.game import Action, Phase
from poker_bot.web_server import serialize_public_table


class AppIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_website_table_snapshot_exposes_hole_cards_for_table_play(self):
        registry = TableRegistry(StatsStore(":memory:"), NoopSyncBackend())
        table = await registry.create_table(123, "online", 10, 20, 1000)
        table.add_player(1, "Alice")
        table.add_player(2, "Bob")
        table.start_hand()

        snapshot = serialize_public_table(registry, str(table.channel_id))
        snapshot_text = repr(snapshot)

        self.assertIn("hole_cards", snapshot_text)
        for player in table.players.values():
            for card in player.hole:
                self.assertIn(card.label(), snapshot_text)

    async def test_registry_can_create_multiple_tables(self):
        registry = TableRegistry(StatsStore(":memory:"), NoopSyncBackend())
        first = await registry.create_table(123, "online", 10, 20, 1000)
        second = await registry.create_table(123, "offline", 5, 10, 500)

        self.assertNotEqual(first.channel_id, second.channel_id)
        self.assertEqual(len(registry.tables()), 2)

    async def test_web_play_flow_can_start_and_act(self):
        registry = TableRegistry(StatsStore(":memory:"), NoopSyncBackend())
        table = await registry.create_table(123, "online", 10, 20, 1000)
        table.add_player(1, "Alice")
        table.add_player(2, "Bob")

        table.start_hand()
        actor = table.current_user_id
        table.apply_action(actor, Action.CALL)

        self.assertIn(table.phase, {Phase.PREFLOP, Phase.FLOP, Phase.FINISHED})
        self.assertGreater(sum(player.committed for player in table.players.values()), 0)

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
