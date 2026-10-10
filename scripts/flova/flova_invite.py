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
from typing import Any

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
VB_LOCAL = Path(os.environ.get("LOCALAPPDATA", "")) / "VirtualBrowser"
VB_KERNEL_ROOT = Path(r"C:\Program Files\VirtualBrowser\VirtualBrowser")
CDP_BASE = 18850
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
        flova = (m.get("registration") or {}).get("flova") or {}
        if not addr or not key:
            continue
        if flova.get("registered") is True:
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


def find_vb_kernel() -> Path:
    env = os.environ.get("FLOVA_VB_KERNEL")
    if env and Path(env).is_file():
        return Path(env)
    if not VB_KERNEL_ROOT.is_dir():
        raise RuntimeError(f"VirtualBrowser kernel root missing: {VB_KERNEL_ROOT}")
    versions = sorted(
        [p for p in VB_KERNEL_ROOT.iterdir() if p.is_dir() and (p / "VirtualBrowser.exe").is_file()],
        key=lambda p: p.name,
    )
    if not versions:
        raise RuntimeError("no VirtualBrowser.exe under kernel root")
    return versions[-1] / "VirtualBrowser.exe"


def next_workers(n: int) -> list[tuple[str, int, Path]]:
    """一次性预分配 n 个 VB worker（独立 user-data-dir + CDP 端口）。"""
    workers = VB_LOCAL / "Workers"
    workers.mkdir(parents=True, exist_ok=True)
    existing = {p.name for p in workers.iterdir() if p.is_dir()}
    out: list[tuple[str, int, Path]] = []
    k = 10
    while len(out) < n:
        sid = str(k)
        if sid not in existing:
            out.append((sid, CDP_BASE + (k % 100), workers / sid))
            existing.add(sid)
        k += 1
    return out


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


