# Discord Texas Hold'em Bot

一个可部署到云上的德州扑克服务。Discord 只负责创建牌桌、加入/离开牌桌、启动内嵌 App、发送单个牌桌链接和查看统计；真正的开始牌局、下注、摊牌和线下记账流程都在网站中完成。玩家打开同一个网址后用 Discord 登录，服务端按 Discord user id 判断他能看到哪一手牌、能执行哪些动作。

## 功能

- **线上模式**：网站开始牌局、发牌、显示玩家手牌，网站按钮完成 `Check` / `Call` / `Raise` / `All-in` / `Fold`。
- **线下模式**：实体桌自己发牌，网站负责记录下注、筹码、盲注、底池、公共牌、玩家手牌、摊牌判定和统计。
- **单网址牌桌**：同一个 `/table/<table_id>` 同时服务观战、玩家操作和自己的手牌显示。
- **Discord 登录**：不再发私人 token 链接；玩家用 Discord OAuth 登录，只有自己的 Discord 账号能看到自己的手牌和行动按钮。
- **Discord 内嵌**：支持 `/poker_launch` 启动 Discord Activity，配置 Activity URL Mapping 后可以在 Discord 内打开网站。
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
# 可选：测试时填服务器ID，slash commands 会同步得更快
DISCORD_GUILD_ID=
DISCORD_CLIENT_ID=你的ApplicationID
DISCORD_CLIENT_SECRET=你的OAuth2ClientSecret
# 可选：默认是 POKER_PUBLIC_BASE_URL/oauth/callback
DISCORD_REDIRECT_URI=
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

云部署见 [DEPLOYMENT.md](DEPLOYMENT.md)，Discord 内嵌 App 配置见 [DISCORD_EMBEDDED_APP.md](DISCORD_EMBEDDED_APP.md)，维护规范见 [MAINTENANCE.md](MAINTENANCE.md)。

## Discord 权限

在 Discord Developer Portal 创建 bot 并邀请到服务器。需要：

- `bot`
- `applications.commands`
- 发送消息
- 嵌入链接
- 使用 slash commands

## 常用指令

线上模式：

- `/poker_online_create small_blind big_blind starting_chips`
- 点击 `Join` 入座
- 打开 `Open Table` 或使用 `/poker_launch` 打开内嵌 App
- 在网站里 `Log in with Discord`，然后开局、看自己的手牌、下注
- `/poker_link` 获取外部牌桌链接

线下模式：

- `/poker_offline_create small_blind big_blind starting_chips`
- `/poker_join`
- 打开 `Open Table`
- 在网站上调整座位、开始游戏、记录下注、录入公共牌/玩家手牌、摊牌或手动发奖

统计和状态：

- `/poker_link`
- `/poker_launch`
- `/poker_tables`
- `/poker_stats`

## 牌面格式

使用 `Ah Kd Qs 7c 2h` 这种格式：

- `c`: clubs
- `d`: diamonds
- `h`: hearts
- `s`: spades

## 外部牌桌

bot 启动后会同时启动 web 服务：

- 页面：`/table/<table_id>`
- 登录：`/login`
- OAuth 回调：`/oauth/callback`
- Embedded SDK token exchange：`/api/token`
- 状态 API：`/api/tables/<table_id>`，根据登录 session 自动决定是否显示自己的手牌
- 高清牌桌图：`/api/tables/<table_id>/image`
- 健康检查：`/healthz`

本地默认地址：

```text
http://127.0.0.1:8765
```

部署到云服务后，把 `POKER_PUBLIC_BASE_URL` 设置为真实 HTTPS 地址，Discord 里的 `Open Table` 会自动使用公网链接。然后在 Discord Developer Portal 的 OAuth2 Redirects 加入：

```text
https://你的域名/oauth/callback
```

每次创建牌桌都会生成新的 table id，所以同一个 Discord 频道可以同时开多个牌桌。

## 项目结构

- `main.py`：程序入口。
- `poker_bot/app.py`：组装配置、统计、牌桌注册表、web server 和 Discord bot。
- `poker_bot/bot.py`：Discord 创建/加入/离开/链接/统计指令。
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
- 未登录或未入座用户不能看手牌、不能操作。
- 登录 session 保存在内存中，服务重启后需要重新登录。
- 建议生产环境只运行一个实例；多实例需要 Redis/Postgres 等共享状态。
