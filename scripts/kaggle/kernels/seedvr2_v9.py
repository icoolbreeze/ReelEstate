#!/usr/bin/env python3
"""Project video super-resolution kernel (SeedVR2 V9).

1280x720 at 24fps only. Output is 1920x1080. Original audio and playback
speed are kept. Do not retune the measured settings.

Launch with scripts/kaggle/push_job.py --kernel seedvr2_v9. When
/kaggle/input/*/job.json exists, that file selects the one video and the
script writes /kaggle/working/out. Without job.json this file behaves as the
measured V9 script (auto-detect talkinghead.mp4, write
/kaggle/working/seedvr2_optimized).

Default: a 33-frame validation, then the entire source. preview mode
processes at most 120 frames after that gate.

Settings can be changed here or via environment variables:
  SEEDVR_INPUT_PATH=/kaggle/input/.../talkinghead.mp4  (auto-detect if absent)
  SEEDVR_RUN_MODE=full                              (full / preview)
  SEEDVR_VALIDATE_FRAMES=33                         (0 skips validation)
  SEEDVR_BATCH_TEMPORAL_OVERLAP=0
  SEEDVR_GPU_BOUNDARY_OVERLAP=3
  SEEDVR_GPU_DEVICES=0,1                            (auto if absent)

Only the batch overlap is passed to the upstream CLI. GPU splitting and join
blending belong to this wrapper. No upstream temporal-index patch is needed.
The only upstream modification is the previously validated T4 FP16 patch.
Short-test checks are artifact screens, not proof of perceptual video quality.
"""

import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from contextlib import ExitStack
from fractions import Fraction
from pathlib import Path


_ALLOWED_PARAMS = ("run_mode", "validate_frames")
_VIDEO_SUFFIXES = (".mp4", ".mov", ".mkv", ".webm")


def _reject_unknown_params(params):
    """Tuned V9 settings are not per-job knobs."""
    if not isinstance(params, dict):
        raise SystemExit("job.json params must be an object")
    unknown = sorted(key for key in params if key not in _ALLOWED_PARAMS)
    if unknown:
        raise SystemExit(
            "seedvr2_v9 does not accept params %s; only run_mode and validate_frames"
            % ", ".join(unknown))


def _env_from_params(params):
    """Return env updates for unset V9 knobs. Existing env vars win."""
    _reject_unknown_params(params)
    updates = {}
    if "run_mode" in params and "SEEDVR_RUN_MODE" not in os.environ:
        mode = str(params["run_mode"])
        if mode not in ("full", "preview"):
            raise SystemExit("run_mode must be full or preview")
        updates["SEEDVR_RUN_MODE"] = mode
    if "validate_frames" in params and "SEEDVR_VALIDATE_FRAMES" not in os.environ:
        raw = params["validate_frames"]
        try:
            count = int(str(raw).strip())
        except (TypeError, ValueError):
            raise SystemExit("validate_frames must be an integer >= 0")
        if count < 0 or str(raw).strip() != str(count):
            raise SystemExit("validate_frames must be an integer >= 0")
        updates["SEEDVR_VALIDATE_FRAMES"] = str(count)
    return updates


def _apply_kaggle_job(input_root=None):
    """Map push_job's job.json onto V9 env before the constants below are read."""
    root = Path(input_root) if input_root is not None else Path("/kaggle/input")
    if not root.is_dir():
        return
    matches = sorted(root.glob("*/job.json"))
    if not matches:
        return
    if len(matches) != 1:
        raise SystemExit("expected exactly one job.json under %s" % root)
    job_path = matches[0]
    job = json.loads(job_path.read_text(encoding="utf-8"))
    if not isinstance(job, dict):
        raise SystemExit("job.json must be an object")
    names = job.get("inputs") or []
    if not isinstance(names, list):
        raise SystemExit("job.json inputs must be a list")
    videos = [name for name in names
              if str(name).lower().endswith(_VIDEO_SUFFIXES)]
    if len(videos) != 1:
        raise SystemExit(
            "seedvr2_v9 requires exactly one video input, got %s" % (videos,))
    video = job_path.parent / str(videos[0])
    if not video.is_file():
        raise SystemExit("video input missing: %s" % video)
    os.environ.setdefault("SEEDVR_INPUT_PATH", str(video))
    os.environ.setdefault("SEEDVR_OUTPUT_DIR", "/kaggle/working/out")
    for key, value in _env_from_params(job.get("params") or {}).items():
        os.environ[key] = value


_apply_kaggle_job()

