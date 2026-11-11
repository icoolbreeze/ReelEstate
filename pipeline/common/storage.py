"""Measure unique file identities; compact verified derivatives without touching originals."""
import argparse
import hashlib
import json
import os
import sys
import uuid
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from pipeline.common.episodes import list_episodes
from pipeline.common.workspace import episode_path

MEDIA = {".mp4", ".mov", ".webm", ".wav", ".mp3", ".png", ".jpg", ".jpeg", ".woff2", ".ttf"}
PROTECTED = {"raw", "consent", "original", "originals", "clone"}


def linked(path):
    return path.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(path))


def walk_files(root):
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not linked(Path(base) / d)]
        for name in names:
            path = Path(base) / name
            if not linked(path):
                yield path


def measure(ep):
    groups = defaultdict(int)
    identities = set()
    logical = unique = count = 0
    for path in walk_files(ep):
        stat = path.stat()
        size = stat.st_size
        groups[path.relative_to(ep).parts[0]] += size
        logical += size
        count += 1
        identity = (stat.st_dev, stat.st_ino)
        if identity not in identities:
            unique += size
            identities.add(identity)
    return {"path": ep.relative_to(REPO).as_posix(), "files": count,
            "logical_bytes": logical, "unique_bytes": unique,
            "groups": dict(sorted(groups.items(), key=lambda x: -x[1]))}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def eligible(ep, path):
    rel = path.relative_to(ep)
    return path.suffix.lower() in MEDIA and not PROTECTED.intersection(rel.parts)


def compact_groups(ep):
    """Only generated public copies and closed draft exports may be consolidated."""
    by_size = defaultdict(list)
    roots = ("footage", "broll", "voice", "public", "out/drafts")
    for root in roots:
        folder = ep / root
        if not folder.is_dir():
            continue
        for path in walk_files(folder):
            if eligible(ep, path) and path.stat().st_size >= 1024 * 1024:
                by_size[path.stat().st_size].append(path)
    groups = []
    for size, paths in by_size.items():
        if len(paths) < 2 or len({(p.stat().st_dev, p.stat().st_ino) for p in paths}) < 2:
            continue
        hashes = defaultdict(list)
        for path in paths:
            hashes[sha256(path)].append(path)
        for digest, same in hashes.items():
            if len(same) < 2:
                continue
            # Originals/working masters keep their current inode. Only a derivative
            # public copy or another draft filename may become a hardlink.
            masters = [p for p in same if p.relative_to(ep).parts[0] in ("footage", "broll", "voice")]
            source = sorted(masters or same, key=lambda p: p.as_posix())[0]
            targets = [p for p in same if p != source and (
                p.relative_to(ep).parts[0] == "public" or
                (not masters and p.relative_to(ep).parts[:2] == ("out", "drafts")))]
            targets = [p for p in targets if not os.path.samefile(source, p)]
            if targets:
                groups.append({"source": source, "targets": targets, "sha256": digest, "bytes": size})
    return groups


def build_directories(ep):
    candidates = list((ep / "work/remotion").glob("build*"))
    candidates += list((ep / "work").glob("build_*"))
    for path in candidates:
        if path.is_dir() and not linked(path) and (path / "index.html").is_file() and (path / "bundle.js").is_file():
            yield path


def remove_generated_tree(path):
    # Do not traverse Windows junctions or file/directory symlinks in public/.
    for child in path.iterdir():
        if linked(child):
            if child.is_symlink():
                child.unlink()
            else:
                os.rmdir(child)
        elif child.is_dir():
            remove_generated_tree(child)
        else:
            child.unlink()
    path.rmdir()


def compact(ep, apply=False):
    before = measure(ep)
    # Existing data/config must not refer to a generated bundle before removal.
    refs = []
    for path in walk_files(ep):
        rel = path.relative_to(ep)
        if rel.parts[0] in ("work", "out", "qa", "jobs"):
            continue
        if path.suffix in (".json", ".yaml") and path.stat().st_size < 2 * 1024 * 1024:
            refs.append(path.read_text(encoding="utf-8-sig", errors="replace").replace("\\", "/"))
    removed, skipped = [], []
    for path in build_directories(ep):
        rel = path.relative_to(ep).as_posix()
        if any(rel in text for text in refs):
            skipped.append(rel)
            continue
        removed.append(rel)
        if apply:
            remove_generated_tree(path)
    groups = compact_groups(ep)
    changes = []
    for group in groups:
        source = group["source"]
        for target in group["targets"]:
            entry = {"source": source.relative_to(ep).as_posix(), "target": target.relative_to(ep).as_posix(),
                     "sha256": group["sha256"], "bytes": group["bytes"]}
            if apply:
                # Recheck content immediately before mutation; preserve every path.
                if sha256(source) != group["sha256"] or sha256(target) != group["sha256"]:
                    raise ValueError("asset changed during compaction: " + str(target))
                temporary = target.with_name(".%s.%s.link" % (target.name, uuid.uuid4().hex))
                try:
                    os.link(source, temporary)
                    os.replace(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)
            changes.append(entry)
    after = measure(ep) if apply else None
    return {"applied": apply, "before": before, "after": after,
            "reclaimed_bytes": before["unique_bytes"] - after["unique_bytes"] if after else None,
            "removed_builds": removed, "referenced_builds_kept": skipped, "consolidated": changes}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("audit", "compact"))
    ap.add_argument("episode", nargs="?")
    ap.add_argument("--apply", action="store_true", help="apply the reviewed plan; default is read-only")
    ap.add_argument("--report", help="JSON report path inside this repo")
    args = ap.parse_args()
    eps = [episode_path(args.episode)] if args.episode else list_episodes(REPO)
    if args.action == "compact" and not args.episode:
        raise ValueError("compact requires an explicit episode")
    result = [measure(ep) if args.action == "audit" else compact(ep, args.apply) for ep in eps]
    if args.report:
        path = (REPO / args.report).resolve()
        if REPO not in path.parents:
            raise ValueError("report must stay inside this repository")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # Console output stays compact; the optional report retains the full path manifest.
    print(json.dumps([{k: v for k, v in row.items() if k != "consolidated"} | (
        {"consolidated_files": len(row["consolidated"])} if "consolidated" in row else {})
        for row in result], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
