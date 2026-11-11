"""Flova 并行邀请补分（按单次报价 B，无固定保底）。

调用时机：``flova_dispatch`` 判定全池没有任何账号付得起本次预算 B。

补分策略（见 flova-fleet policy.json）：

- ``B <= signup_liquid_credits``（默认 100）：新子号注册即有流动积分可付，
  并行注册，让子号付款。
- ``B > signup_liquid_credits``：母号付款。需要
  ``n = ceil((B - 母号余额) / 200)`` 个邀请奖励，n 个注册**并行执行**、
  不等待间隔。剩余名额不够时切换合格接班人（满 7 天 + 导出 + keyed）。
- 接班人未就绪：ok=false、do_not_generate=true，不烧最后名额。

用法::

    python flova_invite.py plan --budget 200 --profile prod
    python flova_invite.py ensure --budget 200 --profile prod
    python flova_invite.py candidates

注册浏览器默认走 Virtual Browser（VB，``FLOVA_BROWSER_BACKEND=vb``）：内核直拉 +
``--worker-id`` + worker 目录 ``virtual.dat`` 指纹，启动前按目标国家重写指纹（每次
随机、自洽）并以无痕 + 对应代理/语言启动，没有 AdsPower 免费版「每日打开次数」限额。
AdsPower 本地 API 保留为回退（``FLOVA_BROWSER_BACKEND=adspower``）。两种后端都返回
统一的 :class:`Worker`，Playwright 经 CDP 端口驱动同一套注册流程。
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, NamedTuple

import requests

HOME = Path(os.environ.get("USERPROFILE", Path.home()))
MAILBOX_API = os.environ.get("FLOVA_MAILBOX_API", "http://119.29.187.184:18793")
FLOVA_BIN = r"C:\Users\shipi\AppData\Local\Programs\flova\flova.exe"
API_BASE = "https://service.flova.ai/api/agent/v2"
REGISTRY = HOME / ".flova" / "registry.json"
LOCK_PATH = HOME / ".flova" / "invite.lock"
# 优先用本仓库策略副本；不存在时回退到 flova-fleet 的 fleet policy。
REPO_POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "flova-credits-policy.json"
FLEET_POLICY_PATH = HOME / ".agents" / "skills" / "flova-fleet" / "references" / "policy.json"
POLICY_PATH = REPO_POLICY_PATH if REPO_POLICY_PATH.exists() else FLEET_POLICY_PATH
# ---- AdsPower 本地 API（复用已有免费版配置，不创建/不删除配置）----
ADS_DEFAULT_BASE = "http://127.0.0.1:50325"
ADS_DEFAULT_EXE = r"C:\Program Files\AdsPower Global\AdsPower Global.exe"
ADS_DEFAULT_PROFILE_IDS = ("k1i4dj3c", "k1hhj2u")
ADS_PAID_MSG = "This feature is only available in paid subscriptions."
MCP_DIR = HOME / ".flova-mcp"
WEB_PROFILES_DIR = MCP_DIR / "browser-profiles"


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def auto_invite_enabled() -> bool:
    return os.environ.get("FLOVA_AUTO_INVITE", "1").strip() not in ("0", "false", "no")


def load_policy() -> dict[str, Any]:
    if POLICY_PATH.exists():
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return {"mother": {"default_profile": "prod"}, "dispatch": {}}


def signup_liquid() -> float:
    return float(load_policy().get("dispatch", {}).get("signup_liquid_credits", 100))


def profile_from_ref(ref: str | None) -> str:
    s = str(ref or "")
    if s.startswith("flova-profile:"):
        return s.split(":", 1)[1]
    return s


def active_mother_profile() -> str:
    reg = load_registry()
    p = str(reg.get("active_mother_profile") or "").strip()
    if p:
        return p
    for a in reg.get("accounts", []):
        if a.get("role") == "mother":
            got = profile_from_ref(a.get("api_key_ref"))
            if got:
                return got
    return str(load_policy().get("mother", {}).get("default_profile", "prod"))


def resolve_inviter(profile: str) -> str:
    """Default/prod 解析为当前活跃母号（可能已切到接班人）。"""
    default = str(load_policy().get("mother", {}).get("default_profile", "prod"))
    if profile in (default, "prod", "", None):
        return active_mother_profile()
    return profile


def load_registry() -> dict[str, Any]:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {"version": "3", "accounts": []}


def save_registry(reg: dict[str, Any]) -> None:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(REGISTRY)


def min_keep_credits() -> float:
    """余额低于此值的号移除。0 分视为封号，同样移除。"""
    return float(load_policy().get("account", {}).get("min_keep_credits", 25))


def _cli_default_profile() -> str | None:
    try:
        out = subprocess.run(
            [FLOVA_BIN, "profile", "show"],
            capture_output=True, text=True, timeout=20,
        )
        data = json.loads(out.stdout).get("data") or {}
        return data.get("profile") or data.get("name")
    except Exception:
        return None


def _remove_cli_profile(name: str) -> None:
    default = _cli_default_profile()
    if default == name:
        others = sorted(p for p in known_profiles() if p != name)
        if not others:
            raise RuntimeError(f"refuse to remove the only profile {name}")
        use = subprocess.run(
            [FLOVA_BIN, "profile", "use", others[0]],
            capture_output=True, text=True, timeout=20,
        )
        if use.returncode != 0:
            raise RuntimeError((use.stderr or use.stdout or "profile use failed")[:240])
    rm = subprocess.run(
        [FLOVA_BIN, "profile", "remove", name],
        capture_output=True, text=True, timeout=20,
    )
    if rm.returncode != 0:
        raise RuntimeError((rm.stderr or rm.stdout or "profile remove failed")[:240])


def prune_low_accounts() -> dict[str, Any]:
    """移除余额 < min_keep（默认 25）的 CLI profile，并从账本删掉。

    余额为 0 记为封号（banned_zero_balance）。读不到余额的号不删。
    """
    from flova_pricing import get_balance

    threshold = min_keep_credits()
    removed: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for name in sorted(known_profiles()):
        try:
            bal = float(get_balance(name))
        except Exception as e:
            errors.append({"profile": name, "error": str(e)[:200]})
            continue
        if bal < threshold:
            reason = "banned_zero_balance" if bal == 0 else "below_min_keep"
            try:
                _remove_cli_profile(name)
            except Exception as e:
                errors.append({"profile": name, "balance": bal, "reason": reason, "error": str(e)[:200]})
                continue
            removed.append({"profile": name, "balance": bal, "reason": reason})
        else:
            kept.append({"profile": name, "balance": bal})

    removed_names = {r["profile"] for r in removed}
    if removed_names:
        reg = load_registry()
        reg["accounts"] = [
            a for a in reg.get("accounts", [])
            if profile_from_ref(a.get("api_key_ref")) not in removed_names
        ]
        if reg.get("active_mother_profile") in removed_names:
            reg["active_mother_profile"] = kept[0]["profile"] if kept else ""
        reg["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_registry(reg)
    return {
        "threshold": threshold,
        "removed": removed,
        "kept": kept,
        "errors": errors,
    }


def known_emails(reg: dict[str, Any] | None = None) -> set[str]:
    reg = reg or load_registry()
    return {str(a.get("email", "")).lower() for a in reg.get("accounts", []) if a.get("email")}


def known_profiles() -> set[str]:
    try:
        out = subprocess.run(
            [FLOVA_BIN, "profile", "list"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(out.stdout)["data"]
        return {p["name"] for p in data}
    except Exception:
        return {a.get("api_key_ref", "").split(":")[-1]
                for a in load_registry().get("accounts", [])
                if a.get("api_key_ref")}


def next_child_profiles(n: int) -> list[str]:
    """一次性预分配 n 个不重名 kid profile（并行注册防撞名）。"""
    have = known_profiles()
    out: list[str] = []
    k = 1
    while len(out) < n:
        name = f"kid{k}"
        if name not in have:
            out.append(name)
            have.add(name)
        k += 1
    return out


def mailbox_order_key(m: dict[str, Any]) -> tuple[int, float, str]:
    """邮箱挑选顺序的纯排序 key（pick_mailboxes / invite_batch.pick_fresh 共用）。

    1. 没有导入时间（``imported_at`` 缺失、None、""、0 或非正数/非数字）的是
       最早一批，排在所有数字时间戳之前。
    2. 有数字时间戳的按 ``imported_at`` 从早到晚（先导入先注册）。
    3. 同档按地址小写升序，保证顺序稳定。
    """
    try:
        ts = float(m.get("imported_at"))
    except (TypeError, ValueError):
        ts = 0.0
    address = str(m.get("address") or "").strip().lower()
    if ts > 0:
        return (1, ts, address)
    return (0, 0.0, address)


def pick_mailboxes(n: int) -> list[dict[str, str]]:
    """一次性取 n 个未用过的活跃 outlook 邮箱（并行注册防撞邮箱）。

    先收集全部合格邮箱，按 mailbox_order_key 排序（无导入时间的最早一批先消费，
    再按 imported_at 先导入先注册），再取前 n 个，不按接口返回顺序直接取。
    邮箱池 flova.registered 标记从不回写，必须额外用 signals.flova_verification_seen
    排除已收过验证码的旧邮箱。
    """
    r = requests.get(
        f"{MAILBOX_API}/v1/mailboxes",
        params={"provider": "outlook", "active": 1},
        timeout=30,
    )
    r.raise_for_status()
    used = known_emails()
    eligible: list[dict[str, Any]] = []
    for m in r.json().get("mailboxes", []):
        addr = (m.get("address") or "").strip()
        key = m.get("key")
        reg = m.get("registration") or {}
        flova = reg.get("flova") or {}
        signals = reg.get("signals") or {}
        if not addr or not key:
            continue
        if flova.get("registered") is True:
            continue
        if signals.get("flova_verification_seen"):   # 已收过 Flova 验证码 = 已注册/被封旧号
            continue
        if addr.lower() in used:
            continue
        if not m.get("active") or m.get("expired"):
            continue
        eligible.append(m)
    eligible.sort(key=mailbox_order_key)
    picked = [{"key": m["key"], "address": (m.get("address") or "").strip()}
              for m in eligible[:n]]
    if len(picked) < n:
        raise RuntimeError(f"need {n} unused active outlook mailboxes, got {len(picked)}")
    return picked


# ----------------------------- 浏览器后端抽象（VB 默认 / AdsPower 回退）------

class Worker(NamedTuple):
    """统一浏览器 worker。

    id：后端内的唯一标识（VB 是 int worker id；AdsPower 是 profile id 字符串）。
    name 仅展示用。launch() 返回 CDP 端口，stop() 幂等关闭。
    """
    id: Any
    name: str

    @property
    def profile_id(self) -> Any:
        # 兼容旧调用点 worker.profile_id；VB 即 int worker id，AdsPower 即 profile id。
        return self.id


# 旧名保留为别名，供 invite_manual 等的类型注解与外部引用向后兼容。
AdsPowerSession = Worker


def browser_backend() -> str:
    """``FLOVA_BROWSER_BACKEND=vb|adspower``，默认 vb。"""
    b = os.environ.get("FLOVA_BROWSER_BACKEND", "vb").strip().lower()
    return "adspower" if b == "adspower" else "vb"


def next_workers(n: int) -> list[Worker]:
    """返回至多 n 个互不相同、可并行的 worker（不创建/删除任何浏览器资源）。

    n 大于池大小时只返回池大小个 worker，由 ``_run_parallel`` 分波复用：同一
    worker id 绝不并发（VB 同一 user-data-dir 有 Chromium 锁）。
    """
    backend = browser_backend()
    if backend == "adspower":
        ensure_ads_api()
        pool = ads_profile_pool()
        k = max(0, min(int(n), len(pool)))
        return [Worker(id=pid, name=pid) for pid in pool[:k]]
    import vb_backend as vbb
    pool = vbb.worker_pool()
    k = max(0, min(int(n), len(pool)))
    return [Worker(id=w.id, name=w.name) for w in pool[:k]]


def launch_worker(worker_id: Any) -> int:
    """启动一个 worker，返回 CDP debug 端口（int）。

    默认（``FLOVA_VB_WINDOW=minimized``）VB 窗口启动后立即最小化到任务栏：
    不弹窗、不抢焦点，注册全程后台跑；只有出现需要人工的滑块验证码时才由
    ``invite_manual.settle_captcha`` 把窗口恢复到前台。``FLOVA_VB_WINDOW=normal``
    恢复旧的可见窗口行为。
    """
    if browser_backend() == "adspower":
        return launch_ads(str(worker_id))
    import vb_backend as vbb
    port = vbb.launch_worker(int(worker_id), country_code=vbb.country(),
                             incognito=True, rotate=True)
    if vbb.window_mode() == "minimized":
        vbb.set_window_state(port, "minimized")
    return port


def stop_worker(worker_id: Any) -> None:
    """幂等关闭一个 worker（只关浏览器/进程树，绝不删除配置或 worker 目录）。"""
    if browser_backend() == "adspower":
        stop_ads(str(worker_id))
        return
    import vb_backend as vbb
    vbb.stop_worker(int(worker_id))


def fingerprint_rotated(worker_id: Any) -> bool:
    """本次启动是否换了指纹。

    VB：启动前总会重写 virtual.dat（每次随机）→ True。AdsPower：看本次
    new-fingerprint 是否被付费墙挡下（挡下为 False，沿用旧指纹继续）。
    """
    if browser_backend() == "adspower":
        return bool(_ADS_FINGERPRINT.get(str(worker_id), False))
    return True


# 记录每个 AdsPower profile 本次启动 new-fingerprint 是否成功（同 profile 不会并发，见分波）。
_ADS_FINGERPRINT: dict[str, bool] = {}


def ads_api_base() -> str:
    base = os.environ.get("ADSPOWER_API_BASE", "").strip()
    if base:
        return base.rstrip("/")
    port = os.environ.get("ADSPOWER_API_PORT", "").strip()
    if port:
        return f"http://127.0.0.1:{port}"
    return ADS_DEFAULT_BASE


def ads_profile_pool() -> list[str]:
    """可复用的 AdsPower profile id 池（免费版固定两个，可用环境变量覆盖）。"""
    raw = os.environ.get("ADSPOWER_PROFILE_IDS", "").strip()
    if raw:
        ids = [p.strip() for p in raw.split(",") if p.strip()]
        if ids:
            return ids
    return list(ADS_DEFAULT_PROFILE_IDS)


def _ads_headers() -> dict[str, str]:
    # 仅当显式提供 ADSPOWER_API_KEY 时带 Bearer；未配置就不发任何认证头。
    key = os.environ.get("ADSPOWER_API_KEY", "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def _ads_exe_path() -> Path:
    env = os.environ.get("ADSPOWER_BROWSER_EXE", "").strip()
    if env and Path(env).is_file():
        return Path(env)
    return Path(ADS_DEFAULT_EXE)


def ensure_ads_api() -> None:
    """确保 AdsPower 本地 API 在监听（``GET /status`` 返回 code 0）。

    就绪探测不依赖 api-key（API verification 关闭时即可用）。探测失败时同进程启动
    本机 GUI（不带任何参数、不传 api-key），最多轮询 45 秒。绝不打印密钥。
    """
    base = ads_api_base()

    def _ready() -> bool:
        try:
            r = requests.get(f"{base}/status", timeout=2)
            if r.status_code != 200:
                return False
            return bool((r.json() or {}).get("code") == 0)
        except Exception:
            return False

    if _ready():
        return

    exe = _ads_exe_path()
    if not exe.is_file():
        raise RuntimeError(f"AdsPower browser exe not found: {exe}")
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [str(exe)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
    )
    deadline = time.time() + 45
    while time.time() < deadline:
        if _ready():
            return
        time.sleep(0.5)
    raise RuntimeError(f"AdsPower Local API not ready at {base} after 45s")


def _refresh_fingerprint_once(base: str, headers: dict[str, str],
                              profile_id: str) -> bool:
    """启动前尝试一次 new-fingerprint。

    code 0 → True；免费版返回“仅付费套餐可用”→ False（不拒绝启动）；其余非零
    code/网络错误抛错。``profile_id`` 必须是数组（上限 10）。绝不记录指纹值。
    """
    r = requests.post(
        f"{base}/api/v2/browser-profile/new-fingerprint",
        headers=headers,
        json={"profile_id": [profile_id]},
        timeout=30,
    )
    try:
        body = r.json()
    except Exception as e:
        raise RuntimeError(
            f"AdsPower new-fingerprint bad response http={r.status_code}: "
            f"{r.text[:200]}"
        ) from e
    code = body.get("code")
    msg = str(body.get("msg") or "")
    if code == 0:
        return True
    if ADS_PAID_MSG in msg:
        return False
    raise RuntimeError(
        f"AdsPower new-fingerprint failed http={r.status_code} code={code}: {msg[:200]}"
    )


def launch_ads(profile_id: str) -> int:
    """启动一个已有 AdsPower profile，返回 CDP debug 端口（int）。

    先尝试一次 new-fingerprint（免费版拒绝时记 fingerprint_refreshed=False 继续），
    再 ``GET /api/v1/browser/start?ip_tab=0&open_tabs=1``。非付费指纹提示之外的非零
    code 抛 RuntimeError（带 http/code/截断 msg，不含任何密钥）。
    """
    base = ads_api_base()
    headers = _ads_headers()
    refreshed = False
    try:
        refreshed = _refresh_fingerprint_once(base, headers, profile_id)
    finally:
        _ADS_FINGERPRINT[profile_id] = refreshed

    r = requests.get(
        f"{base}/api/v1/browser/start",
        params={"user_id": profile_id, "ip_tab": 0, "open_tabs": 1},
        headers=headers,
        timeout=60,
    )
    try:
        body = r.json()
    except Exception as e:
        raise RuntimeError(
            f"AdsPower start bad response http={r.status_code}: {r.text[:200]}"
        ) from e
    code = body.get("code")
    if code != 0:
        msg = str(body.get("msg") or "")[:240]
        raise RuntimeError(
            f"AdsPower start failed http={r.status_code} code={code}: {msg}"
        )
    data = body.get("data") or {}
    port = data.get("debug_port")
    if port is None or str(port).strip() == "":
        raise RuntimeError("AdsPower start response missing data.debug_port")
    return int(str(port))


def stop_ads(profile_id: str) -> None:
    """只关闭浏览器：``GET /api/v1/browser/stop?user_id=<id>``。

    “User_id is not open”（已关闭）与网络错误都视为成功。绝不删除 profile。
    """
    base = ads_api_base()
    try:
        requests.get(
            f"{base}/api/v1/browser/stop",
            params={"user_id": profile_id},
            headers=_ads_headers(),
            timeout=30,
        )
    except requests.RequestException:
        return


def wait_cdp(port: int, timeout_s: float = 45) -> None:
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return
            last = r.status_code
        except Exception as e:
            last = str(e)[:80]
        time.sleep(0.5)
    raise RuntimeError(f"CDP :{port} not ready ({last})")


class _Lock:
    def __init__(self, path: Path):
        self.path = path
        self.fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "a+", encoding="utf-8")
        try:
            if os.name == "nt":
                import msvcrt
                if self.fh.tell() == 0:
                    self.fh.write("1")
                    self.fh.flush()
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            self.fh.close()
            self.fh = None
            raise RuntimeError("another invite is already running") from e
        return self

    def __exit__(self, *exc):
        if not self.fh:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self.fh.close()
        self.fh = None


def _stats_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return raw.get("data") or raw


def invite_snapshot(profile: str = "prod") -> dict[str, Any]:
    from flova_pricing import get_balance, get_invite_stats_web

    stats = _stats_payload(get_invite_stats_web(profile=profile))
    reg = stats.get("registration_reward") or {}
    elig = stats.get("eligibility") or {}
    return {
        "profile": profile,
        "balance": get_balance(profile),
        "promotion_code": stats.get("promotion_code"),
        "rewarded_count": int(reg.get("rewarded_count") or 0),
        "max_invitees": int(reg.get("max_invitees") or 20),
        "credit_reward_num": int(reg.get("credit_reward_num") or 200),
        "invite_reward_disabled": bool(
            elig.get("invite_reward_disabled")
            or stats.get("invite_reward_disabled")
        ),
        "eligibility": elig,
    }


def invite_requirement(*, budget: float, mother_profile: str) -> dict[str, Any]:
    """为本次预算 B 计算补分方式，不注册。

    B <= signup_liquid：新子号即可付款，n=1（子号付款）。
    B > signup_liquid：母号付款，n=ceil((B-母号余额)/200)，受剩余名额限制。
    """
    snap = invite_snapshot(mother_profile)
    liquid = signup_liquid()
    remaining = max(0, snap["max_invitees"] - snap["rewarded_count"])

    if budget <= liquid:
        return {
            "payer": "new_child",
            "n": 1,
            "remaining_slots_needed": 1,
            "remaining_slots": remaining,
            "slots_ok": remaining >= 1 and not snap["invite_reward_disabled"],
            **snap,
        }

    n = max(0, math.ceil((float(budget) - float(snap["balance"]))
                         / max(1, snap["credit_reward_num"])))
    n = max(n, 0)
    return {
        "payer": "mother",
        "n": n,
        "remaining_slots_needed": n,
        "remaining_slots": remaining,
        "slots_ok": n == 0 or (remaining >= n and not snap["invite_reward_disabled"]),
        **snap,
    }


def successor_candidates() -> list[dict[str, Any]]:
    """Probe keyed children for invite eligibility (web session + 7d + export)."""
    inviter = active_mother_profile()
    out: list[dict[str, Any]] = []
    for a in load_registry().get("accounts", []):
        role = a.get("role")
        if role in ("mother", "retired_mother"):
            continue
        pref = profile_from_ref(a.get("api_key_ref"))
        if not pref or pref == inviter:
            continue
        item: dict[str, Any] = {
            "profile": pref,
            "email": a.get("email"),
            "role": role,
            "state": a.get("state"),
            "eligible": False,
            "blockers": [],
        }
        if a.get("state") != "keyed" or not pref:
            item["blockers"] = ["not_keyed"]
            out.append(item)
            continue
        try:
            snap = invite_snapshot(pref)
        except Exception as e:
            item["blockers"] = ["no_web_session"]
            item["error"] = str(e)[:200]
            item["hint"] = f"node C:/Users/shipi/.flova-mcp/login-web.js --profile {pref}"
            out.append(item)
            continue
        elig = snap.get("eligibility") or {}
        remaining = max(0, snap["max_invitees"] - snap["rewarded_count"])
        blockers: list[str] = []
        if not elig.get("account_age_7d"):
            blockers.append("account_age_7d")
        if not elig.get("has_export"):
            blockers.append("no_export")
        if snap.get("invite_reward_disabled"):
            blockers.append("invite_reward_disabled")
        if remaining <= 0:
            blockers.append("no_invite_slots")
        item.update({
            "balance": snap["balance"],
            "remaining_invitees": remaining,
            "promotion_code": snap.get("promotion_code"),
            "eligibility": elig,
            "blockers": blockers,
            "eligible": not blockers,
        })
        out.append(item)
    return out


def pick_successor(*, target: float) -> dict[str, Any] | None:
    for c in successor_candidates():
        if not c.get("eligible"):
            continue
        max_after = float(c.get("balance") or 0) + int(c.get("remaining_invitees") or 0) * 200
        if max_after >= target:
            return c
    return None


def promote_mother(new_profile: str) -> None:
    """账本切换活跃母号。不改 CLI default_profile（仍建议钉在 prod）。"""
    reg = load_registry()
    for a in reg.get("accounts", []):
        pref = profile_from_ref(a.get("api_key_ref"))
        if a.get("role") == "mother" and pref != new_profile:
            a["role"] = "retired_mother"
        if pref == new_profile:
            a["role"] = "mother"
    reg["active_mother_profile"] = new_profile
    reg["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_registry(reg)


def _poll_otp(mailbox_key: str, t0: float, tries: int = 14) -> str:
    for i in range(tries):
        try:
            r = requests.get(
                f"{MAILBOX_API}/v1/mailboxes/{mailbox_key}/messages",
                params={"force": 1, "limit": 8},
                timeout=40,
            )
            msgs = r.json().get("messages") or []
        except Exception:
            msgs = []
        for m in msgs:
            if m.get("sender_address") != "notifications@account.flova.ai":
                continue
            if float(m.get("received_epoch") or 0) < t0 - 30:
                continue
            uid = requests.utils.quote(m["message_id"], safe="")
            body = requests.get(
                f"{MAILBOX_API}/v1/mailboxes/{mailbox_key}/messages/{uid}",
                params={"format": "text"},
                timeout=40,
            ).text
            found = re.findall(r"(?<!\d)(\d{6})(?!\d)", body)
            if found:
                return found[0]
        time.sleep(8)
    raise RuntimeError("OTP not received from mailbox pool")


def _click_text(page, text: str) -> bool:
    return bool(page.evaluate(
        """(t) => {
          const el = [...document.querySelectorAll("button,a,[role=button],div,span")]
            .find(e => (e.innerText || "").trim().replace(/\\s+/g, " ") === t && e.offsetParent !== null);
          if (el) { el.click(); return true; }
          return false;
        }""",
        text,
    ))


# ----------------------------- 网页会话采纳（cookie 迁移） -----------------

def _is_flova_domain(domain: str | None) -> bool:
    d = str(domain or "").lower().lstrip(".")
    return d == "flova.ai" or d.endswith(".flova.ai")


def _normalize_storage_cookie(c: dict) -> dict:
    """把任意来源 cookie 归一化成 storage_state/add_cookies 接受的形状。"""
    c = dict(c)
    c.setdefault("path", "/")
    try:
        if float(c.get("expires") or 0) <= 0:
            c["expires"] = -1.0
        else:
            c["expires"] = float(c["expires"])
    except (TypeError, ValueError):
        c["expires"] = -1.0
    c.setdefault("httpOnly", False)
    c.setdefault("secure", True)
    if c.get("sameSite") not in {"Strict", "Lax", "None"}:
        # CDP 可能给 "Unspecified"，storage_state 只接受这三个值。
        c["sameSite"] = "Lax"
    return c


def _cdp_flova_cookies(context) -> list[dict]:
    """经 CDP Network.getAllCookies 读全部 cookie，只留 flova 域并归一化。

    VirtualBrowser 内核经 CDP 接入时，Playwright 的 context.cookies() 实测会
    返回空罐（Storage.getCookies 同样为空），只有原始 CDP Network.getAllCookies
    能拿到页面真实 cookie。优先用本函数，context.cookies() 作为回退。
    """
    page = None
    try:
        for pg in context.pages:
            try:
                if "flova.ai" in (pg.url or ""):
                    page = pg
                    break
            except Exception:  # noqa: BLE001
                continue
        if page is None and context.pages:
            page = context.pages[0]
        if page is None:
            return []
        sess = context.new_cdp_session(page)
        raw = sess.send("Network.getAllCookies").get("cookies", [])
    except Exception:  # noqa: BLE001
        return []
    out = []
    for c in raw:
        if not _is_flova_domain(c.get("domain")):
            continue
        out.append(_normalize_storage_cookie(c))
    return out


def context_flova_cookies(context) -> list[dict]:
    """读 context 里的 flova cookie：先 Playwright，空则回退原始 CDP。"""
    try:
        pw = [_normalize_storage_cookie(dict(c))
              for c in context.cookies() if _is_flova_domain(c.get("domain"))]
    except Exception:  # noqa: BLE001
        pw = []
    if pw:
        return pw
    return _cdp_flova_cookies(context)


def page_logged_in(page) -> dict[str, Any]:
    """在页面里发 get_user_info（与网站自身请求完全同环境）。

    无论会话载体是 cookie 还是 localStorage 里的 Bearer 令牌，页面内 fetch 都会
    自动带上，避免「迁移时只搬 cookie、漏了 localStorage 令牌」导致的假未登录。
    返回 {http_ok, code, email, user_id}；失败返回 {}。
    """
    try:
        res = page.evaluate(
            """async () => {
                try {
                  const r = await fetch(
                    'https://service.flova.ai/api/v2/user/get_user_info',
                    {method:'POST',
                     headers:{'content-type':'application/json'},
                     body:'{}', credentials:'include'});
                  const j = await r.json().catch(()=>({}));
                  const d = j && j.data ? j.data : {};
                  return {http_ok:r.ok, code:j.code,
                          email:d.email || null, user_id:d.user_id || null};
                } catch (e) { return {error:String(e).slice(0,160)}; }
              }""")
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(res, dict) or res.get("error"):
        return {}
    return res


def page_auth_storage(page) -> dict[str, Any] | None:
    """读 localStorage 的 videoagent-auth-storage（不返回令牌明文，只给形态）。

    登录成功后 state.user 非空。供判断会话是否同时依赖 localStorage。
    """
    try:
        return page.evaluate(
            """() => {
                const raw = localStorage.getItem('videoagent-auth-storage');
                if (!raw) return null;
                try {
                  const j = JSON.parse(raw);
                  const u = j && j.state ? j.state.user : null;
                  return {present:true, hasUser:!!u,
                          userKeys:u?Object.keys(u):[]};
                } catch (e) { return {present:true, parseError:String(e).slice(0,80)}; }
              }""")
    except Exception:  # noqa: BLE001
        return None


def _system_chrome() -> str:
    """与 web-session.js candidateBrowsers 同顺序的系统 Chrome/Edge。"""
    cands = [
        os.environ.get("FLOVA_CHROME_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in cands:
        if c and Path(c).is_file():
            return c
    raise RuntimeError("No system Chrome/Edge found. Set FLOVA_CHROME_PATH.")


def _web_get_user_info(context) -> dict[str, Any]:
    """web-session.js getUserInfo 的 Python 等价：返回 code/email（不打印）。"""
    r = context.request.post(
        "https://service.flova.ai/api/v2/user/get_user_info",
        headers={"content-type": "application/json"},
        data="{}",
    )
    try:
        j = r.json()
    except Exception:
        j = {}
    data = j.get("data") or {}
    return {"http_ok": r.ok, "code": j.get("code"),
            "email": data.get("email"), "user_id": data.get("user_id")}


def _source_flova_page(source_context):
    """在来源 context 里找一个 flova 页面；没有就新开一个。"""
    try:
        for pg in source_context.pages:
            try:
                if "flova.ai" in (pg.url or ""):
                    return pg
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    try:
        pg = source_context.new_page()
        pg.goto("https://www.flova.ai/en/", wait_until="domcontentloaded", timeout=45000)
        return pg
    except Exception:  # noqa: BLE001
        return None


def _dump_local_storage(page) -> dict[str, str]:
    try:
        return page.evaluate(
            """() => {
                const o = {};
                for (let i = 0; i < localStorage.length; i++) {
                  const k = localStorage.key(i);
                  o[k] = localStorage.getItem(k);
                }
                return o;
              }""") or {}
    except Exception:  # noqa: BLE001
        return {}


# 只迁移可能承载会话的 localStorage 前缀/键，避免把纯统计标识也搬过去。
_LS_AUTH_HINTS = ("auth", "token", "session", "credential", "user", "login")


def adopt_web_session(profile_name: str, source_context, *,
                      expected_email: str | None = None,
                      playwright=None, proxy_server: str | None = None) -> dict[str, Any]:
    """把一个**已登录同账号**的浏览器 context 的会话采纳到
    ``~/.flova-mcp/browser-profiles/<profile_name>``。

    同时迁移两种会话载体（flova 网页可能用其中任意一种）：
      1. flova 域 cookie：经 Playwright 读，空则回退原始 CDP
         ``Network.getAllCookies``（VirtualBrowser 内核下 Playwright 罐为空）。
      2. www.flova.ai 的 localStorage 鉴权条目（如 ``videoagent-auth-storage``，
         登录令牌可能放这里并以 Bearer 发送）；通过 init script 在目标页面脚本
         运行前注入，首次导航后由 Chrome 持久化进 profile。
    验证在目标里打开 flova 页面、用**页面内 fetch** 调 get_user_info（cookie 与
    localStorage 都会带上），必须 code==0 且邮箱 == expected_email。失败立刻清空
    cookie + localStorage 并抛错，不留半成品。
    绝不拷贝 Cookies sqlite——DPAPI 加密键不匹配。
    """
    cookies = context_flova_cookies(source_context)
    if not cookies:
        raise RuntimeError("no flova cookies in source context")

    src_page = _source_flova_page(source_context)
    ls_all = _dump_local_storage(src_page) if src_page is not None else {}
    ls_auth = {k: v for k, v in ls_all.items()
               if any(h in str(k).lower() for h in _LS_AUTH_HINTS)}

    own_pw = playwright is None
    if own_pw:
        from playwright.sync_api import sync_playwright
        playwright = sync_playwright().start()
    target = None
    verify_page = None
    try:
        target_dir = WEB_PROFILES_DIR / profile_name
        target_dir.mkdir(parents=True, exist_ok=True)
        launch_kwargs: dict[str, Any] = dict(
            executable_path=_system_chrome(),
            headless=True,
            args=["--no-default-browser-check", "--no-first-run",
                  "--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 860},
        )
        # 采纳验证走与登录同一个出口代理：登录态若对 IP 敏感，换国内直连 IP 验证
        # 可能立刻把刚建的会话冲掉。proxy_server 形如 http://127.0.0.1:7897。
        if proxy_server:
            launch_kwargs["proxy"] = {"server": proxy_server}
        target = playwright.chromium.launch_persistent_context(
            str(target_dir), **launch_kwargs)
        target.add_cookies(cookies)
        if ls_auth:
            literal = json.dumps(ls_auth, ensure_ascii=False).replace("</", "<\\/")
            target.add_init_script(
                "(()=>{try{const o=%s;"
                "if(location.hostname.endsWith('flova.ai')){"
                "for(const k in o){localStorage.setItem(k,o[k]);}}}catch(e){}})();"
                % literal
            )

        verify_page = target.new_page()
        verify_page.goto("https://www.flova.ai/en/",
                         wait_until="domcontentloaded", timeout=45000)
        # 前端水合/令牌恢复可能是异步的，轮询几轮。
        info: dict[str, Any] = {}
        for _ in range(6):
            info = page_logged_in(verify_page)
            if info.get("code") == 0 and info.get("email"):
                break
            time.sleep(1.5)

        email = info.get("email")
        email_match = (
            not expected_email
            or (bool(email)
                and str(email).lower() == str(expected_email).lower())
        )
        if info.get("code") != 0 or not email_match:
            # 不保留任何导入的会话：cookie 整罐清空 + localStorage 清空。
            try:
                target.clear_cookies()
            except Exception:  # noqa: BLE001
                pass
            try:
                verify_page.evaluate("()=>localStorage.clear()")
            except Exception:  # noqa: BLE001
                pass
            if info.get("code") != 0:
                err = RuntimeError("FLOVA_WEB_UNAUTHENTICATED")
                err.code = "FLOVA_WEB_UNAUTHENTICATED"
            else:
                err = RuntimeError("FLOVA_WEB_EMAIL_MISMATCH")
                err.code = "FLOVA_WEB_EMAIL_MISMATCH"
            raise err

        # 确保 videoagent-auth-storage 拥有合法的 user，防止前端 UI 鉴权未水合时重定向跳出工作台
        try:
            auth_val = json.dumps({"state": {"user": {
                "email": email, "user_id": info.get("user_id")
            }}, "version": 0})
            verify_page.evaluate(
                """(val) => {
                    try {
                        const raw = localStorage.getItem('videoagent-auth-storage');
                        const parsed = raw ? JSON.parse(raw) : {};
                        if (!parsed.state || !parsed.state.user) {
                            localStorage.setItem('videoagent-auth-storage', val);
                        }
                    } catch(e) {}
                }""",
                auth_val,
            )
        except Exception:
            pass
        return {"profile": profile_name, "email": email,
                "user_id": info.get("user_id"),
                "migrated_localstorage": sorted(ls_auth.keys())}
    finally:
        if verify_page is not None:
            try:
                verify_page.close()
            except Exception:  # noqa: BLE001
                pass
        if target is not None:
            target.close()
        if own_pw:
            playwright.stop()


def _begin_email_auth(page, *, signup: bool) -> None:
    """打开「Email 登录/注册」面板。signup=True 走邀请落地页 CTA。"""
    time.sleep(2)
    if signup:
        _click_text(page, "Sign up for 300 credits")
        time.sleep(2)
    else:
        clicked = (_click_text(page, "Sign in")
                   or _click_text(page, "Sign In")
                   or _click_text(page, "Log in"))
        if not clicked:
            raise RuntimeError("sign-in entry not found")
        time.sleep(2)
    _click_text(page, "Sign in with Email")
    time.sleep(2)


def _submit_email_and_otp(page, email: str, mailbox_key: str, *,
                          signup: bool = True) -> None:
    """填邮箱 → 等 Turnstile → Continue → 收邮箱 OTP → 填入。注册/登录共用。

    检测与刷新循环只有一套实现：``invite_manual.submit_email_and_otp``。
    一看到 Turnstile 复选框且没有 token 就立刻刷新（最多 3 次，不点击复选框）；
    滑动验证（阿里云拼图）可见时等用户、不刷新。函数内 lazy import 避免与
    invite_manual 的顶层 import 形成循环。signup=False（登录）时刷新后重新打开
    的是登录面板，而不是 “Sign up for 300 credits”。
    """
    from invite_manual import submit_email_and_otp

    submit_email_and_otp(
        page, email, mailbox_key,
        fallback_url=page.url, signup=signup,
    )


def _signup_in_browser(cdp: str, email: str, invite_url: str, mailbox_key: str,
                       profile_name: str) -> str | None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(invite_url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=25000)
        except Exception:
            pass

        _begin_email_auth(page, signup=True)
        _submit_email_and_otp(page, email, mailbox_key, signup=True)

        still_cta = page.evaluate("document.body.innerText.includes('Sign up for 300')")
        if still_cta:
            raise RuntimeError("still on signup CTA after OTP")

        # 浏览器关闭前把网页会话采纳进新 CLI profile（code/邮箱校验内含）。
        adopt_web_session(profile_name, ctx, expected_email=email, playwright=p)

        tok = ctx.request.post(
            "https://service.flova.ai/api/agent/v2/token",
            headers={"content-type": "application/json"},
            data=json.dumps({"name": f"auto-{int(time.time())}"}),
        )
        body = tok.json()
        token_value = (body.get("data") or {}).get("token")
        browser.close()
        return token_value


def _add_cli_profile(name: str, token: str) -> None:
    add = subprocess.run(
        [FLOVA_BIN, "--api-base", API_BASE, "profile", "add", name],
        capture_output=True, text=True, timeout=30,
    )
    login = subprocess.run(
        [FLOVA_BIN, "--profile", name, "auth", "login", "--token", token],
        capture_output=True, text=True, timeout=30,
    )
    subprocess.run([FLOVA_BIN, "profile", "use", "prod"], capture_output=True, text=True, timeout=20)
    check = subprocess.run(
        [FLOVA_BIN, "profile", "show"],
        capture_output=True, text=True, timeout=20,
    )
    if add.returncode != 0:
        raise RuntimeError(f"profile add failed: {add.stderr or add.stdout}"[:300])
    if login.returncode != 0:
        raise RuntimeError(f"auth login failed: {login.stderr or login.stdout}"[:300])
    try:
        shown = json.loads(check.stdout)
        default = (shown.get("data") or {}).get("profile")
        if default and default != "prod":
            subprocess.run([FLOVA_BIN, "profile", "use", "prod"], timeout=20)
    except Exception:
        pass


def invite_one(*, mother_profile: str, mailbox: dict[str, str],
               profile_name: str, worker: Worker) -> dict[str, Any]:
    """注册 1 个子号（资源由调用方预分配，可并行）。成功标准：拿到子号 token。

    无论成功失败（含提前返回）都在 finally 里 stop_worker 自己的 worker；VB 只
    taskkill 进程树，AdsPower 只 stop，绝不删除任何配置或 worker 目录/virtual.dat。
    """
    worker_id = worker.id
    port: int | None = None
    signup_err = None
    child_token = None
    try:
        try:
            snap0 = invite_snapshot(mother_profile)
            code = snap0["promotion_code"]
            if not code:
                return {"ok": False, "reason": "no_promotion_code",
                        "child_email": mailbox["address"]}
        except Exception as e:
            return {"ok": False, "reason": f"mother_snapshot_failed: {str(e)[:120]}",
                    "child_email": mailbox["address"]}

        invite_url = f"https://www.flova.ai/?refCode={code}"
        port = launch_worker(worker_id)
        wait_cdp(port)
        time.sleep(2)
        try:
            child_token = _signup_in_browser(
                f"http://127.0.0.1:{port}", mailbox["address"],
                invite_url, mailbox["key"], profile_name,
            )
        except Exception as e:
            signup_err = str(e)[:240]
        keyed = False
        if child_token:
            _add_cli_profile(profile_name, child_token)
            keyed = True
        return {
            "ok": bool(keyed),
            "reason": "keyed" if keyed else (signup_err or "registered_but_token_missing"),
            "child_email": mailbox["address"],
            "child_profile": profile_name if keyed else None,
            "keyed": keyed,
            "backend": browser_backend(),
            "vb_worker_id": worker_id if browser_backend() == "vb" else None,
            "ads_profile_id": worker_id if browser_backend() == "adspower" else None,
            "fingerprint_rotated": fingerprint_rotated(worker_id),
            "cdp_port": port,
        }
    finally:
        stop_worker(worker_id)


def _run_parallel(mother_profile: str, slots: list[dict[str, Any]],
                  entered: set[Any] | None = None) -> list[dict[str, Any]]:
    """分波注册：每波同时运行的 slot 各自占用池内互不相同的 worker id。

    波大小 = slots 里出现的不同 worker id 数（即 ``min(n, 池大小)``）。一波所有注册
    都结束（``invite_one`` 在 finally 里已对自己的 worker 调过 ``stop_worker`` 并返回）
    后，下一波才复用同 worker，因此同一个 worker id（同一 user-data-dir）绝不会在两个
    仍在运行的会话里。VB 没有 AdsPower 的池大小/每日限额，唯一约束是同 id 不并发。

    ``entered`` 若给出，会记录真正进入 invite_one 的 worker id，供调用方只清理
    那些因异常从未进入 invite_one（因而没被它自己 stop_worker）的孤儿浏览器。
    """
    def _run(slot: dict[str, Any]) -> dict[str, Any]:
        if entered is not None:
            entered.add(slot["worker"].id)
        return invite_one(mother_profile=mother_profile, **slot)

    wave_size = len({s["worker"].id for s in slots}) or 1
    results: list[dict[str, Any]] = []
    for start in range(0, len(slots), wave_size):
        wave = slots[start:start + wave_size]
        if len(wave) == 1:
            results.append(_run(wave[0]))
            continue
        with ThreadPoolExecutor(max_workers=len(wave)) as ex:
            futs = [ex.submit(_run, s) for s in wave]
            results.extend(f.result() for f in futs)
    return results


def _allocate_slots(n: int) -> list[dict[str, Any]]:
    mailboxes = pick_mailboxes(n)
    profiles = next_child_profiles(n)
    # next_workers 只做后端就绪检查并返回池内已有 worker（≤ 池大小），绝不创建。
    pool = next_workers(n)
    if not pool:
        raise RuntimeError(f"no {browser_backend()} worker available in pool")
    # 池比 n 小时按槽位轮转复用；真正的并发互斥由 _run_parallel 分波保证。
    return [
        {"mailbox": mb, "profile_name": prof, "worker": pool[i % len(pool)]}
        for i, (mb, prof) in enumerate(zip(mailboxes, profiles))
    ]


def _record_children(results: list[dict[str, Any]], inviter_email: str | None) -> None:
    reg = load_registry()
    known = {a.get("email", "").lower() for a in reg.get("accounts", [])}
    for r in results:
        if not r.get("ok") or not r.get("child_profile"):
            continue
        if r["child_email"].lower() in known:
            continue
        state = r.get("reason") if r.get("reason") in ("keyed", "web_session") else "keyed"
        reg.setdefault("accounts", []).append({
            "email": r["child_email"],
            "role": "child",
            "state": state,
            "invited_by": inviter_email,
            "api_key_ref": f"flova-profile:{r['child_profile']}" if state == "keyed" else None,
            # 网页会话已采纳到 MCP 持久 profile 目录（与 mother 同款记录）。
            "web_profile_ref": f"~/.flova-mcp/browser-profiles/{r['child_profile']}",
            "last_verified": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "notes": "parallel auto-invite via flova_invite.py",
        })
    reg["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_registry(reg)


def ensure_credits(*, budget: float, profile: str = "prod") -> dict[str, Any]:
    """为本次预算 B 并行邀新，直到池中有账号付得起 B。无固定保底。"""
    from flova_pricing import get_balance

    if not auto_invite_enabled():
        return {
            "ok": False, "do_not_generate": True,
            "reason": "FLOVA_AUTO_INVITE=0", "budget": float(budget),
        }

    pruned = prune_low_accounts()
    billing = resolve_inviter(profile)
    if billing not in known_profiles() and known_profiles():
        billing = active_mother_profile()
    switched = False
    successor_info: dict[str, Any] | None = None

    req = invite_requirement(budget=budget, mother_profile=billing)
    n = int(req["n"])

    # 母号自己已够（n=0）：无需注册。
    if n <= 0 and req["payer"] == "mother":
        return {
            "ok": True, "invited_this_call": 0, "do_not_generate": False,
            "billing_profile": billing, "balance": req["balance"],
            "budget": float(budget), "reason": "balance_covers_budget",
            "pruned": pruned,
        }

    with _Lock(LOCK_PATH):
        # 锁内重算（可能上一次 ensure 已补过）。
        req = invite_requirement(budget=budget, mother_profile=billing)
        n = int(req["n"])
        if n <= 0 and req["payer"] == "mother":
            return {
                "ok": True, "invited_this_call": 0, "do_not_generate": False,
                "billing_profile": billing, "balance": req["balance"],
                "budget": float(budget), "reason": "balance_covers_budget",
                "pruned": pruned,
            }

        # 名额不够：先尝试接班人，不烧旧母号最后名额。
        if not req["slots_ok"]:
            cand = pick_successor(target=budget)
            if not cand:
                return {
                    "ok": False, "do_not_generate": True,
                    "reason": "successor_required",
                    "billing_profile": billing,
                    "budget": float(budget),
                    "candidates": successor_candidates(),
                    "hint": (
                        "Current mother's remaining invite slots cannot cover this job. "
                        "No eligible successor (need 7-day account + successful export + "
                        "web session via login-web.js --profile <child>). Do not generate."
                    ),
                    "pruned": pruned,
                }
            promote_mother(cand["profile"])
            billing = cand["profile"]
            switched = True
            successor_info = cand
            req = invite_requirement(budget=budget, mother_profile=billing)
            n = int(req["n"])

        # 资源一次性预分配，然后分波注册（每波并发不超过池大小）。
        slots = _allocate_slots(max(1, n))
        entered: set[Any] = set()
        try:
            results = _run_parallel(billing, slots, entered=entered)
        finally:
            # invite_one 总会自己 stop；这里只关闭因异常从未进入 invite_one 的孤儿
            # 浏览器（stop_worker 幂等：VB taskkill 进程树、AdsPower stop），绝不删除
            # 任何配置 / worker 目录 / virtual.dat，也不让清理拖垮 ensure。
            for s in slots:
                wid = s["worker"].id
                if wid not in entered:
                    try:
                        stop_worker(wid)
                    except Exception:
                        pass
        inviter_email = next(
            (a.get("email") for a in load_registry().get("accounts", [])
             if a.get("role") == "mother"),
            None,
        )
        _record_children(results, inviter_email)

    succeeded = sum(1 for r in results if r.get("ok"))
    mother_bal = get_balance(billing)

    # 验收：按付款方判定池子里是否真的有号付得起 B。
    if req["payer"] == "mother":
        ok = mother_bal >= float(budget)
    else:
        ok = succeeded >= 1
        if ok:
            # 新子号实际余额以注册到账为准；取不到时保守判失败。
            try:
                new_profiles = [r["child_profile"] for r in results if r.get("ok")]
                ok = any(get_balance(p) >= float(budget) for p in new_profiles)
            except Exception:
                ok = False

    return {
        "ok": ok,
        "invited_this_call": succeeded,
        "parallel": True,
        "invites": results,
        "do_not_generate": not ok,
        "balance": mother_bal,
        "budget": float(budget),
        "payer": req["payer"],
        "billing_profile": billing,
        "switched_mother": switched,
        "successor": successor_info,
        "reason": "ok" if ok else (
            "invite_quota_exhausted" if not req["slots_ok"] else "invite_step_failed"
        ),
        "hint": None if ok else (
            f"Top-up incomplete for budget {budget:g}; {succeeded}/{len(results)} "
            "registrations succeeded. Do not generate."
        ),
        "pruned": pruned,
    }


# ----------------------------- 存量子号会话修复 ----------------------------

def _is_legacy_virtualbrowser_ref(ref: str | None) -> bool:
    s = str(ref or "")
    return s.startswith("virtualbrowser-worker:") or s.startswith("virtualbrowser-dir:")


def _signin_existing_in_browser(cdp: str, email: str, mailbox_key: str,
                                profile_name: str) -> None:
    """对**已存在**账号做一次邮箱 OTP 登录（不是新注册），然后采纳会话。

    一次只处理一个账号；调用方负责保证 user-data-dir 未被重复打开。
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.flova.ai/en/generator/",
                  wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=25000)
        except Exception:
            pass
        _begin_email_auth(page, signup=False)
        _submit_email_and_otp(page, email, mailbox_key, signup=False)

        info = _web_get_user_info(ctx)
        if info.get("code") != 0:
            raise RuntimeError("FLOVA_WEB_UNAUTHENTICATED after OTP sign-in")
        adopt_web_session(profile_name, ctx, expected_email=email, playwright=p)
        browser.close()


