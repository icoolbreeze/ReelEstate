#!/usr/bin/env python3
"""Track annotation targets through a Muse clip → annotations/<ID>.json for <ScanAnnotate>.

usage:
  python pipeline/track_annotations.py grid  footage/shots/LR1.mp4 [--t 0.4]          # writes annotations/seeds/LR1_grid.jpg (10% grid) to place seed boxes
  python pipeline/track_annotations.py track footage/shots/LR1.mp4 [--method vit|csrt|flow] [--step 3] [--t0 0.4]
seed file annotations/seeds/<ID>.json:
  { "t": 0.4, "targets": [ { "label": "布艺沙发", "sub": "FABRIC SOFA", "box": [x, y, w, h] }, ... ] }   # normalised 0–1 at time t
  a target may carry "pad" (feature-mask margin) or "kf": [[t_sec, x, y, w, h], ...] to hand-key it (tracking skipped)
output annotations/<ID>.json:
  { "space": "video", "size": [w, h], "method": "...", "targets": [ { "id", "label", "sub", "kf": [[t_sec, x, y, w, h], ...] } ] }
Methods: vit = cv2.TrackerVit (needs pipeline/models/object_tracking_vittrack_2023sep.onnx, opencv>=4.9);
         csrt = cv2.TrackerCSRT (opencv-contrib); flow = LK optical flow + similarity fit (no model, good for slow pans/pushes).
Default "auto" = flow: on a 5 s synthetic slow push-in (I1 still, 1.09x) flow matched ground truth within 0.002 (normalised)
while TrackerVit grew the sofa box ~25 % too wide (its box regression is weak on large, low-texture furniture).
Use --method vit/csrt only for objects that move independently of the camera.
Tracks forward AND backward from t so boxes exist from frame 0.
Low-confidence frames hold the last good box; boxes are smoothed (centre/size EMA) so the viewfinder does not jitter.
"""
import argparse, json, sys
from pathlib import Path
import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VIT = HERE / "models" / "object_tracking_vittrack_2023sep.onnx"

def read_frames(path):
    cap = cv2.VideoCapture(str(path)); fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok: break
        frames.append(fr)
    return frames, fps

def make_tracker(method):
    if method == "vit":
        p = cv2.TrackerVit_Params(); p.net = str(VIT); return cv2.TrackerVit_create(p)
    if method == "csrt":
        return cv2.TrackerCSRT_create() if hasattr(cv2, "TrackerCSRT_create") else cv2.legacy.TrackerCSRT_create()
    raise ValueError(method)

def pick_method(m):
    if m == "auto": return "flow"
    if m != "best-available": return m
    if hasattr(cv2, "TrackerVit_create") and VIT.exists(): return "vit"
    if hasattr(cv2, "TrackerCSRT_create") or hasattr(cv2, "legacy"): return "csrt"
    return "flow"

def track_cv(frames, i0, box, method):
    """returns dict frame_index -> (x,y,w,h) px; forward + backward from i0."""
    out = {i0: tuple(box)}
    for direction in (1, -1):
        tr = make_tracker(method); tr.init(frames[i0], tuple(int(v) for v in box)); last = box
        i = i0 + direction
        while 0 <= i < len(frames):
            ok, b = tr.update(frames[i])
            score = tr.getTrackingScore() if method == "vit" else (1.0 if ok else 0.0)
            if ok and score > 0.3 and b[2] > 4 and b[3] > 4:
                last = b
            out[i] = tuple(last); i += direction
    return out

def track_flow(frames, i0, box, pad=0.25):
    """pad: features are taken from the box grown by pad*size on each side, so low-texture targets
    (a black TV, sky between towers, glass) still move with their surroundings."""
    gray = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    H, W = gray[0].shape
    out = {i0: tuple(box)}
    for direction in (1, -1):
        x, y, w, h = box; i = i0
        while 0 <= i + direction < len(frames):
            g0, g1 = gray[i], gray[i + direction]
            mask = np.zeros_like(g0)
            mx0, my0 = max(0, int(x - pad * w)), max(0, int(y - pad * h)); mx1, my1 = min(W, int(x + w + pad * w)), min(H, int(y + h + pad * h))
            mask[my0:my1, mx0:mx1] = 255
            pts = cv2.goodFeaturesToTrack(g0, 200, 0.01, 5, mask=mask)
            if pts is not None and len(pts) >= 6:
                nxt, st, _ = cv2.calcOpticalFlowPyrLK(g0, g1, pts, None, winSize=(21, 21), maxLevel=3)
                good0, good1 = pts[st == 1], nxt[st == 1]
                if len(good0) >= 6:
                    M, _ = cv2.estimateAffinePartial2D(good0, good1, method=cv2.RANSAC)
                    if M is not None:
                        s = float(np.sqrt(abs(np.linalg.det(M[:, :2]))))
                        cx, cy = x + w / 2, y + h / 2
                        ncx, ncy = M @ np.array([cx, cy, 1.0])
                        w, h = w * s, h * s; x, y = ncx - w / 2, ncy - h / 2
            i += direction; out[i] = (x, y, w, h)
    return out

