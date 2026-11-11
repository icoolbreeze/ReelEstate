"""Voiceover TTS for ReelEstate. Default engine flova_minimax (MiniMax Speech 2.8 HD preset Gentle_Youth via flova CLI,
scripts/voice/flova_minimax_tts.py). Fallbacks: indextts25 (Kaggle), then local F5 (last resort). Also cosyvoice / indextts2 / mimo.
Usage: python scripts\voice\clone_tts.py script.json [--out DIR] [--engine flova_minimax|indextts25|f5|cosyvoice|indextts2|mimo] [--auto-fallback] [--fp16]
script.json: {"engine": "cosyvoice|f5", "ref_wav": "assets/presenter/cool-breeze/voice/ref_phone_v1.wav" (default; fallback voices/clone/reference.wav),
              "ref_text": "voices/clone/reference.txt" (file or literal),
              "lines": [{"id": "s01", "text": "...", "seed"?: int, "speed"?: float}, ...]}
              (lines may also be plain strings)
Writes DIR/<id>.wav + DIR/timings.json. fp32 (Pascal has no bf16)."""
import sys, os, json, time, argparse, subprocess
from pathlib import Path
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ap = argparse.ArgumentParser()
ap.add_argument("script")
ap.add_argument("--out")
ap.add_argument("--episode", help="resolve shared presenter and per-episode voice settings")
ap.add_argument("--fp16", action="store_true")
ap.add_argument("--tempo", type=float, help="flova_minimax: pitch-preserving atempo (default 1.1 / presenter voice.tempo)")
ap.add_argument("--mode", choices=["passage", "line"], help="flova_minimax: one call for the whole passage (default) or one per line")
ap.add_argument("--no-retime", action="store_true", help="flova_minimax passage mode: skip pause retiming")
ap.add_argument("--no-timings", action="store_true", help="flova_minimax passage mode: skip Whisper timings/split")
ap.add_argument("--auto-fallback", action="store_true", help="flova_minimax: on failure run local F5 (last resort) after printing the indextts25 command")
ap.add_argument("--engine", choices=["flova_minimax", "cosyvoice", "f5", "indextts2", "indextts25", "mimo"], default=None)
a = ap.parse_args()
cfg = json.load(open(a.script, encoding="utf-8"))
engine = a.engine or cfg.get("engine") or "flova_minimax"
if engine == "flova_minimax":
    # Default voiceover (approved 2026-10-12). Text goes verbatim to flova; no speaker ref needed.
    script_path = a.script
    if a.episode:
        sys.path.insert(0, os.path.join(ROOT, "pipeline", "maphub"))
        from voice_config import prepare_narration
        cfg, _voice = prepare_narration(Path(a.episode), cfg, engine=engine)
        script_path = os.path.join(a.out or os.path.dirname(os.path.abspath(a.script)), "resolved_flova_minimax.json")
        os.makedirs(os.path.dirname(script_path), exist_ok=True)
        json.dump(cfg, open(script_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "voice", "flova_minimax_tts.py"), script_path]
    if a.out: cmd += ["--out", a.out]
    if cfg.get("voice"): cmd += ["--voice", cfg["voice"]]
    if cfg.get("flova_profile"): cmd += ["--profile", cfg["flova_profile"]]
    tempo = a.tempo or cfg.get("tempo")
    if tempo: cmd += ["--tempo", str(tempo)]
    mode = a.mode or cfg.get("mode")
    if mode: cmd += ["--mode", mode]
    if a.no_retime: cmd += ["--no-retime"]
    if a.no_timings: cmd += ["--no-timings"]
    rc = subprocess.call(cmd)
    if rc == 21:
        print("flova_minimax failed. Fallback 1 (Kaggle): C:\\ProgramData\\miniconda3\\python.exe scripts\\voice\\push_indextts25.py --episode <EP> --script <json>")
        if a.auto_fallback:
            print("--auto-fallback: running local F5 (last resort)")
            f5 = [os.path.join(ROOT, "scripts", "voice", "clone_tts_f5.cmd"), a.script] + (["--out", a.out] if a.out else []) + (["--episode", a.episode] if a.episode else [])
            rc = subprocess.call(["cmd", "/c", *f5])
    sys.exit(rc)
if a.episode:
    sys.path.insert(0, os.path.join(ROOT, "pipeline", "maphub"))
    from voice_config import prepare_narration
    cfg, _voice = prepare_narration(Path(a.episode), cfg, engine=engine)
if engine == "indextts25":
    raise SystemExit("indextts25 (default) runs on Kaggle: python scripts/voice/push_indextts25.py --episode <ep> --script <json>; local F5: --engine f5")

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
# F5 clips refs >12 s (ref_text then mismatches and the ref tail leaks into output), so F5 defaults to a 6.6 s cut.
_dref = "assets/presenter/cool-breeze/voice/ref_phone_v1_f5" if engine == "f5" else "assets/presenter/cool-breeze/voice/ref_phone_v1"
ref_wav = p(cfg.get("ref_wav", _dref + ".wav"))
rt = cfg.get("ref_text", _dref + ".txt")
ref_text = open(p(rt), encoding="utf-8").read().strip() if os.path.exists(p(rt)) else rt
out = a.out or cfg.get("out") or os.path.join(base, "tts")
if not os.path.isabs(out): out = os.path.join(ROOT, out)
os.makedirs(out, exist_ok=True)

t = time.time()
if engine == "mimo":
    # Xiaomi MiMo voiceclone (cloud). Key from env MIMO_API_KEY; base URL from MIMO_BASE_URL
    # (Token Plan: https://token-plan-sgp.xiaomimimo.com/v1, pay-as-you-go: https://api.xiaomimimo.com/v1).
    # Interactive use only: the Token Plan terms forbid automated backends.
    import base64, urllib.request
    MIMO_KEY = os.environ.get("MIMO_API_KEY") or sys.exit("set MIMO_API_KEY")
    MIMO_URL = os.environ.get("MIMO_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1").rstrip("/") + "/chat/completions"
    model = cfg.get("mimo_model", "mimo-v2.5-tts-voiceclone")
    _voice = "data:%s;base64,%s" % ("audio/wav" if ref_wav.lower().endswith(".wav") else "audio/mpeg",
                                     base64.b64encode(open(ref_wav, "rb").read()).decode())
    def mimo_tts(text, style=""):
        body = {"model": model, "messages": [{"role": "user", "content": style}, {"role": "assistant", "content": text}],
                "audio": {"format": "wav", "voice": _voice}}
        rq = urllib.request.Request(MIMO_URL, json.dumps(body).encode(), {"Content-Type": "application/json", "api-key": MIMO_KEY})
        d = json.load(urllib.request.urlopen(rq, timeout=300))
        return base64.b64decode(d["choices"][0]["message"]["audio"]["data"])
elif engine == "f5":
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
    if engine == "mimo":
        data = mimo_tts(ln["text"], ln.get("style", cfg.get("style", "")))
        open(f, "wb").write(data)
        import wave
        with wave.open(f) as wf: dur = wf.getnframes() / wf.getframerate()
    elif engine == "f5":
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
