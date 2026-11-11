# Virtual Browser 指纹浏览器后端（flova 注册自动化）

flova 积分邀请/注册的浏览器后端从 AdsPower 迁到 Virtual Browser（VB）。本文记录已实测的机制、工具、字段语义、限制和排错方法，供后续排查与加功能。对应规则见 `rules/flova-register.md`，邀请入口仍是 `scripts/flova/flova_invite.py`。

- 验证日期：2026-10-19，VB 免费版 2.2.16，内核 Chromium 146.0.7680.72。
- 关键结论：**免费版就能用指纹，不需要 VIP、不需要扩展、不需要本地 HTTP API**。指纹在「内核直拉 + 正确的 worker 目录」时生效；VB 没有 AdsPower 那种「每日打开次数」硬限额。

## 1. 机制（为什么直拉内核有时没指纹）

指纹不是扩展注入的，而是**内核自己读 JSON**：

- 内核 `C:\Program Files\VirtualBrowser\VirtualBrowser\146.0.7680.72\VirtualBrowser.exe`
  启动时按命令行 `--worker-id=<id>`，在 `--user-data-dir=<dir>` 下找 `virtual.dat`，
  匹配其中 `users[].id == <id>` 的记录来应用指纹。
- 必备两个条件，缺一读到的就是真机指纹：
  1. `--user-data-dir` 指向的目录里**必须有 `virtual.dat`**；
  2. 命令行带 `--worker-id=<id>`，且 `virtual.dat` 里有同 id 的 user。
