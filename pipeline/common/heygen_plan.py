#!/usr/bin/env python3
"""Plan / split the HeyGen avatar render for a map-hub episode (free plan: <= 60 s total, 720p, 16:9).

usage:
  python pipeline/heygen_plan.py episodes/<id> plan                 # after build_vo.py --script script_v2.json
      -> <episode>/heygen/heygen_audio.wav   (upload to HeyGen as the lip-sync audio; ONE landscape video)
         <episode>/heygen/segments.json      (seg id, line, text, speech + cut points in the HeyGen export)
         <episode>/heygen_segments.md
  python pipeline/maphub/heygen_plan.py <episode> split [src.mp4]
      With no src, uses heygen/export_nomark.mp4 after heygen_mark.py (status done),
      or heygen/export.mp4 when the mark step reports absent. Refuses to split while the mark step is pending.
      --sync S (default 0 = OFF): optional lip-sync shift, only if the user explicitly asks (decided 2026-10-19: no compensation by default; apparent desync came from remote-desktop viewing); per segment in episode.yaml heygen_sync. --dry-run prints the cuts.
  python pipeline/heygen_plan.py episodes/<id> placeholders <P-clip dir>  -> stand-in segments from the Muse P1–P5 clips (16:9 padded)

Layout of the HeyGen audio: LEAD s silence, seg1 speech, GAP s, seg2 speech, ..., TAIL s.
Cut i = [speech_start_i - GAP/2, speech_end_i + GAP/2] (first starts at 0), so segments tile the export and each keeps 0.25 s
of mouth-closed handle on both sides. In Remotion a segment starts PAD frames before its line's first word.
Uses the per-line TTS files (proj/public/episode/vo/<line>.mp3) so timing matches the timeline exactly; when the cloned
voice replaces the TTS, re-run build_vo.py then this plan step, and give HeyGen the new heygen_audio.wav.
"""
import argparse, json, math, subprocess, sys
from pathlib import Path
import numpy as np
from .workspace import project_for
from .voice_config import read_yaml
from .voice_timing import fingerprint

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
SR, LEAD, GAP, TAIL, LIMIT = 48000, 0.25, 0.5, 1.5, 55.0   # TAIL covers the end-card hold after the last word

def dec(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)

def on_cam(tl):
    segs = []
    if tl.get("hook"):
        h = tl["hook"]; segs.append({"seg": h["clip"], "line": h["id"], "layout": "A (hook, before opener)", "text": h["tts"], "audio": h["audio"]})
    for L in tl["lines"]:
        if L.get("onCam") in ("A", "PIP"):
            segs.append({"seg": L["clip"], "line": L["id"], "layout": L["onCam"], "text": L["tts"], "audio": L["audio"]})
        elif L.get("pip"):   # presenter PiP card over a map / B-roll line (template `pip`)
            segs.append({"seg": L["pip"], "line": L["id"], "layout": "pip", "text": L["tts"], "audio": L["audio"]})
    return segs

