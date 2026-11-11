"""DJI Osmo Pocket 3 D-Log M detection and automatic Rec.709 restore.

Usage (via npm / video.py):
    npm run restore -- projects/listing/<episode> [--style Spring] [--dry-run] [--force]
        [--assume dlogm|rec709] [--encoder prores|x264|nvenc|auto] [--proxy] [--only <name> ...]
    npm run restore -- --scan D:\\DCIM\\DJI_001          (read-only classification of any folder)

Reads footage/raw/ (never modified), classifies every clip as dlogm / rec709 / unknown,
writes the 10-bit ProRes 422 HQ master to footage/restored/master/<name>_r709.mov (default),
the 8-bit H.264 render proxy to footage/restored/proxy/<name>_r709.mp4
(+ <name>_r709_<Style>.*) and footage/restored/color_report.json.

Detection. Calibrated 2026-10-28 on 129 real Pocket 3 clips (1080p29.97) + 26 ep02 phone clips;
still provisional for other resolutions / frame rates / firmware.
 1. Metadata (ffprobe). Pocket 3 facts: format tag encoder="DJI OsmoPocket3"; D-Log M is 10-bit
    HEVC (Main 10) tagged BT.709 (the tag alone proves nothing); HLG is tagged BT.2020 /
    arib-std-b67; Normal is 8-bit per DJI spec. DJI files carry a "DJI dbgi" data stream whose
    first packet names the sensor template, e.g. TPLG_IMX989_VIDEO_1080P_2997_HDR_10BIT.
    - our restore marker or *_r709 name          -> rec709 (already restored, skip)
    - HLG / PQ transfer                          -> unknown (HDR; the D-Log M LUT does not apply)
    - 8-bit                                      -> rec709 (Pocket 3 cannot record D-Log M in 8-bit)
    - 10-bit, DJI template ends with _10BIT      -> dlogm (118/129 real clips, all looked log)
    - 10-bit, DJI template without _10BIT        -> unknown, likely Normal-type processing
                                                    (template HDR / LOWLIGHT: deep blacks below
                                                    legal 16, higher saturation), review
    - 10-bit, no DJI template                    -> pixels decide
 2. Pixels: SAMPLE_FRAMES frames, downscaled, ffmpeg signalstats on an 8-bit limited-range scale.
    Real D-Log M: darkest pixel 14-49 (median 24), median SATAVG 0.8-12.9 (median 4.5).
    "Normal-like" DJI clips: darkest pixel 4-15. Phone Rec.709 (ep02): darkest 14-32, SATAVG
    4-18. Highlights and luma spread do NOT separate D-Log M (it reaches 255), so they are
    reported but not scored.
 Unknown clips are never converted unless --assume dlogm is given.
"""
import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LUT_DIR = REPO / "assets/luts/pocket3"
RESTORE_LUT = LUT_DIR / "restore/DJI OSMO Pocket 3 D-Log M to Rec.709 V1.cube"
STYLES = ("Spring", "Summer", "Autumn", "Winter")
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".mts"}   # DJI .LRF proxies are ignored
MARKER = "reelestate-color=restored-dlogm-r709"

SAMPLE_FRAMES = 5
# 8-bit limited-range scale (Y 16..235, SATAVG 0..~180). See calibration notes above.
TH = {
    "black_floor_min": 17,   # darkest pixel over all samples >= this -> lifted blacks (log)
    "sat_max": 8,            # median SATAVG <= this -> desaturated
}
WEIGHTS = {"black": 0.5, "sat": 0.5}
DLOGM_SCORE = 1.0            # 10-bit clip without DJI template: BOTH votes required -> dlogm
PROVISIONAL = True
HDR_TRC = {"arib-std-b67", "smpte2084"}


def _run(cmd, cwd=None):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=cwd)


