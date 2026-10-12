#!/usr/bin/env python3
"""Kaggle kernel: batch IndexTTS-2.5 voice clone on one T4.

Launch only through scripts/voice/push_indextts25.py or:
  python scripts/kaggle/push_job.py --episode <ep> --job tts \\
      --kernel tts_indextts25 --run indextts25 --accelerator NvidiaTeslaT4 \\
      --inputs <ref.wav> <narration.json> --param ref=<wav> --param script=<json>

Code pin: https://github.com/index-tts/index-tts @ CODE_REV
Weights: IndexTeam/IndexTTS-2.5
T4 (compute capability 7.5) has no BF16 tensor cores, so inference is fp32
unless the GPU is Ampere or newer, or the job sets bf16=1.

Importing this module does not touch /kaggle, the network, or torch.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CODE_REV = "d9e41aac89fd00b3d71497fddb287b7f24613712"
REPO_URL = "https://github.com/index-tts/index-tts.git"
MODEL_ID = "IndexTeam/IndexTTS-2.5"
LANGS = ("ZH", "EN", "JA", "ES", "AR")
SAMPLE_RATE = 22050
_TRUE = {"1", "true", "yes"}
_FALSE = {"0", "false", "no"}


def duration_factor_for(line, default_speed):
    """Map repo speed (>1 is faster) to IndexTTS duration_factor (>1 is slower)."""
    if not isinstance(line, dict):
        raise SystemExit("line must be an object")
    if line.get("duration_factor") is not None:
        try:
            value = float(line["duration_factor"])
        except (TypeError, ValueError):
            raise SystemExit("bad duration_factor: %s" % line.get("duration_factor"))
    else:
        raw = default_speed if line.get("speed") is None else line["speed"]
        try:
            speed = float(raw)
        except (TypeError, ValueError):
            raise SystemExit("bad speed: %s" % raw)
        if speed <= 0:
            raise SystemExit("speed must be > 0, got %s" % speed)
        value = 1.0 / speed
    if not (0.5 <= value <= 2.0):
        raise SystemExit("duration_factor %s out of range 0.5-2.0" % value)
    return value


def use_bf16_for(capability_major, params):
    """bf16 only on capability >= 8, unless params['bf16'] forces it."""
    if not isinstance(params, dict):
        raise SystemExit("params must be an object")
    raw = params.get("bf16")
    if raw is not None and str(raw).strip() != "":
        token = str(raw).strip().lower()
        if token in _TRUE:
            return True
        if token in _FALSE:
            return False
        raise SystemExit("bf16 must be 0 or 1, got %s" % raw)
    return int(capability_major) >= 8


def normalize_lang(value, default="ZH"):
    token = str(default if value is None or str(value).strip() == "" else value).strip().upper()
    if token not in LANGS:
        raise SystemExit("lang must be one of %s, got %s" % (", ".join(LANGS), value))
    return token


def _safe_id(raw, index):
    lid = str(raw or ("L%02d" % index))
    if lid in (".", "..") or lid != Path(lid).name:
        raise SystemExit("unsafe line id: %s" % lid)
    return lid


def _seed(line, default_seed):
    raw = default_seed if line.get("seed") is None else line.get("seed")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise SystemExit("bad seed: %s" % raw)


def _emo_vector(line):
    raw = line.get("emo_vector")
    if not isinstance(raw, (list, tuple)) or len(raw) != 8:
        return None
    try:
        return [float(x) for x in raw]
    except (TypeError, ValueError):
        return None


def _emo_text(line):
    raw = line.get("emo_text")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw.strip()


def _emo_alpha(line):
    if line.get("emo_alpha") is None:
        return None
    try:
        value = float(line["emo_alpha"])
    except (TypeError, ValueError):
        raise SystemExit("bad emo_alpha: %s" % line.get("emo_alpha"))
    if not (0.0 <= value <= 1.0):
        raise SystemExit("emo_alpha %s out of range 0-1" % value)
    return value


def plan_lines(data, params):
    """Flat lines only. Nested variants are ignored, not expanded."""
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict):
        raw = data.get("lines") or []
    else:
        raise SystemExit("script must be an object with lines or a top-level array")
    if not isinstance(raw, list):
        raise SystemExit("lines must be an array")
    default_speed = float(params.get("speed", 1.0))
    default_lang = params.get("lang")
    default_seed = params.get("seed")
    planned = []
    for i, line in enumerate(raw):
        if not isinstance(line, dict):
            continue
        text = line.get("text") if line.get("text") not in (None, "") else line.get("line")
        text = "" if text is None else str(text)
        if not text.strip():
            continue
        item = {
            "id": _safe_id(line.get("id"), i + 1),
            "text": text,
            "duration_factor": duration_factor_for(line, default_speed),
            "lang": normalize_lang(line.get("lang"), normalize_lang(default_lang)),
            "seed": _seed(line, default_seed),
        }
        emo_ref = line.get("emo_ref")
        if emo_ref:
            if str(emo_ref) != Path(str(emo_ref)).name:
                raise SystemExit("unsafe emo_ref: %s" % emo_ref)
            item["emo_ref"] = str(emo_ref)
            alpha = _emo_alpha(line)
            item["emo_alpha"] = 1.0 if alpha is None else alpha
        emo_text = None if emo_ref else _emo_text(line)
        if emo_ref:
            pass
        elif emo_text:
            item["emo_text"] = emo_text
            alpha = _emo_alpha(line)
            item["emo_alpha"] = 0.65 if alpha is None else alpha
        else:
            emo = _emo_vector(line)
            if emo is not None:
                item["emo_vector"] = emo
        planned.append(item)
    if not planned:
        raise SystemExit("no flat text lines to synthesize")
    return planned


def _run(cmd, cwd=None, env=None, check=True):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    result = subprocess.run(cmd, cwd=cwd, env=env, text=True, encoding="utf-8", errors="replace")
    if check and result.returncode != 0:
        raise SystemExit("command failed (%s): %s" % (result.returncode, cmd[0]))
    return result


def _uv_bin():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "uv"])
    cand = Path(sys.executable).with_name("uv")
    if cand.is_file():
        return str(cand)
    found = shutil.which("uv")
    if found:
        return found
    raise SystemExit("uv installed but not on PATH")


def _checkout(dest):
    dest.mkdir(parents=True, exist_ok=True)
    if not (dest / ".git").is_dir():
        _run(["git", "init"], cwd=dest)
        _run(["git", "remote", "add", "origin", REPO_URL], cwd=dest)
    _run(["git", "fetch", "--depth", "1", "origin", CODE_REV], cwd=dest)
    _run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=dest)
    rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=dest, text=True).strip()
    if rev != CODE_REV:
        raise SystemExit("code rev %s != %s" % (rev, CODE_REV))
    return rev


def _uv(uv, repo, *args, env=None):
    cmd = [uv, "run", "--project", str(repo), "python", str(Path(__file__).resolve()), *args]
    merged = os.environ.copy()
    merged["CUDA_VISIBLE_DEVICES"] = "0"
    merged["PYTHONPATH"] = str(repo) + (os.pathsep + merged["PYTHONPATH"] if merged.get("PYTHONPATH") else "")
    if env:
        merged.update(env)
    result = subprocess.run(cmd, cwd=str(repo), env=merged, text=True, encoding="utf-8", errors="replace",
                            capture_output=True)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise SystemExit("uv run failed (%s)" % result.returncode)
    return result.stdout


def _last_json(text):
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise SystemExit("helper did not print JSON")


def _sync(uv, repo):
    _run([uv, "sync", "--project", str(repo), "--python", "3.11"])


def find_job_json(root):
    """Return job.json files under a Kaggle input root.

    Datasets now mount at /kaggle/input/datasets/<owner>/<slug>/job.json.
    A one-level glob only sees the datasets folder and misses the file.
    """
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("job.json") if path.is_file())


def _load_job():
    matches = find_job_json("/kaggle/input")
    if len(matches) != 1:
        raise SystemExit("job.json not found under /kaggle/input (%s hits)" % len(matches))
    folder = matches[0].parent
    job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    params = job.get("params") or {}
    if not isinstance(params, dict):
        raise SystemExit("job.json params must be an object")
    names = job.get("inputs") or []
    ref_name = params.get("ref") or next(n for n in names if str(n).lower().endswith(".wav"))
    script_name = params.get("script") or next(n for n in names if str(n).lower().endswith(".json"))
    ref = folder / ref_name
    script = folder / script_name
    if not ref.is_file():
        raise SystemExit("reference wav missing: %s" % ref)
    if not script.is_file():
        raise SystemExit("script missing: %s" % script)
    return job, params, ref, script


def _find_cfg(model_dir):
    for name in ("config.yaml", "config_v2_5.yaml"):
        path = model_dir / name
        if path.is_file():
            return path
    hits = sorted(model_dir.glob("*.yaml"))
    if len(hits) == 1:
        return hits[0]
    raise SystemExit("no config.yaml under %s" % model_dir)


def _wav_meta(path):
    try:
        import soundfile as sf
        info = sf.info(str(path))
        return int(info.samplerate), round(float(info.duration), 3)
    except Exception:
        import wave
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            frames = handle.getnframes()
        return int(rate), round(frames / float(rate), 3)


def probe_gpu():
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    import torch
    if not torch.cuda.is_available():
        print(json.dumps({"ok": False}))
        return
    major, minor = torch.cuda.get_device_capability(0)
    print(json.dumps({
        "ok": True,
        "major": int(major),
        "minor": int(minor),
        "name": torch.cuda.get_device_name(0),
    }))


def download_main(dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    errors = []

    def ensure(pkg):
        try:
            __import__(pkg)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

    def huggingface(endpoint):
        if endpoint:
            os.environ["HF_ENDPOINT"] = endpoint
        else:
            os.environ.pop("HF_ENDPOINT", None)
        ensure("huggingface_hub")
        from huggingface_hub import HfApi, snapshot_download
        revision = HfApi().model_info(MODEL_ID).sha
        snapshot_download(repo_id=MODEL_ID, local_dir=str(dest), revision=revision)
        return revision

    rev = None
    for endpoint in (None, "https://hf-mirror.com"):
        try:
            rev = huggingface(endpoint)
            break
        except Exception as exc:
            errors.append("huggingface endpoint=%s: %s" % (endpoint or "default", exc))
    if rev is None:
        try:
            ensure("modelscope")
            from modelscope.hub.snapshot_download import snapshot_download
            path = snapshot_download(MODEL_ID, local_dir=str(dest))
            rev = "modelscope:%s" % path
        except Exception as exc:
            errors.append("modelscope: %s" % exc)
    if rev is None:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit("IndexTTS-2.5 weight download failed")
    print(json.dumps({"model_rev": rev, "model": MODEL_ID}))


def infer_main(plan_path):
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    import torch
    from indextts.infer_v2_5 import IndexTTS2

    use_bf16 = bool(plan["use_bf16"])
    use_qwen_emo = any(line.get("emo_text") for line in plan["lines"])
    tts = IndexTTS2(
        cfg_path=plan["cfg"],
        model_dir=plan["model_dir"],
        use_bf16=use_bf16,
        use_cuda_kernel=False,
        use_deepspeed=False,
        use_accel=False,
        use_torch_compile=False,
        use_qwen_emo=use_qwen_emo,
    )
    out_dir = Path(plan["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for line in plan["lines"]:
        if line.get("seed") is not None:
            torch.manual_seed(int(line["seed"]))
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(int(line["seed"]))
        target = out_dir / ("%s.wav" % line["id"])
        kwargs = {
            "spk_audio_prompt": plan["ref"],
            "text": line["text"],
            "lang": line["lang"],
            "output_path": str(target),
            "duration_factor": float(line["duration_factor"]),
            "use_random": False,
            "text_normalization": True,
            "verbose": True,
        }
        if line.get("emo_audio"):
            kwargs["emo_audio_prompt"] = line["emo_audio"]
            kwargs["emo_alpha"] = float(line.get("emo_alpha", 1.0))
        elif line.get("emo_text"):
            kwargs["use_emo_text"] = True
            kwargs["emo_text"] = line["emo_text"]
            kwargs["emo_alpha"] = float(line.get("emo_alpha") if line.get("emo_alpha") is not None else 0.65)
        elif line.get("emo_vector") is not None:
            kwargs["emo_vector"] = line["emo_vector"]
        print(">> %s lang=%s duration_factor=%s emo=%s" % (
            line["id"], line["lang"], line["duration_factor"],
            "text" if line.get("emo_text") else ("vector" if line.get("emo_vector") else "ref")), flush=True)
        tts.infer(**kwargs)
        if not target.is_file():
            raise SystemExit("missing output for %s" % line["id"])
        rate, seconds = _wav_meta(target)
        written.append({
            "id": line["id"],
            "text": line["text"],
            "file": target.name,
            "seconds": seconds,
            "sample_rate": rate,
            "duration_factor": line["duration_factor"],
            "seed": line.get("seed"),
            "lang": line["lang"],
        })
    if not written:
        raise SystemExit("no wavs written")
    Path(plan["result_json"]).write_text(
        json.dumps({"lines": written}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({"wrote": len(written)}))


def main():
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    job, params, ref, script = _load_job()
    data = json.loads(script.read_text(encoding="utf-8"))
    lines = plan_lines(data, params)
    for line in lines:
        if line.get("emo_ref"):
            emo = ref.parent / line["emo_ref"]
            if not emo.is_file():
                raise SystemExit("emo_ref missing: %s" % emo)
            line["emo_audio"] = str(emo)
    print("lines", len(lines), flush=True)

    work = Path("/kaggle/working")
    repo = work / "index-tts"
    uv = _uv_bin()
    code_rev = _checkout(repo)
    _sync(uv, repo)

    gpu = _last_json(_uv(uv, repo, "--probe-gpu"))
    if not gpu.get("ok"):
        raise SystemExit("CUDA is not available in the IndexTTS environment")
    use_bf16 = use_bf16_for(int(gpu["major"]), params)
    dtype = "bf16" if use_bf16 else "fp32"
    print("device", gpu.get("name"), "cc", gpu.get("major"), gpu.get("minor"), "dtype", dtype, flush=True)

    model_dir = work / "checkpoints"
    downloaded = _last_json(_uv(uv, repo, "--download", str(model_dir)))
    cfg = _find_cfg(model_dir)
    out_dir = work / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    result_json = work / "tts25_lines.json"
    plan = {
        "cfg": str(cfg),
        "model_dir": str(model_dir),
        "use_bf16": use_bf16,
        "ref": str(ref),
        "out_dir": str(out_dir),
        "result_json": str(result_json),
        "lines": lines,
    }
    plan_path = work / "tts25_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    _uv(uv, repo, "--infer", str(plan_path))
    produced = json.loads(result_json.read_text(encoding="utf-8"))
    manifest = {
        "engine": "indextts25",
        "model": MODEL_ID,
        "code_rev": code_rev,
        "model_rev": downloaded.get("model_rev"),
        "dtype": dtype,
        "device": gpu.get("name"),
        "use_bf16": use_bf16,
        "sample_rate": SAMPLE_RATE,
        "lines": produced["lines"],
        "slug": job.get("slug"),
    }
    rates = {row["sample_rate"] for row in produced["lines"]}
    if rates != {SAMPLE_RATE}:
        manifest["sample_rate_measured"] = sorted(rates)
        print("warning: measured sample rate %s, expected %s" % (sorted(rates), SAMPLE_RATE), flush=True)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    print("wrote", out_dir / "manifest.json", flush=True)
    # keep Kaggle output small: only out/ should be pulled
    for junk in (model_dir, repo):
        shutil.rmtree(junk, ignore_errors=True)
    print("cleaned checkpoints/ and index-tts/", flush=True)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--probe-gpu":
        probe_gpu()
    elif len(sys.argv) >= 3 and sys.argv[1] == "--download":
        download_main(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "--infer":
        infer_main(sys.argv[2])
    else:
        main()
