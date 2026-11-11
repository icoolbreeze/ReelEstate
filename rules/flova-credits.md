# Flova 积分获取与账号管理

- 用户当次明确说「进行积分邀请」「积分邀请」「补积分」「邀请子号」「选号」「清号」「接班」时，先读本文件和 `config/flova-credits-policy.json`，再执行。
- 做片、地图重绘、`generate_image` 因积分失败时，不自动进入本文件的邀请或清号。把错误原文告诉用户。
- 邀请和注册只跑本仓库 `scripts/flova/`。不要运行其他仓库里的 `flova_invite.py`。派发报价仍不从其他仓库引入。


## 图片账号分配（2026-10-26 用户新约定）

本节覆盖本文此前针对图片的“仅手动选号”和“默认钉活跃母号”约定；视频仍按原单账号流程。

- `generate_image` 不指定 `profile`、不复用旧 `project_id` 时，默认从现有 CLI 账号池选择能支付单张预算的账号。
- `count > 1` 拆成单张任务，优先使用本批次尚未使用的可用账号；每张图记录实际账号、项目和输出文件。单张图不能合并多个账号积分支付。
- 显式 `profile` 是账号固定指令；复用 `project_id` 必须提供归属账号，不跨账号移动项目。
- `account_mode: single` 可显式恢复单账号处理。`dry_run: true` 只查询余额和报价并返回分配计划，不上传、不创建项目、不生图、不邀请或注册。
- 账号忙或余额不够可在提交前换候选；已提交生成后失败则停止并报告，不能换号重复提交。部分成功时保留已经生成的文件。
- 各账号独立上传参考图并使用各自网页会话下载，不能混用项目或登录态。图片默认逐张执行，支持跨 MCP 进程的账号互斥，不承诺同账号并行。
- 图片预算不足不自动邀请、注册、删除或切换母号；实际扣费与预算校准继续分开记录，账号分配不修正未知来源的旧报价系数。
- 分配实现：`scripts/flova/image_dispatch.js`；本机 MCP 服务 `~/.flova-mcp/server.js` 调用该文件。报价使用本仓库 `scripts/flova/flova_pricing.py`，不调用其他仓库脚本。
- `node --test scripts/flova/test_image_dispatch.js` 验证分配、账号固定、单图支付、失败不重试、部分成功、dry-run、账号互斥等关键行为。

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