def track_camera(frames, i0, boxes):
    """One homography per frame, from the seed frame. Seed boxes are masked out of the feature search.
    Returns one smoothed box sequence per seed box, a keyframe on every frame."""
    gray = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    H, W = gray[0].shape
    mask = np.full((H, W), 255, np.uint8)
    for x, y, w, h in boxes:
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(W, int(x + w)), min(H, int(y + h))
        mask[y0:y1, x0:x1] = 0
    pts0 = cv2.goodFeaturesToTrack(gray[i0], 400, 0.01, 8, mask=mask)
    n = len(frames)
    Hs = [None] * n
    eye = np.eye(3, dtype=np.float64)
    Hs[i0] = eye
    if pts0 is not None and len(pts0) >= 8:
        for direction in (1, -1):
            alive = pts0.reshape(-1, 2).astype(np.float32)
            origin = alive.copy()
            i = i0
            last = eye.copy()
            while 0 <= i + direction < n:
                nxt, st, _ = cv2.calcOpticalFlowPyrLK(gray[i], gray[i + direction], alive.reshape(-1, 1, 2), None, winSize=(21, 21), maxLevel=3)
                ok = st.reshape(-1).astype(bool)
                if int(ok.sum()) >= 8:
                    alive = nxt.reshape(-1, 2)[ok]
                    origin = origin[ok]
                    M, _ = cv2.findHomography(origin.reshape(-1, 1, 2), alive.reshape(-1, 1, 2), cv2.RANSAC, 3.0)
                    if M is None:
                        A, _ = cv2.estimateAffinePartial2D(origin.reshape(-1, 1, 2), alive.reshape(-1, 1, 2), method=cv2.RANSAC)
                        if A is not None:
                            M = np.eye(3); M[:2] = A
                    if M is not None:
                        last = M
                i += direction
                Hs[i] = last
    def warp_box(Hmat, box):
        x, y, w, h = box
        corners = np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], np.float64).reshape(-1, 1, 2)
        ph = cv2.perspectiveTransform(corners, Hmat if Hmat is not None else eye).reshape(-1, 2)
        x0, y0 = float(ph[:, 0].min()), float(ph[:, 1].min())
        x1, y1 = float(ph[:, 0].max()), float(ph[:, 1].max())
        return (x0, y0, max(4.0, x1 - x0), max(4.0, y1 - y0))
    out = []
    for box in boxes:
        seq = [warp_box(Hs[i], box) for i in range(n)]
        out.append(smooth_both(seq))
    return out

def smooth(seq, a=0.35):
    out, prev = [], None
    for b in seq:
        c = np.array([b[0] + b[2] / 2, b[1] + b[3] / 2, b[2], b[3]])
        prev = c if prev is None else prev + a * (c - prev)
        out.append((prev[0] - prev[2] / 2, prev[1] - prev[3] / 2, prev[2], prev[3]))
    return out

def smooth_both(seq):
    """Average a forward and a backward EMA so the box does not lag the picture or breathe."""
    fwd = smooth(seq, 0.45)
    back = list(reversed(smooth(list(reversed(fwd)), 0.45)))
    return [tuple((a[k] + b[k]) / 2 for k in range(4)) for a, b in zip(fwd, back)]

def interp(kf, t):
    if t <= kf[0][0]: return kf[0][1:]
    for a, b in zip(kf, kf[1:]):
        if t <= b[0]:
            u = (t - a[0]) / max(1e-6, b[0] - a[0]); return [a[k] + u * (b[k] - a[k]) for k in range(1, 5)]
    return kf[-1][1:]

def ann_dir(clip):
    """<episode>/annotations for a clip anywhere inside the episode (normally footage/shots/<ID>.mp4)"""
    clip = Path(clip).resolve()
    for parent in clip.parents:
        if (parent / "episode.yaml").is_file():
            return parent / "annotations"
    return clip.parent.parent / "annotations"

