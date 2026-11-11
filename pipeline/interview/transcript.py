"""Import a corrected transcript. This module does not invent speech and does not call a model."""
import json
from pathlib import Path

from pipeline.interview.timebase import require_ms

TRACK_SPEAKER = {"interviewer_audio": "interviewer", "guest_audio": "guest"}


def resolve_speaker(span, roles):
    track = span.get("track")
    from_track = TRACK_SPEAKER.get(roles.get(track or ""))
    stated = span.get("speaker")
    if stated not in (None, "", "interviewer", "guest", "unknown"):
        raise ValueError("unknown speaker label: %s" % stated)
    if from_track and stated in ("interviewer", "guest") and stated != from_track:
        return "unknown", "待确认"
    if from_track:
        return from_track, None
    if stated in ("interviewer", "guest"):
        return stated, None
    return "unknown", "待确认"


def load_corrected(path, roles=None):
    path = Path(path)
    if not path.is_file():
        return {"status": "pending_transcript", "completed": False, "fixture": False, "spans": [],
                "note": "没有 transcript/corrected.json。不编造转录。现有 align_voice 只对齐已有稿，不能把采访提纲套成字幕。"}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("invented") is True:
        raise ValueError("refusing an invented transcript")
    roles = roles or {}
    spans = []
    for index, row in enumerate(data.get("spans") or []):
        start = require_ms(row.get("source_in_ms"), "spans[%d].source_in_ms" % index)
        end = require_ms(row.get("source_out_ms"), "spans[%d].source_out_ms" % index)
        if end <= start:
            raise ValueError("transcript span out point must be exclusive and after the in point")
        speaker, note = resolve_speaker(row, roles)
        text = str(row.get("text") or "").strip()
        if not text:
            raise ValueError("transcript span has no text")
        spans.append({
            "id": str(row.get("id") or "t%02d" % (index + 1)),
            "speaker": speaker,
            "speaker_note": note,
            "text": text,
            "source_in_ms": start,
            "source_out_ms": end,
            "track": row.get("track"),
            "source_id": row.get("source_id"),
        })
    return {"status": "corrected", "completed": True, "fixture": bool(data.get("fixture")),
            "source": data.get("source") or "human", "spans": spans}
