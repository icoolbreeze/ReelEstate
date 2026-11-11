# -*- coding: utf-8 -*-
"""在随机指纹 Virtual Browser 里完成一次网页登录，并把会话采纳到本机 profile。

号池面板的「网页登录」「录入已有账号」「补登录关联 profile」统一走这里，
不再调用仓库外的 login-web.js（那个脚本用系统 Chrome/Edge 持久目录，不换指纹）。

流程：
  1. flova_invite.launch_worker 开一个无痕 VB（incognito=True、rotate=True，
     每次启动重写一套全新随机指纹），打开 https://www.flova.ai/en/generator/。
  2. 人在窗口里自己登录（Google 或邮箱都行）。轮询时读**浏览器 context 自己的
     cookie 罐**（context.cookies()，只留 flova 域），再用这些 cookie 开一个独立
     的纯 HTTP 请求上下文（playwright.request.new_context + storage_state，不开
     新 Chrome，用完即 dispose）打 get_user_info；code==0 且读到邮箱即成功，最多
     等 5 分钟。不能只靠 context.request：CDP 接入时它的 cookie 罐和页面登录态不是
     同一份。不自动填邮箱、不碰验证码。
  3. adopt_web_session 把登录成功的那个 context 的 flova cookie 收进
     ~/.flova-mcp/browser-profiles/<profile>（系统 Chrome 无头持久目录），
     然后 stop_worker 关掉 VB。
  4. --expect-email 给出时，邮箱不一致直接失败，adopt_web_session 会清空已导入
     cookie，不留半成品会话。

标准输出最终只打印一行 JSON，键只允许 profile / ok / backend /
fingerprint_rotated；过程提示和失败原因走 stderr，绝不打印邮箱、token、
cookie、邀请码。

用法:
    python scripts/flova/login_web.py --profile <name> [--expect-email <email>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flova_invite as fi
import pool_status as ps
import vb_backend as vbb

GENERATOR_URL = "https://www.flova.ai/en/generator/"
LOGIN_WAIT_SEC = 300.0
POLL_SEC = 3.0


class BrowserClosedError(RuntimeError):
    """轮询期间 CDP 断开 / 浏览器被关掉。"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Flova web sign-in via a fresh-fingerprint Virtual Browser")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--expect-email", default="")
    args = ap.parse_args(argv)
    args.profile = args.profile.strip()
    args.expect_email = args.expect_email.strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.profile):
        ap.error("invalid profile")
    if args.expect_email and (
        "@" not in args.expect_email
        or any(ch in args.expect_email for ch in " \r\n\t")
    ):
        ap.error("invalid --expect-email")
    return args


def session_ready(info: dict) -> bool:
    """get_user_info 结果只有 code==0 且邮箱非空才算已登录。"""
    return bool(info) and info.get("code") == 0 and bool(info.get("email"))


def _flova_cookies(context) -> list[dict]:
    """读 context 的 flova cookie（Playwright 罐为空时回退原始 CDP，已归一化）。

    VirtualBrowser 经 CDP 接入时 context.cookies() 实测为空，真实 cookie 只能用
    Network.getAllCookies 拿到；归一化逻辑统一在 flova_invite 里。
    """
    return fi.context_flova_cookies(context)


def _probe_context(context, playwright) -> dict:
    """用 context 自己的 flova cookie 开一个独立纯 HTTP 请求上下文验证登录态。

    不再只靠 context.request：CDP 接入时它的 cookie 罐与页面登录态可能不是同一份。
    这里不开新 Chrome，请求上下文用完立即 dispose。响应解析仍复用
    flova_invite._web_get_user_info（它只取入参的 .request.post）。
    """
    cookies = _flova_cookies(context)
    if not cookies:
        return {}
    req = playwright.request.new_context(
        storage_state={"cookies": cookies, "origins": []})
    try:
        holder = types.SimpleNamespace(request=req)
        return fi._web_get_user_info(holder)
    finally:
        try:
            req.dispose()
        except Exception:
            pass


