# Architecture Notes

项目目标：Discord 只负责创建牌桌、启动内嵌 App 和发单个牌桌链接，web 页面负责登录、入座和完整游戏流程，核心德州扑克规则保持独立可测试。

## Runtime

`main.py` 调用 `poker_bot/app.py`。

`app.py` 负责创建：

- `AppConfig`
- `StatsStore`
- `SyncBackend`
- `TableRegistry`
- `PokerWebServer`
- Discord `PokerBot`

这样 import `poker_bot.bot` 时不会自动启动 web server，也不会创建全局 bot 单例。

## Domain

文件：

- `poker_bot/cards.py`
- `poker_bot/evaluator.py`
- `poker_bot/game.py`

职责：

- 牌和牌组
- 牌型比较
- 德州扑克状态机
- 下注、边池、座位、摊牌

限制：

- 不 import `discord`
- 不 import `aiohttp`
- 不访问 SQLite
- 不读取环境变量

## Application

文件：

- `poker_bot/config.py`
- `poker_bot/registry.py`
- `poker_bot/storage.py`
- `poker_bot/sync.py`
- `poker_bot/app.py`

职责：

- 读取环境变量
- 管理 live tables
- 记录统计
- 发布同步事件
- 组装运行时依赖

## Adapters

文件：

- `poker_bot/bot.py`
- `poker_bot/web_server.py`
- `poker_bot/table_renderer.py`

职责：

- Discord slash commands 和 seating buttons
- 牌桌页面、Discord OAuth session 和 API
- PNG 牌桌渲染

限制：

- 不在 adapter 里实现核心规则
- 网站根据 Discord 登录 session 只显示当前玩家自己的手牌
- Discord command 只调用 domain/application 层

## Data Flow

1. Discord command 创建 table，并回复 `Open Table` 链接。
2. 玩家通过 `/poker_launch` 打开 Discord Activity，或点击牌桌链接。
3. Activity 内前端用 Embedded App SDK 自动认证；浏览器模式可走 `/login` fallback。
4. 玩家在网站内 `Join This Table` 入座。
5. 页面轮询 `/api/tables/<table_id>` 和 `/api/tables/<table_id>/image`；服务端用 session 决定是否显示自己的手牌。
6. 页面 POST 到 web API 来入座、开始牌局、下注、调座位、录入线下牌面和摊牌。
7. `TableRegistry` 发布同步事件，必要时写入统计。

## Extension Points

多 bot 同步：

- 新增 `SyncBackend` 实现。
- 不要把同步逻辑放进 `game.py`。

Discord 内嵌 App：

- `/poker_launch` 使用 Discord interaction 的 `launch_activity` response。
- Developer Portal 需要启用 Activities 并配置 URL Mapping 到公网域名。
- Activity 内使用 Embedded App SDK `authorize()` / `/api/token` / `authenticate()` 自动登录；普通浏览器保留 OAuth2 redirect fallback。

多实例部署：

- 当前不支持。
- 需要把 live table 状态迁移到 Redis/Postgres 或实现强一致事件流。

更多统计：

- 改 `storage.py`。
- 给 SQLite migration 留清晰路径。
- 更新 `/poker_stats` 展示。
