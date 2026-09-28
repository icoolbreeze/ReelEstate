"""Stage 6 · tts via edge-tts (Microsoft Edge online TTS, free). Fallback when qwen-tts is unavailable.

Writes audio/seg_<id>.wav + audio/segments.json and sets project.json ai_voice=true.
Own-voice mode (brief.voice.mode=own) just validates that the user dropped wavs and builds segments.json.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reel_common import REPO_ROOT, load_json, save_json  # noqa: E402


def _ffprobe(path: Path) -> float | None:
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return round(float(out), 3)
    except Exception:
        return None


async def _synth(text: str, out: Path, voice: str, rate: str) -> None:
    import edge_tts
    # edge-tts writes mp3; we re-wrap to wav for Remotion / ffprobe consistency.
    mp3 = out.with_suffix(".mp3")
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    await communicate.save(str(mp3))
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp3), "-ac", "1", "-ar", "24000", str(out)],
        check=True, capture_output=True,
    )
    mp3.unlink(missing_ok=True)


def run(project_dir: Path, brief: dict | None = None, force: bool = False) -> dict:
    project = load_json(project_dir / "project.json")
    brief = brief or {}
    mode = (brief.get("voice") or {}).get("mode") or (project.get("tts") or {}).get("mode") or "edge"
    audio_dir = project_dir / "audio"
    audio_dir.mkdir(exist_ok=True)
    seg_json = audio_dir / "segments.json"
    if seg_json.exists() and not force and mode != "own":
        return {"skipped": True, "segments": len(load_json(seg_json))}

    segments = project.get("narration", {}).get("segments", [])
    results = []

    if mode == "own":
        for seg in segments:
            wav = audio_dir / f"seg_{seg['id']}.wav"
            if not wav.exists():
                raise SystemExit(f"own-voice 模式：缺少 {wav.relative_to(REPO_ROOT).as_posix()}，请放入本人录音")
            results.append({"id": seg["id"], "text": seg["text"], "file": f"audio/{wav.name}", "duration": _ffprobe(wav)})
        save_json(seg_json, results)
        project["ai_voice"] = False
        save_json(project_dir / "project.json", project)
        return {"mode": "own", "segments": len(results)}

    # Prefer edge-tts (works without local model). qwen path remains available via npm run tts.
    voice = (brief.get("voice") or {}).get("edge_voice") or "zh-CN-YunxiNeural"
    rate = (brief.get("voice") or {}).get("rate") or "+15%"
    try:
        import edge_tts  # noqa: F401
    except ImportError as e:
        raise SystemExit("未安装 edge-tts：pip install edge-tts（或改用 npm run tts 走 qwen）") from e

    async def all_segs():
        for seg in segments:
            out = audio_dir / f"seg_{seg['id']}.wav"
            if out.exists() and not force:
                results.append({"id": seg["id"], "text": seg["text"], "file": f"audio/{out.name}", "duration": _ffprobe(out)})
                continue
            print(f"▶ edge-tts {seg['id']}: {seg['text']}")
            await _synth(seg["text"], out, voice, rate)
            results.append({"id": seg["id"], "text": seg["text"], "file": f"audio/{out.name}", "duration": _ffprobe(out)})

    asyncio.run(all_segs())
    save_json(seg_json, results)
    project["ai_voice"] = True
    project.setdefault("tts", {})["mode"] = "edge"
    project["tts"]["voice"] = voice
    save_json(project_dir / "project.json", project)
    print(f"✅ edge-tts 写入 {seg_json.relative_to(REPO_ROOT).as_posix()}（{len(results)} 段）")
    return {"mode": "edge", "segments": len(results), "voice": voice}