REPO_URL = "https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler.git"
PINNED_TAG = "v2.5.23"
PINNED_COMMIT = "5a4bf428f3735cc72ac760d40f372f94dec28422"
SEEDVR_DIR = Path(os.environ.get("SEEDVR_REPO_DIR", "/tmp/seedvr2"))
MODEL_DIR = Path(os.environ.get("SEEDVR_MODEL_DIR", "/tmp/seedvr2-models"))
OUT_DIR = Path(os.environ.get("SEEDVR_OUTPUT_DIR", "/kaggle/working/seedvr2_optimized"))
RUN_MODE = os.environ.get("SEEDVR_RUN_MODE", "full")
VALIDATE_FRAMES = int(os.environ.get("SEEDVR_VALIDATE_FRAMES", "33"))
PREVIEW_FRAMES = 120
CLIP_FPS = 24
SRC_W, SRC_H = 1280, 720
TARGET_W, TARGET_H = 1920, 1080
DIT_MODEL = "seedvr2_ema_3b_fp16.safetensors"
VAE_MODEL = "ema_vae_fp16.safetensors"
BATCH_TEMPORAL_OVERLAP = int(os.environ.get("SEEDVR_BATCH_TEMPORAL_OVERLAP", "0"))
GPU_BOUNDARY_OVERLAP = int(os.environ.get("SEEDVR_GPU_BOUNDARY_OVERLAP", "3"))
TUNED_CFG = {
    "batch_size": 9, "blocks": 24,
    "encode_tile": 256, "decode_tile": 256, "spatial_overlap": 32,
    "batch_temporal_overlap": BATCH_TEMPORAL_OVERLAP,
    "gpu_boundary_overlap": GPU_BOUNDARY_OVERLAP,
}
EXTRA_PACKAGES = [
    ("safetensors", "safetensors"), ("einops", "einops"),
    ("omegaconf", "omegaconf"), ("diffusers", "diffusers"),
    ("peft", "peft"), ("rotary_embedding_torch", "rotary_embedding_torch"),
    ("gguf", "gguf"), ("psutil", "psutil"),
    ("matplotlib", "matplotlib"), ("huggingface_hub", "huggingface_hub"),
    ("numpy", "numpy"),
]
OLD_DUAL_120_SECONDS = 922.227
OOM_PATTERN = re.compile(r"out of memory|cuda oom", re.I)


def run_command(argv, **kwargs):
    result = subprocess.run([str(a) for a in argv], capture_output=True,
                            text=True, **kwargs)
    if result.returncode:
        raise RuntimeError("command failed (%s): %s\n%s" % (
            result.returncode, argv[0], result.stderr[-3000:]))
    return result


def probe_summary(path):
    data = json.loads(run_command([
        "ffprobe", "-v", "error", "-show_streams", "-show_format",
        "-of", "json", path]).stdout)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise RuntimeError("No video stream: %s" % path)
    audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), {})
    rate = video.get("avg_frame_rate", "0/0")
    if rate in ("0/0", "0"):
        rate = video.get("r_frame_rate", "0/0")
    fps = float(Fraction(rate))
    frames = video.get("nb_frames")
    if not str(frames).isdigit():
        counted = json.loads(run_command([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-count_frames", "-show_entries", "stream=nb_read_frames",
            "-of", "json", path]).stdout)
        frames = counted["streams"][0].get("nb_read_frames")
    if not str(frames).isdigit():
        raise RuntimeError("Could not count frames: %s" % path)
    duration = float(video.get("duration") or data.get("format", {}).get("duration")
                     or int(frames) / fps)
    return {"width": int(video["width"]), "height": int(video["height"]),
            "fps": rate, "fps_value": fps, "frames": int(frames),
            "duration": duration, "audio_codec": audio.get("codec_name")}


def validate_video(path, count, width=TARGET_W, height=TARGET_H):
    info = probe_summary(path)
    if (info["width"], info["height"], info["frames"]) != (width, height, count):
        raise RuntimeError("Unexpected dimensions/frame count: %s" % info)
    if abs(info["fps_value"] - CLIP_FPS) > 1e-6:
        raise RuntimeError("Unexpected frame rate: %s" % info)
    if abs(info["duration"] - count / CLIP_FPS) > 1 / CLIP_FPS + 0.001:
        raise RuntimeError("Unexpected video duration: %s" % info)
    return info


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_report(report):
    target = OUT_DIR / "report.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(target)


