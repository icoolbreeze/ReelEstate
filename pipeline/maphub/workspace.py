"""Episode-owned Remotion workspaces; shared template links never switch during a job."""
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "templates/map-hub/remotion"
SHARED = REPO / "templates/map-hub/shared/public"

def episode_path(value):
    ep = Path(value)
    if not ep.is_absolute():
        candidate = REPO / ep
        ep = candidate if candidate.exists() else REPO / "projects/map-hub" / ep
    ep = ep.resolve()
    if REPO / "projects" not in ep.parents or not (ep / "episode.json").is_file():
        raise ValueError("episode must contain episode.json under this repo's projects/")
    return ep

def directory_link(dst, src):
    dst, src = Path(dst), Path(src).resolve()
    if dst.exists() or dst.is_symlink():
        if dst.resolve() == src:
            return
        raise ValueError("refusing to replace an existing path: %s" % dst)
    if not src.is_dir():
        raise ValueError("missing shared directory: %s" % src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)],
                       check=True, capture_output=True)
    else:
        dst.symlink_to(src, target_is_directory=True)

def workspace_path(ep):
    return episode_path(ep) / "work/remotion"

def stage_episode(value):
    ep = episode_path(value)
    work = workspace_path(ep)
    for name in ("data", "public", "footage", "annotations", "out", "voice", "heygen", "jobs"):
        (ep / name).mkdir(exist_ok=True)
    (work / "src").mkdir(parents=True, exist_ok=True)
    files = list(TEMPLATE.glob("*.json")) + list(TEMPLATE.glob("*.ts"))
    files += [p for p in (TEMPLATE / "src").rglob("*") if p.is_file()
              and "episode" not in p.relative_to(TEMPLATE / "src").parts]
    digest = hashlib.sha256()
    for src in sorted(set(files)):
        relative = src.relative_to(TEMPLATE)
        content = src.read_bytes()
        digest.update(relative.as_posix().encode() + content)
        dst = work / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.read_bytes() != content:
            dst.write_bytes(content)
    # Remove deleted template source files, without traversing the episode data link.
    expected = {p.relative_to(TEMPLATE).as_posix() for p in files}
    for dst in (work / "src").rglob("*"):
        relative = dst.relative_to(work)
        if "episode" not in relative.parts and dst.is_file() and relative.as_posix() not in expected:
            dst.unlink()
    directory_link(work / "src/episode", ep / "data")
    directory_link(work / "public", ep / "public")
    if (TEMPLATE / "node_modules").is_dir():
        directory_link(work / "node_modules", TEMPLATE / "node_modules")
    for name in ("fonts", "brands", "social"):
        if (SHARED / name).is_dir():
            directory_link(ep / "public" / name, SHARED / name)
    (work / "workspace.json").write_text(json.dumps({
        "episode": ep.name, "template_sha256": digest.hexdigest()
    }, indent=2) + "\n", encoding="utf-8")
    return work

def project_for(ep, explicit=None):
    work = stage_episode(ep)
    if explicit and Path(explicit).resolve() != work.resolve():
        raise ValueError("--proj must be the episode-owned workspace: %s" % work)
    return work
