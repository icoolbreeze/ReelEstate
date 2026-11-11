"""Local person matting (torch + numpy + ffmpeg).

Default engine is MatAnyone2; RobustVideoMatting stays as the automatic backup.

    python scripts/matting/matte_local.py IN.mp4 [IN2.mp4 ...] [--out DIR]
        [--engine matanyone2|rvm] [--mask MASK.png] [--max-size 1080] [--no-fallback]
        (RVM only: [--model resnet50|mobilenetv3] [--downsample 0.4] [--fp16])

Per input writes into --out (default: <episode>/footage/matte/ inside an episode, else <input dir>/../matte/):
  <stem>_rgba.mov    ProRes 4444 + alpha (yuva444p10le)  -> editing / master
  <stem>_alpha.webm  VP9 + alpha (yuva420p)              -> Remotion <OffthreadVideo transparent>
  <stem>_check.mp4   grayscale matte, H.264              -> QA
The MatAnyone2 path additionally writes its first-frame RVM seed mask:
  <stem>_mask.png    binary first-frame mask (or use --mask to supply one)

Weights (all gitignored, downloaded on first run):
  vendor/rvm/rvm_<model>_fp32.torchscript
  vendor/matanyone2/pretrained_models/matanyone2.pth
"""
import argparse, json, shutil, subprocess, sys, time, urllib.request
from pathlib import Path
import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from pipeline.common.matte_size import acceptance, inference_size, oom_note, use_fp16  # noqa: E402
from pipeline.common.color_restore import restored_for_any  # noqa: E402
WDIR = REPO / "vendor" / "rvm"
M2DIR = REPO / "vendor" / "matanyone2" / "pretrained_models"
URL = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_{m}_fp32.torchscript"
M2_URL = "https://github.com/pq-yang/MatAnyone2/releases/download/v1.0.0/matanyone2.pth"
N_WARMUP = 10          # upstream MatAnyone2 first-frame warmup iterations
MASK_KERNEL = 10       # upstream dilate/erode kernel on the seed mask
FF = shutil.which("ffmpeg") or sys.exit("ffmpeg not found")

_RVM_CACHE = {}


def weights(m):
    p = WDIR / f"rvm_{m}_fp32.torchscript"
    if not p.is_file():
        WDIR.mkdir(parents=True, exist_ok=True)
        print("downloading", p.name)
        urllib.request.urlretrieve(URL.format(m=m), p)
    return p


def m2_weights():
    p = M2DIR / "matanyone2.pth"
    if not p.is_file():
        M2DIR.mkdir(parents=True, exist_ok=True)
        print("downloading", p.name)
        urllib.request.urlretrieve(M2_URL, p)
    return p


def probe(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate", "-of", "json", str(f)],
                       capture_output=True, text=True, check=True)
    s = json.loads(r.stdout)["streams"][0]
    return s["width"], s["height"], s["r_frame_rate"]


def enc(args):
    return subprocess.Popen([FF, "-y", "-loglevel", "error", *args], stdin=subprocess.PIPE)


