#!/usr/bin/env python3
"""Retime pauses in a whole-passage voiceover to chat-style targets (offline, no credits).

Usage: python scripts/voice/retime_pauses.py DIR/passage.wav [--timings DIR/timings.json] [--out DIR/passage.wav]
       [--sent 0.42] [--comma 0.31] [--section 0.6] [--jitter 0.15] [--seed 7]
Needs timings.json from passage_timings.py (script-aligned character times). For every punctuation gap
(。！？ -> --sent, ，、；： -> --comma, line/section boundary -> --section or the line's "pause_after" in
passage.json, e.g. a longer pause after the hook) the silence is resized to target × (1 ± jitter, fixed seed).
Never cuts speech: only the low-energy core of a gap is edited (60 ms guard after the previous char, 40 ms before
the next, plus an energy check); lengthening loops room tone from that gap; every join has a 30 ms crossfade.
Writes the new wav and DIR/retime_report.json (before/after per gap). Re-run passage_timings.py afterwards."""
import argparse, json, os, random
import numpy as np, soundfile as sf

SENT, COMMA = set("。！？!?…"), set("，,、；;：:")
GUARD_PRE, GUARD_POST, XF = 0.06, 0.04, 0.03


def punct_after(text):
    """For each alnum char index (normalized order) -> punctuation that follows it (or '')."""
    import unicodedata, re
    from passage_timings import cn_num
    t = unicodedata.normalize("NFKC", text)
    t = re.sub(r"\d+", lambda m: cn_num(m.group()) if len(m.group()) <= 5 else m.group(), t)
    out = []
    for ch in t.lower():
        if ch.isalnum(): out.append("")
        elif out and (ch in SENT or ch in COMMA) and not out[-1]: out[-1] = ch
    return out


def xfade(a, b, sr):
    n = min(int(XF * sr), len(a), len(b))
    if n <= 0: return np.concatenate([a, b])
    r = np.linspace(0, 1, n)
    return np.concatenate([a[:-n], a[-n:] * (1 - r) + b[:n] * r, b[n:]])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("audio"); ap.add_argument("--timings"); ap.add_argument("--lines")
    ap.add_argument("--out"); ap.add_argument("--sent", type=float, default=0.42); ap.add_argument("--comma", type=float, default=0.31)
    ap.add_argument("--section", type=float, default=0.6); ap.add_argument("--jitter", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    d = os.path.dirname(os.path.abspath(a.audio))
    T = json.load(open(a.timings or os.path.join(d, "timings.json"), encoding="utf-8"))
    lp = a.lines or os.path.join(d, "passage.json")
    lines = json.load(open(lp, encoding="utf-8-sig"))["lines"] if os.path.exists(lp) else T["lines"]
    x, sr = sf.read(a.audio); x = x.mean(1) if x.ndim > 1 else x
    chars = T["chars"]; rnd = random.Random(a.seed)
    marks = []
    for li, l in enumerate(lines):
        marks += punct_after(l["text"] if isinstance(l, dict) else l)
    assert len(marks) == len(chars), "timings do not match passage.json text"
    rms_all = np.sqrt(np.mean(x ** 2)); thr = rms_all * 0.12
    gaps = []
    for k in range(len(chars) - 1):
        c, n = chars[k], chars[k + 1]
        boundary = c["line"] != n["line"]
        p = marks[k]
        if not (boundary or p): continue
        if boundary:
            l = lines[c["line"]]
            tgt = float(l.get("pause_after", a.section)) if isinstance(l, dict) else a.section
            kind = "section"
        else:
            tgt, kind = (a.sent, "sent") if p in SENT else (a.comma, "comma")
        tgt *= 1 + rnd.uniform(-a.jitter, a.jitter)
        s0, s1 = c["e"] + GUARD_PRE, n["s"] - GUARD_POST
        gaps.append(dict(k=k, kind=kind, punct=p, before=round(n["s"] - c["e"], 3), target=round(tgt, 3), s0=s0, s1=s1))
    out, pos, report = [], 0, []
    for g in gaps:
        i0, i1 = int(g["s0"] * sr), int(g["s1"] * sr)
        core = x[i0:i1] if i1 > i0 else np.zeros(0)
        cur = g["before"]
        delta = g["target"] - cur
        quiet = len(core) > int(0.02 * sr) and np.sqrt(np.mean(core ** 2)) < thr
        if not quiet or abs(delta) < 0.02 or (delta < 0 and len(core) + int(delta * sr) < int(3 * XF * sr)):
            g["after"] = cur; g["action"] = "kept" if quiet else "kept_not_silent"; report.append(g); continue
        seg = x[pos:i0]
        if delta < 0:  # shorten: drop the middle of the quiet core
            keep = len(core) + int(delta * sr) + 2 * int(XF * sr); h = keep // 2
            new_core = xfade(core[:h + int(XF * sr)], core[len(core) - (keep - h):], sr)
        else:  # lengthen: loop room tone from this core
            need = len(core) + int(delta * sr) + 2 * int(XF * sr); tone = core
            while len(tone) < need: tone = xfade(tone, core, sr)
            new_core = tone[:need]
        out.append(seg if not out else seg); out.append(new_core); pos = i1
        g["after"] = round(cur + (len(new_core) - len(core)) / sr - 2 * XF, 3); g["action"] = "retimed"; report.append(g)
    out.append(x[pos:])
    y = out[0]
    for part in out[1:]: y = xfade(y, part, sr) if len(part) > int(XF * sr) and len(y) > int(XF * sr) else np.concatenate([y, part])
    dst = a.out or a.audio
    sf.write(dst, y, sr)
    for g in report: g.pop("s0"); g.pop("s1")
    json.dump({"source": os.path.basename(a.audio), "seed": a.seed, "targets": {"sent": a.sent, "comma": a.comma, "section": a.section, "jitter": a.jitter},
               "duration_before": round(len(x) / sr, 3), "duration_after": round(len(y) / sr, 3), "gaps": report},
              open(os.path.join(os.path.dirname(os.path.abspath(dst)), "retime_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = sum(g["action"] == "retimed" for g in report)
    print("retimed %d/%d gaps, %.2fs -> %.2fs -> %s" % (n, len(report), len(x) / sr, len(y) / sr, dst))


if __name__ == "__main__":
    main()