def plan(ep, proj):
    tl = json.loads((proj / "src/episode/timeline.json").read_text(encoding="utf-8"))
    segs = on_cam(tl); out = ep / "heygen"; out.mkdir(exist_ok=True)
    previous = out / "segments.json"
    timeline_hash = fingerprint(proj / "src/episode/timeline.json")
    if previous.is_file() and (out / "heygen_audio.wav").is_file():
        old = json.loads(previous.read_text(encoding="utf-8"))
        current_budget = float(read_yaml(ep / "episode.yaml").get("oncam_budget_s", LIMIT))
        if not math.isfinite(current_budget) or current_budget <= 0 or float(old.get("total", 0)) > current_budget:
            raise ValueError("existing HeyGen plan exceeds the current budget")
        if old.get("timeline_sha256") == timeline_hash:
            print("HeyGen plan unchanged; preserving existing upload audio and cut points")
            return
    buf = [np.zeros(int(LEAD * SR), np.float32)]; t = LEAD
    for i, s in enumerate(segs):
        a = dec(proj / "public" / s["audio"]); d = len(a) / SR
        s["speech"] = [round(t, 3), round(t + d, 3)]; s["dur"] = round(d, 3)
        buf.append(a); t += d
        buf.append(np.zeros(int((GAP if i < len(segs) - 1 else TAIL) * SR), np.float32)); t += GAP if i < len(segs) - 1 else TAIL
    total = t
    budget = float(read_yaml(ep / "episode.yaml").get("oncam_budget_s", LIMIT))
    if not segs or not math.isfinite(budget) or budget <= 0 or total > budget:
        raise ValueError("HeyGen audio %.2fs exceeds budget %.2fs or contains no on-camera segments" % (total, budget))
    for i, s in enumerate(segs):
        s["cut"] = [round(0 if i == 0 else s["speech"][0] - GAP / 2, 3), round(total if i == len(segs) - 1 else s["speech"][1] + GAP / 2, 3)]
        s["cutDur"] = round(s["cut"][1] - s["cut"][0], 3)
    y = np.concatenate(buf); pk = np.abs(y).max() or 1
    wav = out / "heygen_audio.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-ar", str(SR), str(wav)],
                   input=(y / pk * 0.9).astype(np.float32).tobytes(), check=True)
    J = {"total": round(total, 3), "speech": round(sum(s["dur"] for s in segs), 3), "lead": LEAD, "gap": GAP, "tail": TAIL, "segments": segs, "timeline_sha256": fingerprint(proj / "src/episode/timeline.json")}
    (out / "segments.json").write_text(json.dumps(J, ensure_ascii=False, indent=1), encoding="utf-8")
    _ep = read_yaml(ep / "episode.yaml")
    _pres = read_yaml(REPO / "assets/presenter" / (_ep.get("presenter") or "cool-breeze") / "presenter.yaml")
    look = ((_ep.get("presenter_override") or {}).get("heygen") or {}).get("look") or (_pres.get("heygen") or {}).get("look")
    if not look or str(look).strip().lower() == "default":
        raise ValueError("presenter.yaml heygen.look must name the user's saved look (never 'default')")
    md = [f"# HeyGen segments — {ep.name}", "",
          f"LOOK RULE: open avatar Cool Breeze, select the SAVED look **{look}** by name, verify it is selected before Generate; if it is not found, STOP (do not generate with a default look).",
          f"ONE landscape 16:9 video, 720p, avatar **Cool Breeze** (look **{look}**), audio = upload `heygen/heygen_audio.wav` (lip-sync to our audio; do not type the script).",
          f"Total length **{total:.2f} s** (speech {J['speech']:.2f} s + {GAP}s pauses) — free-plan limit 60 s, our budget {LIMIT:.0f} s.", "",
          "Framing: after runbook 7b (heygen_43.py) segments are native 4:3 1440x1080, no crop. Fallback without 7b: keep the face near the horizontal centre — Remotion centre-crops 16:9 → 4:3 (keeps the middle 75 % of the width).", "",
          "| # | seg | line | layout | text | speech (s in export) | dur | cut in → out | cut dur |", "|---|---|---|---|---|---|---|---|---|"]
    for i, s in enumerate(segs):
        md.append(f"| {i+1} | {s['seg']} | {s['line']} | {s['layout']} | {s['text']} | {s['speech'][0]:.2f}–{s['speech'][1]:.2f} | {s['dur']:.2f} | {s['cut'][0]:.2f} → {s['cut'][1]:.2f} | {s['cutDur']:.2f} |")
    md += ["", "After download, cover the corner mark on the original, then split:", "",
           f"    python pipeline/maphub/heygen_mark.py {ep.as_posix()}",
           "    # exit 3: agent saves heygen/mark/repair.png from heygen/mark/flova_request.json (generate_image), then rerun",
           f"    python pipeline/maphub/heygen_plan.py {ep.as_posix()} split", "",
           "If HeyGen's export is longer/shorter than the plan (it can add ~0.1–0.5 s at the head), set `--offset <s>` on split (positive = export starts later).",
           "Then `python pipeline/maphub/sync_assets.py " + ep.as_posix() + "` and render."]
    (ep / "heygen_segments.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(segs)} segments, HeyGen video {total:.2f} s (speech {J['speech']:.2f} s) -> {wav}")
    if total > LIMIT: print(f"!! over the {LIMIT:.0f} s budget")

def default_split_src(ep):
    """Cleaned original after heygen_mark.py. Explicit src on the command line skips this."""
    four3 = ep / "heygen" / "export_43.mp4"
    if four3.is_file():   # runbook 7b: heygen_43.py (de-watermarked, outpainted 1440x1080)
        print("split source", four3, "(4:3, de-watermarked)")
        return four3
    status_p = ep / "heygen" / "mark" / "status.json"
    export, clean = ep / "heygen" / "export.mp4", ep / "heygen" / "export_nomark.mp4"
    if not status_p.is_file():
        print(f"run python pipeline/maphub/heygen_mark.py {ep.as_posix()} before split", file=sys.stderr)
        raise SystemExit(2)
    status = json.loads(status_p.read_text(encoding="utf-8")).get("status")
    if status == "done":
        if not clean.is_file():
            print(f"mark status is done but {clean} is missing", file=sys.stderr)
            raise SystemExit(2)
        print("split source", clean)
        return clean
    if status == "absent":
        if not export.is_file():
            print(f"missing {export}", file=sys.stderr)
            raise SystemExit(2)
        print("split source", export, "(no corner mark)")
        return export
    print(f"heygen mark is {status}; finish python pipeline/maphub/heygen_mark.py {ep.as_posix()} before split", file=sys.stderr)
    raise SystemExit(2)

SYNC_DEFAULT = 0.0   # s; OFF by default (decided 2026-10-19). Only set via --sync / episode.yaml heygen_sync when the user explicitly asks.
                       # Negative = cut earlier in the export, i.e. delay the picture relative to the voice (same as knowledge cut_v5.py).

def sync_table(ep, default):
    """Per-segment lip-sync shift in seconds: episode.yaml `heygen_sync: {default: 0, HG03: -0.12}` overrides the default (off unless explicitly given)."""
    cfg = read_yaml(ep / "episode.yaml").get("heygen_sync") or {}
    base = float(cfg.get("default", default))
    return base, {k: float(v) for k, v in cfg.items() if k != "default"}

