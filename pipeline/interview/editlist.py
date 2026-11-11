"""Edit decisions. Every cut points at an exclusive source range."""
import json
from pathlib import Path

from pipeline.interview.timebase import require_ms

LAYOUTS = ("question", "name", "case", "data")


def load_decisions(path):
    path = Path(path)
    if not path.is_file():
        return {"confirmed": False, "status": "missing", "segments": [], "unit": "ms", "out_point": "exclusive"}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("unit") not in (None, "ms"):
        raise ValueError("edit times must use unit ms")
    if data.get("out_point") not in (None, "exclusive"):
        raise ValueError("edit out point must be exclusive")
    segments = []
    seen = set()
    for index, row in enumerate(data.get("segments") or []):
        ident = str(row.get("id") or "E%02d" % (index + 1))
        if ident in seen:
            raise ValueError("duplicate edit id: %s" % ident)
        seen.add(ident)
        start = require_ms(row.get("source_in_ms"), ident + ".source_in_ms")
        end = require_ms(row.get("source_out_ms"), ident + ".source_out_ms")
        if end <= start:
            raise ValueError("%s source_out_ms must be exclusive and after source_in_ms" % ident)
        if not str(row.get("source_id") or "").strip():
            raise ValueError("%s missing source_id" % ident)
        layout = str(row.get("layout") or "question")
        if layout not in LAYOUTS:
            raise ValueError("%s layout must be question, name, case, or data" % ident)
        if not str(row.get("shot") or "").strip():
            raise ValueError("%s missing shot" % ident)
        segments.append({
            "id": ident,
            "source_id": str(row["source_id"]),
            "source_in_ms": start,
            "source_out_ms": end,
            "shot": str(row["shot"]),
            "layout": layout,
            "speaker": row.get("speaker") or "unknown",
            "card_id": row.get("card_id"),
            "question": row.get("question"),
        })
    return {
        "confirmed": bool(data.get("confirmed")),
        "status": "confirmed" if data.get("confirmed") else "unconfirmed",
        "unit": "ms",
        "out_point": "exclusive",
        "segments": segments,
    }
