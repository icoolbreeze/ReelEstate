"""Regression cases for foreground-aware distant-background checks."""
import hashlib
import json
import pathlib
import tempfile
import unittest

from PIL import Image, ImageDraw
from harmony_check import analyze_image

REPO = pathlib.Path(__file__).resolve().parents[2]

class ForegroundChecks(unittest.TestCase):
    def setUp(self):
        (REPO / "tmp").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=REPO / "tmp")
        self.path = pathlib.Path(self.temp.name) / "still.png"

    def tearDown(self):
        self.temp.cleanup()

    def scene(self, second_world=False):
        im = Image.new("RGB", (400, 300), "#e9e5df")
        d = ImageDraw.Draw(im)
        for y in range(120, 224, 12):
            d.line((110, y, 290, y), fill="#aaa39b", width=1)
        if second_world:
            for x in range(0, 400, 4):
                d.line((x, 33, x, 83), fill="#4c4943", width=2)
        d.rectangle((40, 42, 240, 70), fill="#faf8f4")
        for x in range(44, 236, 8):
            d.rectangle((x, 46, x + 3, 66), fill="#24211f")
        im.save(self.path)

    def sidecar(self, regions=None):
        data = {
            "version": 1, "width": 400, "height": 300, "frame": 0,
            "image_sha256": hashlib.sha256(self.path.read_bytes()).hexdigest(),
            "foreground": regions or [{"role": "title", "x": 40, "y": 42, "w": 200, "h": 28}],
        }
        self.path.with_suffix(".layers.json").write_text(json.dumps(data), encoding="utf-8")

    def finding(self, report, key):
        return next(f for f in report.findings if f.id == key)

    def test_foreground_title_is_not_a_second_background(self):
        self.scene()
        self.assertFalse(self.finding(analyze_image(str(self.path), "#9A463D"), "D3").ok)
        self.sidecar()
        self.assertTrue(self.finding(analyze_image(str(self.path), "#9A463D"), "D3").ok)

    def test_a_second_sharp_background_still_fails(self):
        self.scene(second_world=True)
        self.sidecar()
        self.assertFalse(self.finding(analyze_image(str(self.path), "#9A463D"), "D3").ok)

    def test_stale_bounds_fail_instead_of_exempting_image(self):
        self.scene()
        self.sidecar()
        Image.new("RGB", (400, 300), "white").save(self.path)
        self.assertFalse(self.finding(analyze_image(str(self.path), "#9A463D"), "D3meta").ok)

    def test_whole_image_cannot_be_declared_foreground(self):
        self.scene()
        self.sidecar([{"role": "title", "x": 0, "y": 0, "w": 400, "h": 300}])
        self.assertFalse(self.finding(analyze_image(str(self.path), "#9A463D"), "D3meta").ok)

    def test_other_metrics_are_unchanged(self):
        self.scene()
        before = analyze_image(str(self.path), "#9A463D")
        self.sidecar()
        after = analyze_image(str(self.path), "#9A463D")
        a = [(f.id, f.ok) for f in before.findings if not f.id.startswith("D3")]
        b = [(f.id, f.ok) for f in after.findings if not f.id.startswith("D3")]
        self.assertEqual(a, b)


    def test_measured_single_full_frame_footage_is_one_world(self):
        self.scene(second_world=True)
        self.sidecar()
        sidecar=self.path.with_suffix(".layers.json")
        data=json.loads(sidecar.read_text(encoding="utf-8"))
        data["worlds"]=[{"kind":"video","source":"living-room.mp4","x":0,"y":0,"w":400,"h":300}]
        sidecar.write_text(json.dumps(data),encoding="utf-8")
        self.assertTrue(self.finding(analyze_image(str(self.path),"#9A463D"),"D3").ok)

    def test_two_background_worlds_are_never_exempted(self):
        self.scene(second_world=True)
        self.sidecar()
        sidecar=self.path.with_suffix(".layers.json")
        data=json.loads(sidecar.read_text(encoding="utf-8"))
        data["worlds"]=[
            {"kind":"video","source":"living-room.mp4","x":0,"y":0,"w":400,"h":300},
            {"kind":"map","source":"second-map.png","x":0,"y":0,"w":400,"h":100},
        ]
        sidecar.write_text(json.dumps(data),encoding="utf-8")
        self.assertFalse(self.finding(analyze_image(str(self.path),"#9A463D"),"D3").ok)

if __name__ == "__main__":
    unittest.main()
