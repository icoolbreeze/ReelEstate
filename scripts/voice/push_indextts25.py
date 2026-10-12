#!/usr/bin/env python3
"""Push a narration script to Kaggle T4 for IndexTTS-2.5.

python scripts/voice/push_indextts25.py --episode <episode-dir> --script <narration.json> [--dry-run] [--param k=v]

Does not pull. Does not print Kaggle credentials.
Flat lines only: {"lines": [{"id", "text", "seed"?, "speed"?}]} or a top-level array.
speed > 1 means faster; the kernel converts it to IndexTTS duration_factor = 1/speed.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "kaggle"))
from _common import episode_dir  # noqa: E402

sys.path.insert(0, str(REPO / "scripts" / "kaggle" / "kernels"))
from tts_indextts25 import plan_lines  # noqa: E402


def _inside_repo(path):
    resolved = path.resolve()
    root = REPO.resolve()
    if resolved != root and root not in resolved.parents:
        raise SystemExit("path must be inside the repo: %s" % path)
    return resolved


def _resolve_file(raw, base_hint):
    path = Path(raw)
    if not path.is_absolute():
        candidate = (base_hint / path)
        path = candidate if candidate.is_file() else (REPO / path)
    path = _inside_repo(path)
    if not path.is_file():
        raise SystemExit("file not found: %s" % path)
    return path


def main():
    parser = argparse.ArgumentParser(description="Push IndexTTS-2.5 voice clone to one Kaggle T4")
    parser.add_argument("--episode", required=True, help="episode folder under projects/")
    parser.add_argument("--script", required=True, help="narration.json with flat lines[].text")
    parser.add_argument("--dry-run", action="store_true", help="print the push_job payload and do not upload")
    parser.add_argument("--param", action="append", default=[], help="extra k=v forwarded to the kernel")
    args = parser.parse_args()

    script = _resolve_file(args.script, Path.cwd())
    try:
        data = json.loads(script.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit("script is not JSON: %s" % exc)
    try:
        plan_lines(data, {"lang": "ZH"})
    except SystemExit as exc:
        message = str(exc)
        if message == "no flat text lines to synthesize":
            print(
                "narration has no flat text lines; IndexTTS-2.5 expects lines[].text "
                "(nested variants are not synthesized)",
                file=sys.stderr)
            raise SystemExit(2)
        raise

    ref_raw = None
    if isinstance(data, dict):
        ref_raw = data.get("ref_wav") or data.get("spk_ref")
    ref = _resolve_file(ref_raw or "assets/presenter/cool-breeze/voice/ref_phone_v1.wav", script.parent)
    episode = episode_dir(args.episode)

    params = ["ref=%s" % ref.name, "script=%s" % script.name]
    extra = list(args.param)
    if not any(item.startswith("lang=") for item in extra):
        params.append("lang=ZH")
    params.extend(extra)

    cmd = [
        sys.executable,
        str(REPO / "scripts" / "kaggle" / "push_job.py"),
        "--episode", str(episode),
        "--job", "tts",
        "--kernel", "tts_indextts25",
        "--run", "indextts25",
        "--accelerator", "NvidiaTeslaT4",
        "--inputs", str(ref), str(script),
    ]
    for item in params:
        cmd.extend(["--param", item])
    if args.dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("next: python scripts/kaggle/pull_job.py --episode %s --job tts --run indextts25" % args.episode)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
