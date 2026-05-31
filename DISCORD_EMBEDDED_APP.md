# Discord Embedded App Setup

目标：玩家在 Discord 里只接触一个 Poker App。Discord 负责开桌和启动 App；网站负责登录后入座和完整游戏流程；登录身份来自 Discord。

## 当前实现

- `/poker_online_create` 和 `/poker_offline_create` 创建牌桌。
- `/table/<table_id>` 是唯一牌桌 URL。
- `/` 是 Discord Activity lobby，会自动授权并列出当前 live tables。
- Activity 内自动使用 Embedded App SDK 登录。
- `/api/token` 给 Embedded App SDK 使用：前端拿到 SDK `authorize()` 返回的 code 后，交给服务端换取 access token，同时建立网站 session。
- `/assets/discord-sdk.mjs` 由服务端代理 Embedded App SDK，避免 Activity iframe 直接加载第三方脚本失败。
- 浏览器 fallback 仍可通过 `/login` 使用 Discord OAuth2 `identify` 登录。
- `/api/tables/<table_id>` 和 `/api/tables/<table_id>/image` 根据服务端 session 只显示当前玩家自己的手牌。
- `/api/tables/<table_id>/me/join` 和 `/api/tables/<table_id>/me/leave` 负责网站内入座/离座。
- `/poker_launch` 调用 Discord 的 `launch_activity` response，用于启动内嵌 Activity。

## Developer Portal

在同一个 Discord Application 里配置：

1. Bot 页面：复制并设置 `DISCORD_TOKEN`。
2. OAuth2 页面：复制 Application ID 到 `DISCORD_CLIENT_ID`。
3. OAuth2 页面：复制 Client Secret 到 `DISCORD_CLIENT_SECRET`。
4. OAuth2 Redirects：加入 `https://你的域名/oauth/callback`。
5. Installation / OAuth2 invite：包含 `bot` 和 `applications.commands` scopes。
6. Activities / Embedded App SDK：启用 Activity。
7. URL Mapping：指向你的公网域名，例如 `https://discord-poker-bot-production.up.railway.app`。

## Environment

```env
DISCORD_TOKEN=...
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_REDIRECT_URI=https://你的域名/oauth/callback
POKER_SESSION_SECRET=一串长随机字符串
POKER_PUBLIC_BASE_URL=https://你的域名
```

`DISCORD_REDIRECT_URI` 可以不填，默认就是 `POKER_PUBLIC_BASE_URL/oauth/callback`。
`POKER_SESSION_SECRET` 用来签名登录 cookie，云上建议固定设置，避免每次 redeploy 后玩家重新授权。

## Test Flow

1. 部署云服务。
2. 打开 `https://你的域名/healthz`，确认返回 `ok: true`。
3. Discord 中执行 `/poker_online_create`。
4. 玩家点击牌桌消息里的 `Open Poker App`，或执行 `/poker_launch` 启动内嵌 App。
5. Activity lobby 自动登录 Discord 并显示 live tables。
6. 玩家打开牌桌，在网站内点击 `Join This Table` 入座。
7. 入座后开始牌局，只有当前登录玩家能看到自己的手牌和合法动作。

## Notes

- 如果 `/poker_launch` 或 `Open Poker App` 报错，先确认 Developer Portal 已启用 Activities，并且当前 Discord 客户端/频道支持 Activity。
- 如果 OAuth 回调失败，检查 Redirect URI 是否和云平台域名完全一致。
- 当前 session 在单进程内存里；多实例部署前需要 Redis/Postgres session 和 live table 状态。
- 前端已接入 Discord Embedded App SDK 的 `authorize()` / `authenticate()`，并调用后端 `/api/token`。浏览器里不在 Activity 环境时会显示 OAuth fallback。
