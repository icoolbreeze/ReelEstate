#!/usr/bin/env python3
"""Verify every presenter matte is frame-synced with its plate segment (same source, in-point, crop, size).
usage: python pipeline/maphub/check_matte.py <EP> [--qa]   -> exit 1 on any mismatch
Checks per footage/heygen/<seg>_alpha.webm: sidecar sha256 == <seg>.mp4, same frame count, same size, and the
mean RGB difference inside the matte (alpha>0.5) vs the plate frame <= 12/255 on every frame (a drifted or frozen matte shows up as
a doubled presenter). --qa writes plate|matte-over-plate|difference grabs at each segment start/end to heygen/qa/."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np

def frames(path, w, h, pix, n_ch, vcodec=None):
    cmd = ["ffmpeg", "-v", "error", *(["-c:v", vcodec] if vcodec else []), "-i", str(path), "-vf", f"scale={w}:{h}", "-pix_fmt", pix, "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE); sz = w * h * n_ch
    while True:
        b = p.stdout.read(sz)
        if len(b) < sz: break
        yield np.frombuffer(b, np.uint8).reshape(h, w, n_ch)

def probe(path):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()
    return tuple(int(v) for v in o.split(",")[:2])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("episode"); ap.add_argument("--qa", action="store_true"); ap.add_argument("--tol", type=float, default=12.0)
    a = ap.parse_args(); ep = Path(a.episode); fd = ep / "footage/heygen"; bad = 0
    for alpha in sorted(fd.glob("*_alpha.webm")):
        seg = alpha.name[:-len("_alpha.webm")]; plate = fd / f"{seg}.mp4"; side = alpha.with_suffix(".json"); errs = []
        if not plate.is_file(): errs.append("no plate")
        else:
            if not side.is_file() or json.loads(side.read_text(encoding="utf-8")).get("source_sha256") != hashlib.sha256(plate.read_bytes()).hexdigest():
                errs.append("sidecar sha256 != plate (matte is from another split)")
            if probe(plate) != probe(alpha): errs.append(f"size {probe(alpha)} != plate {probe(plate)}")
            P = list(frames(plate, 360, 270, "rgb24", 3)); A = list(frames(alpha, 360, 270, "rgba", 4, "libvpx-vp9"))
            if len(P) != len(A): errs.append(f"frames {len(A)} != plate {len(P)}")
            worst = (0, -1)
            for i, (p, m) in enumerate(zip(P, A)):
                k = m[..., 3] > 128
                d = float(np.abs(p.astype(int) - m[..., :3].astype(int)).mean(-1)[k].mean()) if k.any() else 0.0
                worst = max(worst, (d, i))
            if worst[0] > a.tol: errs.append(f"diff {worst[0]:.1f} at frame {worst[1]} > {a.tol}")
            if a.qa and P and A:
                from PIL import Image
                q = ep / "heygen/qa"; q.mkdir(parents=True, exist_ok=True)
                for tag, i in (("start", 0), ("end", min(len(P), len(A)) - 1)):
                    p, m = P[i], A[i]; al = m[..., 3:4] / 255.0
                    comp = (p * (1 - al) * 0.35 + m[..., :3] * al).astype(np.uint8)
                    diff = np.clip(np.abs(p.astype(int) - m[..., :3].astype(int)) * (al > 0.5) * 4, 0, 255).astype(np.uint8)
                    Image.fromarray(np.hstack([p, comp, diff])).save(q / f"{seg}_{tag}.jpg", quality=85)
        print(seg, "OK" if not errs else "FAIL: " + "; ".join(errs)); bad += bool(errs)
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
