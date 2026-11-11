# -*- coding: utf-8 -*-
"""号池面板动作的纯函数 / 源码契约测试。不联网、不开浏览器、不跑真实流程。

    python scripts/flova/test_pool_actions.py
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import pool_panel

HERE = Path(__file__).resolve().parent
LOGIN_WEB_SRC = (HERE / "login_web.py").read_text(encoding="utf-8")
INVITE_HAND_SRC = (HERE / "invite_hand.py").read_text(encoding="utf-8")
REPAIR_CLI_SRC = (HERE / "repair_cli.py").read_text(encoding="utf-8")
PANEL_SRC = (HERE / "pool_panel.py").read_text(encoding="utf-8")


class StartupContractTests(unittest.TestCase):
    def test_main_does_not_kick_off_a_probe(self):
        # 启动只装结构行并监听端口：main 源码里不得再出现 start_refresh，
        # 也不得留着启动探测线程。
        main_body = PANEL_SRC.split("def main(", 1)[1]
        main_body = main_body.split("if __name__", 1)[0]
        self.assertNotIn("start_refresh", main_body)
        self.assertNotIn("flova-pool-startup-probe", main_body)


class BuildJobTests(unittest.TestCase):
    def _assert_login_web_python(self, cmd):
        # 命令第二个元素是脚本，必须以 login_web.py 结尾。
        self.assertTrue(cmd[1].endswith("login_web.py"))
        joined = " ".join(cmd)
        self.assertIn("--profile", joined)
        self.assertNotIn("login-web.js", joined)
        self.assertNotIn(".flova-mcp", joined)

    def test_login_web_onboard_relink_use_python_vb_script(self):
        login = pool_panel.build_job("login_web", "kid9", 1)
        onboard = pool_panel.build_job("onboard", "kid9", 1)
        relink = pool_panel.build_job(
            "relink", "kid9", 1, expect_email="kid9@example.com")
        self._assert_login_web_python(login)
        self._assert_login_web_python(onboard)
        self._assert_login_web_python(relink)
        # relink 必须把账本邮箱传给脚本做一致性校验。
        self.assertIn("--expect-email", relink)
        self.assertEqual(
            relink[relink.index("--expect-email") + 1], "kid9@example.com")
        self.assertIn("kid9", relink)

    def test_relink_requires_expect_email(self):
        with self.assertRaises(ValueError):
            pool_panel.build_job("relink", "kid9", 1)

    def test_invite_hand_command(self):
        cmd = pool_panel.build_job("invite_hand", "kid9", 1)
        self.assertTrue(cmd[1].endswith("invite_hand.py"))
        self.assertEqual(cmd[-3:], ["--profile", "kid9", "1"])
        self.assertNotIn("refCode", " ".join(cmd))

    def test_repair_cli_command(self):
        cmd = pool_panel.build_job("repair_cli", "kid9", 1)
        self.assertTrue(cmd[1].endswith("repair_cli.py"))
        self.assertEqual(cmd[-2:], ["--profile", "kid9"])

    def test_unknown_and_bad_profile_rejected(self):
        with self.assertRaises(ValueError):
            pool_panel.build_job("nope", "kid9", 1)
        with self.assertRaises(ValueError):
            pool_panel.build_job("invite_hand", "bad name", 1)


class PageContractTests(unittest.TestCase):
    def test_page_has_new_actions(self):
        page = pool_panel.PAGE
        self.assertIn("刷新", page)
        self.assertIn("手动邀请", page)
        self.assertIn("补 CLI", page)
        # 单卡刷新按钮仍然存在。
        self.assertIn('data-act="probe_one"', page)

    def test_single_card_refresh_is_not_gated_by_probe_or_double_logout(self):
        page = pool_panel.PAGE
        # 旧条件：未检测或双端都掉线才给单卡检测按钮——必须消失。
        self.assertNotIn(
            "(!row.probed || (!row.web_logged_in && !row.cli_logged_in))", page)
        # 旧按钮文案「检测」不再作为 probe_one 的按钮出现。
        self.assertNotIn(">检测</button>", page)
        # 新的单卡刷新只看有没有 profile：取 probe_one 所在按钮那一小段，
        # 紧邻的守卫条件必须是无条件的 if (row.profile)。
        idx = page.index('data-act="probe_one"')
        window = page[max(0, idx - 260):idx]
        self.assertIn("if (row.profile) {", window)

    def test_invite_hand_and_repair_cli_buttons_post_jobs(self):
        page = pool_panel.PAGE
        self.assertIn('data-act="invite_hand"', page)
        self.assertIn('data-act="repair_cli"', page)
        # 手动邀请与手动注册共用通用 /api/jobs 投递路径（labels 里要有它）。
        self.assertIn("invite_hand: \"手动邀请\"", page)
        self.assertIn('action: action, profile: profile, n: count', page)
        # 补 CLI 有自己的确认分支。
        self.assertIn('action === "repair_cli"', page)
        # 刷新仍走 /api/pool/refresh 的单卡强制探测。
        self.assertIn('scope: "one", profile: profile, force: true', page)

    def test_onboard_button_does_not_prompt_for_profile_name(self):
        page = pool_panel.PAGE
        # 不再让用户手填 profile 名。
        self.assertNotIn("输入要录入的已有账号", page)
        # 直接 POST 空对象，名字由服务端分配。
        self.assertIn('post("/api/pool/onboard", {})', page)
        # 补登录关联 profile 的 prompt 保留（那是给已有账本行指定名字）。
        self.assertIn("补登录关联 profile", page)


class OnboardNamingContractTests(unittest.TestCase):
    def test_start_onboard_computes_profile_and_ignores_payload_name(self):
        src = PANEL_SRC
        body = src.split("def start_onboard(", 1)[1].split("def start_relink(", 1)[0]
        self.assertIn("next_onboard_profile", body)
        self.assertIn("collect_onboard_taken", body)
        # 请求体里即使带了 profile 名也不能当作新号名字：不允许读取
        # payload["profile"] / payload.get("profile") 后再用于 build_job。
        self.assertNotIn('payload.get("profile")', body)
        self.assertNotIn("payload[\"profile\"]", body)
        # intro 必须告诉用户本次自动分配的 profile 名。
        self.assertIn("本次 profile 是", body)

    def test_next_onboard_profile_contract(self):
        import pool_status as ps
        self.assertEqual(ps.next_onboard_profile(set()), "kid1")
        self.assertEqual(ps.next_onboard_profile({"kid1", "kid2", "kid4"}), "kid3")


class LoginWebSourceTests(unittest.TestCase):
    def test_uses_vb_worker_with_rotated_fingerprint(self):
        # 必须经 launch_worker 启动，且显式 rotate=True（每次随机指纹）。
        self.assertIn("launch_worker", LOGIN_WEB_SRC)
        self.assertIn("rotate=True", LOGIN_WEB_SRC)
        self.assertIn("incognito=True", LOGIN_WEB_SRC)
        # 网页登录固定 Virtual Browser，不允许退回 AdsPower：代码里不得读取
        # FLOVA_BROWSER_BACKEND（docstring 里说明“不受其影响”不算）。
        self.assertIn("vb_backend", LOGIN_WEB_SRC)
        self.assertNotIn('os.environ.get("FLOVA_BROWSER_BACKEND"', LOGIN_WEB_SRC)
        self.assertNotIn("adspower", LOGIN_WEB_SRC.lower())

    def test_polls_user_info_and_adopts_session(self):
        self.assertIn("_web_get_user_info", LOGIN_WEB_SRC)
        self.assertIn("adopt_web_session", LOGIN_WEB_SRC)
        self.assertIn("--expect-email", LOGIN_WEB_SRC)
        self.assertIn("stop_worker", LOGIN_WEB_SRC)

    def test_wait_reads_browser_cookies_into_independent_request_context(self):
        # 等待逻辑必须读浏览器自己的 cookie 罐，并塞进独立的纯 HTTP 请求上下文，
        # 不能再只靠 context.request（CDP 下与页面登录态不是同一份 cookie）。
        # cookies/storage_state 在等待轮询调用的 _probe_context helper 里。
        self.assertIn("cookies()", LOGIN_WEB_SRC)
        self.assertIn("storage_state", LOGIN_WEB_SRC)
        self.assertIn("new_context", LOGIN_WEB_SRC)
        self.assertIn("dispose()", LOGIN_WEB_SRC)
        # wait_logged_in 必须扫所有 context（含后来弹出的页面），
        # 登录成功的那个才传给采纳。
        wait_body = LOGIN_WEB_SRC.split("def wait_logged_in(", 1)[1]
        wait_body = wait_body.split("def login(", 1)[0]
        self.assertIn("browser.contexts", wait_body)
        self.assertIn("_probe_context", wait_body)
        self.assertIn("context_flova_cookies", LOGIN_WEB_SRC)
        # 旧的唯一判定路径 _web_get_user_info(context) 必须消失。
        self.assertNotIn("_web_get_user_info(context)", LOGIN_WEB_SRC)
        self.assertNotIn("_web_get_user_info(ctx)", LOGIN_WEB_SRC)

    def test_session_ready_requires_code_zero_and_email(self):
        import login_web
        self.assertTrue(
            login_web.session_ready({"code": 0, "email": "a@example.com"}))
        for bad in (
            {},
            {"code": 0},
            {"email": "a@example.com"},
            {"code": 401, "email": "a@example.com"},
            {"code": None, "email": "a@example.com"},
            {"code": 0, "email": ""},
            {"code": 0, "email": None},
            None,
        ):
            self.assertFalse(login_web.session_ready(bad), bad)

    def test_closed_browser_fails_fast_without_waiting_out_deadline(self):
        # 浏览器被关掉要立刻失败并打指定 stderr，不干等满 5 分钟。
        self.assertIn("BrowserClosedError", LOGIN_WEB_SRC)
        self.assertIn("浏览器已关闭，未检测到登录会话", LOGIN_WEB_SRC)
        self.assertIn("已检测到登录，正在保存会话", LOGIN_WEB_SRC)

    def test_stdout_fields_are_whitelisted(self):
        # 正常 stdout 是一行 JSON，结果 dict 只允许四个白名单键。
        flat = re.sub(r"\s+", " ", LOGIN_WEB_SRC)
        self.assertRegex(flat, r'"profile"[^}]*"ok"[^}]*"backend"[^}]*"fingerprint_rotated"')
        for forbidden in ("token", "cookie", "invite", "promotion"):
            self.assertNotIn(f'"{forbidden}"', LOGIN_WEB_SRC)


class InviteHandSourceTests(unittest.TestCase):
    def test_records_children_and_never_prints_code(self):
        src = (HERE / "invite_hand.py").read_text(encoding="utf-8")
        self.assertIn("_record_children", src)
        self.assertIn("_add_cli_profile", src)
        self.assertIn("adopt_web_session", src)
        self.assertIn("next_child_profiles", src)
        self.assertIn("page_logged_in", src)
        self.assertIn("repair_cli", src)
        # 邀请码只能取来拼链接，任何 print 都不许带出 promotion_code。
        self.assertIsNone(
            re.search(r"print\s*\([^)]*promotion_code", src, re.S))
        self.assertNotIn('print("promotion_code', src)
        # 不自动填邮箱、不领邮箱池、不点 Continue。
        self.assertNotIn("pick_fresh", src)
        self.assertNotIn("pick_mailboxes", src)
        self.assertNotIn("_begin_email_auth", src)

    def test_cli_invocation_shape_matches_manual(self):
        import invite_hand
        self.assertEqual(invite_hand.cli_invocation(["2"]),
                         {"n": 2, "mother_profile": None})
        self.assertEqual(invite_hand.cli_invocation(["--profile", "kid3", "1"]),
                         {"n": 1, "mother_profile": "kid3"})


class RepairCliSourceTests(unittest.TestCase):
    def test_login_plan_for_existing_and_missing_profile(self):
        import repair_cli
        self.assertEqual(repair_cli.cli_login_plan(True), "login_only")
        self.assertEqual(repair_cli.cli_login_plan(False), "add_and_login")

    def test_existing_profile_skips_add_and_still_logs_in(self):
        # repair() 的 login_only 分支不得调 _add_cli_profile（它会先 profile add，
        # 名字已存在时直接失败）。
        repair_body = REPAIR_CLI_SRC.split("def repair(", 1)[1]
        branch = repair_body.split('if plan == "login_only":', 1)[1].split("else:", 1)[0]
        self.assertNotIn("_add_cli_profile", branch)
        # login_only 走专门的只登录 helper，缺名字的路径仍走 _add_cli_profile。
        self.assertIn("_login_token_only(profile, token)", branch)
        self.assertIn("fi._add_cli_profile(profile, token)", REPAIR_CLI_SRC)
        # helper 内部就是 _add_cli_profile 后半的两步：auth login --token，
        # 然后 profile use prod；没有 profile add。
        helper = REPAIR_CLI_SRC.split("def _login_token_only(", 1)[1]
        helper = helper.split("def ", 1)[0]
        self.assertIn('"auth", "login", "--token"', helper)
        self.assertIn('"profile", "use", "prod"', helper)
        self.assertNotIn('"profile", "add"', helper)
        # 用 known_profiles() 判定，且不打印 profile list 原文。
        self.assertIn("known_profiles()", REPAIR_CLI_SRC)

    def test_uses_saved_session_and_updates_only_registry_row(self):
        self.assertIn("WEB_PROFILES_DIR", REPAIR_CLI_SRC)
        self.assertIn("headless=True", REPAIR_CLI_SRC)
        self.assertIn("_add_cli_profile", REPAIR_CLI_SRC)
        self.assertIn("load_registry", REPAIR_CLI_SRC)
        self.assertIn("save_registry", REPAIR_CLI_SRC)
        self.assertIn('"state"] = "keyed"', REPAIR_CLI_SRC)
        # 不新登录、不开可见浏览器、不调 auth login 的浏览器模式。
        self.assertNotIn("launch_worker", REPAIR_CLI_SRC)
        self.assertNotIn("headless=False", REPAIR_CLI_SRC)
        # token 不允许出现在任何 print 里。
        self.assertIsNone(
            re.search(r"print\s*\([^)]*token", REPAIR_CLI_SRC, re.S))


class OpenBrowserTests(unittest.TestCase):
    def test_frontend_has_button_and_action(self):
        panel_src = (HERE / "pool_panel.py").read_text(encoding="utf-8")
        self.assertIn('data-act="open_browser"', panel_src)
        self.assertIn("进入后台", panel_src)
        self.assertIn('post("/api/pool/open_browser"', panel_src)
        self.assertIn('path == "/api/pool/open_browser"', panel_src)

    def test_open_browser_rejects_bad_profile(self):
        code, resp = pool_panel.open_browser({"profile": "../bad"})
        self.assertEqual(code, 400)
        self.assertFalse(resp["ok"])

    def test_open_browser_rejects_nonexistent_profile_dir(self):
        code, resp = pool_panel.open_browser({"profile": "nonexistent_profile_999"})
        self.assertEqual(code, 404)
        self.assertFalse(resp["ok"])
        self.assertIn("未找到", resp["message"])

    def test_open_browser_launches_vb_with_user_data_dir(self):
        from unittest.mock import patch
        with patch("subprocess.Popen") as mock_popen, \
             patch("vb_backend.ensure_proxy", return_value={"proxy": "http://127.0.0.1:7897"}), \
             patch("vb_backend.running_worker", return_value=False):
            resp = pool_panel.open_browser({"profile": "kid3"})
            self.assertTrue(resp.get("ok"))
            self.assertIn("已打开", resp.get("message", ""))
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            # 必须使用 VirtualBrowser 内核
            self.assertTrue(any("VirtualBrowser.exe" in arg for arg in cmd))
            # 必须带对应目录和 worker-id
            self.assertTrue(any("--user-data-dir=" in arg and "kid3" in arg for arg in cmd))
            self.assertTrue(any("--worker-id=203" == arg for arg in cmd))
            # 必须带代理、语言与本地 CDP 端口（用于自动导航页面）
            self.assertTrue(any("--proxy-server=" in arg for arg in cmd))
            self.assertTrue(any("--lang=" in arg for arg in cmd))
            self.assertTrue(any("--remote-debugging-port=" in arg for arg in cmd))
            # 不能无痕，不能后台最小化
            self.assertNotIn("--incognito", cmd)
            self.assertNotIn("--disable-backgrounding-occluded-windows", cmd)

    def test_open_browser_rejects_already_running_worker(self):
        from unittest.mock import patch
        with patch("vb_backend.running_worker", return_value=True):
            code, resp = pool_panel.open_browser({"profile": "kid3"})
            self.assertEqual(code, 409)
            self.assertFalse(resp["ok"])
            self.assertIn("已在运行中", resp["message"])


class AutoRepairCliTests(unittest.TestCase):
    def test_login_web_calls_repair_cli_after_adoption(self):
        src = (HERE / "login_web.py").read_text(encoding="utf-8")
        self.assertIn("repair_cli.repair(profile)", src)

    def test_pool_panel_auto_repairs_when_web_logged_in_and_cli_missing(self):
        src = (HERE / "pool_panel.py").read_text(encoding="utf-8")
        self.assertIn('row.get("web_logged_in") and not row.get("cli_logged_in")', src)
        self.assertIn('repair_cli.repair(str(row["profile"]))', src)


if __name__ == "__main__":
    unittest.main()
