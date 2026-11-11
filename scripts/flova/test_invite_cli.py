# -*- coding: utf-8 -*-
"""邀请脚本的命令行解析，以及面板拼出的启动命令。不跑注册。

    python scripts/flova/test_invite_cli.py
"""
from __future__ import annotations

import unittest

import invite_batch
import invite_hand
import invite_manual
import pool_panel


class InviteCliTests(unittest.TestCase):
    def test_batch_omitted_profile_stays_prod(self):
        spec = invite_batch.cli_invocation(["4"])
        self.assertEqual(spec["n"], 4)
        self.assertEqual(spec["mother_profile"], "prod")
        self.assertTrue(spec["resolve_inviter_email"])
        self.assertNotIn("inviter_email", spec)

    def test_batch_profile_is_the_clicked_account(self):
        original = invite_batch.email_for_profile
        invite_batch.email_for_profile = lambda profile: "kid9@example.com"
        try:
            spec = invite_batch.cli_invocation(["--profile", "kid9", "1"])
        finally:
            invite_batch.email_for_profile = original
        self.assertEqual(spec["mother_profile"], "kid9")
        self.assertEqual(spec["n"], 1)
        self.assertFalse(spec["resolve_inviter_email"])
        self.assertEqual(spec["inviter_email"], "kid9@example.com")

    def test_manual_omitted_profile_defers_to_active_mother(self):
        spec = invite_manual.cli_invocation(["1"])
        self.assertEqual(spec, {"n": 1, "mother_profile": None})

    def test_manual_profile_is_passed_through(self):
        spec = invite_manual.cli_invocation(["--profile", "kid2", "2"])
        self.assertEqual(spec, {"n": 2, "mother_profile": "kid2"})

    def test_hand_omitted_profile_defers_to_active_mother(self):
        spec = invite_hand.cli_invocation(["1"])
        self.assertEqual(spec, {"n": 1, "mother_profile": None})

    def test_hand_profile_is_passed_through(self):
        spec = invite_hand.cli_invocation(["--profile", "kid2", "2"])
        self.assertEqual(spec, {"n": 2, "mother_profile": "kid2"})


class JobCommandTests(unittest.TestCase):
    def test_commands_name_the_profile_and_direct_signup_has_no_ref(self):
        batch = pool_panel.build_job("invite_batch", "kid9", 2)
        manual = pool_panel.build_job("invite_manual", "kid9", 1)
        hand = pool_panel.build_job("invite_hand", "kid9", 1)
        repair = pool_panel.build_job("repair_cli", "kid9", 1)
        direct = pool_panel.build_job("register_direct", None, 1)
        login = pool_panel.build_job("login_web", "kid9", 1)
        self.assertEqual(batch[-3:], ["--profile", "kid9", "2"])
        self.assertTrue(batch[-4].endswith("invite_batch.py"))
        self.assertEqual(manual[-3:], ["--profile", "kid9", "1"])
        self.assertTrue(manual[-4].endswith("invite_manual.py"))
        self.assertEqual(hand[-3:], ["--profile", "kid9", "1"])
        self.assertTrue(hand[-4].endswith("invite_hand.py"))
        self.assertTrue(repair[1].endswith("repair_cli.py"))
        self.assertEqual(repair[-2:], ["--profile", "kid9"])
        self.assertTrue(direct[-1].endswith("register_direct.py"))
        self.assertNotIn("--profile", direct)
        self.assertNotIn("refCode", " ".join(direct))
        # 网页登录统一走仓库内 Python（随机指纹 VB），不再调 login-web.js。
        self.assertEqual(login[-2:], ["--profile", "kid9"])
        self.assertTrue(login[1].endswith("login_web.py"))
        self.assertNotIn("login-web.js", " ".join(login))

    def test_relink_command_carries_expect_email(self):
        relink = pool_panel.build_job(
            "relink", "kid9", 1, expect_email="old@example.com")
        self.assertTrue(relink[1].endswith("login_web.py"))
        self.assertIn("--profile", relink)
        self.assertIn("--expect-email", relink)
        self.assertEqual(relink[relink.index("--expect-email") + 1],
                         "old@example.com")
        self.assertNotIn("login-web.js", " ".join(relink))

    def test_relink_without_expect_email_is_rejected(self):
        with self.assertRaises(ValueError):
            pool_panel.build_job("relink", "kid9", 1)

    def test_invite_without_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            pool_panel.build_job("invite_batch", "", 1)

    def test_panel_can_rebind_after_the_window_closes(self):
        self.assertTrue(pool_panel.PanelServer.allow_reuse_address)


if __name__ == "__main__":
    unittest.main()
