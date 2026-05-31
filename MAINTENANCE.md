# Maintenance Guide

这份文档说明以后怎么维护、扩展和验证项目。核心原则是：规则、Discord 控制层、外部牌桌 UI、统计和同步接口保持分层。

## 架构边界

Domain:

- `poker_bot/cards.py`
- `poker_bot/evaluator.py`
- `poker_bot/game.py`

这里放德州扑克规则，不 import `discord`、`aiohttp`、SQLite 或云平台相关代码。

Application:

- `poker_bot/app.py`
- `poker_bot/registry.py`
- `poker_bot/storage.py`
- `poker_bot/sync.py`
- `poker_bot/config.py`

这里负责运行时组装、live table 管理、统计和同步事件。

Adapters:

- `poker_bot/bot.py`
- `poker_bot/web_server.py`
- `poker_bot/table_renderer.py`

这里负责 Discord、外部网页和图片渲染。不要在 adapter 里实现德州扑克核心规则。

## 修改规则

改下注流程、行动顺序、边池、座位、摊牌：

1. 先在 `tests/test_poker_core.py` 增加规则测试。
2. 再改 `poker_bot/game.py`。
3. 跑完整测试。

改牌型判断：

1. 增加覆盖特定牌型的测试。
2. 改 `poker_bot/evaluator.py`。

改牌面输入：

1. 改 `poker_bot/cards.py`。
2. 更新 README 的牌面格式。

## 修改 Discord 指令

只改 `poker_bot/bot.py`。

常见位置：

- Slash commands: `PokerCog`
- 游戏按钮: `GameActionView`
- 开局/加入按钮: `LobbyView`
- Raise 输入框: `RaiseModal`

不要在按钮回调里直接写复杂规则。按钮应该调用 `PokerTable` 或 `TableRegistry`。

## 修改外部牌桌

页面结构和 API：

- `poker_bot/web_server.py`

牌桌图片样式：

- `poker_bot/table_renderer.py`

公开 API 必须遵守：

- 可以公开座位、筹码、下注、公共牌、状态、结果。
- 不可以公开线上模式玩家手牌。
- 私人手牌只能通过 Discord 私信发送给本人。

## 数据和状态

当前状态：

- live table: 内存
- stats: SQLite
- sync event: 可选 JSONL

生产约束：

- 单实例部署可以继续用当前结构。
- 多实例部署前，需要把 live table 状态迁移到 Redis/Postgres，或实现严格的同步后端。
- SQLite 数据库路径在云上应指向持久化磁盘，例如 `/data/poker_stats.sqlite3`。

## 环境变量

本地：

```env
DISCORD_TOKEN=...
POKER_DB_PATH=poker_stats.sqlite3
POKER_WEB_HOST=127.0.0.1
POKER_WEB_PORT=8765
POKER_PUBLIC_BASE_URL=http://127.0.0.1:8765
```

云上：

```env
DISCORD_TOKEN=...
POKER_PUBLIC_BASE_URL=https://你的真实公网域名
POKER_DB_PATH=/data/poker_stats.sqlite3
```

平台如果提供 `PORT`，程序会自动使用它。

## 验证命令

本地测试：

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python -m compileall poker_bot main.py tests
```

Bot import 检查：

```bash
.venv/bin/python -c "from poker_bot.app import create_runtime; from poker_bot.bot import create_bot; r=create_runtime(); create_bot(r); print('ok')"
```

Web smoke test 可参考测试中的 `PokerWebServer` 用法，至少验证：

- `/healthz`
- `/api/tables/<id>`
- `/api/tables/<id>/image`

Docker 验证：

```bash
docker build -t discord-poker-bot .
docker run --env-file .env -p 8765:8765 discord-poker-bot
```

## 发布检查清单

- `.env` 没有被提交。
- `.env.example` 只包含占位符。
- `DISCORD_TOKEN` 只存在于本地或云平台 secret。
- `POKER_PUBLIC_BASE_URL` 是真实 HTTPS 地址。
- `/healthz` 返回成功。
- Discord slash commands 已同步。
- `/poker_online_create` 和 `/poker_offline_create` 都能发出 `Open Table` 链接。
- 外部页面能打开并自动刷新。
- 线上模式手牌只通过私信发送。

## 已知限制

- 当前没有用户登录系统，外部页面是公开只读。
- live table 不是持久化状态。
- 当前不支持多实例。
- 当前不支持从外部网页直接操作下注。

这些限制都可以扩展，但需要先设计认证、共享状态和事件一致性。
