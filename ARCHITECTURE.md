# Architecture Notes

项目目标：Discord 只负责创建牌桌、加入/离开牌桌和发链接，外部 web 页面负责完整游戏流程，核心德州扑克规则保持独立可测试。

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
- 外部牌桌页面和公开 API
- PNG 牌桌渲染

限制：

- 不在 adapter 里实现核心规则
- 当前网站是游戏控制台，会显示线上玩家手牌
- Discord command 只调用 domain/application 层

## Data Flow

1. Discord command 创建 table，并回复 `Open Table` 链接。
2. Discord Join/Leave button 只负责入座/离座。
3. 浏览器打开 `web_server.py` 的 `/table/<table_id>`。
4. 页面轮询 `/api/tables/<table_id>` 和 `/api/tables/<table_id>/image`。
5. 页面 POST 到 web API 来开始牌局、下注、调座位、录入线下牌面和摊牌。
6. `TableRegistry` 发布同步事件，必要时写入统计。

## Extension Points

多 bot 同步：

- 新增 `SyncBackend` 实现。
- 不要把同步逻辑放进 `game.py`。

私人玩家视角：

- 先设计认证和玩家身份绑定。
- 再把 web API 拆成 public table view 和 private player view。
- 私人 API 才能隐藏其他玩家手牌。

多实例部署：

- 当前不支持。
- 需要把 live table 状态迁移到 Redis/Postgres 或实现强一致事件流。

更多统计：

- 改 `storage.py`。
- 给 SQLite migration 留清晰路径。
- 更新 `/poker_stats` 展示。
