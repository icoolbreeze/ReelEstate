"""Read-only production readiness check; never calls a paid service or renders."""
import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from pipeline.common.episodes import list_episodes, next_release_number
from pipeline.common.workspace import episode_path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("episode", nargs="?")
    ap.add_argument("--draft", action="store_true")
    args = ap.parse_args()
    checks = {name: bool(shutil.which(name)) for name in ("node", "ffmpeg", "ffprobe")}
    checks.update({"python_" + name: importlib.util.find_spec(name) is not None for name in ("yaml", "numpy", "PIL")})
    for rel in ("tools/remotion/node_modules/@remotion/cli/package.json", "tools/remotion/node_modules/typescript/bin/tsc", "templates/listing/episode.json", "templates/listing/compliance.example.json", "templates/shared/remotion/src/fonts.ts", "templates/shared/remotion/src/ScanAnnotate.tsx", "templates/interview/remotion/src/index.ts", "docs/PRODUCTION.md", "docs/RUNBOOK-interview.md"):
        checks[rel] = (REPO / rel).is_file()
    report = {"pass": all(checks.values()), "python_executable": sys.executable, "checks": checks,
              "episodes": [ep.relative_to(REPO).as_posix() for ep in list_episodes(REPO)],
              "next_release_number": next_release_number(REPO), "handoff": "docs/PRODUCTION.md",
              "external_steps": "CRM 登录/素材取用、TTS、HeyGen、可选 Kaggle 按需使用既有账号；本检查不会代替这些步骤。"}
    if args.episode:
        ep = episode_path(args.episode)
        cmd = [sys.executable, "-B", str(REPO / "pipeline/video.py"), "check", str(ep)]
        if args.draft:
            cmd.append("--draft")
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            report["episode_check"] = json.loads(proc.stdout)
        except ValueError:
            report["episode_check"] = {"error": proc.stdout + proc.stderr}
        report["pass"] = report["pass"] and proc.returncode == 0
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
