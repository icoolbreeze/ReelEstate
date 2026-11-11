"""Integration checks use small real files, never GPU or external services."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from pipeline.interview import production, avio, timeline, editlist, transcript, check_episode, sync

class MediaTests(unittest.TestCase):
    def setUp(self):
        root=production.REPO/"tmp"
        root.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix="interview-check-",dir=root)
        self.ep=Path(self.tmp.name)
        for name in ("data","edit","transcript","footage/raw","matte"):
            (self.ep/name).mkdir(parents=True,exist_ok=True)
        src=self.ep/"footage/raw/cam.mp4"
        production.ff(["-f","lavfi","-i","testsrc2=size=160x90:rate=25",
                       "-f","lavfi","-i","sine=frequency=997:sample_rate=48000",
                       "-t","1","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",src])
        self.cfg={"series":"interview","purpose":"production","technical_test":False,
                  "render":{"fps":25,"width":1920,"height":1080,"background":"live"},
                  "matting":{"engine":"matanyone2","max_size":1080,"keep_furniture":"drop"},
                  "guest":{"display_name":"fixture","consent":"confirmed"},"sync":{}}
        production.dump(self.ep/"data/media_sources.json",[{"id":"cam_a","role":"host_camera","path":"footage/raw/cam.mp4","required":True}])
        production.dump(self.ep/"edit/decisions.json",{"confirmed":True,"unit":"ms","out_point":"exclusive","segments":[
            {"id":"E01","source_id":"cam_a","shot":"A","layout":"name","source_in_ms":0,"source_out_ms":400},
            {"id":"E02","source_id":"cam_a","shot":"A","layout":"case","source_in_ms":400,"source_out_ms":1000}]})
        production.dump(self.ep/"transcript/corrected.json",{"fixture":False,"spans":[
            {"source_id":"cam_a","speaker":"guest","text":"技术验证一","source_in_ms":40,"source_out_ms":360},
            {"source_id":"cam_a","speaker":"guest","text":"技术验证二","source_in_ms":440,"source_out_ms":960}]})

    def tearDown(self):
        self.tmp.cleanup()

    def compose(self):
        d=editlist.load_decisions(self.ep/"edit/decisions.json")
        t=transcript.load_corrected(self.ep/"transcript/corrected.json")
        return timeline.write_timeline(self.ep,self.cfg,d,t["spans"],{})

    def test_real_media_roundtrip_and_handoff(self):
        tl=self.compose()
        self.assertEqual(tl["total"],25)
        self.assertTrue(all(row.get("video_src") for row in tl["segments"]))
        self.assertTrue(check_episode.report(self.ep,self.cfg,False)["pass"])
        handoff=production.export_resolve(self.ep,self.cfg)
        self.assertTrue(handoff["completed"])
        self.assertEqual([r["frames"] for r in handoff["files"]],[10,15])
        self.assertTrue((self.ep/"out/drafts/resolve/program.wav").is_file())

    def test_invalid_source_and_empty_transcript_block_final(self):
        self.compose()
        (self.ep/"footage/raw/cam.mp4").write_bytes(b"invalid")
        self.assertFalse(check_episode.report(self.ep,self.cfg,False)["pass"])
        production.dump(self.ep/"transcript/corrected.json",{"fixture":False,"spans":[]})
        self.assertFalse(check_episode.report(self.ep,self.cfg,False)["pass"])

    def test_missing_virtual_alpha_and_stale_output_block(self):
        self.compose()
        self.cfg["render"]["background"]="virtual"
        with self.assertRaisesRegex(ValueError,"抠像"):
            self.compose()
        self.assertFalse(check_episode.report(self.ep,self.cfg,False)["pass"])
        self.cfg["render"]["background"]="live"
        self.compose()
        (self.ep/"public/audio/program.wav").write_bytes(b"broken")
        self.assertFalse(check_episode.report(self.ep,self.cfg,False)["pass"])

    def test_distinct_sources_masks_and_ranges_have_distinct_keys(self):
        d=editlist.load_decisions(self.ep/"edit/decisions.json")["segments"][0]
        first=production.matte_key(self.ep,self.cfg,d)
        rows=production.read(self.ep/"data/media_sources.json")
        production.dump(self.ep/"data/media_sources.json",rows+[dict(rows[0],id="cam_b")])
        self.assertNotEqual(first,production.matte_key(self.ep,self.cfg,dict(d,source_id="cam_b")))
        mask=self.ep/"matte/seed.png"
        mask.write_bytes(b"one")
        self.cfg["matting"]["mask"]="matte/seed.png"
        a=production.matte_key(self.ep,self.cfg,d)
        mask.write_bytes(b"two")
        self.assertNotEqual(a,production.matte_key(self.ep,self.cfg,d))
        self.assertNotEqual(first,production.matte_key(self.ep,self.cfg,dict(d,source_out_ms=800)))

    def test_independent_tracks_require_confirmation(self):
        self.cfg["audio_tracks"]=[{"source_id":"cam_a"}]
        with self.assertRaisesRegex(ValueError,"同步"):
            self.compose()
        self.cfg["sync"]={"confirmed":True,"offsets_ms":{"cam_a":0}}
        self.compose()
        self.assertTrue(check_episode.report(self.ep,self.cfg,False)["pass"])

    def test_alignment_rejects_unrelated_audio(self):
        rng=np.random.default_rng(56)
        a=rng.normal(size=32000)
        b=rng.normal(size=32000)
        self.assertTrue(sync.measure_buffers(a,b,8000)["needs_human"])
        delayed=np.concatenate([np.zeros(640),a])[:len(a)]
        measured=sync.measure_buffers(a,delayed,8000)
        self.assertTrue(measured["completed"])
        self.assertEqual(measured["head_offset_ms"],80)
        self.assertEqual(measured["atempo"],1)

    def test_virtual_clips_with_same_basename_stay_distinct(self):
        self.cfg["render"]["background"] = "virtual"
        self.cfg["render"]["studio"] = {"match_status": "reference_matched_preview", "foreground": {"x": 440, "y": 40, "w": 1920, "h": 1080}}
        decisions = editlist.load_decisions(self.ep / "edit/decisions.json")
        index = {}
        for segment, color in zip(decisions["segments"], ("red", "blue")):
            folder = self.ep / "matte" / segment["id"]
            folder.mkdir()
            rgba = folder / "selected_rgba.mov"
            webm = folder / "selected_alpha.webm"
            duration = (segment["source_out_ms"] - segment["source_in_ms"]) / 1000
            production.ff(["-f", "lavfi", "-i", "color=c=%s:s=32x32:r=25" % color, "-t", str(duration),
                           "-vf", "format=yuva444p10le", "-c:v", "prores_ks", "-profile:v", "4444", rgba])
            production.clip_video(rgba, webm, 0, duration * 1000, 25, "webm")
            index[segment["id"]] = {"key": production.matte_key(self.ep, self.cfg, segment),
                "rgba": rgba.relative_to(self.ep).as_posix(), "webm": webm.relative_to(self.ep).as_posix(),
                "rgba_sha": production.file_hash(rgba)}
        production.dump(self.ep / "matte/index.json", index)
        tl = self.compose()
        paths = [row["foreground_src"] for row in tl["segments"]]
        self.assertEqual(len(set(paths)), 2)
        for segment, path in zip(decisions["segments"], paths):
            self.assertEqual(production.file_hash(self.ep / "public" / path),
                             production.file_hash(self.ep / index[segment["id"]]["webm"]))
        self.assertEqual(tl["studio"], self.cfg["render"]["studio"])
        self.assertEqual(tl["background_match"], "reference_matched_preview")

if __name__=="__main__":
    unittest.main()
