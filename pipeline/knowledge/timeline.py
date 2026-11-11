#!/usr/bin/env python3
"""Build the KnowledgeKoubo timeline + footage data for a knowledge episode (compose step).

Reads  <ep>/episode.yaml (segments), voice wavs in <ep>/voice/<engine-dir>/ (<seg id>.wav + word sidecars),
       b-roll media in <ep>/broll/{flova,muse,screens}/ (<ref>.mp4|.png|.jpg), HeyGen segments in <ep>/footage/heygen/.
Writes <ep>/data/timeline.json   (rows are heygen_plan-compatible: oncam rows carry clip=HGnn + onCam="A" + audio)
       <ep>/data/footage.json    (b-roll + HeyGen segments, probed; missing media -> kind "pending" cards)
       <ep>/data/{episode,brands,social}.json  (composition imports)
       public copies under <ep>/public/        (episode/vo/, broll/, footage/heygen/)
       <ep>/script_timed.md      (human-readable timed script)

Shared logic is imported from pipeline/maphub (read_yaml, fingerprint, read_alignment, caption_frames,
sync_assets.probe/img_size) â€” no duplication. No map / POI / listing data is read or written.

usage: python pipeline/knowledge/timeline.py <ep> [--voice-dir <dir>] [--draft]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from pipeline.common.voice_config import read_yaml  # noqa: E402  (shared with map-hub)
from pipeline.common.voice_timing import caption_frames, fingerprint, read_alignment  # noqa: E402  (shared)
from pipeline.common.media import img_size, probe, materialize  # noqa: E402  (shared)

import episode as kepi  # noqa: E402  (same package)

FPS, GAP_S, TAIL_S = 30, 0.5, 1.4
MEDIA_EXT = (".mp4", ".mov", ".png", ".jpg", ".jpeg", ".webp")


def cap_chunks(text: str) -> list[str]:
    """Split spoken text into caption chunks at clause boundaries; normalized chunks still tile the text."""
    parts = re.split(r"(?<=[ã€‚ï¼ï¼Ÿ!?â€¦ï¼›;])|(?<=[ï¼Œ,ã€])", text)
    chunks = [p.strip() for p in parts if re.sub(r"[ï¼Œã€‚ï¼›ï¼šã€ï¼ï¼Ÿ,.;:!?\sâ€¦]", "", p)]
    return chunks or [text]


def voice_dir_for(ep: Path, cfg: dict, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    engine = (cfg.get("voice_defaults") or {}).get("engine", "flova_minimax")
    return (ep / "voice" / engine).resolve()


def find_media(ep: Path, cfg: dict, kind: str, ref: str) -> Path | None:
    base = ep / (cfg.get("broll_dirs") or {}).get(kind, f"broll/{kind}")
    for ext in MEDIA_EXT:
        p = base / f"{ref}{ext}"
        if p.is_file():
            return p
    return None


def build(value, voice_dir=None, draft=False) -> dict:
    ep, cfg, segments = kepi.load_episode(value)
    vdir = voice_dir_for(ep, cfg, voice_dir)
    if REPO not in vdir.parents:
        raise ValueError("voice-dir must be inside the repo")
    data = ep / "data"
    pub = ep / "public"
    (data).mkdir(exist_ok=True)
    (pub / "episode" / "vo").mkdir(parents=True, exist_ok=True)
    (pub / "broll").mkdir(parents=True, exist_ok=True)

    rows, t = [], 0.0
    hg = 0
    audio_mode = "clone"
    for seg in segments:
        sid = seg["id"]
        wav = vdir / f"{sid}.wav"
        words, source_audio, source_sha = [], None, None
        if wav.is_file():
            dur = float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                capture_output=True, text=True, check=True).stdout.strip())
            materialize(wav, pub / "episode" / "vo" / f"{sid}.wav")
            source_audio = str(wav.relative_to(REPO))
            source_sha = fingerprint(wav)
            try:
                words = read_alignment(wav, seg["text"])
            except ValueError as exc:
                if not draft:
                    raise
                print(f"!! {sid}: {exc} (draft: estimated captions)")
        else:
            audio_mode = "draft"
            dur = float(seg["est_s"])
        f0 = round(t * FPS)
        f1 = round((t + dur) * FPS)
        caps = caption_frames(seg["text"], cap_chunks(seg["text"]), words, dur, f0, FPS,
                              allow_estimated=draft or not words)
        row = {
            "id": sid, "n": seg["n"], "type": seg["type"], "name": seg.get("name", sid),
            "text": seg["text"], "tts": seg["text"],
            "f0": f0, "f1": f1, "dur": round(dur, 3), "caps": caps,
            "audio": f"episode/vo/{sid}.wav",
            "caption_timing": "word" if words else "estimated",
        }
        if source_audio:
            row["source_audio"] = source_audio
            row["source_sha256"] = source_sha
        if seg["type"] == "oncam":
            row["clip"] = f"HG{hg:02d}"
            row["onCam"] = "A"
            hg += 1
        else:
            if seg.get("process"):
                row["process"] = [str(x) for x in seg["process"]]
            if seg.get("cards"):
                row["cards"] = [{"value": str(c.get("value", "")), "sub": str(c.get("sub", ""))}
                                for c in seg["cards"]][:2]
        if seg.get("end"):
            row["end"] = True
        rows.append(row)
        t += dur + GAP_S

    # visual spans: each row holds until the next starts; last row keeps a tail
    for i, r in enumerate(rows):
        if i:
            rows[i - 1]["v1"] = r["f0"]
        r["v0"] = r["f0"] if i == 0 else rows[i - 1]["v1"]
    rows[-1]["v1"] = rows[-1]["f1"] + round(TAIL_S * FPS)
    total = rows[-1]["v1"]

    # b-roll items split their segment's visual span equally
    footage: dict = {}
    for seg, row in zip(segments, rows):
        if seg["type"] != "voiceover":
            continue
        items = seg.get("broll") or []
        if not items:
            continue
        span = row["v1"] - row["v0"]
        step = span / len(items)
        row["broll"] = []
        for k, b in enumerate(items):
            clip = str(b["ref"])
            row["broll"].append({
                "ref": clip, "clip": clip, "desc": str(b.get("desc") or clip),
                "f0": round(row["v0"] + k * step), "f1": round(row["v0"] + (k + 1) * step),
            })
            src = find_media(ep, cfg, b["kind"], clip)
            if src is None:
                footage[clip] = {"kind": "pending", "status": "pending",
                                 "label": str(b.get("desc") or clip), "purpose": f"{b['kind']} ç´ æå¾…è¡¥ï¼š{b.get('desc', clip)}"}
                continue
            dst = pub / "broll" / src.name
            if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                materialize(src, dst)
            if src.suffix.lower() in (".mp4", ".mov"):
                footage[clip] = {"kind": "video", "src": f"broll/{src.name}", "status": b["kind"],
                                 **(probe(dst) or {})}
            else:
                footage[clip] = {"kind": "image", "src": f"broll/{src.name}", "status": b["kind"],
                                 **img_size(dst),
                                 "kb": {"s0": 1.0, "s1": 1.07, "ox0": 0.5, "oy0": 0.5, "ox1": 0.5, "oy1": 0.45}}
            footage[clip]["purpose"] = str(b.get("desc") or clip)

    # HeyGen segments + mattes (mirrors maphub sync_assets: footage/heygen/<seg>.mp4, <seg>_alpha.webm)
    hdir = ep / "footage" / "heygen"
    if hdir.is_dir():
        crop = {}
        if (ep / "heygen" / "crop.json").is_file():
            crop = json.loads((ep / "heygen" / "crop.json").read_text(encoding="utf-8"))
        (pub / "footage" / "heygen").mkdir(parents=True, exist_ok=True)
        for src in sorted(list(hdir.glob("*.mp4")) + list(hdir.glob("*_alpha.webm"))):
            dst = pub / "footage" / "heygen" / src.name
            if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                materialize(src, dst)
            footage[src.stem] = {"kind": "video", "src": f"footage/heygen/{src.name}", "status": "heygen",
                                 "cx": crop.get(src.stem, 0.5), **(probe(dst) or {})}

    timeline = {
        "fps": FPS, "width": 1440, "height": 1080, "total": total, "series": "knowledge",
        "voice": (cfg.get("voice_defaults") or {}).get("voice", "Gentle_Youth"),
        "lines": rows, "audio_mode": audio_mode, "draft": bool(draft or audio_mode != "clone"),
        "script_file": "episode.yaml", "script_sha256": fingerprint(ep / "episode.yaml"),
    }
    (data / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=1) + "\n",
                                        encoding="utf-8", newline="\n")
    (data / "footage.json").write_text(json.dumps(footage, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")

    # composition data: episode.json copy, brands (episode override or series default), social rows
    materialize(ep / "episode.json", data / "episode.json")
    if not (data / "brands.json").is_file():
        materialize(REPO / "templates" / "knowledge" / "brands.json", data / "brands.json")
    pres = read_yaml(REPO / "assets" / "presenter" / str(cfg.get("presenter") or "cool-breeze") / "presenter.yaml")
    rows_social = cfg.get("social") or (pres or {}).get("social") or []
    (data / "social.json").write_text(json.dumps({"rows": rows_social}, ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8", newline="\n")

    md = ["# å£æ’­ç¨¿ï¼ˆå¸¦æ—¶é—´ï¼‰Â· " + ep.name, "",
          f"æ¨¡å¼ {audio_mode}ï¼›æ€»é•¿ {total} å¸§ = {total / FPS:.1f}sã€‚"
          f"éœ²è„¸ {sum(1 for r in rows if r['type'] == 'oncam')} æ®µ "
          f"{sum(r['f1'] - r['f0'] for r in rows if r['type'] == 'oncam') / FPS:.1f}sï¼ˆé¢„ç®— {cfg.get('oncam_budget_s', 55)}sï¼‰ã€‚", "",
          "| æ®µ | æ—¶é—´ (s) | ç±»åž‹ | ç”»é¢ | å°è¯ |", "|---|---|---|---|---|"]
    for r in rows:
        if r["type"] == "oncam":
            vis = f"ä¸»æŒäººå…¨å± {r.get('clip', '')}"
        else:
            bits = [f"{b['clip']}({b['desc']})" for b in r.get("broll", [])]
            if r.get("process"):
                bits.append("æµç¨‹åŠ¨ç”»:" + "â†’".join(r["process"]))
            vis = "B-roll " + "ã€".join(bits)
        md.append(f"| {r['id']} | {r['v0'] / FPS:.1f}â€“{r['v1'] / FPS:.1f} | {r['type']} | {vis} | {r['text']} |")
    (ep / "script_timed.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")

    oncam_s = sum(r["f1"] - r["f0"] for r in rows if r["type"] == "oncam") / FPS
    budget = float(cfg.get("oncam_budget_s", 55))
    print(f"timeline: {len(rows)} æ®µ, total {total} f = {total / FPS:.1f}s, éœ²è„¸ {oncam_s:.1f}s / é¢„ç®— {budget:.0f}s, æ¨¡å¼ {audio_mode}")
    pending = [k for k, v in footage.items() if v.get("status") == "pending"]
    if pending:
        print("pending ç´ æ:", ", ".join(pending))
    if oncam_s > budget:
        print(f"!! éœ²è„¸åˆè®¡è¶…è¿‡ oncam_budget_sï¼ˆ{budget:.0f}sï¼‰â€” åŽ‹ç¨¿æˆ–å‡æ®µ")
    return timeline


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode")
    ap.add_argument("--voice-dir", default=None, help="dir of <seg id>.wav (default <ep>/voice/<engine>)")
    ap.add_argument("--draft", action="store_true", help="allow estimated captions / missing voice")
    a = ap.parse_args()
    build(a.episode, voice_dir=a.voice_dir, draft=a.draft)


if __name__ == "__main__":
    main()