def cmd_grid(a):
    frames, fps = read_frames(a.clip)
    i = min(len(frames) - 1, int(a.t * fps)); im = frames[i].copy(); h, w = im.shape[:2]
    for k in range(1, 10):
        cv2.line(im, (w * k // 10, 0), (w * k // 10, h), (0, 0, 255), 1); cv2.line(im, (0, h * k // 10), (w, h * k // 10), (0, 0, 255), 1)
        cv2.putText(im, f"{k/10:.1f}", (w * k // 10 + 3, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        cv2.putText(im, f"{k/10:.1f}", (3, h * k // 10 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    out = ann_dir(a.clip) / "seeds" / f"{Path(a.clip).stem}_grid.jpg"; out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), im); print("wrote", out, f"(frame {i}, t={i / fps:.2f}s, {w}x{h})")

def cmd_track(a):
    cid = Path(a.clip).stem
    seed = json.loads((ann_dir(a.clip) / "seeds" / f"{cid}.json").read_text(encoding="utf-8"))
    frames, fps = read_frames(a.clip)
    if not frames: sys.exit("no frames: " + a.clip)
    H, W = frames[0].shape[:2]
    method = pick_method(a.method)
    i0 = min(len(frames) - 1, int(seed.get("t", a.t0) * fps))
    targets = []
    pending = []
    for k, t in enumerate(seed["targets"]):
        if t.get("kf"):
            targets.append({"id": t.get("id", f"t{k}"), "label": t["label"], "sub": t.get("sub", ""), "kf": t["kf"], "hand": True}); print(f"{cid} {t['label']}: hand-keyed"); continue
        bx = [t["box"][0] * W, t["box"][1] * H, t["box"][2] * W, t["box"][3] * H]
        pending.append((k, t, bx))
    cam_seqs = track_camera(frames, i0, [bx for _, _, bx in pending]) if method == "camera" and pending else None
    step = 1 if method == "camera" else a.step
    for j, (k, t, bx) in enumerate(pending):
        if cam_seqs is not None:
            seq = cam_seqs[j]
        else:
            try:
                res = track_flow(frames, i0, bx, t.get("pad", a.pad)) if method == "flow" else track_cv(frames, i0, bx, method)
            except cv2.error as e:
                print(f"!! {method} failed on {t['label']} ({e.msg if hasattr(e, 'msg') else e}); falling back to flow"); res = track_flow(frames, i0, bx)
            seq = smooth([res[i] for i in range(len(frames))])
        kf = [[round(i / fps, 3), round(b[0] / W, 4), round(b[1] / H, 4), round(b[2] / W, 4), round(b[3] / H, 4)] for i, b in enumerate(seq) if i % step == 0 or i == len(seq) - 1]
        targets.append({"id": t.get("id", f"t{k}"), "label": t["label"], "sub": t.get("sub", ""), "kf": kf})
        print(f"{cid} {t['label']}: {len(kf)} keyframes")
    out = {"space": "video", "size": [W, H], "fps": fps, "method": method, "seed_t": i0 / fps, "targets": targets}
    p = ann_dir(a.clip) / f"{cid}.json"; p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8"); print("wrote", p)
    if a.preview:
        vw = cv2.VideoWriter(str(ann_dir(a.clip) / f"{cid}_preview.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
        for i, fr in enumerate(frames):
            im = fr.copy()
            for t in targets:
                x, y, w, h = interp(t["kf"], i / fps); x, y, w, h = x * W, y * H, w * W, h * H
                cv2.rectangle(im, (int(x), int(y)), (int(x + w), int(y + h)), (0, 255, 255) if t.get("hand") else (255, 255, 255), 2)
                cv2.putText(im, t["id"], (int(x) + 4, int(y) + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(im, f"{i / fps:.2f}s", (10, H - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            vw.write(im)
        vw.release(); print("preview", ann_dir(a.clip) / f"{cid}_preview.mp4")

def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("grid"); g.add_argument("clip"); g.add_argument("--t", type=float, default=0.4)
    t = sp.add_parser("track"); t.add_argument("clip"); t.add_argument("--method", default="auto"); t.add_argument("--step", type=int, default=3)
    t.add_argument("--t0", type=float, default=0.4); t.add_argument("--preview", action="store_true")
    t.add_argument("--pad", type=float, default=0.25, help="grow the feature mask by this fraction of the box (per side); per-target 'pad' in the seed overrides")
    a = ap.parse_args(); {"grid": cmd_grid, "track": cmd_track}[a.cmd](a)

if __name__ == "__main__":
    main()
