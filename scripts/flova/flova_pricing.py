"""Flova official model-price quoting and separate usage reconciliation.

Quotes follow https://config.flova.ai/config/model-list/read.
The official frontend converts normal/member values to credits by multiplying
by 100. Historical balance-delta calibration never changes an official quote.
Images: per-image price times count once. Videos: per-second price times the
applicable duration once. Balance deltas are observations, not billing receipts.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import time
import tempfile
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any

import requests

CONFIG_URL = "https://config.flova.ai/config/model-list/read"
FLOVA_BIN = r"C:\Users\shipi\AppData\Local\Programs\flova\flova.exe"
HOME = Path(os.environ.get("USERPROFILE", Path.home()))
STORE_PATH = HOME / ".flova" / "pricing_store.json"
CALIB_PATH = HOME / ".flova" / "pricing_calibration.json"
USD_TO_CREDITS = 100
# 容差：预算口径下实际与预估相差超过这么多积分，才认为对不上
DISCREPANCY_TOL = 2


# ----------------------------- 记录层 ----------------------------------

def fetch_remote() -> dict[str, Any]:
    r = requests.get(CONFIG_URL, timeout=30)
    r.raise_for_status()
    return r.json()


def refresh(store_path: Path = STORE_PATH) -> dict[str, Any]:
    """拉取最新价格表并版本化记录到本地（校准表保留）。"""
    raw = fetch_remote()
    data = raw["data"]
    store = {
        "recorded_at": time.time(),
        "source": CONFIG_URL,
        "usd_to_credits": USD_TO_CREDITS,
        "revision": data["revision"],
        "updated_at": data.get("updatedAt"),
        "stale": False,
        "models": data["models"],
    }
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=store_path.parent,
                                     prefix=store_path.name + ".", suffix=".tmp", delete=False) as stream:
        json.dump(store, stream, ensure_ascii=False, indent=2)
        temporary = Path(stream.name)
    try:
        temporary.replace(store_path)
    finally:
        temporary.unlink(missing_ok=True)
    return store


def load(store_path: Path = STORE_PATH, *, max_age_hours: float | None = 24) -> dict[str, Any]:
    """Load the official table, refreshing missing, stale or expired records."""
    if not store_path.exists():
        return refresh(store_path)
    store = json.loads(store_path.read_text(encoding="utf-8"))
    age_h = (time.time() - store["recorded_at"]) / 3600
    if store.get("stale") or (max_age_hours is not None and age_h > max_age_hours):
        return refresh(store_path)
    return store


def remote_revision() -> str:
    return fetch_remote()["data"]["revision"]


def mark_stale(store_path: Path = STORE_PATH) -> None:
    store = json.loads(store_path.read_text(encoding="utf-8"))
    store["stale"] = True
    store_path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def is_stale(store_path: Path = STORE_PATH) -> bool:
    return bool(load(store_path).get("stale"))


# ----------------------------- 校准层 ----------------------------------

def _calib_load() -> dict[str, float]:
    if CALIB_PATH.exists():
        return json.loads(CALIB_PATH.read_text(encoding="utf-8"))
    return {}


def _calib_save(calib: dict[str, float]) -> None:
    CALIB_PATH.parent.mkdir(parents=True, exist_ok=True)
    CALIB_PATH.write_text(json.dumps(calib, ensure_ascii=False, indent=2), encoding="utf-8")


def calib_key(model_key: str, resolution: str, variant: str = "price") -> str:
    return f"{model_key}|{str(resolution).lower()}|{variant}"


def get_factor(model_key: str, resolution: str, variant: str = "price") -> float:
    """Compatibility field: official quotes have no empirical multiplier."""
    return 1.0


def set_factor(model_key: str, resolution: str, factor: float, variant: str = "price") -> None:
    raise ValueError("Empirical price multipliers are disabled; quotes use the official model table")


# ----------------------------- 查价层 ----------------------------------

def find_model(store: dict[str, Any], key: str) -> dict[str, Any]:
    for m in store["models"]:
        if m.get("key") == key:
            return m
    raise KeyError(f"model key not found: {key}")


def _unit_usd(model: dict[str, Any], resolution: str, *, with_ref_video: bool, member: bool) -> float:
    variant = "priceWithRefVideo" if with_ref_video else "price"
    res = str(resolution).strip().lower()
    rows = [p for p in model.get("prices", []) if str(p.get("resolution", "")).lower() == res]
    exact = [p for p in rows if p.get("variant", "price") == variant]
    # Models without any reference-video tier use their documented base tier.
    if not exact and with_ref_video and not any(p.get("variant") == variant for p in model.get("prices", [])):
        exact = [p for p in rows if p.get("variant", "price") == "price"]
    exact = sorted(exact, key=lambda p: p.get("region", "default") != "default")
    if not exact:
        raise KeyError(f"no official price for {model.get('key')} {resolution} {variant}")
    col = "member" if member else "normal"
    value = exact[0].get(col)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"official price unavailable for {model.get('key')} {resolution} {col}")
    return float(value)


# ----------------------------- 余额层 ----------------------------------

def _cli_account(profile: str) -> dict[str, Any]:
    out = subprocess.run(
        [FLOVA_BIN, "--profile", profile, "account", "user"],
        capture_output=True, text=True, timeout=60,
    )
    if out.returncode != 0:
        raise RuntimeError(f"flova CLI failed (rc={out.returncode}): {out.stdout[:200]} {out.stderr[:200]}")
    data = json.loads(out.stdout)["data"]
    if not data:
        raise RuntimeError(f"flova CLI returned null data for profile {profile}")
    return data


def get_balance(profile: str) -> float:
    return float(_cli_account(profile)["credits_balance"])


def is_member(profile: str) -> bool:
    return bool(_cli_account(profile).get("subscription_info"))


# ----------------------------- 预估层 ----------------------------------

@dataclass
class Quote:
    model_key: str
    model_type: str
    unit_usd: float
    table_credits: int        # 纯表价（整数积分）
    factor: float             # 兼容字段，官方报价固定为1
    estimated_credits: int    # 官方表价，不乘经验系数
    quantity: float           # 计费数量：视频=生成+参考秒数；图/音=1
    ref_seconds: float        # 参考视频叠加时长
    resolution: str
    variant: str              # price / priceWithRefVideo
    member: bool
    pricing_source: str = CONFIG_URL
    pricing_revision: str = ""


def quote(
    model_key: str,
    *,
    profile: str | None = None,
    resolution: str | None = None,
    seconds: float | None = None,
    ref_seconds: float = 0.0,
    with_ref_video: bool = False,
    member: bool | None = None,
    store: dict[str, Any] | None = None,
) -> Quote:
    """按官方 Model Pricing Table 预估一次生成的积分成本，不使用历史系数。

    金额整数化：unit_usd → Decimal ×100 得表价积分，
    再 × 数量（视频为生成+参考秒数）后 ceil。
    """
    store = store or load()
    model = find_model(store, model_key)
    member = is_member(profile) if member is None and profile else bool(member)

    if resolution is None:
        res_param = next((x for x in model.get("params", []) if x["key"] == "resolution"), None)
        resolution = res_param["default"] if res_param else "default"

    ref_seconds = float(ref_seconds)
    if not math.isfinite(ref_seconds) or ref_seconds < 0:
        raise ValueError("ref_seconds must be finite and non-negative")
    with_ref_video = bool(with_ref_video or ref_seconds > 0)
    unit = _unit_usd(model, resolution, with_ref_video=with_ref_video, member=bool(member))
    unit_credits_dec = Decimal(str(unit)) * USD_TO_CREDITS
    if model["type"] == "video":
        duration = next((x for x in model.get("params", []) if x["key"] == "duration"), None)
        seconds = float(seconds if seconds is not None else duration["default"] if duration else 5)
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("seconds must be finite and positive")
        quantity = float(Decimal(str(seconds)) + Decimal(str(ref_seconds)))
        variant = "priceWithRefVideo" if with_ref_video else "price"
    else:
        if ref_seconds:
            raise ValueError("image/audio quote cannot include reference-video seconds")
        quantity = 1
        variant = "price"
    raw = unit_credits_dec * Decimal(str(quantity))
    table_credits = int(raw.to_integral_value(rounding=ROUND_CEILING))
    factor = 1.0  # The official table is authoritative; no historical calibration.
    estimated = table_credits

    return Quote(
        model_key=model_key,
        model_type=model["type"],
        unit_usd=unit,
        table_credits=table_credits,
        factor=factor,
        estimated_credits=estimated,
        quantity=quantity,
        ref_seconds=float(ref_seconds),
        resolution=resolution,
        variant=variant,
        member=bool(member),
        pricing_revision=str(store.get("revision", "")),
    )


def assess(q: Quote, *, balance: float, count: int = 1) -> dict[str, Any]:
    """生成前判断积分是否够用（按预算口径 × 张数）。

    图片多张按 ``estimated_credits * count`` 留预算；视频 count 恒为 1。
    quote() 仍返回单张口径；总量口径只在这里和 preflight/postflight 里算。
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer")
    budget = q.estimated_credits * count
    return {
        "balance": balance,
        "table_credits": q.table_credits,
        "factor": q.factor,
        "estimated_credits": q.estimated_credits,
        "count": count,
        "budget_credits": budget,
        "enough": balance >= budget,
        "shortfall": max(0, budget - balance),
    }


