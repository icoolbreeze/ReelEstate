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
    python invite_manual.py 4
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import flova_invite as fi
import flova_pricing as fp
from invite_batch import pick_fresh

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


def settle_captcha(page, label: str = "", *, settle_window: float = 10.0,
                   human_timeout: float = float(HUMAN_WAIT_SEC)) -> None:
    """轮询等待拼图弹窗（含延迟弹出）；一旦出现就等人工滑过。

    弹窗未出现时持续观察 settle_window 秒；滑过后重新开窗，防止连弹。
    """
    announced = False
    quiet_until = time.time() + settle_window
    while True:
        if captcha_mask_visible(page):
            if not announced:
                print(f"  ⏳ 请在弹出的浏览器窗口人工滑动拼图验证码{('（' + label + '）') if label else ''}，"
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

    on_otp = page.evaluate(
        "[...document.querySelectorAll('input')].some(e => e.type === 'text' && e.maxLength === 6)"
    )
    if not on_otp:
        raise RuntimeError("did not reach OTP page")

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
                 worker: tuple, inviter_email: str) -> dict:
    worker_id, port, worker_dir = worker
    code = fi.invite_snapshot(mother_profile)["promotion_code"]
    if not code:
        return {"ok": False, "reason": "no_promotion_code",
                "child_email": mailbox["address"]}

    kernel = fi.find_vb_kernel()
    worker_dir.mkdir(parents=True, exist_ok=True)
    invite_url = f"https://www.flova.ai/?refCode={code}"
    proc = fi.subprocess.Popen(
        [str(kernel), f"--user-data-dir={worker_dir}", f"--worker-id={worker_id}",
         "--no-first-run", "--no-default-browser-check",
         f"--remote-debugging-port={port}"],
        stdout=fi.subprocess.DEVNULL, stderr=fi.subprocess.DEVNULL,
    )
    child_token = None
    signup_err = None
    try:
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
            tok = ctx.request.post(
                "https://service.flova.ai/api/agent/v2/token",
                headers={"content-type": "application/json"},
                data=json.dumps({"name": f"manual-{int(time.time())}"}),
            )
            child_token = (tok.json().get("data") or {}).get("token")
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()

    if not child_token:
        return {"ok": False, "reason": "token_missing",
                "child_email": mailbox["address"]}
    fi._add_cli_profile(profile_name, child_token)
    return {"ok": True, "reason": "keyed", "child_email": mailbox["address"],
            "child_profile": profile_name}


def main(n: int) -> None:
    inviter_email = mother_email()
    # prod 余额查询打桩（子号付款，不需要母号余额）。
    _orig_balance = fp.get_balance
    fp.get_balance = lambda p: 0.0 if str(p) == "prod" else _orig_balance(p)

    # 快照和注册都走账本里的活跃母号（不写死 prod）。
    mother_profile = fi.active_mother_profile()
    print("active_mother_profile:", mother_profile)

    # 邀请码串行预热一次并缓存。
    snap0 = fi.invite_snapshot(mother_profile)
    print("promotion_code:", snap0["promotion_code"])
    fi.invite_snapshot = lambda *a, **k: dict(snap0)

    mailboxes = pick_fresh(n)
    profiles = fi.next_child_profiles(n)
    workers = fi.next_workers(n)

    results = []
    with fi._Lock(fi.LOCK_PATH):
        for mb, prof, wk in zip(mailboxes, profiles, workers):
            print(f"== 注册 {prof} | {mb['address']} | worker {wk[0]}", flush=True)
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
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
