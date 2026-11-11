# Flova 子号注册与激活

用户当次明确说「注册」「注册子号」「邀请子号」「进行积分邀请」「补积分」时才执行。做片、地图重绘、生图失败都不自动注册。

权威实现是本仓库 `scripts/flova/`（与 GrokVG 的 `flova_invite.py` / `invite_batch.py` / `invite_manual.py` 同一套）。不要再去跑其他 git 仓库里的同名脚本。`flova_register.py` 不是注册流程。

token、cookie、验证码不进对话、不进 git、不进项目文件。不手改 `credentials.yaml` 或 `config.yaml`。

## 入口

在仓库根目录执行。`prod` 在脚本里是默认档：`resolve_inviter` 会把它解析成 `~/.flova/registry.json` 的 `active_mother_profile`，没有则用 `config/flova-credits-policy.json` 的 `mother.default_profile`（`prod`）。

```text
python scripts/flova/flova_invite.py plan --budget <B> --profile prod
python scripts/flova/flova_invite.py ensure --budget <B> --profile prod
python scripts/flova/flova_invite.py candidates
python scripts/flova/flova_invite.py prune
python scripts/flova/flova_invite.py repair-web --profile <子号名>
python scripts/flova/invite_batch.py <N>
python scripts/flova/invite_batch.py --profile <profile> <N>
python scripts/flova/invite_manual.py <N>
python scripts/flova/invite_manual.py --profile <profile> <N>
python scripts/flova/invite_hand.py <N>
python scripts/flova/invite_hand.py --profile <profile> <N>
python scripts/flova/login_web.py --profile <name> [--expect-email <email>]
python scripts/flova/repair_cli.py --profile <name>
python scripts/flova/register_direct.py
npm run flova:pool
```

