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
python scripts/flova/invite_manual.py <N>
```

- `ensure`：先清低分号，再按预算并行注册。`B <= signup_liquid_credits`（100）时新子号付款，注册 1 个。`B` 更大时母号付款，人数 = 向上取整( (`B` − 母号余额) / 当次 `credit_reward_num` )。名额盖不住就切合格接班人，不烧旧母号最后名额。没有接班人则 `do_not_generate=true`，立刻停。
- `invite_batch.py`：并行注册固定 N 个。邮箱额外排除 `registration.signals.flova_verification_seen`。邀请码只预热一次并缓存，并行线程不再各自打开母号网页会话。
- `invite_manual.py`：顺序注册，一次一个，方便人工处理验证。滑动验证（阿里云拼图）`#aliyunCaptcha-mask` 出现后最多等 900 秒，等人滑完再继续，不要自动拖滑块，不要刷新。复选框验证（Turnstile）出现且还没有 `cf-turnstile-response` 时自动刷新页面，刷新后重新打开邮箱面板并重填邮箱，最多刷新 3 次，不点击复选框。两种验证同时出现时先等用户滑完滑块。
- `repair-web`：不邀新、不删号。逐个打开已有 VirtualBrowser 目录，会话邮箱一致就采纳；没有会话且有 `mailbox_ref` 时允许一次邮箱 OTP 登录。

`FLOVA_AUTO_INVITE=0` 时 `ensure` 直接返回 `do_not_generate`，不注册。

## 脚本里的注册步骤

`invite_one` 对每个号做这些事。Agent 不要平行再手点一遍。

1. 邮箱：`GET http://119.29.187.184:18793/v1/mailboxes?provider=outlook&active=1`。要活跃、未过期、`registration.flova.registered != true`、不在账本里。`invite_batch.py` 还排除收过 Flova 验证码的邮箱。挑选顺序：没有导入时间的是最早一批，最先消费；有导入时间的按 `imported_at` 从早到晚（先导入先注册）；同档按地址小写升序。
2. VirtualBrowser：内核在 `C:\Program Files\VirtualBrowser\VirtualBrowser\<版本>\VirtualBrowser.exe`。worker 从编号 10 起分配，CDP 端口 `18850 + (编号 % 100)`，目录在 `%LOCALAPPDATA%\VirtualBrowser\Workers\<id>`。命令行里的网址不会打开，脚本用 CDP `page.goto`。
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

`npm run make`、`map:fetch`、装饰图生成不调用这些脚本。地图底图重绘的 profile 钉为当前活跃母号（`~/.flova/registry.json` 的 `active_mother_profile`；请求里已写明的非空 `params.profile` 沿用），不换号。视频仍默认关闭。
