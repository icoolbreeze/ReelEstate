"""Word timestamps tied to the actual wav, with normalized caption character mapping."""
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path

def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKC", str(text)).lower() if c.isalnum())

def read_alignment(audio, text, directory=None):
    sidecar = (Path(directory) / (Path(audio).stem + ".json")) if directory else Path(audio).with_suffix(".json")
    if not sidecar.is_file():
        return []
    data = json.loads(sidecar.read_text(encoding="utf-8-sig"))
    if data.get("audio_sha256") != fingerprint(audio):
        raise ValueError("stale word timestamps for %s; align the current wav again" % Path(audio).name)
    if normalized(data.get("text", "")) != normalized(text):
        raise ValueError("timestamps belong to a different script: %s" % Path(audio).name)
    words = []
    previous = 0.0
    for word in data.get("words", []):
        token = str(word.get("t", word.get("word", ""))).strip()
        start = float(word.get("s", word.get("start", -1)))
        end = float(word.get("e", word.get("end", -1)))
        if not token or not all(math.isfinite(x) for x in (start, end)) or start < previous or end <= start:
            raise ValueError("invalid word timestamps in %s" % sidecar.name)
        words.append({"t": token, "s": start, "e": end})
        previous = end
    if not words or normalized("".join(w["t"] for w in words)) != normalized(text):
        raise ValueError("word transcript does not match narration; review %s" % sidecar.name)
    return words

def caption_frames(text, captions, words, duration, f0, fps, spans=None, allow_estimated=False):
    """Exact text spans use real speech edges; editorial captions use word-boundary interpolation."""
    cleaned = normalized(text)
    if not cleaned or not captions or any(not normalized(c) for c in captions):
        raise ValueError("narration and captions must be nonempty")
    starts, ends = [], []
    for word in words:
        count = len(normalized(word["t"]))
        for i in range(count):
            starts.append(word["s"] + (word["e"] - word["s"]) * i / count)
            ends.append(word["s"] + (word["e"] - word["s"]) * (i + 1) / count)
    if words and len(starts) != len(cleaned):
        raise ValueError("word transcript length differs from narration")
    exact = "".join(normalized(c) for c in captions) == cleaned
    if not exact and spans is None and not allow_estimated:
        raise ValueError("editorial captions need cap_spans (normalized character offsets), or use --draft")
    if spans is not None and len(spans) != len(captions):
        raise ValueError("cap_spans count must match captions")
    result, position, weight = [], 0, 0
    total = sum(len(normalized(c)) for c in captions)
    for index, caption in enumerate(captions):
        count = len(normalized(caption))
        a = position if exact else round(weight * len(cleaned) / total)
        weight += count
        b = position + count if exact else round(weight * len(cleaned) / total)
        position = b
        if spans is not None:
            a, b = spans[index]
            if not isinstance(a, int) or not isinstance(b, int) or not 0 <= a < b <= len(cleaned):
                raise ValueError("invalid cap_spans offsets")
        a = min(a, len(cleaned) - 1); b = min(max(a + 1, b), len(cleaned))
        start = starts[a] if words else duration * a / len(cleaned)
        end = ends[b - 1] if words else duration * b / len(cleaned)
        result.append({"text": caption, "f0": f0 + round(start * fps), "f1": f0 + round(end * fps)})
    return result

def require_clone_files(script, directory):
    ids = [x["id"] for x in script.get("lines", [])]
    if script.get("hook"):
        ids.append(script["hook"]["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate voice line IDs")
    missing = [lid for lid in ids if not (Path(directory) / (lid + ".wav")).is_file()]
    if missing:
        raise ValueError("missing cloned wavs: %s; generate them with IndexTTS or explicitly select F5" % ", ".join(missing))