def split(ep, src, offset, fdir, sync_default=SYNC_DEFAULT, dry_run=False):
    plan_path = ep / "heygen/segments.json"
    J = json.loads(plan_path.read_text(encoding="utf-8"))
    if not dry_run:
        if J.get("timeline_sha256") != fingerprint(ep / "data/timeline.json"):
            raise ValueError("HeyGen plan is stale; rebuild it before split")
        original = ep / "heygen/export.mp4"
        if (original if original.is_file() else src).stat().st_mtime < plan_path.stat().st_mtime:
            raise ValueError("HeyGen export predates the current voice plan; download the matching generation first")
        fdir.mkdir(parents=True, exist_ok=True)
    base, per = sync_table(ep, sync_default)
    provenance = {"plan_sha256": fingerprint(plan_path), "source_sha256": None if dry_run else fingerprint(src), "offset": offset, "sync": {}, "segments": {}}
    for s in J["segments"]:
        a, b = s["cut"]
        shift = per.get(s["seg"], base)
        ss = a + offset + shift
        pre = max(0.0, -ss); ss = max(0.0, ss)
        vf = ["-vf", f"tpad=start_mode=clone:start_duration={pre:.3f}"] if pre > 0 else []
        argv = ["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.3f}", "-i", str(src), "-t", f"{b - a - pre:.3f}", "-an", *vf, "-r", "30",
                "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(fdir / f"{s['seg']}.mp4")]
        print(s["seg"], f"{a:.2f}–{b:.2f}", f"sync {shift:+.3f}s", "(dry-run)" if dry_run else "")
        provenance["sync"][s["seg"]] = shift
        if dry_run:
            print("  +", " ".join(argv)); continue
        subprocess.run(argv, check=True)
        provenance["segments"][s["seg"]] = fingerprint(fdir / (s["seg"] + ".mp4"))
        # a matte must come from this exact segment: a re-split invalidates any older <seg>_alpha.webm (it would drift / freeze -> doubled presenter)
        alpha = fdir / f"{s['seg']}_alpha.webm"; side = alpha.with_suffix(".json")
        ok = side.is_file() and json.loads(side.read_text(encoding="utf-8")).get("source_sha256") == provenance["segments"][s["seg"]]
        if alpha.is_file() and not ok:
            (fdir / "stale").mkdir(exist_ok=True); alpha.replace(fdir / "stale" / alpha.name)
            if side.is_file(): side.replace(fdir / "stale" / side.name)
            print(f"  ! {alpha.name} was matted from an older {s['seg']}; moved to stale/. Re-run: python pipeline/maphub/matte_avatar.py {(fdir / (s['seg'] + '.mp4')).as_posix()}", file=sys.stderr)
    if not dry_run:
        (ep / "heygen/split_manifest.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8", newline="\n")

def placeholders(ep, pdir, fdir):
    """stand-ins: Muse P clips, padded to 1280x720 (blurred sides) like a HeyGen export, trimmed to each cut length"""
    J = json.loads((ep / "heygen/segments.json").read_text(encoding="utf-8")); fdir.mkdir(parents=True, exist_ok=True)
    order = ["P1", "P2", "P3", "P2", "P4", "P2", "P3", "P2", "P4", "P2", "P5"]
    for i, s in enumerate(J["segments"]):
        p = pdir / f"{order[i % len(order)] if s['line'] != 'L24' else 'P5'}.mp4"
        d = s["cutDur"]; ss = max(0.0, 10 - d - 0.1) if s["line"] == "L24" else (i * 1.3) % max(0.1, 10 - d - 0.2)
        vf = "[0]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,boxblur=20[bg];[0]scale=-2:720[fg];[bg][fg]overlay=(W-w)/2:0"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.2f}", "-i", str(p), "-t", f"{d:.3f}", "-an", "-filter_complex", vf, "-r", "30",
                        "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", str(fdir / f"{s['seg']}.mp4")], check=True)
        print("placeholder", s["seg"], "<-", p.name)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("episode"); ap.add_argument("cmd", choices=["plan", "split", "placeholders"]); ap.add_argument("src", nargs="?")
    ap.add_argument("--proj", default=None, help="episode-owned workspace only"); ap.add_argument("--footage", default=None, help="default <episode>/footage/heygen"); ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--sync", type=float, default=SYNC_DEFAULT, help="optional lip-sync shift in s for every segment (default 0 = off; only if the user asks; episode.yaml heygen_sync overrides per segment)")
    ap.add_argument("--dry-run", action="store_true", help="split: print the ffmpeg cuts only")
    a = ap.parse_args(); ep = Path(a.episode)
    if a.cmd == "plan": plan(ep.resolve(), project_for(ep, a.proj))
    fh = Path(a.footage) if a.footage else ep / "footage/heygen"
    if a.cmd == "plan": pass
    elif a.cmd == "split": split(ep, Path(a.src) if a.src else default_split_src(ep), a.offset, fh, a.sync, a.dry_run)
    else: placeholders(ep, Path(a.src or (ep / "footage")), fh)

