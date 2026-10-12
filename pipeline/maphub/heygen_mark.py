#!/usr/bin/env python3
"""Cover the static bottom-right HeyGen mark on the original avatar export.

usage:
  python pipeline/maphub/heygen_mark.py <episode> [--force]
  python pipeline/maphub/heygen_mark.py --self-test

Reads only <episode>/heygen/export.mp4 (1280x720). Writes heygen/mark/* and
heygen/export_nomark.mp4. Does not overwrite export.mp4.

Python cannot call MCP. Until heygen/mark/repair.png exists this exits 3 and
prints the generate_image hand-off (same shape as map:fetch). The repair must
keep the shot's shallow depth of field. The mask is a soft blob around the
mark, not a hard glyph paste.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
W, H = 1280, 720
MARK_X0, MARK_Y0 = 1040, 540
PROMPT = (
    "Edit this photograph. It was shot with a shallow depth of field: the person's face and hands "
    "are the focal plane and stay sharp, while the sofa, including the bottom-right arm and seat, "
    "is already softly out of focus, matching the cushion beside it. Remove only the semi-transparent "
    "white lettering and the small white geometric mark in the bottom-right corner. Rebuild the beige "
    "upholstery, seam, and shading underneath at the same defocus and the same soft weave as the "
    "surrounding sofa. Do not sharpen the fabric, do not reveal a crisp weave, and do not change focus, "
    "bokeh, or depth of field anywhere else. Leave the person, face, hands, clothes, pillows, windows, "
    "and framing unchanged. No text, letters, logo, icon, or watermark."
)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def probe(src: Path) -> dict:
    raw = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate,nb_frames",
         "-of", "json", str(src)],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(raw)
    video = next(s for s in data.get("streams") or [] if s.get("codec_type") == "video")
    rate = str(video.get("r_frame_rate") or "0/1")
    num, den = rate.split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": fps,
        "frames": int(video.get("nb_frames") or 0),
        "duration": float(data.get("format", {}).get("duration") or 0),
        "audio": any(s.get("codec_type") == "audio" for s in data.get("streams") or []),
    }


def extract_frame(src: Path, dest: Path, t: float) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ss", f"{t:.3f}", "-frames:v", "1", "-update", "1", str(dest)],
        check=True, capture_output=True,
    )


def build_mask(frame: np.ndarray) -> np.ndarray:
    """Soft blob around the bottom-right mark. Empty array (shape HxW) of zeros if none."""
    rgb = frame.astype(np.int16)
    blur = cv2.GaussianBlur(frame, (0, 0), 7).astype(np.int16)
    lift = rgb.sum(2) - blur.sum(2)
    sat = rgb.max(2) - rgb.min(2)
    total = rgb.sum(2)
    hit = (lift > 55) & (sat < 40) & (total > 450)
    hit[:MARK_Y0, :] = False
    hit[:, :MARK_X0] = False
    n, labels, stats, _ = cv2.connectedComponentsWithStats(hit.astype(np.uint8), 8)
    keep = np.zeros(hit.shape, np.uint8)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] > 200:
            keep[labels == i] = 255
    if not keep.any():
        return keep
    inv = cv2.bitwise_not(keep)
    flood = inv.copy()
    ff = np.zeros((inv.shape[0] + 2, inv.shape[1] + 2), np.uint8)
    cv2.floodFill(flood, ff, (0, 0), 0)
    solid = cv2.bitwise_or(keep, flood)
    blob = cv2.dilate(solid, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    blob = cv2.morphologyEx(blob, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
    return cv2.GaussianBlur(blob, (0, 0), 6)


def color_match(src: np.ndarray, gen: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Scale gen so the ring around the mask matches src. Returns uint8 RGB."""
    ring = (cv2.dilate((mask > 20).astype(np.uint8), np.ones((25, 25), np.uint8)) > 0) & (mask < 12)
    out = gen.astype(np.float32)
    if int(ring.sum()) > 50:
        sm = src[ring].astype(np.float32).mean(0)
        gm = gen[ring].astype(np.float32).mean(0)
        out *= sm / np.maximum(gm, 1.0)
    return np.clip(out, 0, 255).astype(np.uint8)


def make_request(profile: str) -> dict:
    return {
        "purpose": "Cover only the bottom-right mark on the original HeyGen export. Keep the shallow depth of field. Image only.",
        "tool": "generate_image",
        "model": "gpt-image-2.5-sunburst",
        "aspect_ratio": "16:9",
        "resolution": "1K",
        "prompt": PROMPT,
        "source_image": "heygen/mark/frame.png",
        "output_image": "heygen/mark/repair.png",
        "params": {"profile": profile, "original": True},
    }


def pinned_profile(existing: dict) -> str:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from pipeline.stages.map_fetch import resolve_map_profile
    return resolve_map_profile(existing)