def discover_gpus():
    # The parent never creates a CUDA context: leave VRAM for the workers.
    rows = csv.reader(run_command([
        "nvidia-smi", "--query-gpu=index,uuid,name,memory.total",
        "--format=csv,noheader,nounits"]).stdout.splitlines())
    gpus = [{"index": r[0].strip(), "uuid": r[1].strip(),
             "name": r[2].strip(), "total_memory_mib": float(r[3])} for r in rows]
    visible = os.environ.get("CUDA_VISIBLE_DEVICES")
    permitted = visible.split(",") if visible is not None else None
    if permitted is not None:
        permitted = [p.strip() for p in permitted if p.strip()]
        gpus = [g for g in gpus if g["index"] in permitted or g["uuid"] in permitted]
    requested = os.environ.get("SEEDVR_GPU_DEVICES")
    if requested:
        identifiers = [x.strip() for x in requested.split(",")]
        chosen = []
        for identifier in identifiers:
            matches = [g for g in gpus if identifier in (g["index"], g["uuid"])]
            if len(matches) != 1:
                raise RuntimeError("Unavailable GPU: %s" % identifier)
            chosen.append(matches[0])
        gpus = chosen
    else:
        gpus = gpus[:2]
    if not 1 <= len(gpus) <= 2 or len({g["uuid"] for g in gpus}) != len(gpus):
        raise RuntimeError("Select one or two distinct available GPUs")
    return gpus


def patch_t4_float16():
    path = SEEDVR_DIR / "src" / "optimization" / "compatibility.py"
    text = path.read_text(encoding="utf-8")
    needle = ("def _probe_bfloat16_support() -> bool:\n"
              "    if not torch.cuda.is_available():\n"
              "        return True\n")
    if "compute capability 7.5" in text:
        return
    if needle not in text:
        raise RuntimeError("Pinned bfloat16 probe changed; refusing an unsafe patch")
    insert = needle + (
        "    major, minor = torch.cuda.get_device_capability(0)\n"
        "    # Tesla T4 is compute capability 7.5; prefer native FP16.\n"
        "    if (major, minor) == (7, 5):\n"
        "        return False\n")
    path.write_text(text.replace(needle, insert, 1), encoding="utf-8")


def clone_seedvr2(report):
    if not SEEDVR_DIR.exists():
        run_command(["git", "clone", "--depth", "1", "--branch", PINNED_TAG,
                     REPO_URL, SEEDVR_DIR])
    head = run_command(["git", "-C", SEEDVR_DIR, "rev-parse", "HEAD"]).stdout.strip()
    report["pinned"]["checked_head"] = head
    if head != PINNED_COMMIT:
        raise RuntimeError("Existing checkout is not the pinned commit: %s" % head)
    patch_t4_float16()


def install_seedvr_requirements():
    missing = [package for module, package in EXTRA_PACKAGES
               if importlib.util.find_spec(module) is None]
    if importlib.util.find_spec("cv2") is None:
        missing.append("opencv-python-headless")
    if not missing:
        print("Dependencies already present; keeping installed versions", flush=True)
        return
    # Protect Kaggle's torch/CUDA stack and NumPy from transitive pip upgrades.
    constraints = []
    for package in ("torch", "torchvision", "torchaudio", "numpy"):
        try:
            constraints.append("%s==%s" % (package, importlib.metadata.version(package)))
        except importlib.metadata.PackageNotFoundError:
            pass
    with tempfile.TemporaryDirectory(prefix="seedvr-pip-") as directory:
        constraint_file = Path(directory) / "constraints.txt"
        constraint_file.write_text("\n".join(constraints) + "\n", encoding="utf-8")
        # Only missing packages: no complete requirements reinstall or flash-attn.
        run_command([sys.executable, "-m", "pip", "install", "-q", "-c",
                     constraint_file, *missing])
    importlib.invalidate_caches()


def prefetch_weights(report):
    # Download once, serially, before launching two workers against the same
    # model directory. Use repo names and hashes from the pinned registry.
    code = r'''
import hashlib, json, sys
from pathlib import Path
from huggingface_hub import hf_hub_download
from src.utils.model_registry import MODEL_REGISTRY
root = Path(sys.argv[1]); root.mkdir(parents=True, exist_ok=True)
results = []
for name in sys.argv[2:]:
    entry = MODEL_REGISTRY[name]
    target = root / name
    reused = target.is_file()
    if not reused:
        target = Path(hf_hub_download(repo_id=entry.repo, filename=name, local_dir=str(root)))
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if entry.sha256 and actual != entry.sha256:
        raise RuntimeError("Weight hash mismatch: " + name)
    results.append({"name": name, "sha256": actual, "reused": reused,
                    "size_bytes": target.stat().st_size})
print("WEIGHTS_JSON=" + json.dumps(results))
'''
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = ""  # Downloader needs no CUDA context.
    env["PYTHONPATH"] = str(SEEDVR_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    result = run_command([sys.executable, "-c", code, MODEL_DIR, DIT_MODEL, VAE_MODEL],
                         cwd=SEEDVR_DIR, env=env)
    (OUT_DIR / "weights.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    record = next((line[13:] for line in result.stdout.splitlines()
                   if line.startswith("WEIGHTS_JSON=")), None)
    if record is None:
        raise RuntimeError("Weight prefetch did not return metadata")
    report["weights"] = json.loads(record)


