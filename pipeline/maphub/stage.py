#!/usr/bin/env python3
"""Point the shared map-hub Remotion template at ONE episode (run before any build_vo / sync_assets / render).

usage: python pipeline/maphub/stage.py projects/map-hub/<ep>

Creates (Windows: directory junctions, no admin needed; elsewhere: symlinks):
  templates/map-hub/remotion/public        -> <ep>/public
  templates/map-hub/remotion/src/episode   -> <ep>/data
  <ep>/public/fonts, <ep>/public/brands    -> templates/map-hub/shared/public/{fonts,brands}
So every generated file (vo, mix.wav, timeline.json, footage copies, room stills) lands inside the episode folder,
and the template itself holds code only. Both links are gitignored. Re-run to switch episodes.
"""
import os, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TPL = REPO / "templates/map-hub/remotion"
SHARED = REPO / "templates/map-hub/shared/public"

def link(dst: Path, src: Path):
    src = src.resolve(); src.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or (dst.exists() and os.path.isjunction(dst) if hasattr(os.path, "isjunction") else False):
        dst.unlink() if dst.is_symlink() else os.rmdir(dst)
    elif dst.exists():
        try: os.rmdir(dst)                               # junction on older Pythons / empty dir
        except OSError: sys.exit(f"{dst} exists and is a real folder - move it into the episode first")
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)], check=True, capture_output=True)
    else:
        dst.symlink_to(src, target_is_directory=True)
    print(f"{dst.relative_to(REPO)} -> {src}")

def main():
    if len(sys.argv) != 2: sys.exit(__doc__)
    ep = Path(sys.argv[1]).resolve()
    if not (ep / "episode.json").exists(): sys.exit(f"no episode.json in {ep}")
    for d in ("data", "public", "footage", "annotations", "out", "voice", "heygen"): (ep / d).mkdir(exist_ok=True)
    link(TPL / "public", ep / "public")
    link(TPL / "src/episode", ep / "data")
    for d in ("fonts", "brands"): link(ep / "public" / d, SHARED / d)
    (TPL / ".current-episode").write_text(str(ep), encoding="utf-8")
    print("staged", ep.name)

if __name__ == "__main__":
    main()
