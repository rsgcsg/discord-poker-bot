from __future__ import annotations

import time

from .registry import TableRegistry


def serialize_public_table(registry: TableRegistry, table_id: str) -> dict[str, object]:
    return serialize_table(registry, table_id)


def serialize_viewer_table(registry: TableRegistry, table_id: str, viewer_id: int | None) -> dict[str, object]:
    return serialize_table(registry, table_id, viewer_id)


def serialize_table(registry: TableRegistry, table_id: str, viewer_id: int | None = None) -> dict[str, object]:
    table = registry.get_by_public_id(table_id)
    table.expire_if_needed()
    data = table.snapshot()
    current = table.players.get(table.current_user_id) if table.current_user_id else None
    roles = table.seat_roles()
    data["current_player_name"] = current.name if current else None
    data["viewer_id"] = viewer_id
    data["viewer_is_seated"] = viewer_id in table.players if viewer_id else False
    data["viewer_legal_actions"] = table.legal_actions_for(viewer_id) if data["viewer_is_seated"] else []
    data["seconds_until_timeout"] = (
        max(0, int(table.hand_timeout_seconds - (time.time() - table.last_action_at)))
        if table.hand_running
        else None
    )
    for player in data["players"]:
        player["roles"] = roles.get(player["user_id"], [])
        source = table.players[player["user_id"]]
        can_view_hole = viewer_id == source.user_id or table.phase.value == "finished"
        player["hole_cards"] = [card.label() for card in source.hole] if can_view_hole else []
        player["offline_cards"] = [card.label() for card in source.offline_cards]
    return data
