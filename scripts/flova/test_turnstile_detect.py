# -*- coding: utf-8 -*-
"""invite_manual 的 Turnstile 检测测试：纯决策逻辑 + 本地页面（无网络）。

从仓库根目录运行：
    python -c "import sys; sys.path.insert(0, 'scripts/flova'); \
import test_turnstile_detect; test_turnstile_detect.main()"
"""
from __future__ import annotations

import os
import time

import invite_manual as im

MAX = im.TURNSTILE_MAX_RELOADS

# Turnstile iframe 只放在 open shadow root 里。src 用 data URL 且串内含
# "turnstile"：检测只看属性，不产生任何网络请求。
SHADOW_IFRAME_PAGE = """
<!doctype html><html><body>
<div id="host"></div>
<script>
(() => {
  const root = document.getElementById('host').attachShadow({mode: 'open'});
  const f = document.createElement('iframe');
  f.src = 'data:text/html;charset=utf-8,<body>turnstile</body>';
  f.title = 'Widget containing a Cloudflare security challenge';
  root.appendChild(f);
})();
</script>
</body></html>
"""

# 轻 DOM 里只有 .cf-turnstile，没有任何 iframe。
LIGHT_WIDGET_PAGE = """
<!doctype html><html><body>
<div class="cf-turnstile" data-sitekey="dummy-sitekey"></div>
</body></html>
"""

# Turnstile iframe 只放在 **closed** shadow root 里：querySelector 和 open-shadow
# walk 都看不到 iframe 元素，只能靠 Playwright frame.url 判定。data URL 的编码
# 内容里带 turnstile / challenges.cloudflare.com，frame.url 因此含这些串；
# data URL 不产生任何网络请求。
CLOSED_SHADOW_IFRAME_PAGE = """
<!doctype html><html><body>
<div id="host"></div>
<script>
(() => {
  const root = document.getElementById('host').attachShadow({mode: 'closed'});
  const f = document.createElement('iframe');
  f.src = 'data:text/html;charset=utf-8,<body>turnstile challenges.cloudflare.com</body>';
  root.appendChild(f);
})();
</script>
</body></html>
"""

ADD_SHADOW_TOKEN_JS = """
() => {
  const root = document.getElementById('host').shadowRoot;
  const i = document.createElement('input');
  i.name = 'cf-turnstile-response';
  i.value = 'dummy-token';
  root.appendChild(i);
  return true;
}
"""

ADD_LIGHT_TOKEN_JS = """
() => {
  const i = document.createElement('input');
  i.name = 'cf-turnstile-response';
  i.value = 'dummy-token';
  document.body.appendChild(i);
  return true;
}
"""


def test_decision() -> None:
    """无浏览器：turnstile_decision 在各种状态组合下的决定。"""
    d = im.turnstile_decision
    # 复选框已出现、没 token、没滑块、还没刷新过 → 立刻刷新。
    assert d(checkbox=True, token=False, slide=False, reloads=0) == "refresh"
    # 滑块可见 → 等用户，不刷新（滑块优先，即使刷新次数已用完）。
    assert d(checkbox=True, token=False, slide=True, reloads=0) == "wait"
    assert d(checkbox=True, token=False, slide=True, reloads=MAX) == "wait"
    # token 已签发 → 继续，不刷新。
    assert d(checkbox=True, token=True, slide=False, reloads=0) == "continue"
    assert d(checkbox=True, token=True, slide=True, reloads=MAX) == "continue"
    # 什么都还没出现 → 窗口内继续观察，不按计时器刷新。
    assert d(checkbox=False, token=False, slide=False, reloads=0) == "wait"
    # 复选框仍在但刷新次数已达上限 → 失败。
    assert d(checkbox=True, token=False, slide=False, reloads=MAX) == "fail"


def test_url_text_helper() -> None:
    """无浏览器：纯 URL / 文本 helper（frame.url 与 frame 文档文本判定）。"""
    u = im.turnstile_url_match
    # Cloudflare Turnstile frame URL → 复选框（大小写不敏感）。
    assert u("https://challenges.cloudflare.com/turnstile/v0/siteverify") is True
    assert u("HTTPS://Challenges.Cloudflare.COM/Turnstile/X") is True
    # 普通 flova 页面 / 空值 → 不是复选框。
    assert u("https://www.flova.ai/") is False
    assert u("https://www.flova.ai/?refCode=abc") is False
    assert u("") is False
    assert u(None) is False

    t = im.turnstile_text_match
    # frame 文档文本含 “Verify you are human” → 复选框（大小写不敏感）。
    assert t("Verify you are human") is True
    assert t("widget: verify you are human to continue") is True
    assert t("VERIFY YOU ARE HUMAN") is True
    # 无关文本 / 空值 → 不是复选框。
    assert t("Sign in with Email") is False
    assert t("") is False
    assert t(None) is False


def _launch_browser(p):
    """优先用 Playwright 自带 Chromium；缺失时退到本机 chrome / msedge。

    不触发浏览器下载。
    """
    exe = p.chromium.executable_path
    if exe and os.path.exists(exe):
        try:
            return p.chromium.launch()
        except Exception:
            pass
    last_error: Exception | None = None
    for channel in ("chrome", "msedge"):
        try:
            return p.chromium.launch(channel=channel)
        except Exception as e:  # 该 channel 不存在，试下一个
            last_error = e
    raise RuntimeError(
        f"no usable local browser (tried bundled chromium, chrome, msedge): {last_error}")


def test_browser() -> None:
    """本地 set_content 页面（无网络）：shadow iframe / 轻 DOM 部件 / token。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = _launch_browser(p)
        try:
            page = browser.new_page()

            # 1) iframe 只存在于 open shadow root 内。
            page.set_content(SHADOW_IFRAME_PAGE, wait_until="load")
            # 普通 document.querySelector 看不到 shadow root 里的 iframe。
            assert page.evaluate("document.querySelector('iframe')") is None
            checkbox, token = im.turnstile_state(page)
            assert checkbox is True and token is False
            assert im.turnstile_pending(page) is True

            # token 也放进同一个 shadow root：穿透检测到后不再 pending。
            page.evaluate(ADD_SHADOW_TOKEN_JS)
            checkbox, token = im.turnstile_state(page)
            assert token is True and checkbox is True
            assert im.turnstile_pending(page) is False

            # 2) 轻 DOM 的 .cf-turnstile（没有 iframe）。
            page.set_content(LIGHT_WIDGET_PAGE, wait_until="load")
            checkbox, token = im.turnstile_state(page)
            assert checkbox is True and token is False
            assert im.turnstile_pending(page) is True

            page.evaluate(ADD_LIGHT_TOKEN_JS)
            checkbox, token = im.turnstile_state(page)
            assert token is True
            assert im.turnstile_pending(page) is False

            # 3) iframe 只存在于 closed shadow root：querySelector 和 open-shadow
            #    walk 都够不到元素，只能靠 Playwright frame.url 判定。
            page.set_content(CLOSED_SHADOW_IFRAME_PAGE, wait_until="load")
            deadline = time.time() + 5
            while len(page.frames) < 2 and time.time() < deadline:
                page.wait_for_timeout(100)
            assert len(page.frames) >= 2, "closed-shadow iframe frame missing"
            assert page.evaluate("document.querySelector('iframe')") is None
            checkbox, token = im.turnstile_state(page)
            assert checkbox is True and token is False
            assert im.turnstile_pending(page) is True
        finally:
            browser.close()


def main() -> int:
    test_decision()
    test_url_text_helper()
    test_browser()
    print("all turnstile detection tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
