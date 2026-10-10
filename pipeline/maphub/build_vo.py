#!/usr/bin/env python3
"""TTS voiceover + timeline + audio mix for a map-hub episode.

usage: python pipeline/build_vo.py episodes/ep07-xihu [--proj proj] [--voice zh-CN-YunjianNeural] [--rate +18%]
Reads  <episode>/script.json (+ episode.json, pois.json)
Writes <proj>/public/episode/vo/<line>.mp3, <proj>/public/episode/mix.wav,
       <proj>/src/episode/timeline.json   (frame-accurate lines, caption chunks, click cues)
       <episode>/script_timed.md          (human-readable script with timings/layouts)
Requires: edge-tts (pip install edge-tts), ffmpeg on PATH, numpy.
Muse presenter clips carry their own audio but are NOT lip-synced, so the final mix is TTS-only;
presenter clips are used muted as visuals (rules/RULES.md §3).
"""
import argparse, asyncio, json, os, re, subprocess, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parent.parent   # ReelEstate repo root (pipeline/maphub/..)
SR, FPS = 48000, 30
OPENER_FRAMES = 240          # opener comp length; first non-opener line starts after it
CLICK_LEAD = 20              # click this many frames before an `enter` line; clip finishes opening ~9 f into the line (proj CLICK: glide 24, pause 9, press 11, open 18, close 18)
SHOTCRAFT = Path(os.environ.get("SHOTCRAFT_DIR", REPO / "vendor/video-shotcraft"))

def sh(*a, **k):
    return subprocess.run(list(map(str, a)), capture_output=True, check=True, **k)

async def _synth(text, voice, rate, mp3):
    import edge_tts
    c = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as fh:
        async for ch in c.stream():
            if ch["type"] == "audio":
                fh.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"t": ch["text"], "s": ch["offset"] / 1e7, "e": (ch["offset"] + ch["duration"]) / 1e7})
    return words

VOICE_DIR = None   # --voice-dir: pre-made (cloned) wavs <id>.wav replace edge-tts; captions fall back to linear timing

def tts(text, voice, rate, outdir, lid):
    mp3, js = outdir / f"{lid}.mp3", outdir / f"{lid}.json"
    if VOICE_DIR and (VOICE_DIR / f"{lid}.wav").exists():
        src = VOICE_DIR / f"{lid}.wav"
        sh("ffmpeg", "-y", "-v", "error", "-i", src, "-ar", "48000", "-b:a", "256k", mp3)
        dur = float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp3, text=True).stdout)
        j = {"text": text, "rate": "clone", "voice": "clone:" + src.parent.name, "words": [], "dur": dur}
        js.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8"); return j
    if js.exists():
        j = json.loads(js.read_text(encoding="utf-8"))
        if j.get("text") == text and j.get("rate") == rate and j.get("voice") == voice and mp3.exists():
            return j
    for k in range(6):
        try:
            words = asyncio.run(_synth(text, voice, rate, mp3)); break
        except Exception as e:
            print("tts retry", lid, k, type(e).__name__); time.sleep(2 + 3 * k)
    else:
        raise RuntimeError(f"edge-tts failed for {lid}")
    dur = float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp3, text=True).stdout)
    j = {"text": text, "rate": rate, "voice": voice, "words": words, "dur": dur}
    js.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    return j

def load(p, ch=1):
    raw = sh("ffmpeg", "-v", "error", "-i", p, "-ac", ch, "-ar", SR, "-f", "f32le", "-").stdout
    a = np.frombuffer(raw, np.float32).astype(np.float64)
    return a if ch == 1 else a.reshape(-1, ch)

def char_time(words, text, dur):
    """map char index in `text` -> seconds using word boundaries (fallback: linear)."""
    pos, marks = 0, []
    for w in words:
        i = text.find(w["t"], pos)
        if i < 0:
            continue
        marks.append((i, w["s"])); marks.append((i + len(w["t"]), w["e"])); pos = i + len(w["t"])
    if not marks:
        return lambda c: dur * c / max(1, len(text))
    xs, ys = zip(*marks)
    return lambda c: float(np.interp(c, xs, ys))

