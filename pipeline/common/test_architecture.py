"""Regression tests for shared staging, numbering and non-destructive compaction."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.common import episodes, storage, workspace
from pipeline.common.media import materialize
from pipeline.common.rendering import atomic_output


class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2] / "tmp/architecture-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def episode(self, kind, name, text):
        ep = self.root / "projects" / kind / name
        ep.mkdir(parents=True)
        (ep / "episode.json").write_text("{}", encoding="utf-8")
        (ep / "episode.yaml").write_text(text, encoding="utf-8")
        return ep

    def test_tests_and_directory_aliases_do_not_consume_release_numbers(self):
        self.episode("knowledge", "ep01-intro", "release_number: 1\n")
        self.episode("listing", "ep02-home", "release_number: 2\n")
        self.episode("listing", "ep07-test", "purpose: test\nepisode: 7\n")
        self.episode("interview", "ep00-techtest", "series: interview\npurpose: test\nepisode: 0\n")
        self.assertEqual(episodes.next_release_number(self.root), 3)
        self.assertEqual(len(episodes.list_episodes(self.root)), 4)

    def test_ambiguous_short_name_is_rejected(self):
        for kind in ("listing", "knowledge"):
            self.episode(kind, "ep03-same", "series: " + kind)
        with patch.object(workspace, "REPO", self.root), self.assertRaisesRegex(ValueError, "ambiguous"):
            workspace.episode_path("ep03-same")

    def test_shared_source_is_staged_and_snapshots_are_excluded(self):
        ep = self.episode("listing", "ep02-home", "series: listing\n")
        template = self.root / "templates/map-hub/remotion"
        (template / "src").mkdir(parents=True)
        (template / "src/index.ts").write_text("export {};", encoding="utf-8")
        (template / "src/old.ts.bak_v1").write_text("old", encoding="utf-8")
        (template / "package.json").write_text("{}", encoding="utf-8")
        shared = self.root / "templates/shared/remotion/src"
        shared.mkdir(parents=True)
        (shared / "fonts.ts").write_text("export const ready = true;", encoding="utf-8")
        (self.root / "tools/remotion/node_modules").mkdir(parents=True)
        with patch.multiple(workspace, REPO=self.root, TEMPLATE=template, SHARED=self.root / "public"):
            work = workspace.stage_episode(ep)
            self.assertTrue((work / "src/shared/fonts.ts").is_file())
            self.assertFalse((work / "src/old.ts.bak_v1").exists())
            self.assertEqual((work / "node_modules").resolve(), self.root / "tools/remotion/node_modules")
            old = json.loads((work / "workspace.json").read_text())["template_sha256"]
            (shared / "fonts.ts").write_text("export const ready = false;", encoding="utf-8")
            workspace.stage_episode(ep)
            self.assertNotEqual(json.loads((work / "workspace.json").read_text())["template_sha256"], old)

    def test_atomic_rerender_does_not_change_another_export(self):
        a, b = self.root / "a.mp4", self.root / "b.mp4"
        a.write_bytes(b"old"); os.link(a, b)
        with atomic_output(b) as pending:
            pending.write_bytes(b"new")
        self.assertEqual(a.read_bytes(), b"old")
        self.assertEqual(b.read_bytes(), b"new")
        with self.assertRaises(RuntimeError):
            with atomic_output(b) as pending:
                pending.write_bytes(b"bad")
                raise RuntimeError("render failed")
        self.assertEqual(b.read_bytes(), b"new")

    def test_materialization_detaches_a_hardlinked_generated_copy(self):
        source, destination, update = [self.root / n for n in ("source.mp4", "public.mp4", "update.mp4")]
        source.write_bytes(b"old"); os.link(source, destination)
        update.write_bytes(b"new-content")
        materialize(update, destination)
        self.assertEqual(source.read_bytes(), b"old")
        self.assertEqual(destination.read_bytes(), b"new-content")

    def test_compaction_preserves_raw_paths_and_external_link_targets(self):
        ep = self.episode("listing", "ep02-home", "series: listing\n")
        blob = b"x" * (1024 * 1024)
        for relative in ("footage/raw/original.mp4", "footage/clip.mp4", "public/footage/clip.mp4", "out/drafts/v1/a.mp4", "out/drafts/v1/b.mp4"):
            p = ep / relative; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(blob)
        original = ep / "footage/raw/original.mp4"
        inode = original.stat().st_ino
        build = ep / "work/remotion/build_old"
        build.mkdir(parents=True)
        for name in ("index.html", "bundle.js"):
            (build / name).write_text("generated", encoding="utf-8")
        workspace.directory_link(build / "public", ep / "public")
        with patch.object(storage, "REPO", self.root):
            dry = storage.compact(ep)
            self.assertTrue(build.exists())
            self.assertIsNone(dry["after"])
            result = storage.compact(ep, apply=True)
        self.assertFalse(build.exists())
        self.assertTrue((ep / "public/footage/clip.mp4").is_file())
        self.assertEqual(original.stat().st_ino, inode)
        self.assertFalse(os.path.samefile(original, ep / "footage/clip.mp4"))
        self.assertTrue(os.path.samefile(ep / "footage/clip.mp4", ep / "public/footage/clip.mp4"))
        self.assertGreater(result["reclaimed_bytes"], 1024 * 1024)

    def test_referenced_build_is_kept(self):
        ep = self.episode("listing", "ep02-home", "series: listing\n")
        build = ep / "work/remotion/build_used"; build.mkdir(parents=True)
        for name in ("index.html", "bundle.js"):
            (build / name).write_text("generated", encoding="utf-8")
        (ep / "episode.json").write_text('{"asset":"work/remotion/build_used/public/file.mp4"}', encoding="utf-8")
        with patch.object(storage, "REPO", self.root):
            result = storage.compact(ep, apply=True)
        self.assertTrue(build.exists())
        self.assertEqual(result["referenced_builds_kept"], ["work/remotion/build_used"])


if __name__ == "__main__":
    unittest.main()
