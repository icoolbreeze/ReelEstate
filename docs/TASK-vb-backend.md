# TASK：把 flova 注册浏览器后端从 AdsPower 换成 Virtual Browser（给新 session）

> 用法：新建一个 session，把「==== 任务提示词开始 ====」之后的内容整段贴进去执行。先读背景文档，不要凭印象改。

==== 任务提示词开始 ====

把 `scripts/flova/flova_invite.py` 的注册浏览器后端从 AdsPower 正式换成 Virtual Browser（VB），去掉 AdsPower 免费版「每日打开次数」硬限额，保留现有邀请业务逻辑不变。

## 必读（按顺序）
1. `docs/virtual-browser-backend.md` —— 已实测的 VB 机制、字段语义、代理/语言/无痕/轮换/限制/排错。一切以它为准。
2. `rules/flova-register.md`、`AGENTS.md` §3C —— 现有注册规则（第 2 节目前写的是 AdsPower，需要同步改成 VB）。
3. 代码：`scripts/flova/flova_invite.py`（AdsPower 面见下）、`scripts/flova/invite_batch.py`、`scripts/flova/invite_manual.py`。
4. 已验证可用的原型（在 tmp/，先读再迁）：
   - `tmp/vb_launch.py`（启动 + 指纹验收 + 代理/语言/无痕/轮换）
   - `tmp/vb_fingerprint.py`（生成自洽指纹写 `Workers\<id>\virtual.dat`）

## 已确认事实（不要再走弯路）
- VB 免费版 2.2.16，指纹内核自带，无需 VIP/扩展/本地 HTTP API；没有每日打开限额。
- 指纹生效条件：内核启动带 `--worker-id=<id>`，且 `--user-data-dir` 指向的目录里有 `virtual.dat`（里面有同 id 的 user）。内核每次启动重读，**无缓存**——启动前重写该文件即可「每次启动不同指纹」（已实测 CPU/GPU/canvas 都变）。
- 启动命令（Playwright 经 `http://127.0.0.1:<port>` `connect_over_cdp`，取 `contexts[0]`）：
  `内核.exe --user-data-dir=%LOCALAPPDATA%\VirtualBrowser\Workers\<id> --worker-id=<id> --no-first-run --no-default-browser-check --remote-debugging-port=<free> --remote-allow-origins=* --proxy-server=<proxy> --lang=<lang> --accept-lang=<...> [--incognito]`
- 内核路径：`C:\Program Files\VirtualBrowser\VirtualBrowser\146.0.7680.72\VirtualBrowser.exe`（支持环境变量覆盖，便于改版本）。
- 代理：美国 `http://127.0.0.1:7898`（mihomo，美 4 日 4，美国优先）；日本 `http://127.0.0.1:7899`（日本专线）。语言必须用启动参数强制（内核不按 IP 改语言）：美 `--lang=en-US`，日 `--lang=ja-JP --accept-lang=ja-JP,ja,en-US,en`。
- 无痕 `--incognito` 下指纹全保留、localStorage 不复用 → 注册一律用无痕，做到「每次注册设备指纹不同 + 会话干净」。
- 同一 user-data-dir 不能并发开两个（Chromium 锁）；不同 id 可并行。
- 已知内核限制：`navigator.deviceMemory` 不伪装（读真机），UA 完整版本靠 Client Hints（`ua-full-version`），这两点不算 bug，验收不要卡。

