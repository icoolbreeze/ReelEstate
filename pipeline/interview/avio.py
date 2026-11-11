"""ffmpeg / ffprobe helpers for the interview pipeline.

Everything here is read-only with respect to source media: probes and decodes
never modify inputs. numpy is required (already a production dependency for the
matting venv and the ASR step); no third-party media bindings are used.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


class AVError(RuntimeError):
    pass


def require_tools():
    missing = [name for name, path in (("ffmpeg", FFMPEG), ("ffprobe", FFPROBE)) if not path]
    if missing:
        raise AVError("缺少可执行文件：%s" % "、".join(missing))


def run(cmd, *, capture=True, text=True):
    proc = subprocess.run([str(part) for part in cmd], capture_output=capture, text=text,
                          encoding="utf-8" if text else None, errors="replace" if text else None)
    if proc.returncode != 0:
        detail = ((proc.stderr or proc.stdout or "") if text else "") or "command failed"
        raise AVError("命令失败 exit=%s: %s\n%s" % (proc.returncode, " ".join(str(c) for c in cmd), detail[-1200:]))
    return proc


def sha256_file(path, chunk=1 << 20):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def _fps(rate):
    try:
        num, den = str(rate or "0/1").split("/")
        value = float(Fraction(int(num), int(den)))
    except (ValueError, ZeroDivisionError):
        return None
    return round(value, 3)


def ffprobe_json(path):
    require_tools()
    proc = run([FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise AVError("ffprobe 输出无法解析：%s" % path) from exc


def probe(path):
    """Return normalized media info, or {"valid": False, "error": ...}. Never raises on bad media."""
    path = Path(path)
    row = {"valid": False, "video": None, "audios": [], "duration_ms": None, "size": None}
    if not path.is_file():
        row["error"] = "文件不存在"
        return row
    row["size"] = path.stat().st_size
    if row["size"] == 0:
        row["error"] = "空文件"
        return row
    try:
        data = ffprobe_json(path)
    except AVError as exc:
        row["error"] = str(exc)[:400]
        return row
    streams = data.get("streams") or []
    duration = (data.get("format") or {}).get("duration")
    if duration is not None:
        try:
            row["duration_ms"] = int(round(float(duration) * 1000))
        except ValueError:
            pass
    for stream in streams:
        kind = stream.get("codec_type")
        if kind == "video" and row["video"] is None:
            fps = _fps(stream.get("r_frame_rate"))
            row["video"] = {
                "codec": stream.get("codec_name"),
                "width": stream.get("width"),
                "height": stream.get("height"),
                "fps": fps,
                "pix_fmt": stream.get("pix_fmt"),
                "has_alpha": str(stream.get("pix_fmt") or "").startswith("yuva"),
                "nb_frames": int(stream["nb_frames"]) if str(stream.get("nb_frames") or "").isdigit() else None,
            }
        elif kind == "audio":
            row["audios"].append({
                "codec": stream.get("codec_name"),
                "sample_rate": int(stream["sample_rate"]) if str(stream.get("sample_rate") or "").isdigit() else None,
                "channels": stream.get("channels"),
                "duration_ms": int(round(float(stream["duration"]) * 1000)) if stream.get("duration") else row["duration_ms"],
            })
    video = row["video"] or {}
    if not row["audios"] and not (video.get("width") and video.get("height") and video.get("fps")):
        row["error"] = "没有可解码的视频流或分辨率/帧率无效"
        return row
    if video and video.get("fps") not in (25.0, 30.0):
        row["error"] = "视频帧率 %s 不是 25 或 30" % video["fps"]
        return row
    if (row["duration_ms"] or 0) <= 0:
        row["error"] = "时长无效"
        return row
    row["valid"] = True
    return row


def decode_audio(path, *, start_ms=0, end_ms=None, rate=16000, mono=True):
    """Decode any container's audio to float32 mono numpy. Raises AVError when there is no audio."""
    require_tools()
    cmd = [FFMPEG, "-v", "error", "-nostdin"]
    if start_ms:
        cmd += ["-ss", "%.6f" % (start_ms / 1000.0)]
    if end_ms is not None:
        cmd += ["-t", "%.6f" % (max(0, end_ms - start_ms) / 1000.0)]
    cmd += ["-i", str(path), "-vn", "-ac", "1" if mono else "2", "-ar", str(rate),
            "-f", "f32le", "-"]
    proc = subprocess.run([str(c) for c in cmd], capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        raise AVError("无法解码音轨 %s：%s" % (path, (proc.stderr or b"").decode("utf-8", "replace")[-400:]))
    samples = np.frombuffer(proc.stdout, dtype="<f4").astype(np.float64)
    if samples.size < rate // 10:
        raise AVError("音轨过短（%d 采样）" % samples.size)
    return samples, rate


def audio_rms(samples):
    return float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0


def has_real_audio(path, *, start_ms=0, end_ms=None, min_rms=1e-3):
    """A declared audio track must actually carry non-silence. Tech tones count as signal."""
    try:
        samples, _ = decode_audio(path, start_ms=start_ms, end_ms=end_ms)
    except AVError:
        return False, None
    rms = audio_rms(samples)
    return rms >= min_rms, rms


def count_frames(path):
    """Exact video frame count. Short clips only (demuxes the whole video)."""
    require_tools()
    proc = run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_frames",
                "-show_entries", "stream=nb_read_frames", "-of",
                "default=nokey=1:noprint_wrappers=1", str(path)])
    text = (proc.stdout or "").strip()
    return int(text) if text.isdigit() else None


def alpha_stats(path, *, max_frames=None):
    """Decode the alpha plane of a transparent clip. Coverage must be non-trivial."""
    require_tools()
    info = probe(path)
    if not info["valid"] or not info["video"].get("has_alpha"):
        return {"has_alpha": False, "coverage": 0.0, "edge_ratio": 0.0, "frames": 0}
    width, height = info["video"]["width"], info["video"]["height"]
    cmd = [FFMPEG, "-v", "error", "-nostdin", "-i", str(path)]
    if max_frames:
        cmd += ["-frames:v", str(max_frames)]
    cmd += ["-vf", "alphaextract", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    proc = subprocess.run([str(c) for c in cmd], capture_output=True)
    raw = proc.stdout
    frame_size = width * height
    if proc.returncode != 0 or not raw or len(raw) % frame_size != 0:
        return {"has_alpha": False, "coverage": 0.0, "edge_ratio": 0.0, "frames": 0}
    frames = len(raw) // frame_size
    blob = np.frombuffer(raw[: frames * frame_size], dtype=np.uint8)
    coverage = float(np.mean(blob > 16))
    edge = float(np.mean((blob > 16) & (blob < 240)))
    return {"has_alpha": True, "coverage": round(coverage, 6), "edge_ratio": round(edge, 6),
            "frames": frames, "width": width, "height": height}


def make_wav(path, samples, rate):
    require_tools()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    final = path
    path = path.with_name(path.stem + ".pending" + path.suffix)
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2").tobytes()
    proc = subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "s16le", "-ar", str(rate),
                           "-ac", "1", "-i", "-", "-c:a", "pcm_s16le", str(path)],
                          input=pcm, capture_output=True)
    if proc.returncode != 0:
        raise AVError("写 wav 失败：%s" % proc.stderr.decode("utf-8", "replace")[-400:])
    path.replace(final)

