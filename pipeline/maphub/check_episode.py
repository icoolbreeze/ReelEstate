#!/usr/bin/env python3
"""Technical preflight for map-hub; live listings also pass the existing compliance checker."""
import argparse
import json
import math
import sys
from pathlib import Path
from workspace import episode_path
from voice_config import read_yaml
from voice_timing import fingerprint

REPO = Path(__file__).resolve().parents[2]

def inside_file(ep, relative):
    path = (Path(ep) / relative).resolve()
    if Path(ep).resolve() not in path.parents or not path.is_file():
        raise ValueError("missing or out-of-episode file: %s" % relative)
    return path

def check_episode(value, draft=False, heygen=False):
    ep = episode_path(value)
    errors, warnings = [], []
    data = ep / "data"
    def load(name):
        try:
            return json.loads((data / name).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            errors.append("cannot read data/%s: %s" % (name, type(exc).__name__))
            return {}
    timeline, footage = load("timeline.json"), load("footage.json")
    settings = read_yaml(ep / "episode.yaml")
    if not draft and (timeline.get("draft") or timeline.get("audio_mode") != "clone"):
        errors.append("final render needs cloned narration and current word timestamps; draft audio is not final")
    try:
        script = inside_file(ep, timeline.get("script_file", settings.get("script", "script.json")))
        if timeline.get("script_sha256") != fingerprint(script):
            errors.append("script changed since voice/timeline build; rebuild build_vo and HeyGen plan")
        if settings.get("script") and script.name != settings["script"]:
            errors.append("timeline script differs from episode.yaml")
    except (ValueError, TypeError) as exc:
        errors.append(str(exc))
    fps = timeline.get("fps", 0)
    if not isinstance(fps, (int, float)) or fps <= 0:
        errors.append("invalid timeline fps")
    rows = list(timeline.get("lines", []))
    if timeline.get("hook"):
        rows.append(timeline["hook"])
    if not rows:
        errors.append("empty timeline")
    references = set()
    for row in rows:
        lid = row.get("id", "?")
        if row.get("f1", 0) <= row.get("f0", 0):
            errors.append("invalid speech duration: " + lid)
        if not row.get("caps"):
            errors.append("missing captions: " + lid)
        for cap in row.get("caps", []):
            if cap.get("f1", 0) <= cap.get("f0", 0) or cap.get("f0", 0) < row.get("f0", 0) or cap.get("f1", 0) > row.get("f1", 0) + 1:
                errors.append("caption outside speech span: " + lid)
        if not draft and row.get("caption_timing") != "word":
            errors.append("estimated captions in final: " + lid)
        if row.get("source_audio"):
            try:
                src = (REPO / row["source_audio"]).resolve()
                if REPO not in src.parents or not src.is_file() or fingerprint(src) != row.get("source_sha256"):
                    errors.append("cloned audio changed/missing: " + lid)
            except (OSError, ValueError) as exc:
                errors.append("cannot verify cloned audio: " + lid)
        elif not draft:
            errors.append("missing audio provenance: " + lid)
        try:
            inside_file(ep, "public/" + row.get("audio", ""))
        except ValueError as exc:
            errors.append(str(exc))
        cid = row.get("clip")
        if heygen and row.get("onCam") in ("A", "PIP") and not str(cid).startswith("HG"):
            errors.append("on-camera line is not a HeyGen segment: " + lid)
        if cid:
            references.add(cid)
        if row.get("insert", {}).get("clip"):
            references.add(row["insert"]["clip"])
    for cid in references:
        asset = footage.get(cid, {})
        if asset.get("kind") == "pending" or asset.get("status") in ("pending", "placeholder") or not asset:
            (warnings if draft else errors).append("pending/placeholder footage: " + str(cid))
            continue
        try:
            inside_file(ep, "public/" + asset.get("src", ""))
        except ValueError as exc:
            errors.append(str(exc))
    mix = ep / "public/episode/mix.wav"
    if not mix.is_file():
        errors.append("missing narration mix.wav")
    if timeline.get("hook") and not (ep / "public/episode/hook.wav").is_file():
        errors.append("missing hook.wav")
    if heygen:
        try:
            plan = json.loads((ep / "heygen/segments.json").read_text(encoding="utf-8"))
            split_data = json.loads((ep / "heygen/split_manifest.json").read_text(encoding="utf-8"))
            if split_data.get("plan_sha256") != fingerprint(ep / "heygen/segments.json"):
                errors.append("HeyGen segments belong to another voice plan; split the matching export")
            for cid in references:
                if str(cid).startswith("HG"):
                    asset = footage.get(cid, {})
                    path = inside_file(ep, "public/" + asset.get("src", ""))
                    if split_data.get("segments", {}).get(cid) != fingerprint(path):
                        errors.append("HeyGen segment changed since split: " + str(cid))
            if plan.get("timeline_sha256") != fingerprint(data / "timeline.json"):
                errors.append("HeyGen plan is stale; rerun plan and generate/split the matching avatar")
            budget = float(settings.get("oncam_budget_s", 55))
            if not math.isfinite(budget) or budget <= 0 or float(plan.get("total", 0)) > budget:
                errors.append("HeyGen on-camera budget exceeded")
            if timeline.get("hook"):
                references.add(timeline["hook"]["clip"] + "_alpha")
                matte = footage.get(timeline["hook"]["clip"] + "_alpha", {})
                inside_file(ep, "public/" + matte.get("src", ""))
        except (OSError, ValueError, KeyError) as exc:
            errors.append("invalid HeyGen plan/hook alpha: " + type(exc).__name__)
    episode = json.loads((ep / "episode.json").read_text(encoding="utf-8-sig"))
    if not draft and episode.get("sampleData") is not True and episode.get("category", settings.get("category")) != "knowledge":
        if not (ep / "project.json").is_file():
            errors.append("live listing needs project.json for the existing compliance checker")
        else:
            sys.path.insert(0, str(REPO / "pipeline"))
            sys.path.insert(0, str(REPO / "pipeline/check"))
            import check as checker
            report = checker.run(ep)
            if report.failed:
                errors.append("live listing compliance failed; run npm run check -- " + str(ep.relative_to(REPO)))
    return {"pass": not errors, "draft": draft, "errors": errors, "warnings": warnings}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--heygen", action="store_true")
    args = parser.parse_args()
    report = check_episode(args.episode, args.draft, args.heygen)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["pass"] else 1)

if __name__ == "__main__":
    main()