def wait_logged_in(browser, playwright, *, deadline: float, profile: str):
    """轮询所有 context 的浏览器自有 cookie，直到某一个已登录。

    扫 browser.contexts 里的全部 context（含后来弹出的页面所属的新 context），
    不只是启动时的第一页。返回 (登录成功的 context, info)；超时返回 (None, {})；
    CDP 断开/浏览器被关掉立刻抛 BrowserClosedError。过程提示不含邮箱。
    """
    print(f"[{profile}] 浏览器已打开，请在窗口里登录 Flova，"
          f"最多等待 {int(LOGIN_WAIT_SEC // 60)} 分钟 …", file=sys.stderr, flush=True)
    while time.time() < deadline:
        try:
            contexts = list(browser.contexts)
        except Exception as exc:
            raise BrowserClosedError("browser closed during login wait") from exc
        if not contexts:
            if time.time() >= deadline:
                break
            time.sleep(POLL_SEC)
            continue
        for ctx in contexts:
            # 触碰 pages：context 已销毁时会抛错，触发上面的断开判断。
            try:
                pages = list(ctx.pages)
            except BrowserClosedError:
                raise
            except Exception:
                continue
            info: dict = {}
            # 主检测：在 flova 页面里 fetch，cookie 与 localStorage 令牌都会带上，
            # 与网站自身请求同环境，最可靠。
            for pg in pages:
                try:
                    if "flova.ai" not in (pg.url or ""):
                        continue
                except Exception:
                    continue
                try:
                    info = fi.page_logged_in(pg)
                except Exception:
                    info = {}
                if session_ready(info):
                    break
            # 兜底：拿 CDP cookie 开独立纯 HTTP 请求上下文（页面 fetch 异常时）。
            if not session_ready(info):
                try:
                    info = _probe_context(ctx, playwright)
                except Exception:
                    info = {}
            if session_ready(info):
                print(f"[{profile}] 已检测到登录，正在保存会话。",
                      file=sys.stderr, flush=True)
                return ctx, info
        time.sleep(POLL_SEC)
    # 再确认一次是不是浏览器已经没了，避免断开时还干等满超时。
    try:
        list(browser.contexts)
    except Exception as exc:
        raise BrowserClosedError("browser closed during login wait") from exc
    return None, {}


def login(profile: str, expect_email: str = "") -> dict:
    """开 VB 等登录、采纳会话。返回只含允许字段的结果 dict。

    网页登录一律随机指纹 Virtual Browser：直接调 vb_backend，
    incognito=True、rotate=True，不受 FLOVA_BROWSER_BACKEND 影响。
    """
    pool = vbb.worker_pool()
    if not pool:
        raise RuntimeError("no vb worker available in pool")
    worker_id = pool[0].id
    result = {
        "profile": profile,
        "ok": False,
        "backend": "vb",
        "fingerprint_rotated": True,
    }
    try:
        cc = vbb.country()
        port = vbb.launch_worker(
            int(worker_id), country_code=cc,
            incognito=True, rotate=True,
        )
        fi.wait_cdp(port)
        time.sleep(2)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            # 首屏偶发证书/中断错误（坏中继）时重连几次，每次连接会换中继。
            opened = False
            for attempt in range(1, 9):
                try:
                    page.goto(GENERATOR_URL, wait_until="domcontentloaded", timeout=45000)
                    if "flova.ai" in (page.url or ""):
                        opened = True
                        break
                except Exception:
                    pass
                time.sleep(2)
            if not opened:
                print(f"[{profile}] 页面多次打开失败（可能代理节点异常），未采纳会话。",
                      file=sys.stderr, flush=True)
                browser.close()
                return result
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            try:
                logged_ctx, info = wait_logged_in(
                    browser, p, deadline=time.time() + LOGIN_WAIT_SEC,
                    profile=profile)
            except BrowserClosedError:
                print(f"[{profile}] 浏览器已关闭，未检测到登录会话。",
                      file=sys.stderr, flush=True)
                return result
            if not logged_ctx:
                print(f"[{profile}] 等待登录超时，未采纳会话。",
                      file=sys.stderr, flush=True)
                browser.close()
                return result
            # 邮箱一致性由 adopt_web_session 校验；失败时它先清空会话再抛错。
            # 验证走同一个出口代理，避免登录态对 IP 敏感时被国内直连冲掉。
            fi.adopt_web_session(
                profile, logged_ctx,
                expected_email=expect_email or None,
                playwright=p,
                proxy_server=vbb.proxy_for(cc),
            )
            browser.close()
        # 网页登录/录入成功后自动补全 CLI，实现双绿标一步到位
        try:
            import repair_cli
            repair_cli.repair(profile)
        except Exception as rep_exc:
            print("auto repair cli note: " + ps.redact(str(rep_exc))[:200],
                  file=sys.stderr, flush=True)
        result["ok"] = True
        return result
    finally:
        vbb.stop_worker(int(worker_id))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = login(args.profile, args.expect_email)
    except Exception as exc:
        # 异常文本先打码再进 stderr；stdout 始终只有允许的四个键。
        print("login_web failed: " + ps.redact(str(exc))[:200],
              file=sys.stderr, flush=True)
        result = {
            "profile": args.profile,
            "ok": False,
            "backend": "vb",
            "fingerprint_rotated": True,
        }
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
