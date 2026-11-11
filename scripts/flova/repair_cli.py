# -*- coding: utf-8 -*-
"""CLI 掉线但网页仍在线时，用已采纳的网页会话补建 CLI profile。

适用场景（如 kid6，不要在代码里写死具体名字）：``flova profile list`` 里
没有这个 profile，而 ``~/.flova-mcp/browser-profiles/<name>`` 的 cookie 仍能
读出登录用户。这是**读旧会话**，不是新登录：系统 Chrome/Edge 无头持久上下文
（与 adopt_web_session 相同的目录布局），不会打开可见浏览器，也不调用
``flova auth login`` 默认的开浏览器模式。

流程：
  1. 无头打开已采纳的 profile 目录，_web_get_user_info 校验 code==0；
     code!=0（会话失效）直接失败，提示先用 login_web.py 做 VB 网页登录。
  2. 用同一上下文 POST /api/agent/v2/token 拿 agent token，
     fi._add_cli_profile 建 CLI profile（内部 profile add + auth login --token
     + 默认切回 prod）。token 不打印、不写仓库、不进异常文本。
  3. load_registry / save_registry 只更新该 profile 的账本行：
     api_key_ref=flova-profile:<name>、state=keyed、last_verified。
     不改别的账号，不存余额。

用法:
    python scripts/flova/repair_cli.py --profile <name>
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flova_invite as fi
import pool_status as ps
import vb_backend as vbb

TOKEN_URL = "https://service.flova.ai/api/agent/v2/token"


def _mint_token_in_page(page, token_name: str) -> str:
    """在页面里 POST /token 换 agent token（cookie/localStorage 都自动带上）。

    不用 context.request：VirtualBrowser/CDP 下它的 cookie 罐与页面登录态可能不是
    同一份。token 只在 Python 进程内返回，绝不打印/落盘。
    """
    payload = json.dumps({"name": token_name})
    res = page.evaluate(
        """async (body) => {
            try {
              const r = await fetch(%s, {
                method:'POST',
                headers:{'content-type':'application/json'},
                body: body, credentials:'include'});
              const j = await r.json().catch(()=>({}));
              return {status:r.status, token:(j.data && j.data.token) || null,
                      code:j.code, message:j.message || null};
            } catch (e) { return {error:String(e).slice(0,160)}; }
          }""" % json.dumps(TOKEN_URL),
        payload,
    )
    if not isinstance(res, dict) or res.get("error"):
        raise RuntimeError("token request failed in page")
    token = res.get("token")
    if not token:
        raise RuntimeError("agent token missing in web response")
    return token


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Rebuild a flova CLI profile from the adopted web session")
    ap.add_argument("--profile", required=True)
    args = ap.parse_args(argv)
    args.profile = args.profile.strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.profile):
        ap.error("invalid profile")
    return args


def token_from_web_session(profile: str) -> tuple[str, str | None, str | None]:
    """用已采纳的无头持久会话读用户并换 token。

    返回 (token, email, user_id)。网页未登录时抛 RuntimeError（错误文本不含
    邮箱/token）。走与网页登录同一个出口代理：登录态若对 IP 敏感，国内直连换 token
    可能把会话冲掉或被判未登录。
    """
    profile_dir = fi.WEB_PROFILES_DIR / profile
    if not profile_dir.is_dir():
        raise RuntimeError(
            f"no adopted web session for {profile}; run login_web.py first")
    proxy_server = vbb.proxy_for(vbb.country())
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        launch_kwargs: dict = dict(
            executable_path=fi._system_chrome(),
            headless=True,
            args=["--no-default-browser-check", "--no-first-run",
                  "--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 860},
        )
        try:
            vbb.ensure_proxy(vbb.country())
            launch_kwargs["proxy"] = {"server": proxy_server}
        except Exception:
            # 代理不可用时退回直连，但优先仍尝试代理路径。
            pass
        ctx = p.chromium.launch_persistent_context(str(profile_dir), **launch_kwargs)
        try:
            page = ctx.new_page()
            page.goto("https://www.flova.ai/en/",
                      wait_until="domcontentloaded", timeout=45000)
            info: dict = {}
            for _ in range(6):
                info = fi.page_logged_in(page)
                if info.get("code") == 0 and info.get("email"):
                    break
                time.sleep(1.5)
            if info.get("code") != 0 or not info.get("email"):
                raise RuntimeError(
                    "web session is not logged in; run login_web.py "
                    "(fresh-fingerprint Virtual Browser) first")
            token = _mint_token_in_page(page, f"repair-{int(time.time())}")
            return token, info.get("email"), info.get("user_id")
        finally:
            ctx.close()


def update_registry_row(profile: str) -> int:
    """只把该 profile 的账本行置为 keyed。返回更新条数。不写余额。"""
    reg = fi.load_registry()
    want_ref = f"flova-profile:{profile}"
    changed = 0
    for account in reg.get("accounts", []):
        if not isinstance(account, dict):
            continue
        ref_name = fi.profile_from_ref(account.get("api_key_ref"))
        web_name = ""
        web_ref = str(account.get("web_profile_ref") or "").replace("\\", "/")
        m = re.search(r"browser-profiles/([A-Za-z0-9._-]+)$", web_ref)
        if m:
            web_name = m.group(1)
        if ref_name != profile and web_name != profile:
            continue
        account["api_key_ref"] = want_ref
        account["state"] = "keyed"
        account["last_verified"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        changed += 1
    if changed:
        reg["updated_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        fi.save_registry(reg)
    return changed


def cli_login_plan(profile_exists: bool) -> str:
    """CLI profile 名已存在时只重新登录换 token；不存在时先 add 再登录。"""
    return "login_only" if profile_exists else "add_and_login"


def _login_token_only(profile: str, token: str) -> None:
    """与 flova_invite._add_cli_profile 后半相同的两步，跳过 profile add。

    token 只作为子进程参数传递，不打印、不写文件；login 非 0 即失败，
    异常文本先打码再抛，防止 CLI 输出里带出 token。
    """
    login = subprocess.run(
        [fi.FLOVA_BIN, "--profile", profile, "auth", "login", "--token", token],
        capture_output=True, text=True, timeout=30,
    )
    subprocess.run(
        [fi.FLOVA_BIN, "profile", "use", "prod"],
        capture_output=True, text=True, timeout=20,
    )
    if login.returncode != 0:
        raise RuntimeError(ps.redact(
            f"auth login failed: {login.stderr or login.stdout}"[:300]))


def repair(profile: str) -> dict:
    token, _email, _user_id = token_from_web_session(profile)
    # 名字可能还在 CLI profile 列表里、只是 token 失效：这种情况不能再
    # profile add（名字冲突会直接失败），只跑 auth login --token。
    plan = cli_login_plan(profile in fi.known_profiles())
    if plan == "login_only":
        _login_token_only(profile, token)
    else:
        # token 只在进程内传给 _add_cli_profile，不落任何输出。
        fi._add_cli_profile(profile, token)
    updated = update_registry_row(profile)
    return {"profile": profile, "ok": True,
            "plan": plan, "registry_rows_updated": updated}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = repair(args.profile)
    except Exception as exc:
        # 异常先打码：防止 token / cookie / 邮箱混进错误文本。
        print("repair_cli failed: " + ps.redact(str(exc))[:200],
              file=sys.stderr, flush=True)
        print(json.dumps({"profile": args.profile, "ok": False},
                         ensure_ascii=False), flush=True)
        return 1
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