class GpuSampler:
    def __init__(self, path):
        self.path = Path(path)
        self.samples = []
        self.error = None
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self.thread.start()

    def _loop(self):
        while not self.stop.is_set():
            try:
                output = run_command([
                    "nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used,power.draw",
                    "--format=csv,noheader,nounits"], timeout=5).stdout
                for row in csv.reader(output.splitlines()):
                    self.samples.append([time.time(), *[v.strip() for v in row]])
            except Exception as exc:
                self.error = str(exc)
            self.stop.wait(2)

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=6)
        with self.path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["unix_time", "index", "utilization_gpu",
                             "memory_used_mib", "power_w"])
            writer.writerows(list(self.samples))

    def per_gpu(self):
        buckets = {}
        for row in list(self.samples):
            if len(row) < 5:
                continue
            bucket = buckets.setdefault(row[1], {"memory": [], "util": []})
            for key, value in (("memory", row[3]), ("util", row[2])):
                try:
                    bucket[key].append(float(value))
                except ValueError:
                    pass
        return {index: {
            "samples": len(values["memory"]),
            "peak_mem_mib": max(values["memory"]) if values["memory"] else None,
            "avg_util": sum(values["util"]) / len(values["util"]) if values["util"] else None,
        } for index, values in buckets.items()}


def make_segments(count, gpus, boundary_overlap):
    if count <= 0 or boundary_overlap < 0:
        raise ValueError("Invalid frame count / boundary overlap")
    if len(gpus) == 1 or count < 2:
        return [{"gpu": gpus[0], "start": 0, "end": count}], 0
    split = count // 2
    overlap = min(boundary_overlap, count - split)
    return [
        {"gpu": gpus[0], "start": 0, "end": split + overlap},
        {"gpu": gpus[1], "start": split, "end": count},
    ], overlap


def cut_segment(source, target, start, end):
    # Frame-index trim + lossless encode: no fps filter, extra lossy input
    # compression, timestamp seek rounding, or frame interpolation.
    run_command([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-filter_threads", "2",
        "-threads", "2", "-i", source, "-map", "0:v:0", "-an", "-sn", "-dn",
        "-vf", "trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS" % (start, end),
        "-fps_mode", "passthrough", "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", "0", "-threads", "2", "-pix_fmt", "yuv420p", target])
    validate_video(target, end - start, SRC_W, SRC_H)


def seedvr_cli_argv(input_path, output_path, cfg):
    # IMPORTANT: omit --cuda_device. This CLI rewrites CUDA_VISIBLE_DEVICES
    # when that option is passed, so '--cuda_device 0' could move GPU1 to GPU0.
    # Each process sees exactly one physical GPU through its environment.
    return [
        sys.executable, "-u", "-X", "faulthandler", str(SEEDVR_DIR / "inference_cli.py"),
        str(input_path), "--output", str(output_path),
        "--output_format", "mp4", "--video_backend", "ffmpeg",
        "--model_dir", str(MODEL_DIR), "--dit_model", DIT_MODEL,
        "--resolution", "1080", "--max_resolution", "1920",
        "--batch_size", str(cfg["batch_size"]), "--seed", "42",
        "--temporal_overlap", str(cfg["batch_temporal_overlap"]),
        "--dit_offload_device", "cpu", "--vae_offload_device", "cpu",
        "--blocks_to_swap", str(cfg["blocks"]),
        "--vae_encode_tiled", "--vae_encode_tile_size", str(cfg["encode_tile"]),
        "--vae_encode_tile_overlap", str(cfg["spatial_overlap"]),
        "--vae_decode_tiled", "--vae_decode_tile_size", str(cfg["decode_tile"]),
        "--vae_decode_tile_overlap", str(cfg["spatial_overlap"]),
        "--attention_mode", "sdpa", "--debug",
    ]