- `ensure`：先清低分号，再按预算并行注册。`B <= signup_liquid_credits`（100）时新子号付款，注册 1 个。`B` 更大时母号付款，人数 = 向上取整( (`B` − 母号余额) / 当次 `credit_reward_num` )。名额盖不住就切合格接班人，不烧旧母号最后名额。没有接班人则 `do_not_generate=true`，立刻停。
- `invite_batch.py`：并行注册固定 N 个。邮箱额外排除 `registration.signals.flova_verification_seen`。邀请码只预热一次并缓存，并行线程不再各自打开母号网页会话。写出 `--profile` 时，邀请人就是这个 profile，奖励进这个号；省略时仍是原来的 `mother_profile="prod"`。
- `invite_manual.py`：顺序注册，一次一个，方便人工处理验证。滑动验证（阿里云拼图）`#aliyunCaptcha-mask` 出现后最多等 900 秒，等人滑完再继续，不要自动拖滑块，不要刷新。复选框验证（Turnstile）出现且还没有 `cf-turnstile-response` 时自动刷新页面，刷新后重新打开邮箱面板并重填邮箱，最多刷新 3 次，不点击复选框。两种验证同时出现时先等用户滑完滑块。写出 `--profile` 时邀请人就是这个 profile；省略时仍用账本里的活跃母号。
- `invite_hand.py`：**手动邀请**。用法和 `invite_manual.py` 相同（省略 `--profile` 用活跃母号，`cli_invocation()` 形状一致），但脚本每个名额只开一个全新随机指纹的无痕 Virtual Browser（`launch_worker`，`rotate=True`）打开邀请链接 `https://www.flova.ai/?refCode=<code>`，**不**自动填邮箱、不领邮箱池、不点 Continue；人在窗口里用 Google 或邮箱自己完成注册，脚本轮询直到读到已登录且邮箱不是邀请人本人的用户（超时 15 分钟）。邀请码只在进程内拼链接，**绝不打印**。成功后和 `invite_manual.register_one` 相同收尾：`adopt_web_session`（带 `expected_email`）→ `POST /api/agent/v2/token` → `_add_cli_profile` → `next_child_profiles` 预分配 profile 名；N 个串行、同一 worker id 不并发、持有 `flova_invite._Lock`。全部结束后 `_record_children`：拿到 token 的新号自动入账（role=child、state=keyed、api_key_ref、web_profile_ref），没拿到 token 的不写入。号池面板上「手动邀请」与「手动注册」并列，共用人数输入框，后端校验与手动注册相同（不要求 `invite_ready`）。
- `login_web.py`：号池面板「网页登录」「录入已有账号」「补登录关联 profile」的统一入口，替代直接调仓库外 `login-web.js`（那个脚本用系统 Chrome/Edge 持久目录、不换指纹；本脚本不改它，探测积分仍读它已采纳的 cookie）。用随机指纹 Virtual Browser（`vb_backend.launch_worker`，无痕 `incognito=True`、`rotate=True`，固定 VB 不退回 AdsPower、不读 `FLOVA_BROWSER_BACKEND`）打开 `https://www.flova.ai/en/generator/`，人自己登录，轮询 `flova_invite._web_get_user_info`（code==0 且有邮箱为成功，最多 5 分钟），成功后 `adopt_web_session` 收 cookie 进 `~/.flova-mcp/browser-profiles/<profile>` 再 `stop_worker`。`--expect-email` 给值时邮箱不一致即失败，`adopt_web_session` 会清空已导入 cookie，不留半成品。stdout 最终只打印一行 JSON：`profile` / `ok` / `backend:"vb"` / `fingerprint_rotated`；邮箱、token、cookie、邀请码一律不打印，异常先经 `pool_status.redact` 打码再进 stderr。
- `repair_cli.py`：CLI 掉线但网页仍在线（如 kid6，只是例子不写死）：`flova profile list` 里没有该名，而 `~/.flova-mcp/browser-profiles/<名>` 的已采纳 cookie 仍能 `get_user_info` code==0。这是**读旧会话**，不是新登录：系统 Chrome/Edge 无头持久上下文（与 `adopt_web_session` 同目录布局，headless），不开可见浏览器、不调 `flova auth login` 的默认开浏览器模式；网页 `code!=0` 时失败并提示先跑 `login_web.py` 做 VB 网页登录。拿到 token 后调现有 `flova_invite._add_cli_profile`（内部 profile add + auth login --token + 默认切回 prod），token 不打印、不写仓库、异常先打码再抛。成功后用 `load_registry` / `save_registry` **只更新该 profile 的账本行**：`api_key_ref=flova-profile:<名>`、`state=keyed`、`last_verified`，不改别的账号、不存余额。号池面板对已探测、`web_logged_in`、`!cli_logged_in`、有 profile 的卡显示「补 CLI」，任务完成后探测这一张卡并刷新结构。
- `register_direct.py`：打开 `https://www.flova.ai/`，不带 `refCode`。浏览器仍是 Virtual Browser。
- **窗口默认不弹出**：所有走 `flova_invite.launch_worker` 的注册/邀请（`ensure`、`invite_batch`、`invite_manual`、`invite_hand`、`register_direct`、`repair-web`）在 VB 后端下启动后立即把窗口最小化到任务栏（`FLOVA_VB_WINDOW=minimized`，默认），不弹窗、不抢焦点；内核带防节流参数，后台窗口里 Turnstile 等 JS 挑战照常跑。出现阿里云滑块时 `invite_manual.settle_captcha` 自动把窗口恢复到前台等人工；`invite_hand` 的窗口也最小化，提示自己点任务栏图标开始注册。恢复旧行为设 `FLOVA_VB_WINDOW=normal`。AdsPower 回退与 `login_web.py` 不受影响。
- `npm run flova:pool`：本机号池页面。打开后逐个查登录、积分和剩余邀请次数。未入账且读得到邮箱可以加入号池。可邀请的行才能点自动邀请；网页登录在线、非已退休母号的行可点手动注册或手动邀请（不要求 `invite_ready`）；任何有 profile 的卡始终可点单卡「刷新」（只探测这一张）；网页在线、CLI 掉线的已探测卡可点「补 CLI」。网页登录/录入/补关联都由后端拼 `login_web.py` 命令（`relink` 带 `--expect-email`）。号池账号里已检测但 CLI、网页都掉线的卡折叠进「非可用账号」组（默认收起，计数在标题里；展开后按钮照常，可刷新、补 CLI、网页登录、移出号池）。注册/邀请类任务退出后自动重读结构行，新入账的号立即出现（保持未探测）。做片流程不打开这个页面。
- `repair-web`：不邀新、不删号。已采纳到 `~/.flova-mcp/browser-profiles` 的不再打开浏览器。仍指向旧虚拟浏览器目录（`virtualbrowser-worker:` / `virtualbrowser-dir:`）且有 `mailbox_ref` 的，复用后端池里的一个 worker（默认 VB，串行、无痕、按国家轮换指纹；`FLOVA_BROWSER_BACKEND=adspower` 时用 AdsPower 池里一个已有 profile）做一次邮箱 OTP 登录后采纳；没有邮箱则跳过（reason `legacy_virtualbrowser_profile`）。不启动旧虚拟浏览器，也不创建或删除任何 worker/profile/目录。

