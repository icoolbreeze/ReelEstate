"""Voice-clone TTS for ReelEstate (Fun-CosyVoice3 / F5-TTS / IndexTTS2).
Usage: python scripts\voice\clone_tts.py script.json [--out DIR] [--engine cosyvoice|f5|indextts2] [--fp16]
script.json: {"engine": "cosyvoice|f5", "ref_wav": "voices/clone/reference.wav",
              "ref_text": "voices/clone/reference.txt" (file or literal),
              "lines": [{"id": "s01", "text": "...", "seed"?: int, "speed"?: float}, ...]}
              (lines may also be plain strings)
Writes DIR/<id>.wav + DIR/timings.json. fp32 (Pascal has no bf16)."""
import sys, os, json, time, argparse, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ap = argparse.ArgumentParser()
ap.add_argument("script")
ap.add_argument("--out")
ap.add_argument("--fp16", action="store_true")
ap.add_argument("--engine", choices=["cosyvoice", "f5", "indextts2"], default=None)
a = ap.parse_args()
cfg = json.load(open(a.script, encoding="utf-8"))
engine = a.engine or cfg.get("engine") or "cosyvoice"

if engine == "indextts2":
    if a.fp16:
        print("note: --fp16 ignored for indextts2 (fp32; worker manages OOM fallback)")
    venv_py = os.path.join(ROOT, "vendor", "indextts2", ".venv", "Scripts", "python.exe")
    if not os.path.isfile(venv_py):
        sys.stderr.write("missing IndexTTS2 venv python: " + venv_py + "\n")
        sys.exit(2)
    cmd = [venv_py, os.path.join(ROOT, "scripts", "voice", "indextts2_worker.py"), a.script]
    if a.out:
        cmd += ["--out", a.out]
    sys.exit(subprocess.call(cmd))

base = os.path.dirname(os.path.abspath(a.script))
p = lambda x: x if os.path.isabs(x) else (os.path.join(base, x) if os.path.exists(os.path.join(base, x)) else os.path.join(ROOT, x))
ref_wav = p(cfg.get("ref_wav", "voices/clone/reference.wav"))
rt = cfg.get("ref_text", "voices/clone/reference.txt")
ref_text = open(p(rt), encoding="utf-8").read().strip() if os.path.exists(p(rt)) else rt
out = a.out or cfg.get("out") or os.path.join(base, "tts")
if not os.path.isabs(out): out = os.path.join(ROOT, out)
os.makedirs(out, exist_ok=True)

t = time.time()
if engine == "f5":
    from f5_tts.api import F5TTS
    model = "F5TTS_v1_Base"
    m = F5TTS(model=model, device="cuda", hf_cache_dir=os.path.join(ROOT, "vendor", "f5tts", "hf"))
else:
    V = os.path.join(ROOT, "vendor", "cosyvoice")
    sys.path += [V, os.path.join(V, "third_party", "Matcha-TTS")]
    import torch, torchaudio
    from cosyvoice.cli.cosyvoice import AutoModel
    MD = os.environ.get("COSYVOICE_MODEL_DIR") or os.path.join(V, "pretrained_models", "Fun-CosyVoice3-0.5B")
    model = os.path.basename(MD)
    m = AutoModel(model_dir=MD, fp16=a.fp16)
    prompt = "You are a helpful assistant.<|endofprompt|>" + ref_text

tim = {"engine": engine, "model": model, "load_s": round(time.time() - t, 1), "lines": []}
sum_gen = sum_dur = 0.0
for i, ln in enumerate(cfg["lines"]):
    if isinstance(ln, str): ln = {"id": f"line{i+1:02d}", "text": ln}
    f = os.path.join(out, ln["id"] + ".wav")
    t = time.time()
    if engine == "f5":
        wav, sr, spec = m.infer(
            ref_file=ref_wav,
            ref_text=ref_text,
            gen_text=ln["text"],
            speed=float(ln["speed"]) if "speed" in ln and ln["speed"] is not None else 1.0,
            seed=int(ln["seed"]) if "seed" in ln and ln["seed"] is not None else None,
            file_wave=f,
        )
        dur = len(wav) / sr if wav.ndim == 1 else wav.shape[-1] / sr
    else:
        if "seed" in ln and ln["seed"] is not None:
            torch.manual_seed(int(ln["seed"]))
            torch.cuda.manual_seed_all(int(ln["seed"]))
        kw = {"speed": float(ln["speed"])} if "speed" in ln and ln["speed"] is not None else {}
        chunks = [j["tts_speech"] for j in m.inference_zero_shot(ln["text"], prompt, ref_wav, stream=False, **kw)]
        w = torch.cat(chunks, dim=1)
        torchaudio.save(f, w, m.sample_rate)
        dur = w.shape[1] / m.sample_rate
    d = time.time() - t
    rec = {"id": ln["id"], "gen_s": round(d, 2), "audio_s": round(dur, 2), "rtf": round(d / dur, 2)}
    if "seed" in ln and ln["seed"] is not None: rec["seed"] = int(ln["seed"])
    if "speed" in ln and ln["speed"] is not None: rec["speed"] = float(ln["speed"])
    tim["lines"].append(rec)
    sum_gen += d; sum_dur += dur
    print(ln["id"], f"{d:.1f}s for {dur:.1f}s audio", flush=True)
tim["rtf"] = round(sum_gen / sum_dur, 2)
with open(os.path.join(out, "timings.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(tim, f, indent=1)
print(f"OVERALL_RTF={tim['rtf']:.2f} LINES={len(tim['lines'])}")
