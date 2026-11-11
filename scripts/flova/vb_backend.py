# -*- coding: utf-8 -*-
"""Virtual Browser（VB）注册浏览器后端 —— flova 邀请/注册默认后端。

替代旧的 AdsPower 本地 API：VB 免费版 2.2.16 自带指纹内核，无 VIP / 扩展 /
本地 HTTP API，也没有 AdsPower 免费版「每日打开次数」硬限额。机制全部来自
docs/virtual-browser-backend.md（2026-10-19 实测）。

要点：
- 内核按 ``--worker-id=<id>`` 在 ``--user-data-dir`` 里读 ``virtual.dat`` 应用指纹；
  每次启动都重读、无缓存 → 启动前重写该文件即「每次启动一套新指纹」。
- 注册一律 ``--incognito``：指纹保留、localStorage 不落盘，会话干净。
- 代理/语言/时区按国家强制自洽：us→127.0.0.1:7898 + en-US + America/New_York；
  jp→127.0.0.1:7899 + ja-JP + Asia/Tokyo。
- 同一 worker id（同一 user-data-dir）不能并发开两个（Chromium 锁），分波由调用方保证。

只依赖标准库（+ 调用方已有的 playwright，且仅在 read_proof 时 lazy import）。
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, NamedTuple

import vb_fingerprint as vbf

# ---- 配置（环境变量可覆盖） -------------------------------------------------
VB_DEFAULT_KERNEL = r"C:\Program Files\VirtualBrowser\VirtualBrowser\146.0.7680.72\VirtualBrowser.exe"
VB_DEFAULT_WORKER_IDS = (100, 101)

# country -> (proxy url, --lang, --accept-lang)
COUNTRY_CFG: dict[str, dict[str, str]] = {
    "us": {
        "proxy": "http://127.0.0.1:7898",
        "lang": "en-US",
        "accept_lang": "en-US",
    },
    "jp": {
        "proxy": "http://127.0.0.1:7899",
        "lang": "ja-JP",
        "accept_lang": "ja-JP,ja,en-US,en",
    },
}


class VBWorker(NamedTuple):
    """一个 VB worker：id = worker 目录名/--worker-id，name 仅展示用。"""
    id: int
    name: str

    @property
    def profile_id(self) -> int:
        # 兼容旧代码里 worker.profile_id 的读法（AdsPower 回退路径仍用字符串 id）。
        return self.id


def backend_name() -> str:
    return "vb"


def country() -> str:
    c = ""
    try:
        import os
        c = os.environ.get("FLOVA_VB_COUNTRY", "us").strip().lower()
    except Exception:
        c = "us"
    return c if c in COUNTRY_CFG else "us"


def window_mode() -> str:
    """注册浏览器窗口形态：``FLOVA_VB_WINDOW`` = ``minimized``（默认）| ``normal``。

    minimized：启动后立即把窗口最小化到任务栏，不弹窗、不抢焦点；同时给内核加
    防节流参数，保证后台窗口里 Turnstile 等 JS 挑战满速运行。需要人工时（阿里云
    滑块）由 invite_manual.settle_captcha 自动把窗口恢复到前台。``normal`` 恢复
    旧的可见窗口行为。
    """
    import os
    m = os.environ.get("FLOVA_VB_WINDOW", "minimized").strip().lower()
    return m if m in ("minimized", "normal") else "minimized"


def kernel_path() -> Path:
    import os
    env = os.environ.get("FLOVA_VB_KERNEL", "").strip()
    return Path(env) if env else Path(VB_DEFAULT_KERNEL)


# Clash Verge GUI 自带 mihomo 的默认 mixed-port（可被 FLOVA_CLASH_PROXY 覆盖）。
CLASH_PROXY_DEFAULT = "http://127.0.0.1:7897"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def proxy_mode() -> str:
    """VB 出口代理来源（优先级：环境变量 > 仓库标记文件 > 默认 mihomo）。

    - ``FLOVA_VB_PROXY`` 显式给出时恒为 ``custom``（整条代理 URL 直接用它）。
    - 否则看 ``FLOVA_VB_PROXY_MODE``：
        * ``clash`` = 直接走 Clash Verge 的本地混合端口（默认 7897），节点在
          Clash GUI 里自己钉一个稳定美/日节点；不自动起专用 mihomo、不轮换。
        * ``mihomo`` = 按国家走仓库专用 mihomo（7898 美 / 7899 日）。
    - 没设环境变量时读仓库标记文件 ``tmp/vb-proxy-mode``（内容 ``clash`` 或
      ``mihomo``）。这样从「Flova号池」面板点网页登录也能切换，**不用重启面板**。
    """
    import os
    if os.environ.get("FLOVA_VB_PROXY", "").strip():
        return "custom"
    env_m = os.environ.get("FLOVA_VB_PROXY_MODE", "").strip().lower()
    if env_m in ("clash", "mihomo"):
        return env_m
    try:
        raw = (_repo_root() / "tmp" / "vb-proxy-mode").read_text(
            encoding="utf-8", errors="replace").strip().lower()
        if raw in ("clash", "mihomo"):
            return raw
    except OSError:
        pass
    return "mihomo"


def clash_proxy() -> str:
    import os
    return os.environ.get("FLOVA_CLASH_PROXY", "").strip() or CLASH_PROXY_DEFAULT


def proxy_for(cc: str) -> str:
    """本次启动 VB 实际要用的代理 URL（按 proxy_mode 解析）。"""
    import os
    explicit = os.environ.get("FLOVA_VB_PROXY", "").strip()
    if explicit:
        return explicit
    if proxy_mode() == "clash":
        return clash_proxy()
    return COUNTRY_CFG[cc]["proxy"]


def worker_pool() -> list[VBWorker]:
    """可并行复用的 VB worker 池（默认 100,101；FLOVA_VB_WORKER_IDS 逗号分隔覆盖）。"""
    import os
    raw = os.environ.get("FLOVA_VB_WORKER_IDS", "").strip()
    ids: list[int] = []
    if raw:
        for part in raw.split(","):
            part = part.strip()
            if part:
                ids.append(int(part))
    if not ids:
        ids = list(VB_DEFAULT_WORKER_IDS)
    return [VBWorker(id=i, name=f"vb-{i}") for i in ids]


# ---- 网络 / 进程工具 --------------------------------------------------------

def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _proxy_host_port(url: str) -> tuple[str, int]:
    from urllib.parse import urlparse
    u = urlparse(url)
    return (u.hostname or "127.0.0.1", int(u.port or 0))


def proxy_listening(proxy_url: str, timeout: float = 1.5) -> bool:
    host, port = _proxy_host_port(proxy_url)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---- 代理自动拉起（独立 mihomo 实例，与 Clash Verge GUI 互不影响） ----------

# 仓库根目录 = scripts/flova 上两级。
_REPO_ROOT = Path(__file__).resolve().parents[2]
# cc -> (代理 mixed-port, 配置文件相对仓库根)
_MIHOMO_CFG: dict[str, tuple[int, str]] = {
    "us": (7898, "tmp/mihomo8.yaml"),
    "jp": (7899, "tmp/mihomo_jp7899.yaml"),
}
_MIHOMO_EXE_CANDIDATES = (
    r"C:\Program Files\Clash Verge\verge-mihomo.exe",
    r"C:\Program Files (x86)\Clash Verge\verge-mihomo.exe",
)


def _mihomo_exe() -> str | None:
    import os
    env = os.environ.get("FLOVA_MIHOMO_EXE", "").strip()
    cands = [env] if env else []
    cands.extend(_MIHOMO_EXE_CANDIDATES)
    for c in cands:
        if c and Path(c).is_file():
            return c
    return None


def proxy_exit_loc(proxy_url: str, *, timeout: float = 12.0) -> str:
    """经代理查 cloudflare trace 的出口国家码（US/JP/...）；失败返回 ""。"""
    import shutil
    curl = shutil.which("curl")
    if not curl:
        return ""
    try:
        r = subprocess.run(
            [curl, "-s", "-m", str(int(timeout)), "-x", proxy_url,
             "https://www.cloudflare.com/cdn-cgi/trace"],
            capture_output=True, text=True, timeout=timeout + 3,
        )
        for line in r.stdout.splitlines():
            if line.startswith("loc="):
                return line[4:].strip().upper()
    except Exception:  # noqa: BLE001
        return ""
    return ""


def ensure_proxy(cc: str, *, auto_start: bool = True,
                 verify_loc: bool = True) -> dict[str, Any]:
    """确保本次 VB 要用的本地代理在监听并能转发。

    代理来源由 :func:`proxy_mode` 决定：
    - ``clash`` / ``custom``：直接用 Clash Verge 端口（默认 7897）或 FLOVA_VB_PROXY，
      **只检查监听 + 出口国家是否和指纹一致，绝不自动起 mihomo**（节点由用户在
      Clash GUI 里钉）。出口 loc 与 cc 不符只告警不阻断（避免 trace 抖动卡死登录）。
    - ``mihomo``（默认）：按国家走仓库专用 mihomo（7898/7899）；端口没监听且
      auto_start 时用仓库 tmp 配置 detached 自动拉起，跨次复用、幂等，不动系统代理。
    """
    mode = proxy_mode()
    proxy_url = proxy_for(cc)
    host, port = _proxy_host_port(proxy_url)

    # clash / 自定义：不自动拉起任何 mihomo，只确认端口在监听、出口国家对得上。
    if mode in ("clash", "custom"):
        if not proxy_listening(proxy_url):
            raise RuntimeError(
                f"{mode} proxy not listening on {host}:{port}. "
                + ("Start Clash Verge and set a stable node, "
                   if mode == "clash" else "check FLOVA_VB_PROXY, ")
                + f"or switch FLOVA_VB_PROXY_MODE=mihomo."
            )
        info: dict[str, Any] = {"proxy": proxy_url, "started": False,
                                "status": f"{mode}_listening", "mode": mode}
        if verify_loc:
            loc = proxy_exit_loc(proxy_url)
            info["exit_loc"] = loc
            want = "JP" if cc == "jp" else "US"
            if loc and loc != want:
                # 不阻断：Clash 节点可能临时漂移；打印告警让用户在 GUI 切回对应国家。
                print(
                    f"[vb] WARNING: proxy exit loc={loc} but fingerprint country={cc}"
                    f" (want {want}). Pick a {want} node in Clash to stay consistent.",
                    file=sys.stderr, flush=True,
                )
                info["loc_mismatch"] = True
        return info

    # 默认 mihomo 模式：下面是原有自动拉起逻辑。
    if proxy_listening(proxy_url):
        return {"proxy": proxy_url, "started": False, "status": "already_listening",
                "mode": "mihomo"}

    if not auto_start:
        raise RuntimeError(
            f"proxy for country={cc} not listening on {host}:{port} "
            "(set FLOVA_MIHOMO_EXE / start it manually, or use "
            "FLOVA_VB_PROXY_MODE=clash)."
        )

    exe = _mihomo_exe()
    if not exe:
        raise RuntimeError(
            f"proxy for country={cc} not listening on {host}:{port}, and no mihomo "
            "found to auto-start. Install Clash Verge or set FLOVA_MIHOMO_EXE."
        )
    rel = _MIHOMO_CFG.get(cc, _MIHOMO_CFG["us"])[1]
    conf = _REPO_ROOT / rel
    if not conf.is_file():
        raise RuntimeError(
            f"proxy for country={cc} not listening and mihomo config missing: {conf}"
        )

    work = conf.parent
    flags = 0
    if sys.platform == "win32":
        flags = (subprocess.DETACHED_PROCESS
                 | subprocess.CREATE_NEW_PROCESS_GROUP
                 | subprocess.CREATE_NO_WINDOW)
    log = open(work / f"mihomo_{port}.log", "ab")
    subprocess.Popen(
        [exe, "-d", str(work), "-f", str(conf)],
        cwd=str(work),
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        close_fds=True,
        creationflags=flags,
    )

    # 等 mixed-port 监听（最多 ~15s）。
    deadline = time.time() + 15.0
    while time.time() < deadline:
        if proxy_listening(proxy_url, timeout=1.0):
            return {"proxy": proxy_url, "started": True,
                    "status": "started", "mode": "mihomo",
                    "exe": exe, "config": str(conf)}
        time.sleep(0.5)
    tail = ""
    try:
        tail = (work / f"mihomo_{port}.log").read_text(
            encoding="utf-8", errors="replace")[-300:]
    except Exception:  # noqa: BLE001
        pass
    raise RuntimeError(
        f"auto-started mihomo but proxy {host}:{port} did not come up. "
        f"Log tail: {tail!r}"
    )


def wait_cdp(port: int, timeout_s: float = 45) -> None:
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.time() + timeout_s
    last: Any = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return
            last = r.status
        except Exception as e:  # noqa: BLE001
            last = str(e)[:80]
        time.sleep(0.5)
    raise RuntimeError(f"VB CDP :{port} not ready ({last})")


def _worker_pids(env_id: int) -> list[int]:
    """命令行含 ``--worker-id=<id>``（带边界）的 VirtualBrowser.exe PID。"""
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='VirtualBrowser.exe'\" | "
        f"Where-Object {{ $_.CommandLine -match '--worker-id={int(env_id)}(\\s|$)' }} | "
        "Select-Object -ExpandProperty ProcessId"
    )
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            text=True, errors="replace", timeout=20,
        )
    except Exception:  # noqa: BLE001
        return []
    pids: list[int] = []
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def running_worker(env_id: int) -> bool:
    return bool(_worker_pids(env_id))


# ---- 启动 / 停止 ------------------------------------------------------------

def ensure_fingerprint(env_id: int, cc: str, *, rotate: bool = True) -> Path:
    """确保 Workers/<id>/virtual.dat 存在且自洽。

    rotate=True（注册默认）：无论是否已存在都重写一套全新随机指纹（每次启动换新）。
    rotate=False：仅在缺文件时生成。
    """
    path = vbf.worker_dir(env_id) / "virtual.dat"
    if rotate or not path.exists():
        return vbf.write_fingerprint(env_id, cc)
    return path


def preflight(cc: str) -> dict[str, Any]:
    """启动前自检：内核存在、所选国家代理在监听（必要时自动拉起 mihomo）。

    代理端口没监听时，用仓库 tmp 配置自动起一个独立 verge-mihomo 实例（detached、
    幂等、跨次复用），不动系统代理也不影响 Clash Verge GUI。设 FLOVA_PROXY_AUTOSTART=0
    可关闭自动拉起，恢复成只检查并报错。
    """
    exe = kernel_path()
    if not exe.is_file():
        raise RuntimeError(
            f"VB kernel not found: {exe} "
            "(set FLOVA_VB_KERNEL to the installed VirtualBrowser.exe)"
        )
    import os
    auto = os.environ.get("FLOVA_PROXY_AUTOSTART", "1").strip() not in {"0", "false", "False"}
    pinfo = ensure_proxy(cc, auto_start=auto)
    return {"kernel": str(exe), "country": cc,
            "proxy": proxy_for(cc), "proxy_mode": proxy_mode(),
            "proxy_started": pinfo.get("started", False),
            "exit_loc": pinfo.get("exit_loc", ""),
            "loc_mismatch": pinfo.get("loc_mismatch", False)}


def launch_worker(env_id: int, *, country_code: str | None = None,
                  incognito: bool = True, rotate: bool = True,
                  port: int = 0) -> int:
    """启动一个 VB worker，返回 CDP 端口（int）。

    流程：按国家重写指纹（每次随机）→ 自检内核/代理 → 确认同 id 未在跑 →
    拼命令（无痕 + 代理 + 语言）→ 拉起内核 → 等 CDP。
    """
    cc = country_code or country()
    if cc not in COUNTRY_CFG:
        raise ValueError(f"country must be us|jp, got {cc!r}")
    env_id = int(env_id)

    ensure_fingerprint(env_id, cc, rotate=rotate)
    pinfo = preflight(cc)
    proxy_url = pinfo["proxy"]

    if running_worker(env_id):
        raise RuntimeError(f"VB worker {env_id} is already running (same user-data-dir)")

    cfg = COUNTRY_CFG[cc]
    ud = vbf.worker_dir(env_id)
    cdp_port = int(port) or _free_port()
    cmd = [
        str(kernel_path()),
        f"--user-data-dir={ud}",
        f"--worker-id={env_id}",
        "--no-first-run",
        "--no-default-browser-check",
        f"--remote-debugging-port={cdp_port}",
        "--remote-allow-origins=*",
        f"--proxy-server={proxy_url}",
        f"--lang={cfg['lang']}",
        f"--accept-lang={cfg['accept_lang']}",
    ]
    if incognito:
        cmd.append("--incognito")
    if window_mode() == "minimized":
        # 后台满速：禁用最小化/遮挡节流，窗口不可见时渲染与定时器照常，
        # Turnstile / 滑块检测等 JS 挑战不因窗口在后台而卡住。
        cmd += [
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling",
            "--disable-features=CalculateNativeWinOcclusion",
        ]

    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        cmd,
        cwd=str(kernel_path().parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
    )
    wait_cdp(cdp_port)
    return cdp_port


def set_window_state(port: int, state: str) -> bool:
    """用 CDP ``Browser.setWindowBounds`` 调整浏览器窗口状态（不弹窗的后台化）。

    state 只允许 minimized / normal / maximized；bounds 里只能带 windowState
    （CDP 禁止它与 left/top/width/height 同传）。连接失败返回 False，调用方兜底，
    绝不因此中断注册流程。
    """
    if state not in ("minimized", "normal", "maximized"):
        raise ValueError(f"bad window state: {state!r}")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            try:
                ctx = browser.contexts[0]
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                cdp = ctx.new_cdp_session(page)
                w = cdp.send("Browser.getWindowForTarget")
                cdp.send(
                    "Browser.setWindowBounds",
                    {"windowId": w["windowId"],
                     "bounds": {"windowState": state}},
                )
                return True
            finally:
                browser.close()
    except Exception:  # noqa: BLE001
        return False


def stop_worker(env_id: int) -> None:
    """按命令行 ``--worker-id=<id>`` taskkill 整棵进程树（幂等）。

    已不在跑视为成功。绝不删除 worker 目录或 virtual.dat。
    """
    for pid in _worker_pids(int(env_id)):
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30,
        )


def cleanup_orphans(workers) -> None:
    """ensure 末尾兜底：把给定 worker 池里仍在跑的内核全部 taskkill（幂等）。"""
    for w in workers:
        try:
            stop_worker(w.id if hasattr(w, "id") else int(w))
        except Exception:  # noqa: BLE001
            pass


# ---- 指纹/出口验收（只读，供验证脚本用） ------------------------------------

_PROOF_JS = r"""
async () => {
  const out = {};
  out.ua = navigator.userAgent;
  out.platform = navigator.platform;
  out.hardwareConcurrency = navigator.hardwareConcurrency;
  out.deviceMemory = navigator.deviceMemory;
  out.screen = {width: screen.width, height: screen.height, dpr: window.devicePixelRatio};
  out.timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  out.timeZoneOffsetMin = new Date().getTimezoneOffset();
  out.languages = navigator.languages;
  const hi = navigator.userAgentData
    ? await navigator.userAgentData.getHighEntropyValues(["uaFullVersion", "fullVersionList", "wow64"])
    : null;
  out.uaFullVersion = hi && hi.uaFullVersion;
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl");
  const dbg = gl.getExtension("WEBGL_debug_renderer_info");
  out.webglVendor = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);
  out.webglRenderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
  const c2 = document.createElement("canvas");
  c2.width = 280; c2.height = 60;
  const g = c2.getContext("2d");
  g.textBaseline = "top"; g.font = "14px Arial";
  g.fillStyle = "#f60"; g.fillRect(5, 5, 80, 30);
  g.fillStyle = "#069"; g.fillText("fp-vb-3", 8, 8);
  const url = c2.toDataURL();
  out.canvasSha256 = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(url))
    .then((buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join(""));
  return out;
}
"""


def read_proof(port: int, *, check_exit: bool = True) -> dict[str, Any]:
    """通过 CDP 读内核实际呈现的指纹 + cloudflare trace 出口 IP/loc。

    deviceMemory 仅记录不判失败（这版内核不伪装，读真机，见文档第 6 节）。
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://example.com", wait_until="domcontentloaded", timeout=30000)
        fp = page.evaluate(_PROOF_JS)
        if check_exit:
            try:
                page.goto("https://www.cloudflare.com/cdn-cgi/trace",
                          wait_until="domcontentloaded", timeout=20000)
                text = page.inner_text("body")
                trace: dict[str, str] = {}
                for line in text.splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        if k in {"ip", "loc", "colo", "uag"}:
                            trace[k] = v
                fp["exit"] = trace
            except Exception as e:  # noqa: BLE001
                fp["exit"] = {"error": repr(e)[:160]}
        browser.close()
    return fp