def adopt_web_session(profile_name: str, source_context, *,
                      expected_email: str | None = None,
                      playwright=None) -> dict[str, Any]:
    """把一个**已登录同账号**的 Playwright context 的 flova cookies 采纳到
    ``~/.flova-mcp/browser-profiles/<profile_name>``。

    signup 与 repair 共用此函数。流程：
      1. ``source_context.cookies()`` 已由 Playwright/CDP 解密；只取 flova 域。
      2. 系统 Chrome/Edge 持久 context（与 web-session.js 同布局）addCookies。
         绝不拷贝 Cookies sqlite——DPAPI 加密键不匹配。
      3. 必须 get_user_info code==0 且网页邮箱 == expected_email。
         失败立刻清空已导入 cookies 并抛错，不留半成品（绝不保留错误会话）。
    """
    cookies = [dict(c) for c in source_context.cookies()
               if _is_flova_domain(c.get("domain"))]
    if not cookies:
        raise RuntimeError("no flova cookies in source context")
    # 会话型 cookie expires<=0：add_cookies 不接受负 expires，去掉让其按会话处理。
    for c in cookies:
        if float(c.get("expires") or 0) <= 0:
            c.pop("expires", None)

    own_pw = playwright is None
    if own_pw:
        from playwright.sync_api import sync_playwright
        playwright = sync_playwright().start()
    target = None
    try:
        target_dir = WEB_PROFILES_DIR / profile_name
        target_dir.mkdir(parents=True, exist_ok=True)
        target = playwright.chromium.launch_persistent_context(
            str(target_dir),
            executable_path=_system_chrome(),
            headless=True,
            args=["--no-default-browser-check", "--no-first-run",
                  "--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 860},
        )
        target.add_cookies(cookies)
        info = _web_get_user_info(target)
        email = info.get("email")
        email_match = (
            not expected_email
            or (bool(email)
                and str(email).lower() == str(expected_email).lower())
        )
        if info.get("code") != 0 or not email_match:
            # 不保留导入的 cookies：该 profile 是专用空 jar，整罐清空。
            target.clear_cookies()
            if info.get("code") != 0:
                err = RuntimeError("FLOVA_WEB_UNAUTHENTICATED")
                err.code = "FLOVA_WEB_UNAUTHENTICATED"
            else:
                err = RuntimeError("FLOVA_WEB_EMAIL_MISMATCH")
                err.code = "FLOVA_WEB_EMAIL_MISMATCH"
            raise err
        return {"profile": profile_name, "email": email,
                "user_id": info.get("user_id")}
    finally:
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
               profile_name: str, worker: tuple[str, int, Path]) -> dict[str, Any]:
    """注册 1 个子号（资源由调用方预分配，可并行）。成功标准：拿到子号 token。"""
    worker_id, port, worker_dir = worker
    code = None
    try:
        snap0 = invite_snapshot(mother_profile)
        code = snap0["promotion_code"]
        if not code:
            return {"ok": False, "reason": "no_promotion_code",
                    "child_email": mailbox["address"]}
    except Exception as e:
        return {"ok": False, "reason": f"mother_snapshot_failed: {str(e)[:120]}",
                "child_email": mailbox["address"]}

    kernel = find_vb_kernel()
    worker_dir.mkdir(parents=True, exist_ok=True)
    invite_url = f"https://www.flova.ai/?refCode={code}"
    proc = subprocess.Popen(
        [
            str(kernel),
            f"--user-data-dir={worker_dir}",
            f"--worker-id={worker_id}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--remote-debugging-port={port}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    signup_err = None
    child_token = None
    try:
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
            "worker_id": worker_id,
            "cdp_port": port,
        }
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _run_parallel(mother_profile: str, slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """n 个注册并行执行，不等待；资源已在锁内预分配，互不冲突。"""
    n = len(slots)
    if n == 1:
        return [invite_one(mother_profile=mother_profile, **slots[0])]
    with ThreadPoolExecutor(max_workers=n) as ex:
        futs = [ex.submit(invite_one, mother_profile=mother_profile, **s)
                for s in slots]
        return [f.result() for f in futs]


def _allocate_slots(n: int) -> list[dict[str, Any]]:
    mailboxes = pick_mailboxes(n)
    profiles = next_child_profiles(n)
    workers = next_workers(n)
    return [
        {"mailbox": mb, "profile_name": prof, "worker": wk}
        for mb, prof, wk in zip(mailboxes, profiles, workers)
    ]


def _record_children(results: list[dict[str, Any]], inviter_email: str | None) -> None:
    reg = load_registry()
    known = {a.get("email", "").lower() for a in reg.get("accounts", [])}
    for r in results:
        if not r.get("ok") or not r.get("child_profile"):
            continue
        if r["child_email"].lower() in known:
            continue
        reg.setdefault("accounts", []).append({
            "email": r["child_email"],
            "role": "child",
            "state": "keyed",
            "invited_by": inviter_email,
            "api_key_ref": f"flova-profile:{r['child_profile']}",
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

        # 资源一次性预分配，然后并行注册、不等待。
        slots = _allocate_slots(max(1, n))
        results = _run_parallel(billing, slots)
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

def _vb_userdata_for_ref(ref: str) -> Path | None:
    """把 web_profile_ref 解析成 VirtualBrowser user-data-dir。

    MCP 目录引用（已采纳过）返回 None。virtualbrowser-dir 按精确目录取，
    不猜名；账号归属一律以会话邮箱比对为准。
    """
    s = str(ref or "")
    if s.startswith("virtualbrowser-worker:"):
        wid = s.split(":", 1)[1].split("(", 1)[0]
        return VB_LOCAL / "Workers" / wid
    if s.startswith("virtualbrowser-dir:"):
        name = s.split(":", 1)[1].split("(", 1)[0]
        return VB_LOCAL / name
    return None


def _free_tcp_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _launch_vb(userdata: Path, port: int) -> tuple[subprocess.Popen, str | None]:
    kernel = find_vb_kernel()
    worker_id: str | None = None
    if userdata.parent.name == "Workers":
        worker_id = userdata.name
    args = [
        str(kernel),
        f"--user-data-dir={userdata}",
        "--no-first-run",
        "--no-default-browser-check",
        f"--remote-debugging-port={port}",
    ]
    if worker_id:
        args.append(f"--worker-id={worker_id}")
    proc = subprocess.Popen(
        args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc, worker_id


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
    """逐个修复 keyed 子号：开 web_profile_ref 指向的 VB user-data-dir，
    有同账号 Flova 会话就采纳；会话不可恢复且有 mailbox_ref 时允许一次
    邮箱 OTP 登录（非注册）；两者都没有则 skipped。

    串行：Chrome user-data-dir 不能同时开两次。不邀新、不删任何账号/profile。
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

        userdata = _vb_userdata_for_ref(a.get("web_profile_ref"))
        recovered = False
        mismatch = False
        if userdata is not None and userdata.is_dir():
            port = _free_tcp_port()
            proc, _wid = _launch_vb(userdata, port)
            try:
                wait_cdp(port)
                time.sleep(2)
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.connect_over_cdp(
                        f"http://127.0.0.1:{port}")
                    ctx = browser.contexts[0]
                    info = _web_get_user_info(ctx)
                    if info.get("code") == 0:
                        web_email = str(info.get("email") or "").lower()
                        if web_email == expected_email:
                            adopt_web_session(prof, ctx,
                                              expected_email=expected_email,
                                              playwright=p)
                            recovered = True
                        else:
                            mismatch = True
                    browser.close()
            finally:
                try:
                    proc.terminate()
                    proc.wait(timeout=8)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                time.sleep(2)  # 等 user-data-dir 锁释放

        if recovered:
            a["web_profile_ref"] = f"~/.flova-mcp/browser-profiles/{prof}"
            touched = True
            results.append({"profile": prof, "status": "adopted",
                            "source": str(userdata) if userdata else None})
            continue

        if mismatch:
            results.append({"profile": prof, "status": "skipped",
                            "reason": "email_mismatch"})
            continue

        # 无源会话：有 mailbox_ref 才允许一次 OTP 登录（存量账号，非注册）。
        mailbox_ref = a.get("mailbox_ref")
        if allow_otp_signin and mailbox_ref and userdata is not None \
                and userdata.is_dir():
            port = _free_tcp_port()
            proc, _wid = _launch_vb(userdata, port)
            try:
                wait_cdp(port)
                time.sleep(2)
                try:
                    _signin_existing_in_browser(
                        f"http://127.0.0.1:{port}", expected_email,
                        mailbox_ref, prof)
                    a["web_profile_ref"] = (
                        f"~/.flova-mcp/browser-profiles/{prof}")
                    touched = True
                    results.append({"profile": prof, "status": "adopted",
                                    "source": "otp_signin"})
                    continue
                except Exception as e:
                    signin_err = str(e)[:120]
            finally:
                try:
                    proc.terminate()
                    proc.wait(timeout=8)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                time.sleep(2)
        else:
            signin_err = None

        results.append({
            "profile": prof, "status": "skipped",
            "reason": "no_source_session",
            **({"detail": signin_err} if signin_err else {}),
        })

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
