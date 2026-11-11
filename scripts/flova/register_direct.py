# -*- coding: utf-8 -*-
"""直接执行子号注册（不带任何邀请码 / 不进行邀请，纯直接注册）。

用于排查邀请链路或直接获取新账号。
使用 Virtual Browser 后端（无痕模式、按国家自洽指纹与代理）。
遇滑块时在终端打印提示并等待人工滑过。

用法:
    python scripts/flova/register_direct.py [--email <addr>] [--key <key>] [--profile <name>]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# 加入当前目录
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flova_invite as fi
import flova_pricing as fp
import vb_backend as vbb

DIRECT_URL = "https://www.flova.ai/"


def main() -> int:
    ap = argparse.ArgumentParser(description="Directly register a new flova account without invite refCode")
    ap.add_argument("--email", default="", help="Mailbox address (default: pick fresh from pool)")
    ap.add_argument("--key", default="", help="Mailbox key")
    ap.add_argument("--profile", default="", help="Profile name (default: next kid name)")
    args = ap.parse_args()

    # 1. 挑选邮箱
    if args.email and args.key:
        mb = {"address": args.email.strip(), "key": args.key.strip()}
    else:
        # 从邮箱池挑选真正未注册的新鲜邮箱
        picked = fi.pick_mailboxes(1)
        if not picked:
            print("ERROR: no fresh mailbox available in pool", file=sys.stderr)
            return 2
        mb = picked[0]

    # 2. profile 名称
    prof_name = args.profile.strip() or fi.next_child_profiles(1)[0]

    # 3. worker 分配
    worker = fi.next_workers(1)[0]

    print(f"============================================================")
    print(f"直接注册（不进行邀请，无 refCode）")
    print(f"  邮箱:    {mb['address']} (key: {mb['key']})")
    print(f"  Profile: {prof_name}")
    print(f"  Worker:  {fi.browser_backend()} {worker.id}")
    print(f"  URL:     {DIRECT_URL}")
    print(f"============================================================", flush=True)

    port = None
    child_token = None
    signup_err = None

    try:
        # 启动 VB worker（无痕、自动轮换指纹）
        port = fi.launch_worker(worker.id)
        fi.wait_cdp(port)
        time.sleep(2)

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            print(f"打开官网落地页: {DIRECT_URL} ...", flush=True)
            page.goto(DIRECT_URL, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass

            # 打开注册/登录面板并提交邮箱 + OTP
            print("打开 Email 认证面板并开始提交...", flush=True)
            fi._begin_email_auth(page, signup=True)
            fi._submit_email_and_otp(page, mb["address"], mb["key"], signup=True)

            still_cta = page.evaluate("document.body.innerText.includes('Sign up for 300')")
            if still_cta:
                raise RuntimeError("still on signup CTA after OTP")

            # 采纳网页会话到 ~/.flova-mcp/browser-profiles/<prof_name>
            print("采纳网页会话到 MCP profiles...", flush=True)
            fi.adopt_web_session(prof_name, ctx, expected_email=mb["address"], playwright=p)

            # 获取 agent API token
            print("获取 Agent API Token...", flush=True)
            tok = ctx.request.post(
                "https://service.flova.ai/api/agent/v2/token",
                headers={"content-type": "application/json"},
                data=json.dumps({"name": f"direct-{int(time.time())}"}),
            )
            body = tok.json()
            child_token = (body.get("data") or {}).get("token")
            browser.close()

    except Exception as e:
        signup_err = str(e)[:300]
        print(f"注册过程异常: {signup_err}", file=sys.stderr, flush=True)
    finally:
        if port:
            fi.stop_worker(worker.id)

    if not child_token:
        print(json.dumps({
            "ok": False,
            "reason": signup_err or "token_missing",
            "email": mb["address"],
            "profile": prof_name,
        }, ensure_ascii=False, indent=2))
        return 1

    # 4. 配置 CLI profile
    print(f"配置 CLI profile {prof_name}...", flush=True)
    fi._add_cli_profile(prof_name, child_token)

    # 5. 记录到账本 registry.json
    reg = fi.load_registry()
    known = {a.get("email", "").lower() for a in reg.get("accounts", [])}
    if mb["address"].lower() not in known:
        reg.setdefault("accounts", []).append({
            "email": mb["address"],
            "role": "child",
            "state": "keyed",
            "invited_by": None,  # 直接注册，不通过邀请
            "api_key_ref": f"flova-profile:{prof_name}",
            "web_profile_ref": f"~/.flova-mcp/browser-profiles/{prof_name}",
            "last_verified": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "notes": "direct signup via register_direct.py (no invite refCode)",
        })
        reg["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        fi.save_registry(reg)

    # 6. 查询新账号余额
    bal = None
    try:
        bal = fp.get_balance(prof_name)
    except Exception as e:
        bal = f"get_balance error: {e}"

    res = {
        "ok": True,
        "email": mb["address"],
        "profile": prof_name,
        "balance": bal,
        "token_obtained": bool(child_token),
        "web_profile": f"~/.flova-mcp/browser-profiles/{prof_name}",
    }
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
