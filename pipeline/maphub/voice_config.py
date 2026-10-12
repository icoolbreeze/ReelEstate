"""Resolve speaker settings for IndexTTS main and explicitly selected F5 backup."""
import copy
import json
import math
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

def read_yaml(path):
    import yaml
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8-sig")) or {}
    if not isinstance(data, dict):
        raise ValueError("configuration must be an object: %s" % path)
    return data

def resolve_voice(ep):
    episode = read_yaml(Path(ep) / "episode.yaml")
    name = episode.get("presenter") or "cool-breeze"
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
        raise ValueError("unsafe presenter name")
    profile = read_yaml(REPO / "assets/presenter" / name / "presenter.yaml")
    voice = dict(profile.get("voice") or {})
    overrides = (episode.get("presenter_override") or {}).get("voice") or {}
    voice.update(overrides)
    return episode, voice

def prepare_narration(ep, data, engine="indextts25"):
    if engine not in ("indextts25", "f5"):
        raise ValueError("supported main/backup engines: indextts25, f5")
    episode, voice = resolve_voice(ep)
    raw = data if isinstance(data, list) else data.get("lines", [])
    if not isinstance(raw, list):
        raise ValueError("lines must be an array")
    cfg = {} if isinstance(data, list) else copy.deepcopy(data)
    for key in ("ref_wav", "ref_text", "seed", "speed"):
        if cfg.get(key) is not None:
            voice[key] = cfg[key]
    script_name = episode.get("script") or "script.json"
    script_path = (Path(ep) / script_name).resolve()
    if Path(ep).resolve() not in script_path.parents:
        raise ValueError("script must stay inside the episode")
    oncam = set()
    if script_path.is_file():
        script = json.loads(script_path.read_text(encoding="utf-8-sig"))
        if script.get("hook"):
            oncam.add(script["hook"]["id"])
        oncam.update(x["id"] for x in script.get("lines", []) if x.get("onCam") in ("A", "PIP"))
    lines, seen = [], set()
    for i, original in enumerate(raw):
        line = {"id": "L%02d" % (i + 1), "text": original} if isinstance(original, str) else copy.deepcopy(original)
        if not isinstance(line, dict) or not str(line.get("text") or line.get("line") or "").strip():
            raise ValueError("each narration line needs flat text")
        lid = str(line.get("id") or "L%02d" % (i + 1))
        if not re.fullmatch(r"[A-Za-z0-9_-]+", lid) or lid in seen:
            raise ValueError("unsafe or duplicate line id: %s" % lid)
        seen.add(lid)
        line["id"] = lid
        line["text"] = str(line.get("text") or line.get("line"))
        defaults = {"seed": voice.get("seed"),
                    "speed": voice.get("speed", voice.get("speed_oncam" if lid in oncam else "speed_vo", 1.0))}
        for key, value in defaults.items():
            if line.get(key) is None and value is not None:
                line[key] = value
        speed = float(line.get("speed", 1.0))
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError("speed must be positive and finite")
        if engine == "indextts25" and not any(line.get(k) for k in ("emo_ref", "emo_text", "emo_vector")):
            ref = voice.get("emo_ref_wav")
            if ref:
                line["emo_ref"] = Path(ref).name
                line.setdefault("emo_alpha", voice.get("emo_alpha", 1.0))
        lines.append(line)
    if not lines:
        raise ValueError("no narration lines")
    cfg.update(engine=engine, ref_wav=voice.get("ref_wav"), ref_text=voice.get("ref_text"), lines=lines)
    if not cfg.get("ref_wav"):
        raise ValueError("missing speaker reference")
    cfg["resolved"] = {"presenter": episode.get("presenter", "cool-breeze"), "engine": engine,
                       "fallback_engine": voice.get("fallback_engine", "f5"),
                       "fallback_policy": "explicit"}
    return cfg, voice