def probe(path):
    r = _run(["ffprobe", "-v", "error", "-show_entries",
              "stream=index,codec_type,codec_name,profile,pix_fmt,r_frame_rate,width,height,color_range,color_space,"
              "color_transfer,color_primaries,bits_per_raw_sample:stream_tags:format=duration:format_tags",
              "-of", "json", str(path)])
    if r.returncode:
        raise ValueError("ffprobe failed: %s" % r.stderr.strip()[:300])
    data = json.loads(r.stdout or "{}")
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("no video stream")
    audio = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    tags = {}
    for k, v in (data.get("format", {}).get("tags") or {}).items():
        tags["format." + k] = v
    for st in data.get("streams", []):
        for k, v in (st.get("tags") or {}).items():
            tags["stream%s.%s" % (st.get("index"), k)] = v
    pix = video.get("pix_fmt", "")
    bits = 10 if re.search(r"10|p010|12", pix) else 8
    try:
        duration = float(data.get("format", {}).get("duration") or 0)
    except ValueError:
        duration = 0.0
    template = None
    dbgi = next((s for s in data.get("streams", []) if (s.get("tags") or {}).get("handler_name") == "DJI dbgi"), None)
    if dbgi is not None:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:%d" % dbgi["index"],
                              "-frames:d", "1", "-c", "copy", "-f", "data", "-"], capture_output=True).stdout
        found = re.findall(rb"TPLG_[A-Za-z0-9_]+", raw[:65536])
        template = found[0].decode() if found else None
    return {"dji_template": template, "codec": video.get("codec_name"), "pix_fmt": pix, "bits": bits,
            "width": video.get("width"), "height": video.get("height"),
            "color_range": video.get("color_range"), "color_space": video.get("color_space"),
            "color_transfer": video.get("color_transfer"),
            "color_primaries": video.get("color_primaries"),
            "duration": duration, "audio_codecs": [a.get("codec_name") for a in audio], "tags": tags}


def is_dji(meta):
    return any("dji" in str(v).lower() for v in meta["tags"].values())


def frame_stats(path, t, full_range):
    vf = "scale=320:-2,format=yuv420p,signalstats,metadata=mode=print"
    r = _run(["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "info", "-ss", "%.3f" % t,
              "-i", str(path), "-map", "0:v:0", "-frames:v", "1", "-an", "-vf", vf, "-f", "null", "-"])
    vals = dict(re.findall(r"lavfi\.signalstats\.(\w+)=([\d.]+)", r.stderr))
    if not vals:
        return None
    out = {k: float(vals[k]) for k in ("YMIN", "YLOW", "YAVG", "YHIGH", "YMAX", "SATAVG", "SATHIGH") if k in vals}
    if full_range:  # map full-range codes to limited-range scale so thresholds stay comparable
        for k in ("YMIN", "YLOW", "YAVG", "YHIGH", "YMAX"):
            if k in out:
                out[k] = 16 + out[k] * 219 / 255
    return out


def pixel_metrics(path, meta, n=SAMPLE_FRAMES):
    d = meta["duration"]
    times = [d * (i + 1) / (n + 1) for i in range(n)] if d > 1 else [0.0]
    full = meta.get("color_range") == "pc"
    frames = [f for f in (frame_stats(path, t, full) for t in times) if f]
    if not frames:
        return None
    m = {
        "frames": len(frames),
        "black_floor": min(f["YMIN"] for f in frames),
        "white_peak": max(f["YMAX"] for f in frames),
        "spread": statistics.median(f["YHIGH"] - f["YLOW"] for f in frames),
        "sat": statistics.median(f["SATAVG"] for f in frames),
        "yavg": statistics.median(f["YAVG"] for f in frames),
    }
    votes = {
        "black": m["black_floor"] >= TH["black_floor_min"],
        "sat": m["sat"] <= TH["sat_max"],
    }
    m["votes"] = votes
    m["log_score"] = round(sum(WEIGHTS[k] for k, v in votes.items() if v), 3)
    for k in ("black_floor", "white_peak", "spread", "sat", "yavg"):
        m[k] = round(m[k], 1)
    return m


