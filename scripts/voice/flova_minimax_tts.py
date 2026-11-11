#!/usr/bin/env python3
"""Default ReelEstate voiceover: MiniMax Speech 2.8 HD preset voice via the flova CLI (approved 2026-10-12).

Usage: python scripts/voice/flova_minimax_tts.py script.json [--out DIR] [--profile kid4] [--voice "Chinese (Mandarin)_Gentle_Youth"]
                                                 [--project-id ID] [--lufs -16]
script.json: {"lines": [{"id": "L01", "text": "..."}, ...]} (plain strings allowed).
Default --mode passage: all lines joined into ONE flova run (saves credits, ~10 per call) -> DIR/passage.wav plus
DIR/passage.json (line ids + texts in order; derive per-line/section timings from Whisper word timestamps on the
sped-up wav). --mode line: one run per line -> DIR/<id>.wav.
--tempo (default 1.1, or "tempo" in the script/presenter voice): ffmpeg atempo (pitch-preserving) before loudnorm.
Route: flova MCP tool generate_speech (~/.flova-mcp/server.js, via scripts/flova/mcp_call.py call()), which runs
flova run with MiniMax Speech 2.8 HD + the preset voice, balance-gated (fail-closed), and downloads the mp3;
then ffmpeg loudnorm to <lufs> LUFS mono 44.1 kHz wav. About 10 credits per line (2026-10-12).
Writes DIR/<id>.wav, DIR/<id>.src.mp3, DIR/generation.json. Passage mode then runs (offline, skip with --no-timings /
--no-retime): passage_timings.py -> retime_pauses.py -> loudnorm -> passage_timings.py --split (timings.json + per-line
<id>.wav/<id>.json sidecars for build_vo.py --alignment-dir). Spends flova credits (~10 per call).
Exit 21 on any flova failure, so callers can fall back (indextts25 on Kaggle, then local F5)."""
import argparse, json, os, subprocess, sys, time, wave

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "flova"))
from mcp_call import call  # noqa: E402
EXIT_FALLBACK = 21


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script"); ap.add_argument("--out")
    ap.add_argument("--profile", default="kid4")
    ap.add_argument("--voice", default="Gentle_Youth")
    ap.add_argument("--model", default="speech-2.8-hd")
    ap.add_argument("--project-id"); ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--timeout", type=int, default=1500)
    ap.add_argument("--mode", choices=["passage", "line"], default=None)
    ap.add_argument("--tempo", type=float, default=None)
    ap.add_argument("--no-retime", action="store_true", help="skip retime_pauses.py (passage mode)")
    ap.add_argument("--no-timings", action="store_true", help="skip passage_timings.py (passage mode)")
    a = ap.parse_args()
    cfg = json.load(open(a.script, encoding="utf-8-sig"))
    lines = cfg if isinstance(cfg, list) else cfg["lines"]
    voice = cfg.get("voice", a.voice) if isinstance(cfg, dict) else a.voice
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.script)), "tts")
    os.makedirs(out, exist_ok=True)
    tempo = a.tempo or (cfg.get("tempo") if isinstance(cfg, dict) else None) or 1.1
    mode = a.mode or (cfg.get("mode") if isinstance(cfg, dict) else None) or "passage"
    if not 0.5 <= float(tempo) <= 2.0: raise SystemExit("tempo must be 0.5-2.0 (single atempo stage)")
    lines = [{"id": "line%02d" % (i + 1), "text": l} if isinstance(l, str) else l for i, l in enumerate(lines)]
    if mode == "passage":
        def _end(t):
            t = t.strip()
            return t if t[-1:] in "。！？!?…，," else t + "。"
        json.dump({"lines": [{"id": l["id"], "text": l["text"]} for l in lines]},
                  open(os.path.join(out, "passage.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        lines = [{"id": "passage", "text": "".join(_end(l["text"]) for l in lines)}]
    tim = {"tempo": float(tempo), "mode": mode, "engine": "flova_minimax", "model": a.model, "voice": voice, "profile": a.profile, "lines": []}
    try:
        pid = a.project_id
        for i, ln in enumerate(lines):
            if isinstance(ln, str): ln = {"id": "line%02d" % (i + 1), "text": ln}
            text = ln["text"]
            if "——" in text or "--" in text:
                raise SystemExit("line %s: do not use —— or -- in TTS text (read aloud); use ， or …" % ln["id"])
            t = time.time()
            src = os.path.join(os.path.abspath(out), ln["id"] + ".src.mp3"); f = os.path.join(out, ln["id"] + ".wav")
            args = {"text": text, "model": a.model, "voice": voice, "profile": a.profile, "out_path": src,
                    "run_timeout": a.timeout}
            if pid: args["project_id"] = pid
            res = call("generate_speech", args)
            if res.get("status") != "ok":
                raise RuntimeError("line %s: generate_speech %s: %s" % (ln["id"], res.get("status"), json.dumps(res, ensure_ascii=False)[:300]))
            pid = res.get("project_id"); tim["project_id"] = pid
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-af",
                            "atempo=%g,loudnorm=I=%g:TP=-1.5:LRA=11" % (float(tempo), a.lufs), "-ar", "44100", "-ac", "1", f], check=True)
            with wave.open(f) as w: dur = w.getnframes() / w.getframerate()
            tim["lines"].append({"id": ln["id"], "gen_s": round(time.time() - t, 1), "audio_s": round(dur, 2),
                                 "credits": (res.get("cost") or {}).get("spent"), "resource_id": res.get("resource_id")})
            print(ln["id"], "%.1fs audio, %s credits" % (dur, (res.get("cost") or {}).get("spent")), flush=True)
    except (RuntimeError, subprocess.SubprocessError, KeyError, OSError) as e:
        sys.stderr.write("FLOVA_MINIMAX_FAILED: %s\nfallback: indextts25 (scripts/voice/push_indextts25.py), "
                         "last resort local F5 (scripts/voice/clone_tts_f5.cmd)\n" % e)
        sys.exit(EXIT_FALLBACK)
    with open(os.path.join(out, "generation.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(tim, fh, ensure_ascii=False, indent=1)
    if mode == "passage":
        # Offline post-steps (no credits): Whisper-aligned timings -> pause retime -> timings again + per-line split.
        here = os.path.dirname(os.path.abspath(__file__))
        py, wav, pj = sys.executable, os.path.join(out, "passage.wav"), os.path.join(out, "passage.json")
        if not a.no_timings or not a.no_retime:
            subprocess.run([py, os.path.join(here, "passage_timings.py"), wav, "--lines", pj], check=True)
        if not a.no_retime:
            subprocess.run([py, os.path.join(here, "retime_pauses.py"), wav, "--lines", pj], check=True)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-af",  # re-normalize after edits
                            "loudnorm=I=%g:TP=-1.5:LRA=11" % a.lufs, "-ar", "44100", "-ac", "1", wav + ".tmp.wav"], check=True)
            os.replace(wav + ".tmp.wav", wav)
        if not a.no_timings:
            subprocess.run([py, os.path.join(here, "passage_timings.py"), wav, "--lines", pj, "--split"], check=True)
    print("LINES=%d project=%s" % (len(tim["lines"]), tim.get("project_id")))


if __name__ == "__main__":
    main()
