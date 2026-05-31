from __future__ import annotations

import time

from .game import PokerTable
from .storage import StatsStore
from .sync import SyncBackend, SyncEvent


class TableRegistry:
    """Owns live tables and emits sync events around state changes."""

    def __init__(self, stats: StatsStore, sync: SyncBackend) -> None:
        self._tables: dict[int, PokerTable] = {}
        self._stats = stats
        self._sync = sync
        self._last_table_id = 0

    def get(self, table_id: int | None) -> PokerTable:
        if table_id is None or table_id not in self._tables:
            raise ValueError("No poker table exists for that id.")
        return self._tables[table_id]

    def get_by_public_id(self, public_id: str) -> PokerTable:
        try:
            table_id = int(public_id)
        except ValueError as exc:
            raise ValueError("Invalid table id.") from exc
        return self.get(table_id)

    def tables(self) -> list[PokerTable]:
        self.prune_empty_tables()
        return list(self._tables.values())

    def prune_empty_tables(self, max_empty_seconds: int = 600) -> list[int]:
        now = time.time()
        removed: list[int] = []
        for table_id, table in list(self._tables.items()):
            if table.players or table.hand_running:
                continue
            empty_since = table.empty_since or table.created_at
            if now - empty_since < max_empty_seconds:
                continue
            removed.append(table_id)
            del self._tables[table_id]
        return removed

    def latest_table_id(self) -> int | None:
        self.prune_empty_tables()
        if not self._tables:
            return None
        return max(self._tables)

    async def create_table(
        self,
        channel_id: int,
        mode: str,
        small_blind: int,
        big_blind: int,
        starting_chips: int,
    ) -> PokerTable:
        table_id = self._new_table_id()
        table = PokerTable(table_id, mode, small_blind, big_blind, starting_chips)
        self._tables[table_id] = table
        await self.publish("table.created", table)
        return table

    def _new_table_id(self) -> int:
        candidate = int(time.time() * 1000)
        if candidate <= self._last_table_id:
            candidate = self._last_table_id + 1
        self._last_table_id = candidate
        return candidate

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