`FLOVA_AUTO_INVITE=0` 时 `ensure` 直接返回 `do_not_generate`，不注册。

## 脚本里的注册步骤

`invite_one` 对每个号做这些事。Agent 不要平行再手点一遍。

1. 邮箱：`GET http://119.29.187.184:18793/v1/mailboxes?provider=outlook&active=1`。要活跃、未过期、`registration.flova.registered != true`、不在账本里。`invite_batch.py` 还排除收过 Flova 验证码的邮箱。挑选顺序：没有导入时间的是最早一批，最先消费；有导入时间的按 `imported_at` 从早到晚（先导入先注册）；同档按地址小写升序。
2. 浏览器后端默认是 **Virtual Browser（VB）**，免费版 2.2.16（内核 Chromium 146.0.7680.72），无需 VIP/扩展/本地 HTTP API，也没有 AdsPower 免费版「每日打开次数」限额。机制与排错以 `docs/virtual-browser-backend.md` 为准，正式实现是 `scripts/flova/vb_backend.py` + `scripts/flova/vb_fingerprint.py`。
   - 后端开关：`FLOVA_BROWSER_BACKEND=vb`（默认）或 `adspower`（回退，代码保留）。国家/出口：`FLOVA_VB_COUNTRY=us`（默认）|`jp`，据此选代理端口、语言、指纹、时区，三者必须一致。worker 池：`FLOVA_VB_WORKER_IDS`（默认 `100,101`，即 `%LOCALAPPDATA%\VirtualBrowser\Workers\100|101`）；内核路径可用 `FLOVA_VB_KERNEL` 覆盖（换版本时）。
   - 指纹：内核启动带 `--worker-id=<id>` 且 `--user-data-dir=Workers\<id>` 里有 `virtual.dat`（含同 id 的 user）时生效；内核每次启动重读、无缓存。每次启动前 `vb_fingerprint` 都按目标国家**重写该 worker 的 `virtual.dat`（全新随机、自洽：CPU/GPU/screen/canvas/audio/字体/MAC/设备名/时区）**，等价于「每次启动一套新指纹」。只写 `Workers\<id>\virtual.dat`，不碰 GUI 全局 `User Data\virtual.dat`，自动化时尽量关着 GUI。
   - 启动命令：`VirtualBrowser.exe --user-data-dir=Workers\<id> --worker-id=<id> --no-first-run --no-default-browser-check --remote-debugging-port=<free> --remote-allow-origins=* --proxy-server=<proxy> --lang=<lang> --accept-lang=<...> --incognito`，Playwright 经 `http://127.0.0.1:<port>` `connect_over_cdp`，取 `contexts[0]`。注册一律 `--incognito`：指纹全保留、localStorage 不复用，会话干净。
   - 代理/语言/时区（自洽）：美国 `--proxy-server=http://127.0.0.1:7898`（mihomo 美 4 日 4、美国优先）+ `--lang=en-US`，指纹时区 `America/New_York`；日本 `http://127.0.0.1:7899`（日本专线）+ `--lang=ja-JP --accept-lang=ja-JP,ja,en-US,en`，指纹时区 `Asia/Tokyo`。内核不按 IP 改语言，语言必须用启动参数强制。启动前自检：内核 exe 存在、所选代理端口在监听（没在监听就报错提示去起 mihomo，不自动改系统代理）；worker 目录缺 `virtual.dat` 时自动生成。
   - 并发约束：同一 worker id（同一 user-data-dir，Chromium 锁）不能并发开两个；不同 id 可并行。注册数量超过池大小时分波串行，同一波各占不同 id，等上一波全部 taskkill 后才复用。结束按命令行 `--worker-id=<id>` `taskkill /F /T` 整棵进程树（幂等），**绝不删除 worker 目录或 virtual.dat**，不启动 GUI、不创建/删除环境。
   - 已知内核限制（不算 bug，验收不卡）：`navigator.deviceMemory` 不伪装（读真机）；UA 完整版本靠 Client Hints（`ua-full-version`）。
   - **AdsPower 仅作回退**：`FLOVA_BROWSER_BACKEND=adspower` 时走旧本地 API（默认 `http://127.0.0.1:50325`，池 `k1i4dj3c,k1hhj2u`，`ADSPOWER_PROFILE_IDS` 可覆盖），只复用已有 profile、不创建/不删除；启动前尝试一次 `new-fingerprint`，被付费墙拒绝时记 `fingerprint_refreshed=false` 继续（指纹不随每次启动随机），受免费版每日打开次数限制。默认路径不再使用它。结果 JSON 字段：VB 为 `backend:"vb"` + `vb_worker_id` + `fingerprint_rotated` + `cdp_port`；AdsPower 为 `backend:"adspower"` + `ads_profile_id`（+ 兼容 `fingerprint_refreshed`）。
