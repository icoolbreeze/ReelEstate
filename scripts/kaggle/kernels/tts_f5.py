# Kaggle kernel: batch F5-TTS voice clone. Inputs + job.json in /kaggle/input/<slug>/, outputs to /kaggle/working/out/
import glob, json, subprocess, sys
from pathlib import Path

INP = Path(glob.glob("/kaggle/input/*/job.json")[0]).parent
OUT = Path("/kaggle/working/out"); OUT.mkdir(parents=True, exist_ok=True)
job = json.loads((INP / "job.json").read_text(encoding="utf-8"))
P = job.get("params", {})
ref_wav = INP / P.get("ref", next(n for n in job["inputs"] if n.lower().endswith(".wav")))
script_f = INP / P.get("script", next(n for n in job["inputs"] if n.lower().endswith(".json")))
speed = float(P.get("speed", 1.0)); nfe = int(P.get("nfe", 32))

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "f5-tts"], check=True)
from f5_tts.api import F5TTS  # noqa: E402

data = json.loads(script_f.read_text(encoding="utf-8"))
lines = data if isinstance(data, list) else data.get("lines", [])
ref_text = P.get("ref_text") or (data.get("ref_text", "") if isinstance(data, dict) else "")
if not ref_text and Path(str(ref_wav) + ".txt").is_file():
    ref_text = Path(str(ref_wav) + ".txt").read_text(encoding="utf-8").strip()
# empty ref_text -> F5 auto-transcribes the reference with Whisper

tts = F5TTS(model=P.get("model", "F5TTS_v1_Base"))
manifest = []
for i, ln in enumerate(lines):
    lid = ln.get("id") or f"L{i+1:02d}"
    text = ln.get("text") or ln.get("line") or ""
    if not text.strip():
        continue
    out = OUT / f"{lid}.wav"
    wav, sr, _ = tts.infer(ref_file=str(ref_wav), ref_text=ref_text, gen_text=text,
                           file_wave=str(out), speed=float(ln.get("speed", speed)), nfe_step=nfe, seed=-1)
    manifest.append({"id": lid, "text": text, "file": out.name, "sr": sr, "seconds": round(len(wav) / sr, 2)})
    print(lid, manifest[-1]["seconds"], "s")

(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