def worker_environment(gpu):
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = gpu["uuid"]
    env["PYTHONPATH"] = str(SEEDVR_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONFAULTHANDLER"] = "1"
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    env.setdefault("OMP_NUM_THREADS", "2")
    env.setdefault("MKL_NUM_THREADS", "2")
    return env


def parse_worker_log(text):
    phases = {}
    for number, seconds in re.findall(r"Phase (\d+):.*?complete: ([0-9.]+)s", text):
        phases.setdefault("phase_" + number, []).append(float(seconds))
    counts = {"output_frames": None, "computed_frames": None,
              "padding_frames": None, "removed_internal_overlap_frames": None}
    assembly = re.search(r"Output assembled:\s*(\d+) frames(?:\s*\(([^)]*)\))?", text)
    if assembly:
        counts["output_frames"] = int(assembly[1])
        body = assembly[2] or ""
        for key, pattern in (
            ("computed_frames", r"(\d+) computed"),
            ("padding_frames", r"(\d+) padding"),
            ("removed_internal_overlap_frames", r"(\d+) overlap removed"),
        ):
            match = re.search(pattern, body)
            if match:
                counts[key] = int(match[1])
    return {
        "phases_s": {key: sum(values) for key, values in phases.items()},
        "phase_occurrences": {key: len(values) for key, values in phases.items()},
        "float16_confirmed": ("Unified compute dtype: torch.float16" in text
                              and "Unified compute dtype: torch.bfloat16" not in text
                              and ("VAE=torch.float16" in text or "to torch.float16" in text)),
        "oom": bool(OOM_PATTERN.search(text)),
        "nonfinite_in_log": bool(re.search(
            r"non-finite|\b(?:found|detected|contains?)\b[^\n]*\b(?:nan|infinity)\b", text, re.I)),
        "frame_accounting": counts,
    }


def stop_process(process, whole_group=False):
    if whole_group:
        # The CLI can spawn its own CUDA children. Stopping only its parent
        # would leave GPU inference running after a sibling fails.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def launch_workers(segments, cfg, stage_dir, stage_entry):
    running = []
    sampler = GpuSampler(stage_dir / "gpu.csv")
    sampler.start()
    inference_started = time.perf_counter()
    failed = False
    try:
        for index, segment in enumerate(segments):
            logfile = stage_dir / ("gpu%s.log" % segment["gpu"]["index"])
            output = stage_dir / ("worker%d.mp4" % index)
            output.unlink(missing_ok=True)
            argv = seedvr_cli_argv(segment["input"], output, cfg)
            worker = {"gpu_index": segment["gpu"]["index"],
                      "gpu_uuid": segment["gpu"]["uuid"],
                      "local_cuda_device": "cuda:0",
                      "start_frame": segment["start"], "end_frame_exclusive": segment["end"],
                      "input_frames": segment["end"] - segment["start"],
                      "output": str(output), "log": str(logfile), "argv": argv}
            stage_entry["workers"].append(worker)
            segment["output"] = output
            handle = logfile.open("wb")
            started = time.perf_counter()
            try:
                process = subprocess.Popen(argv, cwd=SEEDVR_DIR,
                    env=worker_environment(segment["gpu"]), stdout=handle,
                    stderr=subprocess.STDOUT, start_new_session=True)
            except BaseException:
                handle.close()
                raise
            running.append((process, handle, started, worker))
        last_update = 0.0
        while any(process.poll() is None for process, *_ in running):
            now = time.perf_counter()
            for process, handle, started, worker in running:
                code = process.poll()
                if code is not None and "returncode" not in worker:
                    worker["returncode"] = code
                    worker["wall_clock_seconds"] = round(now - started, 3)
                    if code:
                        failed = True
            if failed:
                raise RuntimeError("A SeedVR worker failed; sibling worker stopped")
            if now - last_update >= 30:
                active = [w["gpu_index"] for p, _, _, w in running if p.poll() is None]
                print("[%s] running GPUs %s; elapsed %.1f min" % (
                    stage_entry["name"], ",".join(active), (now - inference_started) / 60),
                    flush=True)
                last_update = now
            time.sleep(0.25)
    finally:
        for process, handle, started, worker in running:
            stop_process(process, whole_group=True)
            handle.close()
            worker.setdefault("returncode", process.returncode)
            worker.setdefault("wall_clock_seconds", round(time.perf_counter() - started, 3))
            worker.update(parse_worker_log(Path(worker["log"]).read_text(
                encoding="utf-8", errors="replace")))
        sampler.finish()
        stage_entry["inference_wall_clock_seconds"] = round(
            time.perf_counter() - inference_started, 3)
        stage_entry["nvidia_smi_per_gpu"] = sampler.per_gpu()
        stage_entry["gpu_sampling_error"] = sampler.error
    for worker in stage_entry["workers"]:
        if worker["returncode"] or worker["oom"] or worker["nonfinite_in_log"]:
            raise RuntimeError("Invalid inference; inspect %s" % worker["log"])
        if not worker["float16_confirmed"]:
            raise RuntimeError("FP16 was not confirmed; inspect %s" % worker["log"])
        worker["probe"] = validate_video(worker["output"], worker["input_frames"])
    # These phase totals belong to separate workers. Do not pretend their
    # sum or per-phase maximum represents a synchronized global timeline.
    values = [w["frame_accounting"]["computed_frames"] for w in stage_entry["workers"]]
    stage_entry["actual_computed_frames"] = (
        sum(values) if all(value is not None for value in values) else None)


def read_exact(stream, size):
    pieces = bytearray()
    while len(pieces) < size:
        part = stream.read(size - len(pieces))
        if not part:
            break
        pieces.extend(part)
    if not pieces:
        return None
    if len(pieces) != size:
        raise RuntimeError("Truncated decoded video frame")
    return bytes(pieces)


def write_all(stream, data):
    view = memoryview(data)
    while view:
        written = stream.write(view)
        if not written:
            raise RuntimeError("Encoder pipe stopped accepting frames")
        view = view[written:]


def decoder_argv(path, scale=None):
    argv = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-filter_threads", "2",
            "-threads", "2", "-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn"]
    if scale:
        argv += ["-vf", "scale=%d:%d" % scale]
    return argv + ["-fps_mode", "passthrough", "-threads", "2",
                   "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]


def merge_segments(segments, count, overlap, output, width=TARGET_W, height=TARGET_H):
    if len(segments) == 1:
        shutil.copyfile(segments[0]["output"], output)
        return
    import numpy as np
    split = segments[1]["start"]
    size = width * height * 3
    processes = []
    with ExitStack() as stack:
        error_logs = [stack.enter_context(tempfile.TemporaryFile()) for _ in range(3)]
        try:
            for index, segment in enumerate(segments):
                processes.append(subprocess.Popen(decoder_argv(segment["output"]),
                    stdout=subprocess.PIPE, stderr=error_logs[index]))
            left, right = processes
            encoder = subprocess.Popen([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-filter_threads", "2",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s:v", "%dx%d" % (width, height),
                "-r", str(CLIP_FPS), "-i", "pipe:0", "-an", "-c:v", "libx264",
                "-preset", "fast", "-crf", "18", "-threads", "2", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(output)],
                stdin=subprocess.PIPE, stderr=error_logs[2], stdout=subprocess.DEVNULL)
            processes.append(encoder)

            def take(process):
                data = read_exact(process.stdout, size)
                if data is None:
                    raise RuntimeError("Worker ended before its expected frame count")
                return data

            for _ in range(split):
                write_all(encoder.stdin, take(left))
            # Cosine crossfade, aligned by the SAME original frame index.
            for index in range(overlap):
                a = np.frombuffer(take(left), np.uint8).astype(np.float32)
                b = np.frombuffer(take(right), np.uint8).astype(np.float32)
                weight = (0.5 if overlap == 1 else
                          0.5 - 0.5 * math.cos(math.pi * index / (overlap - 1)))
                mixed = np.rint(a * (1 - weight) + b * weight).clip(0, 255).astype(np.uint8)
                write_all(encoder.stdin, mixed.tobytes())
            for _ in range(count - split - overlap):
                write_all(encoder.stdin, take(right))
            if left.stdout.read(1) or right.stdout.read(1):
                raise RuntimeError("Worker produced extra frames")
            left.stdout.close()
            right.stdout.close()
            encoder.stdin.close()
            for process in processes:
                if process.wait(timeout=60):
                    raise RuntimeError("FFmpeg splice process failed")
        except BaseException as exc:
            details = []
            for process in processes:
                stop_process(process)
            for handle in error_logs:
                handle.seek(0)
                details.append(handle.read().decode("utf-8", errors="replace")[-1500:])
            if isinstance(exc, Exception):
                raise RuntimeError("Video splice failed: %s\n%s" % (exc, "\n".join(details))) from exc
            raise
        finally:
            for process in processes:
                stop_process(process)
                for stream in (process.stdin, process.stdout):
                    if stream and not stream.closed:
                        stream.close()


def inspect_video(path, boundaries):
    """Stream small frames; screen pops/black frames, not perceived flicker."""
    import numpy as np
    width, height = 256, 144
    info = probe_summary(path)
    process = subprocess.Popen(decoder_argv(path, (width, height)),
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    previous = None
    global_diffs, face_diffs, means = [], [], []
    frame_count = 0
    try:
        while True:
            data = read_exact(process.stdout, width * height * 3)
            if data is None:
                break
            frame = np.frombuffer(data, np.uint8).reshape(height, width, 3).astype(np.int16)
            means.append(float(frame.mean()))
            if previous is not None:
                difference = np.abs(frame - previous)
                global_diffs.append(float(difference.mean()))
                # Fixed central ROI for this centered talking-head source;
                # not a face detector or a general lipsync measurement.
                face_diffs.append(float(difference[20:100, 80:176].mean()))
            previous = frame
            frame_count += 1
        process.stdout.close()
        if process.wait(timeout=30):
            raise RuntimeError("Video quality decoder failed")
    finally:
        stop_process(process)
        if process.stdout and not process.stdout.closed:
            process.stdout.close()
    med_global = float(np.median(global_diffs)) if global_diffs else 0.0
    med_face = float(np.median(face_diffs)) if face_diffs else 0.0
    checks = {}
    for boundary in sorted(set(boundaries)):
        # Check before, within and after each blend, not just its first frame.
        if 1 <= boundary < frame_count:
            dg, df = global_diffs[boundary - 1], face_diffs[boundary - 1]
            checks[str(boundary)] = {
                "global_diff": round(dg, 4), "center_roi_diff": round(df, 4),
                "global_ratio": round(dg / max(med_global, 0.5), 3),
                "center_roi_ratio": round(df / max(med_face, 0.5), 3),
            }
    suspect = [key for key, value in checks.items()
               if value["global_ratio"] >= 4 or value["center_roi_ratio"] >= 4]
    black = [i for i, value in enumerate(means) if value < 8]
    blown = [i for i, value in enumerate(means) if value > 247]
    return {"ok": frame_count == info["frames"] and not black and not blown and not suspect,
            "decoded_frames": frame_count, "black_frames": black, "blown_out_frames": blown,
            "suspect_boundaries": suspect, "boundary_checks": checks,
            "median_global_diff": med_global, "median_center_roi_diff": med_face,
            "note": "Heuristic artifact screen; motion can trigger it; passing does not prove no flicker."}


def mux_original_audio(silent, source, final, count, codec):
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
               "-i", str(silent), "-i", str(source), "-map", "0:v:0", "-map", "1:a:0?",
               "-c:v", "copy"]
    command += ["-c:a", "copy"] if codec == "aac" else ["-c:a", "aac", "-b:a", "192k"]
    run_command(command + ["-t", "%.9f" % (count / CLIP_FPS), "-map_metadata", "-1",
                           "-movflags", "+faststart", str(final)])


def stage_boundaries(segments, count, cfg, overlap):
    points = set()
    stride = cfg["batch_size"] - cfg["batch_temporal_overlap"]
    for segment in segments:
        for local in range(stride, segment["end"] - segment["start"], stride):
            edge = segment["start"] + local
            points.update(range(edge - 1, edge + cfg["batch_temporal_overlap"] + 2))
    if len(segments) == 2:
        split = segments[1]["start"]
        points.update(range(split - 1, split + overlap + 2))
    return [point for point in sorted(points) if 1 <= point < count]


def run_stage(name, source, count, gpus, cfg, root, report):
    stage_dir = OUT_DIR / name
    stage_dir.mkdir(parents=True, exist_ok=True)
    entry = {"name": name, "config": dict(cfg), "requested_frames": count,
             "workers": [], "succeeded": False}
    report["seedvr2"]["stages"].append(entry)
    started = time.perf_counter()
    try:
        segments, overlap = make_segments(count, gpus, cfg["gpu_boundary_overlap"])
        for index, segment in enumerate(segments):
            clip = root / ("%s_worker%d.mp4" % (name, index))
            cut_segment(source, clip, segment["start"], segment["end"])
            segment["input"] = clip
        entry["unique_input_frames"] = count
        entry["total_worker_input_frames"] = sum(s["end"] - s["start"] for s in segments)
        entry["gpu_boundary_overlap_frames"] = overlap
        launch_workers(segments, cfg, stage_dir, entry)
        silent = stage_dir / "merged.silent.mp4"
        merge_segments(segments, count, overlap, silent)
        validate_video(silent, count)
        entry["quality_screen"] = inspect_video(silent, stage_boundaries(segments, count, cfg, overlap))
        if not entry["quality_screen"]["ok"]:
            raise RuntimeError("Artifact screen flagged output; inspect stage video and report")
        output = stage_dir / (name + ".mp4")
        codec = report["source"]["audio_codec"]
        mux_original_audio(silent, source, output, count, codec)
        entry["probe"] = validate_video(output, count)
        if codec and not entry["probe"]["audio_codec"]:
            raise RuntimeError("Source audio was lost")
        entry["output"] = str(output)
        entry["succeeded"] = True
        silent.unlink(missing_ok=True)
    except Exception:
        entry["error"] = traceback.format_exc()
        raise
    finally:
        entry["wall_clock_seconds"] = round(time.perf_counter() - started, 3)
        atomic_report(report)
    return entry


def resolve_source():
    explicit = os.environ.get("SEEDVR_INPUT_PATH") or os.environ.get("SEEDVR_SOURCE_VIDEO")
    if explicit:
        source = Path(explicit)
        if not source.is_file():
            raise FileNotFoundError(source)
        return source
    candidates = sorted(Path("/kaggle/input").rglob("*.mp4"))
    named = [p for p in candidates if p.name == "talkinghead.mp4"]
    if len(named) == 1:
        return named[0]
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError("Set SEEDVR_INPUT_PATH; MP4 candidates: %s" % candidates)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {"pinned": {"repo": REPO_URL, "tag": PINNED_TAG, "commit": PINNED_COMMIT},
              "seedvr2": {"succeeded": False, "stages": []},
              "realesrgan": {"skipped": True, "note": "No new comparison pass requested"},
              "errors": []}
    total_started = time.perf_counter()
    try:
        if RUN_MODE not in ("full", "preview"):
            raise ValueError("SEEDVR_RUN_MODE must be full or preview")
        if VALIDATE_FRAMES < 0 or not 0 <= BATCH_TEMPORAL_OVERLAP < TUNED_CFG["batch_size"]:
            raise ValueError("Invalid validation frame count / batch overlap")
        source = resolve_source()
        info = probe_summary(source)
        report["source"] = dict(info, path=str(source))
        if (info["width"], info["height"]) != (SRC_W, SRC_H):
            raise RuntimeError("This tuned script expects a 1280x720 source")
        if abs(info["fps_value"] - CLIP_FPS) > 1e-6:
            raise RuntimeError("This script expects 24fps; it will not resample another frame rate")
        count = info["frames"] if RUN_MODE == "full" else min(PREVIEW_FRAMES, info["frames"])
        gpus = discover_gpus()
        report["gpus"] = gpus
        clone_seedvr2(report)
        install_seedvr_requirements()
        prefetch_weights(report)
        atomic_report(report)
        with tempfile.TemporaryDirectory(prefix="seedvr-run-") as directory:
            root = Path(directory)
            if VALIDATE_FRAMES and VALIDATE_FRAMES < count:
                run_stage("validate%d" % VALIDATE_FRAMES, source, VALIDATE_FRAMES,
                          gpus, TUNED_CFG, root, report)
            # One final job: no full 5-second benchmark followed by an 8-second rerun.
            winner = run_stage("%s%d" % (RUN_MODE, count), source, count,
                               gpus, TUNED_CFG, root, report)
        final = OUT_DIR / "seedvr2_1080p.mp4"
        temporary_final = OUT_DIR / "seedvr2_1080p.publish.mp4"
        shutil.copyfile(winner["output"], temporary_final)
        winner_hash = sha256(winner["output"])
        final_hash = sha256(temporary_final)
        if winner_hash != final_hash:
            raise RuntimeError("Published file differs from selected output")
        final_probe = validate_video(temporary_final, count)
        temporary_final.replace(final)
        report["seedvr2"].update({
            "succeeded": True, "final": str(final), "final_probe": final_probe,
            "chosen": winner["config"], "winner_publish": {
                "winner_stage": winner["name"], "sha256_winner": winner_hash,
                "sha256_final": final_hash, "hashes_match": True}})
        # Compare actual equal-length inference times only. The short validation
        # and weight downloads are separate from this measurement.
        if count == 120 and len(gpus) == 2:
            new = winner["inference_wall_clock_seconds"]
            report["comparison"] = {
                "old_dual_120_inference_seconds": OLD_DUAL_120_SECONDS,
                "new_120_inference_seconds": new,
                "speedup": OLD_DUAL_120_SECONDS / new,
                "note": "Both include CLI loading; input preparation, merging and validation excluded."}
        print("Finished: %s" % final, flush=True)
    except Exception:
        error = traceback.format_exc()
        report["errors"].append(error)
        report["seedvr2"]["error"] = error
        print(error, file=sys.stderr, flush=True)
    finally:
        report["total_wall_clock_seconds"] = round(time.perf_counter() - total_started, 3)
        atomic_report(report)
    # A stale file from a previous run is never evidence of current success.
    return 0 if report["seedvr2"]["succeeded"] else 1


if __name__ == "__main__":
    sys.exit(main())
