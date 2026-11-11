#!/usr/bin/env python3
"""footage/raw_manifest.json: which camera clip in footage/raw/ is which room / shot.

footage/raw/ is read-only and keeps the camera's own file names (DJI_..._D.MP4, phone names,
房间_序号.mp4 all allowed). The mapping to rooms and template shot ids lives next to it in
footage/raw_manifest.json, never inside footage/raw/:

  {"version": 1, "episode": "ep03-bangtai-cangjin",
   "clips": [{"file": "DJI_..._0271_D.MP4", "room": "客厅", "shot": "LR1", "in": 1.2, "out": 6.0,
              "use": "auto", "duration_s": 42.1, "note": ""}]}

use: auto (default, may be picked) | must (must appear) | skip (never used).
shot: template shot id from shots.json; sync_assets uses it when footage/shots/<ID>.mp4 is absent.
in/out: optional seconds; sync_assets then renders a trimmed Rec.709 shot into footage/shots/.

  python pipeline/common/raw_manifest.py <episode> [--init] [--check]
  --init  add every unlisted raw clip (room guessed from 房间_序号 names); existing rows are kept
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = "footage/raw_manifest.json"
RAW = "footage/raw"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".mts"}
USES = ("auto", "must", "skip")
ROOM_NAME = re.compile(r"^(?P<room>[\u4e00-\u9fff]+)_(?P<n>\d{1,2})$")


def raw_clips(ep):
    root = Path(ep) / RAW
    if not root.is_dir():
        return []
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                  if p.is_file() and p.suffix.lower() in VIDEO_EXT and not p.name.startswith("."))


def _read(ep):
    path = Path(ep) / MANIFEST
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else None


def _from_legacy(rows):
    """Pre-2026-10-30 import log: [{"source": phone name, "raw": 房间_序号.mp4, "sha256": ...}]."""
    out, stills = [], []
    for r in rows:
        if not isinstance(r, dict) or not r.get("raw"):
            raise ValueError("unknown legacy raw_manifest row: %r" % (r,))
        if Path(r["raw"]).suffix.lower() not in VIDEO_EXT:          # photos/IMG_*.jpg: import log only
            stills.append({"file": r["raw"], "source_name": r.get("source"), "sha256": r.get("sha256")})
            continue
        m = ROOM_NAME.match(Path(r["raw"]).stem)
        out.append({"file": r["raw"], "room": m["room"] if m else "", "shot": "", "in": None, "out": None, "use": "auto",
                    "source_name": r.get("source"), "sha256": r.get("sha256"), "note": ""})
    return out, stills


def load(ep):
    data = _read(ep)
    if data is None:
        return None
    if isinstance(data, list):
        raise ValueError("footage/raw_manifest.json uses the old import-log list; run: npm run manifest -- <ep> --init (converts it, keeps source names and sha256)")
    if not isinstance(data, dict) or not isinstance(data.get("clips"), list):
        raise ValueError("footage/raw_manifest.json must be an object with a clips list")
    return data


def _duration(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=60)
        return round(float(out.stdout.strip()), 2)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def init(ep, probe=True):
    """Create or extend the manifest with every raw clip not yet listed. Never touches footage/raw/."""
    ep = Path(ep)
    old = _read(ep)
    if isinstance(old, list):                                    # convert the pre-2026-10-30 import log
        clips, stills = _from_legacy(old)
        data = {"version": 1, "episode": ep.name, "clips": clips}
        if stills:
            data["stills"] = stills                              # photos in footage/raw/photos: import log, not clips
    else:
        data = load(ep) or {"version": 1, "episode": ep.name, "clips": []}
    known = {row.get("file") for row in data["clips"]}
    added = 0
    for rel in raw_clips(ep):
        if rel in known:
            continue
        m = ROOM_NAME.match(Path(rel).stem)
        row = {"file": rel, "room": m["room"] if m else "", "shot": "", "in": None, "out": None, "use": "auto"}
        if probe:
            row["duration_s"] = _duration(ep / RAW / rel)
        row["note"] = ""
        data["clips"].append(row)
        added += 1
    data["episode"] = ep.name
    path = ep / MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return data, added


def validate(ep):
    """(errors, warnings). Missing manifest with raw clips present is only a warning."""
    ep = Path(ep)
    errors, warnings = [], []
    clips = raw_clips(ep)
    try:
        data = load(ep)
    except (OSError, ValueError) as exc:
        return ["invalid footage/raw_manifest.json: %s" % exc], []
    if data is None:
        if clips:
            warnings.append("footage/raw has %d clips but no footage/raw_manifest.json - run: npm run manifest -- %s --init"
                            % (len(clips), ep.name))
        return errors, warnings
    present, listed, shots = set(clips), set(), {}
    for i, row in enumerate(data["clips"]):
        name = row.get("file")
        if not name:
            errors.append("raw_manifest clip #%d has no file" % i)
            continue
        if name in listed:
            errors.append("raw_manifest lists %s twice" % name)
        listed.add(name)
        if name not in present:
            errors.append("raw_manifest names a clip that is not in footage/raw: %s" % name)
        if row.get("use", "auto") not in USES:
            errors.append("raw_manifest %s: use must be auto|must|skip" % name)
        t_in, t_out = row.get("in"), row.get("out")
        if t_in is not None and t_out is not None and not (0 <= float(t_in) < float(t_out)):
            errors.append("raw_manifest %s: needs 0 <= in < out" % name)
        shot = row.get("shot")
        if shot:
            if shot in shots:
                errors.append("raw_manifest shot %s is mapped to both %s and %s" % (shot, shots[shot], name))
            shots[shot] = name
    unlisted = sorted(present - listed)
    if unlisted:
        warnings.append("%d raw clips not in footage/raw_manifest.json (run --init): %s%s"
                        % (len(unlisted), ", ".join(unlisted[:3]), " ..." if len(unlisted) > 3 else ""))
    return errors, warnings


def clip_for_shot(ep, shot):
    """(raw path, in, out) for a template shot id, or None. Rows with use=skip are ignored."""
    data = load(ep)
    for row in (data or {}).get("clips", []):
        if row.get("shot") == shot and row.get("use", "auto") != "skip":
            return Path(ep) / RAW / row["file"], row.get("in"), row.get("out")
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode")
    ap.add_argument("--init", action="store_true", help="add unlisted raw clips to the manifest")
    ap.add_argument("--no-probe", action="store_true", help="with --init: skip ffprobe durations")
    ap.add_argument("--check", action="store_true", help="validate only (default when --init is absent)")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(REPO))
    from pipeline.common.workspace import episode_path
    ep = episode_path(a.episode)
    if a.init:
        data, added = init(ep, probe=not a.no_probe)
        print("raw_manifest: %d clips (%d added) -> %s" % (len(data["clips"]), added, MANIFEST))
    errors, warnings = validate(ep)
    print(json.dumps({"pass": not errors, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)
