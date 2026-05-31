# Website Poker Flow Specification

目标：Discord 只负责创建牌桌、加入/离开牌桌、启动内嵌 App、发送单个链接和统计。网站负责完整牌局流程，并尽量接近真实德州扑克客户端的交互。

## 1. 视角

### Single Table URL

URL:

```text
/table/<table_id>
```

用途：

- 公共桌面、观战、大屏和玩家操作都使用同一个 URL。
- 显示座位、筹码、底池、公共牌、当前行动玩家、D/SB/BB。
- 未登录或未入座时不显示任何玩家手牌，也不显示操作按钮。
- 登录 Discord 且已经从 Discord 入座后，只显示该登录玩家自己的手牌。
- 在 lobby 或一局结束后，已入座玩家可以 `Start Hand` 和移动自己的座位。
- 一局进行中，只给当前行动玩家显示当前合法动作。

### Discord Login

URL:

```text
/login
/oauth/callback
```

用途：

- 通过 Discord OAuth2 `identify` scope 取得 Discord user id。
- 服务端建立 `poker_session` cookie。
- 后续 `/api/tables/<table_id>` 和 `/api/tables/<table_id>/image` 自动按 session 决定可见信息。
- 不再使用私人 token 链接。

## 2. Lobby 阶段

允许：

- Discord 创建牌桌。
- Discord Join/Leave。
- 网站里已登录、已入座玩家移动自己的座位。
- 网站里已登录、已入座玩家开始一局。

不允许：

- 玩家动作。
- 看手牌。

开始一局前校验：

- 至少 2 个有筹码玩家。
- 当前没有手牌正在进行。
- 桌子没有被超时关闭或游戏结束。

## 3. 手牌进行中

阶段：

```text
preflop -> flop -> turn -> river -> showdown/finished
```

网站显示动作规则：

- 如果 `to_call == 0`：显示 `Check`、`Raise To`、`All-in`。
- 如果 `to_call > 0`：显示 `Call`、`Raise To`、`All-in`、`Fold`。
- 如果不是当前登录玩家回合：不显示动作按钮。
- 如果玩家 folded/all-in/chips=0：不显示动作按钮。

服务端仍然是最终裁判。前端隐藏按钮只是用户体验，非法动作必须由 `PokerTable.apply_action()` 拒绝。

## 4. 结束与结算

一局结束条件：

- 所有人 fold 到只剩 1 人。
- river 后摊牌。
- 所有未弃牌玩家 all-in，自动发完公共牌并摊牌。

一局结束后：

- 显示结算文字。
- 显示玩家筹码变化。
- 如果至少 2 个玩家还有筹码，显示 `Start Next Hand`。
- 如果不足 2 个玩家还有筹码，进入 game over，不允许继续开局。

## 5. 超时和资源限制

当前实现的基础规则：

- 一手牌开始后记录最后动作时间。
- 如果超过 `hand_timeout_seconds` 没有动作，牌局自动停止，回到 finished 状态，并显示超时原因。
- 如果牌桌没有足够有筹码玩家，不允许开新局。
- 同一桌同时只能有一手牌运行。

后续可扩展：

- 超时后自动 fold 当前玩家。
- 桌子长期无人操作自动归档。
- 持久化 live table 到 Redis/Postgres。

## 6. Discord 边界

Discord 只保留：

- 创建线上桌。
- 创建线下桌。
- Join。
- Leave。
- 获取链接。
- 列出牌桌。
- 查看统计。

Discord 不做：

- Start Hand。
- Check / Call / Raise / Fold / All-in。
- 线下录牌。
- 摊牌。
- 私信手牌图片。

## 7. 安全边界

当前 token 链接不是完整账号登录。它能避免公开桌面直接看到所有牌，但如果玩家把自己的链接转发出去，别人仍然可以代操作。

生产级防作弊下一步：

已实现：

- Discord OAuth 登录。
- 绑定 Discord user id。
- 服务端 session。
- 玩家动作必须由登录身份匹配 user id。

后续生产增强：

- session 持久化到 Redis。
- CSRF token。
- 管理员/房主权限。
- Discord Embedded App SDK 前端鉴权，减少浏览器跳转。
