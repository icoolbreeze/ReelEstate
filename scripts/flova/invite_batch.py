# -*- coding: utf-8 -*-
"""手动并行邀请一批子号（修复版）。

修复两点：
1. 邮箱池 flova.registered 标记从不回写，额外用 signals.flova_verification_seen
   排除已注册邮箱，避免重复选取被封旧号。
2. 邀请码（promotion_code）串行预热一次并缓存；并行线程不再各自启动母号
   browser-profile，消除 launchPersistentContext 会话冲突。

用法: python invite_batch.py 4
"""
from __future__ import annotations

import json
import sys

import requests

import flova_invite as fi
import flova_pricing as fp


def pick_fresh(n: int) -> list[dict[str, str]]:
    r = requests.get(
        f"{fi.MAILBOX_API}/v1/mailboxes",
        params={"provider": "outlook", "active": 1},
        timeout=30,
    )
    r.raise_for_status()
    used = fi.known_emails()
    eligible: list[dict] = []
    for m in r.json().get("mailboxes", []):
        reg = m.get("registration") or {}
        flova = reg.get("flova") or {}
        signals = reg.get("signals") or {}
        addr = (m.get("address") or "").strip()
        if not addr or not m.get("key"):
            continue
        if m.get("expired") or not m.get("active"):
            continue
        if flova.get("registered") is True:
            continue
        if signals.get("flova_verification_seen"):   # 已收过 Flova 验证码 = 已注册
            continue
        if addr.lower() in used:
            continue
        eligible.append(m)
    # 与 pick_mailboxes 同一顺序：无导入时间的最早一批先消费，再按 imported_at
    # 先导入先注册；不按接口返回顺序直接取前 n 个。
    eligible.sort(key=fi.mailbox_order_key)
    picked = [{"key": m["key"], "address": (m.get("address") or "").strip()}
              for m in eligible[:n]]
    if len(picked) < n:
        raise RuntimeError(f"need {n} genuinely fresh mailboxes, got {len(picked)}")
    return picked


def main(n: int, mother_profile: str = "prod",
         inviter_email: str | None = None) -> None:
    if inviter_email is None:
        # 和 ensure_credits 相同：账本里 role == "mother" 的账号 email；读不到就 None。
        inviter_email = next(
            (a.get("email") for a in fi.load_registry().get("accounts", [])
             if a.get("role") == "mother"),
            None,
        )
    # prod CLI profile 余额查询打桩（子号付款路径不需要母号余额；网页会话照常）。
    _orig_balance = fp.get_balance

    def _balance(profile: str) -> float:
        return 0.0 if str(profile) == "prod" else _orig_balance(profile)

    fp.get_balance = _balance

    # 邀请码串行预热一次。
    snap0 = fi.invite_snapshot(mother_profile)
    code = snap0["promotion_code"]
    print("promotion_code:", code, "| invite_reward_disabled:",
          snap0["invite_reward_disabled"])
    if not code:
        raise RuntimeError("no promotion code; cannot invite")

    # 缓存快照：并行线程不再各自启动母号 browser-profile。
    fi.invite_snapshot = lambda *a, **k: dict(snap0)
    fi.pick_mailboxes = lambda n: pick_fresh(n)

    with fi._Lock(fi.LOCK_PATH):
        slots = fi._allocate_slots(n)
        for s in slots:
            print("slot:", s["profile_name"], s["mailbox"]["address"], s["worker"][0])
        results = fi._run_parallel(mother_profile, slots)
        fi._record_children(results, inviter_email)

    print(json.dumps(results, ensure_ascii=False, indent=2))

    verified: list[dict] = []
    for r in results:
        if not r.get("ok"):
            continue
        prof = r["child_profile"]
        try:
            bal = _orig_balance(prof)
            verified.append({"profile": prof, "email": r["child_email"], "balance": bal})
        except Exception as e:
            verified.append({"profile": prof, "email": r["child_email"],
                             "error": str(e)[:160]})
    print("verified:", json.dumps(verified, ensure_ascii=False))


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    main(n)
