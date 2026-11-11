#!/usr/bin/env python3
"""Measurable aesthetics harmony check for video stills.

Usage:
  python3 harmony_check.py img1.png img2.png ...
  python3 harmony_check.py --dir ./out --glob 'still_v3_*.png'
  python3 harmony_check.py --accent '#D6EB00' stills/*.png

  python pipeline/check/harmony_check.py --project projects/<cat>/<id>   # auto-find stills in output/

Prints per-image metrics + PASS/FAIL against the measurable-aesthetics-gate checklist.
Exit code: 0 = no hard fails, 1 = hard fail, 2 = no images / usage error.
Rules: rules/taste.md section 8. Needs numpy + Pillow (opencv is NOT required).
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw

# Windows: make stdout/stderr UTF-8 so the box-drawing / CJK / arrow characters survive pipes and cp936 consoles.
os.environ.setdefault("PYTHONUTF8", "1")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

MIN_STILLS = 4  # rules/taste.md section 8: at least 4 stills at distinct shots


def hex_to_rgb(h: str) -> Tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore


def rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    v = maxc
    d = maxc - minc
    s = np.where(maxc < 1e-6, 0.0, d / np.maximum(maxc, 1e-6))
    rc = (maxc - r) / np.maximum(d, 1e-6)
    gc = (maxc - g) / np.maximum(d, 1e-6)
    bc = (maxc - b) / np.maximum(d, 1e-6)
    h = np.zeros_like(maxc)
    mask = d > 1e-6
    h = np.where(mask & (maxc == r), (bc - gc) % 6.0, h)
    h = np.where(mask & (maxc == g), 2.0 + rc - bc, h)
    h = np.where(mask & (maxc == b), 4.0 + gc - rc, h)
    h = (h / 6.0) % 1.0
    return np.stack([h, s, v], axis=-1)


def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def relative_luminance(rgb: np.ndarray) -> np.ndarray:
    lin = srgb_to_linear(rgb)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def contrast_ratio(l1: float, l2: float) -> float:
    a, b = (l1, l2) if l1 >= l2 else (l2, l1)
    return (a + 0.05) / (b + 0.05)


def kmeans(pixels: np.ndarray, k: int = 5, iters: int = 12, seed: int = 0) -> Tuple[np.ndarray, np.ndarray]:
    """Simple k-means on Nx3 float array. Returns (centers kx3, counts k)."""
    rng = np.random.default_rng(seed)
    n = pixels.shape[0]
    if n < k:
        k = max(1, n)
    # init: random sample
    idx = rng.choice(n, size=k, replace=False)
    centers = pixels[idx].copy()
    labels = np.zeros(n, dtype=np.int32)
    for _ in range(iters):
        # assign
        d2 = ((pixels[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = d2.argmin(axis=1)
        for j in range(k):
            m = labels == j
            if m.any():
                centers[j] = pixels[m].mean(axis=0)
            else:
                centers[j] = pixels[rng.integers(0, n)]
    counts = np.bincount(labels, minlength=k)
    # sort by count desc
    order = np.argsort(-counts)
    return centers[order], counts[order]


def sobel_mag(gray: np.ndarray) -> np.ndarray:
    """gray float HxW → edge magnitude."""
    # pad
    g = np.pad(gray, 1, mode="edge")
    gx = (
        -1 * g[:-2, :-2]
        + -2 * g[:-2, 1:-1]
        + -1 * g[:-2, 2:]
        + 1 * g[2:, :-2]
        + 2 * g[2:, 1:-1]
        + 1 * g[2:, 2:]
    )
    gy = (
        -1 * g[:-2, :-2]
        + -2 * g[1:-1, :-2]
        + -1 * g[2:, :-2]
        + 1 * g[:-2, 2:]
        + 2 * g[1:-1, 2:]
        + 1 * g[2:, 2:]
    )
    return np.sqrt(gx * gx + gy * gy)


def rgb_to_hex(rgb: np.ndarray) -> str:
    r, g, b = (np.clip(rgb, 0, 1) * 255).astype(int)
    return f"#{r:02X}{g:02X}{b:02X}"


@dataclass
class Finding:
    id: str
    severity: str  # hard | soft
    ok: bool
    detail: str


@dataclass
class ImageReport:
    path: str
    findings: List[Finding] = field(default_factory=list)
    palette: List[Tuple[str, float]] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def hard_fails(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "hard" and not f.ok]

    @property
    def soft_warns(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "soft" and not f.ok]


def foreground_mask(path: str, size: Tuple[int, int], target: Tuple[int, int]):
    """Read renderer-measured foreground bounds, bound to these exact image bytes.

    Only D3's distant-background measurement uses this mask. Palette, contrast,
    peripheral sharpness and all other gates still inspect the complete image.
    Missing metadata preserves the legacy measurement; invalid metadata is a hard fail.
    """
    sidecar = os.path.splitext(path)[0] + ".layers.json"
    if not os.path.isfile(sidecar):
        return None, None, []
    try:
        with open(sidecar, encoding="utf-8") as fh:
            meta = json.load(fh)
        if meta.get("version") != 1:
            raise ValueError("unsupported foreground metadata version")
        with open(path, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        if meta.get("image_sha256") != digest:
            raise ValueError("foreground metadata does not match this image")
        w, h = size
        if (meta.get("width"), meta.get("height")) != (w, h):
            raise ValueError("foreground metadata has the wrong image dimensions")
        regions = meta.get("foreground")
        if not isinstance(regions, list) or len(regions) > 128:
            raise ValueError("foreground regions must be a list of at most 128 items")
        worlds = meta.get("worlds", [])
        if not isinstance(worlds, list) or len(worlds) > 8:
            raise ValueError("invalid world layer metadata")
        for world in worlds:
            values = [float(world[k]) for k in ("x","y","w","h")]
            if world.get("kind") not in {"video","image","map"} or not world.get("source") or not all(math.isfinite(v) for v in values):
                raise ValueError("invalid world layer")
            x,y,ww,hh=values
            if x < 0 or y < 0 or ww <= 0 or hh <= 0 or x+ww > w+1 or y+hh > h+1:
                raise ValueError("world bounds escape the image")
        mask = Image.new("L", (w, h))
        draw = ImageDraw.Draw(mask)
        for region in regions:
            if region.get("role") not in {"title", "photo", "icon", "label", "presenter", "caption", "brand", "info"}:
                raise ValueError("unknown foreground role")
            x, y, rw, rh = [float(region[k]) for k in ("x", "y", "w", "h")]
            if not all(math.isfinite(v) for v in (x, y, rw, rh)):
                raise ValueError("non-finite foreground coordinates")
            if x < 0 or y < 0 or rw <= 0 or rh <= 0 or x + rw > w + 1 or y + rh > h + 1:
                raise ValueError("foreground bounds escape the image")
            draw.rectangle((max(0, x - 2), max(0, y - 2), min(w - 1, x + rw + 2), min(h - 1, y + rh + 2)), fill=255)
        if (np.asarray(mask) > 0).mean() > 0.65:
            raise ValueError("foreground metadata covers too much of the image")
        mask = mask.resize((target[1], target[0]), Image.Resampling.NEAREST)
        blocked = np.asarray(mask) > 0
        # Sobel's 3x3 neighbourhood must not sample the edge of a foreground box.
        padded = np.pad(blocked, 1, mode="edge")
        blocked = np.logical_or.reduce([padded[dy:dy + target[0], dx:dx + target[1]] for dy in range(3) for dx in range(3)])
        return blocked, None, worlds
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return None, str(exc), []


def subject_edge_ratio(edges, focus_box):
    """Compare detail outside the declared subject with detail inside it.

    Bounds are normalized to the actual frame. The legacy center ROI remains
    the default, and other color/contrast/depth gates are unaffected.
    """
    x, y, width, height = map(float, focus_box)
    if not all(math.isfinite(v) for v in (x, y, width, height)) or min(x, y) < 0 or min(width, height) <= 0 or x + width > 1.000001 or y + height > 1.000001 or not 0.1 <= width * height <= 0.5:
        raise ValueError("invalid subject focus box")
    h, w = edges.shape
    x0, y0 = int(x * w), int(y * h)
    x1, y1 = min(w, round((x + width) * w)), min(h, round((y + height) * h))
    outside = np.ones((h, w), dtype=bool)
    outside[y0:y1, x0:x1] = False
    return float(edges[outside].mean() / max(float(edges[y0:y1, x0:x1].mean()), 1e-6))


def analyze_image(path: str, accent_hex: str, focus_box=None) -> ImageReport:
    rep = ImageReport(path=path)
    im = Image.open(path).convert("RGB")
    # downscale for speed
    max_side = 720
    w, h = im.size
    scale = max_side / max(w, h)
    if scale < 1:
        im_s = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
    else:
        im_s = im
        scale = 1.0
    arr = np.asarray(im_s).astype(np.float64) / 255.0
    hs, ws = arr.shape[:2]
    hsv = rgb_to_hsv(arr)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    gray = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    edges = sobel_mag(gray)
    foreground, foreground_error, worlds = foreground_mask(path, (w, h), (hs, ws))
    if foreground_error:
        rep.findings.append(Finding("D3meta", "hard", False, foreground_error))

    # subsample for k-means
    flat = arr.reshape(-1, 3)
    step = max(1, flat.shape[0] // 8000)
    sample = flat[::step]
    centers, counts = kmeans(sample, k=5, iters=14, seed=42)
    total = counts.sum()
    for c, n in zip(centers, counts):
        rep.palette.append((rgb_to_hex(c), 100.0 * n / total))

    # hue count: chromatic pixels clustered by hue bin
    chromatic = S >= 0.25
    hue_bins = np.zeros(12, dtype=np.int64)
    if chromatic.any():
        hb = (H[chromatic] * 12).astype(int) % 12
        hue_bins = np.bincount(hb, minlength=12)
    significant_hues = int((hue_bins > chromatic.sum() * 0.02).sum()) if chromatic.any() else 0
    chromatic_share = float(chromatic.mean())

    # accent area
    ar, ag, ab = hex_to_rgb(accent_hex)
    accent_hsv = rgb_to_hsv(np.array([[[ar, ag, ab]]]))[0, 0]
    ah, as_, av = accent_hsv
    # circular hue distance
    dh = np.minimum(np.abs(H - ah), 1.0 - np.abs(H - ah))
    accent_mask = (dh < 0.07) & (S > 0.35) & (V > 0.35)
    accent_pct = 100.0 * accent_mask.mean()

    # region thirds
    t1, t2 = hs // 3, 2 * hs // 3
    regions = {
        "top": (S[:t1].mean(), V[:t1].mean(), edges[:t1].mean()),
        "mid": (S[t1:t2].mean(), V[t1:t2].mean(), edges[t1:t2].mean()),
        "bot": (S[t2:].mean(), V[t2:].mean(), edges[t2:].mean()),
    }
    # center vs periphery edge
    cy0, cy1 = int(hs * 0.25), int(hs * 0.75)
    cx0, cx1 = int(ws * 0.20), int(ws * 0.80)
    center_edge = edges[cy0:cy1, cx0:cx1].mean()
    peri_mask = np.ones((hs, ws), dtype=bool)
    peri_mask[cy0:cy1, cx0:cx1] = False
    peri_edge = edges[peri_mask].mean()
    edge_ratio = peri_edge / max(center_edge, 1e-6)
    if focus_box is not None:
        edge_ratio = subject_edge_ratio(edges, focus_box)

    # double-detail: split into 2x2 tiles, count tiles with high edge
    tile_h, tile_w = hs // 2, ws // 2
    tile_edges = []
    for i in range(2):
        for j in range(2):
            te = edges[i * tile_h : (i + 1) * tile_h, j * tile_w : (j + 1) * tile_w].mean()
            tile_edges.append(te)
    tau = np.median(tile_edges) * 1.15
    high_tiles = sum(1 for te in tile_edges if te >= tau and te > 0.08)
    # also: if top half edge ≈ bottom half and both high → map-on-map signal
    top_e, bot_e = edges[: hs // 2].mean(), edges[hs // 2 :].mean()
    double_detail = high_tiles >= 3 and min(top_e, bot_e) > 0.10 and abs(top_e - bot_e) / max(top_e, bot_e, 1e-6) < 0.35

    # dark-chip on bright canvas
    canvas_bright = V.mean() > 0.70
    dark = V < 0.22
    # exclude very small noise: morphological-ish via downsample count of dark blobs in mid sizes
    dark_pct = 100.0 * dark.mean()
    # UI-sized: count SOLID dark blocks only (a filled chip, not glyph strokes:
    # large type fills well under 85% of a block and carries internal edges).
    bh, bw = 8, 8
    dark_blocks = 0
    block_total = 0
    for y in range(0, hs - bh, bh):
        for x in range(0, hs - bw, bw):
            block_total += 1
            solid_dark = dark[y : y + bh, x : x + bw].mean() > 0.95
            low_edge = edges[y : y + bh, x : x + bw].mean() < 0.12
            if solid_dark and low_edge:
                dark_blocks += 1
    dark_block_pct = 100.0 * dark_blocks / max(block_total, 1)

    # Text contrast: only patches that look like UI glyphs (bimodal ink/bg),
    # not pale-on-pale map building edges.
    lum = relative_luminance(arr)
    contrasts = []
    win = 14
    for y in range(0, hs - win, win):
        for x in range(0, ws - win, win):
            patch = lum[y : y + win, x : x + win].ravel()
            lo, hi = float(patch.min()), float(patch.max())
            if hi - lo < 0.25:
                continue
            mid = 0.5 * (lo + hi)
            ink_frac = float((patch <= mid).mean())
            # glyph-like: minority ink 8–42% OR reverse light-on-dark
            minority = min(ink_frac, 1.0 - ink_frac)
            if minority < 0.08 or minority > 0.42:
                continue
            if edges[y : y + win, x : x + win].mean() < 0.18:
                continue
            cr = contrast_ratio(hi, lo)
            if cr >= 2.2:  # ignore muddy texture
                contrasts.append(cr)
    if contrasts:
        p20 = float(np.percentile(contrasts, 15))
        med_c = float(np.median(contrasts))
    else:
        p20, med_c = 21.0, 21.0

    large_worlds = [layer for layer in worlds if layer["w"] * layer["h"] >= w * h * 0.20]
    duplicated_worlds = len(large_worlds) > 1
    full_frame_footage = len(large_worlds) == 1 and large_worlds[0]["kind"] in {"video", "image"} and large_worlds[0]["w"] * large_worlds[0]["h"] >= w * h * 0.98

    # Far-band detail (single-world check): edge density of the band just below the chrome row
    # (y 11-28% of H) vs the focal center. A second sharp background layer keeps this high.
    fb0, fb1 = int(hs * 0.11), int(hs * 0.28)
    raw_far_band_edge = float(edges[fb0:fb1, :].mean())
    far_band_edge = raw_far_band_edge
    far_background_fraction = 1.0
    if foreground is not None:
        background = ~foreground[fb0:fb1, :]
        far_background_fraction = float(background.mean())
        if far_background_fraction < 0.25:
            rep.findings.append(Finding("D3meta", "hard", False, "too little distant background remains to assess"))
        else:
            far_band_edge = float(edges[fb0:fb1, :][background].mean())
    far_band_ratio = far_band_edge / max(center_edge, 1e-6)
    # §5.1 explicitly allows ONE continuous world: detail running unbroken
    # top→bottom (a full-frame photo / map). D3 only targets a second sharp
    # layer pasted over a smoother ground, which leaves a low-detail band
    # somewhere between the far band and the focal area.
    nbands = 10
    band_edges = [
        float(edges[k * hs // nbands : (k + 1) * hs // nbands, :].mean())
        for k in range(nbands)
    ]
    continuous = all(e >= 0.45 * max(center_edge, 1e-6) for e in band_edges) and raw_far_band_edge > 0.08
    # A second sharp layer must itself be sharp: a far band under edge 0.10
    # reads as soft distance / blur, not a pasted detailed layer.
    sharp_far = far_band_edge >= 0.10

    primary_pct = rep.palette[0][1] if rep.palette else 0.0
    # A full-frame natural photograph carries real-world hues (window, floor,
    # walls) that are not designed signal colours; do not treat them as a
    # multi-accent failure when no single colour dominates.
    natural_world = continuous and primary_pct < 45.0
    far_s, near_s = regions["top"][0], max(regions["mid"][0], regions["bot"][0], 1e-6)
    atm_ratio = far_s / near_s

    rep.metrics = {
        "accent_pct": accent_pct,
        "hue_count": significant_hues,
        "primary_pct": primary_pct,
        "edge_ratio_peri_center": edge_ratio,
        "double_detail": double_detail,
        "high_tiles": high_tiles,
        "atm_s_ratio": atm_ratio,
        "far_band_ratio": far_band_ratio,
        "far_band_raw_ratio": raw_far_band_edge / max(center_edge, 1e-6),
        "far_background_fraction": far_background_fraction,
        "foreground_metadata": foreground is not None,
        "full_frame_footage": full_frame_footage,
        "large_world_layers": len(large_worlds),
        "dark_block_pct": dark_block_pct,
        "dark_pct": dark_pct,
        "mean_v": float(V.mean()),
        "mean_s": float(S.mean()),
        "contrast_p20": p20,
        "contrast_med": med_c,
        "center_edge": float(center_edge),
        "peri_edge": float(peri_edge),
        "regions": {k: {"S": float(v[0]), "V": float(v[1]), "edge": float(v[2])} for k, v in regions.items()},
        "canvas_bright": canvas_bright,
    }

    # Checklist
    def add(fid, severity, ok, detail):
        rep.findings.append(Finding(fid, severity, ok, detail))

    add("P1", "hard", accent_pct <= 18.0, f"accent area {accent_pct:.1f}% (fail if >18; ideal 5–12)")
    # A near-monochrome frame (e.g. >94% neutral pixels) cannot be a multi-hue
    # failure no matter how many tiny chromatic specks noise produces.
    hue_ok = significant_hues <= 5 or chromatic_share < 0.06 or natural_world
    add("P2", "hard", hue_ok, f"chromatic hues {significant_hues} (fail if ≥6; chromatic share {chromatic_share:.2%})")
    add("P3", "soft", primary_pct >= 50.0, f"primary cluster {primary_pct:.1f}% (warn if <50)")
    # Hard gate on median (resists pale-map texture false-positives); p20 is soft body AA target.
    add("C1", "hard", med_c >= 3.0, f"text-like contrast med={med_c:.2f}:1 (fail if <3 AA-large)")
    add("C1b", "soft", p20 >= 4.5 or med_c >= 4.5, f"body contrast target: p20={p20:.2f} med={med_c:.2f}")
    add("D1", "soft", edge_ratio <= 0.85, f"peri/center edge={edge_ratio:.2f} (warn if >0.85)")
    add("D1h", "hard", edge_ratio < 1.05, f"peri/center edge={edge_ratio:.2f} (fail if ≥1.05 bg sharper)")
    add("D2", "hard", not double_detail, f"double-detail={'YES' if double_detail else 'no'} high_tiles={high_tiles}")
    add(
        "D3",
        "hard",
        not duplicated_worlds and (full_frame_footage or continuous or not sharp_far or far_band_ratio <= 0.30),
        f"far-background/center edge={far_band_ratio:.2f} raw={raw_far_band_edge / max(center_edge, 1e-6):.2f} background_sample={far_background_fraction:.0%} full_footage={full_frame_footage} worlds={len(large_worlds)} (fail if >0.30: second sharp layer; exempt: {continuous}, single continuous world)",
    )
    add("A1", "soft", atm_ratio <= 0.95, f"far/near S={atm_ratio:.2f} (warn if >0.95; want atmosphere)")
    # A visible dark chip covers well over 3% of the frame; under that the dark
    # pixels are a designed element (e.g. a large headline number), not chips.
    negligible_dark = dark_pct < 3.0
    if canvas_bright:
        add("L1", "hard", negligible_dark or dark_block_pct <= 1.5,
            f"dark-chip blocks {dark_block_pct:.2f}% on bright canvas (fail if >1.5; dark total {dark_pct:.2f}%)")
    else:
        add("L1", "soft", True, f"dark-chip skipped (canvas not bright; mean V={V.mean():.2f})")
    add("T1", "soft", (0.70 <= float(V.mean()) <= 0.98) or (0.05 <= float(V.mean()) <= 0.25), f"mean V={V.mean():.2f}")

    return rep


def find_stills(project_dir) -> List[str]:
    """Stills produced by `npm run still` (output/<id>_<ratio>_f<N>.png) or dropped in output/stills/."""
    out = os.path.join(str(project_dir), "output")
    found = set(glob.glob(os.path.join(out, "*_f*.png")))
    found.update(glob.glob(os.path.join(out, "stills", "*.png")))
    return sorted(found)


def expand_paths(items: List[str]) -> List[str]:
    """PowerShell / cmd do not expand globs for native programs: do it here."""
    paths: List[str] = []
    for it in items:
        if any(ch in it for ch in "*?["):
            paths.extend(sorted(glob.glob(it)))
        else:
            paths.append(it)
    return paths


def main() -> int:
    ap = argparse.ArgumentParser(description="Measurable aesthetics harmony check")
    ap.add_argument("images", nargs="*", help="Image paths (globs allowed)")
    ap.add_argument("--project", default=None, help="Project dir: check its stills in output/ (npm run check:taste -- <dir>)")
    ap.add_argument("--dir", default=None, help="Directory to scan")
    ap.add_argument("--glob", default="*.png", dest="pattern", help="Glob under --dir")
    ap.add_argument("--accent", default="#D6EB00", help="Brand accent hex")
    ap.add_argument("--focus-box", nargs=4, type=float, metavar=("X", "Y", "W", "H"), help="Normalized subject box for peripheral sharpness only")
    args = ap.parse_args()

    paths: List[str] = expand_paths(list(args.images))
    if args.project:
        pd = args.project
        if not os.path.isdir(pd):
            alt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", pd)
            pd = alt if os.path.isdir(alt) else pd
        paths.extend(find_stills(pd))
        if not paths:
            print(f"[taste] {args.project}: 没有静帧 (no stills). 先对多个镜头运行:\n"
                  f"  npm run still -- {args.project} --frame <N>   (至少 {MIN_STILLS} 个不同镜头)\n"
                  f"然后重跑 npm run check:taste -- {args.project}", file=sys.stderr)
            return 2
    if args.dir:
        paths.extend(sorted(glob.glob(os.path.join(args.dir, args.pattern))))
    paths = [p for p in paths if os.path.isfile(p)]
    if not paths:
        print("No images found.", file=sys.stderr)
        return 2
    if len(paths) < MIN_STILLS:
        print(f"[taste] WARN: only {len(paths)} still(s); rules/taste.md requires >= {MIN_STILLS} at distinct shots.", file=sys.stderr)

    reports = [analyze_image(p, args.accent, args.focus_box) for p in paths]
    hard = 0
    soft = 0
    print("=" * 72)
    print("HARMONY CHECK — measurable-aesthetics-gate")
    print(f"accent={args.accent}  images={len(reports)}")
    print("=" * 72)
    if args.focus_box:
        print("Sharpness focus: actual subject box", args.focus_box, "(all other gates unchanged)")

    for r in reports:
        print(f"\n## {os.path.basename(r.path)}")
        print("  palette:", ", ".join(f"{h} {p:.1f}%" for h, p in r.palette[:5]))
        m = r.metrics
        print(
            f"  accent={m['accent_pct']:.1f}%  hues={m['hue_count']}  primary={m['primary_pct']:.1f}%  "
            f"meanV={m['mean_v']:.2f} meanS={m['mean_s']:.2f}"
        )
        print(
            f"  edge peri/center={m['edge_ratio_peri_center']:.2f}  double_detail={m['double_detail']}  "
            f"farBand={m['far_band_ratio']:.2f}  atmS={m['atm_s_ratio']:.2f}  dark_blocks={m['dark_block_pct']:.2f}%  contrast_p20={m['contrast_p20']:.2f}"
        )
        for f in r.findings:
            mark = "PASS" if f.ok else ("FAIL" if f.severity == "hard" else "WARN")
            if not f.ok:
                if f.severity == "hard":
                    hard += 1
                else:
                    soft += 1
            print(f"  [{mark}] {f.id}: {f.detail}")

    print("\n" + "=" * 72)
    overall = "PASS" if hard == 0 else "FAIL"
    print(f"AGGREGATE: {overall}  hard_fails={hard}  soft_warns={soft}")
    print("=" * 72)
    return 0 if hard == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
