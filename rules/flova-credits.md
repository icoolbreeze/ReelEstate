# Flova 积分获取与账号管理

- 用户当次明确说「进行积分邀请」「积分邀请」「补积分」「邀请子号」「选号」「清号」「接班」时，先读本文件和 `config/flova-credits-policy.json`，再执行。
- 做片、地图重绘、`generate_image` 因积分失败时，不自动进入本文件的邀请或清号。把错误原文告诉用户。
- 邀请和注册只跑本仓库 `scripts/flova/`。不要运行其他仓库里的 `flova_invite.py`。派发报价仍不从其他仓库引入。

### 积分

- 个人账号之间不能转积分。邀请奖励只进当前母号。
- 邀请码、单次奖励额、名额上限、已邀人数以当次工具返回的 stats 为准，字段名见 policy 的 `invite.*_source`。不写死，不写进项目文件或 git。
- 余额用 MCP `account_info` 实时查，不写进文件。
- 不设固定保底。policy 已取消母号固定保底。
- 邀请奖励经验有效期 7 天（`invite.reward_validity_days`）。过期前优先消耗临期邀请分。
- 单次奖励经验值：stats 返回了 `credit_reward_num` 就用返回值；没返回时才用 200 估算。
- 新号立即可用注册积分约 `dispatch.signup_liquid_credits`（100）。注册当时实际到账为准。探索奖励一次性。

### 预算和邀请

用户给了本次需要的积分 `B` 就用 `B`。没给时先用 `account_info` 看母号余额；仍然不知道要补多少就问一个数字，问完再做。不要去其他仓库跑报价脚本。

- `B` 不超过新号立即可用注册积分：由新子号承担这次消费，不为这点差额去邀一串号。
- `B` 更大，且母号余额不够：母号付钱。邀请人数 = 向上取整( (`B` − 母号余额) / 单次奖励额 )。并行邀请（`invite.parallel=true`，`gap_sec=0`）。
- 剩余名额盖不住这个人数：不把旧母号最后的名额烧完，改接班人。没有合格接班人就停。
- 执行邀请运行 `python scripts/flova/flova_invite.py ensure --budget <B> --profile prod`。返回 `do_not_generate`、失败或停奖就立刻停，把原文告诉用户，不换路径继续邀。
- 自邀请和异常批量会被平台停奖。停奖就停。

### 选号

只在用户当次明确要求选号时使用。地图重绘的 profile 钉为当前活跃母号（`~/.flova/registry.json` 的 `active_mother_profile`；请求里已写明的非空 `params.profile` 沿用不换），任何已经写明的 `profile` 或已有 `project_id` 也钉死该号，不按下面的顺序换号。

顺序（`dispatch.rules`）：

1. pinned：钉死的号
2. first_image_bonus：还没领首次生图奖励的号
3. expiring_invite_credits：临期邀请分够付的最穷号
4. child_best_fit：余额够付的子号里最穷的
5. mother_fallback：母号兜底
6. invite_if_entire_pool_cannot_pay：全池都付不起才邀请

垫分 `dispatch.pad_credits` = 3。低于 `dispatch.min_credit_to_dispatch`（10）的余额不拿去派发。全池付不起才走上一节的邀请，不在做片流水线里自动走。

### 接班人

- 开始养的时点：已邀人数 ≥ 实时 max_invitees − `successor.max_invitees_minus`（减 7；max 为 20 时就是 13，开始养接班人的人数 = 实时 max_invitees − max_invitees_minus）。
- 合格条件同时满足：账龄满 `successor.required_account_age_days`（7 天）、成功导出过媒体（上传或草稿不算）、该号已经有自己的网页会话。资格信号以 `successor.signals_source`（stats 的 eligibility）为准。
- 轮换条件：`successor.rotate_when`，没有任何还能邀请的母号盖住 `B`。
- 没有合格接班人：停，告诉用户，不要烧旧母号剩余名额。

### 清号

只在用户当次明确要求清号时做。做片时不删号。

- 余额 0：当封号删除（`account.zero_means_banned`）。
- 余额低于 `account.min_keep_credits`（25）：删除。
- 读不到余额：不删。
- 删除用本机 `flova` CLI 的 profile 子命令。删完把默认 profile 设回 policy 的 `mother.default_profile`（`prod`），再查 `flova profile show` 和 `flova account user`。

### 账号

- `mother.default_profile` 当前是 `prod`。邀请/注册脚本结束时 CLI 默认是 `prod`。
- 显式 `profile` 或已有 `project_id` 钉死，不换号。
- 凭证只在 `~/.flova/credentials.yaml` 和浏览器配置目录。账本只记 profile 名，不记 token。不手改 YAML。token、cookie 不进对话、不进 git、不进命令行、不进项目文件。
- 用户当次明确要求加号时，只用本机 flova CLI：`profile add`、`auth login`，然后 `profile use prod`，再分别核对新号和默认号。这是本机程序，不是其他 git 仓库。
- 需要注册新子号时（用户当次说「注册」「注册子号」「邀请子号」且邮箱尚未注册 Flova），按 `rules/flova-register.md` 执行，入口是 `scripts/flova`：`ensure` / `invite_batch.py` 并行注册，`invite_manual.py` 一次一个。
- 母号和子号的网页会话都用各自 profile 的目录：`~/.flova-mcp/browser-profiles/<profile>`。不要把旧的 `~/.flova-mcp/browser-profile` 挪过来，也不要用旧母号的 cookie。会话是否在线用 MCP `web_status`。

### 和做片的分界

`npm run make`、`map:fetch`、装饰图生成不读本文件来自动选号、自动邀请或自动清号。地图底图重绘仍按 AGENTS.md §3E：profile 钉为当前活跃母号（`~/.flova/registry.json` 的 `active_mother_profile`；请求里已写明的非空 `params.profile` 沿用），不自动换号。