# ----------------------------- 核对层 ----------------------------------

def reconcile(
    q: Quote,
    *,
    balance_before: float,
    balance_after: float,
    reward_credits: float = 0.0,
    store_path: Path = STORE_PATH,
) -> dict[str, Any]:
    """Compare an unattributed balance observation with the official quote.

    Never treat concurrent spend, expiry, refunds, rewards or a whole batch as
    evidence for a new unit-price multiplier. Exact charges require task records.
    """
    observed = (balance_before - balance_after) + reward_credits
    diff = observed - q.estimated_credits
    matched = abs(diff) <= DISCREPANCY_TOL
    recorded = load(store_path)["revision"]
    result = {
        "balance_before": balance_before, "balance_after": balance_after,
        "reward_credits": reward_credits,
        "actual_credits": None,
        "observed_credits": observed,
        "observation_source": "balance_delta_plus_known_rewards_not_a_billing_receipt",
        "table_credits": q.table_credits, "budget_estimate": q.estimated_credits,
        "diff": diff, "matched": matched, "recorded_revision": recorded,
        "needs_usage_review": not matched, "factor_updated": False,
    }
    if matched:
        result.update(stale=False, action="balance observation matches official quote; confirm exact charges in Credit Details")
    else:
        try:
            remote = remote_revision()
            stale = remote != recorded
            if stale:
                mark_stale(store_path)
            result.update(stale=stale, action="refresh official price table" if stale else
                "review matching task charges, expiry, refunds and rewards in Credit Details; official quote unchanged")
        except Exception as exc:
            result.update(stale=None, action="official revision check failed; quote unchanged", revision_error=str(exc)[:120])
    return result


