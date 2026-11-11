# -*- coding: utf-8 -*-
"""人工邀请：开邀请链接，人自己完成注册，成功的新号和「手动注册」一样自动入账。

和 invite_manual.py 的区别：脚本不填邮箱、不领邮箱池、不点 Continue。
每个名额开一个全新随机指纹的无痕 Virtual Browser，打开邀请人链接，
人在窗口里用 Google 或邮箱自己注册；脚本只轮询登录态，读到已登录用户、
且邮箱不是邀请人邮箱即视为成功，然后走和 invite_manual.register_one
完全相同的收尾：adopt_web_session 采纳网页会话 → POST agent token →
_add_cli_profile 建 CLI profile。全部结束后 _record_children 写账本，
拿到 token 的新号 role=child/state=keyed 自动进号池；没拿到 token 的不写入。

邀请码只在进程内拼邀请链接，绝不打印。N 个串行，同一 worker id 不并发，
全程持有 flova_invite._Lock。

用法:
    python scripts/flova/invite_hand.py [N]
    python scripts/flova/invite_hand.py --profile <profile> [N]

省略 --profile 时用账本里的活跃母号。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flova_invite as fi
import flova_pricing as fp
from invite_batch import email_for_profile
from invite_manual import mother_email

HUMAN_SIGNUP_WAIT_SEC = 900     # 每个人工注册最长等 15 分钟
POLL_SEC = 3.0
GENERATOR_HOST = "https://www.flova.ai/"


def _vb_window_minimized() -> bool:
    """VB 后台最小化模式（默认）时提示「点任务栏」，不弹窗。"""
    try:
        import vb_backend as vbb
        return vbb.window_mode() == "minimized"
    except Exception:
        return False


def parse_args(argv: list[str] | None = None) -> tuple[int, str | None]:
    parser = argparse.ArgumentParser(description="Manually invite-register N children one at a time")
    parser.add_argument("n", nargs="?", type=int, default=1)
    parser.add_argument("--profile", default="")
    args = parser.parse_args(argv)
    if args.n < 1:
        parser.error("n must be >= 1")
    profile = args.profile.strip() or None
    if profile and not re.fullmatch(r"[A-Za-z0-9._-]+", profile):
        parser.error("invalid profile")
    return args.n, profile


def cli_invocation(argv: list[str] | None = None) -> dict:
    """形状与 invite_manual.cli_invocation 相同；不注册。"""
    count, profile = parse_args(argv)
    if profile:
        return {"n": count, "mother_profile": profile}
    return {"n": count, "mother_profile": None}


def _wait_new_user(browser, context, playwright, *, deadline: float, inviter_email: str | None) -> tuple[Any, dict]:
    """轮询直到出现已登录、且不是邀请人本人的用户。返回 (page, info)；超时返回 (None, {})。"""
    blocked = (inviter_email or "").strip().lower()
    import types
    while time.time() < deadline:
        contexts = list(browser.contexts) if hasattr(browser, "contexts") else [context]
        for ctx in contexts:
            # 1. 优先扫页面内部登录态（与网站真实环境完全同上下文）
            for pg in list(ctx.pages):
                try:
                    if "flova.ai" not in (pg.url or ""):
                        continue
                except Exception:
                    continue
                try:
                    info = fi.page_logged_in(pg)
                except Exception:
                    info = {}
                email = str(info.get("email") or "").strip().lower()
                if info.get("code") == 0 and email and email != blocked:
                    return pg, info
            # 2. 兜底扫 context CDP cookies
            try:
                cookies = fi.context_flova_cookies(ctx)
                if cookies:
                    req = playwright.request.new_context(
                        storage_state={"cookies": cookies, "origins": []})
                    try:
                        info = fi._web_get_user_info(types.SimpleNamespace(request=req))
                        email = str(info.get("email") or "").strip().lower()
                        if info.get("code") == 0 and email and email != blocked:
                            pg = ctx.pages[0] if ctx.pages else None
                            return pg, info
                    finally:
                        try:
                            req.dispose()
                        except Exception:
                            pass
            except Exception:
                pass
        time.sleep(POLL_SEC)
    return None, {}


def invite_one_hand(mother_profile: str, profile_name: str,
                    worker: fi.Worker, inviter_email: str | None) -> dict:
    """开一个随机指纹无痕 VB 走人工邀请注册；成功标准与 register_one 相同。"""
    worker_id = worker.id
    child_email = None
    child_token = None
    signup_err = None
    try:
        # 邀请码只在这里取、只用于拼链接，不打印、不进日志。
        code = fi.invite_snapshot(mother_profile)["promotion_code"]
        if not code:
            return {"ok": False, "reason": "no_promotion_code", "child_email": None}
        invite_url = f"{GENERATOR_HOST}?refCode={code}"

        port = fi.launch_worker(worker_id)
        fi.wait_cdp(port)
        time.sleep(2)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(invite_url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            minimized = fi.browser_backend() == "vb" and _vb_window_minimized()
            print(f"== 名额 {profile_name} | {fi.browser_backend()} {worker_id}："
                  + ("浏览器窗口已最小化到任务栏、不会自动弹出，点开任务栏图标后"
                     "用 Google 或邮箱自己完成注册，"
                     if minimized else "请在弹出的浏览器里用 Google 或邮箱自己完成注册，")
                  + f"最多等 {HUMAN_SIGNUP_WAIT_SEC // 60} 分钟 …",
                  file=sys.stderr, flush=True)
            pg, info = _wait_new_user(
                browser, ctx, p,
                deadline=time.time() + HUMAN_SIGNUP_WAIT_SEC,
                inviter_email=inviter_email,
            )
            if not info:
                browser.close()
                return {"ok": False, "reason": "human_signup_timeout",
                        "child_email": None}
            child_email = info.get("email")
            fi.adopt_web_session(profile_name, ctx,
                                 expected_email=child_email, playwright=p)
            # 优先从页面内请求 agent token（带完整 cookies/localStorage）
            target_page = pg if pg is not None else page
            try:
                import repair_cli
                child_token = repair_cli._mint_token_in_page(
                    target_page, f"hand-{int(time.time())}")
            except Exception:
                child_token = None
            browser.close()
    except Exception as exc:
        signup_err = str(exc)[:240]
    finally:
        fi.stop_worker(worker_id)

    if not child_token and child_email:
        # 页面内未拿到时，无头持久会话二次补救获取 token 并建 CLI
        try:
            import repair_cli
            rep = repair_cli.repair(profile_name)
            if rep.get("ok"):
                return {"ok": True, "reason": "keyed",
                        "child_email": child_email, "child_profile": profile_name}
        except Exception as exc:
            signup_err = str(exc)[:240]

    if not child_token:
        # 只要成功采纳了网页会话，就必须记录入账，由后续自动补 CLI 保证双绿标
        if child_email:
            return {"ok": True, "reason": "web_session",
                    "child_email": child_email, "child_profile": profile_name}
        return {"ok": False,
                "reason": signup_err or "token_missing",
                "child_email": child_email}
    fi._add_cli_profile(profile_name, child_token)
    return {"ok": True, "reason": "keyed",
            "child_email": child_email, "child_profile": profile_name}


def main(n: int, mother_profile: str | None = None) -> None:
    if mother_profile is None:
        mother_profile = fi.active_mother_profile()
        inviter_email = mother_email()
        print("active_mother_profile:", mother_profile, file=sys.stderr)
    else:
        inviter_email = email_for_profile(mother_profile)
        print("mother_profile:", mother_profile, file=sys.stderr)
    # 与 invite_manual 相同：prod 余额查询打桩（子号付款，不需要母号余额）。
    _orig_balance = fp.get_balance
    fp.get_balance = lambda p: 0.0 if str(p) == "prod" else _orig_balance(p)

    # 邀请码串行预热一次并缓存；绝不打印。
    snap0 = fi.invite_snapshot(mother_profile)
    if not snap0.get("promotion_code"):
        raise RuntimeError("no promotion code; cannot invite")
    fi.invite_snapshot = lambda *a, **k: dict(snap0)

    profiles = fi.next_child_profiles(n)
    pool = fi.next_workers(n)
    if not pool:
        raise RuntimeError(f"no {fi.browser_backend()} worker available in pool")
    workers = [pool[i % len(pool)] for i in range(n)]

    results = []
    # 串行：每个名额结束都 stop_worker，下一个才启动，同一 worker id 不并发。
    with fi._Lock(fi.LOCK_PATH):
        for prof, wk in zip(profiles, workers):
            r = invite_one_hand(mother_profile, prof, wk, inviter_email)
            print("   ->", "OK" if r.get("ok") else r.get("reason"),
                  prof, file=sys.stderr, flush=True)
            results.append(r)
        # 成功拿到 token 的新号在这里写入账本、自动进入号池；失败的不写入。
        fi._record_children(results, inviter_email)

    recorded = [r["child_profile"] for r in results if r.get("ok")]
    print(json.dumps({"ok": bool(recorded), "recorded": recorded,
                      "attempted": n}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main(**cli_invocation())
