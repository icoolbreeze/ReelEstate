"""Flova Model Pricing Table 服务（v2，2026-09-21 按 grok 审核整改）。

闭环：
  生成前  quote() 预估成本（表价 × 实扣经验系数）+ assess() 判断积分够不够
  生成后  reconcile() 用实际余额差核对；revision 变化才标记表需重录

v2 整改（对应审核报告 P1-1/P1-2/P1-4）：
  1. 金额整数化：unit_usd 先 round 到 0.0001 再 ×100×数量，消除浮点 ceil 伪影
     （Wan 5s 表价 35 不再被报成 36）。
  2. 实扣经验系数表 ~/.flova/pricing_calibration.json：
     key = "model_key|resolution|variant"，value = 实扣/表价 中位数。
     quote() 返回 table_credits（纯表价）与 estimated_credits（×系数后的预算口径）。
     图片档当前经验系数 2.0（表5实10）；Wan 480p 按 8cr/s（40/5s）。
  3. stale 语义修正：reconcile 不匹配时先比对 remote revision——
     revision 变了 → 标 stale（表真的更新了）；没变 → 只记偏差到 calibration，
     不再把整张表打成 stale（系统性口径差 ≠ 表更新）。
  4. reconcile 有 CLI 子命令；探索奖励可从网页会话自动读取（需 web-session.js）。
  5. 视频参考时长：quantity = 生成秒数 + 参考视频总秒数（ref_seconds）；
     有 priceWithRefVideo 行用之，无该行（如 Wan）按标准单价 × 叠加时长。

余额读取走 flova CLI（`flova --profile <name> account user`）。
网页会话只读接口（积分桶/邀请/探索）见 web_ops()，走 ~/.flova-mcp/web-session.js。
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import time
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
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
    tmp = store_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(store_path)
    return store


def load(store_path: Path = STORE_PATH, *, max_age_hours: float | None = 24) -> dict[str, Any]:
    """读取已记录的价格表；缺失或过旧时自动拉取。

    注意：自动 refresh 不清除 stale 标记——stale 只由 reconcile 判定
    （revision 变化时）清除。
    """
    need_fetch = not store_path.exists()
    store = None
    if not need_fetch:
        store = json.loads(store_path.read_text(encoding="utf-8"))
        age_h = (time.time() - store["recorded_at"]) / 3600
        if max_age_hours is not None and age_h > max_age_hours:
            need_fetch = True
    if need_fetch:
        new_store = refresh(store_path)
        # 保留 stale 标记：数据老化重拉 ≠ 口径问题解决
        if store is not None and store.get("stale"):
            new_store["stale"] = True
            store_path.write_text(json.dumps(new_store, ensure_ascii=False, indent=2), encoding="utf-8")
        return new_store
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
    """实扣/表价经验系数；无记录返回 1.0。"""
    return float(_calib_load().get(calib_key(model_key, resolution, variant), 1.0))


def set_factor(model_key: str, resolution: str, factor: float, variant: str = "price") -> None:
    calib = _calib_load()
    calib[calib_key(model_key, resolution, variant)] = round(factor, 3)
    _calib_save(calib)


# ----------------------------- 查价层 ----------------------------------

def find_model(store: dict[str, Any], key: str) -> dict[str, Any]:
    for m in store["models"]:
        if m.get("key") == key:
            return m
    raise KeyError(f"model key not found: {key}")


def _unit_usd(model: dict[str, Any], resolution: str, *, with_ref_video: bool, member: bool) -> float:
    want_variant = "priceWithRefVideo" if with_ref_video else "price"
    res = resolution.lower()
    for p in model.get("prices", []):
        if p.get("resolution", "").lower() != res:
            continue
        if p.get("variant", "price") != want_variant:
            continue
        col = "member" if member else "normal"
        val = p.get(col)
        if isinstance(val, (int, float)):
            return float(val)
    # 回退：忽略 variant 精确匹配（如 Wan 3.0 无参考视频行）
    for p in model.get("prices", []):
        if p.get("resolution", "").lower() == res:
            col = "member" if member else "normal"
            val = p.get(col)
            if isinstance(val, (int, float)):
                return float(val)
    raise KeyError(f"no usable price for {model.get('key')} {resolution}")


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
    factor: float             # 实扣经验系数
    estimated_credits: int    # 预算口径 = ceil(table_credits × factor)
    quantity: float           # 计费数量：视频=生成+参考秒数；图/音=1
    ref_seconds: float        # 参考视频叠加时长
    resolution: str
    variant: str              # price / priceWithRefVideo
    member: bool


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
    """按 Model Pricing Table × 实扣系数 预估一次生成的积分成本。

    金额整数化：unit_usd → Decimal 四舍五入到 0.0001 → ×100 得表价积分，
    再 × 数量（视频为生成+参考秒数）后 ceil。
    """
    store = store or load()
    model = find_model(store, model_key)
    member = is_member(profile) if member is None and profile else bool(member)

    if resolution is None:
        res_param = next((x for x in model.get("params", []) if x["key"] == "resolution"), None)
        resolution = res_param["default"] if res_param else "default"

    unit = _unit_usd(model, resolution, with_ref_video=with_ref_video, member=bool(member))

    # 表价积分：整数化运算，消除 0.07*100 伪影
    unit_credits_dec = (Decimal(str(unit)) * USD_TO_CREDITS).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)

    if model["type"] == "video":
        dur_param = next((x for x in model.get("params", []) if x["key"] == "duration"), None)
        if seconds is None:
            seconds = float(dur_param["default"]) if dur_param else 5
        quantity = float(seconds) + float(ref_seconds)
        variant = "priceWithRefVideo" if with_ref_video else "price"
        # Wan 等无参考视频行的模型：回退标准单价，靠叠加时长计费
        raw = unit_credits_dec * Decimal(str(quantity))
    else:
        quantity = 1
        variant = "price"
        raw = unit_credits_dec

    table_credits = math.ceil(float(raw))

    factor = get_factor(model_key, resolution, variant)
    estimated = math.ceil(table_credits * factor)

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
    )


def assess(q: Quote, *, balance: float, count: int = 1) -> dict[str, Any]:
    """生成前判断积分是否够用（按预算口径 × 张数）。

    图片多张按 ``estimated_credits * count`` 留预算；视频 count 恒为 1。
    quote() 仍返回单张口径；总量口径只在这里和 preflight/postflight 里算。
    """
    count = max(1, int(count))
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
    """用实际余额差核对预估（预算口径）。

    actual = (before - after) + 本次首做奖励。
    对不上时：先比对 remote revision——
      变了 → mark_stale（表真的更新了，需 refresh 重录）；
      没变 → 记录偏差到校准表（更新经验系数），不动 stale。
    """
    actual = (balance_before - balance_after) + reward_credits
    diff = actual - q.estimated_credits
    matched = abs(diff) <= DISCREPANCY_TOL

    result: dict[str, Any] = {
        "balance_before": balance_before,
        "balance_after": balance_after,
        "reward_credits": reward_credits,
        "actual_credits": actual,
        "table_credits": q.table_credits,
        "budget_estimate": q.estimated_credits,
        "diff": diff,
        "matched": matched,
        "recorded_revision": load(store_path)["revision"],
    }

    if not matched and actual > 0:
        # 更新经验系数：实扣/表价（数量>1 时按单位）
        try:
            unit_actual = actual / q.quantity if q.quantity else actual
            unit_table = q.table_credits / q.quantity if q.quantity else q.table_credits
            if unit_table > 0:
                new_factor = unit_actual / unit_table
                old = get_factor(q.model_key, q.resolution, q.variant)
                # 取保守（较大）系数，避免单次异常拉低预算
                set_factor(q.model_key, q.resolution, max(old, new_factor), q.variant)
                result["factor_updated"] = {"old": old, "new": round(new_factor, 3)}
        except Exception as e:  # 校准失败不影响核对结论
            result["factor_error"] = str(e)[:120]

    if not matched:
        try:
            remote = remote_revision()
            if remote != result["recorded_revision"]:
                mark_stale(store_path)
                result["stale"] = True
                result["action"] = (
                    f"revision changed {result['recorded_revision']} -> {remote}; "
                    "pricing table updated, call refresh() to re-record"
                )
            else:
                result["stale"] = False
                result["action"] = (
                    "revision unchanged: systematic table-vs-actual gap; "
                    "factor calibrated, table NOT marked stale"
                )
        except Exception as e:
            result["stale"] = None
            result["action"] = f"revision check failed: {str(e)[:120]}"
    else:
        result["stale"] = False
        result["action"] = "matched"

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
                  ref_seconds: float = 0.0) -> dict[str, Any]:
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
        "exploration": exploration_snapshot(profile),
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
    count = max(1, int(count))
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
        _print_json(_calib_load())
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
                                  ref_seconds=a.ref_seconds))
    elif a.cmd == "postflight":
        before = None
        if a.exploration_before:
            before = json.loads(a.exploration_before)
        _print_json(cmd_postflight(a.model, profile=a.profile, resolution=a.resolution,
                                   count=a.count, balance_before=a.balance_before,
                                   exploration_before=before, seconds=a.seconds,
                                   ref_seconds=a.ref_seconds))