def classify(path):
    path = Path(path)
    meta = probe(path)
    reasons = []
    base = {"metadata": meta}
    comment = " ".join(str(v) for v in meta["tags"].values())
    if MARKER in comment or re.search(r"_r709(_(%s))?$" % "|".join(STYLES), path.stem, re.I):
        return {**base, "class": "rec709", "confidence": 0.99, "already_restored": True,
                "reasons": ["restore marker / _r709 name: already restored"], "metrics": None}
    if (meta.get("color_transfer") or "") in HDR_TRC:
        return {**base, "class": "unknown", "confidence": 0.9, "hdr": True,
                "reasons": ["HDR transfer %s (HLG/PQ): not D-Log M, restore LUT does not apply" % meta["color_transfer"]],
                "metrics": None}
    dji = is_dji(meta) or path.name.upper().startswith("DJI_")
    meta["dji"] = dji
    reasons.append("%s%d-bit %s, transfer=%s" % ("DJI, " if dji else "", meta["bits"], meta["codec"], meta.get("color_transfer")))
    metrics = pixel_metrics(path, meta)
    score = metrics["log_score"] if metrics else None
    if metrics:
        reasons.append("log_score %.2f (votes: %s)" % (score, ", ".join(k for k, v in metrics["votes"].items() if v) or "none"))
    else:
        reasons.append("could not sample frames")
    if meta["bits"] == 8:
        reasons.append("Pocket 3 D-Log M is always 10-bit -> 8-bit clip is normal colour")
        conf = 0.95 if dji else 0.85
        return {**base, "class": "rec709", "confidence": conf, "reasons": reasons, "metrics": metrics}
    tpl = meta.get("dji_template")
    if tpl:
        reasons.append("DJI sensor template " + tpl)
        if tpl.endswith("_10BIT"):
            conf = 0.95 if (score is None or score >= DLOGM_SCORE) else 0.8
            return {**base, "class": "dlogm", "confidence": conf, "reasons": reasons, "metrics": metrics}
        reasons.append("template without _10BIT: on the test card these were Normal-looking (deep blacks), review")
        return {**base, "class": "unknown", "confidence": 0.5, "suspect_normal": True, "reasons": reasons, "metrics": metrics}
    if score is None:
        return {**base, "class": "unknown", "confidence": 0.0, "reasons": reasons, "metrics": None}
    if score >= DLOGM_SCORE:
        conf = 0.75 + (0.1 if dji else 0)
        return {**base, "class": "dlogm", "confidence": conf, "reasons": reasons, "metrics": metrics}
    reasons.append("10-bit but not both lifted blacks and low saturation, review")
    return {**base, "class": "unknown", "confidence": 0.3, "reasons": reasons, "metrics": metrics}


def style_lut(name):
    match = [p for p in (LUT_DIR / "style").glob("*.cube") if name.lower() in p.stem.lower()]
    if len(match) != 1:
        raise ValueError("style LUT not found (one of %s): %s" % ("/".join(STYLES), name))
    return match[0]


def nvenc_ok():
    r = _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
              "color=black:s=256x256:d=0.1", "-c:v", "h264_nvenc", "-f", "null", "-"])
    return r.returncode == 0


ENCODERS = {
    # default: 10-bit 4:2:2 ProRes 422 HQ intermediate for DaVinci Resolve (free) fine grading
    "prores": {"ext": ".mov", "pix": "yuv422p10le",
               "v": ["-c:v", "prores_ks", "-profile:v", "3", "-vendor", "apl0", "-bits_per_mb", "8000"],
               "a": ["-c:a", "pcm_s16le"]},
    # 8-bit H.264 proxies (Remotion / Chrome cannot decode ProRes)
    "x264": {"ext": ".mp4", "pix": "yuv420p", "v": ["-c:v", "libx264", "-preset", "medium", "-crf", "16"], "a": None},
    "nvenc": {"ext": ".mp4", "pix": "yuv420p",
              "v": ["-c:v", "h264_nvenc", "-preset", "p7", "-rc", "vbr", "-cq", "17", "-b:v", "0"], "a": None},
}


