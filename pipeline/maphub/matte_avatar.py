#!/usr/bin/env python3
"""Matte an avatar clip (plain background) into a transparent VP9 webm for the hook's layered layout (person in front of the list).

usage: python pipeline/matte_avatar.py footage/heygen/HG00.mp4 [--out footage/heygen/HG00_alpha.webm] [--model u2net_human_seg]
Runs rembg per frame (pip install "rembg[gpu]" onnxruntime-gpu on the user's PC; CPU works, slower). Plain backgrounds key
cleanly; hair edges are softened by rembg's alpha matting. sync_assets.py picks up <seg>_alpha.webm as clip id "<seg>_alpha".
Portable: pathlib only, ffmpeg on PATH.
"""
import argparse, subprocess, tempfile
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("--out"); ap.add_argument("--model", default="u2net_human_seg"); ap.add_argument("--fps", default="30")
    a = ap.parse_args(); src = Path(a.src); out = Path(a.out) if a.out else src.with_name(src.stem + "_alpha.webm")
    from rembg import new_session, remove
    from PIL import Image
    sess = new_session(a.model)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-r", a.fps, str(td / "f_%05d.png")], check=True)
        for p in sorted(td.glob("f_*.png")):
            remove(Image.open(p), session=sess, alpha_matting=True, post_process_mask=True).save(td / ("a" + p.name[1:]))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", a.fps, "-i", str(td / "a_%05d.png"), "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                        "-b:v", "0", "-crf", "24", "-auto-alt-ref", "0", str(out)], check=True)
    print("->", out)

if __name__ == "__main__":
    main()