# ----------------------------- 网页会话只读接口 ---------------------------

import re as _re

_PROFILE_RE = _re.compile(r"^[A-Za-z0-9._-]+$")


def sanitize_profile(name: str | None) -> str:
    """与 web-session.js 同规则：合法字符子集，空/非法回退 prod。"""
    s = str(name or "prod").strip() or "prod"
    if not _PROFILE_RE.match(s):
        return "prod"
    return s


def web_ops_script(method: str, path: str, body: dict | None = None, profile: str = "prod") -> str:
    """生成经 web-session.js 调 service.flova.ai 的 node 脚本（含 profile）。

    抽成纯函数方便单测 grep/断言 profile 已透传；web_ops() 直接执行它。
    """
    profile = sanitize_profile(profile)
    script = (
        "const path=require('path');"
        f"const ws=require(path.join(process.env.USERPROFILE,'.flova-mcp','web-session.js'));"
        "ws.withSession(async ctx=>{"
        f"const r=await ctx.request.{method.lower()}('https://service.flova.ai{path}'"
        + (", {data:" + json.dumps(body or {}) + ", headers:{'content-type':'application/json'}}" if method.upper() == "POST" else "")
        + ");console.log(JSON.stringify(await r.json()));"
        + "},{headless:true,profile:" + json.dumps(profile) + "}).catch(e=>{console.error(e.message);process.exit(1)});"
    )
    return script


