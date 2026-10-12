#!/usr/bin/env python3
"""Render map-hub from an isolated workspace after technical preflight."""
import argparse
import json
import shutil
import subprocess
from workspace import stage_episode, episode_path
from check_episode import check_episode

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode")
    parser.add_argument("--composition", choices=("MapHubHeygen", "MapHubKoubo"), default="MapHubHeygen")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--still", type=int, metavar="FRAME")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    if args.concurrency < 1:
        raise SystemExit("concurrency must be positive")
    ep = episode_path(args.episode)
    report = check_episode(ep, args.draft, args.composition == "MapHubHeygen")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["pass"]:
        raise SystemExit(1)
    work = stage_episode(ep)
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx or not (work / "node_modules").is_dir():
        raise SystemExit("install the template's Remotion dependencies first")
    name = ("draft" if args.draft else "final") + "_" + args.composition
    if args.still is not None:
        name += "_f%d.png" % args.still
        argv = [npx, "remotion", "still", "src/index.ts", args.composition, str(ep / "out" / name), "--frame=%d" % args.still]
    else:
        name += ".mp4"
        argv = [npx, "remotion", "render", "src/index.ts", args.composition, str(ep / "out" / name),
                "--gl=angle", "--concurrency=%d" % args.concurrency]
    subprocess.run(argv, cwd=work, check=True)
    print(ep / "out" / name)
    if args.still is None:
        print("Rendered. Run the runbook's loudness, motion, still-frame and manual QA before delivery.")

if __name__ == "__main__":
    main()
