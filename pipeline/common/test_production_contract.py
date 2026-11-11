"""The current production contract cannot fall back to historical projects or test data."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.common import workspace
from pipeline import video

REPO = Path(__file__).resolve().parents[2]


class ProductionContractTests(unittest.TestCase):
    def setUp(self):
        base = REPO / "tmp/production-contract-tests"
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def test_old_project_json_is_never_dispatched(self):
        ep = self.root / "projects/rental/old-project"
        ep.mkdir(parents=True)
        (ep / "project.json").write_text("{}", encoding="utf-8")
        with patch.object(workspace, "REPO", self.root), patch.object(video, "REPO", self.root), patch.object(video, "run") as run:
            with self.assertRaisesRegex(ValueError, "episode.yaml"):
                video.main(["render", str(ep)])
            run.assert_not_called()

    def test_episode_json_without_yaml_is_rejected(self):
        ep = self.root / "projects/listing/ep03-partial"
        ep.mkdir(parents=True)
        (ep / "episode.json").write_text("{}", encoding="utf-8")
        with patch.object(workspace, "REPO", self.root), self.assertRaisesRegex(ValueError, "episode.yaml"):
            workspace.episode_path(ep)

    def test_creator_has_no_test_episode_dependency(self):
        spec = importlib.util.spec_from_file_location("production_new_episode", REPO / "scripts/new_episode.py")
        creator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(creator)
        self.assertEqual(creator.TEMPLATE, REPO / "templates/listing/episode.json")
        self.assertNotIn("xihu", creator.TEMPLATE.read_text(encoding="utf-8").lower())
        for category in ("rental", "resale", "new-home"):
            data = {"episode": 3, "category": category, "slug": category.replace("-", ""), "layout": "", "id": "ep03-" + category.replace("-", ""), "listing": "test-ref" if category != "new-home" else "", "topic": "", "title": "测试楼盘", "city": "成都", "footage": None}
            ep = creator.create(self.root / category, data, creator.TEMPLATE)
            payload = json.loads((ep / "episode.json").read_text(encoding="utf-8"))
            self.assertIsNone(payload["listing"]["area"])
            self.assertIsNone(payload["plane"]["center"])
            self.assertEqual(payload["mapBase"]["file"], "")
            draft = json.loads((ep / "compliance.json.draft").read_text(encoding="utf-8"))
            self.assertEqual(draft["category"], category)
            self.assertNotIn("narration", draft)
            self.assertFalse((ep / "project.json").exists())
            self.assertFalse((ep / "data/project.json").exists())
            self.assertTrue((ep / "footage/raw_manifest.json").is_file())
            self.assertEqual("rent" in payload["listing"], category == "rental")
            self.assertEqual((ep / "sources/docs").is_dir(), category == "new-home")
            self.assertIs(payload["sampleData"], False)                  # all listings are real by default
            self.assertEqual(payload["sampleTag"], "")
            self.assertIn("sample_data: false", (ep / "episode.yaml").read_text(encoding="utf-8"))

    def test_old_file_cannot_satisfy_new_compliance_requirement(self):
        sys.path.insert(0, str(REPO / "pipeline/check"))
        import check as checker
        ep = self.root / "projects/listing/ep03-check"
        ep.mkdir(parents=True)
        (ep / "episode.yaml").write_text("category: rental\n", encoding="utf-8")
        (ep / "episode.json").write_text("{}", encoding="utf-8")
        (ep / "project.json").write_text("{}", encoding="utf-8")
        report = checker.run(ep)
        self.assertTrue(report.failed)
        self.assertTrue(any("compliance.json" in msg for _, _, msg in report.items))


if __name__ == "__main__":
    unittest.main()