def open_encoders(out, stem, w, h, fps):
    raw = ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", fps, "-i", "-"]
    e_pro = enc(raw + ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                       "-alpha_bits", "16", str(out / f"{stem}_rgba.mov")])
    e_webm = enc(raw + ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24",
                        "-row-mt", "1", "-auto-alt-ref", "0", str(out / f"{stem}_alpha.webm")])
    e_chk = enc(["-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", fps, "-i", "-",
                 "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(out / f"{stem}_check.mp4")])
    return e_pro, e_webm, e_chk


def default_out(f):
    """<episode>/footage/matte for any input inside an episode (raw, restored/master, shots, heygen)."""
    f = Path(f).resolve()
    for parent in f.parents:
        if (parent / "episode.yaml").is_file():
            return parent / "footage" / "matte"
    return f.parent.parent / "matte"


def out_names(stem):
    return (f"{stem}_rgba.mov", f"{stem}_alpha.webm", f"{stem}_check.mp4")


def rvm_model(model_name, dev, fp16):
    key = (model_name, dev, fp16)
    if key not in _RVM_CACHE:
        m = torch.jit.load(str(weights(model_name)), map_location=dev).eval()
        m = torch.jit.freeze(m)
        if fp16 and dev == "cuda":
            m = m.half()
        _RVM_CACHE[key] = m
    return _RVM_CACHE[key]


def read_frame_rgb(f, w, h):
    """Decode one frame (the first by default) as a uint8 HxWx3 RGB ndarray."""
    dec = subprocess.Popen([FF, "-loglevel", "error", "-i", str(f), "-frames:v", "1",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    buf = dec.stdout.read(w * h * 3)
    dec.wait()
    if len(buf) < w * h * 3:
        raise RuntimeError("could not decode first frame")
    return np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)


def rvm_seed_mask(f, out, stem, model_name, downsample, dev):
    """Build a binary first-frame mask with RVM resnet50: <stem>_mask.png."""
    w, h, _ = probe(f)
    frame = read_frame_rgb(f, w, h)
    src = torch.from_numpy(frame).to(dev).permute(2, 0, 1)[None].float() / 255
    with torch.no_grad():
        _, pha, *_ = rvm_model(model_name, dev, False)(src, None, None, None, None, downsample)
    alpha = pha[0, 0].cpu().numpy()
    if not (alpha > 0.5).any():
        raise RuntimeError("rvm seed mask is empty (no person detected)")
    mask = np.where(alpha > 0.5, 255, 0).astype(np.uint8)
    from PIL import Image
    p = out / f"{stem}_mask.png"
    Image.fromarray(mask, mode="L").save(p)
    return p


def rvm_one(f, out, model_name, downsample, fp16, dev):
    """Today's RobustVideoMatting path, unchanged."""
    model = rvm_model(model_name, dev, fp16)
    dt = torch.float16 if (fp16 and dev == "cuda") else torch.float32
    w, h, fps = probe(f)
    e_pro, e_webm, e_chk = open_encoders(out, f.stem, w, h, fps)
    dec = subprocess.Popen([FF, "-loglevel", "error", "-i", str(f), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    rec = [None] * 4
    n, t0, fsz = 0, time.time(), w * h * 3
    with torch.no_grad():
        while True:
            buf = dec.stdout.read(fsz)
            if len(buf) < fsz:
                break
            src = torch.frombuffer(bytearray(buf), dtype=torch.uint8).to(dev).view(h, w, 3)
            src = src.permute(2, 0, 1)[None].to(dt) / 255
            fgr, pha, *rec = model(src, *rec, downsample)
            rgba = (torch.cat([fgr, pha], 1)[0].permute(1, 2, 0).clamp(0, 1) * 255 + 0.5).byte().cpu().numpy()
            b = rgba.tobytes()
            e_pro.stdin.write(b); e_webm.stdin.write(b)
            e_chk.stdin.write(np.ascontiguousarray(rgba[..., 3]).tobytes())
            n += 1
    dec.wait()
    for e in (e_pro, e_webm, e_chk):
        e.stdin.close(); e.wait()
    return n, time.time() - t0


def matanyone2_one(f, out, explicit_mask, max_size, rvm_model_name, downsample, dev):
    """MatAnyone2 path. Raises on any failure (caller falls back to RVM)."""
    import torch.nn.functional as F
    from PIL import Image
    from matanyone2.inference.inference_core import InferenceCore
    from matanyone2.utils.get_default_model import get_matanyone2_model
    from matanyone2.utils.inference_utils import gen_dilate, gen_erosion

    if dev != "cuda":
        raise RuntimeError("MatAnyone2 needs CUDA on this machine")
    w, h, fps = probe(f)

    if explicit_mask:
        mask_path = Path(explicit_mask)
        if not mask_path.is_file():
            raise RuntimeError(f"mask not found: {mask_path}")
    else:
        mask_path = rvm_seed_mask(f, out, f.stem, rvm_model_name, downsample, dev)

    # load mask + upstream morphology
    mask_np = np.array(Image.open(mask_path).convert("L"))
    mask_np = gen_dilate(mask_np, MASK_KERNEL, MASK_KERNEL)
    mask_np = gen_erosion(mask_np, MASK_KERNEL, MASK_KERNEL)

    mat = get_matanyone2_model(str(m2_weights()), dev)
    processor = InferenceCore(mat, cfg=mat.cfg)

    # processing size: short-side cap. Never upscale. 4K inferred below 4K is not native 4K.
    sized = inference_size(w, h, max_size)
    nh, nw = sized["inference_height"], sized["inference_width"]
    mask_t = torch.from_numpy(mask_np).float().to(dev)
    if (nh, nw) != (h, w):
        mask_t = F.interpolate(mask_t[None, None], size=(nh, nw), mode="nearest")[0, 0]

    e_pro, e_webm, e_chk = open_encoders(out, f.stem, w, h, fps)
    dec = subprocess.Popen([FF, "-loglevel", "error", "-i", str(f), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    fsz = w * h * 3
    n, t0 = 0, time.time()

    def step_to_rgba(img0, n_th):
        """Run one processor step on a full-res float [3,H,W] /255 image; return rgba uint8."""
        simg = img0
        if (nh, nw) != (h, w):
            simg = F.interpolate(img0[None], size=(nh, nw), mode="area")[0]
        if n_th == 0:
            output_prob = processor.step(simg, mask_t, objects=[1])   # encode given mask
            output_prob = processor.step(simg, first_frame_pred=True)
        elif n_th <= N_WARMUP:
            output_prob = processor.step(simg, first_frame_pred=True)
        else:
            output_prob = processor.step(simg)
        m = processor.output_prob_to_mask(output_prob).clamp(0, 1)   # [nh,nw]
        if (nh, nw) != (h, w):
            m = F.interpolate(m[None, None], size=(h, w), mode="bilinear", align_corners=False)[0, 0]
        alpha = (m * 255 + 0.5).byte().cpu().numpy()
        rgb = (img0.permute(1, 2, 0) * 255 + 0.5).byte().cpu().numpy()
        return np.dstack([rgb, alpha])

    try:
        with torch.inference_mode():  # fp32; no fp16 on Pascal
            buf = dec.stdout.read(fsz)
            if len(buf) < fsz:
                raise RuntimeError("could not decode first frame")
            img0 = torch.frombuffer(bytearray(buf), dtype=torch.uint8).to(dev).view(h, w, 3)
            img0 = img0.permute(2, 0, 1).float() / 255
            # upstream warmup: first frame repeated; emit once after N_WARMUP reps
            rgba = None
            for ti in range(N_WARMUP + 1):
                rgba = step_to_rgba(img0, ti)
            b = rgba.tobytes()
            e_pro.stdin.write(b); e_webm.stdin.write(b)
            e_chk.stdin.write(np.ascontiguousarray(rgba[..., 3]).tobytes())
            n += 1
            while True:
                buf = dec.stdout.read(fsz)
                if len(buf) < fsz:
                    break
                img = torch.frombuffer(bytearray(buf), dtype=torch.uint8).to(dev).view(h, w, 3)
                img = img.permute(2, 0, 1).float() / 255
                rgba = step_to_rgba(img, N_WARMUP + n)
                b = rgba.tobytes()
                e_pro.stdin.write(b); e_webm.stdin.write(b)
                e_chk.stdin.write(np.ascontiguousarray(rgba[..., 3]).tobytes())
                n += 1
    finally:
        dec.wait()
        for e in (e_pro, e_webm, e_chk):
            try:
                e.stdin.close()
            except (BrokenPipeError, OSError):
                pass
            e.wait()
    return n, time.time() - t0


def cleanup_others(out, before, keep):
    """Remove files MatAnyone2 may drop that are not our three outputs or seed mask."""
    for p in out.iterdir():
        if p.name not in before and p.name not in keep and p.is_file():
            try:
                p.unlink()
            except OSError:
                pass


def remove_partials(out, stem):
    for name in out_names(stem):
        p = out / name
        if p.is_file():
            p.unlink()


def write_matte_report(out, stem, payload):
    path = Path(out) / f"{stem}_report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out")
    ap.add_argument("--engine", choices=["matanyone2", "rvm"], default="matanyone2",
                    help="matting engine (default: matanyone2; rvm is the automatic backup)")
    ap.add_argument("--mask", help="first-frame binary mask PNG for MatAnyone2 (default: RVM seeds one)")
    ap.add_argument("--max-size", type=int, default=1080,
                    help="MatAnyone2: downsample when the short side exceeds this (default: 1080; smaller inputs are not upscaled)")
    ap.add_argument("--no-fallback", action="store_true",
                    help="exit non-zero instead of falling back to RVM")
    ap.add_argument("--model", default="resnet50", help="RVM only: resnet50 (default) | mobilenetv3")
    ap.add_argument("--downsample", type=float, default=0.4, help="RVM only (default: 0.4)")
    ap.add_argument("--fp16", action="store_true", help="RVM only; slow on Pascal (1070 Ti); off by default")
    a = ap.parse_args()

    if a.mask and len(a.inputs) > 1:
        ap.error("--mask can only be used with a single input video")

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print("device:", dev, torch.cuda.get_device_name(0) if dev == "cuda" else "")

    report, failed = [], False
    for f in (restored_for_any(Path(x), "matte") for x in a.inputs):   # D-Log M camera clips -> restored ProRes
        out = Path(a.out) if a.out else default_out(f)
        out.mkdir(parents=True, exist_ok=True)
        keep = set(out_names(f.stem)) | {f"{f.stem}_mask.png"}
        before = {p.name for p in out.iterdir()}

        requested = a.engine
        fallback_reason = None
        actual = requested
        n, dt_s = 0, 0.0
        if requested == "matanyone2" and a.fp16:
            print("fp16 ignored: MatAnyone2 stays fp32 on this machine")
        if requested == "rvm":
            n, dt_s = rvm_one(f, out, a.model, a.downsample, use_fp16("rvm", a.fp16), dev)
            print("engine: rvm")
        else:
            try:
                n, dt_s = matanyone2_one(f, out, a.mask, a.max_size, a.model, a.downsample, dev)
                cleanup_others(out, before, keep)
                print("engine: matanyone2")
            except Exception as e:  # import / download / CUDA / OOM / inference -> RVM
                reason = f"{type(e).__name__}: {e}".replace("\n", " ")[:300]
                fallback_reason = reason
                actual = "failed" if a.no_fallback else "rvm"
                remove_partials(out, f.stem)
                if dev == "cuda":
                    torch.cuda.empty_cache()
                oom = oom_note(reason)
                if a.no_fallback:
                    print(f"engine: failed (fallback disabled: {reason})")
                    if oom:
                        print(oom)
                    failed_report = acceptance(requested, "failed", reason)
                    failed_report.update({"matanyone2_passed": False, "frames": 0, "fp16": False, "max_size": a.max_size, "oom": oom})
                    write_matte_report(out, f.stem, failed_report)
                    failed = True
                    continue
                n, dt_s = rvm_one(f, out, a.model, a.downsample, use_fp16("rvm", a.fp16), dev)
                print(f"engine: rvm (fallback: {reason})")
                if oom:
                    print(oom)
                print("matanyone2_passed: false")

        missing = [nm for nm in out_names(f.stem) if not (out / nm).is_file()]
        if missing:
            print("missing outputs:", ", ".join(missing))
            failed = True
            continue
        sized = None
        try:
            pw, ph, _fps = probe(f)
            sized = inference_size(pw, ph, a.max_size if requested == "matanyone2" else 0)
        except (OSError, subprocess.CalledProcessError, ValueError, KeyError):
            sized = None
        r = acceptance(requested, actual, fallback_reason)
        r.update({"input": str(f), "out": str(out), "frames": n, "seconds": round(dt_s, 1),
                  "fps": round(n / dt_s, 2) if dt_s else None, "fp16": use_fp16(actual if actual != "failed" else requested, a.fp16),
                  "max_size": a.max_size, "mask": a.mask})
        if sized:
            r.update(sized)
            if sized["mask_interpolated_to_output"]:
                r["size_note"] = "遮罩已插值回输入尺寸，不能标成该档原生抠像。"
                r["native_4k"] = False
        if fallback_reason:
            r["inference_note"] = "实际引擎不是 MatAnyone2。上面的推理尺寸只描述原先请求，不能当作 MatAnyone2 验收。"
        write_matte_report(out, f.stem, r)
        print(json.dumps(r, ensure_ascii=False)); report.append(r)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
