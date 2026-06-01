import os
import tempfile
import unittest
from unittest.mock import patch

from poker_bot.config import AppConfig
from poker_bot.registry import TableRegistry
from poker_bot.storage import StatsStore
from poker_bot.sync import NoopSyncBackend
from poker_bot.game import Action, Phase
from poker_bot.table_views import serialize_public_table, serialize_viewer_table
from poker_bot.web_server import APP_BUILD, HTML, LOBBY_HTML


class AppIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_table_snapshot_hides_hole_cards(self):
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
                self.assertNotIn(card.label(), snapshot_text)

    async def test_player_table_snapshot_only_exposes_own_hole_cards(self):
        registry = TableRegistry(StatsStore(":memory:"), NoopSyncBackend())
        table = await registry.create_table(123, "online", 10, 20, 1000)
        table.add_player(1, "Alice")
        table.add_player(2, "Bob")
        table.start_hand()

        bob = table.players[2]
        snapshot_text = repr(serialize_viewer_table(registry, str(table.channel_id), 1))

        for card in table.players[1].hole:
            self.assertIn(card.label(), snapshot_text)
        for card in bob.hole:
            self.assertNotIn(card.label(), snapshot_text)

    async def test_registry_can_create_multiple_tables(self):
        registry = TableRegistry(StatsStore(":memory:"), NoopSyncBackend())
        first = await registry.create_table(123, "online", 10, 20, 1000)
        second = await registry.create_table(123, "offline", 5, 10, 500)

        self.assertNotEqual(first.channel_id, second.channel_id)
        self.assertEqual(len(registry.tables()), 2)

    async def test_empty_tables_are_pruned_after_ttl(self):
        registry = TableRegistry(StatsStore(":memory:"), NoopSyncBackend())
        table = await registry.create_table(123, "online", 10, 20, 1000)
        table.empty_since -= 601

        removed = registry.prune_empty_tables(max_empty_seconds=600)

        self.assertEqual(removed, [table.channel_id])
        self.assertEqual(registry.tables(), [])

    async def test_recent_empty_tables_are_not_pruned(self):
        registry = TableRegistry(StatsStore(":memory:"), NoopSyncBackend())
        table = await registry.create_table(123, "online", 10, 20, 1000)

        removed = registry.prune_empty_tables(max_empty_seconds=600)

        self.assertEqual(removed, [])
        self.assertEqual(registry.tables(), [table])

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

    async def test_timeout_refunds_current_bets_and_stops_hand(self):
        registry = TableRegistry(StatsStore(":memory:"), NoopSyncBackend())
        table = await registry.create_table(123, "online", 10, 20, 1000)
        table.add_player(1, "Alice")
        table.add_player(2, "Bob")
        table.hand_timeout_seconds = 0
        table.start_hand()
        total_chips = sum(player.chips for player in table.players.values())

        table.last_action_at -= 10
        self.assertTrue(table.expire_if_needed())

        self.assertFalse(table.hand_running)
        self.assertEqual(sum(player.chips for player in table.players.values()), total_chips + 30)
        self.assertIn("refunded", table.last_result)

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
                "DISCORD_CLIENT_ID": "123",
                "DISCORD_CLIENT_SECRET": "secret",
            },
            clear=True,
        ):
            config = AppConfig.from_env()
        self.assertEqual(config.web_host, "0.0.0.0")
        self.assertEqual(config.web_port, 9999)
        self.assertEqual(config.public_base_url, "https://example.com")
        self.assertEqual(config.discord_client_id, "123")
        self.assertEqual(config.discord_redirect_uri, "https://example.com/oauth/callback")

    def test_activity_html_uses_current_auth_message(self):
        combined = HTML + LOBBY_HTML

        self.assertIn(APP_BUILD, combined)
        self.assertIn("Activity SDK unavailable", combined)
        self.assertNotIn("Discord authorization did not start", combined)
        self.assertNotIn("Use the Open Poker App button in Discord", combined)


if __name__ == "__main__":
    unittest.main()
