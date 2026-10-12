#!/usr/bin/env python3
"""HeyGen export -> clean 4:3 (1440x1080) export_43.mp4. Runbook step 7b.

usage:
  python pipeline/maphub/heygen_43.py <episode> [--force] [--qa]

Stages (resumable, files under <EP>/heygen/dewm/):
  1. matte    scripts/matting/matte_local.py heygen/export.mp4 --out heygen/dewm  (MatAnyone2, RVM fallback)
              -> export_check.mp4 (grayscale alpha)
  2. plate    per-pixel median of the background over frames where the presenter is absent -> plate.png
              canvas.png = plate scaled to 1440x810 at the BOTTOM of a 1440x1080 canvas (top 270 px empty)
  3. flova    Python cannot call MCP. If plate_43.png is missing this writes flova_request.json and exits 3.
              The agent calls flova-image generate_image (gpt-image-2.5-sunburst, aspect 4:3, original=true,
              profile kid4, reference_images=[canvas.png]) and saves the result as heygen/dewm/plate_43.png.
              (scripts/flova/mcp_call.py generate_image <request.json> does the MCP call from a shell.)
  4. composite plate_43 is aligned to the original plate (ECC affine on the bottom area), then each frame:
              presenter (scaled x1.125, bottom-anchored) over the clean plate using the alpha.
              HeyGen mark pixels that fall on the presenter are inpainted (cv2 Telea) per frame.
              -> heygen/export_43.mp4 (1440x1080, source fps, original audio)
heygen_plan.py split prefers export_43.mp4 when present. export.mp4 is never modified.
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from heygen_mark import build_mask, probe  # noqa: E402

OW, OH = 1440, 1080
SW, SH = 1280, 720
S = OW / SW                     # 1.125
BH = int(round(SH * S))         # 810
TOP = OH - BH                   # 270
PROMPT = (
    "Edit this photograph of a living room. The bottom part is a real camera frame; the top band is empty. "
    "1) Remove the semi-transparent white HeyGen lettering and the small white logo in the bottom-right corner, "
    "rebuilding the sofa/upholstery underneath with the same soft focus. "
    "2) Outpaint the empty top band upward so the frame becomes a natural 4:3 shot: continue the walls, windows, "
    "ceiling and lighting of the same room, same perspective, same shallow depth of field, same colour grade. "
    "3) The smeared blurry area in the middle is where a person stood; fill it with the empty sofa and room behind it, matching both sides. "
    "Keep everything else in the existing bottom part pixel-identical in position, scale and content. "
    "No people, no text, no letters, no logo, no watermark."
)


def read_gray(cap):
    ok, f = cap.read()
    return cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) if ok else None


def stage_matte(ep: Path, d: Path) -> Path:
    chk = d / "export_check.mp4"
    if not chk.is_file():
        subprocess.run([sys.executable, str(REPO / "scripts/matting/matte_local.py"),
                        str(ep / "heygen/export.mp4"), "--out", str(d)], check=True)
    return chk


def stage_plate(ep: Path, d: Path, chk: Path, force: bool) -> np.ndarray:
    plate_p = d / "plate.png"
    if plate_p.is_file() and not force:
        return cv2.imread(str(plate_p))
    vc, ac = cv2.VideoCapture(str(ep / "heygen/export.mp4")), cv2.VideoCapture(str(chk))
    frames, masks, i = [], [], 0
    k = np.ones((41, 41), np.uint8)
    while True:
        ok, f = vc.read()
        a = read_gray(ac)
        if not ok or a is None:
            break
        if i % 4 == 0:
            a = cv2.resize(a, (f.shape[1], f.shape[0]))
            frames.append(f)
            masks.append(cv2.dilate((a > 8).astype(np.uint8), k) == 0)
        i += 1
    st = np.stack(frames).astype(np.float32)
    valid = np.stack(masks)
    st[~valid] = np.nan
    plate = np.nanmedian(st, axis=0)
    holes = np.isnan(plate).any(2)
    plate = np.nan_to_num(plate).clip(0, 255).astype(np.uint8)
    if holes.any():
        plate = cv2.inpaint(plate, holes.astype(np.uint8) * 255, 7, cv2.INPAINT_TELEA)
    cv2.imwrite(str(plate_p), plate)
    cv2.imwrite(str(d / "plate_holes.png"), holes.astype(np.uint8) * 255)
    canvas = np.full((OH, OW, 3), 128, np.uint8)
    canvas[TOP:] = cv2.resize(plate, (OW, BH), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(str(d / "canvas.png"), canvas)
    json.dump({"never_uncovered_px": int(holes.sum()), "frames_used": len(frames)},
              open(d / "plate.json", "w"), indent=2)
    return plate


def stage_flova(ep: Path, d: Path) -> Path:
    p43 = d / "plate_43.png"
    if p43.is_file():
        return p43
    req = {"prompt": PROMPT, "model": "gpt-image-2.5-sunburst", "aspect_ratio": "4:3", "resolution": "2K",
           "count": 1, "reference_images": [str((d / "canvas.png").resolve())], "original": True,
           "profile": "kid4", "output_dir": str((d / "flova").resolve()), "project_name": f"dewm-{ep.name}"}
    (d / "flova_request.json").write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"need flova: call generate_image with {d/'flova_request.json'} and save the image as {p43}")
    raise SystemExit(3)


def align(plate43: np.ndarray, plate: np.ndarray) -> np.ndarray:
    """Warp plate43 (1440x1080) so its bottom band matches the scaled original plate."""
    plate43 = cv2.resize(plate43, (OW, OH), interpolation=cv2.INTER_AREA)
    ref = cv2.resize(plate, (OW, BH), interpolation=cv2.INTER_LANCZOS4)
    g1 = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY).astype(np.float32)
    full = cv2.cvtColor(plate43, cv2.COLOR_BGR2GRAY).astype(np.float32)
    w = np.eye(2, 3, dtype=np.float32)
    w[1, 2] = TOP                     # plate43 coords = ref coords + (0, TOP)
    init = w.copy()
    try:
        _, w = cv2.findTransformECC(g1, full, w, cv2.MOTION_AFFINE,
                                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), None, 5)
    except cv2.error:
        w = init
    # reject a diverged fit: allow only small scale/shear and <= 24 px shift
    if np.abs(w[:, :2] - np.eye(2)).max() > 0.03 or np.abs(w[:, 2] - init[:, 2]).max() > 24:
        print("ECC fit rejected, using plain placement:", w.tolist())
        w = init
    # map plate43 into output space: out(x, y+TOP) <- plate43(w @ [x, y, 1])
    shift = np.array([[1, 0, 0], [0, 1, -TOP], [0, 0, 1]], np.float32)
    M = np.vstack([w, [0, 0, 1]]) @ shift
    out = cv2.warpAffine(plate43, M[:2], (OW, OH), flags=cv2.INTER_LANCZOS4 | cv2.WARP_INVERSE_MAP,
                         borderMode=cv2.BORDER_REPLICATE)
    # colour-match the bottom band to the original plate (per channel gain)
    gain = ref.reshape(-1, 3).mean(0) / np.maximum(out[TOP:].reshape(-1, 3).mean(0), 1)
    out = (out.astype(np.float32) * gain).clip(0, 255).astype(np.uint8)
    return out, w


def stage_composite(ep: Path, d: Path, chk: Path, plate: np.ndarray, p43: Path, force: bool) -> Path:
    dest = ep / "heygen/export_43.mp4"
    if dest.is_file() and not force:
        print("skip, export_43.mp4 exists")
        return dest
    src = ep / "heygen/export.mp4"
    info = probe(src)
    clean, w = align(cv2.imread(str(p43)), plate)
    cv2.imwrite(str(d / "plate_43_aligned.png"), clean)
    json.dump({"ecc_affine": w.tolist()}, open(d / "align.json", "w"), indent=2)
    vc, ac = cv2.VideoCapture(str(src)), cv2.VideoCapture(str(chk))
    fps = f"{info['fps']:.6f}"
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                            "-s", f"{OW}x{OH}", "-r", fps, "-i", "-", "-i", str(src), "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest",
                            str(dest)], stdin=subprocess.PIPE)
    cf = clean.astype(np.float32)
    n = hits = 0
    while True:
        ok, f = vc.read()
        a = read_gray(ac)
        if not ok or a is None:
            break
        a = cv2.resize(a, (SW, SH))
        mark = build_mask(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        on_person = (mark > 20) & (a > 12)
        if on_person.any():
            hits += 1
            f = cv2.inpaint(f, on_person.astype(np.uint8) * 255, 5, cv2.INPAINT_TELEA)
        fg = cv2.resize(f, (OW, BH), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
        al = cv2.resize(a, (OW, BH), interpolation=cv2.INTER_LINEAR).astype(np.float32)[..., None] / 255.0
        out = cf.copy()
        out[TOP:] = fg * al + cf[TOP:] * (1 - al)
        enc.stdin.write(out.clip(0, 255).astype(np.uint8).tobytes())
        n += 1
    enc.stdin.close()
    enc.wait()
    json.dump({"frames": n, "frames_mark_on_person": hits}, open(d / "composite.json", "w"), indent=2)
    print("wrote", dest, "frames", n, "mark-on-person frames", hits)
    return dest


def qa(ep: Path, d: Path) -> None:
    q = d / "qa"
    q.mkdir(exist_ok=True)
    src, out = ep / "heygen/export.mp4", ep / "heygen/export_43.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "3", "-i", str(src), "-frames:v", "1", str(q / "before.png")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "3", "-i", str(out), "-frames:v", "1", str(q / "after.png")], check=True)
    b = cv2.imread(str(q / "before.png"))
    b = cv2.resize(b, (int(SW * OH / SH), OH))
    a = cv2.imread(str(q / "after.png"))
    cv2.imwrite(str(q / "before_after.png"), np.hstack([b, np.full((OH, 20, 3), 255, np.uint8), a]))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0", "-t", "5", "-i", str(out),
                    "-c:v", "libx264", "-crf", "18", "-c:a", "aac", str(q / "dewm_5s.mp4")], check=True)
    print("qa ->", q)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--qa", action="store_true")
    a = ap.parse_args()
    ep = Path(a.episode)
    d = ep / "heygen/dewm"
    d.mkdir(parents=True, exist_ok=True)
    chk = stage_matte(ep, d)
    plate = stage_plate(ep, d, chk, a.force)
    p43 = stage_flova(ep, d)
    stage_composite(ep, d, chk, plate, p43, a.force)
    if a.qa:
        qa(ep, d)


if __name__ == "__main__":
    main()
