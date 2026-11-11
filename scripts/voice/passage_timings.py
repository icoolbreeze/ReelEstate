#!/usr/bin/env python3
"""Per-line timings for a whole-passage voiceover (flova_minimax passage mode).

Usage: python scripts/voice/passage_timings.py DIR/passage.wav [--lines DIR/passage.json] [--split] [--model small]
- faster-whisper word timestamps on the wav (initial_prompt = script, so numerals come out as written).
- Fuzzy character alignment (difflib) of Whisper characters to the script characters in passage.json order;
  mishearings (换城/换乘) still align by position, unmatched script characters get interpolated times.
- Writes DIR/timings.json: {"audio": ..., "audio_sha256": ..., "duration": s, "lines": [{"id","text","start","end"}],
  "chars": [{"line","c","s","e"}]}.
- --split (default in the pipeline): also cuts DIR/<id>.wav per line (cut in the middle of the inter-line gap)
  plus DIR/<id>.json word sidecars {audio_sha256, text, words:[{t,s,e}]} in the format
  pipeline/maphub/voice_timing.read_alignment expects (build_vo.py --alignment-dir DIR)."""
import argparse, difflib, hashlib, json, os, re, sys, unicodedata
import numpy as np, soundfile as sf

DIG = "零一二三四五六七八九"


def cn_num(n):
    n = int(n)
    if n < 10: return DIG[n]
    out, units, s = "", ["", "十", "百", "千", "万"], str(n)
    for i, d in enumerate(s):
        p = len(s) - 1 - i; d = int(d)
        if d: out += DIG[d] + units[p]
        elif out and not out.endswith("零"): out += "零"
    out = out.rstrip("零")
    return out[1:] if out.startswith("一十") else out


def norm_chars(text):
    text = unicodedata.normalize("NFKC", str(text))
    text = re.sub(r"\d+", lambda m: cn_num(m.group()) if len(m.group()) <= 5 else m.group(), text)
    return [c for c in text.lower() if c.isalnum()]


def sha(p):
    h = hashlib.sha256(); h.update(open(p, "rb").read()); return h.hexdigest()


def load_lines(path):
    d = json.load(open(path, encoding="utf-8-sig"))
    return [l if isinstance(l, dict) else {"id": "line%02d" % (i + 1), "text": l} for i, l in enumerate(d["lines"])]


def transcribe(audio, prompt, model="small"):
    from faster_whisper import WhisperModel
    from scipy.signal import resample_poly
    a, sr = sf.read(audio, dtype="float32")
    a = a.mean(1) if a.ndim > 1 else a
    a16 = resample_poly(a, 16000, sr).astype("float32") if sr != 16000 else a
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(a16, language="zh", word_timestamps=True, initial_prompt=prompt[:200], vad_filter=True)
    hyp = []  # (char, s, e)
    for s in segs:
        for w in s.words:
            cs = norm_chars(w.word)
            for i, c in enumerate(cs):
                d = (w.end - w.start) / max(len(cs), 1)
                hyp.append((c, w.start + i * d, w.start + (i + 1) * d))
    return hyp, len(a) / sr


def align(lines, hyp):
    ref = [(li, c) for li, l in enumerate(lines) for c in norm_chars(l["text"])]
    sm = difflib.SequenceMatcher(None, [c for _, c in ref], [c for c, _, _ in hyp], autojunk=False)
    t = [None] * len(ref)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1): t[i1 + k] = hyp[j1 + k][1:]
        elif op == "replace" and j2 > j1:  # uneven: spread hyp span over ref span
            s0, e0 = hyp[j1][1], hyp[j2 - 1][2]
            for k in range(i2 - i1):
                t[i1 + k] = (s0 + (e0 - s0) * k / (i2 - i1), s0 + (e0 - s0) * (k + 1) / (i2 - i1))
    known = [i for i, x in enumerate(t) if x]
    if not known: raise SystemExit("alignment failed: no characters matched")
    for i in range(len(t)):  # interpolate gaps (deleted / unheard chars)
        if t[i] is None:
            prev = max([k for k in known if k < i], default=None); nxt = min([k for k in known if k > i], default=None)
            a = t[prev][1] if prev is not None else t[nxt][0]; b = t[nxt][0] if nxt is not None else t[prev][1]
            lo = prev if prev is not None else i - 1; hi = nxt if nxt is not None else i + 1
            step = (b - a) / (hi - lo); t[i] = (a + step * (i - lo - 1) + 0, a + step * (i - lo))
    ratio = sm.ratio()
    return [{"line": li, "c": c, "s": round(x[0], 3), "e": round(max(x[1], x[0] + 0.01), 3)} for (li, c), x in zip(ref, t)], ratio


def run(audio, lines_path, split=False, model="small", out_dir=None):
    lines = load_lines(lines_path)
    prompt = "".join(l["text"] for l in lines)
    hyp, dur = transcribe(audio, prompt, model)
    chars, ratio = align(lines, hyp)
    out_dir = out_dir or os.path.dirname(os.path.abspath(audio))
    res = {"audio": os.path.basename(audio), "audio_sha256": sha(audio), "duration": round(dur, 3),
           "match_ratio": round(ratio, 3), "whisper_text": "".join(c for c, _, _ in hyp), "lines": [], "chars": chars}
    for li, l in enumerate(lines):
        cs = [c for c in chars if c["line"] == li]
        res["lines"].append({"id": l["id"], "text": l["text"], "start": cs[0]["s"], "end": cs[-1]["e"]})
    json.dump(res, open(os.path.join(out_dir, "timings.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if split:
        a, sr = sf.read(audio)
        L = res["lines"]
        for i, l in enumerate(L):
            t0 = 0.0 if i == 0 else (L[i - 1]["end"] + l["start"]) / 2
            t1 = dur if i == len(L) - 1 else (l["end"] + L[i + 1]["start"]) / 2
            f = os.path.join(out_dir, l["id"] + ".wav")
            sf.write(f, a[int(t0 * sr):int(t1 * sr)], sr)
            words = [{"t": c["c"], "s": round(max(c["s"] - t0, 0), 3), "e": round(c["e"] - t0, 3)}
                     for c in chars if c["line"] == i]
            for k in range(1, len(words)):  # enforce monotonic for read_alignment
                words[k]["s"] = max(words[k]["s"], words[k - 1]["e"])
                words[k]["e"] = max(words[k]["e"], words[k]["s"] + 0.005)
            json.dump({"audio_sha256": sha(f), "text": l["text"], "words": words},
                      open(os.path.join(out_dir, l["id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("audio"); ap.add_argument("--lines")
    ap.add_argument("--split", action="store_true"); ap.add_argument("--model", default="small")
    a = ap.parse_args()
    lp = a.lines or os.path.join(os.path.dirname(os.path.abspath(a.audio)), "passage.json")
    r = run(a.audio, lp, a.split, a.model)
    print("match_ratio=%.3f lines=%d duration=%.2fs" % (r["match_ratio"], len(r["lines"]), r["duration"]))
    for l in r["lines"]: print("%-10s %7.2f %7.2f %s" % (l["id"], l["start"], l["end"], l["text"][:30]))
