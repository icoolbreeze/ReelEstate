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
SHARED = REPO / "templates/shared/public"

def episode_path(value):
    ep = Path(value)
    if not ep.is_absolute():
        candidate = REPO / ep
        if not candidate.exists():
            matches = {p.resolve(): p for p in (REPO / "projects").glob(f"*/{value}") if p.is_dir()}
            if len(matches) > 1:
                raise ValueError("ambiguous episode name; use projects/<kind>/<id>: %s" % value)
            candidate = next(iter(matches)) if matches else REPO / "projects/listing" / ep
        ep = candidate
    ep = ep.resolve()
    if REPO / "projects" not in ep.parents or not (ep / "episode.json").is_file() or not (ep / "episode.yaml").is_file():
        raise ValueError("Only current episodes are supported: require episode.yaml + episode.json under projects/listing, projects/knowledge, or projects/interview")
    return ep

SERIES_TEMPLATE = {"listing": "map-hub", "knowledge": "knowledge", "interview": "interview"}   # templates/map-hub is the listing template

def series_of(ep):
    yaml_path = Path(ep) / "episode.yaml"
    if not yaml_path.is_file():
        return None
    match = re.search(r"(?m)^\s*series:\s*([a-z0-9-]+)", yaml_path.read_text(encoding="utf-8-sig", errors="replace"))
    return match.group(1) if match else None

def template_for(ep):
    """Per-series Remotion template. listing uses the map-hub template. Unknown series is an error."""
    series = series_of(ep)
    if series is None:
        parts = set(Path(ep).resolve().parts)
        if "interview" in parts or "knowledge" in parts:
            raise ValueError("episode.yaml missing series")
        series = "listing"
    if series not in SERIES_TEMPLATE:
        raise ValueError("unknown series: %s; expected listing, knowledge, or interview" % series)
    candidate = REPO / "templates" / SERIES_TEMPLATE[series] / "remotion"
    if not candidate.is_dir():
        raise ValueError("missing remotion template for series %s" % series)
    return candidate

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
    template = template_for(ep)
    work = workspace_path(ep)
    for name in ("data", "public"):        # linked into work/remotion; every other folder is created when first written
        (ep / name).mkdir(exist_ok=True)
    (work / "src").mkdir(parents=True, exist_ok=True)
    files = list(template.glob("*.json")) + list(template.glob("*.ts"))
    files += [p for p in (template / "src").rglob("*") if p.is_file()
              and "episode" not in p.relative_to(template / "src").parts
              and p.suffix in (".ts", ".tsx", ".json")]
    # Both workflows receive the same versioned low-level rendering services.
    shared_src = REPO / "templates/shared/remotion/src"
    digest = hashlib.sha256()
    for src in sorted(set(files)):
        relative = src.relative_to(template)
        content = src.read_bytes()
        digest.update(relative.as_posix().encode() + content)
        dst = work / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.read_bytes() != content:
            dst.write_bytes(content)
    expected = {p.relative_to(template).as_posix() for p in files}
    for src in sorted(shared_src.rglob("*")) if shared_src.is_dir() else []:
        if not src.is_file() or src.suffix not in (".ts", ".tsx", ".json"):
            continue
        relative = Path("src/shared") / src.relative_to(shared_src)
        content = src.read_bytes()
        digest.update(relative.as_posix().encode() + content)
        dst = work / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.read_bytes() != content:
            dst.write_bytes(content)
        expected.add(relative.as_posix())
    # Remove deleted source files, without traversing the episode data link.
    for dst in (work / "src").rglob("*"):
        relative = dst.relative_to(work)
        if "episode" not in relative.parts and dst.is_file() and relative.as_posix() not in expected:
            dst.unlink()
    directory_link(work / "src/episode", ep / "data")
    directory_link(work / "public", ep / "public")
    for nm in (REPO / "tools/remotion/node_modules", template / "node_modules", TEMPLATE / "node_modules"):
        if nm.is_dir():
            directory_link(work / "node_modules", nm)
            break
    for name in ("fonts", "brands", "social"):
        if (SHARED / name).is_dir():
            directory_link(ep / "public" / name, SHARED / name)
    (work / "workspace.json").write_text(json.dumps({
        "episode": ep.name, "template": template.relative_to(REPO).as_posix(),
        "template_sha256": digest.hexdigest(), "shared": "templates/shared/remotion/src",
        "dependency_manifest": "tools/remotion/package-lock.json"
    }, indent=2) + "\n", encoding="utf-8")
    return work

def project_for(ep, explicit=None):
    work = stage_episode(ep)
    if explicit and Path(explicit).resolve() != work.resolve():
        raise ValueError("--proj must be the episode-owned workspace: %s" % work)
    return work


