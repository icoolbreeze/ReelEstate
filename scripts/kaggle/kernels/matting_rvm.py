# Kaggle kernel: RobustVideoMatting. Inputs + job.json in /kaggle/input/<slug>/, outputs to /kaggle/working/out/
import glob, json, os, subprocess, sys
from pathlib import Path

INP = Path(glob.glob("/kaggle/input/*/job.json")[0]).parent
OUT = Path("/kaggle/working/out"); OUT.mkdir(parents=True, exist_ok=True)
job = json.loads((INP / "job.json").read_text(encoding="utf-8"))
P = job.get("params", {})
fmt = P.get("format", "prores")          # prores | png | both
model_name = P.get("model", "resnet50")  # mobilenetv3 | resnet50
ds = float(P.get("downsample", 0.25))

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "av", "pims"], check=False)
import torch, numpy as np, av  # noqa: E402

dev = "cuda" if torch.cuda.is_available() else "cpu"
print("device", dev, torch.cuda.get_device_name(0) if dev == "cuda" else "")
model = torch.hub.load("PeterL1n/RobustVideoMatting", model_name).to(dev).eval()
if dev == "cuda":
    model = model.half()
dtype = torch.float16 if dev == "cuda" else torch.float32
manifest = []

for name in job["inputs"]:
    src = INP / name
    if src.suffix.lower() not in (".mp4", ".mov", ".mkv", ".webm"):
        continue
    stem = src.stem
    cin = av.open(str(src)); vs = cin.streams.video[0]
    fps = vs.average_rate or 30
    w, h = vs.codec_context.width, vs.codec_context.height
    pro = alpha = None
    if fmt in ("prores", "both"):
        pro = av.open(str(OUT / f"{stem}_rgba.mov"), "w")
        ps = pro.add_stream("prores_ks", rate=fps); ps.width, ps.height = w, h
        ps.pix_fmt = "yuva444p10le"; ps.options = {"profile": "4444", "qscale": "9"}
    png_dir = OUT / f"{stem}_png"
    if fmt in ("png", "both"):
        png_dir.mkdir(exist_ok=True)
    alpha = av.open(str(OUT / f"{stem}_alpha.mp4"), "w")
    as_ = alpha.add_stream("libx264", rate=fps); as_.width, as_.height = w, h; as_.pix_fmt = "yuv420p"
    rec = [None] * 4; n = 0
    with torch.no_grad():
        for frame in cin.decode(video=0):
            rgb = frame.to_ndarray(format="rgb24")
            t = torch.from_numpy(rgb).to(dev).permute(2, 0, 1)[None].to(dtype) / 255
            fgr, pha, *rec = model(t, *rec, downsample_ratio=ds)
            rgba = torch.cat([fgr, pha], 1)[0].permute(1, 2, 0).clamp(0, 1)
            rgba = (rgba.float() * 255).byte().cpu().numpy()
            if pro is not None:
                for pk in ps.encode(av.VideoFrame.from_ndarray(rgba, format="rgba")):
                    pro.mux(pk)
            if fmt in ("png", "both"):
                av.VideoFrame.from_ndarray(rgba, format="rgba").to_image().save(png_dir / f"{n:05d}.png")
            a = np.repeat(rgba[..., 3:4], 3, axis=2)
            for pk in as_.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(a), format="rgb24")):
                alpha.mux(pk)
            n += 1
    if pro is not None:
        for pk in ps.encode(): pro.mux(pk)
        pro.close()
    for pk in as_.encode(): alpha.mux(pk)
    alpha.close(); cin.close()
    manifest.append({"input": name, "frames": n, "fps": float(fps), "size": [w, h], "format": fmt})
    print("done", name, n, "frames")

(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
