# Discord Texas Hold'em Bot

一个可部署到云上的德州扑克 Discord bot。Discord 只负责开桌、加入、下注和管理指令；真正的大牌桌在外部网页中展示，玩家点开 Discord 里的 `Open Table` 就能看到真实公网页面。

## 功能

- **线上模式**：bot 发牌、私信玩家手牌，Discord 按钮完成 `Check` / `Call` / `Raise` / `All-in` / `Fold`。
- **线下模式**：实体桌自己发牌，bot 负责记录下注、筹码、盲注、底池、摊牌判定和统计。
- **外部牌桌**：浏览器大屏显示座位、庄位、小盲/大盲、公共牌、底池、下注额和当前行动玩家。
- **座位管理**：支持移动座位和交换座位，保证德州扑克座位顺序清晰。
- **统计**：SQLite 记录玩家手数、胜/负/平和净筹码。
- **云部署**：Docker、`PORT`、`/healthz` 和公网链接配置已准备好。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：

```env
DISCORD_TOKEN=你的DiscordBotToken
POKER_DB_PATH=poker_stats.sqlite3
POKER_WEB_HOST=127.0.0.1
POKER_WEB_PORT=8765
POKER_PUBLIC_BASE_URL=http://127.0.0.1:8765
```

启动：

```bash
python main.py
```

浏览器健康检查：

```text
http://127.0.0.1:8765/healthz
```

云部署见 [DEPLOYMENT.md](DEPLOYMENT.md)，维护规范见 [MAINTENANCE.md](MAINTENANCE.md)。

## Discord 权限

在 Discord Developer Portal 创建 bot 并邀请到服务器。需要：

- `bot`
- `applications.commands`
- 发送消息
- 嵌入链接
- 使用 slash commands
- 线上模式需要能给玩家发私信

## 常用指令

线上模式：

- `/poker_online_create small_blind big_blind starting_chips`
- 点击 `Join`
- 用 `/poker_seat_move` 或 `/poker_seat_swap` 调整座位
- 点击 `Start Hand`
- 当前行动玩家用按钮操作
- `/poker_link` 获取外部牌桌链接

线下模式：

- `/poker_offline_create small_blind big_blind starting_chips`
- `/poker_join`
- `/poker_seat_move player seat`
- `/poker_seat_swap first_player second_player`
- `/poker_offline_start`
- `/poker_offline_action player action amount`
- `/poker_offline_board cards`
- `/poker_offline_cards player cards`
- `/poker_offline_showdown`
- `/poker_offline_award winner`

统计和状态：

- `/poker_status`
- `/poker_link`
- `/poker_stats`

## 牌面格式

使用 `Ah Kd Qs 7c 2h` 这种格式：

- `c`: clubs
- `d`: diamonds
- `h`: hearts
- `s`: spades

## 外部牌桌

bot 启动后会同时启动 web 服务：

- 页面：`/table/<Discord频道ID>`
- 公开状态 API：`/api/tables/<Discord频道ID>`
- 高清牌桌图：`/api/tables/<Discord频道ID>/image`
- 健康检查：`/healthz`

本地默认地址：

```text
http://127.0.0.1:8765
```

部署到云服务后，把 `POKER_PUBLIC_BASE_URL` 设置为真实 HTTPS 地址，Discord 里的 `Open Table` 会自动使用公网链接。

## 项目结构

- `main.py`：程序入口。
- `poker_bot/app.py`：组装配置、统计、牌桌注册表、web server 和 Discord bot。
- `poker_bot/bot.py`：Discord slash commands、buttons、modal。
- `poker_bot/web_server.py`：外部牌桌页面和公开 API。
- `poker_bot/table_renderer.py`：生成牌桌 PNG。
- `poker_bot/game.py`：德州扑克状态机。
- `poker_bot/evaluator.py`：牌型比较。
- `poker_bot/cards.py`：牌、牌组和牌面解析。
- `poker_bot/registry.py`：live table 管理和同步事件发布。
- `poker_bot/storage.py`：SQLite 统计。
- `poker_bot/sync.py`：同步后端接口。

## 当前边界

- live table 仍保存在内存里，服务重启后需要重新开桌。
- 统计保存在 SQLite；云上需要持久化磁盘。
- 外部页面是公开只读页面，玩家操作仍通过 Discord 完成。
- 公开 API 不包含线上玩家手牌。
- 建议生产环境只运行一个实例；多实例需要 Redis/Postgres 等共享状态。
