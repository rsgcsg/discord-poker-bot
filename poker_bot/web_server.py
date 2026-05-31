from __future__ import annotations

from aiohttp import web

from .config import AppConfig
from .registry import TableRegistry
from .table_renderer import render_table


def serialize_public_table(registry: TableRegistry, table_id: str) -> dict[str, object]:
    table = registry.get_by_public_id(table_id)
    data = table.snapshot()
    current = table.players.get(table.current_user_id) if table.current_user_id else None
    roles = table.seat_roles()
    data["current_player_name"] = current.name if current else None
    for player in data["players"]:
        player["roles"] = roles.get(player["user_id"], [])
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

    function text(value) {
      return value === null || value === undefined || value === '' ? '-' : String(value);
    }

    function render(data) {
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
        </div>
      `).join('') || '<div class="row">No players seated</div>';
      result.textContent = data.last_result || '-';
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
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.config.web_host, self.config.web_port)
        await self.site.start()

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


def table_url(config: AppConfig, table: object) -> str:
    channel_id = getattr(table, "channel_id")
    return f"{config.public_base_url}/table/{channel_id}"