- 常见踩坑：新建的空目录（如脚本自建 `Workers\10`）里没有 `virtual.dat`，此时只给 `--worker-id` 不生效。
  GUI 第一次「启动」某环境时会把全局 `User Data\virtual.dat` 拷一份进 `Workers\<id>\`；
  我们也可以直接写。
- 指纹逻辑在内核 `chrome.dll`（键表含 `users/webgl-img/audio-context/client-rects/ua-full-version/virtual.dat/global.dat/worker-id`，无 `isVip`）。
- `--load-extension=` 为空只表示该环境没装用户 CRX，与指纹无关。`resources\res\core.dll` 是 GUI 的窗口同步库，不进内核。
- VIP 实际只挡：本地自动化 HTTP API（旧版 9000 → 现动态端口+API Key，`launchBrowserHTTPHandler/getApiPort`）与云同步。指纹本身免费。

数据文件：

- 全局环境库（GUI 列表）：`%LOCALAPPDATA%\VirtualBrowser\User Data\virtual.dat`（明文 JSON，`{"users":[...]}`）。
- 单环境运行目录：`%LOCALAPPDATA%\VirtualBrowser\Workers\<id>\`（Chromium user-data-dir），指纹文件 `Workers\<id>\virtual.dat`。
- 内核只认 worker 目录里那份。GUI 运行时把环境列表放内存，手改磁盘 `virtual.dat` 可能在 GUI 下次保存时被覆盖；自动化阶段要么关 GUI，要么只写 worker 目录、不碰全局库。

## 2. 工具（都在仓库 `tmp/`，接入正式代码时应迁到 `scripts/flova/`）

| 文件 | 作用 |
|---|---|
| `tmp/vb_fingerprint.py` | 生成一套全新自洽指纹，写到 `Workers\<id>\virtual.dat`。`python tmp/vb_fingerprint.py <id> --country us\|jp [--seed N] [--name X]` |
| `tmp/vb_launch.py` | 启动环境并验证。`python tmp/vb_launch.py <id> [--rotate us\|jp] [--proxy http://127.0.0.1:7898] [--lang en-US\|ja-JP] [--incognito] [--port P] [--exit-after-proof]`，打印 CDP 地址，证明写 `tmp/vb_launch_last.json` |

标准启动命令（`vb_launch.py` 内部就是这样拼的）：

```text
VirtualBrowser.exe \
  --user-data-dir=%LOCALAPPDATA%\VirtualBrowser\Workers\<id> \
  --worker-id=<id> --no-first-run --no-default-browser-check \
  --remote-debugging-port=<free> --remote-allow-origins=* \
  --proxy-server=http://127.0.0.1:7898 \
  --lang=en-US --accept-lang=en-US \
  [--incognito]
```

Python 用 Playwright `connect_over_cdp(f"http://127.0.0.1:{port}")` 接管，`browser.contexts[0]` 即目标上下文。

## 3. 每次启动不同指纹（已实测支持）

- **内核不缓存指纹**：每次进程启动都重新读 `virtual.dat`。在启动前重写 `Workers\<id>\virtual.dat`，本次启动就用新指纹（CPU/GPU/screen/canvas/audio/字体/MAC/设备名/时区都会变）。
- 实测同一个 id 连续两次：CPU 4核/AMD → 8核/NVIDIA，canvas 哈希随之变化。
- 一键轮换：`python tmp/vb_launch.py <id> --rotate us`（内部先调 `vb_fingerprint.py` 重新生成，再启动；`--rotate jp` 默认带 `--lang ja-JP`）。
- 两种隔离策略：
  - **单槽轮换（推荐配合无痕）**：固定少量 worker id，每次启动前 `--rotate` 重写指纹 + `--incognito`，做到「每次注册设备指纹不同 + 会话不落盘」。
  - **多 worker 固定指纹**：为每个长期账号保留独立 `Workers\<id>`（指纹稳定，Cookie/登录态可留存）。批量新号用新 id。
- 同一 user-data-dir 不能同时开两个进程（Chromium ProcessSingleton 锁）。`vb_launch.py` 用命令行检测 `--worker-id=<id>` 是否已在跑来避免重复启动。

## 4. 代理、语言、时区的自洽

- 代理用内核参数 `--proxy-server=http://127.0.0.1:<port>` 即可，和指纹同时生效，会盖过系统代理；**不用改 `virtual.dat` 的 proxy**（`proxy.mode=0` 跟随系统，但命令行优先）。
- 本地代理：
  - `127.0.0.1:7898`：独立 mihomo，订阅路径 `/proxyip=` 美 4 + 日 4 列表（美国在前），配置 `tmp/mihomo8.yaml`。
  - `127.0.0.1:7899`：日本专线（单 Tokyo AWS 54.95.106.234），配置 `tmp/mihomo_jp7899.yaml`。
  - 上游是自建 edgetunnel 面板 `https://845157204.xyz/admin`；PROXYIP 经节点 WS 路径 `/proxyip=<ip>` 下发，详见本文件第 7 节与记忆 `flova-adspower-proxy-exit`。
- **语言**：这版内核的 `ua-language.mode=2（跟随IP）` 实测并不会自动改 `navigator.language`（默认 en-US）。要日语必须启动加 `--lang=ja-JP --accept-lang=ja-JP,ja,en-US,en`。美国用 `--lang=en-US`。
- **时区**：`virtual.dat` 的 `time-zone` 生效。`mode=2` 名义是「跟随 IP」，但实测换出口后时区名不再变（用的是文件里写死的值）。生成器按 `--country` 写死：US=`America/New_York`(UTC−5，DST 期 −4)，JP=`Asia/Tokyo`(+9)。文件里旧的 `America/Santa_Isabel` 已从 tzdata 删除，Chromium 报后继名 `America/Tijuana`。
- 配对原则：**美国指纹 → 7898（美出口）→ en-US → 美国时区**；**日本指纹 → 7899（日出口）→ ja-JP → Asia/Tokyo**。三者必须一致，否则自相矛盾容易被风控。

## 5. 无痕模式

- `--incognito` 与 `--worker-id`、`--user-data-dir`、`--proxy-server` 可共存，CDP 可连（只有一个 context）。
- 无痕里指纹**全部保留**（指纹在内核，不依赖扩展；Chromium 无痕默认不加载 `--load-extension` 扩展，但此环境本来就没有扩展）。
- 实测连开两次无痕：第一次写入的 localStorage 第二次为空。→ 每次注册用 `--incognito` 即可获得干净会话又保住本次指纹。
- 若一次注册流程内要保留 Cookie/存储，就不要用无痕，改为「新建一个只含 `virtual.dat` 的干净 user-data-dir」。

## 5.5 窗口模式：默认最小化后台，不弹窗

- `flova_invite.launch_worker` 启动 VB 后立即用 CDP `Browser.setWindowBounds` 把窗口最小化到任务栏：**不弹窗、不抢焦点**，注册全程后台跑。默认生效，`FLOVA_VB_WINDOW=normal` 恢复可见窗口旧行为。
- 最小化启动时内核额外带防节流参数（`--disable-backgrounding-occluded-windows`、`--disable-renderer-backgrounding`、`--disable-background-timer-throttling`、`--disable-features=CalculateNativeWinOcclusion`），保证窗口不可见时渲染与定时器照常，Turnstile 等 JS 挑战不会因后台而卡住。这些参数不影响指纹。
- 需要人工的环节只有阿里云滑块：`invite_manual.settle_captcha` 一看到 `#aliyunCaptcha-mask` 就把窗口恢复到前台（`windowState=normal` + `bring_to_front`）再等人工滑过。
- `invite_hand`（手动邀请）的窗口同样最小化，终端提示改为自己点任务栏图标开始注册。
- 覆盖范围：`ensure`、`invite_batch`、`invite_manual`、`invite_hand`、`register_direct`、`repair-web`（都走 `flova_invite.launch_worker`）。AdsPower 回退后端与 `login_web.py`（直接调 `vb_backend.launch_worker`，网页登录本来就要人操作）不受影响。

## 6. 指纹字段语义与已知限制

`virtual.dat` 的 user 记录 39 个字段，指纹项都是 `{"mode":0|1|2,...}`：`mode=0` 默认/真机，`mode=1` 自定义（读 `value` 等），`mode=2` 跟随 IP/智能。已实测的有效项：

- 有效：`ua-full-version`(Client Hints 完整版本)、`cpu`、`webgl`(vendor/render)、`webgpu`、`screen`、`time-zone`、`canvas`、`webgl-img`、`audio-context`、`client-rects`、`fonts`、`speech_voices`、`mac`、`device-name`、`media`、`webrtc`(0=替换/不泄露 host candidate)、`location`(2=跟随IP)。
- UA 注意：`ua.mode=0`（默认）时地址栏 UA 是精简 `Chrome/146.0.0.0`，完整版本由 `ua-full-version.mode=1` 写进 Client Hints（`navigator.userAgentData.getHighEntropyValues` 读到 146.0.7635.3）；`sec-ch-ua.mode=0` 时品牌是真实的 `Not-A.Brand/24`，文件里手写的品牌不生效。要彻底自定义 UA 串需额外研究 `ua.mode`。
- **`deviceMemory` 这版内核不伪装**：无论 `memory.value` 写什么，`navigator.deviceMemory` 都读真机（本机 8）。`vb_launch.py` 已把它排除出验收门，只记录不判失败。区分设备主要靠 CPU 核数/GPU/UA 完整版/时区/canvas。
- `location` 曾返回 code 3 超时，不能假定已按 IP 伪装；注册流程不建议强制弹地理授权。
- WebRTC `mode=0`：伪装进程 2.5s 内无 ICE candidate，对照进程泄露 host candidate，方向正确。
- canvas/webgl/audio/client-rects 噪声是小幅 RGBA/float 扰动；同一份 `virtual.dat` 多次启动 canvas 哈希稳定（利于固定指纹），重写文件后变化（利于轮换）。

## 7. 上游出口面板（845157204.xyz）补充

- 面板是 BPB/edgetunnel，登录 `POST /login`（form password），cookie 绑定 UA：**保存配置的 POST 必须和登录用同一 UA**，否则 302 回 `/login`。
- 出口由「反代 → PROXYIP」控制（逗号分隔 IP），保存接口 `POST /admin/config.json`（整份配置回写）。
- PROXYIP 只对「目标站本身在 Cloudflare 后面」生效（flova.ai 在 CF 上，满足）；非 CF 目标走 CF WARP。且**只在订阅节点 WS 路径 `/proxyip=<ip1,ip2...>` 时生效**，用 path `/` 连不生效。
- 节点筛选/测速用 `https://api.090227.xyz/check?proxyip=<ip>`（返回 success、落地 country/city/asn、bot score）。该接口怕并发：>3~并发会临时 403，需低并发+退避。

## 8. 排错清单

| 现象 | 原因 / 处理 |
|---|---|
| 读到真机指纹（Chrome/143 或真机 CPU/GPU） | worker 目录缺 `virtual.dat`，或没带匹配的 `--worker-id`。用 `vb_launch.py`，确认 `Workers\<id>\virtual.dat` 存在 |
| 同目录第二次启动报占用/连不上 | user-data-dir 已被占用；先 taskkill 旧进程树。`vb_launch.py` 有在跑检测（退出码 3） |
| 语言还是 en-US（日本号） | 内核不按 IP 改语言，加 `--lang=ja-JP --accept-lang=...` |
| 时区和出口国家不符 | 这版不实时跟随 IP，`virtual.dat` 里 `time-zone` 要按国家写死 |
| 改了 `virtual.dat` 没变化 | GUI 开着会用内存覆盖；关掉 GUI 或只写 worker 目录。另确认改的是 `Workers\<id>\virtual.dat` 不是全局那份 |
| 出口不是美/日 | 检查 `--proxy-server` 是否加上、7898/7899 mihomo 是否在跑（`netstat` 查端口；curl `-x` 查 trace） |
| 设备内存 deviceMemory 对不上 | 已知限制，内核不伪装，忽略此项 |
| 需要 GUI 调试 | 给 GUI 主程序加 `--remote-debugging-port=9223` 启动，CDP 可在其渲染层调 `chrome.send(...)`（仅调试用，自动化不依赖它） |

## 9. 接入正式脚本的改造点（AdsPower → VB）

`scripts/flova/flova_invite.py` 当前 AdsPower 面：

- `AdsPowerSession`（NamedTuple，~286）、`ads_api_base/ads_profile_pool/_ads_headers/_ads_exe_path/ensure_ads_api`（49-367）、`next_workers`（370）、`new_fingerprint` 调用（启动前）、`launch_ads`（~414，返回 debug_port）、`stop_ads`（453）。
- `invite_one`（~903）：`start_ads→wait_cdp→_signup_in_browser(cdp)→stop_ads`，结果字段 `ads_profile_id/fingerprint_refreshed/cdp_port`。
- `_run_parallel`（~957）：按 AdsPower 池大小分波；ensure 末尾清理孤儿浏览器。
- repair-web（~1189）也复用池里一个 profile，串行。
- `invite_batch.py` / `invite_manual.py` 通过 `fi.next_workers / fi.launch_ads / fi.wait_cdp / fi.stop_ads / fi.AdsPowerSession` 间接使用（`invite_manual.register_one` ~309、批量 ~385）。

替换为 VB 时保持这些函数签名兼容即可（下游尽量少改）：把 worker 抽象成「id + 启动返回 cdp 端口 + 停止」，启动用本文件第 2 节命令，启动前按目标国家重写 `virtual.dat`（轮换），注册用 `--incognito`，代理按国家选 7898/7899、语言 `--lang`。无 AdsPower 池大小/每日限额约束，但仍遵守「同 user-data-dir 不并发」。
