#!/usr/bin/env python3
"""Resolve IndexTTS narration and push it to Kaggle; F5 remains an explicit backup."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/kaggle"))
from _common import episode_dir
sys.path.insert(0, str(REPO / "scripts/kaggle/kernels"))
from tts_indextts25 import plan_lines
sys.path.insert(0, str(REPO / "pipeline/maphub"))
from voice_config import prepare_narration

def _inside_repo(path):
    path = path.resolve()
    if REPO.resolve() not in path.parents:
        raise SystemExit("path must be inside the repo")
    return path

def _resolve_file(raw, *bases):
    path = Path(raw)
    choices = [path] if path.is_absolute() else [Path(base) / path for base in bases]
    for choice in choices:
        if choice.is_file():
            return _inside_repo(choice)
    raise SystemExit("file not found: %s" % path.name)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--run", default="indextts25")
    parser.add_argument("--emotion-ref", action="append", default=[], help="additional emotion wavs inside the repo")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--param", action="append", default=[])
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.run):
        raise SystemExit("unsafe run name")
    episode = episode_dir(args.episode)
    script = _resolve_file(args.script, Path.cwd(), REPO)
    data = json.loads(script.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        data = {"lines": data}
    params = {}
    for item in args.param:
        if "=" not in item:
            raise SystemExit("--param must be key=value")
        key, value = item.split("=", 1)
        params[key] = value
    for key in ("speed", "seed"):
        if key in params:
            data[key] = params[key]
    try:
        resolved, voice = prepare_narration(episode, data)
        plan_lines(resolved, {"lang": params.get("lang", "ZH")})
    except (ValueError, TypeError) as exc:
        raise SystemExit(str(exc))
    ref = _resolve_file(resolved["ref_wav"], script.parent, REPO)
    inputs = {ref.name: ref}
    for raw in args.emotion_ref:
        path = _resolve_file(raw, script.parent, REPO)
        if path.name in inputs and inputs[path.name] != path:
            raise SystemExit("duplicate input filename: %s" % path.name)
        inputs[path.name] = path
    for line in resolved["lines"]:
        name = line.get("emo_ref")
        if not name:
            continue
        if name != Path(name).name:
            raise SystemExit("emo_ref must be a filename")
        if name not in inputs:
            extra = voice.get("emo_ref_wav")
            path = _resolve_file(extra if extra and Path(extra).name == name else name,
                                 script.parent, ref.parent, REPO)
            if path.name != name:
                raise SystemExit("emotion reference filename mismatch")
            inputs[name] = path
    params.update(ref=ref.name, script="resolved_%s.json" % args.run)
    params.setdefault("lang", "ZH")
    if args.dry_run:
        print(json.dumps({"episode": episode.name, "run": args.run, "inputs": sorted(inputs),
                          "params": params, "resolved": resolved}, ensure_ascii=False, indent=2))
        return
    target = episode / "voice" / params["script"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(resolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    cmd = [sys.executable, str(REPO / "scripts/kaggle/push_job.py"),
           "--episode", str(episode), "--job", "tts", "--kernel", "tts_indextts25",
           "--run", args.run, "--accelerator", "NvidiaTeslaT4",
           "--inputs", *map(str, inputs.values()), str(target)]
    for key, value in params.items():
        cmd += ["--param", "%s=%s" % (key, value)]
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("next: python scripts/kaggle/pull_job.py --episode %s --job tts --run %s" % (args.episode, args.run))
    raise SystemExit(result.returncode)

if __name__ == "__main__":
    main()
