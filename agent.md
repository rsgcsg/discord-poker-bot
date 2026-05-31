# Agent Guide

This project is a Discord-launched Texas Hold'em web app. Discord should stay thin: it creates tables, launches the Activity, links to a table, and shows stats. Gameplay belongs in the web app and poker engine.

## Run And Verify

Use the repo venv when possible:

```bash
source .venv/bin/activate
python main.py
```

Fast checks before handing work back:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
PYTHONPYCACHEPREFIX=/private/tmp/discord_project_pycache .venv/bin/python -m compileall poker_bot main.py tests
.venv/bin/python -c "from poker_bot.app import create_runtime; from poker_bot.bot import create_bot; r=create_runtime(); create_bot(r); print('ok')"
git diff --check
```

If you change JavaScript embedded in `poker_bot/web_server.py`, also run a syntax check with Node if available.

## Boundaries

- `poker_bot/game.py`: poker rules and table state. Do not import Discord, aiohttp, SQLite, or cloud-provider code here.
- `poker_bot/evaluator.py` and `poker_bot/cards.py`: card parsing and hand evaluation.
- `poker_bot/registry.py`: owns live tables, table creation, pruning, sync publishing, and stats recording.
- `poker_bot/sync.py`: future multi-bot synchronization seam. Add Redis/WebSocket/queue backends here, not inside `PokerTable`.
- `poker_bot/storage.py`: durable hand statistics.
- `poker_bot/table_views.py`: API-safe table snapshots, including viewer-specific card visibility.
- `poker_bot/table_renderer.py`: rendered poker table scene. Prefer render objects over scattered drawing code.
- `poker_bot/web_server.py`: aiohttp routes, Activity pages, OAuth/session handling, and web actions.
- `poker_bot/bot.py`: Discord slash commands and Activity launch only.
- `poker_bot/urls.py`: public URL construction shared by bot and web code.
- `poker_bot/runtime_types.py`: Protocols for cross-layer dependencies.

## Design Rules

- Keep Discord commands out of gameplay flow. Do not add Discord `/call`, `/raise`, `/fold`, or DM-hand flows unless the product direction changes.
- The website is the source of player actions. The server remains the final authority; hiding a button in the UI is not validation.
- Online mode must only expose a viewer's own hole cards before showdown. Use `serialize_viewer_table()` for table pages.
- Offline mode may record external cards and chip movement, but should still route state changes through `PokerTable` and `TableRegistry`.
- Keep future bot synchronization behind `SyncBackend`; do not hard-code remote bot calls in commands or game rules.
- Prefer small data/config objects for UI and renderer changes. Avoid large hard-coded string templates or coordinate blocks when an object can describe the element.
- Python must remain friendly to Python 3.9 in slash-command import paths. Avoid Python 3.10-only annotations on `discord.app_commands` callbacks.

## Activity Notes

- The Activity lobby is `/`.
- Table pages are `/table/{table_id}`.
- Activity auth uses Embedded App SDK `authorize()` and `/api/token`; normal browser fallback uses `/login`.
- If Discord returns error `50231`, the Activity platform is not enabled for that client in Developer Portal.
- `POKER_PUBLIC_BASE_URL` must be the HTTPS public domain in deployment.

## Secrets

Never commit `.env`, bot tokens, OAuth secrets, session secrets, SQLite production data, or Railway/Fly credentials. If a Discord token appears in chat or logs, tell the user to rotate it.

## Extension Checklist

When adding a feature:

1. Put rules/state changes in `PokerTable`.
2. Add registry/sync publishing if other clients or future bots need to observe it.
3. Expose only safe data through `table_views.py`.
4. Add web route/API handling in `web_server.py`.
5. Add UI rendering as data-driven objects/config where possible.
6. Keep Discord changes limited to creating/opening/linking tables.
7. Add focused tests for any rule or serialization behavior.
