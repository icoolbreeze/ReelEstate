"""footage/raw_manifest.json maps read-only camera clips (DJI names kept) to rooms and shots."""
import json
import tempfile
import unittest
from pathlib import Path
from pipeline.common import raw_manifest as rm

REPO = Path(__file__).resolve().parents[2]


class RawManifestTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / "tmp/raw-manifest-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.ep = Path(self.tmp.name) / "ep09-demo"
        raw = self.ep / "footage/raw"
        raw.mkdir(parents=True)
        (self.ep / "episode.yaml").write_text("id: ep09-demo\n", encoding="utf-8")
        for name in ("DJI_20261030111005_0271_D.MP4", "客厅_1.mp4", "DJI_20261030111005_0271_D.LRF"):
            (raw / name).write_bytes(b"")

    def test_init_validate_and_lookup(self):
        raw = self.ep / "footage/raw"
        before = sorted((p.name, p.stat().st_mtime_ns) for p in raw.iterdir())
        errors, warnings = rm.validate(self.ep)
        self.assertEqual(errors, [])
        self.assertTrue(any("no footage/raw_manifest.json" in w for w in warnings))
        data, added = rm.init(self.ep, probe=False)
        self.assertEqual(added, 2)                                     # .LRF proxies are not clips
        rows = {r["file"]: r for r in data["clips"]}
        self.assertEqual(rows["客厅_1.mp4"]["room"], "客厅")
        self.assertEqual(rows["DJI_20261030111005_0271_D.MP4"]["room"], "")
        self.assertEqual(before, sorted((p.name, p.stat().st_mtime_ns) for p in raw.iterdir()))   # raw untouched
        self.assertFalse((raw / "raw_manifest.json").exists())
        self.assertEqual(rm.validate(self.ep), ([], []))
        rows["DJI_20261030111005_0271_D.MP4"].update(shot="LR1", **{"in": 1.0, "out": 4.0})
        (self.ep / rm.MANIFEST).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        path, t_in, t_out = rm.clip_for_shot(self.ep, "LR1")
        self.assertEqual((path.name, t_in, t_out), ("DJI_20261030111005_0271_D.MP4", 1.0, 4.0))
        self.assertIsNone(rm.clip_for_shot(self.ep, "KT1"))
        data["clips"].append({"file": "gone.mp4", "shot": "LR1", "use": "maybe"})
        (self.ep / rm.MANIFEST).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors, _ = rm.validate(self.ep)
        self.assertEqual(len(errors), 3, errors)                        # missing file, bad use, duplicate shot
        _, again = rm.init(self.ep, probe=False)
        self.assertEqual(again, 0)                                      # existing rows kept, nothing re-added

    def test_legacy_import_log_is_converted(self):
        legacy = [{"source": "VID_20261019_165943.mp4", "raw": "客厅_1.mp4", "sha256": "AB"},
                  {"source": "IMG_1.jpg", "raw": "photos/IMG_1.jpg", "sha256": "CD"}]
        (self.ep / rm.MANIFEST).write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
        errors, _ = rm.validate(self.ep)
        self.assertTrue(errors and "old import-log" in errors[0])
        data, added = rm.init(self.ep, probe=False)
        rows = {r["file"]: r for r in data["clips"]}
        self.assertEqual((rows["客厅_1.mp4"]["source_name"], rows["客厅_1.mp4"]["sha256"], rows["客厅_1.mp4"]["room"]),
                         ("VID_20261019_165943.mp4", "AB", "客厅"))
        self.assertEqual(added, 1)                                      # the DJI clip
        self.assertEqual(data["stills"], [{"file": "photos/IMG_1.jpg", "source_name": "IMG_1.jpg", "sha256": "CD"}])
        self.assertEqual(rm.validate(self.ep), ([], []))


if __name__ == "__main__":
    unittest.main()