def norm_cap(s):
    return re.sub(r"[，。；：、！？,.;:!?\s]", "", s)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--voice-dir", default=None, help="dir of cloned <line id>.wav (normalized) used instead of edge-tts")
    ap.add_argument("--script", default="script.json", help="script file inside the episode dir (e.g. script_v2.json)")
    ap.add_argument("--proj", default=str(REPO / "templates/map-hub/remotion"))
    ap.add_argument("--voice"); ap.add_argument("--rate")
    ap.add_argument("--bgm", default=str(SHOTCRAFT / "assets/audio/bgm/house-vibez.mp3"))
    ap.add_argument("--opener-sfx", default="", help="wav laid at t=0 under the opener (e.g. multiplane-opener/out/sfx_v4.wav)")
    a = ap.parse_args()
    epd, proj = Path(a.episode), Path(a.proj)
    global VOICE_DIR; VOICE_DIR = Path(a.voice_dir) if a.voice_dir else None
    S = json.loads((epd / a.script).read_text(encoding="utf-8"))
    voice, rate = a.voice or S["voice"], a.rate or S["rate"]
    vodir = proj / "public/episode/vo"; vodir.mkdir(parents=True, exist_ok=True)
    (proj / "src/episode").mkdir(parents=True, exist_ok=True)

    lines, t = [], 0.0
    for L in S["lines"]:
        j = tts(L["tts"], voice, rate, vodir, L["id"])
        t += L.get("gap", 0.3)
        if L["layout"] != "OPENER" and lines and lines[-1]["layout"] == "OPENER":
            t = max(t, OPENER_FRAMES / FPS + 0.15)
        start = t; end = t + j["dur"]
        f0 = round(start * FPS)
        ct = char_time(j["words"], L["tts"], j["dur"])
        # caption chunks: locate each chunk's start in the tts text by matching normalised chars proportionally
        caps, ntts, acc = [], norm_cap(L["tts"]), 0
        total = sum(len(norm_cap(c)) for c in L["cap"])
        for c in L["cap"]:
            frac0 = acc / total; acc += len(norm_cap(c)); frac1 = acc / total
            caps.append({"text": c, "f0": f0 + round(ct(frac0 * len(L["tts"])) * FPS), "f1": f0 + round(ct(frac1 * len(L["tts"])) * FPS)})
        rec = {k: v for k, v in L.items() if k not in ("tts", "cap", "gap")}
        rec.update(f0=f0, f1=round(end * FPS), dur=round(j["dur"], 3), caps=caps, audio=f"episode/vo/{L['id']}.mp3", tts=L["tts"])
        if L.get("enter"):
            rec["click"] = f0 - CLICK_LEAD
        if L.get("insert"):   # cut-away inside a map line: cursor clicks `mark`, clip opens from it at caption chunk `cap`, closes at line end
            ins = dict(L["insert"]); fi = caps[ins.get("cap", 0)]["f0"] - 4
            ins.update(f0=fi, click=fi - CLICK_LEAD, f1=min(round(end * FPS) - 4, fi + ins.get("dur", 60))); rec["insert"] = ins
        lines.append(rec); t = end
    # each line's visual holds until the next line starts (last line + 1.2 s tail)
    for i, r in enumerate(lines):
        r["v0"] = 0 if i == 0 else r["f0"] - (lines[i]["f0"] - lines[i - 1]["f1"])  # visual starts in the gap before the line
    for i, r in enumerate(lines):
        r["v1"] = lines[i + 1]["v0"] if i + 1 < len(lines) else r["f1"] + 36
    for r in lines:   # entering lines: visual (clip) starts at the line start; the gap belongs to the map/click
        if r.get("click") is not None:
            r["v0"] = r["f0"]
    for i in range(1, len(lines)):
        if lines[i]["layout"] != "OPENER" and lines[i - 1]["layout"] == "OPENER":
            lines[i]["v0"] = max(lines[i]["v0"], OPENER_FRAMES)   # the opener always plays to its last frame
        lines[i - 1]["v1"] = lines[i]["v0"]
    total = lines[-1]["v1"]
    tl = {"fps": FPS, "width": 1440, "height": 1080, "total": total, "opener": OPENER_FRAMES, "voice": voice, "rate": rate, "lines": lines}
    # optional on-camera hook BEFORE the opener (own audio file; the main mix stays aligned to the opener at frame 0 of the main comp)
    if S.get("hook"):
        Hk = S["hook"]; j = tts(Hk["tts"], voice, rate, vodir, Hk["id"])
        lead = 0.25; f0 = round(lead * FPS); ct = char_time(j["words"], Hk["tts"], j["dur"])
        caps, acc, tot = [], 0, sum(len(norm_cap(c)) for c in Hk["cap"])
        for c in Hk["cap"]:
            fr0 = acc / tot; acc += len(norm_cap(c)); fr1 = acc / tot
            caps.append({"text": c, "f0": f0 + round(ct(fr0 * len(Hk["tts"])) * FPS), "f1": f0 + round(ct(fr1 * len(Hk["tts"])) * FPS)})
        hf = round((lead + j["dur"] + 0.35) * FPS)
        tl["hook"] = {**{k: v for k, v in Hk.items() if k not in ("cap",)}, "f0": f0, "f1": f0 + round(j["dur"] * FPS), "dur": round(j["dur"], 3), "frames": hf, "caps": caps, "audio": f"episode/vo/{Hk['id']}.mp3"}
        sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", str(hf / FPS), "-i", f"anullsrc=r={SR}:cl=stereo", "-i", vodir / f"{Hk['id']}.mp3",
           "-filter_complex", f"[1]adelay={int(lead*1000)}|{int(lead*1000)},aresample={SR},loudnorm=I=-16:TP=-1.5:LRA=7[v];[0][v]amix=inputs=2:duration=first:normalize=0", "-ar", SR, proj / "public/episode/hook.wav")
    (proj / "src/episode/timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- mix: VO + bgm bed + click/whoosh cues + optional opener sfx ----
    n = int(total / FPS * SR) + SR
    vo = np.zeros(n)
    for r in lines:
        x = load(vodir / f"{r['id']}.mp3"); i = int(r["f0"] / FPS * SR); vo[i:i + len(x)] += x[: n - i]
    fx = np.zeros(n)
    def put(p, frame, g):
        if not Path(p).exists(): return
        x = load(p); i = int(frame / FPS * SR); fx[i:i + len(x)] += g * x[: n - i]
    sfx = SHOTCRAFT / "assets/audio/sfx"
    for r in lines:
        if r.get("click") is not None:
            # mouse-click read at the ripple frame; the swoosh waits until the clip-open frame (click + CLICK.press)
            put(sfx / "ui/ui-select-click.mp3", r["click"], 0.4)
            put(sfx / "transition/swoosh-slow.mp3", r["click"] + 11, 0.2)
        if r["layout"] == "B":
            put(sfx / "data/data-scan.mp3", r["v0"] + 6, 0.10)
        if r.get("insert"):
            put(sfx / "ui/ui-select-click.mp3", r["insert"]["click"], 0.4)
            put(sfx / "transition/swoosh-slow.mp3", r["insert"]["click"] + 11, 0.2)
            put(sfx / "data/data-scan.mp3", r["insert"]["f0"] + 6, 0.10)
    if a.opener_sfx and Path(a.opener_sfx).exists():
        fx[: min(n, len(load(a.opener_sfx)))] += 0.8 * load(a.opener_sfx)[:n]
    bed = np.zeros(n)
    if Path(a.bgm).exists():
        b = load(a.bgm); reps = int(np.ceil(n / len(b))); bed = np.tile(b, reps)[:n]
        # duck under voice: envelope of VO (50 ms smoothing)
        k = int(0.05 * SR); env = np.convolve(np.abs(vo), np.ones(k) / k, "same")
        duck = np.where(env > 0.01, 0.10, 0.18)
        duck = np.convolve(duck, np.ones(int(0.25 * SR)) / int(0.25 * SR), "same")
        fade = np.minimum(1, np.arange(n) / SR / 1.0) * np.minimum(1, (n - np.arange(n)) / SR / 2.0)
        bed = bed * duck * fade
    mix = vo + fx + bed
    raw = proj / "public/episode/mix_raw.wav"
    import wave
    st = np.clip(np.stack([mix, mix], 1), -1, 1)
    with wave.open(str(raw), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype("<i2").tobytes())
    sh("ffmpeg", "-y", "-v", "error", "-i", raw, "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-ar", SR, proj / "public/episode/mix.wav")
    raw.unlink()

    # ---- human-readable timed script ----
    md = ["# 口播稿（带时间、版式）· " + epd.name, "", f"TTS {voice} {rate}；总长 {total} 帧 = {total / FPS:.1f}s。房源信息全部为**示例数据**。", "",
          "| 行 | 时间 (s) | 版式 | 画面 | 进入方式 | 台词 |", "|---|---|---|---|---|---|"]
    a_frames = 0
    for r in lines:
        if r["layout"] in ("A",): a_frames += r["v1"] - r["v0"]
        vis = {"OPENER": "开场（多层景深→扫描→滑动变焦进地图）", "A": f"主持人全屏 {r.get('clip','')}", "END": f"总结面板 + 主持人小窗 {r.get('clip','')}", "PIP": f"地图（{r.get('cam','')}）+ 主持人小窗",
               "MAP": f"地图（{r.get('cam','')}）", "B": f"B-roll {r.get('clip','')} + 扫描标注"}[r["layout"]]
        if r.get("insert"): vis += f"；{r['insert']['f0']/FPS:.1f}s 起插入 {r['insert']['clip']}（点击 {r['insert']['mark']}）"
        md.append(f"| {r['id']} | {r['v0']/FPS:.1f}–{r['v1']/FPS:.1f} | {r['layout']} | {vis} | {'光标点击 ' + r['enter'] if r.get('enter') else ''} | {r['tts']} |")
    md += ["", f"主持人全屏占比 {100 * a_frames / total:.0f}%（地图段另有小窗）。"]
    (epd / "script_timed.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"total {total} f = {total / FPS:.1f}s; A share {100 * a_frames / total:.0f}%")

if __name__ == "__main__":
    main()
