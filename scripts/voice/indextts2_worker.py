"""IndexTTS2 emotive voice-clone worker (run inside vendor/indextts2/.venv).
Usage: python scripts/voice/indextts2_worker.py script.json [--out DIR]

script.json: {"spk_ref"?: "voices/clone/reference.wav" (alias "ref_wav"),
              "out"?: "dir",
              "lines": [{"id": "HOOK", "variants": [{"v": "a",
                         "segments": [{"text": "...", "emo_text"?: str,
                                       "emo_vector"?: [8 floats] | {emo: float},
                                       "emo_alpha"?: float}]}]}]}
Each segment is synthesized on its own with its own emotion and the waveforms
are concatenated with punctuation-based gaps. Writes <id>[_<v>].wav +
timings.json. fp32 by default (Pascal sm_61 has no bf16); DeepSpeed and
custom CUDA kernels are never enabled."""
import sys, os, json, time, argparse, subprocess, tempfile, shutil, traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENDOR = os.path.join(ROOT, "vendor", "indextts2")
CACHE = os.path.join(VENDOR, ".cache")
# Redirect every HF / ModelScope download into the vendor cache BEFORE imports.
os.environ.setdefault("HF_HOME", CACHE)
os.environ.setdefault("HF_HUB_CACHE", os.path.join(CACHE, "hub"))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", os.path.join(CACHE, "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", os.path.join(CACHE, "transformers"))
os.environ.setdefault("MODELSCOPE_CACHE", os.path.join(CACHE, "modelscope"))
sys.path.insert(0, VENDOR)
# facebook/w2v-bert-2.0 is offline. The weights live next to the vendor tree.
os.environ["INDEXTTS_W2V_BERT"] = os.path.join(VENDOR, "w2v-bert-2.0")

DEFAULT_MODEL_DIR = r"C:\Users\shipi\vswp\QWAN-Terminal\QWANagent\ModelServices\models\IndexTTS2"
EMO_ORDER = ["happy", "angry", "sad", "afraid", "disgusted", "melancholic", "surprised", "calm"]


def clear_segment_temps(out):
    """Remove leftover .segments_* directories from a crashed synthesis."""
    if not out or not os.path.isdir(out):
        return
    for name in os.listdir(out):
        if not name.startswith(".segments_"):
            continue
        path = os.path.join(out, name)
        if os.path.isdir(path):
            print(">> removing stale {}".format(path), flush=True)
            shutil.rmtree(path, ignore_errors=True)


def _is_oom(exc):
    return isinstance(exc, RuntimeError) and "out of memory" in str(exc).lower()


def note_peak(peak):
    """Track the high-water GPU used memory and this process's torch peak."""
    snap = vram_snapshot()
    used = snap.get("used_mib")
    if isinstance(used, int):
        peak["nvidia_used_mib"] = max(peak.get("nvidia_used_mib") or 0, used)
    try:
        import torch
        if torch.cuda.is_available():
            peak["torch_reserved_mib"] = max(
                peak.get("torch_reserved_mib") or 0,
                int(torch.cuda.max_memory_reserved() / (1024 * 1024)),
            )
            peak["torch_allocated_mib"] = max(
                peak.get("torch_allocated_mib") or 0,
                int(torch.cuda.max_memory_allocated() / (1024 * 1024)),
            )
    except Exception:
        pass
    return snap