def convert(src, dst, luts, meta, encoder="prores"):
    """Apply LUT chain with ffmpeg lut3d in 16-bit RGB (no 8-bit intermediate).
    LUTs are copied to a no-space temp dir and referenced relatively (cwd), which avoids
    Windows drive-colon and space escaping in filter strings."""
    enc = ENCODERS[encoder]
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = dst.with_name(".%s.tmp%s" % (dst.stem, dst.suffix))
    in_range = "pc" if meta.get("color_range") == "pc" else "tv"
    with tempfile.TemporaryDirectory(prefix="reel_lut_") as td:
        names = []
        for i, lut in enumerate(luts):
            name = "lut%d.cube" % i
            shutil.copyfile(lut, Path(td) / name)
            names.append(name)
        chain = ",".join("lut3d=file=%s:interp=tetrahedral" % n for n in names)
        vf = ("scale=in_color_matrix=bt709:in_range=%s,format=gbrp16le,%s,"
              "scale=out_color_matrix=bt709:out_range=tv,format=%s,"
              "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv" % (in_range, chain, enc["pix"]))
        acodecs = meta.get("audio_codecs") or []
        if not acodecs:
            aenc = []
        elif enc["a"]:
            aenc = enc["a"]
        else:
            aenc = ["-c:a", "copy"] if acodecs[0] == "aac" else ["-c:a", "aac", "-b:a", "256k"]
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(Path(src).resolve()),
               "-map", "0:v:0", "-map", "0:a:0?", "-vf", vf, *enc["v"], *aenc,
               "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
               "-map_metadata", "0", "-metadata", "comment=" + MARKER,
               *(["-movflags", "+faststart"] if enc["ext"] == ".mp4" else []), str(tmp_out.resolve())]
        r = _run(cmd, cwd=td)
    if r.returncode:
        tmp_out.unlink(missing_ok=True)
        raise ValueError("ffmpeg failed: %s" % r.stderr.strip()[-400:])
    os.replace(tmp_out, dst)


def up_to_date(dst, deps):
    dst = Path(dst)
    return dst.is_file() and all(dst.stat().st_mtime >= Path(d).stat().st_mtime for d in deps)


def configured_style(ep):
    try:
        from pipeline.common.voice_config import read_yaml
        cfg = read_yaml(Path(ep) / "episode.yaml")
    except Exception:
        return None
    color = cfg.get("color") or {}
    return (color.get("style") if isinstance(color, dict) else None) or cfg.get("color_style")


# Camera-source folders inside an episode: (kind, folder, always_dlogm)
SOURCE_DIRS = (("raw", "footage/raw", False), ("selects", "footage/selects_dlogm", True))
RESTORED_DIR = "footage/restored"
MASTER_DIR = RESTORED_DIR + "/master"     # 10-bit ProRes .mov (grade / matte)
PROXY_DIR = RESTORED_DIR + "/proxy"       # 8-bit H.264 .mp4 (Remotion render)
REPORT = RESTORED_DIR + "/color_report.json"


def restored_dir(ep, ext):
    """footage/restored/master for .mov masters, footage/restored/proxy for .mp4 proxies."""
    return Path(ep) / (MASTER_DIR if ext.lower() == ".mov" else PROXY_DIR)
_PROXY = []


def proxy_encoder():
    if not _PROXY:
        _PROXY.append("nvenc" if nvenc_ok() else "x264")
    return _PROXY[0]


def list_clips(root):
    root = Path(root)
    if root.is_file():
        return [root]
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXT
                  and not p.name.startswith("."))


def out_stem(kind, rel):
    stem = Path(rel).with_suffix("").as_posix().replace("/", "__")
    return stem if kind == "raw" else kind + "__" + stem


def required_outputs(ep, kind, rel):
    """Every D-Log M source needs the 10-bit ProRes master and the 8-bit H.264 proxy."""
    name = out_stem(kind, rel) + "_r709"
    return [restored_dir(ep, ".mov") / (name + ".mov"), restored_dir(ep, ".mp4") / (name + ".mp4")]