def web_ops(method: str, path: str, body: dict | None = None, timeout_ms: int = 60000,
            profile: str = "prod") -> dict:
    """经 ~/.flova-mcp/web-session.js 走指定 profile 网页会话调 service.flova.ai。

    method: "GET" 或 "POST"。valid_v2/stats/exploration_rewards 仅网页 cookie 可调。
    prod → browser-profile，其它 → browser-profiles/<name>（由 web-session 侧解析）。
    """
    import tempfile
    script = web_ops_script(method, path, body, profile=profile)
    tf = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    tf.write(script)
    tf.close()
    out = subprocess.run(["node", tf.name], capture_output=True, text=True, timeout=timeout_ms / 1000)
    os.unlink(tf.name)
    if out.returncode != 0:
        raise RuntimeError(f"web session call failed: {out.stderr[:200]}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def get_valid_credits_web(profile: str = "prod") -> dict:
    """指定号积分桶（含 invite_reward/exploration 等构成）。POST /valid_v2。"""
    return web_ops("POST", "/api/v2/user/plan/credits/valid_v2", {}, profile=profile)


def get_invite_stats_web(profile: str = "prod") -> dict:
    """邀请资格/计数/邀请码。GET /invite/promotion/stats。"""
    return web_ops("GET", "/api/v2/invite/promotion/stats", profile=profile)


def get_exploration_rewards_web(profile: str = "prod") -> dict:
    """12 项一次性探索奖励清单（status 0 未领 / 1 已领）。POST。"""
    return web_ops("POST", "/api/v2/user/exploration_rewards", {}, profile=profile)


def pending_exploration_bonus_web(profile: str = "prod") -> list[str]:
    """返回尚未领取的探索奖励 source 列表（30 天有效）。"""
    j = get_exploration_rewards_web(profile=profile)
    return [r["source"] for r in j.get("data", {}).get("rewards", []) if r.get("status") == 0]


def _reward_credits_of(item: dict) -> float:
    """从探索奖励条目里找数值奖励字段（credit_num / credits / reward / credit）。"""
    for k in ("init_amount", "credit_num", "credits", "reward", "credit"):
        v = item.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return 0.0


def exploration_snapshot(profile: str = "prod") -> list[dict] | None:
    """该 profile 探索奖励快照 [{source, status, credits}]；会话缺失/失败返回 None。"""
    try:
        j = get_exploration_rewards_web(profile=profile)
    except Exception:
        return None
    try:
        rewards = j.get("data", {}).get("rewards", [])
        if not isinstance(rewards, list):
            return None
        return [
            {"source": r.get("source"), "status": r.get("status"),
             "credits": _reward_credits_of(r)}
            for r in rewards if isinstance(r, dict)
        ]
    except Exception:
        return None


def web_session_ok(buckets: Any, snapshot: Any) -> bool:
    """纯判断（无网络）：网页会话有效 ⇔ 积分桶 JSON ``code == 0`` 且探索快照
    是**非空** list。

    HTTP 200 不代表登录：未登录的 Chrome 同样返回 JSON（code != 0），
    缺失/空快照也按未登录处理。flova_dispatch._probe 与 web 侧选号共用此门。
    """
    if not isinstance(buckets, dict) or buckets.get("code") != 0:
        return False
    return isinstance(snapshot, list) and len(snapshot) > 0


def cmd_preflight(model: str, profile: str = "prod", resolution: str | None = None,
                  count: int = 1, seconds: float | None = None,
                  ref_seconds: float = 0.0, include_exploration: bool = True) -> dict[str, Any]:
    """生成前：余额 + 单价报价 + 按张数 assess + 探索快照（单 JSON 由 CLI 打印）。"""
    from dataclasses import asdict as _asdict
    q = quote(model, profile=profile, resolution=resolution,
              seconds=seconds, ref_seconds=ref_seconds)
    balance = get_balance(profile)
    a = assess(q, balance=balance, count=count)
    return {
        "profile": sanitize_profile(profile),
        "pricing_model": model,
        "resolution": q.resolution,
        "count": max(1, int(count)),
        "quote": _asdict(q),
        "table_credits": q.table_credits,
        "budget_credits": a["budget_credits"],
        "balance": balance,
        "enough": a["enough"],
        "shortfall": a["shortfall"],
        "exploration": exploration_snapshot(profile) if include_exploration else None,
    }


def cmd_postflight(model: str, profile: str = "prod", resolution: str | None = None,
                   count: int = 1, balance_before: float = 0.0,
                   exploration_before: list | None = None,
                   seconds: float | None = None,
                   ref_seconds: float = 0.0) -> dict[str, Any]:
    """生成后：实际余额差 + 探索 0→1 奖励 → reconcile。

    图片多张按总量核对：把 Quote 的 estimated/table 同乘 count、quantity 置为
    count（视频 quantity 保持生成秒数），actual=(b0-b1)+reward 与总量预算比；
    这样校准层按单位回算（actual/count ÷ table/count）不会被总量污染。
    """
    from dataclasses import replace as _replace
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer")
    q = quote(model, profile=profile, resolution=resolution,
              seconds=seconds, ref_seconds=ref_seconds)
    b1 = get_balance(profile)
    reward = 0.0
    claimed: list[str] = []
    if isinstance(exploration_before, list):
        try:
            after = exploration_snapshot(profile)
            if after is not None:
                before_status = {r.get("source"): r.get("status")
                                 for r in exploration_before if isinstance(r, dict)}
                for r in after:
                    src = r.get("source")
                    if before_status.get(src) == 0 and r.get("status") == 1:
                        c = float(r.get("credits", 0) or 0)
                        reward += c
                        claimed.append(src)
        except Exception:
            reward = 0.0
            claimed = []
    if q.model_type != "video" and count > 1:
        q = _replace(q, estimated_credits=q.estimated_credits * count,
                     table_credits=q.table_credits * count,
                     quantity=float(count))
    r = reconcile(q, balance_before=balance_before, balance_after=b1,
                  reward_credits=reward)
    r["reward_credits"] = reward
    r["balance_after"] = b1
    r["claimed_sources"] = claimed
    return r


# ----------------------------- CLI ----------------------------------

def _print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=[
        "refresh", "show", "quote", "stale", "reconcile",
        "factors", "set-factor", "buckets", "invite", "exploration",
        "preflight", "postflight",
    ])
    ap.add_argument("--skip-exploration", action="store_true", help="Read-only pool pricing probe without opening web sessions")
    ap.add_argument("--model")
    ap.add_argument("--profile", default="prod")
    ap.add_argument("--resolution")
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--ref-seconds", type=float, default=0.0)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--balance-before", type=float)
    ap.add_argument("--balance-after", type=float)
    ap.add_argument("--reward", type=float, default=0.0)
    ap.add_argument("--exploration-before", default=None,
                    help="JSON array snapshot from preflight.exploration, or omit")
    ap.add_argument("--key")   # model|resolution|variant
    ap.add_argument("--factor", type=float)
    a = ap.parse_args()

    if a.cmd == "refresh":
        s = refresh(); print("revision:", s["revision"], "models:", len(s["models"]))
    elif a.cmd == "stale":
        print("stale:", is_stale())
    elif a.cmd == "show":
        s = load(); print("revision:", s["revision"], "stale:", s.get("stale"), "models:", len(s["models"]))
    elif a.cmd == "quote":
        q = quote(a.model, profile=a.profile, resolution=a.resolution,
                  seconds=a.seconds, ref_seconds=a.ref_seconds)
        _print_json(asdict(q))
        _print_json(assess(q, balance=get_balance(a.profile), count=a.count))
    elif a.cmd == "reconcile":
        q = quote(a.model, profile=a.profile, resolution=a.resolution,
                  seconds=a.seconds, ref_seconds=a.ref_seconds)
        r = reconcile(q, balance_before=a.balance_before,
                      balance_after=a.balance_after, reward_credits=a.reward)
        _print_json(r)
    elif a.cmd == "factors":
        _print_json({"used_for_quotes": False, "legacy_factors": _calib_load()})
    elif a.cmd == "set-factor":
        model, res, var = (a.key.split("|") + ["price"])[:3]
        set_factor(model, res, a.factor, var)
        print("set", a.key, "=", a.factor)
    elif a.cmd == "buckets":
        _print_json(get_valid_credits_web(profile=a.profile))
    elif a.cmd == "invite":
        _print_json(get_invite_stats_web(profile=a.profile))
    elif a.cmd == "exploration":
        _print_json(get_exploration_rewards_web(profile=a.profile))
    elif a.cmd == "preflight":
        _print_json(cmd_preflight(a.model, profile=a.profile, resolution=a.resolution,
                                  count=a.count, seconds=a.seconds,
                                  ref_seconds=a.ref_seconds, include_exploration=not a.skip_exploration))
    elif a.cmd == "postflight":
        before = None
        if a.exploration_before:
            before = json.loads(a.exploration_before)
        _print_json(cmd_postflight(a.model, profile=a.profile, resolution=a.resolution,
                                   count=a.count, balance_before=a.balance_before,
                                   exploration_before=before, seconds=a.seconds,
                                   ref_seconds=a.ref_seconds))