def vram_snapshot():
    """nvidia-smi used/free MiB; error dict if it cannot be queried."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            text=True, timeout=20, stderr=subprocess.STDOUT)
        used, free = out.strip().splitlines()[0].split(",")[:2]
        return {"used_mib": int(used), "free_mib": int(free)}
    except Exception as e:
        return {"error": "{}: {}".format(type(e).__name__, str(e).strip())}


def to_emo_vector(v):
    """8-float list in EMO_ORDER from a list (len 8) or dict."""
    if isinstance(v, dict):
        return [float(v.get(k, 0.0) or 0.0) for k in EMO_ORDER]
    if isinstance(v, list) and len(v) == 8:
        return [float(x) for x in v]
    raise ValueError("emo_vector must be a list of 8 floats or a dict, got {!r}".format(v))


def gap_ms(text):
    """Silence after a segment based on the last char of its stripped text."""
    t = text.strip()
    if not t:
        return 200
    last = t[-1]
    if last in "，,、—–-－~～":
        return 150
    if last in "。！？!?…":
        return 250
    return 200


def segment_kwargs(seg):
    """Build infer() kwargs for one segment (emotion rules, use_random=False)."""
    alpha = seg.get("emo_alpha", 1.0)
    alpha = float(alpha) if alpha is not None else 1.0
    kw = {"use_random": False}
    ev = seg.get("emo_vector")
    if ev is not None:
        kw.update(emo_vector=to_emo_vector(ev), use_emo_text=False, emo_alpha=alpha)
    else:
        et = seg.get("emo_text")
        if isinstance(et, str) and et.strip():
            kw.update(use_emo_text=True, emo_text=et, emo_alpha=alpha)
        elif "emo_alpha" in seg and seg["emo_alpha"] is not None:
            kw["emo_alpha"] = float(seg["emo_alpha"])
    return kw


class PersistentOOM(Exception):
    pass


def synth_segment(m, spk_ref, seg, tmp_path, oom_log):
    """Synthesize one segment to tmp_path; retry once in fp32 after OOM."""
    text = seg["text"]
    kw = segment_kwargs(seg)
    try:
        m.infer(spk_audio_prompt=spk_ref, text=text, output_path=tmp_path, **kw)
    except RuntimeError as e:
        msg = str(e)
        if "out of memory" not in msg.lower():
            raise
        oom_log.append(msg)
        print(">> CUDA OOM; emptying cache and retrying once in fp32", flush=True)
        import torch
        torch.cuda.empty_cache()
        try:
            m.infer(spk_audio_prompt=spk_ref, text=text, output_path=tmp_path, **kw)
        except RuntimeError as e2:
            if "out of memory" not in str(e2).lower():
                raise
            oom_log.append(str(e2))
            raise PersistentOOM(str(e2))


def build_model(model_dir, use_fp16):
    import torch  # noqa
    from indextts.infer_v2 import IndexTTS2
    from indextts.utils.model_download import ensure_models_available
    # Aux models live in the vendor cache, never inside the QWAN weights folder.
    aux_root = os.path.join(CACHE, "auxmodels")
    aux_paths = ensure_models_available(aux_root)
    t = time.time()
    m = IndexTTS2(
        cfg_path=os.path.join(model_dir, "config.yaml"),
        model_dir=model_dir,
        use_fp16=use_fp16,
        use_cuda_kernel=False,
        use_deepspeed=False,
        use_qwen_emo=True,
        aux_paths=aux_paths,
    )
    return m, time.time() - t


def resolve_items(cfg, base):
    p = lambda x: x if os.path.isabs(x) else (
        os.path.join(base, x) if os.path.exists(os.path.join(base, x)) else os.path.join(ROOT, x))
    spk_ref = p(cfg.get("spk_ref") or cfg.get("ref_wav") or "assets/presenter/cool-breeze/voice/ref_phone_v1.wav")
    items = []
    for i, ln in enumerate(cfg["lines"]):
        if isinstance(ln, str):
            ln = {"id": "line{:02d}".format(i + 1), "text": ln}
        if "variants" in ln:
            for var in ln["variants"]:
                segs = var.get("segments")
                if segs is None:
                    segs = [{"text": var["text"]}]
                items.append(("{}_{}".format(ln["id"], var["v"]), segs))
        else:
            segs = ln.get("segments")
            if segs is None:
                segs = [{"text": ln["text"]}]
            items.append((ln["id"], segs))
    return spk_ref, items


def run_all(model_dir, out, spk_ref, items, use_fp16, vram_before, oom_log):
    import torch, torchaudio
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.empty_cache()
    m, load_s = build_model(model_dir, use_fp16)
    clear_segment_temps(out)
    tmp_dir = tempfile.mkdtemp(prefix=".segments_", dir=out)
    peak = {}
    note_peak(peak)
    tim = {
        "engine": "indextts2",
        "model": "IndexTTS2",
        "model_dir": os.path.abspath(model_dir),
        "fp16": bool(use_fp16),
        "load_s": round(load_s, 1),
        "w2v_bert": os.environ.get("INDEXTTS_W2V_BERT"),
        "vram": {"before_load": vram_before, "after_first_file": None, "peak": peak},
        "lines": [],
    }
    sum_gen = sum_dur = 0.0
    try:
        for idx, (fid, segs) in enumerate(items):
            final_path = os.path.join(out, fid + ".wav")
            t = time.time()
            parts = []
            sr = None
            for j, seg in enumerate(segs):
                tmp_path = os.path.join(tmp_dir, "{}_{}.wav".format(fid, j))
                synth_segment(m, spk_ref, seg, tmp_path, oom_log)
                wav, sr = torchaudio.load(tmp_path)
                parts.append(wav)
                if j < len(segs) - 1:
                    parts.append(torch.zeros(wav.shape[0], int(sr * gap_ms(seg["text"]) / 1000.0)))
                os.remove(tmp_path)
            wav = torch.cat(parts, dim=1)
            torchaudio.save(final_path, wav, sr)
            dur = wav.shape[1] / sr
            gen = time.time() - t
            sum_gen += gen
            sum_dur += dur
            tim["lines"].append({
                "id": fid,
                "path": os.path.abspath(final_path),
                "gen_s": round(gen, 2),
                "audio_s": round(dur, 2),
                "rtf": round(gen / dur, 2) if dur else 0.0,
                "segments": len(segs),
            })
            print("{} {:.1f}s for {:.1f}s audio".format(fid, gen, dur), flush=True)
            snap = note_peak(peak)
            if idx == 0:
                tim["vram"]["after_first_file"] = snap
        tim["rtf"] = round(sum_gen / sum_dur, 2) if sum_dur else 0.0
        note_peak(peak)
        tim["vram"]["peak_vram_mib"] = peak.get("nvidia_used_mib")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return tim


def print_summary(tim):
    print("---- A3 SUMMARY ----", flush=True)
    for line in tim.get("lines") or []:
        print(
            "WAV {} duration_s={} synthesis_s={}".format(
                line.get("path"), line.get("audio_s"), line.get("gen_s")),
            flush=True,
        )
    print("MODEL_LOAD_S={}".format(tim.get("load_s")), flush=True)
    print("PEAK_VRAM_MIB={}".format((tim.get("vram") or {}).get("peak_vram_mib")), flush=True)
    print("DONE_A", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = json.load(open(a.script, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(a.script))
    spk_ref, items = resolve_items(cfg, base)
    out = a.out or cfg.get("out") or os.path.join(base, "tts")
    if not os.path.isabs(out):
        out = os.path.join(ROOT, out)
    os.makedirs(out, exist_ok=True)
    clear_segment_temps(out)
    model_dir = os.environ.get("INDEXTTS2_MODEL_DIR") or DEFAULT_MODEL_DIR

    oom_log = []
    vram_before = vram_snapshot()
    try:
        tim = run_all(model_dir, out, spk_ref, items, False, vram_before, oom_log)
    except PersistentOOM as e:
        # fp32 could not fit; restart the whole run in fp16 so samples exist.
        print(">> fp32 OOM persists; restarting run with use_fp16=True", flush=True)
        import torch
        torch.cuda.empty_cache()
        oom_reason = str(e)
        tim = run_all(model_dir, out, spk_ref, items, True, vram_before, oom_log)
        tim["fp16_fallback_reason"] = oom_reason
    except RuntimeError as e:
        if not _is_oom(e):
            raise
        print(">> fp32 load OOM; restarting run with use_fp16=True", flush=True)
        import torch
        torch.cuda.empty_cache()
        oom_reason = str(e)
        tim = run_all(model_dir, out, spk_ref, items, True, vram_before, oom_log)
        tim["fp16_fallback_reason"] = oom_reason
    except Exception:
        tim = {
            "engine": "indextts2", "model": "IndexTTS2",
            "model_dir": os.path.abspath(model_dir), "fp16": False,
            "vram": {"before_load": vram_before, "after_first_file": None,
                     "oom_text": oom_log or traceback.format_exc()},
            "lines": [],
        }
        with open(os.path.join(out, "timings.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(tim, f, indent=1)
        raise

    tim["vram"]["oom_text"] = oom_log or None
    with open(os.path.join(out, "timings.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(tim, f, indent=1)
    print("OVERALL_RTF={:.2f} LINES={}".format(tim["rtf"], len(tim["lines"])))
    print_summary(tim)


if __name__ == "__main__":
    main()