## 改造要求
1. 把 `tmp/vb_fingerprint.py`、`tmp/vb_launch.py` 的能力迁进仓库正式位置（建议 `scripts/flova/vb_backend.py` 与 `scripts/flova/vb_fingerprint.py`，或合并为一个模块），不要在正式代码里 import tmp/。Python 只用标准库 + 现有的 requests/playwright（先看现有脚本依赖，别引入新三方包）。
2. 在 `flova_invite.py` 用「同签名兼容」的后端抽象替换 AdsPower，尽量不动下游注册流程：
   - worker 抽象保留 `id/name`，并能 `launch() -> cdp_port`、`stop()`；`wait_cdp` 可继续用。
   - `next_workers(n)`：改为返回 VB worker。保留环境变量覆盖，例如 `FLOVA_VB_WORKER_IDS`（默认给一个可并行的小池，如 `100,101`，但要确认这些 id 的 `Workers\<id>\virtual.dat` 存在；不存在则在启动前生成）。
   - 启动前不再调 AdsPower `new-fingerprint`，改为：按目标国家用 `vb_fingerprint` **重写该 worker 的 virtual.dat（每次随机、自洽）**，再以无痕 + 对应代理/语言启动。等价于「每次启动不同指纹」。
   - `launch_ads/stop_ads` 改名或包一层 `launch_worker/stop_worker`；`invite_batch.py`、`invite_manual.py` 里的 `fi.launch_ads/fi.stop_ads/fi.AdsPowerSession/fi.next_workers` 调用点要同步改（见 `invite_manual.register_one` ~309、批量 ~385）。
   - `_run_parallel` 的分波逻辑保留，但约束从「AdsPower 池大小/每日限额」改为「同 worker id 不并发」；ensure 末尾的孤儿浏览器清理改为按 worker id/命令行 `--worker-id=` 清理（taskkill 进程树，幂等），绝不删除 worker 目录或 virtual.dat。
   - repair-web（~1189）同样改走一个 VB worker（串行、无痕）。
   - 结果 JSON 里的 `ads_profile_id/fingerprint_refreshed/cdp_port` 改为 VB 等价字段（如 `vb_worker_id/fingerprint_rotated/cdp_port`），更新所有读取处。
3. 后端选择：加环境变量开关 `FLOVA_BROWSER_BACKEND=vb|adspower`，**默认 `vb`**；保留 AdsPower 代码路径作为回退（不必删，但默认不再用）。国家/出口：`FLOVA_VB_COUNTRY=us|jp`（默认 us），据此选代理端口(us→7898/jp→7899)、语言、指纹国家、时区；三者必须一致。
4. 启动前自检：内核 exe 存在；所选代理端口在监听（没有就给出明确错误，提示去起 mihomo，不要自动改系统代理）；worker 目录缺 virtual.dat 时自动生成而不是报错。
5. 同步文档：更新 `rules/flova-register.md` 第 2 节为 VB（机制/worker 池/轮换/代理/语言/无痕/无每日限额），并核对 `AGENTS.md` §3C 里提到 AdsPower profile（k1i4dj3c 等）的措辞是否需要改成「默认 VB、AdsPower 仅回退」。`docs/virtual-browser-backend.md` 已就绪可直接引用。

## 验证（必须做，逐级来）
1. 单元级：用迁好的模块启动一个 worker（美、日各一次），CDP 读取 uaFullVersion/cpu/webgl/timezone/language/出口 IP，断言与目标国家自洽、`deviceMemory` 不参与判定。两次 `--rotate` 同 id 的 canvas/CPU 至少有一次不同（证明轮换）。
2. 后端级：`FLOVA_BROWSER_BACKEND=vb` 下跑一个不花钱/不注册的 dry 路径（如果脚本没有 dry-run，至少跑到「浏览器打开到邀请落地页」即可，先不提交邮箱），确认 worker 能启动、CDP 连通、无痕、代理出口正确、结束被清理。
3. 端到端（会真实消耗一个邮箱名额，**执行前先向用户确认一次**）：`python scripts/flova/flova_invite.py ensure --budget 100 --profile prod`，预期子号注册成功并 keyed；若仍卡在 Cloudflare Turnstile/阿里云滑块，判定为出口 IP 信誉问题（与浏览器后端无关），如实汇报抓取的现象，不要改 check 规则、不要绕验证码。
4. 回归：`FLOVA_BROWSER_BACKEND=adspower` 路径代码不被破坏（能 import、参数仍在），但当天 AdsPower 有日限额时不必真跑。

## 硬性约束
- 不 git commit/push；不改 `.mcp.json`、`.grok/`、用户本机 MCP 客户端配置；不改 VB 安装目录、不动 GUI 全局 `User Data\virtual.dat`（只写 `Workers\<id>\virtual.dat`，且自动化时尽量关着 GUI）。
- 凭证/token/cookie 不打印、不进 git、不进命令行；遵守 AGENTS.md §3C/§5。
- 文本 UTF-8 无 BOM、LF；Windows 写文件用 `encoding="utf-8", newline="\n"`。
- 不为了让流程通过而改合规/风控规则或自动过验证码；失败就报告原始现象。

## 交付
- 迁好的 VB 后端模块 + flova_invite/invite_batch/invite_manual 的接线；env 开关；规则/文档更新。
- 一份简报：改了哪些文件、怎么验证的（附指纹/出口读数）、默认后端与回退方式、遗留问题（如 Turnstile 是否仍拦）。
==== 任务提示词结束 ====
