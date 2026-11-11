"""Load and validate a knowledge-series episode (projects/knowledge/epNN-<slug>).

Shared helpers are imported from pipeline/maphub (read_yaml / fingerprint) — no duplication.
The episode.yaml schema (knowledge):
  id, series: knowledge, episode, category: knowledge, topic, title, city (default 成都),
  presenter, oncam_budget_s (55), total_target_s (80-90), script_md, research,
  voice_defaults {engine, model, voice, tempo, mode}, heygen {look, oncam_max_s},
  render {size, fps, lufs, on_screen_notes}, broll_dirs {flova, muse, screens},
  segments: [{n, id, type: oncam|voiceover, name, text, est_s, broll: [{ref, kind, desc}],
              process: [step, ...], cards: [{value, sub}], end: bool}]
No listing / map / POI fields — knowledge episodes never have them.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SERIES = REPO / "projects" / "knowledge"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from pipeline.common.voice_config import read_yaml  # noqa: E402  (shared with map-hub)
from pipeline.common.voice_timing import fingerprint  # noqa: E402  (shared with map-hub)

SEG_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,15}$")
BROLL_KINDS = ("screens", "muse", "flova")
SEG_TYPES = ("oncam", "voiceover")
READING_CPS = 4.6          # Chinese chars per second at presenter tempo 1.1 (estimate only)
MIN_S, MAX_S = 2.0, 40.0
BANNED_TEXT = ("——", "--")
BANNED_WORDS = ("最", "第一", "唯一")


def episode_path(value) -> Path:
    ep = Path(value)
    if not ep.is_absolute():
        candidate = REPO / ep
        ep = candidate if candidate.exists() else SERIES / str(value)
    ep = ep.resolve()
    if SERIES.resolve() not in ep.parents:
        raise ValueError("episode must be inside projects/knowledge: %s" % ep)
    if not (ep / "episode.yaml").is_file():
        raise ValueError("missing episode.yaml: %s" % ep)
    return ep


def text_check(text: str, where: str) -> None:
    for bad in BANNED_TEXT:
        if bad in text:
            raise ValueError("%s: 不要用 %s（会被读出来）；用 ，或 ……" % (where, bad))
    for bad in BANNED_WORDS:
        if bad in text:
            raise ValueError("%s: 含违禁词 %r（无最/第一/唯一；见 RUNBOOK 脚本规则）" % (where, bad))


def load_episode(value) -> tuple[Path, dict, list[dict]]:
    """-> (episode dir, parsed episode.yaml, validated segments)."""
    ep = episode_path(value)
    cfg = read_yaml(ep / "episode.yaml")
    if str(cfg.get("series") or "knowledge") != "knowledge":
        raise ValueError("%s 不是 knowledge series（series: %s）— 请走 map-hub 流水线" % (ep.name, cfg.get("series")))
    for key in ("topic", "title"):
        if not str(cfg.get(key) or "").strip():
            raise ValueError("episode.yaml 缺 %s" % key)
    raw = cfg.get("segments")
    if not isinstance(raw, list) or not raw:
        raise ValueError("episode.yaml 需要非空 segments 列表")
    segments, seen = [], set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError("segments[%d] 必须是对象" % i)
        seg = dict(item)
        sid = str(seg.get("id") or "S%02d" % (i + 1))
        if not SEG_ID.fullmatch(sid) or sid in seen:
            raise ValueError("segment id 不安全或重复: %s" % sid)
        seen.add(sid)
        seg["id"] = sid
        seg["n"] = int(seg.get("n") or i + 1)
        stype = str(seg.get("type") or "").strip()
        if stype not in SEG_TYPES:
            raise ValueError("%s: type 只能是 oncam / voiceover" % sid)
        seg["type"] = stype
        text = str(seg.get("text") or "").strip()
        if not text:
            raise ValueError("%s: 缺口播 text" % sid)
        text_check(text, sid)
        seg["text"] = text
        est = seg.get("est_s")
        if est is None:
            est = len(re.sub(r"[，。；：、！？,.;:!?\s…]", "", text)) / READING_CPS
        est = float(est)
        if not MIN_S <= est <= MAX_S:
            raise ValueError("%s: est_s 超出合理范围 (%s)" % (sid, est))
        seg["est_s"] = round(est, 2)
        broll = seg.get("broll") or []
        if stype == "voiceover" and not broll and not seg.get("process"):
            raise ValueError("%s: voiceover 段需要 broll 或 process" % sid)
        refs = []
        for b in broll:
            b = dict(b)
            if str(b.get("kind") or "") not in BROLL_KINDS:
                raise ValueError("%s: broll kind 只能是 screens/muse/flova" % sid)
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,15}", str(b.get("ref") or "")):
                raise ValueError("%s: broll ref 不安全: %s" % (sid, b.get("ref")))
            refs.append(b)
        seg["broll"] = refs
        segments.append(seg)
    oncam = sum(s["est_s"] for s in segments if s["type"] == "oncam")
    budget = float(cfg.get("oncam_budget_s", 55))
    if oncam > budget:
        raise ValueError("露脸段合计 %.1fs 超过 oncam_budget_s %.0fs" % (oncam, budget))
    return ep, cfg, segments


def summary(cfg: dict, segments: list[dict]) -> dict:
    oncam = [s for s in segments if s["type"] == "oncam"]
    return {
        "segments": len(segments),
        "oncam": len(oncam),
        "voiceover": len(segments) - len(oncam),
        "est_total_s": round(sum(s["est_s"] for s in segments), 1),
        "est_oncam_s": round(sum(s["est_s"] for s in oncam), 1),
        "oncam_budget_s": float(cfg.get("oncam_budget_s", 55)),
        "total_target_s": float(cfg.get("total_target_s", 85)),
    }

