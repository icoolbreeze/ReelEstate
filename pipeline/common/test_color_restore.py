"""Fast tests for D-Log M detection and auto-restore using synthetic ffmpeg clips (~10 s)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.common import color_restore as cr

REPO = Path(__file__).resolve().parents[2]


def make_clip(path, vf, audio=True, pix_fmt="yuv420p"):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "testsrc2=s=320x240:d=2:r=24"]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=f=440:d=2"]
    cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", pix_fmt]
    if audio:
        cmd += ["-c:a", "aac", "-shortest"]
    subprocess.run(cmd + [str(path)], check=True)


def identity_cube(path, n=5):
    lines = ["LUT_3D_SIZE %d" % n]
    for b in range(n):
        for g in range(n):
            for r in range(n):
                lines.append("%.6f %.6f %.6f" % (r / (n - 1), g / (n - 1), b / (n - 1)))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg required")
class ColorRestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scratch = REPO / "tmp/color-restore-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(dir=scratch)
        root = Path(cls.tmp.name)
        cls.ep = root / "ep99 test"            # space in path on purpose
        raw = cls.ep / "footage/raw"
        raw.mkdir(parents=True)
        # Simulated D-Log M: 10-bit, lifted blacks, compressed highlights, low saturation.
        make_clip(raw / "模拟log 1.mp4", "eq=contrast=0.45:brightness=0.06:saturation=0.05", pix_fmt="yuv420p10le")
        make_clip(raw / "normal.mp4", "eq=saturation=1.3", audio=False)
        make_clip(raw / "normal10.mp4", "eq=saturation=1.3,drawbox=x=0:y=0:w=80:h=80:color=black:t=fill",
                  audio=False, pix_fmt="yuv420p10le")
        luts = root / "luts dir"
        (luts / "restore").mkdir(parents=True)
        (luts / "style").mkdir()
        cls.restore = luts / "restore/restore lut.cube"
        identity_cube(cls.restore)
        identity_cube(luts / "style/DJI OSMO Pocket 3 Spring Pro.cube")
        cls.patches = [patch.object(cr, "RESTORE_LUT", cls.restore), patch.object(cr, "LUT_DIR", luts)]
        for p in cls.patches:
            p.start()

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()
        cls.tmp.cleanup()

    def test_classification_and_restore(self):
        raw = self.ep / "footage/raw"
        log = cr.classify(raw / "模拟log 1.mp4")
        normal = cr.classify(raw / "normal.mp4")
        self.assertEqual(log["class"], "dlogm", log["reasons"])
        self.assertEqual(normal["class"], "rec709", normal["reasons"])
        self.assertEqual(cr.classify(raw / "normal10.mp4")["class"], "unknown")
        before = {p.name: p.stat().st_mtime_ns for p in raw.iterdir()}

        report = cr.process(self.ep, style="Spring", proxy=True, log=lambda *a, **k: None)
        rows = {r["clip"]: r for r in report["clips"]}
        self.assertEqual(rows["normal.mp4"]["action"], "none_rec709")
        self.assertEqual(rows["normal10.mp4"]["action"], "none_unknown_needs_review")
        self.assertEqual(rows["模拟log 1.mp4"]["action"], "converted")
        out = self.ep / "footage/restored"
        restored, styled = out / "master/模拟log 1_r709.mov", out / "master/模拟log 1_r709_Spring.mov"
        proxy = out / "proxy/模拟log 1_r709.mp4"
        self.assertTrue(restored.is_file() and styled.is_file() and proxy.is_file())
        meta = cr.probe(restored)            # default: 10-bit ProRes 422 HQ for Resolve
        self.assertEqual((meta["codec"], meta["pix_fmt"], meta["bits"]), ("prores", "yuv422p10le", 10))
        self.assertEqual(meta["audio_codecs"], ["pcm_s16le"])
        self.assertEqual((meta["color_transfer"], meta["color_primaries"], meta["color_space"]), ("bt709",) * 3)
        pmeta = cr.probe(proxy)              # 8-bit H.264 proxy for Remotion
        self.assertEqual((pmeta["codec"], pmeta["bits"], pmeta["audio_codecs"]), ("h264", 8, ["aac"]))
        self.assertEqual(cr.classify(restored)["already_restored"], True)
        saved = json.loads((out / "color_report.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["summary"], {"dlogm": 1, "rec709": 1, "unknown": 1})
        # raw untouched, second run skips up-to-date outputs
        self.assertEqual(before, {p.name: p.stat().st_mtime_ns for p in raw.iterdir()})
        again = cr.process(self.ep, style="Spring", log=lambda *a, **k: None)
        self.assertEqual({r["clip"]: r["action"] for r in again["clips"]}["模拟log 1.mp4"], "skipped_up_to_date")

    def test_metadata_rules(self):
        base = {"tags": {"format.encoder": "DJI OsmoPocket3"}, "bits": 10, "codec": "hevc", "color_transfer": "bt709",
                "duration": 2, "color_range": "tv", "audio_codecs": [], "dji_template": None}
        log, normal = ({"log_score": s, "votes": {}} for s in (1.0, 0.0))
        def run(meta, metrics, name="x.mp4"):
            with patch.object(cr, "probe", return_value=dict(meta)), patch.object(cr, "pixel_metrics", return_value=metrics):
                return cr.classify(name)["class"]
        self.assertEqual(run({**base, "bits": 8, "codec": "h264"}, log), "rec709")       # 8-bit: never D-Log M
        self.assertEqual(run({**base, "color_transfer": "arib-std-b67"}, log), "unknown")  # HLG
        # real Pocket 3 sensor templates (2026-10-28 SD card)
        self.assertEqual(run({**base, "dji_template": "TPLG_IMX989_VIDEO_1080P_2997_HDR_10BIT"}, normal), "dlogm")
        self.assertEqual(run({**base, "dji_template": "TPLG_IMX989_VIDEO_1080P_2997_HDR"}, log), "unknown")
        self.assertEqual(run({**base, "dji_template": "TPLG_IMX989_VIDEO_1080P_2997_LOWLIGHT"}, log), "unknown")
        # no template: pixels decide, BOTH lifted blacks and low saturation required
        self.assertEqual(run(base, log), "dlogm")
        self.assertEqual(run(base, {"log_score": 0.5, "votes": {}}), "unknown")
        self.assertEqual(run(base, normal), "unknown")
        self.assertEqual(run(base, log, "DJI_0001_r709.mov"), "rec709")  # already restored


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg required")
class ConventionAndGateTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / "tmp/color-restore-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.ep = root / "ep98"
        (self.ep / "footage/raw").mkdir(parents=True)
        (self.ep / "episode.yaml").write_text("id: ep98\n", encoding="utf-8")
        luts = root / "luts"
        (luts / "restore").mkdir(parents=True)
        (luts / "style").mkdir()
        identity_cube(luts / "restore/r.cube")
        for p in (patch.object(cr, "RESTORE_LUT", luts / "restore/r.cube"), patch.object(cr, "LUT_DIR", luts)):
            p.start()
            self.addCleanup(p.stop)
        self.quiet = lambda *a, **k: None

    def test_gate_fails_until_restored_and_render_paths_use_proxy(self):
        raw = self.ep / "footage/raw"
        make_clip(raw / "log.mp4", "eq=contrast=0.45:brightness=0.06:saturation=0.05", pix_fmt="yuv420p10le")
        make_clip(raw / "phone.mp4", "eq=saturation=1.3", audio=False)
        errors, _ = cr.gate(self.ep)
        self.assertTrue(any("log.mp4" in e for e in errors), errors)      # 10-bit, not classified yet
        with self.assertRaises(ValueError):
            cr.restored_for(self.ep, raw / "log.mp4")
        self.assertEqual(cr.restored_for(self.ep, raw / "phone.mp4"), (raw / "phone.mp4").resolve())
        report = cr.process(self.ep, log=self.quiet)                     # default: ProRes + proxy
        self.assertEqual(report["encoders"][0], "prores")
        self.assertEqual(len(report["encoders"]), 2)
        self.assertEqual(cr.gate(self.ep)[0], [])
        self.assertEqual(cr.restored_for(self.ep, raw / "log.mp4").name, "log_r709.mp4")
        self.assertEqual(cr.restored_for(self.ep, raw / "log.mp4").parent.name, "proxy")
        self.assertEqual(cr.restored_for(self.ep, raw / "log.mp4", "matte").parent.name, "master")
        self.assertEqual(cr.restored_for(self.ep, "footage/raw/log.mp4", "matte").name, "log_r709.mov")
        self.assertEqual(cr.restored_for_any(raw / "log.mp4", "grade").suffix, ".mov")
        (self.ep / "footage/restored/proxy/log_r709.mp4").unlink()             # proxy missing -> check fails again
        self.assertTrue(cr.gate(self.ep)[0])

    def test_assume_needs_only_and_never_applies_to_hdr(self):
        raw = self.ep / "footage/raw"
        make_clip(raw / "n10.mp4", "eq=saturation=1.3,drawbox=x=0:y=0:w=80:h=80:color=black:t=fill",
                  audio=False, pix_fmt="yuv420p10le")
        with self.assertRaisesRegex(ValueError, "--only"):
            cr.process(self.ep, assume="dlogm", dry_run=True, log=self.quiet)
        row = cr.process(self.ep, assume="dlogm", only=["n10"], dry_run=True, log=self.quiet)["clips"][0]
        self.assertEqual(row.get("effective_class"), "dlogm")
        hdr = {"class": "unknown", "confidence": 0.9, "hdr": True, "reasons": [], "metrics": None, "metadata": {}}
        with patch.object(cr, "classify", return_value=dict(hdr)):
            row = cr.process(self.ep, assume="dlogm", only=["n10"], dry_run=True, log=self.quiet)["clips"][0]
        self.assertNotIn("effective_class", row)
        self.assertEqual(row["action"], "none_unknown_needs_review")

    def test_selects_dlogm_always_restored_and_lossless_trim(self):
        raw = self.ep / "footage/raw"
        make_clip(raw / "take.mp4", "eq=saturation=1.3,drawbox=x=0:y=0:w=80:h=80:color=black:t=fill",
                  pix_fmt="yuv420p10le")                                 # looks normal, but user selected it as D-Log M
        before = (raw / "take.mp4").stat().st_mtime_ns
        sel = cr.select_clip(self.ep, "take.mp4", 0.5, 1.5)
        self.assertEqual(sel.parent.name, "selects_dlogm")
        self.assertEqual(cr.probe(sel)["codec"], "h264")                 # stream copy, no re-encode
        self.assertLess(cr.probe(sel)["duration"], 1.9)
        self.assertEqual((raw / "take.mp4").stat().st_mtime_ns, before)
        report = cr.process(self.ep, encoder="x264", log=self.quiet)
        rows = {(r["dir"], r["clip"]): r for r in report["clips"]}
        self.assertEqual(rows[("selects", sel.name)]["effective_class"], "dlogm")
        self.assertEqual(rows[("raw", "take.mp4")]["class"], "unknown")
        self.assertTrue((self.ep / "footage/restored/proxy" / ("selects__" + sel.stem + "_r709.mp4")).is_file())
        shot = self.ep / "footage/shots/take.mp4"                       # render-bound shots/ must not be raw D-Log M
        shot.parent.mkdir(parents=True)
        shutil.copy2(raw / "take.mp4", shot)
        with patch.object(cr, "quick_class", return_value="dlogm"):
            self.assertTrue(any("footage/shots/take.mp4" in e for e in cr.gate(self.ep)[0]))


if __name__ == "__main__":
    unittest.main()
