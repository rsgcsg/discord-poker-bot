# Cloud Deployment

这个项目适合部署为一个长期运行的云服务：同一个进程同时运行 Discord bot 和 web 牌桌。部署完成后，Discord 消息里的 `Open Poker App` 会启动内嵌 Activity；`Browser Backup` 才是普通 HTTPS 网页链接。

## 推荐部署方式

优先选择支持 Docker 和持久化磁盘的平台：

- Railway
- Fly.io
- Render
- VPS + Docker

如果只是临时测试，也可以用 ngrok 或 Cloudflare Tunnel 暴露本机服务，但正式使用建议部署到云上。

## 必需环境变量

```env
DISCORD_TOKEN=你的DiscordBotToken
POKER_PUBLIC_BASE_URL=https://你的真实公网域名
POKER_DB_PATH=/data/poker_stats.sqlite3
DISCORD_CLIENT_ID=你的ApplicationID
DISCORD_CLIENT_SECRET=你的OAuth2ClientSecret
POKER_SESSION_SECRET=一串长随机字符串
```

`DISCORD_TOKEN` 只填 Bot 页面的 token 本体，不要加引号，不要加 `Bot ` 前缀。如果日志出现 `Improper token has been passed` 或 `401 Unauthorized`，说明云平台里的 token 无效或已被重置，需要重新复制 token 并 redeploy。

可选环境变量：

```env
DISCORD_GUILD_ID=
POKER_SYNC_EVENT_LOG=
DISCORD_REDIRECT_URI=https://你的真实公网域名/oauth/callback
```

如果你刚部署后 Discord 里看不到 `/poker_online_create`，建议临时设置 `DISCORD_GUILD_ID` 为你的测试服务器 ID。这样 slash commands 会同步到该服务器，通常比全局命令更快可见。

很多云平台会自动提供 `PORT`。程序会优先读取 `PORT`，并在云平台环境下自动监听 `0.0.0.0`。Railway 上不要设置 `POKER_WEB_HOST=127.0.0.1`，否则公网入口无法访问容器内服务。通常也不用手动设置 `POKER_WEB_PORT`。

## Docker 本地验证

```bash
docker build -t discord-poker-bot .
docker run --env-file .env -p 8765:8765 discord-poker-bot
```

检查：

```text
http://127.0.0.1:8765/healthz
```

返回类似下面内容表示 web 服务正常：

```json
{"ok": true, "tables": 0}
```

## 通用云平台配置

Build:

```text
Dockerfile
```

Start command:

```text
留空，Dockerfile 已经执行 python main.py
```

Health check path:

```text
/healthz
```

Environment variables:

```env
DISCORD_TOKEN=...
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
POKER_SESSION_SECRET=...
DISCORD_GUILD_ID=你的测试服务器ID
POKER_PUBLIC_BASE_URL=https://你的云平台域名
POKER_DB_PATH=/data/poker_stats.sqlite3
```

Railway/Render/Fly 这类平台通常不要设置：

```env
POKER_WEB_HOST
POKER_WEB_PORT
```

让平台提供的 `PORT` 生效即可。

Persistent disk:

```text
Mount path: /data
```

## 平台提示

Railway:

- 新建 service，选择 GitHub repo 或 Dockerfile。
- 设置 `DISCORD_TOKEN`、`DISCORD_CLIENT_ID`、`DISCORD_CLIENT_SECRET`、`POKER_SESSION_SECRET` 和 `POKER_PUBLIC_BASE_URL`。
- 如果要保留统计，添加 volume 并挂载到 `/data`。

Fly.io:

- 使用 Dockerfile 部署。
- 设置 secret：`fly secrets set DISCORD_TOKEN=... DISCORD_CLIENT_ID=... DISCORD_CLIENT_SECRET=... POKER_SESSION_SECRET=... POKER_PUBLIC_BASE_URL=https://...`
- 给 `/data` 配置 volume。

Render:

- 创建 Web Service。
- Environment 选择 Docker。
- Health check path 填 `/healthz`。
- 使用 persistent disk 保存 SQLite。

VPS + Docker:

```bash
docker build -t discord-poker-bot .
docker run -d \
  --name discord-poker-bot \
  --restart unless-stopped \
  -p 8765:8765 \
  -e DISCORD_TOKEN=... \
  -e DISCORD_CLIENT_ID=... \
  -e DISCORD_CLIENT_SECRET=... \
  -e POKER_SESSION_SECRET=... \
  -e POKER_PUBLIC_BASE_URL=https://你的域名 \
  -e POKER_DB_PATH=/data/poker_stats.sqlite3 \
  -v poker-data:/data \
  discord-poker-bot
```

如果用 Nginx/Caddy 反向代理，把 HTTPS 域名转发到容器的 `8765` 或平台分配的端口。

## Discord Developer Portal

部署后确认：

- Bot token 设置到了云平台环境变量。
- OAuth2 Client ID 和 Client Secret 设置到了云平台环境变量。
- `POKER_SESSION_SECRET` 设置到了云平台环境变量。
- OAuth2 Redirects 包含 `https://你的域名/oauth/callback`。
- token 来自 `Bot` 页面，不是 Application ID、Client Secret 或 Public Key。
- 邀请链接包含 `bot` 和 `applications.commands` scope。
- Bot 有发送消息、嵌入链接、使用 slash command 的权限。

## Discord 内嵌 App

如果要让网站在 Discord 内作为 Activity 打开：

1. 进入 Discord Developer Portal 的同一个 Application。
2. 打开 Activities / Embedded App SDK 设置。
3. 启用 Activity。
4. URL Mapping 指向你的公网域名，例如 `https://discord-poker-bot-production.up.railway.app`。
5. 确保 OAuth2 Redirects 仍然包含 `https://你的域名/oauth/callback`。
6. 重新部署并同步 slash commands。
7. 在 Discord 里使用 `/poker_launch`，或点击牌桌消息里的 `Open Poker App`，它会调用 Discord 的 Activity launch response。

如果 `/poker_launch` 或 `Open Poker App` 报错，通常是这个 Application 还没有启用 Activities，或者当前频道/客户端不支持启动 Activity。此时仍可用 `Browser Backup` 单网址方式测试完整游戏流程。

## 生产注意事项

- 不要把 `.env` 提交到仓库。
- 如果 token 曾经泄漏，立即在 Discord Developer Portal 重置。
- 当前 live table 在内存中，服务重启会清空当前牌桌。
- SQLite 只适合单实例部署；多实例需要共享状态和数据库迁移。
- 网站动作需要 Discord 登录；未入座用户不能看自己的手牌或操作。
- session 使用签名 cookie；如果没有固定 `POKER_SESSION_SECRET`，换 token 或 secret 后玩家需要重新登录。
- 部署多个实例前，需要先设计 Redis/Postgres 状态层。