def expected_view(env_id: int) -> dict[str, Any]:
    """从 worker 的 virtual.dat 读出期望值（验收对照）。"""
    path = vbf.worker_dir(env_id) / "virtual.dat"
    data = json.loads(path.read_text(encoding="utf-8"))
    env = next(u for u in data["users"] if int(u["id"]) == int(env_id))
    tz = (env.get("time-zone") or {}).get("utc") or ""
    tz_aliases = {"America/Santa_Isabel": "America/Tijuana"}
    return {
        "uaFullVersion": (env.get("ua-full-version") or {}).get("value"),
        "hardwareConcurrency": (env.get("cpu") or {}).get("value"),
        "webglVendor": (env.get("webgl") or {}).get("vendor"),
        "webglRenderer": (env.get("webgl") or {}).get("render"),
        "screen": f"{(env.get('screen') or {}).get('width')}x{(env.get('screen') or {}).get('height')}",
        "timeZone": tz,
        "timeZoneCanonical": tz_aliases.get(tz, tz),
    }


def compare_proof(fp: dict[str, Any], env_id: int) -> dict[str, Any]:
    """对照 virtual.dat 判定指纹是否生效；deviceMemory 不参与判定。"""
    want = expected_view(env_id)
    got_screen = f"{fp['screen']['width']}x{fp['screen']['height']}"
    checks = {
        "uaFullVersion": fp.get("uaFullVersion") == want["uaFullVersion"],
        "hardwareConcurrency": fp.get("hardwareConcurrency") == want["hardwareConcurrency"],
        "webglVendor": fp.get("webglVendor") == want["webglVendor"],
        "webglRenderer": fp.get("webglRenderer") == want["webglRenderer"],
        "screen": got_screen == want["screen"],
        "timeZone": fp.get("timeZone") in {want["timeZone"], want["timeZoneCanonical"]}
                    and bool(fp.get("timeZone")),
    }
    return {"expected": want, "pass": checks, "allPass": all(checks.values())}
