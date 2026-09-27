"""Run compliance check, then render with Remotion.

Usage:
  python pipeline/render.py projects/<category>/<id> [--ratio 4x3|3x4|9x16]
  python pipeline/render.py projects/<category>/<id> --still [--frame 45] [--ratio 4x3]
Output: projects/<category>/<id>/output/<id>_<ratio>.mp4 (or .png for --still)
There is intentionally NO option to skip the check.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "check"))
from reel_common import COMPOSITION_NAMES, RATIOS, REPO_ROOT, load_json, resolve_project_dir, save_json, setup_console, strip_comments  # noqa: E402
import check as checker  # noqa: E402

REMOTION_DIR = REPO_ROOT / "remotion"


def build_props(project_dir: Path) -> dict:
    props = strip_comments(load_json(project_dir / "project.json"))
    seg_json = project_dir / "audio" / "segments.json"
    props["audio"] = load_json(seg_json) if seg_json.exists() else []
    if props["audio"]:
        props["ai_voice"] = True
    return props


def npx() -> str:
    exe = shutil.which("npx.cmd") or shutil.which("npx")
    if not exe:
        raise SystemExit("错误：找不到 npx，请安装 Node.js")
    return exe


def main(argv=None, still_default=False) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="检查并渲染")
    ap.add_argument("project")
    ap.add_argument("--ratio", choices=list(RATIOS))
    ap.add_argument("--still", action="store_true", help="只渲染单帧 PNG")
    ap.add_argument("--frame", type=int, default=220, help="--still 时的帧号（默认 220≈第 7 秒）")
    args = ap.parse_args(argv)

    project_dir = resolve_project_dir(args.project)
    report = checker.run(project_dir)
    checker.print_report(project_dir, report)
    if report.failed:
        print("\n⛔ 合规检查未通过，拒绝渲染。请先修改 project.json。", file=sys.stderr)
        return 1

    props = build_props(project_dir)
    ratio = args.ratio or props.get("export", {}).get("default_ratio", "4x3")
    comp = f"{COMPOSITION_NAMES[props['category']]}-{ratio}"
    out_dir = project_dir / "output"
    out_dir.mkdir(exist_ok=True)
    props_file = out_dir / "_render_props.json"
    save_json(props_file, props)

    if not (REMOTION_DIR / "node_modules").exists():
        print("错误：remotion/node_modules 不存在，请先运行 npm run setup", file=sys.stderr)
        return 1

    pid = props.get("id") or project_dir.name
    common = ["src/index.ts", comp]
    if args.still or still_default:
        out = out_dir / f"{pid}_{ratio}_f{args.frame}.png"
        cmd = [npx(), "remotion", "still", *common, str(out), f"--frame={args.frame}"]
    else:
        out = out_dir / f"{pid}_{ratio}.mp4"
        cmd = [npx(), "remotion", "render", *common, str(out), "--codec=h264"]
    cmd += [f"--props={props_file}", f"--public-dir={project_dir}"]
    print(f"\n▶ 渲染 {comp} → {out.relative_to(REPO_ROOT).as_posix()}")
    proc = subprocess.run(cmd, cwd=REMOTION_DIR)
    if proc.returncode != 0:
        print(f"❌ Remotion 渲染失败（exit {proc.returncode}）", file=sys.stderr)
        return proc.returncode
    print(f"✅ 完成：{out.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
