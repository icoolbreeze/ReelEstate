"""Register interview media with ffprobe. Raw files are only read.

A source row is "probed" only when ffprobe decodes a real stream of the
expected kind (25/30fps video for cameras, an actual audio track for mics).
Missing or invalid required media is a non-zero result, never a silent pass.
"""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.interview import avio

VIDEO_ROLES = {"host_camera", "aux_camera"}
AUDIO_ROLES = {"interviewer_audio", "guest_audio", "room_tone", "program_audio", "tech_mix"}


def probe_item(ep, item):
    rel = item["path"]
    path = Path(ep) / rel
    row = dict(item)
    row["status"] = "missing"
    row["completed"] = False
    if not path.is_file():
        row["status"] = "missing" if item.get("required", True) else "optional_missing"
        return row
    before_ns = path.stat().st_mtime_ns
    info = avio.probe(path)
    if path.stat().st_mtime_ns != before_ns:
        raise RuntimeError("probe changed the source file")
    row["size"] = info.get("size")
    row["duration_ms"] = info.get("duration_ms")
    role = str(item.get("role") or "")
    if not info["valid"]:
        row.update({"status": "probe_failed", "completed": False, "error": info.get("error")})
        return row
    if role in VIDEO_ROLES or (info.get("video") and role not in AUDIO_ROLES):
        video = info["video"]
        if not video:
            row.update({"status": "probe_failed", "completed": False, "error": "缺少视频流"})
            return row
        row.update({"width": video["width"], "height": video["height"], "fps": video["fps"],
                    "video_codec": video["codec"], "pix_fmt": video["pix_fmt"],
                    "has_audio": bool(info.get("audios")), "audio": info["audios"]})
    else:
        row["audio"] = info["audios"]
        if not info["audios"]:
            row.update({"status": "probe_failed", "completed": False, "error": "缺少音轨"})
            return row
    row["status"] = "probed"
    row["completed"] = True
    row["error"] = None
    return row


def load_sources(ep):
    path = Path(ep) / "data" / "media_sources.json"
    if not path.is_file():
        return []
    rows = json.loads(path.read_text(encoding="utf-8-sig"))
    ids = set()
    for row in rows:
        ident = str(row.get("id") or "")
        if not ident or ident in ids:
            raise ValueError("media_sources.json 存在空或重复 id: %r" % ident)
        ids.add(ident)
        if not row.get("path") or Path(str(row["path"])).is_absolute() or ".." in Path(str(row["path"])).parts:
            raise ValueError("media source 路径必须是期内相对路径: %s" % ident)
    return rows


def run_probe(ep, *, write=True):
    rows = [probe_item(ep, item) for item in load_sources(ep)]
    missing = [r["id"] for r in rows if r.get("required", True) and r["status"] != "probed"]
    optional_bad = [r["id"] for r in rows if not r.get("required", True) and r["status"] not in ("probed", "optional_missing")]
    report = {"items": rows, "completed": not missing, "pending": missing,
              "optional_invalid": optional_bad}
    if write:
        target = Path(ep) / "data" / "media.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")
    return report


def probed_index(ep):
    """id -> probed row, from a fresh read-only probe (never trusts a stale media.json)."""
    return {row["id"]: row for row in run_probe(ep, write=False)["items"] if row["status"] == "probed"}


def refuse_raw_write(ep, destination):
    rel = Path(destination).resolve().relative_to(Path(ep).resolve())
    if "raw" in rel.parts:
        raise ValueError("refusing to write into a raw directory: %s" % rel.as_posix())
    return rel