def quick_class(path):
    """Metadata-only class (no frame decoding): restored | hdr | rec709 | dlogm | unknown10."""
    path = Path(path)
    meta = probe(path)
    tags = " ".join(str(v) for v in meta["tags"].values())
    if MARKER in tags or re.search(r"_r709(_(%s))?$" % "|".join(STYLES), path.stem, re.I):
        return "restored"
    if (meta.get("color_transfer") or "") in HDR_TRC:
        return "hdr"
    if meta["bits"] == 8:
        return "rec709"
    tpl = meta.get("dji_template") or ""
    if tpl.endswith("_10BIT"):
        return "dlogm"
    return "unknown10"


def classify_row(clip, rel):
    row = {"clip": rel}
    try:
        row.update(classify(clip))
    except ValueError as exc:
        row.update({"class": "unknown", "confidence": 0.0, "reasons": [str(exc)], "metrics": None})
    st = Path(clip).stat()
    row["source"] = {"size": st.st_size, "mtime": round(st.st_mtime, 3)}
    return row


def scan(path):
    """Read-only classification of any file or folder (e.g. an SD card). Writes nothing."""
    path = Path(path)
    base = path if path.is_dir() else path.parent
    rows = [classify_row(c, c.relative_to(base).as_posix()) for c in list_clips(path)]
    return {"scan": str(path), "summary": summarize(rows), "clips": rows}


def summarize(rows):
    return {k: sum(1 for r in rows if r.get("effective_class", r["class"]) == k) for k in ("dlogm", "rec709", "unknown")}


def encoders_for(encoder, proxy):
    if encoder == "auto":
        return [proxy_encoder()]
    if encoder == "prores":
        return ["prores"] + ([proxy_encoder()] if proxy else [])
    return [encoder]


