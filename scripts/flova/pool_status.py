# -*- coding: utf-8 -*-
"""Flova MCP 号池只读探测，以及把已有账号补进账本。

不注册、不登录、不清号、不切换母号。余额和邀请码只出现在当次返回里，
邀请码在离开本模块之前被删掉，余额不写回 registry.json。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

import flova_invite as fi
import flova_pricing as fp

PROFILE_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_DROP_KEYS = {
    "promotion_code",
    "token",
    "cookie",
    "cookies",
    "authorization",
    "api_key",
    "mailbox_key",
    "mailbox_ref",
    "refcode",
    "ref_code",
}
_SECRET_RE = re.compile(
    r"(?i)(promotion_code|token|cookie|authorization|api[_-]?key|mailbox[_-]?key|refCode)"
    r"(\s*[:=]\s*|\s+)([^\s,;\"'}]+)"
)
_JSON_SECRET_RE = re.compile(
    r'(?i)("(?:promotion_code|token|cookie|authorization|api_key|mailbox_key|refCode)"\s*:\s*")[^"]*"'
)
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+")


def profile_name_ok(name: str | None) -> bool:
    return bool(name) and bool(PROFILE_RE.fullmatch(str(name)))


def redact(text: str) -> str:
    """日志和错误文本里的邀请码、token、cookie 换成占位。"""
    if not text:
        return ""
    text = _BEARER_RE.sub("bearer [redacted]", text)
    text = _JSON_SECRET_RE.sub(r'\1[redacted]"', text)
    text = _SECRET_RE.sub(lambda m: m.group(1) + m.group(2) + "[redacted]", text)
    return text


def scrub_obj(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in _DROP_KEYS:
                continue
            out[key] = scrub_obj(item)
        return out
    if isinstance(value, list):
        return [scrub_obj(item) for item in value]
    if isinstance(value, str):
        return redact(value)
    return value


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _clean_email(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if "@" not in text or any(ch in text for ch in " \r\n\t"):
        return None
    return text


def _email_from_cli(data: dict | None) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("email", "user_email", "mail"):
        found = _clean_email(data.get(key))
        if found:
            return found
    user = data.get("user")
    if isinstance(user, dict):
        return _clean_email(user.get("email"))
    return None


def _user_id_from(data: dict | None) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("user_id", "id"):
        value = data.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    user = data.get("user")
    if isinstance(user, dict):
        value = user.get("user_id") or user.get("id")
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    nested = data.get("data")
    if isinstance(nested, dict) and nested is not data:
        return _user_id_from(nested)
    return None


def _credits(data: dict | None) -> float | None:
    if not isinstance(data, dict) or "credits_balance" not in data:
        return None
    try:
        return float(data["credits_balance"])
    except (TypeError, ValueError):
        return None


def _web_credits(bucket: Any) -> float | None:
    """网页积分桶 valid_v2 的 data.total，与 CLI credits_balance 同源。
    只有网页会话、没有 CLI profile 的号靠这个显示余额。"""
    if not isinstance(bucket, dict) or bucket.get("code") != 0:
        return None
    data = bucket.get("data")
    if not isinstance(data, dict) or "total" not in data:
        return None
    try:
        return float(data["total"])
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def default_mother_profile() -> str:
    try:
        name = str(fi.load_policy().get("mother", {}).get("default_profile") or "prod")
    except Exception:
        name = "prod"
    return name if profile_name_ok(name) else "prod"


def load_pool_registry(path: Path | None = None) -> dict[str, Any]:
    target = path or fi.REGISTRY
    if not target.exists():
        return {"version": "3", "accounts": []}
    return json.loads(target.read_text(encoding="utf-8"))


def save_pool_registry(reg: dict[str, Any], path: Path | None = None) -> None:
    target = path or fi.REGISTRY
    reg["updated_at"] = _now()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(reg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(target)


# 探测结果缓存：只含已 scrub 的行（无邀请码/token/cookie）。不写进账本，
# 余额只是当次探测的快照。快照不按时间过期，重启面板仍显示上次手动刷新的结果，
# 直到用户自己再点刷新。
PROBE_CACHE_PATH = fi.MCP_DIR / "pool-probe-cache.json"


def load_probe_cache(path: Path | None = None) -> dict[str, tuple[float, dict[str, Any]]]:
    target = path or PROBE_CACHE_PATH
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), dict):
        return {}
    out: dict[str, tuple[float, dict[str, Any]]] = {}
    for key, item in payload["entries"].items():
        if isinstance(item, dict) and isinstance(item.get("ts"), (int, float)) \
                and isinstance(item.get("row"), dict):
            out[str(key)] = (float(item["ts"]), item["row"])
    return out


def save_probe_cache(
    entries: dict[str, tuple[float, dict[str, Any]]],
    path: Path | None = None,
) -> None:
    target = path or PROBE_CACHE_PATH
    cleaned = {
        key: {"ts": ts, "row": scrub_obj(row)}
        for key, (ts, row) in entries.items()
        if isinstance(row, dict) and isinstance(ts, (int, float))
    }
    temporary = target.with_suffix(".tmp")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps({"version": 1, "entries": cleaned}, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(target)


def cli_profile_names() -> set[str]:
    out = subprocess.run(
        [fi.FLOVA_BIN, "profile", "list"],
        capture_output=True,
        text=True,
        timeout=30,
        encoding="utf-8",
    )
    if out.returncode != 0:
        detail = redact((out.stderr or out.stdout or "profile list failed")[:200])
        raise RuntimeError(detail)
    payload = json.loads(out.stdout or "{}")
    data = payload.get("data") or []
    names: set[str] = set()
    for item in data:
        if isinstance(item, dict):
            name = str(item.get("name") or "")
        else:
            name = str(item or "")
        if profile_name_ok(name):
            names.add(name)
    return names


def web_profile_dirs() -> set[str]:
    root = fi.WEB_PROFILES_DIR
    if not root.is_dir():
        return set()
    names: set[str] = set()
    for child in root.iterdir():
        if child.is_dir() and profile_name_ok(child.name):
            names.add(child.name)
    return names


def _web_ref_profile(account: dict[str, Any]) -> str:
    """从 web_profile_ref 尾部取 profile 名（仅网页会话、没有 CLI key 的账本行用）。"""
    web_ref = str(account.get("web_profile_ref") or "").replace("\\", "/")
    match = re.search(r"browser-profiles/([A-Za-z0-9._-]+)$", web_ref)
    if not match:
        return ""
    name = match.group(1)
    return name if profile_name_ok(name) else ""


def next_onboard_profile(taken: set[str]) -> str:
    """从 kid1 起返回第一个未被占用的 profile 名（纯函数）。"""
    occupied = set(taken)
    k = 1
    while f"kid{k}" in occupied:
        k += 1
    return f"kid{k}"


def collect_onboard_taken(
    registry: dict[str, Any],
    cli_names: set[str],
    web_dirs: set[str],
) -> set[str]:
    """合并三类占用来源，给「录入已有账号」分配不撞名的 kidN。

    只看 CLI 的 next_child_profiles 会撞上只存在网页目录的号（如 kid4），
    所以账本里每条 api_key_ref / web_profile_ref 引用也要算进去。
    """
    taken = set(cli_names) | set(web_dirs)
    for account in registry.get("accounts") or []:
        if not isinstance(account, dict):
            continue
        cli_name = fi.profile_from_ref(account.get("api_key_ref"))
        if cli_name and profile_name_ok(cli_name):
            taken.add(cli_name)
        web_name = _web_ref_profile(account)
        if web_name:
            taken.add(web_name)
    return taken


def collect_sources(
    registry: dict[str, Any],
    cli_names: set[str],
    web_dirs: set[str],
) -> list[dict[str, Any]]:
    """合并账本、CLI profile、网页目录。不访问网络。"""
    active = str(registry.get("active_mother_profile") or "")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for account in registry.get("accounts") or []:
        if not isinstance(account, dict):
            continue
        profile = fi.profile_from_ref(account.get("api_key_ref")) or _web_ref_profile(account)
        if profile and not profile_name_ok(profile):
            profile = ""
        email = _clean_email(account.get("email"))
        sources = ["registry"]
        if profile and profile in cli_names:
            sources.append("cli")
        if profile and profile in web_dirs:
            sources.append("web_dir")
        rows.append({
            "profile": profile or "",
            "email": email,
            "user_id": account.get("user_id") if isinstance(account.get("user_id"), str) else None,
            "role": account.get("role"),
            "state": account.get("state"),
            "in_pool": True,
            "active_mother": bool(profile) and profile == active,
            "sources": sources,
        })
        if profile:
            seen.add(profile)
    for name in sorted(cli_names):
        if name in seen:
            continue
        rows.append({
            "profile": name,
            "email": None,
            "user_id": None,
            "role": None,
            "state": None,
            "in_pool": False,
            "active_mother": name == active,
            "sources": ["cli"] + (["web_dir"] if name in web_dirs else []),
        })
        seen.add(name)
    for name in sorted(web_dirs):
        if name in seen:
            continue
        rows.append({
            "profile": name,
            "email": None,
            "user_id": None,
            "role": None,
            "state": None,
            "in_pool": False,
            "active_mother": name == active,
            "sources": ["web_dir"],
        })
    rows.sort(key=lambda row: (
        0 if row.get("active_mother") else 1,
        0 if row.get("in_pool") else 1,
        str(row.get("profile") or row.get("email") or ""),
    ))
    return rows


def invite_view(stats_raw: dict | None) -> dict[str, Any]:
    """与 invite_snapshot 同一套 stats 字段。缺省名额不写成 20，缺省奖励不写成 200。

    不返回 promotion_code。
    """
    raw = stats_raw if isinstance(stats_raw, dict) else {}
    stats = raw.get("data") or raw
    if not isinstance(stats, dict):
        stats = {}
    reward = stats.get("registration_reward") or {}
    if not isinstance(reward, dict):
        reward = {}
    eligibility = stats.get("eligibility") or {}
    if not isinstance(eligibility, dict):
        eligibility = {}
    rewarded = int(reward.get("rewarded_count") or 0)
    max_invitees = _optional_int(reward.get("max_invitees"))
    credit_reward_num = _optional_int(reward.get("credit_reward_num"))
    remaining = None if max_invitees is None else max(0, max_invitees - rewarded)
    disabled = bool(
        eligibility.get("invite_reward_disabled")
        or stats.get("invite_reward_disabled")
    )
    return {
        "rewarded_count": rewarded,
        "max_invitees": max_invitees,
        "remaining_invitees": remaining,
        "credit_reward_num": credit_reward_num,
        "invite_reward_disabled": disabled,
        "eligibility": eligibility,
    }


def _exploration_list(payload: Any) -> list | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    rewards = data.get("rewards")
    if not isinstance(rewards, list):
        return None
    out = []
    for item in rewards:
        if not isinstance(item, dict):
            continue
        out.append({
            "source": item.get("source"),
            "status": item.get("status"),
            "credits": fp._reward_credits_of(item),
        })
    return out


def _email_from_web_user(payload: Any) -> tuple[str | None, str | None]:
    if not isinstance(payload, dict) or payload.get("code") != 0:
        return None, None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    return _clean_email(data.get("email")), _user_id_from(data)


def assemble_row(
    base: dict[str, Any],
    *,
    cli_data: dict | None = None,
    cli_error: str | None = None,
    web_bundle: dict | None = None,
    web_error: str | None = None,
) -> dict[str, Any]:
    """把一条结构行和当次探测合成页面行。返回值不含邀请码。"""
    cli_logged_in = isinstance(cli_data, dict)
    credits = _credits(cli_data) if cli_logged_in else None
    cli_email = _email_from_cli(cli_data) if cli_logged_in else None
    cli_user_id = _user_id_from(cli_data) if cli_logged_in else None

    bundle = web_bundle if isinstance(web_bundle, dict) else {}
    expl = _exploration_list(bundle.get("exploration")) if not web_error else None
    web_logged_in = False
    if not web_error:
        web_logged_in = bool(fp.web_session_ok(bundle.get("credits"), expl))
    web_email, web_user_id = (None, None)
    if web_logged_in:
        web_email, web_user_id = _email_from_web_user(bundle.get("user"))
    web_credits = _web_credits(bundle.get("credits")) if not web_error else None

    email = base.get("email") or cli_email or web_email
    user_id = base.get("user_id") or cli_user_id or web_user_id

    invite = {
        "rewarded_count": None,
        "max_invitees": None,
        "remaining_invitees": None,
        "credit_reward_num": None,
        "invite_reward_disabled": None,
        "eligibility": None,
    }
    if web_logged_in:
        view = invite_view(bundle.get("invite"))
        flags = view["eligibility"] if isinstance(view["eligibility"], dict) else {}
        invite = {
            "rewarded_count": view["rewarded_count"],
            "max_invitees": view["max_invitees"],
            "remaining_invitees": view["remaining_invitees"],
            "credit_reward_num": view["credit_reward_num"],
            "invite_reward_disabled": view["invite_reward_disabled"],
            "eligibility": {
                "account_age_7d": bool(flags.get("account_age_7d")),
                "has_export": bool(flags.get("has_export")),
            },
        }

    remaining = invite["remaining_invitees"]
    disabled = bool(invite["invite_reward_disabled"])
    invite_ready = bool(
        web_logged_in
        and remaining is not None
        and remaining > 0
        and not disabled
    )
    role = base.get("role")
    blockers: list[str] = []
    if role in ("mother", "retired_mother"):
        blockers = ["already_mother" if role == "mother" else "retired_mother"]
    elif not web_logged_in:
        blockers = ["no_web_session"]
    else:
        flags = invite["eligibility"] or {}
        if not flags.get("account_age_7d"):
            blockers.append("account_age_7d")
        if not flags.get("has_export"):
            blockers.append("no_export")
        if disabled:
            blockers.append("invite_reward_disabled")
        if not remaining:
            blockers.append("no_invite_slots")
    successor_eligible = not blockers and role not in ("mother", "retired_mother")

    in_pool = bool(base.get("in_pool"))
    addable = (not in_pool) and bool(email)
    add_block_reason = None
    if not in_pool and not email:
        add_block_reason = "读不到邮箱"

    balance = credits if credits is not None else web_credits
    row = {
        "profile": base.get("profile") or "",
        "email": email,
        "user_id": user_id,
        "role": role,
        "state": base.get("state"),
        "in_pool": in_pool,
        "active_mother": bool(base.get("active_mother")),
        "sources": list(base.get("sources") or []),
        "cli_logged_in": cli_logged_in,
        "cli_error": redact(cli_error or "") or None,
        "credits": balance,
        "credits_source": "cli" if credits is not None else ("web" if web_credits is not None else None),
        "web_logged_in": web_logged_in,
        "web_error": redact(web_error or "") or None,
        "invite_ready": invite_ready,
        "successor_eligible": successor_eligible,
        "successor_blockers": blockers,
        "addable": addable,
        "add_block_reason": add_block_reason,
        **invite,
    }
    return scrub_obj(row)


def read_cli_account(profile: str) -> tuple[dict | None, str | None]:
    if not profile_name_ok(profile):
        return None, "invalid profile"
    try:
        data = fp._cli_account(profile)
    except Exception as exc:
        return None, redact(str(exc)[:200])
    if not isinstance(data, dict):
        return None, "account user 没有返回账号"
    return data, None


def fetch_web_bundle(profile: str) -> tuple[dict | None, str | None]:
    """一次无头网页会话取积分桶、探索奖励、邀请 stats、用户信息。"""
    if not profile_name_ok(profile):
        return None, "invalid profile"
    script = (
        "const path=require('path');"
        "const ws=require(path.join(process.env.USERPROFILE,'.flova-mcp','web-session.js'));"
        "ws.withSession(async ctx=>{"
        "async function grab(method, url){"
        "const r=method==='POST'"
        "? await ctx.request.post(url,{data:{},headers:{'content-type':'application/json'}})"
        ": await ctx.request.get(url);"
        "return await r.json();}"
        "const out={"
        "credits: await grab('POST','https://service.flova.ai/api/v2/user/plan/credits/valid_v2'),"
        "exploration: await grab('POST','https://service.flova.ai/api/v2/user/exploration_rewards'),"
        "invite: await grab('GET','https://service.flova.ai/api/v2/invite/promotion/stats'),"
        "user: await grab('POST','https://service.flova.ai/api/v2/user/get_user_info')};"
        "console.log(JSON.stringify(out));"
        "},{headless:true,profile:" + json.dumps(profile) + "})"
        ".catch(e=>{console.error(String(e&&e.message||e));process.exit(1)});"
    )
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8", newline="\n",
    )
    handle.write(script)
    handle.close()
    try:
        out = subprocess.run(
            ["node", handle.name],
            capture_output=True,
            text=True,
            timeout=90,
            encoding="utf-8",
        )
    except Exception as exc:
        return None, redact(str(exc)[:200])
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
    if out.returncode != 0:
        return None, redact((out.stderr or out.stdout or "web session failed")[:200])
    line = (out.stdout or "").strip().splitlines()
    if not line:
        return None, "web session 没有返回"
    try:
        payload = json.loads(line[-1])
    except json.JSONDecodeError:
        return None, "web session 返回不是 JSON"
    if not isinstance(payload, dict):
        return None, "web session 返回不是对象"
    return payload, None


def probe_row(
    base: dict[str, Any],
    *,
    account_fn: Callable[[str], tuple[dict | None, str | None]] = read_cli_account,
    web_fn: Callable[[str], tuple[dict | None, str | None]] = fetch_web_bundle,
) -> dict[str, Any]:
    profile = str(base.get("profile") or "")
    cli_data = None
    cli_error = None
    web_bundle = None
    web_error = None
    if profile and profile_name_ok(profile):
        if "cli" in (base.get("sources") or []) or base.get("in_pool"):
            cli_data, cli_error = account_fn(profile)
        elif not base.get("in_pool"):
            cli_data, cli_error = (None, None)
        web_bundle, web_error = web_fn(profile)
    return assemble_row(
        base,
        cli_data=cli_data,
        cli_error=cli_error,
        web_bundle=web_bundle,
        web_error=web_error,
    )


def list_structural() -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    try:
        names = cli_profile_names()
    except Exception as exc:
        names = set()
        errors.append(redact(str(exc)[:200]))
    try:
        registry = load_pool_registry()
    except Exception as exc:
        registry = {"version": "3", "accounts": []}
        errors.append(redact(str(exc)[:200]))
    rows = collect_sources(registry, names, web_profile_dirs())
    return rows, errors


def probe_all(
    bases: list[dict[str, Any]] | None = None,
    *,
    on_progress: Callable[[int, int, str], None] | None = None,
    account_fn: Callable[[str], tuple[dict | None, str | None]] = read_cli_account,
    web_fn: Callable[[str], tuple[dict | None, str | None]] = fetch_web_bundle,
) -> list[dict[str, Any]]:
    rows = list(bases) if bases is not None else list_structural()[0]
    total = len(rows)
    probed: list[dict[str, Any]] = []
    for index, base in enumerate(rows, start=1):
        if on_progress:
            on_progress(index, total, str(base.get("profile") or base.get("email") or ""))
        probed.append(probe_row(base, account_fn=account_fn, web_fn=web_fn))
    return probed


def _qualifies_as_mother(profile: str, reg: dict[str, Any], default_mother: str) -> bool:
    accounts = reg.get("accounts") or []
    if any(isinstance(item, dict) and item.get("role") == "mother" for item in accounts):
        return False
    active = str(reg.get("active_mother_profile") or default_mother or "prod")
    return profile == active or profile == default_mother


def mutate_add(
    reg: dict[str, Any],
    *,
    profile: str,
    email: str | None,
    user_id: str | None,
    cli_exists: bool,
    cli_logged_in: bool,
    web_dir_exists: bool,
    default_mother: str,
) -> dict[str, Any]:
    """改内存中的账本。调用方决定是否落盘。不写余额、邀请码、token。"""
    if not profile_name_ok(profile):
        return {"ok": False, "reason": "invalid_profile", "profile": profile,
                "message": "profile 名不合法"}
    if not cli_exists and not web_dir_exists:
        return {"ok": False, "reason": "not_found", "profile": profile,
                "message": "CLI 和网页目录里都没有这个 profile"}
    cleaned = _clean_email(email)
    if not cleaned:
        return {"ok": False, "reason": "no_email", "profile": profile,
                "message": "读不到邮箱"}
    want_ref = f"flova-profile:{profile}"
    web_ref = f"~/.flova-mcp/browser-profiles/{profile}"
    target = cleaned.lower()
    for account in reg.get("accounts") or []:
        if not isinstance(account, dict):
            continue
        existing_email = (_clean_email(account.get("email")) or "").lower()
        if existing_email != target:
            continue
        existing_ref = str(account.get("api_key_ref") or "")
        existing_name = fi.profile_from_ref(existing_ref) if existing_ref else ""
        if existing_name and existing_name != profile:
            return {
                "ok": False,
                "reason": "profile_conflict",
                "profile": profile,
                "existing_profile": existing_name,
                "message": f"邮箱已属于 {existing_name}，与 {profile} 冲突",
            }
        if cli_exists and existing_ref and existing_ref != want_ref:
            return {
                "ok": False,
                "reason": "profile_conflict",
                "profile": profile,
                "existing_profile": existing_name or existing_ref,
                "message": f"邮箱已属于 {existing_name or existing_ref}，与 {profile} 冲突",
            }
        changed = False
        if cli_exists and not existing_ref:
            account["api_key_ref"] = want_ref
            changed = True
        if web_dir_exists and not account.get("web_profile_ref"):
            account["web_profile_ref"] = web_ref
            changed = True
        if user_id and not account.get("user_id"):
            account["user_id"] = user_id
            changed = True
        account["last_verified"] = _now()
        if not changed:
            return {"ok": True, "action": "already", "profile": profile,
                    "email": cleaned, "message": "已在号池"}
        return {"ok": True, "action": "patched", "profile": profile,
                "email": cleaned, "message": "已补上缺失的引用"}

    role = "mother" if _qualifies_as_mother(profile, reg, default_mother) else "child"
    state = "keyed" if cli_logged_in else "web_session"
    record: dict[str, Any] = {
        "email": cleaned,
        "role": role,
        "state": state,
        "last_verified": _now(),
        "notes": "added from pool panel",
    }
    if user_id:
        record["user_id"] = user_id
    if cli_exists:
        record["api_key_ref"] = want_ref
    if web_dir_exists:
        record["web_profile_ref"] = web_ref
    reg.setdefault("accounts", []).append(record)
    return {
        "ok": True,
        "action": "added",
        "profile": profile,
        "email": cleaned,
        "role": role,
        "state": state,
        "message": "已加入号池",
    }


def add_to_pool(
    profile: str,
    *,
    registry_path: Path | None = None,
    email: str | None = None,
    user_id: str | None = None,
    cli_logged_in: bool = False,
    cli_exists: bool | None = None,
    web_dir_exists: bool | None = None,
    default_mother: str | None = None,
) -> dict[str, Any]:
    if cli_exists is None:
        try:
            cli_exists = profile in cli_profile_names()
        except Exception:
            cli_exists = False
    if web_dir_exists is None:
        web_dir_exists = profile in web_profile_dirs()
    mother = default_mother if default_mother is not None else default_mother_profile()
    reg = load_pool_registry(registry_path)
    result = mutate_add(
        reg,
        profile=profile,
        email=email,
        user_id=user_id,
        cli_exists=bool(cli_exists),
        cli_logged_in=bool(cli_logged_in),
        web_dir_exists=bool(web_dir_exists),
        default_mother=mother,
    )
    if result.get("ok") and result.get("action") != "already":
        save_pool_registry(reg, registry_path)
    return result


def _account_matches(
    account: dict[str, Any],
    *,
    profile: str | None,
    email: str | None,
) -> bool:
    if profile:
        ref_name = fi.profile_from_ref(account.get("api_key_ref"))
        if ref_name == profile:
            return True
        web_ref = str(account.get("web_profile_ref") or "").replace("\\", "/")
        if web_ref.endswith(f"browser-profiles/{profile}"):
            return True
    if email:
        found = (_clean_email(account.get("email")) or "").lower()
        if found == email.lower():
            return True
    return False


def mutate_remove(
    reg: dict[str, Any],
    *,
    profile: str | None = None,
    email: str | None = None,
    active_profile: str | None = None,
) -> dict[str, Any]:
    """从内存账本摘除一条。只动 registry.json，不删 CLI key 和网页会话目录。"""
    target_email = (_clean_email(email) or "").lower() or None
    if not profile and not target_email:
        return {"ok": False, "reason": "no_target", "message": "缺少要移除的 profile 或邮箱"}
    accounts = reg.get("accounts") or []
    active = str(active_profile or "")
    for index, account in enumerate(accounts):
        if not isinstance(account, dict):
            continue
        if not _account_matches(account, profile=profile, email=target_email):
            continue
        role = account.get("role")
        ref_name = fi.profile_from_ref(account.get("api_key_ref")) or ""
        if role in ("mother", "retired_mother") or (active and ref_name == active):
            return {
                "ok": False,
                "reason": "protected",
                "profile": ref_name or profile or "",
                "message": "母号（含已退休母号）不能移除；要换号请走交接班",
            }
        accounts.pop(index)
        return {
            "ok": True,
            "action": "removed",
            "profile": ref_name or profile or "",
            "email": _clean_email(account.get("email")),
            "message": "已从号池账本移除，本机 CLI key 与网页登录会话保留",
        }
    return {"ok": False, "reason": "not_in_pool", "message": "账本里没有这个账号"}


def mutate_relink(
    reg: dict[str, Any],
    *,
    email: str,
    profile: str,
    cli_exists: bool,
    web_dir_exists: bool,
    user_id: str | None = None,
) -> dict[str, Any]:
    """给一条缺 profile 引用的账本记录补登本机 profile（按邮箱匹配）。"""
    if not profile_name_ok(profile):
        return {"ok": False, "reason": "invalid_profile", "message": "profile 名不合法"}
    cleaned = _clean_email(email)
    if not cleaned:
        return {"ok": False, "reason": "no_email", "message": "登录后读不到邮箱"}
    accounts = reg.get("accounts") or []
    for other in accounts:
        if not isinstance(other, dict):
            continue
        owner = fi.profile_from_ref(other.get("api_key_ref")) or _web_ref_profile(other)
        if owner == profile and (_clean_email(other.get("email")) or "").lower() != cleaned.lower():
            return {
                "ok": False, "reason": "profile_owned", "profile": profile,
                "owner_email": _clean_email(other.get("email")),
                "message": f"profile {profile} 已属于另一个账号，不能关联到 {cleaned}",
            }
    for account in accounts:
        if not isinstance(account, dict):
            continue
        if (_clean_email(account.get("email")) or "").lower() != cleaned.lower():
            continue
        changed = False
        if web_dir_exists and _web_ref_profile(account) != profile:
            account["web_profile_ref"] = f"~/.flova-mcp/browser-profiles/{profile}"
            changed = True
        if cli_exists and fi.profile_from_ref(account.get("api_key_ref")) != profile:
            account["api_key_ref"] = f"flova-profile:{profile}"
            changed = True
        if user_id and not account.get("user_id"):
            account["user_id"] = user_id
            changed = True
        account["last_verified"] = _now()
        return {
            "ok": True, "action": "patched" if changed else "already",
            "profile": profile, "email": cleaned, "message": "已补登 profile 引用",
        }
    return {"ok": False, "reason": "email_not_in_pool", "email": cleaned,
            "message": "账本里没有这个邮箱，无法补登；请改用「录入已有账号」"}


def relink_registry_row(
    *,
    profile: str,
    email: str,
    user_id: str | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    try:
        cli_exists = profile in cli_profile_names()
    except Exception:
        cli_exists = False
    web_dir_exists = profile in web_profile_dirs()
    reg = load_pool_registry(registry_path)
    result = mutate_relink(
        reg, email=email, profile=profile,
        cli_exists=cli_exists, web_dir_exists=web_dir_exists, user_id=user_id,
    )
    if result.get("ok") and result.get("action") != "already":
        save_pool_registry(reg, registry_path)
    return result


def remove_from_pool(
    *,
    profile: str | None = None,
    email: str | None = None,
    registry_path: Path | None = None,
    active_profile: str | None = None,
) -> dict[str, Any]:
    target = registry_path or fi.REGISTRY
    reg = load_pool_registry(registry_path)
    if active_profile is None:
        active_profile = str(reg.get("active_mother_profile") or "")
    result = mutate_remove(
        reg,
        profile=profile or None,
        email=email or None,
        active_profile=active_profile,
    )
    if not result.get("ok"):
        return result
    if target.exists():
        stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
        backup = target.with_name(f"{target.stem}.bak-remove-{stamp}{target.suffix}")
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8", newline="")
        result["backup"] = backup.name
    save_pool_registry(reg, registry_path)
    return result