def repair_web_sessions(*, only: str | None = None,
                        allow_otp_signin: bool = True) -> dict[str, Any]:
    """逐个处理 keyed 子号的网页会话引用（不邀新、不删任何账号/profile）。

    - web_profile_ref 已采纳到 ``~/.flova-mcp/browser-profiles/...``：保持原样，
      不再打开任何浏览器。
    - 仍指向旧虚拟浏览器（``virtualbrowser-worker:`` / ``virtualbrowser-dir:``）：
      有 ``mailbox_ref`` 且允许 OTP 时，复用后端 worker 池里的一个 worker（默认 VB，
      无痕 + 按国家轮换指纹）做一次邮箱 OTP 登录（非注册）后采纳；没有邮箱或不允许
      OTP 则 skipped（reason=legacy_virtualbrowser_profile）。绝不启动旧虚拟浏览器，
      也不创建、不删除任何 worker / profile / worker 目录。

    串行：一次只开一个 worker。
    """
    from flova_pricing import _cli_account

    reg = load_registry()
    results: list[dict[str, Any]] = []
    touched = False

    for a in reg.get("accounts", []):
        prof = profile_from_ref(a.get("api_key_ref"))
        if not prof or a.get("role") in ("mother", "retired_mother"):
            continue
        if only and prof != only:
            continue

        expected_email = str(a.get("email") or "").lower()
        try:
            cli_email = str(_cli_account(prof).get("email") or "").lower()
        except Exception as e:
            results.append({"profile": prof, "status": "error",
                            "reason": f"cli_unreadable: {str(e)[:100]}"})
            continue
        if expected_email and cli_email and expected_email != cli_email:
            results.append({"profile": prof, "status": "skipped",
                            "reason": "email_mismatch"})
            continue
        expected_email = expected_email or cli_email

        ref = str(a.get("web_profile_ref") or "")

        # 已采纳到 MCP 持久 profile 目录：保持原样，不开浏览器。
        if ref.startswith("~/.flova-mcp/browser-profiles/"):
            results.append({"profile": prof, "status": "skipped",
                            "reason": "web_profile_adopted"})
            continue

        # 仅处理旧虚拟浏览器引用；其他引用无源会话，直接跳过。
        if not _is_legacy_virtualbrowser_ref(ref):
            results.append({"profile": prof, "status": "skipped",
                            "reason": "no_source_session"})
            continue

        mailbox_ref = a.get("mailbox_ref")
        if not (allow_otp_signin and mailbox_ref):
            results.append({"profile": prof, "status": "skipped",
                            "reason": "legacy_virtualbrowser_profile"})
            continue

        # 复用后端池里的一个 worker（默认 VB 无痕轮换；不创建、不删除）。
        session = next_workers(1)[0]
        wid = session.id
        try:
            port = launch_worker(wid)
            wait_cdp(port)
            time.sleep(2)
            _signin_existing_in_browser(
                f"http://127.0.0.1:{port}", expected_email, mailbox_ref, prof)
            a["web_profile_ref"] = f"~/.flova-mcp/browser-profiles/{prof}"
            touched = True
            result = {"profile": prof, "status": "adopted",
                      "source": "otp_signin", "backend": browser_backend(),
                      "fingerprint_rotated": fingerprint_rotated(wid)}
            if browser_backend() == "vb":
                result["vb_worker_id"] = wid
            else:
                result["ads_profile_id"] = wid
            results.append(result)
        except Exception as e:
            results.append({"profile": prof, "status": "skipped",
                            "reason": "legacy_virtualbrowser_profile",
                            "detail": str(e)[:120]})
        finally:
            stop_worker(wid)

    if touched:
        reg["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_registry(reg)
    return {"results": results}


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "ensure", "candidates", "prune",
                                    "repair-web"])
    ap.add_argument("--budget", type=float, default=0.0)
    ap.add_argument("--profile", default="prod")
    ap.add_argument("--no-otp", action="store_true",
                    help="repair-web: 不做邮箱 OTP 登录兜底")
    a = ap.parse_args()

    if a.cmd == "plan":
        billing = resolve_inviter(a.profile)
        out = invite_requirement(budget=a.budget, mother_profile=billing)
        _print_json({"billing_profile": billing, "requirement": out})
    elif a.cmd == "ensure":
        _print_json(ensure_credits(budget=a.budget, profile=a.profile))
    elif a.cmd == "candidates":
        _print_json({
            "active_mother_profile": active_mother_profile(),
            "candidates": successor_candidates(),
        })
    elif a.cmd == "prune":
        _print_json(prune_low_accounts())
    elif a.cmd == "repair-web":
        _print_json(repair_web_sessions(
            only=a.profile if a.profile != "prod" else None,
            allow_otp_signin=not a.no_otp,
        ))
    sys.exit(0)
