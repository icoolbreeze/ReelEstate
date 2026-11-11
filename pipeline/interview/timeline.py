"""Build the interview composition data from the edit list and corrected speech."""
import json
from pathlib import Path

from pipeline.interview.captions import map_captions
from pipeline.interview.layout import layout_document
from pipeline.interview.timebase import frames_for_span, require_fps


def assemble(cfg, decisions, spans, research, fps):
    fps = require_fps(fps)
    segments = []
    cursor = 0
    for segment in decisions["segments"]:
        start, end = frames_for_span(cursor, cursor + (segment["source_out_ms"] - segment["source_in_ms"]), fps)
        segments.append({
            "id": segment["id"],
            "layout": segment["layout"],
            "shot": segment["shot"],
            "speaker": segment.get("speaker") or "unknown",
            "source_id": segment["source_id"],
            "card_id": segment.get("card_id"),
            "question": segment.get("question"),
            "source_in_ms": segment["source_in_ms"],
            "source_out_ms": segment["source_out_ms"],
            "f0": start,
            "f1": end,
        })
        cursor += segment["source_out_ms"] - segment["source_in_ms"]
    captions, total_ms = map_captions(decisions["segments"], spans, fps)
    total_frames = 0 if not segments else segments[-1]["f1"]
    if total_frames < 1:
        total_frames = fps
    render = cfg.get("render") or {}
    return {
        "series": "interview",
        "show": "小ONE会客厅",
        "fps": fps,
        "width": int(render.get("width") or 1920),
        "height": int(render.get("height") or 1080),
        "total": total_frames,
        "duration_ms": total_ms,
        "time_unit": "ms",
        "out_point": "exclusive",
        "background": render.get("background") or "placeholder",
        "background_match": (render.get("studio") or {}).get("match_status", "no_reference_frame") if render.get("background") != "live" else "live_plate",
        "studio": render.get("studio") or {},
        "technical_test": bool(cfg.get("technical_test")),
        "audio": cfg.get("_audio"),
        "segments": segments,
        "captions": captions,
        "cards": (research or {}).get("cards") or [],
        "questions": (research or {}).get("questions") or [],
        "checklist": (research or {}).get("checklist") or [],
        "guest": cfg.get("guest") or {},
        "region": cfg.get("region") or "待填",
        "topic": cfg.get("topic") or "待填",
    }


def write_timeline(ep, cfg, decisions, spans, research):
    ep = Path(ep)
    fps = require_fps((cfg.get("render") or {}).get("fps") or 30)
    media = None
    if cfg["render"].get("background") != "placeholder":
        from pipeline.interview.production import prepare
        media = prepare(ep, cfg, decisions, spans)
    audio = media["audio"] if media else None
    tone = ep / "audio" / "tech" / "tone.wav"
    if tone.is_file() and media is None:
        from pipeline.common.media import materialize
        destination = ep / "public" / "audio" / "tone.wav"
        destination.parent.mkdir(parents=True, exist_ok=True)
        materialize(tone, destination)
        audio = {"src": "audio/tone.wav", "role": "tech_mix"}
    cfg = dict(cfg)
    cfg["_audio"] = audio
    timeline = assemble(cfg, decisions, spans, research, fps)
    if media:
        timeline["signature"] = media["signature"]
        timeline["sync"] = media["sync"]
        by_id = {row["id"]: row for row in media["clips"]}
        for segment in timeline["segments"]:
            segment.update(by_id[segment["id"]])
        background = (cfg.get("render") or {}).get("background_src")
        if background:
            from pipeline.interview.production import within
            from pipeline.common.media import materialize
            src = within(ep, background)
            dst = ep / "public/studio" / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.resolve() != dst.resolve():
                materialize(src, dst)
            timeline["background_src"] = dst.relative_to(ep / "public").as_posix()
    data = ep / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (data / "layout.json").write_text(json.dumps(layout_document(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    guest = dict(cfg.get("guest") or {})
    guest["region"] = cfg.get("region") or "待填"
    (data / "guest.json").write_text(json.dumps(guest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return timeline
