"""Regression checks for episode isolation and explicit TTS backup behavior."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline/maphub"))
import workspace
import voice_config
import voice_timing
import check_episode
import build_vo
import heygen_plan

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / "jobs/agent"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def episode(self, name="ep01-test"):
        ep = self.root / "projects/listing" / name
        (ep / "data").mkdir(parents=True)
        (ep / "public/episode/vo").mkdir(parents=True)
        (ep / "episode.json").write_text('{"sampleData": true}', encoding="utf-8")
        (ep / "episode.yaml").write_text("presenter: test\nscript: script.json\noncam_budget_s: 55\n", encoding="utf-8")
        (ep / "script.json").write_text('{"lines":[]}', encoding="utf-8")
        return ep

    def template(self):
        tpl = self.root / "templates/map-hub/remotion"
        (tpl / "src").mkdir(parents=True)
        (tpl / "node_modules").mkdir()
        (tpl / "src/index.ts").write_text("export {};", encoding="utf-8")
        (tpl / "package.json").write_text("{}", encoding="utf-8")
        shared = self.root / "templates/map-hub/shared/public"
        for name in ("fonts", "brands", "social"):
            (shared / name).mkdir(parents=True)
        return tpl, shared

    def test_two_episodes_have_separate_links_and_never_switch_template(self):
        first, second = self.episode(), self.episode("ep02-other")
        tpl, shared = self.template()
        with patch.multiple(workspace, REPO=self.root, TEMPLATE=tpl, SHARED=shared):
            a = workspace.stage_episode(first)
            b = workspace.stage_episode(second)
            self.assertEqual((a / "src/episode").resolve(), first / "data")
            self.assertEqual((b / "src/episode").resolve(), second / "data")
            self.assertEqual((a / "public").resolve(), first / "public")
            self.assertFalse((tpl / "src/episode").exists())
            (a / "src/episode/test.json").write_text("first", encoding="utf-8")
            self.assertFalse((b / "src/episode/test.json").exists())
            with self.assertRaises(ValueError):
                workspace.project_for(first, tpl)

    def test_voice_precedence_and_explicit_f5_backup(self):
        ep = self.episode()
        profile = self.root / "assets/presenter/test"
        profile.mkdir(parents=True)
        (profile / "presenter.yaml").write_text(
            "voice:\n  engine: indextts25\n  fallback_engine: f5\n  seed: 22\n  speed_oncam: 1.05\n  speed_vo: 1.0\n"
            "  ref_wav: ref.wav\n  ref_text: ref.txt\n  emo_ref_wav: emotion.wav\n", encoding="utf-8")
        (ep / "episode.yaml").write_text(
            "presenter: test\nscript: script.json\npresenter_override:\n  voice: {seed: 33, speed_vo: 1.07}\n", encoding="utf-8")
        (ep / "script.json").write_text(json.dumps({"hook":{"id":"HOOK"}, "lines":[]}), encoding="utf-8")
        data = {"lines":[{"id":"HOOK","text":"开场","seed":44},{"id":"L1","text":"内容"},{"id":"L2","text":"结论","speed":0.95}]}
        with patch.object(voice_config, "REPO", self.root):
            cfg, _ = voice_config.prepare_narration(ep, data)
            self.assertEqual(cfg["lines"][0]["seed"], 44)
            self.assertEqual(cfg["lines"][0]["speed"], 1.05)
            self.assertEqual(cfg["lines"][1]["seed"], 33)
            self.assertEqual(cfg["lines"][1]["speed"], 1.07)
            self.assertEqual(cfg["lines"][2]["speed"], 0.95)
            self.assertEqual(cfg["lines"][1]["emo_ref"], "emotion.wav")
            f5, _ = voice_config.prepare_narration(ep, data, engine="f5")
            self.assertEqual(f5["engine"], "f5")
            self.assertEqual(f5["resolved"]["fallback_policy"], "explicit")
            self.assertNotIn("emo_ref", f5["lines"][1])

    def test_missing_clone_never_invokes_edge(self):
        with patch.object(build_vo, "VOICE_DIR", self.root), patch.object(build_vo, "_synth") as edge:
            with self.assertRaisesRegex(ValueError, "missing cloned audio"):
                build_vo.tts("测试", "voice", "+0%", self.root, "missing")
            edge.assert_not_called()

    def test_duplicate_and_missing_voice_lines_stop_preflight(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            voice_timing.require_clone_files({"lines":[{"id":"L1"}]}, self.root)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            voice_timing.require_clone_files({"lines":[{"id":"L1"},{"id":"L1"}]}, self.root)

    def test_alignment_matches_current_audio_and_script(self):
        audio = self.root / "L1.wav"
        audio.write_bytes(b"original-audio")
        data = {"text":"你好，世界。","audio_sha256":voice_timing.fingerprint(audio),
                "words":[{"t":"你好","s":0.2,"e":0.7},{"t":"世界","s":1.4,"e":2.0}]}
        audio.with_suffix(".json").write_text(json.dumps(data), encoding="utf-8")
        words = voice_timing.read_alignment(audio, "你好，世界。")
        caps = voice_timing.caption_frames("你好，世界。", ["你好","世界"], words, 2.2, 30, 30)
        self.assertEqual(caps[1]["f0"], 72)  # actual pause is preserved
        audio.write_bytes(b"new-audio")
        with self.assertRaisesRegex(ValueError, "stale"):
            voice_timing.read_alignment(audio, "你好，世界。")

    def test_editorial_captions_need_explicit_spans_for_final(self):
        words = [{"t":"你好世界","s":0,"e":2}]
        with self.assertRaises(ValueError):
            voice_timing.caption_frames("你好世界", ["问候"], words, 2, 0, 30)
        caps = voice_timing.caption_frames("你好世界", ["问候"], words, 2, 0, 30, spans=[[0,4]])
        self.assertEqual(caps[0]["f1"], 60)

    def test_heygen_budget_stops_before_writing_audio(self):
        ep = self.episode()
        (ep / "episode.yaml").write_text("oncam_budget_s: 0.5\n", encoding="utf-8")
        proj = self.root / "project"
        (proj / "src/episode").mkdir(parents=True)
        (proj / "src/episode/timeline.json").write_text(json.dumps({"lines":[
            {"id":"L1","clip":"HG1","onCam":"A","tts":"测试","audio":"vo.mp3"}
        ]}), encoding="utf-8")
        import numpy as np
        with patch.object(heygen_plan, "dec", return_value=np.zeros(48000)), patch.object(heygen_plan.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "budget"):
                heygen_plan.plan(ep, proj)
            run.assert_not_called()
            self.assertFalse((ep / "heygen/heygen_audio.wav").exists())

    def test_final_rejects_old_draft_timeline_and_placeholders(self):
        ep = self.episode()
        (ep / "data/timeline.json").write_text(json.dumps({
            "fps":30,"total":30,"script_file":"script.json","script_sha256":voice_timing.fingerprint(ep/"script.json"),
            "audio_mode":"draft","draft":True,"lines":[{"id":"L1","f0":0,"f1":30,"clip":"LR1","audio":"episode/vo/L1.mp3",
            "caps":[{"text":"测试","f0":0,"f1":30}],"caption_timing":"estimated"}]
        }), encoding="utf-8")
        (ep / "data/footage.json").write_text('{"LR1":{"kind":"pending"}}', encoding="utf-8")
        (ep / "public/episode/vo/L1.mp3").write_bytes(b"audio")
        (ep / "public/episode/mix.wav").write_bytes(b"mix")
        with patch.object(workspace, "REPO", self.root), patch.object(check_episode, "REPO", self.root):
            report = check_episode.check_episode(ep)
            self.assertFalse(report["pass"])
            self.assertTrue(any("draft" in e for e in report["errors"]))
            self.assertTrue(any("pending" in e for e in report["errors"]))
            self.assertTrue(check_episode.check_episode(ep, draft=True)["pass"])

    def test_changed_script_requires_new_timeline(self):
        ep = self.episode()
        (ep / "data/timeline.json").write_text(json.dumps({"fps":30,"script_sha256":"old","lines":[]}), encoding="utf-8")
        (ep / "data/footage.json").write_text("{}", encoding="utf-8")
        with patch.object(workspace, "REPO", self.root), patch.object(check_episode, "REPO", self.root):
            report = check_episode.check_episode(ep, draft=True)
            self.assertTrue(any("script changed" in e for e in report["errors"]))

    def test_old_heygen_export_cannot_be_split_against_new_voice(self):
        ep = self.episode()
        (ep / "data/timeline.json").write_text("{}", encoding="utf-8")
        (ep / "heygen").mkdir()
        original = ep / "heygen/export.mp4"
        original.write_bytes(b"old-export")
        import os
        os.utime(original, (1,1))
        plan = {"timeline_sha256":voice_timing.fingerprint(ep/"data/timeline.json"),"segments":[]}
        (ep / "heygen/segments.json").write_text(json.dumps(plan), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "predates"):
            heygen_plan.split(ep, original, 0, ep/"footage/heygen")

    def test_reused_plan_still_respects_reduced_budget(self):
        ep = self.episode()
        proj = self.root / "project"
        (proj / "src/episode").mkdir(parents=True)
        timeline = proj / "src/episode/timeline.json"
        timeline.write_text('{"lines":[]}', encoding="utf-8")
        (ep / "heygen").mkdir()
        (ep / "heygen/heygen_audio.wav").write_bytes(b"audio")
        (ep / "heygen/segments.json").write_text(json.dumps({
            "timeline_sha256":voice_timing.fingerprint(timeline),"total":56
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "budget"):
            heygen_plan.plan(ep, proj)

    def test_clone_audio_build_and_final_preflight_end_to_end(self):
        import math
        import struct
        import wave
        import subprocess
        import shutil
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("ffmpeg/ffprobe not installed")
        parent = REPO / "projects/listing"
        with tempfile.TemporaryDirectory(prefix="ep00-test-", dir=parent) as temp:
            ep = Path(temp)
            (ep/"episode.json").write_text('{"sampleData":true}', encoding="utf-8")
            (ep/"episode.yaml").write_text("script: script.json\n", encoding="utf-8")
            (ep/"script.json").write_text(json.dumps({"voice":"draft-only","rate":"+0%","lines":[
                {"id":"L1","layout":"MAP","onCam":"VO","tts":"你好，世界。","cap":["你好","世界"]}
            ]},ensure_ascii=False),encoding="utf-8")
            (ep/"voice/final").mkdir(parents=True)
            audio = ep/"voice/final/L1.wav"
            with wave.open(str(audio),"wb") as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(22050)
                wav.writeframes(b"".join(struct.pack("<h",int(1000*math.sin(i*2*math.pi*220/22050))) for i in range(66150)))
            audio.with_suffix(".json").write_text(json.dumps({
                "text":"你好，世界。","audio_sha256":voice_timing.fingerprint(audio),
                "words":[{"t":"你好","s":0.2,"e":0.7},{"t":"世界","s":1.4,"e":2.0}]
            }),encoding="utf-8")
            proc = subprocess.run([sys.executable,"-B",str(REPO/"pipeline/maphub/build_vo.py"),str(ep),
                "--voice-dir",str(ep/"voice/final"),"--bgm",str(ep/"absent-bgm.mp3")],
                capture_output=True,text=True,encoding="utf-8")
            self.assertEqual(proc.returncode,0,proc.stderr)
            (ep/"data/footage.json").write_text("{}",encoding="utf-8")
            report = check_episode.check_episode(ep)
            self.assertTrue(report["pass"],report["errors"])
            audio.write_bytes(audio.read_bytes()+b"changed")
            changed = check_episode.check_episode(ep)
            self.assertTrue(any("audio changed" in error for error in changed["errors"]))


if __name__ == "__main__":
    unittest.main()
