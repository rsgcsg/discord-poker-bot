from __future__ import annotations

import sqlite3
from pathlib import Path

from .game import PokerTable


class StatsStore:
    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS player_stats (
                    user_id INTEGER PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    hands INTEGER NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    pushes INTEGER NOT NULL DEFAULT 0,
                    net_chips INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def record_finished_hand(self, table: PokerTable) -> None:
        with self._connect() as conn:
            for player in table.players.values():
                if player.start_chips <= 0:
                    continue
                delta = player.chips - player.start_chips
                win = 1 if delta > 0 else 0
                loss = 1 if delta < 0 else 0
                push = 1 if delta == 0 else 0
                conn.execute(
                    """
                    INSERT INTO player_stats
                        (user_id, display_name, hands, wins, losses, pushes, net_chips)
                    VALUES (?, ?, 1, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        display_name = excluded.display_name,
                        hands = hands + 1,
                        wins = wins + excluded.wins,
                        losses = losses + excluded.losses,
                        pushes = pushes + excluded.pushes,
                        net_chips = net_chips + excluded.net_chips
                    """,
                    (player.user_id, player.name, win, loss, push, delta),
                )

    def leaderboard(self, limit: int = 20) -> list[tuple[str, int, int, int, int, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT display_name, hands, wins, losses, pushes, net_chips
                FROM player_stats
                ORDER BY net_chips DESC, wins DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [(str(name), hands, wins, losses, pushes, net) for name, hands, wins, losses, pushes, net in rows]
