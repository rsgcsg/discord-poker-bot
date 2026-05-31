from __future__ import annotations

import logging

from aiohttp import web

from .config import AppConfig
from .game import Action
from .registry import TableRegistry
from .table_renderer import render_table


logger = logging.getLogger(__name__)


def serialize_public_table(registry: TableRegistry, table_id: str) -> dict[str, object]:
    table = registry.get_by_public_id(table_id)
    data = table.snapshot()
    current = table.players.get(table.current_user_id) if table.current_user_id else None
    roles = table.seat_roles()
    data["current_player_name"] = current.name if current else None
    for player in data["players"]:
        player["roles"] = roles.get(player["user_id"], [])
        source = table.players[player["user_id"]]
        player["hole_cards"] = [card.label() for card in source.hole]
        player["offline_cards"] = [card.label() for card in source.offline_cards]
    return data


HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Texas Hold'em Table</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1118;
      --panel: #111b26;
      --line: #26384a;
      --text: #edf4f8;
      --muted: #9fb0bd;
      --gold: #efd074;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: radial-gradient(circle at top, #182636 0, var(--bg) 54%);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      overflow-x: hidden;
    }
    .app {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 14px 22px;
      background: rgba(10, 16, 23, .86);
      border-bottom: 1px solid var(--line);
    }
    h1 {
      margin: 0;
      font-size: 20px;
      letter-spacing: 0;
    }
    .meta {
      display: flex;
      align-items: center;
      gap: 12px;
      color: var(--muted);
      font-size: 14px;
      white-space: nowrap;
    }
    .pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 7px 10px;
      background: rgba(17, 27, 38, .8);
    }
    main {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      gap: 16px;
      padding: 16px;
      align-items: stretch;
    }
    .stage {
      min-height: calc(100vh - 90px);
      display: grid;
      place-items: center;
      background: #071018;
      border: 1px solid var(--line);
      overflow: hidden;
    }
    .stage img {
      display: block;
      width: min(100%, calc((100vh - 98px) * 1.579));
      max-height: calc(100vh - 98px);
      object-fit: contain;
    }
    aside {
      background: rgba(17, 27, 38, .88);
      border: 1px solid var(--line);
      padding: 16px;
      overflow: auto;
      max-height: calc(100vh - 90px);
    }
    h2 {
      margin: 0 0 12px;
      font-size: 16px;
      color: var(--gold);
    }
    .row {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      padding: 8px 0;
      border-bottom: 1px solid rgba(82, 104, 123, .25);
      font-size: 14px;
    }
    .seat {
      padding: 10px 0;
      border-bottom: 1px solid rgba(82, 104, 123, .25);
    }
    .seat strong {
      display: block;
      font-size: 15px;
    }
    .seat span {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }
    .turn { color: var(--gold); }
    .controls {
      display: grid;
      gap: 10px;
      margin-bottom: 18px;
    }
    button, select, input {
      width: 100%;
      border: 1px solid var(--line);
      background: #172535;
      color: var(--text);
      min-height: 38px;
      padding: 8px 10px;
      font: inherit;
    }
    button {
      cursor: pointer;
      font-weight: 700;
    }
    button.primary {
      background: #1c7a52;
      border-color: #35a673;
    }
    button.danger {
      background: #7c2430;
      border-color: #aa3a4a;
    }
    .grid2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .message {
      color: var(--gold);
      min-height: 18px;
      font-size: 13px;
    }
    @media (max-width: 920px) {
      main { grid-template-columns: 1fr; }
      aside { max-height: none; }
      .stage { min-height: auto; }
      .stage img { width: 100%; max-height: none; }
      header { align-items: flex-start; flex-direction: column; }
      .meta { flex-wrap: wrap; white-space: normal; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <h1 id="title">Texas Hold'em Table</h1>
      <div class="meta">
        <span class="pill" id="phase">Loading</span>
        <span class="pill" id="pot">Pot -</span>
        <span class="pill" id="updated">Connecting</span>
      </div>
    </header>
    <main>
      <section class="stage">
        <img id="tableImage" alt="Poker table">
      </section>
      <aside>
        <h2>Controls</h2>
        <div class="controls">
          <button class="primary" onclick="postAction('start')">Start Hand</button>
          <select id="actor"></select>
          <div class="grid2">
            <button onclick="postAction('check')">Check</button>
            <button onclick="postAction('call')">Call</button>
          </div>
          <div class="grid2">
            <button onclick="postAction('raise_to')">Raise To</button>
            <input id="raiseAmount" type="number" min="1" placeholder="Raise total">
          </div>
          <div class="grid2">
            <button onclick="postAction('all_in')">All-in</button>
            <button class="danger" onclick="postAction('fold')">Fold</button>
          </div>
          <div class="grid2">
            <select id="seatPlayer"></select>
            <input id="seatNumber" type="number" min="1" placeholder="Seat">
          </div>
          <button onclick="postSeatMove()">Move Seat</button>
          <div id="offlineControls">
            <input id="boardCards" placeholder="Board: Ah Kd Qs 7c 2h">
            <button onclick="postOfflineBoard()">Set Board</button>
            <select id="cardPlayer"></select>
            <input id="holeCards" placeholder="Player cards: As Ad">
            <button onclick="postOfflineCards()">Set Player Cards</button>
            <button onclick="postAction('showdown')">Showdown</button>
            <button onclick="postManualAward()">Manual Award To Selected Player</button>
          </div>
          <div id="message" class="message"></div>
        </div>
        <h2>Table</h2>
        <div id="facts"></div>
        <h2 style="margin-top:18px">Seats</h2>
        <div id="seats"></div>
        <h2 style="margin-top:18px">Last Result</h2>
        <div id="result" class="row">-</div>
      </aside>
    </main>
  </div>
  <script>
    const tableId = window.location.pathname.split('/').filter(Boolean).pop();
    const image = document.getElementById('tableImage');
    const phase = document.getElementById('phase');
    const pot = document.getElementById('pot');
    const updated = document.getElementById('updated');
    const facts = document.getElementById('facts');
    const seats = document.getElementById('seats');
    const result = document.getElementById('result');
    const title = document.getElementById('title');
    const actor = document.getElementById('actor');
    const seatPlayer = document.getElementById('seatPlayer');
    const cardPlayer = document.getElementById('cardPlayer');
    const message = document.getElementById('message');
    let latest = null;

    function text(value) {
      return value === null || value === undefined || value === '' ? '-' : String(value);
    }

    function render(data) {
      latest = data;
      title.textContent = `${data.mode.toUpperCase()} Texas Hold'em`;
      phase.textContent = `Phase ${data.phase}`;
      pot.textContent = `Pot ${data.pot}`;
      updated.textContent = `Updated ${new Date().toLocaleTimeString()}`;
      image.src = `/api/tables/${tableId}/image?v=${Date.now()}`;
      facts.innerHTML = `
        <div class="row"><span>Blinds</span><strong>${data.small_blind}/${data.big_blind}</strong></div>
        <div class="row"><span>Current bet</span><strong>${data.highest_bet}</strong></div>
        <div class="row"><span>Board</span><strong>${data.board.length ? data.board.join(' ') : '-'}</strong></div>
        <div class="row"><span>Turn</span><strong class="turn">${text(data.current_player_name)}</strong></div>
      `;
      seats.innerHTML = data.players.map(player => `
        <div class="seat">
          <strong>Seat ${player.seat}: ${player.name}</strong>
          <span>${player.chips} chips - bet ${player.bet} - committed ${player.committed}</span>
          <span>${player.roles.length ? player.roles.join(' / ') + ' - ' : ''}${player.folded ? 'folded' : player.all_in ? 'all-in' : 'active'}</span>
          <span>Cards: ${player.hole_cards.length ? player.hole_cards.join(' ') : player.offline_cards.length ? player.offline_cards.join(' ') : '-'}</span>
        </div>
      `).join('') || '<div class="row">No players seated</div>';
      result.textContent = data.last_result || '-';
      document.getElementById('offlineControls').style.display = data.mode === 'offline' ? 'grid' : 'none';
      updatePlayerSelects(data);
    }

    function updatePlayerSelects(data) {
      const options = data.players.map(player => `<option value="${player.user_id}">${player.seat}. ${player.name}</option>`).join('');
      for (const select of [actor, seatPlayer, cardPlayer]) {
        const old = select.value;
        select.innerHTML = options;
        if ([...select.options].some(option => option.value === old)) select.value = old;
      }
      if (data.current_user_id) actor.value = String(data.current_user_id);
    }

    async function request(path, payload = {}) {
      message.textContent = 'Working...';
      const response = await fetch(`/api/tables/${tableId}/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        message.textContent = data.error || 'Request failed';
        return;
      }
      message.textContent = data.message || 'Done';
      await refresh();
    }

    async function postAction(action) {
      const payload = { action, user_id: Number(actor.value) };
      if (action === 'raise_to') payload.amount = Number(document.getElementById('raiseAmount').value);
      await request('action', payload);
    }

    async function postSeatMove() {
      await request('seat/move', {
        user_id: Number(seatPlayer.value),
        seat: Number(document.getElementById('seatNumber').value),
      });
    }

    async function postOfflineBoard() {
      await request('offline/board', { cards: document.getElementById('boardCards').value });
    }

    async function postOfflineCards() {
      await request('offline/cards', {
        user_id: Number(cardPlayer.value),
        cards: document.getElementById('holeCards').value,
      });
    }

    async function postManualAward() {
      await request('award', { user_id: Number(actor.value) });
    }

    async function refresh() {
      try {
        const response = await fetch(`/api/tables/${tableId}`, { cache: 'no-store' });
        if (!response.ok) throw new Error(await response.text());
        render(await response.json());
      } catch (error) {
        updated.textContent = 'Disconnected';
        result.textContent = error.message;
      }
    }

    refresh();
    setInterval(refresh, 1500);
  </script>
</body>
</html>
"""


class PokerWebServer:
    def __init__(self, registry: TableRegistry, config: AppConfig) -> None:
        self.registry = registry
        self.config = config
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/", self.index)
        app.router.add_get("/healthz", self.healthz)
        app.router.add_get("/table/{table_id}", self.table_page)
        app.router.add_get("/api/tables", self.tables_api)
        app.router.add_get("/api/tables/{table_id}", self.table_api)
        app.router.add_get("/api/tables/{table_id}/image", self.table_image)
        app.router.add_post("/api/tables/{table_id}/action", self.table_action)
        app.router.add_post("/api/tables/{table_id}/seat/move", self.seat_move)
        app.router.add_post("/api/tables/{table_id}/offline/board", self.offline_board)
        app.router.add_post("/api/tables/{table_id}/offline/cards", self.offline_cards)
        app.router.add_post("/api/tables/{table_id}/award", self.award)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.config.web_host, self.config.web_port)
        await self.site.start()
        logger.info("Poker web server listening on %s:%s", self.config.web_host, self.config.web_port)

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()

    async def index(self, request: web.Request) -> web.Response:
        rows = [
            f'<li><a href="/table/{table.channel_id}">Table {table.channel_id} ({table.mode})</a></li>'
            for table in self.registry.tables()
        ]
        body = "<h1>Texas Hold'em Tables</h1><ul>" + "\n".join(rows) + "</ul>"
        return web.Response(text=f"<!doctype html><html><body>{body}</body></html>", content_type="text/html")

    async def healthz(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "tables": len(self.registry.tables())})

    async def table_page(self, request: web.Request) -> web.Response:
        return web.Response(text=HTML, content_type="text/html")

    async def tables_api(self, request: web.Request) -> web.Response:
        return web.json_response([table.snapshot() for table in self.registry.tables()])

    async def table_api(self, request: web.Request) -> web.Response:
        try:
            return web.json_response(serialize_public_table(self.registry, request.match_info["table_id"]))
        except ValueError as exc:
            raise web.HTTPNotFound(text=str(exc))

    async def table_image(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            return web.Response(body=render_table(table).getvalue(), content_type="image/png")
        except ValueError as exc:
            raise web.HTTPNotFound(text=str(exc))

    async def table_action(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            payload = await request.json()
            action = payload.get("action")
            if action == "start":
                table.start_hand()
                message = "Hand started."
            elif action == "showdown":
                table.finish_showdown()
                message = "Showdown resolved."
            else:
                user_id = int(payload["user_id"])
                amount = payload.get("amount")
                message = table.apply_action(
                    user_id,
                    Action(action),
                    int(amount) if amount not in (None, "") else None,
                )
            await self.registry.record_finished_hand_once(table)
            await self.registry.publish("web.action", table, action=action)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    async def seat_move(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            payload = await request.json()
            message = table.move_player_to_seat(int(payload["user_id"]), int(payload["seat"]))
            await self.registry.publish("web.seat_moved", table)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    async def offline_board(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            payload = await request.json()
            message = table.set_offline_board(str(payload.get("cards", "")))
            await self.registry.publish("web.offline_board", table)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    async def offline_cards(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            payload = await request.json()
            message = table.set_offline_cards(int(payload["user_id"]), str(payload.get("cards", "")))
            await self.registry.publish("web.offline_cards", table)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    async def award(self, request: web.Request) -> web.Response:
        try:
            table = self.registry.get_by_public_id(request.match_info["table_id"])
            payload = await request.json()
            message = table.manual_award([int(payload["user_id"])])
            await self.registry.record_finished_hand_once(table)
            await self.registry.publish("web.award", table)
            return web.json_response({"ok": True, "message": message})
        except Exception as exc:
            return self.error_response(exc)

    def error_response(self, exc: Exception) -> web.Response:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)


def table_url(config: AppConfig, table: object) -> str:
    channel_id = getattr(table, "channel_id")
    return f"{config.public_base_url}/table/{channel_id}"
