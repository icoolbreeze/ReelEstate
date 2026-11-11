#!/usr/bin/env python3
"""Render map-hub from an isolated workspace after technical preflight."""
import argparse
import hashlib
import re
import json
import shutil
import subprocess
from workspace import stage_episode, episode_path
from check_episode import check_episode
from pipeline.common.rendering import atomic_output

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode")
    parser.add_argument("--composition", choices=("MapHubHeygen", "MapHubKoubo"), default="MapHubHeygen")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--still", type=int, metavar="FRAME")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--platform", choices=("douyin", "shipinhao"), default="shipinhao", help="final -> out/release/<episode>_<platform>.mp4")
    parser.add_argument("--ver", default="v1", help="draft/still folder: out/drafts/<ver>/")
    parser.add_argument("--presenter-placeholder", action="store_true", help="DRAFT ONLY: HeyGen export not generated yet; freeze presenter frames with a ????? tag and waive ONLY the HeyGen-sync + matte checks (logged)")
    parser.add_argument("--dry-run", action="store_true", help="print the output path and command only")
    parser.add_argument("--badge", help="final export only: top-right badge rows, e.g. douyin or shipinhao (default: one row, the --platform one; shipinhao = 视频号)")
    args = parser.parse_args()
    if args.concurrency < 1:
        raise SystemExit("concurrency must be positive")
    ep = episode_path(args.episode)
    # Output convention (docs/CONVENTIONS-shared.md section 1)
    if args.still is not None:
        target = ep / "out" / "drafts" / args.ver / ("%s_f%d.png" % (args.composition, args.still))
    elif args.draft:
        target = ep / "out" / "drafts" / args.ver / ("draft_%s_%s.mp4" % (args.composition, args.platform))
    else:
        target = ep / "out" / "release" / ("%s_%s.mp4" % (ep.name, args.platform))
    if args.presenter_placeholder and not args.draft:
        raise SystemExit("--presenter-placeholder is only allowed with --draft")
    props = "--props=" + json.dumps({"platform": args.platform, **({"layerAudit": True} if args.still is not None and args.composition == "MapHubHeygen" else {}), **({"badge": args.badge} if args.badge else {}), **({"presenterPlaceholder": True} if args.presenter_placeholder else {})})
    if args.still is not None:
        tail = ["still", "src/index.ts", args.composition, str(target), "--frame=%d" % args.still, "--log=verbose", props]
    else:
        tail = ["render", "src/index.ts", args.composition, str(target), "--gl=angle", "--concurrency=%d" % args.concurrency, props]
    if args.dry_run:
        print("+ npx remotion " + " ".join(tail))
        return
    report = check_episode(ep, args.draft, args.composition == "MapHubHeygen")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    waived = []
    if args.presenter_placeholder:   # guard itself unchanged; only HeyGen-sync errors are waived for this placeholder draft
        waived = [e for e in report["errors"] if e.startswith("HeyGen segments belong") or e.startswith("HeyGen plan is stale") or e.startswith("HeyGen segment changed")]
        report["errors"] = [e for e in report["errors"] if e not in waived]
        report["pass"] = not report["errors"]
        import datetime
        target.parent.mkdir(parents=True, exist_ok=True)
        msg = "%s PRESENTER PLACEHOLDER draft %s: waived %s; check_matte skipped" % (datetime.datetime.now().isoformat(timespec="seconds"), target.name, waived)
        print("WARNING:", msg)
        with open(target.parent / "guard_bypass.log", "a", encoding="utf-8") as fh: fh.write(msg + "\n")
    if not report["pass"]:
        raise SystemExit(1)
    # presenter matte must be frame-synced with its plate segment (see check_matte.py); a stale matte = doubled presenter
    import sys
    from pathlib import Path
    mc = subprocess.CompletedProcess([], 0) if args.presenter_placeholder else subprocess.run([sys.executable, str(Path(__file__).with_name("check_matte.py")), str(ep), "--qa"])
    if mc.returncode:
        raise SystemExit("presenter matte out of sync with its plate: re-run matte_avatar.py on the current segment (heygen/qa/ has grabs)")
    work = stage_episode(ep)
    overlay_check = subprocess.run([sys.executable, str(Path(__file__).with_name("check_overlay_motion.py")), str(ep)])
    if overlay_check.returncode:
        raise SystemExit("shared overlay motion checks failed; fix before rendering")
    pub = work / "public/footage/heygen"   # drop build copies of mattes that no longer exist in the episode (e.g. moved to stale/)
    for m in (pub.glob("*_alpha.webm") if pub.is_dir() else []):
        if not (ep / "footage/heygen" / m.name).is_file():
            m.unlink(); print("removed stale build matte", m.name)
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx or not (work / "node_modules").is_dir():
        raise SystemExit("install the template's Remotion dependencies first")
    target.parent.mkdir(parents=True, exist_ok=True)
    with atomic_output(target) as pending:
        render_tail = list(tail)
        render_tail[3] = str(pending)
        if args.still is not None and args.composition == "MapHubHeygen":
            capture = subprocess.run([npx, "remotion", *render_tail], cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace")
            print(capture.stdout)
            if capture.returncode:
                print(capture.stderr)
                raise SystemExit(capture.returncode)
        else:
            subprocess.run([npx, "remotion", *render_tail], cwd=work, check=True)
    if args.still is not None and args.composition == "MapHubHeygen":
        records = [json.loads(x) for x in re.findall(r"HARMONY_LAYERS:(\{[^\r\n]*\})", capture.stdout + capture.stderr)]
        match = [record for record in records if record["frame"] == args.still]
        if not match:
            raise SystemExit("missing measured foreground/world metadata for the still")
        metadata = match[-1]
        metadata["image_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        target.with_suffix(".layers.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(target)
    if args.still is None:
        print("Rendered. Run the runbook's loudness, motion, still-frame and manual QA before delivery.")

if __name__ == "__main__":
    main()

