"""Real media preparation, matting and handoff for interview episodes."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path
from pipeline.interview import avio, probe
from pipeline.common.media import materialize
from pipeline.common.color_restore import restored_for

REPO = Path(__file__).resolve().parents[2]
VERSION = "interview-media-v1"

def dump(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".pending")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temp.replace(path)

def read(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else default

def within(ep, value):
    ep = Path(ep).resolve()
    path = (ep / str(value)).resolve()
    if ep not in path.parents:
        raise ValueError("素材必须位于本期目录内: %s" % value)
    return path

def file_hash(path):
    return avio.sha256_file(path) if Path(path).is_file() else "missing"

def signature(ep, cfg):
    rows = []
    for item in probe.load_sources(ep):
        path = within(ep, item["path"])
        rows.append((item["id"], item["path"], file_hash(path)))
    for key in ("mask", "furniture_mask"):
        value = (cfg.get("matting") or {}).get(key)
        if value:
            rows.append((key, str(value), file_hash(within(ep, value))))
    for key in ("background_src", "graded_src"):
        value = (cfg.get("render") or {}).get(key)
        if value:
            rows.append((key, str(value), file_hash(within(ep, value))))
    payload = {
        "version": VERSION, "cfg": cfg, "sources": rows,
        "inputs": {name: file_hash(Path(ep) / name) for name in
                   ("edit/decisions.json", "transcript/corrected.json", "data/media_sources.json", "data/research_pack.json")},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def matte_key(ep, cfg, segment):
    mat = cfg.get("matting") or {}
    item = next((s for s in probe.load_sources(ep) if s["id"] == segment["source_id"]), None)
    if item is None:
        raise ValueError("未知 source_id: %s" % segment["source_id"])
    payload = {
        "version": VERSION, "implementation": file_hash(REPO / "scripts/matting/matte_local.py"),
        "source_id": item["id"], "source_sha": file_hash(within(ep, item["path"])),
        "in": segment["source_in_ms"], "out": segment["source_out_ms"],
        "matting": mat, "fps": cfg["render"]["fps"],
        "masks": {k: file_hash(within(ep, mat[k])) for k in ("mask", "furniture_mask") if mat.get(k)},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

def selected_audio(cfg):
    return list(cfg.get("audio_tracks") or [])

def sync_ready(ep, cfg):
    tracks = selected_audio(cfg)
    if not tracks:
        return {"completed": True, "needs_human": False, "status": "camera_embedded", "atempo": 1}
    confirmed = (cfg.get("sync") or {}).get("confirmed") is True
    return {"completed": confirmed, "needs_human": not confirmed,
            "status": "manual_confirmed" if confirmed else "needs_confirmation",
            "offsets_ms": (cfg.get("sync") or {}).get("offsets_ms") or {}, "atempo": 1}

def validate_inputs(ep, cfg, decisions, spans):
    errors = []
    sources = {row["id"]: row for row in probe.run_probe(ep, write=False)["items"]}
    if not decisions.get("confirmed") or not decisions.get("segments"):
        errors.append("需要已确认的非空剪辑清单")
    if not spans:
        errors.append("需要非空的实际转录")
    for row in sources.values():
        if row.get("required", True) and not row.get("completed"):
            errors.append("素材未通过 ffprobe: %s" % row["id"])
    if not sync_ready(ep, cfg)["completed"]:
        errors.append("独立音轨的同步偏移尚未确认")
    for seg in decisions.get("segments", []):
        item = sources.get(seg["source_id"])
        if not item or item.get("status") != "probed" or not item.get("width"):
            errors.append("无有效视频源: %s" % seg["source_id"])
            continue
        if seg["source_out_ms"] > (item.get("duration_ms") or 0) + 1:
            errors.append("剪辑超出原片: %s" % seg["id"])
        overlaps = [s for s in spans if (s.get("source_id") or seg["source_id"]) == seg["source_id"]
                    and s["source_in_ms"] < seg["source_out_ms"] and s["source_out_ms"] > seg["source_in_ms"]]
        if not overlaps:
            errors.append("采用段缺少实际字幕: %s" % seg["id"])
        for span in overlaps:
            if span["source_in_ms"] < seg["source_in_ms"] or span["source_out_ms"] > seg["source_out_ms"]:
                errors.append("剪辑切穿字幕分句，请在词边界拆分转录: %s" % seg["id"])
        if not selected_audio(cfg) and not item.get("has_audio"):
            errors.append("无原片音轨或独立录音: %s" % seg["id"])
    for track in selected_audio(cfg):
        ident = track.get("source_id")
        item = sources.get(ident)
        if not item or not item.get("completed") or not item.get("audio"):
            errors.append("无有效独立音轨: %s" % ident)
    return errors

def ff(args):
    avio.require_tools()
    return avio.run([avio.FFMPEG, "-nostdin", "-y", "-v", "error", *map(str, args)])

def clip_video(src, dst, start, end, fps, codec="rgb"):
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    final = dst
    dst = dst.with_name(dst.stem + ".pending" + dst.suffix)
    opts = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"] if codec == "alpha" else [
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p"]
    if codec == "webm":
        opts = ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", "24",
                "-b:v", "0", "-auto-alt-ref", "0", "-row-mt", "1"]
    ff(["-ss", "%.6f" % (start / 1000), "-i", src, "-t", "%.6f" % ((end-start)/1000),
        "-map", "0:v:0", "-an", "-vf", "fps=%d" % fps, *opts, dst])
    dst.replace(final)

def _track_clip(ep, cfg, source, seg, dst, duration):
    import numpy as np
    tracks = selected_audio(cfg) or [{"source_id": seg["source_id"], "gain": 1}]
    rate = 48000
    mix = np.zeros(round(duration * rate / 1000), dtype=np.float64)
    offsets = (cfg.get("sync") or {}).get("offsets_ms") or {}
    for track in tracks:
        ident = track["source_id"]
        src = within(ep, source[ident]["path"])
        # Positive offset: track content is late on its file clock; read later to align.
        offset = float(offsets.get(ident, 0))
        start = seg["source_in_ms"] + offset
        pad = max(0, round(-start * rate / 1000))
        data, _ = avio.decode_audio(src, start_ms=max(0, start),
                                  end_ms=max(0, start) + max(0, duration - pad * 1000/rate), rate=rate)
        count = min(len(data), max(0, len(mix)-pad))
        if count:
            mix[pad:pad+count] += data[:count] * float(track.get("gain", 1))
    avio.make_wav(dst, mix, rate)

def prepare(ep, cfg, decisions, spans):
    errors = validate_inputs(ep, cfg, decisions, spans)
    if errors:
        raise ValueError("; ".join(errors))
    ep = Path(ep)
    sig = signature(ep, cfg)
    old = read(ep / "data/media_manifest.json", {})
    if old.get("signature") == sig and old.get("clips") and all(
        within(ep, v).is_file() and file_hash(within(ep, v)) == h
        for v, h in old.get("output_hashes", {}).items()
    ) and len(old.get("output_hashes", {})) >= len(old["clips"]) + 1:
        return old
    fps = cfg["render"]["fps"]
    mode = cfg["render"]["background"]
    source = {x["id"]: x for x in probe.load_sources(ep)}
    clips, waves = [], []
    import numpy as np
    for seg in decisions["segments"]:
        dst = ep / "public/media" / (seg["id"] + ".mp4")
        graded = (cfg.get("render") or {}).get("graded_src")
        src = within(ep, graded) if graded else restored_for(ep, within(ep, source[seg["source_id"]]["path"]), "render")
        cursor = sum(c["source_out_ms"]-c["source_in_ms"] for c in clips)
        clip_video(src, dst, cursor if graded else seg["source_in_ms"], (cursor+seg["source_out_ms"]-seg["source_in_ms"]) if graded else seg["source_out_ms"], fps)
        duration = seg["source_out_ms"] - seg["source_in_ms"]
        wav = ep / "work/audio" / (seg["id"] + ".wav")
        _track_clip(ep, cfg, source, seg, wav, duration)
        sound, rate = avio.decode_audio(wav, rate=48000)
        waves.append(sound)
        row = {"id": seg["id"], "video_src": dst.relative_to(ep / "public").as_posix(),
               "source_id": seg["source_id"], "source_in_ms": seg["source_in_ms"],
               "source_out_ms": seg["source_out_ms"], "frames": round(duration * fps / 1000)}
        if mode == "virtual":
            entry = read(ep / "matte/index.json", {}).get(seg["id"])
            if not entry or entry.get("key") != matte_key(ep, cfg, seg):
                raise ValueError("缺少有效抠像或缓存已过期: %s" % seg["id"])
            fg = within(ep, entry["webm"])
            master = within(ep, entry["rgba"])
            if not fg.is_file() or not master.is_file() or file_hash(master) != entry["rgba_sha"]:
                raise ValueError("透明视频不存在或内容已变化: %s" % seg["id"])
            public_fg = ep / "public/matte" / (seg["id"] + "-" + entry["key"][:16] + ".webm")
            public_fg.parent.mkdir(parents=True, exist_ok=True)
            materialize(fg, public_fg)
            row.update({"foreground_src": public_fg.relative_to(ep / "public").as_posix(),
                        "matte_key": entry["key"], "rgba": entry["rgba"]})
        clips.append(row)
    mix_path = ep / "public/audio/program.wav"
    avio.make_wav(mix_path, np.concatenate(waves), 48000)
    media = {"signature": sig, "completed": True, "clips": clips,
             "audio": {"src": "audio/program.wav", "role": "program_audio"}, "mode": mode,
             "sync": sync_ready(ep, cfg)}
    paths = [ep / "public/audio/program.wav"]
    for clip in clips:
        paths.append(ep / "public" / clip["video_src"])
        if clip.get("foreground_src"):
            paths.append(ep / "public" / clip["foreground_src"])
    media["output_hashes"] = {p.relative_to(ep).as_posix(): file_hash(p) for p in paths}
    dump(ep / "data/media_manifest.json", media)
    return media

def _run_matte_ranges(ep, cfg, decisions):
    ep = Path(ep)
    mat = cfg.get("matting") or {}
    fps = cfg["render"]["fps"]
    index = read(ep / "matte/index.json", {})
    source = {r["id"]: r for r in probe.load_sources(ep)}
    for seg in decisions["segments"]:
        key = matte_key(ep, cfg, seg)
        old = index.get(seg["id"], {})
        if old.get("key") == key and all(within(ep, old.get(k, "missing")).is_file() for k in ("rgba", "webm")):
            if file_hash(within(ep, old["rgba"])) == old.get("rgba_sha"):
                continue
        item = source[seg["source_id"]]
        src = restored_for(ep, within(ep, item["path"]), "matte")   # D-Log M -> 10-bit ProRes master
        info = avio.probe(src)
        if not info["valid"] or not info["video"] or seg["source_out_ms"] > info["duration_ms"]:
            raise ValueError("无效视频或区间: %s" % seg["id"])
        start = max(0, seg["source_in_ms"] - 1000)
        end = min(info["duration_ms"], seg["source_out_ms"] + 500)
        job = ep / "matte/jobs" / key[:20]
        job.mkdir(parents=True, exist_ok=True)
        cut = job / "input.mp4"
        clip_video(src, cut, start, end, fps)
        py = REPO / "vendor/cosyvoice/.venv/Scripts/python.exe"
        cmd = [str(py), str(REPO / "scripts/matting/matte_local.py"), str(cut),
               "--out", str(job), "--max-size", str(mat.get("max_size", 1080)),
               "--engine", str(mat.get("engine", "matanyone2"))]
        if mat.get("mask"):
            cmd += ["--mask", str(within(ep, mat["mask"]))]
        if mat.get("no_fallback"):
            cmd += ["--no-fallback"]
        log = job / "inference.log"
        with log.open("w", encoding="utf-8") as out:
            result = subprocess.run(cmd, cwd=REPO, stdout=out, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError("抠像失败 exit=%d，见 %s" % (result.returncode, log))
        report = read(job / "input_report.json", {})
        master = job / "input_rgba.mov"
        if not master.is_file() or not report.get("frames"):
            raise ValueError("抠像没有产生有效报告或透明母版")
        rgba, webm = job / "selected_rgba.mov", job / "selected_alpha.webm"
        local_in, local_out = seg["source_in_ms"] - start, seg["source_out_ms"] - start
        clip_video(master, rgba, local_in, local_out, fps, "alpha")
        # Fixed-camera furniture is a separate, explicit static mask.
        if mat.get("keep_furniture") == "keep":
            mask = within(ep, mat.get("furniture_mask", "missing"))
            if not mask.is_file():
                raise ValueError("保留家具需要本期辅助遮罩")
            combined = job / "furniture_rgba.mov"
            ff(["-i", rgba, "-loop", "1", "-i", mask, "-filter_complex",
                "[0:v]split[r][a];[a]alphaextract[a0];[1:v]format=gray[m];"
                "[a0][m]blend=all_mode=lighten:shortest=1[alpha];[r][alpha]alphamerge[v]",
                "-map", "[v]", "-an", "-shortest", "-c:v", "prores_ks",
                "-profile:v", "4444", "-pix_fmt", "yuva444p10le", combined])
            combined.replace(rgba)
        clip_video(rgba, webm, 0, seg["source_out_ms"]-seg["source_in_ms"], fps, "webm")
        expected = round((seg["source_out_ms"]-seg["source_in_ms"]) * fps / 1000)
        if avio.count_frames(rgba) != expected or avio.count_frames(webm) != expected:
            raise ValueError("RGB/alpha 帧数不匹配")
        index[seg["id"]] = {"key": key, "rgba": rgba.relative_to(ep).as_posix(),
                            "webm": webm.relative_to(ep).as_posix(), "rgba_sha": file_hash(rgba),
                            "report": report, "frames": expected,
                            "warmup_ms": seg["source_in_ms"]-start}
        dump(ep / "matte/index.json", index)
    return index

def run_matte(ep, cfg, decisions):
    """Process contiguous shots once, then cut RGB and alpha on the same boundaries."""
    ep = Path(ep)
    groups = []
    for seg in decisions["segments"]:
        if groups and groups[-1][-1]["source_id"] == seg["source_id"] and groups[-1][-1]["shot"] == seg["shot"] and groups[-1][-1]["source_out_ms"] == seg["source_in_ms"]:
            groups[-1].append(seg)
        else:
            groups.append([seg])
    fps = cfg["render"]["fps"]
    for number, group in enumerate(groups):
        index = read(ep / "matte/index.json", {})
        if all(index.get(seg["id"], {}).get("key") == matte_key(ep, cfg, seg)
               and file_hash(within(ep, index[seg["id"]]["rgba"])) == index[seg["id"]].get("rgba_sha")
               and within(ep, index[seg["id"]]["webm"]).is_file() for seg in group):
            continue
        joined = dict(group[0], id="__shot%d" % number, source_out_ms=group[-1]["source_out_ms"])
        index = _run_matte_ranges(ep, cfg, {"segments": [joined]})
        base = index[joined["id"]]
        master = within(ep, base["rgba"])
        for seg in group:
            key = matte_key(ep, cfg, seg)
            folder = ep / "matte/selected" / key[:20]
            folder.mkdir(parents=True, exist_ok=True)
            rgba, webm = folder / "selected_rgba.mov", folder / "selected_alpha.webm"
            start = seg["source_in_ms"] - joined["source_in_ms"]
            end = seg["source_out_ms"] - joined["source_in_ms"]
            clip_video(master, rgba, start, end, fps, "alpha")
            clip_video(rgba, webm, 0, end-start, fps, "webm")
            count = avio.count_frames(rgba)
            if count != avio.count_frames(webm):
                raise ValueError("分段 RGB/alpha 帧数不一致")
            index[seg["id"]] = {"key": key, "rgba": rgba.relative_to(ep).as_posix(),
                                "webm": webm.relative_to(ep).as_posix(), "rgba_sha": file_hash(rgba),
                                "report": base["report"], "frames": count, "shot_group": joined["id"]}
        dump(ep / "matte/index.json", index)
    return {seg["id"]: index[seg["id"]] for seg in decisions["segments"]}

def validation_errors(ep, cfg, timeline):
    from pipeline.interview.editlist import load_decisions
    from pipeline.interview.transcript import load_corrected
    errors = []
    try:
        decisions = load_decisions(Path(ep) / "edit/decisions.json")
        spans = load_corrected(Path(ep) / "transcript/corrected.json")["spans"]
        errors += validate_inputs(ep, cfg, decisions, spans)
        if timeline.get("signature") != signature(ep, cfg):
            errors.append("时间线指纹已过期，请重新 compose")
        mode = cfg["render"]["background"]
        if timeline.get("background") != mode or mode == "placeholder":
            errors.append("实际制作必须使用 live 或 virtual，背景配置须与时间线一致")
        manifest = read(Path(ep) / "data/media_manifest.json", {})
        if manifest.get("signature") != timeline.get("signature") or not manifest.get("completed"):
            errors.append("缺少当前媒体合成清单")
        actual = timeline.get("segments") or []
        if len(actual) != len(decisions["segments"]):
            errors.append("时间线剪辑数量不匹配")
        for seg in actual:
            path = within(ep, "public/" + str(seg.get("video_src", "missing")))
            info = avio.probe(path)
            if not info["valid"] or not info["video"]:
                errors.append("实际视频无效: %s" % seg["id"])
            if mode == "virtual":
                item = read(Path(ep) / "matte/index.json", {}).get(seg["id"], {})
                if not item or item.get("key") != matte_key(ep, cfg, seg):
                    errors.append("透明遮罩缺失或已过期: %s" % seg["id"])
                elif file_hash(within(ep, item["rgba"])) != item.get("rgba_sha"):
                    errors.append("透明母版内容改变: %s" % seg["id"])
        audio = timeline.get("audio") or {}
        sound = within(ep, "public/" + str(audio.get("src", "missing")))
        if not avio.has_real_audio(sound)[0]:
            errors.append("实际输出音轨缺失或无声")
        for rel, sha in manifest.get("output_hashes", {}).items():
            if file_hash(within(ep, rel)) != sha:
                errors.append("生成媒体内容已改变: %s" % rel)
        if not timeline.get("captions"):
            errors.append("时间线没有字幕")
    except (KeyError, OSError, ValueError, avio.AVError) as exc:
        errors.append(str(exc))
    return list(dict.fromkeys(errors))

def export_resolve(ep, cfg):
    ep = Path(ep)
    tl = read(ep / "data/timeline.json", {})
    problems = validation_errors(ep, cfg, tl)
    if problems:
        raise ValueError("; ".join(problems))
    dest = ep / "out/drafts/resolve"
    dest.mkdir(parents=True, exist_ok=True)
    items = []
    for seg in tl["segments"]:
        clip = within(ep, "public/" + seg["video_src"])
        target = dest / (seg["id"] + "_rgb.mp4")
        materialize(clip, target)
        row = {"id": seg["id"], "rgb": target.name, "f0": seg["f0"], "f1": seg["f1"],
               "frames": avio.count_frames(target), "start_ms": 0}
        if seg.get("rgba"):
            master = within(ep, seg["rgba"])
            rgba = dest / (seg["id"] + "_rgba.mov")
            materialize(master, rgba)
            mask = dest / (seg["id"] + "_mask.mp4")
            ff(["-i", rgba, "-vf", "alphaextract", "-an", "-c:v", "libx264", "-crf", "0", mask])
            if avio.count_frames(rgba) != row["frames"] or avio.count_frames(mask) != row["frames"]:
                raise ValueError("交接文件帧数不一致")
            row.update({"rgba": rgba.name, "mask": mask.name, "alpha_mode": "straight"})
        items.append(row)
    sound = dest / "program.wav"
    materialize(within(ep, "public/" + tl["audio"]["src"]), sound)
    from pipeline.interview.resolve_export import find_resolve
    result = {"completed": True, "export_status": "exported", "files": items, "audio": sound.name,
              "fps": tl["fps"], "signature": tl["signature"], "alpha_mode": "straight",
              "davinci_gui_import": "pending_manual" if find_resolve() else "pending_not_installed",
              "return_path": "edit/graded/<file>.mp4; set render.graded_src then compose"}
    dump(dest / "handoff.json", result)
    return result
