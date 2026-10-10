#!/usr/bin/env python3
"""Plan / split the HeyGen avatar render for a map-hub episode (free plan: <= 60 s total, 720p, 16:9).

usage:
  python pipeline/heygen_plan.py episodes/<id> plan                 # after build_vo.py --script script_v2.json
      -> <episode>/heygen/heygen_audio.wav   (upload to HeyGen as the lip-sync audio; ONE landscape video)
         <episode>/heygen/segments.json      (seg id, line, text, speech + cut points in the HeyGen export)
         <episode>/heygen_segments.md
  python pipeline/heygen_plan.py episodes/<id> split <heygen_export.mp4>   -> footage/heygen/<seg>.mp4 (muted, 16:9 kept; Remotion crops to 4:3)
  python pipeline/heygen_plan.py episodes/<id> placeholders <P-clip dir>  -> stand-in segments from the Muse P1–P5 clips (16:9 padded)

Layout of the HeyGen audio: LEAD s silence, seg1 speech, GAP s, seg2 speech, ..., TAIL s.
Cut i = [speech_start_i - GAP/2, speech_end_i + GAP/2] (first starts at 0), so segments tile the export and each keeps 0.25 s
of mouth-closed handle on both sides. In Remotion a segment starts PAD frames before its line's first word.
Uses the per-line TTS files (proj/public/episode/vo/<line>.mp3) so timing matches the timeline exactly; when the cloned
voice replaces the TTS, re-run build_vo.py then this plan step, and give HeyGen the new heygen_audio.wav.
"""
import argparse, json, subprocess
from pathlib import Path
import numpy as np

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
    return segs

def plan(ep, proj):
    tl = json.loads((proj / "src/episode/timeline.json").read_text(encoding="utf-8"))
    segs = on_cam(tl); out = ep / "heygen"; out.mkdir(exist_ok=True)
    buf = [np.zeros(int(LEAD * SR), np.float32)]; t = LEAD
    for i, s in enumerate(segs):
        a = dec(proj / "public" / s["audio"]); d = len(a) / SR
        s["speech"] = [round(t, 3), round(t + d, 3)]; s["dur"] = round(d, 3)
        buf.append(a); t += d
        buf.append(np.zeros(int((GAP if i < len(segs) - 1 else TAIL) * SR), np.float32)); t += GAP if i < len(segs) - 1 else TAIL
    total = t
    for i, s in enumerate(segs):
        s["cut"] = [round(0 if i == 0 else s["speech"][0] - GAP / 2, 3), round(total if i == len(segs) - 1 else s["speech"][1] + GAP / 2, 3)]
        s["cutDur"] = round(s["cut"][1] - s["cut"][0], 3)
    y = np.concatenate(buf); pk = np.abs(y).max() or 1
    wav = out / "heygen_audio.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-ar", str(SR), str(wav)],
                   input=(y / pk * 0.9).astype(np.float32).tobytes(), check=True)
    J = {"total": round(total, 3), "speech": round(sum(s["dur"] for s in segs), 3), "lead": LEAD, "gap": GAP, "tail": TAIL, "segments": segs}
    (out / "segments.json").write_text(json.dumps(J, ensure_ascii=False, indent=1), encoding="utf-8")
    md = [f"# HeyGen segments — {ep.name}", "",
          f"ONE landscape 16:9 video, 720p, avatar **Cool Breeze**, audio = upload `heygen/heygen_audio.wav` (lip-sync to our audio; do not type the script).",
          f"Total length **{total:.2f} s** (speech {J['speech']:.2f} s + {GAP}s pauses) — free-plan limit 60 s, our budget {LIMIT:.0f} s.", "",
          "Framing: keep the face near the horizontal centre — Remotion centre-crops 16:9 → 4:3 (keeps the middle 75 % of the width).", "",
          "| # | seg | line | layout | text | speech (s in export) | dur | cut in → out | cut dur |", "|---|---|---|---|---|---|---|---|---|"]
    for i, s in enumerate(segs):
        md.append(f"| {i+1} | {s['seg']} | {s['line']} | {s['layout']} | {s['text']} | {s['speech'][0]:.2f}–{s['speech'][1]:.2f} | {s['dur']:.2f} | {s['cut'][0]:.2f} → {s['cut'][1]:.2f} | {s['cutDur']:.2f} |")
    md += ["", "Split after download:", "", f"    python pipeline/heygen_plan.py {ep.as_posix()} split <path/to/heygen_export.mp4>", "",
           "If HeyGen's export is longer/shorter than the plan (it can add ~0.1–0.5 s at the head), set `--offset <s>` on split (positive = export starts later).",
           "Then `python pipeline/sync_assets.py " + ep.as_posix() + "` and render."]
    (ep / "heygen_segments.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(segs)} segments, HeyGen video {total:.2f} s (speech {J['speech']:.2f} s) -> {wav}")
    if total > LIMIT: print(f"!! over the {LIMIT:.0f} s budget")

def split(ep, src, offset, fdir):
    J = json.loads((ep / "heygen/segments.json").read_text(encoding="utf-8")); fdir.mkdir(parents=True, exist_ok=True)
    for s in J["segments"]:
        a, b = s["cut"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a + offset:.3f}", "-i", str(src), "-t", f"{b - a:.3f}", "-an", "-r", "30",
                        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(fdir / f"{s['seg']}.mp4")], check=True)
        print(s["seg"], f"{a:.2f}–{b:.2f}")

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
    ap.add_argument("--proj", default=str(REPO / "templates/map-hub/remotion")); ap.add_argument("--footage", default=None, help="default <episode>/footage/heygen"); ap.add_argument("--offset", type=float, default=0.0)
    a = ap.parse_args(); ep = Path(a.episode)
    if a.cmd == "plan": plan(ep, Path(a.proj))
    fh = Path(a.footage) if a.footage else ep / "footage/heygen"
    if a.cmd == "plan": pass
    elif a.cmd == "split": split(ep, Path(a.src), a.offset, fh)
    else: placeholders(ep, Path(a.src or (ep / "footage")), fh)
