"""Open Remotion Studio with a project's props.

Usage: python pipeline/preview.py projects/<category>/<id>
(no project → opens Studio with built-in sample props)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reel_common import REPO_ROOT, resolve_project_dir, save_json, setup_console  # noqa: E402
from render import build_props, npx  # noqa: E402


def main(argv=None) -> int:
    setup_console()
    argv = sys.argv[1:] if argv is None else argv
    cmd = [npx(), "remotion", "studio", "src/index.ts"]
    if argv:
        project_dir = resolve_project_dir(argv[0])
        props_file = project_dir / "output" / "_render_props.json"
        save_json(props_file, build_props(project_dir))
        cmd += [f"--props={props_file}", f"--public-dir={project_dir}"]
        print("提示：Studio 预览不做合规检查，正式渲染请用 npm run render。")
    return subprocess.run(cmd, cwd=REPO_ROOT / "remotion").returncode


if __name__ == "__main__":
    sys.exit(main())
