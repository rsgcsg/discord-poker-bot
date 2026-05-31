# Architecture Notes

项目目标：Discord 只作为控制接口，外部 web 页面作为主视觉牌桌，核心德州扑克规则保持独立可测试。

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

- Discord slash commands、buttons、modal
- 外部牌桌页面和公开 API
- PNG 牌桌渲染

限制：

- 不在 adapter 里实现核心规则
- 公开 API 不输出线上玩家手牌
- Discord command 只调用 domain/application 层

## Data Flow

1. Discord command 或 button 触发 `PokerCog`。
2. `PokerCog` 调用 `TableRegistry` 或 `PokerTable`。
3. `TableRegistry` 发布同步事件，必要时写入统计。
4. Discord 回复轻量 embed 和 `Open Table` 链接。
5. 浏览器打开 `web_server.py` 的 `/table/<channel_id>`。
6. 页面轮询 `/api/tables/<channel_id>` 和 `/api/tables/<channel_id>/image`。

## Extension Points

多 bot 同步：

- 新增 `SyncBackend` 实现。
- 不要把同步逻辑放进 `game.py`。

外部网页操作：

- 先设计认证和玩家身份绑定。
- 再在 `web_server.py` 增加写接口。
- 写接口最终仍应调用 `PokerTable`。

多实例部署：

- 当前不支持。
- 需要把 live table 状态迁移到 Redis/Postgres 或实现强一致事件流。

更多统计：

- 改 `storage.py`。
- 给 SQLite migration 留清晰路径。
- 更新 `/poker_stats` 展示。
