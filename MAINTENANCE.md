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
- 入座按钮: `SeatingView`

不要在 Discord 回调里直接写复杂规则。Discord 只负责创建、启动 Activity、链接和统计；入座、离座和游戏流程在网站里处理。

## 修改外部牌桌

页面结构和 API：

- `poker_bot/web_server.py`

牌桌图片样式：

- `poker_bot/table_renderer.py`

当前网站是主游戏界面：

- 可以公开座位、筹码、下注、公共牌、状态、结果。
- 公共桌面不能显示线上模式玩家手牌。
- 单个牌桌 URL 通过 Discord Activity SDK 或 OAuth session 判断登录玩家。
- 已入座玩家只看到自己的手牌；未登录或未入座用户不能操作。

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
DISCORD_GUILD_ID=
POKER_DB_PATH=poker_stats.sqlite3
POKER_WEB_HOST=127.0.0.1
POKER_WEB_PORT=8765
POKER_PUBLIC_BASE_URL=http://127.0.0.1:8765
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
```

云上：

```env
DISCORD_TOKEN=...
DISCORD_GUILD_ID=你的测试服务器ID
POKER_PUBLIC_BASE_URL=https://你的真实公网域名
POKER_DB_PATH=/data/poker_stats.sqlite3
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
```

平台如果提供 `PORT`，程序会自动使用它。

云平台注意：

- 当 `PORT` 存在时，程序会强制监听 `0.0.0.0`。
- Railway/Render/Fly 上通常不要设置 `POKER_WEB_HOST` 或 `POKER_WEB_PORT`。
- 如果公网域名打不开但 Discord bot 已连接，优先检查是否错误设置了 `POKER_WEB_HOST=127.0.0.1`。
- 如果 slash commands 看不到，临时设置 `DISCORD_GUILD_ID` 到测试服务器 ID，让命令同步到单个服务器。

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
- `/api/token` 用于 Activity SDK code exchange
- `/login` 会跳转到 Discord OAuth 授权页

Docker 验证：

```bash
docker build -t discord-poker-bot .
docker run --env-file .env -p 8765:8765 discord-poker-bot
```

## 发布检查清单

- `.env` 没有被提交。
- `.env.example` 只包含占位符。
- `DISCORD_TOKEN` 只存在于本地或云平台 secret。
- `DISCORD_TOKEN` 是 Bot token 本体，不带引号、不带 `Bot ` 前缀。
- `POKER_PUBLIC_BASE_URL` 是真实 HTTPS 地址。
- Discord Developer Portal 的 OAuth2 Redirects 包含 `https://你的域名/oauth/callback`。
- 云平台设置了 `DISCORD_CLIENT_ID` 和 `DISCORD_CLIENT_SECRET`。
- `/healthz` 返回成功。
- Discord slash commands 已同步。
- `/poker_online_create` 和 `/poker_offline_create` 都能发出 `Open Table` 链接。
- `/poker_launch` 在启用 Activities 后能启动 Discord 内嵌 App。
- Discord 内没有 `Call` / `Raise` / `Fold` / `Start Hand` 流程按钮。
- 外部页面能打开并自动刷新。
- 入座玩家登录 Discord 后只能看到自己的手牌。
- 外部页面能开始牌局并执行下注动作。

## 常见故障

`discord.errors.LoginFailure: Improper token has been passed`

- 云平台里的 `DISCORD_TOKEN` 不是有效 bot token。
- 去 Discord Developer Portal 的 Bot 页面 reset/copy token。
- 更新云平台环境变量并重新部署。
- 不要使用 Application ID、Client Secret、Public Key。
- 不要给 token 加 `Bot ` 前缀。

`Privileged message content intent is missing`

- 当前项目主要使用 slash commands，这个 warning 通常不是启动失败原因。
- 真正导致退出的错误一般会在 warning 后面的 traceback 里。

公网网址打不开，但日志显示 Discord gateway connected

- Discord token 已经正常。
- 检查云平台是否有 Public Networking/Domain。
- 检查 `POKER_PUBLIC_BASE_URL` 是否是该域名。
- 检查是否设置了 `POKER_WEB_HOST=127.0.0.1`；云上应该删除这个变量或让程序使用 `0.0.0.0`。

## 已知限制

- 登录 session 存在当前进程内存，服务重启会失效。
- live table 不是持久化状态。
- 当前不支持多实例。

这些限制都可以扩展，但需要先设计 Redis/Postgres 状态层、session 持久化和事件一致性。
