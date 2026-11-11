"""Production CLI for episode.yaml listing, knowledge, and interview videos."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from pipeline.common.episodes import TEST_PURPOSES, classify_series, list_episodes, next_release_number
from pipeline.common.voice_config import read_yaml
from pipeline.common.workspace import directory_link, episode_path, stage_episode


def run(path, args):
    return subprocess.call([sys.executable, "-B", str(REPO / path), *args], cwd=REPO)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    action = args.pop(0) if args else "help"
    if action == "help":
        print("video.py check|render|still|stage <episode> [existing options]")
        print("video.py restore <episode> [--style Spring|Summer|Autumn|Winter] [--dry-run] [--force] [--assume dlogm] [--encoder prores|x264|nvenc|auto] [--proxy] | restore --scan <folder>")
        print("video.py manifest <episode> [--init] [--check]   (footage/raw_manifest.json: raw clip -> room/shot)")
        print("video.py doctor [episode] [--draft] | typecheck | setup | episodes | audit [episode] | compact <episode> [--apply]")
        print("video.py new rental|resale|new-home|knowledge|interview <slug> [options]")
        return 0
    if action == "new":
        if len(args) < 2:
            raise ValueError("new requires rental|resale|new-home|knowledge|interview <slug> [options]")
        kind, slug, *options = args
        if kind == "knowledge":
            return run("pipeline/knowledge/new_episode.py", ["--slug", slug, *options])
        if kind == "interview":
            return run("pipeline/interview/new_episode.py", ["--slug", slug, *options])
        if kind not in ("rental", "resale", "new-home"):
            raise ValueError("unknown content category: " + kind)
        return run("scripts/new_episode.py", ["--category", kind, "--slug", slug, *options])
    if action == "doctor":
        return run("pipeline/common/doctor.py", args)
    if action in ("audit", "compact"):
        return run("pipeline/common/storage.py", [action, *args])
    if action == "episodes":
        rows = []
        for ep in list_episodes(REPO):
            cfg = read_yaml(ep / "episode.yaml")
            purpose = cfg.get("purpose", "production")
            number = None if purpose in TEST_PURPOSES else cfg.get("release_number", cfg.get("episode"))
            rows.append({"path": ep.relative_to(REPO).as_posix(), "series": cfg.get("series"),
                         "category": cfg.get("category"), "purpose": purpose,
                         "release_number": number})
        print(json.dumps({"episodes": rows, "next_release_number": next_release_number(REPO)}, ensure_ascii=False, indent=2))
        return 0
    if action == "setup":
        runtime = REPO / "tools/remotion"
        if not (runtime / "node_modules").is_dir():
            npm = shutil.which("npm.cmd") or shutil.which("npm")
            if not npm:
                raise ValueError("npm is required")
            subprocess.run([npm, "ci"], cwd=runtime, check=True)
        for kind in ("map-hub", "knowledge", "interview"):   # template folder names (templates/map-hub = listing)
            directory_link(REPO / "templates" / kind / "remotion/node_modules", runtime / "node_modules")
        for ep in list_episodes(REPO):
            stage_episode(ep)
        print("Shared production runtime ready: listing + knowledge + interview.")
        return 0
    if action == "typecheck":
        node = shutil.which("node")
        if not node:
            raise ValueError("Node is required")
        checks = []
        for ep in list_episodes(REPO):
            work = stage_episode(ep)
            checks.append((work, work / "node_modules/typescript/bin/tsc"))
        result = 0
        for work, compiler in checks:
            print("Typecheck:", work.relative_to(REPO), flush=True)
            rc = subprocess.call([node, str(compiler), "--noEmit", "-p", "."], cwd=work)
            result = max(result, rc)
        return result
    if action == "restore" and (not args or args[0].startswith("-")):
        return run("pipeline/common/color_restore.py", args)
    if not args:
        raise ValueError("episode path is required")
    value, options = args[0], args[1:]
    ep = episode_path(value)
    cfg = read_yaml(ep / "episode.yaml")
    route = classify_series(cfg.get("series"))
    if action == "restore":
        return run("pipeline/common/color_restore.py", [str(ep), *options])
    if action == "manifest":
        return run("pipeline/common/raw_manifest.py", [str(ep), *options])
    if action == "stage":
        print(stage_episode(ep))
        return 0
    if action == "check":
        path = {
            "knowledge": "pipeline/knowledge/check_episode.py",
            "interview": "pipeline/interview/check_episode.py",
            "listing": "pipeline/maphub/check_episode.py",
        }[route]
        extra = [] if route != "listing" else ["--heygen"]
        return run(path, [str(ep), *extra, *options])
    if action in ("render", "still"):
        if action == "still":
            if "--frame" not in options:
                raise ValueError("still requires --frame <number>")
            options[options.index("--frame")] = "--still"
        if route == "knowledge":
            return run("pipeline/knowledge/make_video.py", [str(ep), "--step", "render", *options])
        if route == "interview":
            return run("pipeline/interview/make_video.py", [str(ep), "--step", "render", *options])
        return run("pipeline/maphub/render_episode.py", [str(ep), *options])
    raise ValueError("unknown action: " + action)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)

