# -*- coding: utf-8 -*-
"""号池探测与入账的纯测试。不访问网络，不启动浏览器。

    python scripts/flova/test_pool_status.py
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import flova_invite as fi
import flova_pricing as fp
import pool_status as ps


def _bundle(*, code="SECRETCODE", remaining_fields=None, age=True, exported=True,
            disabled=False, reward=180, max_invitees=20, rewarded=1,
            user_code=0, email="kid@example.com"):
    reward_body = {"rewarded_count": rewarded}
    if max_invitees is not None:
        reward_body["max_invitees"] = max_invitees
    if reward is not None:
        reward_body["credit_reward_num"] = reward
    return {
        "credits": {"code": 0, "data": {"buckets": []}},
        "exploration": {"code": 0, "data": {"rewards": [
            {"source": "first_image", "status": 0, "credit_num": 30},
        ]}},
        "invite": {"data": {
            "promotion_code": code,
            "registration_reward": reward_body,
            "eligibility": {
                "account_age_7d": age,
                "has_export": exported,
                "invite_reward_disabled": disabled,
            },
            "invite_reward_disabled": disabled,
        }},
        "user": {"code": user_code, "data": {"email": email, "user_id": "u-1"}},
        **(remaining_fields or {}),
    }


class RedactTests(unittest.TestCase):
    def test_redact_secrets(self):
        text = redact_sample = (
            'promotion_code: SECRETCODE token=abc cookie: xyz '
            'authorization: Bearer abc.def "promotion_code": "SECRETCODE"'
        )
        cleaned = ps.redact(text)
        self.assertNotIn("SECRETCODE", cleaned)
        self.assertNotIn("abc.def", cleaned)
        self.assertIn("[redacted]", cleaned)
        self.assertNotIn("SECRETCODE", json.dumps(ps.scrub_obj({
            "promotion_code": "SECRETCODE",
            "email": "a@b.com",
            "nested": {"token": "ttt"},
        })))


class InviteViewTests(unittest.TestCase):
    def test_matches_snapshot_fields_and_drops_code(self):
        raw = _bundle()["invite"]
        original_stats = fp.get_invite_stats_web
        original_balance = fp.get_balance
        fp.get_invite_stats_web = lambda profile="prod": raw
        fp.get_balance = lambda profile: 12
        try:
            snap = fi.invite_snapshot("kid1")
        finally:
            fp.get_invite_stats_web = original_stats
            fp.get_balance = original_balance
        view = ps.invite_view(raw)
        self.assertNotIn("promotion_code", view)
        self.assertEqual(view["rewarded_count"], snap["rewarded_count"])
        self.assertEqual(view["max_invitees"], snap["max_invitees"])
        self.assertEqual(view["credit_reward_num"], snap["credit_reward_num"])
        self.assertEqual(view["invite_reward_disabled"], snap["invite_reward_disabled"])
        self.assertNotIn("SECRETCODE", json.dumps(view))

    def test_missing_reward_is_unknown(self):
        view = ps.invite_view(_bundle(reward=None, max_invitees=None)["invite"])
        self.assertIsNone(view["credit_reward_num"])
        self.assertIsNone(view["max_invitees"])
        self.assertIsNone(view["remaining_invitees"])


class AssembleTests(unittest.TestCase):
    def test_invite_ready_and_successor(self):
        base = {
            "profile": "kid9",
            "email": None,
            "user_id": None,
            "role": "child",
            "state": "keyed",
            "in_pool": True,
            "active_mother": False,
            "sources": ["registry", "cli"],
        }
        row = ps.assemble_row(base, cli_data={"email": "kid@example.com", "credits_balance": 40},
                              web_bundle=_bundle())
        self.assertTrue(row["cli_logged_in"])
        self.assertEqual(row["credits"], 40)
        self.assertTrue(row["web_logged_in"])
        self.assertTrue(row["invite_ready"])
        self.assertEqual(row["remaining_invitees"], 19)
        self.assertTrue(row["successor_eligible"])
        self.assertNotIn("SECRETCODE", json.dumps(row))
        self.assertNotIn("promotion_code", json.dumps(row))

    def test_not_ready_when_logged_out_disabled_or_empty(self):
        base = {
            "profile": "kid9", "email": "kid@example.com", "role": "child",
            "state": "keyed", "in_pool": True, "active_mother": False, "sources": ["cli"],
        }
        logged_out = ps.assemble_row(base, web_error="no session")
        self.assertFalse(logged_out["web_logged_in"])
        self.assertFalse(logged_out["invite_ready"])
        self.assertIn("no_web_session", logged_out["successor_blockers"])

        disabled = ps.assemble_row(
            base,
            cli_data={"credits_balance": 1, "email": "kid@example.com"},
            web_bundle=_bundle(disabled=True),
        )
        self.assertFalse(disabled["invite_ready"])
        self.assertFalse(disabled["successor_eligible"])

        empty = ps.assemble_row(
            base,
            cli_data={"credits_balance": 1, "email": "kid@example.com"},
            web_bundle=_bundle(rewarded=20, max_invitees=20),
        )
        self.assertEqual(empty["remaining_invitees"], 0)
        self.assertFalse(empty["invite_ready"])
        self.assertIn("no_invite_slots", empty["successor_blockers"])

    def test_mother_is_not_a_successor(self):
        base = {
            "profile": "prod", "email": "mom@example.com", "role": "mother",
            "state": "keyed", "in_pool": True, "active_mother": True, "sources": ["registry"],
        }
        row = ps.assemble_row(
            base,
            cli_data={"credits_balance": 10, "email": "mom@example.com"},
            web_bundle=_bundle(email="mom@example.com"),
        )
        self.assertTrue(row["invite_ready"])
        self.assertFalse(row["successor_eligible"])
        self.assertFalse(row["addable"])

    def test_unpooled_without_email_cannot_be_added(self):
        base = {
            "profile": "kid3", "email": None, "role": None, "state": None,
            "in_pool": False, "active_mother": False, "sources": ["cli"],
        }
        row = ps.assemble_row(base, cli_error="flova CLI failed")
        self.assertFalse(row["in_pool"])
        self.assertFalse(row["addable"])
        self.assertEqual(row["add_block_reason"], "读不到邮箱")


class AddTests(unittest.TestCase):
    def test_add_cli_profile_omits_balance_and_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            result = ps.add_to_pool(
                "kid3",
                registry_path=path,
                email="Kid3@example.com",
                user_id="u-3",
                cli_logged_in=True,
                cli_exists=True,
                web_dir_exists=True,
                default_mother="prod",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["action"], "added")
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["accounts"]), 1)
            account = saved["accounts"][0]
            self.assertEqual(account["api_key_ref"], "flova-profile:kid3")
            self.assertEqual(account["web_profile_ref"], "~/.flova-mcp/browser-profiles/kid3")
            self.assertEqual(account["role"], "child")
            self.assertEqual(account["state"], "keyed")
            self.assertEqual(account["notes"], "added from pool panel")
            self.assertNotIn("invited_by", account)
            self.assertNotIn("balance_total", account)
            self.assertNotIn("promotion_code", account)
            self.assertNotIn("balance_total", path.read_text(encoding="utf-8"))
            again = ps.add_to_pool(
                "kid3",
                registry_path=path,
                email="kid3@example.com",
                cli_logged_in=True,
                cli_exists=True,
                web_dir_exists=True,
                default_mother="prod",
            )
            self.assertEqual(again["action"], "already")
            self.assertEqual(len(json.loads(path.read_text(encoding="utf-8"))["accounts"]), 1)

    def test_reject_when_email_points_at_another_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text(json.dumps({
                "version": "3",
                "accounts": [{
                    "email": "same@example.com",
                    "role": "child",
                    "state": "keyed",
                    "api_key_ref": "flova-profile:kid1",
                }],
            }), encoding="utf-8")
            result = ps.add_to_pool(
                "kid2",
                registry_path=path,
                email="same@example.com",
                cli_logged_in=True,
                cli_exists=True,
                web_dir_exists=False,
                default_mother="prod",
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason"], "profile_conflict")
            self.assertEqual(result["existing_profile"], "kid1")
            self.assertIn("kid2", result["message"])

    def test_reject_without_email(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            result = ps.add_to_pool(
                "kid4",
                registry_path=path,
                email=None,
                cli_exists=True,
                web_dir_exists=False,
                default_mother="prod",
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason"], "no_email")
            self.assertFalse(path.exists())

    def test_patch_missing_ref_does_not_add_a_second_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text(json.dumps({
                "version": "3",
                "accounts": [{
                    "email": "solo@example.com",
                    "role": "child",
                    "state": "web_session",
                }],
            }), encoding="utf-8")
            result = ps.add_to_pool(
                "kid8",
                registry_path=path,
                email="solo@example.com",
                cli_logged_in=True,
                cli_exists=True,
                web_dir_exists=True,
                default_mother="prod",
            )
            self.assertEqual(result["action"], "patched")
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["accounts"]), 1)
            self.assertEqual(saved["accounts"][0]["api_key_ref"], "flova-profile:kid8")
            self.assertNotIn("balance_total", saved["accounts"][0])

    def test_first_active_mother_profile_becomes_mother(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text(json.dumps({
                "version": "3",
                "active_mother_profile": "prod",
                "accounts": [],
            }), encoding="utf-8")
            result = ps.add_to_pool(
                "prod",
                registry_path=path,
                email="mom@example.com",
                cli_logged_in=True,
                cli_exists=True,
                web_dir_exists=False,
                default_mother="prod",
            )
            self.assertEqual(result["role"], "mother")
            child = ps.add_to_pool(
                "kid1",
                registry_path=path,
                email="kid@example.com",
                cli_logged_in=False,
                cli_exists=False,
                web_dir_exists=True,
                default_mother="prod",
            )
            self.assertEqual(child["role"], "child")
            self.assertEqual(child["state"], "web_session")


class RemoveTests(unittest.TestCase):
    def _registry(self, **extra):
        reg = {
            "version": "3",
            "active_mother_profile": "prod",
            "accounts": [
                {"email": "mom@example.com", "role": "mother", "state": "keyed",
                 "api_key_ref": "flova-profile:prod"},
                {"email": "kid@example.com", "role": "child", "state": "keyed",
                 "api_key_ref": "flova-profile:kid1",
                 "web_profile_ref": "~/.flova-mcp/browser-profiles/kid1"},
                {"email": "legacy@example.com", "role": "child", "state": "registered"},
            ],
        }
        reg.update(extra)
        return reg

    def test_remove_by_profile_drops_the_record_and_makes_a_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text(json.dumps(self._registry()), encoding="utf-8")
            result = ps.remove_from_pool(profile="kid1", registry_path=path)
            self.assertTrue(result["ok"])
            self.assertEqual(result["action"], "removed")
            saved = json.loads(path.read_text(encoding="utf-8"))
            emails = [a["email"] for a in saved["accounts"]]
            self.assertNotIn("kid@example.com", emails)
            self.assertEqual(len(emails), 2)
            backups = list(Path(tmp).glob("registry.bak-remove-*.json"))
            self.assertEqual(len(backups), 1)
            self.assertIn("kid@example.com", backups[0].read_text(encoding="utf-8"))

    def test_remove_by_email_handles_legacy_rows_without_profile_ref(self):
        reg = self._registry()
        result = ps.mutate_remove(reg, email="legacy@example.com", active_profile="prod")
        self.assertTrue(result["ok"])
        self.assertEqual([a["email"] for a in reg["accounts"]],
                         ["mom@example.com", "kid@example.com"])

    def test_active_mother_and_retired_mother_are_protected(self):
        reg = self._registry(accounts=[
            {"email": "mom@example.com", "role": "mother", "state": "keyed",
             "api_key_ref": "flova-profile:prod"},
            {"email": "oldmom@example.com", "role": "retired_mother", "state": "keyed",
             "api_key_ref": "flova-profile:kid9"},
        ])
        denied = ps.mutate_remove(reg, profile="prod", active_profile="prod")
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["reason"], "protected")
        denied_retired = ps.mutate_remove(reg, profile="kid9", active_profile="prod")
        self.assertFalse(denied_retired["ok"])
        self.assertEqual(denied_retired["reason"], "protected")

    def test_remove_unknown_account_is_not_found(self):
        reg = self._registry()
        result = ps.mutate_remove(reg, profile="ghost", active_profile="prod")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "not_in_pool")
        result_no_target = ps.mutate_remove(reg, active_profile="prod")
        self.assertFalse(result_no_target["ok"])
        self.assertEqual(result_no_target["reason"], "no_target")


class RelinkTests(unittest.TestCase):
    def _registry(self):
        return {
            "version": "3",
            "active_mother_profile": "prod",
            "accounts": [
                {"email": "mom@example.com", "role": "mother", "state": "keyed",
                 "api_key_ref": "flova-profile:prod"},
                {"email": "Legacy@example.com", "role": "child", "state": "registered"},
                {"email": "owner@example.com", "role": "child", "state": "keyed",
                 "api_key_ref": "flova-profile:kid2",
                 "web_profile_ref": "~/.flova-mcp/browser-profiles/kid2"},
            ],
        }

    def test_patch_missing_refs_for_matching_email(self):
        reg = self._registry()
        result = ps.mutate_relink(
            reg, email="legacy@example.com", profile="kid11",
            cli_exists=False, web_dir_exists=True, user_id="u-11")
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "patched")
        legacy = next(a for a in reg["accounts"] if a["email"] == "Legacy@example.com")
        self.assertEqual(legacy["web_profile_ref"], "~/.flova-mcp/browser-profiles/kid11")
        self.assertNotIn("api_key_ref", legacy)
        self.assertEqual(legacy["user_id"], "u-11")
        self.assertIn("last_verified", legacy)

    def test_profile_owned_by_another_account_is_rejected(self):
        reg = self._registry()
        result = ps.mutate_relink(
            reg, email="legacy@example.com", profile="kid2",
            cli_exists=True, web_dir_exists=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "profile_owned")
        legacy = next(a for a in reg["accounts"] if a["email"] == "Legacy@example.com")
        self.assertNotIn("api_key_ref", legacy)

    def test_email_not_in_pool_is_rejected(self):
        reg = self._registry()
        result = ps.mutate_relink(
            reg, email="stranger@example.com", profile="kid11",
            cli_exists=False, web_dir_exists=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "email_not_in_pool")

    def test_invalid_profile_name_is_rejected(self):
        result = ps.mutate_relink(
            self._registry(), email="legacy@example.com", profile="bad name",
            cli_exists=False, web_dir_exists=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "invalid_profile")


class ProbeCacheTests(unittest.TestCase):
    def test_roundtrip_keeps_fresh_entries_and_scrubs_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            now = __import__("time").time()
            ps.save_probe_cache({
                "p:kid1": (now, {"profile": "kid1", "credits": 5, "token": "SECRET"}),
            }, path=path)
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("SECRET", raw)
            loaded = ps.load_probe_cache(path=path)
            self.assertIn("p:kid1", loaded)
            ts, row = loaded["p:kid1"]
            self.assertEqual(row["profile"], "kid1")
            self.assertNotIn("token", row)

    def test_old_entries_are_kept_without_expiry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            # 比旧的 30 分钟 TTL 更老的快照：快照不按时间过期。
            old = __import__("time").time() - 1800 - 60
            path.write_text(json.dumps({"version": 1, "entries": {
                "p:kid1": {"ts": old, "row": {"profile": "kid1"}},
            }}), encoding="utf-8")
            loaded = ps.load_probe_cache(path=path)
            self.assertIn("p:kid1", loaded)
            ts, row = loaded["p:kid1"]
            self.assertEqual(ts, old)
            self.assertEqual(row["profile"], "kid1")
            # 再写一次也不能把旧行丢掉。
            ps.save_probe_cache(loaded, path=path)
            reloaded = ps.load_probe_cache(path=path)
            self.assertIn("p:kid1", reloaded)
            self.assertEqual(reloaded["p:kid1"][1]["profile"], "kid1")


class OnboardNamingTests(unittest.TestCase):
    def test_next_onboard_profile_skips_taken(self):
        self.assertEqual(ps.next_onboard_profile(set()), "kid1")
        self.assertEqual(ps.next_onboard_profile({"kid1", "kid2", "kid4"}), "kid3")
        self.assertEqual(ps.next_onboard_profile({"kid1", "kid2", "kid3"}), "kid4")

    def test_collect_onboard_taken_merges_all_three_sources(self):
        registry = {
            "accounts": [
                {"email": "mom@example.com", "api_key_ref": "flova-profile:kid2"},
                {"email": "web-only@example.com",
                 "web_profile_ref": "~/.flova-mcp/browser-profiles/kid4"},
                {"email": "both@example.com", "api_key_ref": "flova-profile:kid5",
                 "web_profile_ref": "~/.flova-mcp/browser-profiles/kid5"},
            ],
        }
        taken = ps.collect_onboard_taken(registry, {"kid1", "kid2"}, {"kid4", "kid6"})
        self.assertEqual(taken, {"kid1", "kid2", "kid4", "kid5", "kid6"})
        # kid1/kid2/kid4/kid5/kid6 都占了，下一个是 kid3（CLI/网页/账本都没有）。
        self.assertEqual(ps.next_onboard_profile(taken), "kid3")

    def test_collect_onboard_taken_does_not_depend_on_cli_only(self):
        # 只存在网页目录的 kid4 必须算占用，不能像 next_child_profiles 那样撞名。
        registry = {"accounts": [
            {"email": "x@example.com",
             "web_profile_ref": "C:/Users/me/.flova-mcp/browser-profiles/kid4"},
        ]}
        taken = ps.collect_onboard_taken(registry, set(), {"kid4"})
        self.assertEqual(ps.next_onboard_profile(taken), "kid1")
        taken = ps.collect_onboard_taken(registry, {"kid1"}, {"kid4"})
        self.assertEqual(ps.next_onboard_profile(taken), "kid2")


class SourceTests(unittest.TestCase):
    def test_cli_and_web_dir_not_in_registry_are_unpooled(self):
        registry = {
            "active_mother_profile": "prod",
            "accounts": [{
                "email": "mom@example.com",
                "role": "mother",
                "state": "keyed",
                "api_key_ref": "flova-profile:prod",
            }],
        }
        rows = ps.collect_sources(registry, {"prod", "kid7"}, {"kid7", "orphan"})
        by_profile = {row["profile"]: row for row in rows}
        self.assertTrue(by_profile["prod"]["in_pool"])
        self.assertFalse(by_profile["kid7"]["in_pool"])
        self.assertIn("cli", by_profile["kid7"]["sources"])
        self.assertFalse(by_profile["orphan"]["in_pool"])
        self.assertEqual(by_profile["orphan"]["sources"], ["web_dir"])


if __name__ == "__main__":
    unittest.main()