def need_image(ep: Path, request: dict, profile: str) -> None:
    frame = (ep / "heygen/mark/frame.png").resolve()
    repair = (ep / "heygen/mark/repair.png").resolve()
    text = (
        f"heygen_mark 需要 Agent 用 flova 图像生成补出口播原片右下角（仓库 Python 调不了 MCP；只生图，不生成视频）：\n"
        f"    1. 读 {ep.as_posix()}/heygen/mark/flova_request.json（prompt / source_image / output_image / params）\n"
        f"    2. 调 flova-image 的 generate_image（model=gpt-image-2.5-sunburst）：prompt=request.prompt，"
        f"参考图={frame}，参数 profile=\"{profile}\"、original=true；不要调 generate_video，不要换号\n"
        f"    3. 把返回的无水印原图保存为 {repair}\n"
        f"    4. 重跑 python pipeline/maphub/heygen_mark.py {ep.as_posix()}\n"
        f"    补图必须保持浅景深：人脸清楚，沙发角和旁边的垫子一样虚。蒙版只盖住右下角那块标。\n"
        f"    若生成失败（含积分原因），把错误原文告诉用户，不要在这一步自动邀号或换号。"
    )
    print("\n" + text)
    raise SystemExit(3)


def composite(src: Path, fill: Path, mask: Path, dest: Path, fps: float) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-i", str(fill), "-i", str(mask),
         "-filter_complex", "[1][2]alphamerge[fg];[0][fg]overlay=0:0:format=auto[v]",
         "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
         "-r", f"{fps:.6f}".rstrip("0").rstrip("."), "-c:a", "copy", str(dest)],
        check=True,
    )


def run(ep: Path, force: bool) -> None:
    export = ep / "heygen" / "export.mp4"
    if not export.is_file():
        raise SystemExit(f"missing original export: {export}")
    info = probe(export)
    if (info["width"], info["height"]) != (W, H):
        raise SystemExit(f"export must be {W}x{H}, got {info['width']}x{info['height']}")
    if not info["audio"]:
        raise SystemExit(f"export has no audio stream: {export}")
    mark = ep / "heygen" / "mark"
    frame_p, mask_p, repair_p = mark / "frame.png", mark / "mask.png", mark / "repair.png"
    req_p, status_p = mark / "flova_request.json", mark / "status.json"
    clean = ep / "heygen" / "export_nomark.mp4"
    t = 2.3 if info["duration"] > 2.5 else max(0.0, info["duration"] / 2)
    extract_frame(export, frame_p, t)
    frame = cv2.cvtColor(cv2.imread(str(frame_p), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    if frame.shape[0] != H or frame.shape[1] != W:
        raise SystemExit(f"frame is {frame.shape[1]}x{frame.shape[0]}, expected {W}x{H}")
    mask = build_mask(frame)
    if not mask.any():
        save_json(status_p, {"status": "absent"})
        print("no corner mark; split can use export.mp4")
        return
    cv2.imwrite(str(mask_p), mask)
    if not repair_p.is_file():
        request = make_request(pinned_profile(load_json(req_p)))
        save_json(req_p, request)
        save_json(status_p, {"status": "pending", "request": "heygen/mark/flova_request.json"})
        need_image(ep, request, request["params"]["profile"])
    st = repair_p.stat()
    prev = load_json(status_p)
    if (not force and clean.is_file() and prev.get("status") == "done"
            and prev.get("repair_size") == st.st_size and prev.get("repair_mtime_ns") == st.st_mtime_ns):
        print("skip, export_nomark.mp4 is current")
        return
    gen = cv2.cvtColor(cv2.imread(str(repair_p), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    if gen.shape[1] != W or gen.shape[0] != H:
        gen = cv2.resize(gen, (W, H), interpolation=cv2.INTER_LANCZOS4)
    fill = color_match(frame, gen, mask)
    fill_p = mark / "fill.png"
    cv2.imwrite(str(fill_p), cv2.cvtColor(fill, cv2.COLOR_RGB2BGR))
    composite(export, fill_p, mask_p, clean, info["fps"])
    save_json(status_p, {
        "status": "done",
        "fps": info["fps"],
        "frames": info["frames"],
        "repair_size": st.st_size,
        "repair_mtime_ns": st.st_mtime_ns,
    })
    print("wrote", clean)


def self_test() -> None:
    img = np.full((H, W, 3), (190, 180, 170), np.uint8)
    img[590:602, 1100:1180] = (245, 245, 245)
    img[610:622, 1100:1160] = (245, 245, 245)
    img[590:640, 1190:1210] = (245, 245, 245)
    mask = build_mask(img)
    assert mask.shape == (H, W)
    assert mask[360, 640] == 0
    assert int(mask[596, 1140]) > 0
    assert int(mask.max()) == 255
    assert bool(((mask > 0) & (mask < 255)).any())
    src = np.full((40, 40, 3), 100, np.uint8)
    gen = np.full((40, 40, 3), 125, np.uint8)
    m = np.zeros((40, 40), np.uint8)
    m[8:32, 8:32] = 255
    matched = color_match(src, gen, m)
    # ring sits outside the solid core and should pull 125 toward 100
    assert int(matched[20, 20, 0]) < 125
    assert abs(int(matched[20, 20, 0]) - 100) <= 2
    req = make_request("kid4")
    assert req["tool"] == "generate_image"
    assert req["model"] == "gpt-image-2.5-sunburst"
    assert req["params"]["original"] is True
    assert "shallow depth of field" in req["prompt"]
    assert "Do not sharpen" in req["prompt"]
    assert "generate_video" not in json.dumps(req)
    print("self-test ok")


def main() -> None:
    ap = argparse.ArgumentParser(description="Cover the HeyGen corner mark on heygen/export.mp4")
    ap.add_argument("episode", nargs="?")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    if not a.episode:
        ap.error("episode is required")
    run(Path(a.episode), a.force)


if __name__ == "__main__":
    main()
