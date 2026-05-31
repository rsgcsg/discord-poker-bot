from __future__ import annotations

from .game import PokerTable
from .storage import StatsStore
from .sync import SyncBackend, SyncEvent


class TableRegistry:
    """Owns live tables and emits sync events around state changes."""

    def __init__(self, stats: StatsStore, sync: SyncBackend) -> None:
        self._tables: dict[int, PokerTable] = {}
        self._stats = stats
        self._sync = sync

    def get(self, channel_id: int | None) -> PokerTable:
        if channel_id is None or channel_id not in self._tables:
            raise ValueError("No poker table exists in this channel.")
        return self._tables[channel_id]

    def get_by_public_id(self, public_id: str) -> PokerTable:
        try:
            channel_id = int(public_id)
        except ValueError as exc:
            raise ValueError("Invalid table id.") from exc
        return self.get(channel_id)

    def tables(self) -> list[PokerTable]:
        return list(self._tables.values())

    async def create_table(
        self,
        channel_id: int,
        mode: str,
        small_blind: int,
        big_blind: int,
        starting_chips: int,
    ) -> PokerTable:
        table = PokerTable(channel_id, mode, small_blind, big_blind, starting_chips)
        self._tables[channel_id] = table
        await self.publish("table.created", table)
        return table

    async def publish(self, event_type: str, table: PokerTable, **extra: object) -> None:
        payload = {"table": table.snapshot()}
        if extra:
            payload["extra"] = extra
        await self._sync.publish(SyncEvent.create(event_type, table.channel_id, payload))

    async def record_finished_hand_once(self, table: PokerTable) -> None:
        if not table.hand_finished_needs_stats():
            return
        self._stats.record_finished_hand(table)
        table.stats_recorded = True
        await self.publish("hand.stats_recorded", table)

    def leaderboard(self, limit: int = 20):
        return self._stats.leaderboard(limit)
