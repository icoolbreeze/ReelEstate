# -*- coding: utf-8 -*-
"""人工辅助注册（顺序注册，一次一个，方便人工）。两种验证分别处理：

- 复选框验证（Cloudflare Turnstile，已出现但还没签发 cf-turnstile-response）：
  不点击复选框，约每 0.3s 轮询，一看到复选框就立刻自动刷新当前页（不等观察窗口），
  刷新后重新打开邮箱面板、把同一个邮箱再输一遍，最多刷新 3 次，仍没有 token 再失败。
  检测穿透所有 frame（含 frame.url 与 “Verify you are human” 文本）并递归进入
  open shadow root。自动路径 flova_invite 共用同一套实现。
- 滑动验证（阿里云拼图 #aliyunCaptcha-mask）：停住等用户人工滑过，只轮询等待，
  不自动拖滑块、不刷新页面、不点击复选框，单个验证最多等 900 秒。
- 两种验证同时出现时先等用户滑完滑块，再处理复选框。

用法:
    python invite_manual.py [N]
    python invite_manual.py --profile <profile> [N]

省略 --profile 时仍用账本里的活跃母号。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import flova_invite as fi
import flova_pricing as fp
from invite_batch import email_for_profile, pick_fresh

HUMAN_WAIT_SEC = 900          # 单个滑块验证人工等待上限
TURNSTILE_MAX_RELOADS = 3     # Turnstile 复选框未签发 token 时最多刷新次数
TURNSTILE_WAIT_SEC = 30.0     # 每次刷新后等 Turnstile 签发 token 的观察窗口


def mother_email() -> str | None:
    """和 ensure_credits 相同：账本里 role == "mother" 的账号 email；读不到就 None。"""
    return next(
        (a.get("email") for a in fi.load_registry().get("accounts", [])
         if a.get("role") == "mother"),
        None,
    )


def captcha_mask_visible(page) -> bool:
    return bool(page.evaluate(
        """() => { const m=document.getElementById('aliyunCaptcha-mask');
          if(!m) return false;
          return m.classList.contains('mask-show') && getComputedStyle(m).display!=='none'; }"""
    ))


# 在单个 frame 内扫描：递归进入 open shadow root（document.querySelector 进不去）。
# 返回 {checkbox, token, human_text}。closed shadow root 和跨域 iframe 内部仍然不可见。
_TURNSTILE_DETECT_JS = """
() => {
  const re = /turnstile|challenges\\.cloudflare\\.com|cloudflare/i;
  let checkbox = false;
  let token = false;
  let human_text = false;
  const seenRoots = new Set();
  function scan(root) {
    if (!root || seenRoots.has(root)) return;
    seenRoots.add(root);
    const els = root.querySelectorAll ? root.querySelectorAll('*') : [];
    for (const el of els) {
      if (el.tagName === 'INPUT'
          && el.getAttribute('name') === 'cf-turnstile-response'
          && el.value) token = true;
      const cls = el.getAttribute('class');
      if (cls && cls.indexOf('cf-turnstile') !== -1) checkbox = true;
      if (el.tagName === 'IFRAME'
          && (re.test(el.getAttribute('src') || '')
              || re.test(el.getAttribute('title') || ''))) checkbox = true;
      if (el.shadowRoot) scan(el.shadowRoot);
    }
  }
  scan(document);
  const text = ((document.body && (document.body.innerText || document.body.textContent)) || '');
  if (text.toLowerCase().indexOf('verify you are human') !== -1) human_text = true;
  return {checkbox: checkbox, token: token, human_text: human_text};
}
"""

TURNSTILE_URL_HINTS = ("turnstile", "challenges.cloudflare.com")
TURNSTILE_HUMAN_TEXT = "verify you are human"


def turnstile_url_match(url: str | None) -> bool:
    """纯 URL 判断（大小写不敏感）：URL 含 turnstile / challenges.cloudflare.com。

    用于 Playwright ``frame.url``：iframe 元素即使藏在 closed shadow root、
    querySelector 够不到，frame.url 仍然可见。
    """
    u = str(url or "").lower()
    return any(hint in u for hint in TURNSTILE_URL_HINTS)


def turnstile_text_match(text: str | None) -> bool:
    """纯文本判断（大小写不敏感）：frame 文档文本含 “Verify you are human”。"""
    return TURNSTILE_HUMAN_TEXT in str(text or "").lower()


def turnstile_state(page) -> tuple[bool, bool]:
    """穿透所有 frame + open shadow root 检测 Turnstile，返回 (checkbox, token)。

    复选框判定（任一成立）：

    - frame 文档/open shadow root 里有 ``.cf-turnstile``，或 src/title 含
      turnstile / challenges.cloudflare.com / Cloudflare 的 iframe；
    - Playwright ``frame.url`` 含 turnstile / challenges.cloudflare.com——
      iframe 元素即使藏在 closed shadow root、querySelector 够不到也算；
    - frame 文档文本含 “Verify you are human”。

    token 检测同样穿透：任一 frame 里非空 ``cf-turnstile-response`` 即已签发。
    frame.evaluate 抛错（跨域等）时只跳过该 frame 的 DOM/文本读取，
    frame.url 判定仍然有效。
    """
    checkbox = False
    token = False
    for frame in page.frames:
        try:
            frame_url = frame.url
        except Exception:
            frame_url = ""
        if turnstile_url_match(frame_url):
            checkbox = True
        try:
            r = frame.evaluate(_TURNSTILE_DETECT_JS)
        except Exception:
            continue
        if isinstance(r, dict):
            checkbox = (checkbox
                        or bool(r.get("checkbox"))
                        or bool(r.get("human_text")))
            token = token or bool(r.get("token"))
    return checkbox, token


def turnstile_pending(page) -> bool:
    """复选框验证（Cloudflare Turnstile）已出现但还没签发 token。

    cf-turnstile-response 已有值（token 已签发）不算 pending。
    """
    checkbox, token = turnstile_state(page)
    return checkbox and not token


def turnstile_decision(*, checkbox: bool, token: bool, slide: bool,
                       reloads: int) -> str:
    """根据当前页面状态决定下一步（纯逻辑、无浏览器，方便测试）。

    返回:
      "continue": token 已签发，继续点 Continue with Email，不刷新
      "wait":     滑块可见（优先等用户滑完），或还没看到复选框（窗口内继续观察）
      "refresh":  复选框已出现且没 token、没滑块，立刻刷新
      "fail":     复选框仍在但刷新次数已用完
    """
    if token:
        return "continue"
    if slide:
        return "wait"
    if not checkbox:
        return "wait"
    if reloads >= TURNSTILE_MAX_RELOADS:
        return "fail"
    return "refresh"


def restore_window(page) -> None:
    """把浏览器窗口恢复到前台。

    后台最小化模式（FLOVA_VB_WINDOW=minimized，默认）下需要人工滑验证码时调用；
    窗口已是前台时是幂等的空操作，失败静默（不阻塞验证码等待）。
    """
    try:
        cdp = page.context.new_cdp_session(page)
        w = cdp.send("Browser.getWindowForTarget")
        cdp.send("Browser.setWindowBounds",
                 {"windowId": w["windowId"],
                  "bounds": {"windowState": "normal"}})
        page.bring_to_front()
    except Exception:
        pass


def settle_captcha(page, label: str = "", *, settle_window: float = 10.0,
                   human_timeout: float = float(HUMAN_WAIT_SEC)) -> None:
    """轮询等待拼图弹窗（含延迟弹出）；一旦出现就等人工滑过。

    弹窗未出现时持续观察 settle_window 秒；滑过后重新开窗，防止连弹。
    后台最小化模式下先把窗口恢复到前台再等人工。
    """
    announced = False
    quiet_until = time.time() + settle_window
    while True:
        if captcha_mask_visible(page):
            if not announced:
                restore_window(page)
                print(f"  ⏳ 已把浏览器窗口调到前台，请人工滑动拼图验证码"
                      f"{('（' + label + '）') if label else ''}，"
                      "滑过后自动继续 …", flush=True)
                announced = True
            t0 = time.time()
            while captcha_mask_visible(page):
                if time.time() - t0 > human_timeout:
                    raise RuntimeError("human captcha wait timeout")
                time.sleep(1)
            print("  ✅ 验证码已通过，继续。", flush=True)
            announced = False
            quiet_until = time.time() + settle_window
            time.sleep(0.8)
        else:
            if time.time() >= quiet_until:
                return
            time.sleep(0.5)


def _type_email(page, email: str) -> None:
    """键盘输入邮箱；聚焦不做命中检测，避免被遮罩挡住而超时。"""
    inp = page.query_selector("input[name=email]")
    if not inp:
        raise RuntimeError("email input not found")
    inp.focus()
    time.sleep(0.3)
    page.keyboard.type(email, delay=70)
    time.sleep(1.2)


def _reload_for_turnstile(page, email: str, fallback_url: str, attempt: int,
                          *, signup: bool) -> None:
    """Turnstile 复选框未签发 token：刷新当前页，重新打开邮箱面板并重填邮箱。

    signup=True 重新点 “Sign up for 300 credits”；signup=False（登录）重新打开
    登录面板，不点注册 CTA。调用方必须先确认滑动验证不可见——滑块在时禁止刷新。
    不点击复选框。
    """
    panel = "注册" if signup else "登录"
    print(f"  ↻ Turnstile 复选框未签发 token，刷新页面（{panel}，"
          f"第 {attempt}/{TURNSTILE_MAX_RELOADS} 次）…", flush=True)
    try:
        page.reload(wait_until="domcontentloaded", timeout=60000)
    except Exception:
        page.goto(fallback_url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    fi._begin_email_auth(page, signup=signup)
    settle_captcha(page, "刷新后填邮箱前")
    _type_email(page, email)


def submit_email_and_otp(page, email: str, mailbox_key: str, *,
                         fallback_url: str, signup: bool = True) -> None:
    """注册/登录共用的邮箱 + OTP 提交流（``flova_invite._submit_email_and_otp``
    直接复用本函数，两条 signup 路径同一套检测，不重复实现）。

    填邮箱 → 等 Turnstile token：复选框验证（Turnstile）未签发 token 时刷新页面
    重来，最多 3 次；滑动验证可见时只等用户滑过，绝不刷新。signup=False（登录）
    时刷新后重新打开的是登录面板，而不是 “Sign up for 300 credits”。
    """
    # 打开 Email 面板后拼图可能延迟弹出。
    settle_captcha(page, "填邮箱前")
    _type_email(page, email)

    # 等 Turnstile 签发 token；等待期间也可能弹滑动拼图。
    reloads = 0
    issued = False
    while not issued:
        # 复选框一出现就立刻刷新，不等完这个窗口；窗口只给“什么都没出现”兜底。
        window_end = time.time() + TURNSTILE_WAIT_SEC
        while True:
            slide = captcha_mask_visible(page)
            checkbox, has_token = turnstile_state(page)
            decision = turnstile_decision(
                checkbox=checkbox, token=has_token, slide=slide, reloads=reloads)
            if decision == "continue":
                issued = True
                break
            if decision == "fail":
                raise RuntimeError("Turnstile token not issued")
            if decision == "refresh":
                reloads += 1
                _reload_for_turnstile(page, email, fallback_url, reloads,
                                      signup=signup)
                break  # 重开一轮观察窗口
            # wait：滑块可见时优先等用户滑完；否则在窗口内每 0.3s 继续观察。
            if slide:
                settle_captcha(page, "等待校验时")
                window_end = time.time() + TURNSTILE_WAIT_SEC
                continue
            if time.time() >= window_end:
                raise RuntimeError("Turnstile token not issued")
            time.sleep(0.3)

    fi._click_text(page, "Continue with Email")
    settle_captcha(page, "提交邮箱后")

    otp_deadline = time.time() + 30.0
    on_otp = False
    while time.time() < otp_deadline:
        if captcha_mask_visible(page):
            settle_captcha(page, "提交邮箱后滑块")
            otp_deadline = time.time() + 30.0
        on_otp = bool(page.evaluate(
            "[...document.querySelectorAll('input')].some(e => e.type === 'text' && e.maxLength === 6)"
        ))
        if on_otp:
            break
        time.sleep(0.5)
    if not on_otp:
        diag = {}
        try:
            diag = page.evaluate("""() => ({
                text: (document.body.innerText || '').slice(0, 400),
                inputs: [...document.querySelectorAll('input')].map(i => ({name: i.name, type: i.type, max: i.maxLength, val: i.value})),
                alerts: [...document.querySelectorAll('[role=alert], .error, [class*="error"], [class*="alert"]')].map(e => (e.innerText || '').trim()).filter(Boolean)
            })""")
            print(f"  [DIAG] 未进入OTP页面，页面状态: {json.dumps(diag, ensure_ascii=False)}", flush=True)
            page.screenshot(path="tmp/otp_fail.png")
        except Exception as e:
            print(f"  [DIAG] dump failed: {e}", flush=True)
        raise RuntimeError(f"did not reach OTP page (page text: {repr(diag.get('text', '')[:100])})")

    code = fi._poll_otp(mailbox_key, time.time())
    n = page.evaluate(
        """() => {
          const els=[...document.querySelectorAll('input')]
            .filter(e=>e.type==='text'&&e.maxLength===6);
          if(!els.length) return 0;
          els[0].focus(); return els.length;
        }"""
    )
    if not n:
        raise RuntimeError("OTP input missing")
    page.keyboard.type(code, delay=140)
    time.sleep(6)
    settle_captcha(page, ("注册" if signup else "登录") + "收尾", settle_window=4)


def submit_email_and_otp_manual(page, email: str, mailbox_key: str,
                                invite_url: str) -> None:
    """人工辅助注册路径：signup=True 的共享 ``submit_email_and_otp``。

    每个环节都先观察/等待拼图；复选框未签发 token 时刷新，最多 3 次。
    """
    submit_email_and_otp(page, email, mailbox_key,
                         fallback_url=invite_url, signup=True)


def register_one(mother_profile: str, mailbox: dict, profile_name: str,
                 worker: fi.Worker, inviter_email: str) -> dict:
    worker_id = worker.id
    invite_url = ""
    child_token = None
    signup_err = None
    try:
        code = fi.invite_snapshot(mother_profile)["promotion_code"]
        if not code:
            return {"ok": False, "reason": "no_promotion_code",
                    "child_email": mailbox["address"]}
        invite_url = f"https://www.flova.ai/?refCode={code}"
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
            fi._begin_email_auth(page, signup=True)
            try:
                submit_email_and_otp_manual(page, mailbox["address"], mailbox["key"],
                                            invite_url)
            except Exception as e:
                signup_err = str(e)[:240]

            still_cta = page.evaluate("document.body.innerText.includes('Sign up for 300')")
            if signup_err or still_cta:
                browser.close()
                return {"ok": False, "reason": signup_err or "still_on_signup_cta",
                        "child_email": mailbox["address"]}

            fi.adopt_web_session(profile_name, ctx, expected_email=mailbox["address"],
                                 playwright=p)
            try:
                import repair_cli
                child_token = repair_cli._mint_token_in_page(
                    page, f"manual-{int(time.time())}")
            except Exception:
                child_token = None
            browser.close()
    finally:
        fi.stop_worker(worker_id)

    if not child_token and mailbox.get("address"):
        try:
            import repair_cli
            rep = repair_cli.repair(profile_name)
            if rep.get("ok"):
                return {"ok": True, "reason": "keyed",
                        "child_email": mailbox["address"],
                        "child_profile": profile_name}
        except Exception as exc:
            signup_err = str(exc)[:240]

    if not child_token:
        # 只要成功采纳了网页会话，也必须作为 web_session 记录入账
        if mailbox.get("address"):
            return {"ok": True, "reason": "web_session",
                    "child_email": mailbox["address"],
                    "child_profile": profile_name}
        return {"ok": False, "reason": "token_missing",
                "child_email": mailbox["address"]}
    fi._add_cli_profile(profile_name, child_token)
    return {"ok": True, "reason": "keyed", "child_email": mailbox["address"],
            "child_profile": profile_name}


def parse_args(argv: list[str] | None = None) -> tuple[int, str | None]:
    parser = argparse.ArgumentParser(description="Invite-register N children one at a time")
    parser.add_argument("n", nargs="?", type=int, default=4)
    parser.add_argument("--profile", default="")
    args = parser.parse_args(argv)
    if args.n < 1:
        parser.error("n must be >= 1")
    profile = args.profile.strip() or None
    if profile and not re.fullmatch(r"[A-Za-z0-9._-]+", profile):
        parser.error("invalid profile")
    return args.n, profile


def cli_invocation(argv: list[str] | None = None) -> dict:
    """解析命令行。不注册。省略 --profile 时 mother_profile 为 None，main 再取活跃母号。"""
    count, profile = parse_args(argv)
    if profile:
        return {"n": count, "mother_profile": profile}
    return {"n": count, "mother_profile": None}


def main(n: int, mother_profile: str | None = None) -> None:
    if mother_profile is None:
        mother_profile = fi.active_mother_profile()
        inviter_email = mother_email()
        print("active_mother_profile:", mother_profile)
    else:
        inviter_email = email_for_profile(mother_profile)
        print("mother_profile:", mother_profile)
    # prod 余额查询打桩（子号付款，不需要母号余额）。
    _orig_balance = fp.get_balance
    fp.get_balance = lambda p: 0.0 if str(p) == "prod" else _orig_balance(p)

    # 邀请码串行预热一次并缓存。
    snap0 = fi.invite_snapshot(mother_profile)
    print("promotion_code:", snap0["promotion_code"])
    fi.invite_snapshot = lambda *a, **k: dict(snap0)

    mailboxes = pick_fresh(n)
    profiles = fi.next_child_profiles(n)
    # 串行注册：按槽位轮转复用后端 worker 池；每个 register_one 结束都会
    # stop_worker，下一个才启动，因此同一个 VB worker id（同一 user-data-dir）不会被
    # 并发打开两次。VB 无 AdsPower 的池大小/每日限额，唯一约束是同 id 不并发。
    pool = fi.next_workers(n)
    if not pool:
        raise RuntimeError(f"no {fi.browser_backend()} worker available in pool")
    workers = [pool[i % len(pool)] for i in range(n)]

    results = []
    with fi._Lock(fi.LOCK_PATH):
        for mb, prof, wk in zip(mailboxes, profiles, workers):
            print(f"== 注册 {prof} | {mb['address']} | {fi.browser_backend()} {wk.id}",
                  flush=True)
            r = register_one(mother_profile, mb, prof, wk, inviter_email)
            print("   ->", "OK" if r.get("ok") else r.get("reason"), flush=True)
            results.append(r)
        fi._record_children(results, inviter_email)

    verified = []
    for r in results:
        if r.get("ok"):
            verified.append({"profile": r["child_profile"],
                             "balance": _orig_balance(r["child_profile"])})
    print("verified:", json.dumps(verified, ensure_ascii=False))


if __name__ == "__main__":
    main(**cli_invocation())
