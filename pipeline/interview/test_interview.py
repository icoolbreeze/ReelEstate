"""Behaviour tests for the interview series. No GPU, no paid API, no real footage."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.common import episodes, workspace
from pipeline.common.matte_size import acceptance, inference_size, oom_note, use_fp16
from pipeline.interview import cache, captions, editlist, layout, matte_plan, probe, research, resolve_export, sync, timebase, transcript


class InterviewTests(unittest.TestCase):
    def test_series_routing_rejects_unknown(self):
        self.assertEqual(episodes.classify_series("interview"), "interview")
        self.assertEqual(episodes.classify_series("listing"), "listing")
        with self.assertRaisesRegex(ValueError, "unknown series"):
            episodes.classify_series("map-hub")      # retired alias (2026-10-30)
        self.assertEqual(episodes.classify_series("knowledge"), "knowledge")
        with self.assertRaisesRegex(ValueError, "unknown series"):
            episodes.classify_series("nope")
        with self.assertRaisesRegex(ValueError, "unknown series"):
            episodes.classify_series(None)

    def test_unknown_template_is_not_listing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ep = root / "projects" / "interview" / "ep00-x"
            ep.mkdir(parents=True)
            (ep / "episode.yaml").write_text("series: nope\n", encoding="utf-8")
            with patch.object(workspace, "REPO", root):
                with self.assertRaisesRegex(ValueError, "unknown series"):
                    workspace.template_for(ep)

    def test_inference_sizes_follow_the_short_side_cap(self):
        native_720 = inference_size(1280, 720, 1080)
        self.assertEqual((native_720["inference_width"], native_720["inference_height"]), (1280, 720))
        self.assertTrue(native_720["native_inference"])
        self.assertFalse(native_720["native_4k"])
        hd = inference_size(1920, 1080, 1080)
        self.assertEqual((hd["inference_width"], hd["inference_height"]), (1920, 1080))
        self.assertFalse(hd["mask_interpolated_to_output"])
        uhd = inference_size(3840, 2160, 1080)
        self.assertEqual((uhd["inference_width"], uhd["inference_height"]), (1920, 1080))
        self.assertFalse(uhd["native_4k"])
        self.assertTrue(uhd["mask_interpolated_to_output"])
        self.assertEqual((uhd["output_width"], uhd["output_height"]), (3840, 2160))
        portrait = inference_size(2160, 3840, 1080)
        self.assertEqual((portrait["inference_width"], portrait["inference_height"]), (1080, 1920))
        self.assertFalse(portrait["native_4k"])
        explicit = inference_size(1920, 1080, 720)
        self.assertEqual(explicit["inference_height"], 720)
        self.assertNotEqual(inference_size(1920, 1080, 1080)["inference_height"], 720)

    def test_fallback_is_not_a_matanyone_pass_and_fp16_stays_off(self):
        row = acceptance("matanyone2", "rvm", "RuntimeError: CUDA out of memory")
        self.assertFalse(row["matanyone2_passed"])
        self.assertTrue(row["fallback"])
        self.assertIsNotNone(oom_note(row["fallback_reason"]))
        self.assertFalse(use_fp16("matanyone2", True))
        self.assertTrue(acceptance("matanyone2", "matanyone2", None)["matanyone2_passed"])

    def test_caption_times_follow_the_edit_not_the_outline(self):
        segments = [{
            "id": "E01", "source_in_ms": 1000, "source_out_ms": 2500, "source_id": "cam_a", "shot": "A", "layout": "question",
        }]
        spans = [
            {"text": "实际说的话", "speaker": "guest", "source_in_ms": 1200, "source_out_ms": 2200},
            {"text": "提纲里的句子不应该变成字幕", "speaker": "interviewer", "source_in_ms": 9000, "source_out_ms": 9500},
        ]
        mapped, total = captions.map_captions(segments, spans, 30)
        self.assertEqual(total, 1500)
        self.assertEqual([row["text"] for row in mapped], ["实际说的话"])
        self.assertEqual(mapped[0]["comp_in_ms"], 200)
        self.assertEqual(mapped[0]["comp_out_ms"], 1200)
        self.assertEqual((mapped[0]["f0"], mapped[0]["f1"]), timebase.frames_for_span(200, 1200, 30))
        self.assertEqual(timebase.frames_for_span(0, 6000, 30)[1], 180)
        self.assertEqual(timebase.frames_for_span(0, 6000, 25)[1], 150)
        self.assertEqual(timebase.frames_for_seconds(10 / 30, 30), 10)
        self.assertEqual(timebase.frames_for_seconds(10 / 30, 25), 8)
        self.assertNotEqual(timebase.frames_for_seconds(10 / 30, 25), 10)

    def test_speaker_track_conflict_is_unconfirmed(self):
        speaker, note = transcript.resolve_speaker(
            {"speaker": "guest", "track": "mic_host"}, {"mic_host": "interviewer_audio"})
        self.assertEqual((speaker, note), ("unknown", "待确认"))
        speaker, note = transcript.resolve_speaker({"text": "x"}, {})
        self.assertEqual(note, "待确认")

    def test_cache_key_changes_when_range_mask_or_size_changes(self):
        base = dict(input="abc", source_in_ms=0, source_out_ms=1000, engine="matanyone2", max_size=1080, mask="m1", keep_furniture="drop", warmup_ms=0)
        first = cache.cache_key(**base)
        self.assertIsNotNone(cache.lookup({first: {"key": first, "path": "a"}}, first))
        for change in ({"max_size": 720}, {"mask": "m2"}, {"source_out_ms": 1200}):
            other = cache.cache_key(**{**base, **change})
            self.assertNotEqual(first, other)
            self.assertIsNone(cache.lookup({first: {"key": first}}, other))

    def test_sync_checks_the_tail_and_does_not_stretch(self):
        import numpy as np
        rate=8000
        rng=np.random.default_rng(45)
        first=rng.normal(size=2*rate)
        last=rng.normal(size=2*rate)
        ref=np.concatenate([first,last])
        def delay(data,ms):
            offset=round(ms*rate/1000)
            return np.concatenate([np.zeros(offset),data])[:len(data)]
        drifted=sync.measure_buffers(ref,np.concatenate([delay(first,40),delay(last,120)]),rate)
        self.assertTrue(drifted["needs_human"])
        self.assertGreater(abs(drifted["tail_drift_ms"]),40)
        self.assertEqual(drifted["atempo"],1)
        stable=sync.measure_buffers(ref,np.concatenate([delay(first,40),delay(last,40)]),rate)
        self.assertTrue(stable["completed"])
        sparse=[0]*(rate*4)
        sparse[800]=30000
        self.assertTrue(sync.measure_buffers(sparse,sparse,rate)["needs_human"])

    def test_research_does_not_invent_or_publish_hidden_fields(self):
        pack = research.build_pack({"region": "待填", "background": "待填", "cases": [{
            "label": "样本", "price_kind": "list", "value": "待填", "public": False,
            "listing_ref": "INTERNAL", "phone": "13800000000", "screenshot": "secret.png",
        }]})
        self.assertEqual(pack["cards"], [])
        self.assertEqual(pack["questions"], [])
        self.assertIn("listing_ref", pack["hidden_dropped"])
        self.assertIn("phone", pack["hidden_dropped"])
        self.assertTrue(any("不推断" in line for line in pack["checklist"]))
        self.assertTrue(any("截图" in line for line in pack["checklist"]))
        shown = research.build_pack({"background": "已核对", "cases": [{
            "label": "样本", "price_kind": "transaction", "value": "3200", "unit": "元/月",
            "source": "门店成交表", "collected_on": "2026-10-01", "basis": "单套成交价", "public": True,
        }]})
        self.assertEqual(shown["cards"][0]["price_label"], "成交价")
        self.assertNotIn("listing_ref", shown["cards"][0])

    def test_layout_keeps_graphics_off_the_face(self):
        self.assertEqual(layout.check_layout(), [])

    def test_edit_requires_an_exclusive_source_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decisions.json"
            path.write_text('{"confirmed": true, "unit": "ms", "out_point": "exclusive", "segments": [{"id": "E01", "shot": "A", "layout": "question"}]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source_in_ms"):
                editlist.load_decisions(path)

    def test_matte_plan_resets_on_a_cut_and_carries_state_inside_a_chunked_shot(self):
        segments = [
            {"id": "E01", "source_id": "cam_a", "shot": "A", "layout": "question", "source_in_ms": 0, "source_out_ms": 1000},
            {"id": "E02", "source_id": "cam_a", "shot": "A", "layout": "name", "source_in_ms": 1000, "source_out_ms": 2000},
            {"id": "E03", "source_id": "cam_a", "shot": "B", "layout": "case", "source_in_ms": 0, "source_out_ms": 25000},
        ]
        planned = matte_plan.plan(segments, "finger", {"engine": "matanyone2", "max_size": 1080, "keep_furniture": "drop"})
        self.assertFalse(planned["executed"])
        self.assertTrue(planned["jobs"][0]["reset_matte"])
        self.assertFalse(planned["jobs"][1]["reset_matte"])
        long_jobs = [job for job in planned["jobs"] if job["segment_id"] == "E03"]
        self.assertGreater(len(long_jobs), 1)
        self.assertTrue(long_jobs[0]["reset_matte"])
        self.assertTrue(long_jobs[1]["carry_state"])
        self.assertGreater(long_jobs[1]["warmup_ms"], 0)
        self.assertFalse(long_jobs[1]["reset_matte"])
        blocked = matte_plan.furniture_status({"keep_furniture": "待填"})
        self.assertFalse(blocked["ready"])

    def test_resolve_handoff_rejects_a_long_png_sequence_and_a_size_mismatch(self):
        with self.assertRaisesRegex(ValueError, "PNG"):
            resolve_export.png_allowed(151)
        self.assertTrue(resolve_export.png_allowed(24))
        self.assertTrue(resolve_export.alignment(10, 10, 1920, 1080, 25, 1920, 1080, 25) == [])
        self.assertTrue(resolve_export.alignment(10, 9, 1920, 1080, 30, 1920, 1080, 25))
        document = resolve_export.handoff_document(Path("ep00-techtest"), None, False)
        self.assertFalse(document["completed"])
        self.assertEqual(document["alpha_mode"], "straight")
        self.assertIn("webm", " ".join(document["not_a_resolve_handoff"]).lower())
        self.assertFalse(document["magic_mask_required"])

    def test_probe_refuses_to_target_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp)
            target = ep / "footage" / "raw" / "cam_a.mp4"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"original")
            with self.assertRaisesRegex(ValueError, "raw"):
                probe.refuse_raw_write(ep, target)
            self.assertEqual(target.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