3. 邀请链接：`https://www.flova.ai/?refCode=<promotion_code>`。`promotion_code` 从母号网页会话 `GET /api/v2/invite/promotion/stats` 的 `data.promotion_code` 读，不写死。
4. 点 “Sign up for 300 credits”，再点 “Sign in with Email”，键盘输入邮箱。
5. 复选框验证（Turnstile）出现且还没有 `cf-turnstile-response` 时，刷新页面，然后重新点 “Sign up for 300 credits” → “Sign in with Email” 并重填邮箱。不点击复选框。检测必须穿透所有 Playwright frame 并递归进入 open shadow root——复选框 iframe 可能只存在于 open shadow root 里，顶层 `document.querySelector` 看不到（跨域 frame 的 evaluate 报错就跳过；closed shadow root 和跨域 iframe 内部不可读，不点击、不抓取）。自动路径（`flova_invite._submit_email_and_otp`，用于 `invite_one` / `invite_batch` 及邮箱登录）和 `invite_manual` 共用同一套检测与刷新实现，不允许两套检测器：除原有 open shadow DOM 匹配（`.cf-turnstile`、iframe src/title 含 turnstile / challenges.cloudflare.com / Cloudflare）外，还必须认 Playwright `frame.url`（含 `turnstile` 或 `challenges.cloudflare.com`，大小写不敏感；iframe 元素即使在 closed shadow root 里、querySelector 够不到也算）和 frame 文档文本 `Verify you are human`（该 frame 的 evaluate 抛错则跳过）。约每 0.3 秒轮询：一旦看到复选框且还没有 token，立刻刷新，不等满观察窗口；30 秒观察窗口只用于“什么都没出现”的兜底失败，复选框没检测到时不按计时器刷新。复选框是当前步骤、还没签发 token 时，绝不能 `browser.close()` 或 `proc.terminate()`——先按下面的刷新处理。最多刷新 3 次，之后仍没有 token 就以 `Turnstile token not issued` 失败。滑动验证（阿里云拼图）出现时停住等用户，最多等 900 秒，不刷新、不自动拖滑块。两种验证同时出现时先等用户滑完，再处理复选框。
6. 验证码不用 `/v1/code`。`GET /v1/mailboxes/{key}/messages?force=1`，再 `GET .../messages/{message_id}?format=text`（`message_id` 要 URL 编码）。只认 `notifications@account.flova.ai` 在本次提交之后到达的邮件，取 6 位数字。用 JS 聚焦 `maxlength===6` 的 input，再 `keyboard.type`。
7. 首页仍显示 “Sign up for 300” 视为失败。
8. 网页会话：脚本把该次浏览器里的 flova cookie 采纳到 `~/.flova-mcp/browser-profiles/<profile>`（系统 Chrome/Edge 持久上下文）。邮箱必须和子号一致，否则清空并失败。不要拷贝 Cookies sqlite。
9. `POST https://service.flova.ai/api/agent/v2/token` 取 `data.token`。然后：

```text
flova --api-base https://service.flova.ai/api/agent/v2 profile add <name>
flova --profile <name> auth login --token <token>
flova profile use prod
```

默认 profile 设回 `prod`。核对：`--profile <name> account user` 是新子号；`profile show` 的 default 是 `prod`。token 不进对话、不进 git。

10. 账本 `~/.flova/registry.json` 追加子号：`role=child`，`state=keyed`，`api_key_ref=flova-profile:<name>`，`web_profile_ref=~/.flova-mcp/browser-profiles/<name>`，`invited_by` 为母号 email。只写引用，不写 token 或 cookie。

## 和做片的分界

做片流程（地图底图重绘、装饰图生成）不调用这些脚本。请求里已写明的非空 `params.profile` 沿用、不换号；没写的交给 MCP 号池（`pipeline/common/map_profile.py`）。视频仍默认关闭。