以下奖励、临期积分等手动选号顺序只在用户明确要求选号时使用。日常图片生成默认由 MCP 自动分配现有账号；新地图图片同样适用，不再自动填写活跃母号。已经明确写入的非空 `profile` 固定账号；已有 `project_id` 必须指定归属账号。

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
- 号池面板是 `npm run flova:pool`，只监听 `127.0.0.1`。启动只显示本地账本、CLI profile、网页目录的结构，不做任何探测（不开浏览器、不查积分和登录态）；「刷新母号」「全部刷新」手动触发，**任何有 profile 的卡片都始终显示单卡「刷新」**（旧的「检测」按钮改名为「刷新」，不再只在未检测或双端掉线时出现），单卡刷新只打 `POST /api/pool/refresh`（`scope:"one"`、`force:true`），只探测这一张卡（CLI/网页会话/积分/剩余邀请），不写 `registry.json`、不邀请、不清号、不换母号，仍走全局忙碌锁。探测结果（余额/登录态/邀请名额）保存在 `~/.flova-mcp/pool-probe-cache.json`，不按时间过期：启动直接沿用上次手动刷新的快照，一直显示到用户自己点「刷新」「刷新母号」或「全部刷新」，不写进 `registry.json`、不含邀请码/token；账本变化（加入/移出/补登）会使对应缓存失效。页面分五区：当前母号、号池账号、可加入号池、未检测、无效/休眠（折叠：已检测但读不到邮箱且 CLI/网页都掉登录）。余额和邀请码不写回账本，邀请码不出现在页面上。「录入已有账号」不再手填 profile 名：服务端自动取下一个未占用的 kidN（同时核对 CLI profile、网页目录、账本 api_key_ref/web_profile_ref 三处占用，不只看 CLI），再调仓库内 `scripts/flova/login_web.py --profile <名>`；「网页登录」与「补登录关联 profile」同样调它（`relink` 额外带账本邮箱 `--expect-email`，不一致即失败且不留半成品会话；补关联仍在页面 prompt 里给已有账本行指定名字），不再调用仓库外 `login-web.js`；该脚本用 `flova_invite.launch_worker` 同款随机指纹 Virtual Browser（无痕、`rotate=True`，固定 VB 不退回 AdsPower），人在窗口里自己登录，轮询 `_web_get_user_info` 成功后 `adopt_web_session` 把 cookie 收进 `~/.flova-mcp/browser-profiles/<名>`（不存账号密码、不写 token，stdout 只回 profile/ok/backend/fingerprint_rotated）。探测积分仍用现有无头 `web-session.js` 读**已采纳**的 cookie，那不是登录，不会每次探测都开 VB。登录成功后「录入」自动探测并入账；「补登录关联 profile」必须**登录邮箱与账本记录一致**才补写引用（防止登错号误关联）；profile 已属于别的账号时拒绝；账本里没有该邮箱时改用「录入已有账号」。未入账且能读到邮箱的行可以「加入号池」，号池里的子号可「移出号池」：只删除账本跟踪记录并先写一份 `registry.bak-remove-<时间戳>.json` 备份，不删 CLI key、不删网页会话目录，之后可重新加入；母号和已退休母号受保护不能移除（换号走交接班）。网页登录在线的号（含母号，已退休母号除外）都可「手动注册」（`invite_manual.py --profile <该号>`）和「手动邀请」（`invite_hand.py --profile <该号> [N]`）：二者都不校验停奖/满 7 天/导出记录/剩余名额，停奖或不满足条件时可能没有邀请奖励，按钮悬停提示会写明原因；区别是「手动邀请」脚本只开一个全新随机指纹无痕 VB 打开邀请链接，**不**自动填邮箱、不领邮箱池、不点 Continue，人用 Google 或邮箱自己完成注册（超时 15 分钟），成功后和手动注册一样 `adopt_web_session` → 换 token → `_add_cli_profile` → `_record_children` 自动入账（role=child、state=keyed），没拿到 token 的不写入，邀请码只在进程内拼链接、绝不打印。「自动邀请」（`invite_batch.py --profile <该号>`）仍只对 `invite_ready`（有剩余名额且资格齐全）的号开放，后端同样拦截。注册/邀请类进程退出后面板重新读结构行，新入账的号不用重启就出现（保持未探测，用户再点该卡「刷新」），不自动邀请或 prune。已探测、网页已登录但 CLI 未登录（如 `flova profile list` 没有该名、网页 cookie 仍有效）的卡显示「补 CLI」：走 `scripts/flova/repair_cli.py --profile <名>`，用**已采纳**的无头持久网页会话（不新开浏览器、不是新登录）调 `POST /api/agent/v2/token` 再 `_add_cli_profile`，成功后只更新该 profile 的账本行（`api_key_ref=flova-profile:<名>`、`state=keyed`、`last_verified`，不存余额、不动别的账号）并探测这一张卡；网页 `code!=0` 时失败并提示先做 VB 网页登录。移出号池在卡片上是垃圾桶图标按钮。「独立注册」走 `register_direct.py`，不带邀请码，浏览器仍是 Virtual Browser。省略 `--profile` 时邀请命令保持原来的邀请人。
- 母号和子号的网页会话都用各自 profile 的目录：`~/.flova-mcp/browser-profiles/<profile>`。不要把旧的 `~/.flova-mcp/browser-profile` 挪过来，也不要用旧母号的 cookie。会话是否在线用 MCP `web_status`。

### 和做片的分界

做片流程（地图底图重绘、装饰图生成）不自动邀请、注册或清号，也不打开号池面板。图片账号分配由 MCP 完成：新任务不默认钉母号，显式账号与已有项目的归属保持固定。2026-10-26 用户授权的新图片分配约定覆盖旧文档中的默认母号要求；AGENTS.md §3E 已于 2026-10-30 同步。

## 官方计费与本地报价（2026-10-26 修正）

报价依据官网“账户管理 → 价格详情 → 模型价格表”，数据源为 `https://config.flova.ai/config/model-list/read`。
官网前端将表中的 normal/member 值乘100显示为积分，本地使用相同换算，不再乘历史“经验系数”。
图片按对应模型、会员档位和分辨率的单张价格乘张数一次；不把历史批次余额差当作单张收费。
本次核对的 GPT Image 2.5 Flare：1K为5积分/张、2K为7积分/张、4K为15积分/张；价格可调整，以实时官网表为准，不在代码中固定这些费率。
旧 pricing_calibration.json 仅保留作诊断，不参与预算；不再允许 set-factor 修改报价。
余额变化只记为 observed_credits，真实 actual_credits 在没有平台对应任务扣费记录时保持未知。
偏差只提示核对到期、奖励、退款及对应任务，不自动抬高后续报价。读取不到有效官方报价时，图片和视频均不启动生成。
新报价/路由检查不会实际生图、调用邀请注册或产生生成扣费。
