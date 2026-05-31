# Website Poker Flow Specification

目标：Discord 只负责创建牌桌、加入/离开牌桌、发送链接和统计。网站负责完整牌局流程，并尽量接近真实德州扑克客户端的交互。

## 1. 视角

### Table View

URL:

```text
/table/<table_id>
```

用途：

- 公共桌面/观战/大屏。
- 显示座位、筹码、底池、公共牌、当前行动玩家、D/SB/BB。
- 不显示任何玩家手牌。
- 在 lobby 或一局结束后显示 `Start Hand` 和座位调整。
- 一局进行中不显示 `Check` / `Call` / `Raise` / `Fold` 等玩家动作。

### Player View

URL:

```text
/table/<table_id>/player/<user_id>?token=<secret>
```

用途：

- 玩家自己的操作页面。
- 只显示该玩家自己的手牌。
- 如果轮到该玩家，显示当前阶段允许的动作。
- 如果不是该玩家回合，只显示等待状态。
- token 由服务端生成，Discord Join 后用 ephemeral message 发给本人。

当前不是完整登录系统，但 token 至少避免普通桌面链接直接看到所有手牌。玩家不要转发自己的私人链接。

## 2. Lobby 阶段

允许：

- Discord 创建牌桌。
- Discord Join/Leave。
- 网站 Table View 调整座位。
- 网站 Table View 开始一局。

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

Player View 显示动作规则：

- 如果 `to_call == 0`：显示 `Check`、`Raise To`、`All-in`。
- 如果 `to_call > 0`：显示 `Call`、`Raise To`、`All-in`、`Fold`。
- 如果不是当前玩家回合：不显示动作按钮。
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

- Discord OAuth 登录。
- 绑定 Discord user id。
- 服务端 session。
- 玩家动作必须由登录身份匹配 user id。