def process(ep, style=None, dry_run=False, force=False, assume=None, encoder="prores", only=None,
            proxy=True, log=print):
    ep = Path(ep)
    if assume and not only:
        raise ValueError("--assume needs --only <clip ...>: name the reviewed clips explicitly")
    out_dir = ep / RESTORED_DIR
    if not (ep / "footage/raw").is_dir() and not (ep / "footage/selects_dlogm").is_dir():
        raise ValueError("missing footage/raw: %s" % (ep / "footage/raw"))
    if style and style.lower() in ("none", "off", "no"):
        style = None
    slut = style_lut(style) if style else None
    encoders = encoders_for(encoder, proxy)
    rows = []
    for kind, folder, always in SOURCE_DIRS:
        root = ep / folder
        for clip in list_clips(root):
            rel = clip.relative_to(root).as_posix()
            if only and clip.stem not in only and clip.name not in only and rel not in only:
                continue
            row = classify_row(clip, rel)
            row["dir"] = kind
            cls = row["class"]
            if always:
                if row.get("hdr"):
                    row["reasons"].append("footage/selects_dlogm must not contain HLG/PQ clips: not converted")
                    row["error"] = "hdr_in_selects"
                else:
                    row["reasons"].append("footage/selects_dlogm convention: always D-Log M")
                    cls = row["effective_class"] = "dlogm"
            elif cls == "unknown" and assume in ("dlogm", "rec709"):
                if row.get("hdr"):
                    row["reasons"].append("--assume ignored: HLG/PQ clips are never restored with the D-Log M LUT")
                else:
                    row["reasons"].append("--assume %s applied to reviewed clip" % assume)
                    cls = row["effective_class"] = assume
            outputs = []
            if cls == "dlogm":
                stem = out_stem(kind, rel)
                targets = []
                for enc in encoders:
                    ext = ENCODERS[enc]["ext"]
                    folder_out = restored_dir(ep, ext)
                    targets.append((folder_out / (stem + "_r709" + ext), [RESTORE_LUT], enc))
                    if slut:
                        targets.append((folder_out / ("%s_r709_%s%s" % (stem, style.capitalize(), ext)), [RESTORE_LUT, slut], enc))
                for dst, luts, enc in targets:
                    item = {"output": dst.relative_to(ep).as_posix(), "encoder": enc,
                            "luts": [Path(l).relative_to(REPO).as_posix() for l in luts]}
                    if dry_run:
                        item["action"] = "would_convert"
                    elif not force and up_to_date(dst, [clip, *luts]):
                        item["action"] = "skipped_up_to_date"
                    else:
                        log("restore %s/%s -> %s" % (folder, rel, item["output"]), flush=True)
                        try:
                            convert(clip, dst, luts, row["metadata"], enc)
                            item["action"] = "converted"
                        except ValueError as exc:
                            item["action"], item["error"] = "failed", str(exc)
                    if dst.is_file():
                        item["bytes"] = dst.stat().st_size
                    outputs.append(item)
                row["action"] = ",".join(sorted({o["action"] for o in outputs}))
            elif cls == "rec709":
                row["action"] = "none_rec709" if not row.get("already_restored") else "none_already_restored"
            else:
                row["action"] = "none_unknown_needs_review"
            row["outputs"] = outputs
            rows.append(row)
    report = {"episode": ep.name, "dirs": [f for _, f, _ in SOURCE_DIRS], "restore_lut": RESTORE_LUT.relative_to(REPO).as_posix(),
              "style": style.capitalize() if style else None, "encoders": encoders,
              "thresholds": {**TH, "weights": WEIGHTS, "dlogm_score": DLOGM_SCORE, "provisional": PROVISIONAL},
              "summary": summarize(rows), "clips": rows}
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        old = _load_report(ep) if only else None
        if old:   # partial run (--only): keep the other clips' rows
            keep = [r for r in old.get("clips", []) if (r.get("dir", "raw"), r["clip"]) not in {(r2["dir"], r2["clip"]) for r2 in rows}]
            report["clips"] = keep + rows
            report["summary"] = summarize(report["clips"])
        (out_dir / "color_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _load_report(ep):
    try:
        return json.loads((Path(ep) / REPORT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _fresh_class(ep, kind, rel, clip, report=None):
    """Class from color_report.json if it describes this exact source file, else metadata-only."""
    report = report if report is not None else (_load_report(ep) or {})
    for row in report.get("clips", []):
        if row.get("dir", "raw") == kind and row["clip"] == rel:
            src, st = row.get("source") or {}, clip.stat()
            if src.get("size") == st.st_size and abs(src.get("mtime", 0) - st.st_mtime) < 1:
                return row.get("effective_class", row["class"])
    q = quick_class(clip)
    return {"dlogm": "dlogm", "unknown10": "unclassified", "restored": "rec709"}.get(q, q)


def restored_for(ep, path, purpose="render"):
    """Map a camera clip in footage/raw or footage/selects_dlogm to its restored version.
    purpose="render": 8-bit H.264 proxy (Remotion/Chrome); "matte"/"grade": 10-bit ProRes master.
    Clips that are not D-Log M are returned unchanged. Unrestored D-Log M raises ValueError."""
    ep = Path(ep).resolve()
    p = Path(path)
    p = (p if p.is_absolute() else ep / p).resolve()
    for kind, folder, always in SOURCE_DIRS:
        root = (ep / folder).resolve()
        if root in p.parents:
            rel = p.relative_to(root).as_posix()
            mov, mp4 = required_outputs(ep, kind, rel)
            dst = mp4 if purpose == "render" else mov
            if up_to_date(dst, [p]):
                return dst
            cls = "dlogm" if always else _fresh_class(ep, kind, rel, p)
            if cls in ("dlogm", "unclassified"):
                raise ValueError("unrestored %s camera clip: %s/%s - run: npm run restore -- %s"
                                 % ("D-Log M" if cls == "dlogm" else "10-bit", folder, rel, ep.relative_to(REPO).as_posix() if REPO in ep.parents else ep))
            return p
    return p


def restored_for_any(path, purpose="render"):
    """restored_for() for a path whose episode is found by walking up to episode.yaml."""
    p = Path(path).resolve()
    for parent in p.parents:
        if (parent / "episode.yaml").is_file():
            return restored_for(parent, p, purpose)
    return p


RENDER_MEDIA_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


def gate(ep):
    """Preflight for every content line: (errors, warnings).
    Errors: D-Log M camera clip without an up-to-date ProRes + H.264 proxy, 10-bit camera clip not yet
    classified, or render-bound media (public/, footage/shots/, broll/) that is itself unrestored D-Log M."""
    ep = Path(ep)
    errors, warnings = [], []
    report = _load_report(ep) or {}
    hint = "run: npm run restore -- " + (ep.resolve().relative_to(REPO).as_posix() if REPO in ep.resolve().parents else str(ep))
    for kind, folder, always in SOURCE_DIRS:
        for clip in list_clips(ep / folder):
            rel = clip.relative_to(ep / folder).as_posix()
            try:
                cls = "dlogm" if always else _fresh_class(ep, kind, rel, clip, report)
                if always and quick_class(clip) == "hdr":
                    errors.append("HLG/PQ clip in footage/selects_dlogm: %s" % rel)
                    continue
            except ValueError as exc:
                errors.append("cannot probe %s/%s: %s" % (folder, rel, exc))
                continue
            if cls == "dlogm":
                missing = [o.relative_to(ep).as_posix() for o in required_outputs(ep, kind, rel)
                           if not up_to_date(o, [clip, RESTORE_LUT])]
                if missing:
                    errors.append("unrestored D-Log M %s/%s (missing/stale %s) - %s" % (folder, rel, ", ".join(missing), hint))
            elif cls == "unclassified":
                errors.append("10-bit camera clip not classified yet: %s/%s - %s" % (folder, rel, hint))
            elif cls == "unknown":
                warnings.append("colour unknown, review (not restored): %s/%s" % (folder, rel))
            elif cls == "hdr":
                warnings.append("HLG/PQ clip, not D-Log M (no restore): %s/%s" % (folder, rel))
    render = [p for p in (ep / "footage").glob("*") if p.is_file() and p.suffix.lower() in RENDER_MEDIA_EXT]
    for sub in ("footage/shots", "public", "broll"):
        if (ep / sub).is_dir():
            render += [p for p in (ep / sub).rglob("*") if p.is_file() and p.suffix.lower() in RENDER_MEDIA_EXT]
    for p in render:
        try:
            if quick_class(p) == "dlogm":
                errors.append("render media is unrestored D-Log M: %s - use the restored proxy" % p.relative_to(ep).as_posix())
        except ValueError:
            pass
    return errors, warnings


def select_clip(ep, clip, t_in, t_out):
    """Lossless (stream-copy) trim of a raw D-Log M clip into footage/selects_dlogm/.
    Stream copy cannot cut between keyframes: the select starts at the keyframe at or before t_in."""
    ep = Path(ep)
    raw = ep / "footage/raw"
    src = Path(clip)
    src = src if src.is_absolute() else (raw / src if (raw / src).is_file() else ep / src)
    src = src.resolve()
    if raw.resolve() not in src.parents or not src.is_file():
        raise ValueError("--select must name a clip in footage/raw: %s" % clip)
    if not 0 <= t_in < t_out:
        raise ValueError("--in must be >= 0 and < --out")
    if quick_class(src) in ("hdr", "rec709", "restored"):
        raise ValueError("source is not D-Log M (metadata says %s); selects_dlogm is for D-Log M only" % quick_class(src))
    dst_dir = ep / "footage/selects_dlogm"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / ("%s_%d-%dms%s" % (src.stem, round(t_in * 1000), round(t_out * 1000), src.suffix))
    tmp = dst.with_name("." + dst.name + ".tmp" + src.suffix)
    r = _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "%.3f" % t_in, "-to", "%.3f" % t_out,
              "-i", str(src), "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy", "-avoid_negative_ts", "make_zero",
              "-map_metadata", "0", "-movflags", "+faststart", str(tmp)])
    if r.returncode:
        tmp.unlink(missing_ok=True)
        raise ValueError("ffmpeg trim failed: %s" % r.stderr.strip()[-300:])
    os.replace(tmp, dst)
    return dst


def print_rows(rows):
    for r in rows:
        m = r.get("metrics") or {}
        print("%-44s %-8s conf=%.2f score=%s black=%s white=%s spread=%s sat=%s  %s" % (
            ("" if r.get("dir", "raw") == "raw" else r["dir"] + "/") + r["clip"], r.get("effective_class", r["class"]),
            r["confidence"], m.get("log_score", "-"),
            m.get("black_floor", "-"), m.get("white_peak", "-"), m.get("spread", "-"), m.get("sat", "-"),
            r.get("action", "scan")))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Detect DJI D-Log M clips in footage/raw (+ footage/selects_dlogm) and restore to Rec.709")
    ap.add_argument("episode", nargs="?")
    ap.add_argument("--scan", metavar="PATH", help="read-only: classify any file/folder (e.g. SD card), write nothing")
    ap.add_argument("--json", metavar="FILE", help="with --scan: also save the scan report to FILE")
    ap.add_argument("--style", help="optional style LUT after restore: %s (default: episode.yaml color.style)" % "|".join(STYLES))
    ap.add_argument("--dry-run", action="store_true", help="classify only; write nothing")
    ap.add_argument("--force", action="store_true", help="re-encode even if outputs are up to date")
    ap.add_argument("--assume", choices=("dlogm", "rec709"), help="treat reviewed unknown clips as this class (needs --only; never HLG/PQ)")
    ap.add_argument("--encoder", choices=("prores", "x264", "nvenc", "auto"), default="prores",
                    help="prores (default): 10-bit ProRes 422 HQ .mov + 8-bit H.264 proxy .mp4; x264/nvenc/auto: H.264 only")
    ap.add_argument("--no-proxy", action="store_true", help="with prores: skip the H.264 proxy (check will fail until it exists)")
    ap.add_argument("--only", nargs="+", help="limit to these clip names/stems")
    ap.add_argument("--select", metavar="RAW_CLIP", help="lossless trim of a raw D-Log M clip into footage/selects_dlogm/")
    ap.add_argument("--in", dest="t_in", type=float, help="with --select: in point, seconds")
    ap.add_argument("--out", dest="t_out", type=float, help="with --select: out point, seconds")
    ap.add_argument("--gate", action="store_true", help="only run the check gate and print errors/warnings")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(REPO))
    if a.scan:
        report = scan(a.scan)
        print_rows(report["clips"])
        print(json.dumps(report["summary"]), "-> scan only (nothing written)")
        if a.json:
            Path(a.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    if not a.episode:
        ap.error("episode or --scan PATH is required")
    if a.assume and not a.only:
        ap.error("--assume needs --only <clip ...>")
    from pipeline.common.workspace import episode_path
    ep = episode_path(a.episode)
    if a.gate:
        errors, warnings = gate(ep)
        print(json.dumps({"pass": not errors, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
        return 1 if errors else 0
    if a.select:
        if a.t_in is None or a.t_out is None:
            ap.error("--select needs --in and --out")
        dst = select_clip(ep, a.select, a.t_in, a.t_out)
        print("select:", dst.relative_to(ep).as_posix(), "(stream copy; starts at the keyframe at/before --in)")
        a.only = [dst.name]
    style = a.style or configured_style(ep)
    report = process(ep, style, a.dry_run, a.force, a.assume, a.encoder, a.only, not a.no_proxy)
    print_rows([r for r in report["clips"] if not a.only or r["clip"] in a.only or Path(r["clip"]).stem in a.only])
    print(json.dumps(report["summary"]), "->", "dry run (nothing written)" if a.dry_run else "footage/restored/color_report.json")
    failed = any(o.get("action") == "failed" for r in report["clips"] for o in r.get("outputs", []))
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)
