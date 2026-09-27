"""Segment-wise TTS via qwentts.cpp (qwen-tts.exe).

Usage:
  python pipeline/tts/qwen_tts.py projects/<category>/<id> [--voice narrator_male_30]
         [--mode voicedesign|customvoice|clone] [--speaker vivian]
         [--ref-wav voices/clone/me.wav | --ref-spk x.spk --ref-rvq x.rvq] [--ref-text x.txt]
         [--only s01,s03] [--seed 42] [--dry-run]

Outputs audio/seg_<id>.wav + audio/segments.json [{id,text,file,duration}], sets project.json ai_voice=true.

Modes (see docs/tts.md):
  voicedesign  talker = QWEN_TTS_TALKER (voicedesign model), --instruct <preset description>
  customvoice  talker = QWEN_TTS_CUSTOMVOICE_TALKER, --speaker <name>   (model not downloaded yet)
  clone        talker = QWEN_TTS_BASE_TALKER (BASE model, as in upstream examples/clone.*),
               --ref-wav or --ref-spk/--ref-rvq plus --ref-text     (model not downloaded yet)
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reel_common import REPO_ROOT, load_env, load_json, resolve_project_dir, save_json, setup_console  # noqa: E402

PRESETS_FILE = REPO_ROOT / "voices" / "presets.json"
BUILD_HINT = "请先编译 qwen-tts：在仓库根目录运行 scripts\\build-tts.cmd（见 docs/tts.md）"


def find_exe(env: dict) -> Path | None:
    candidates: list[Path] = []
    if env.get("QWEN_TTS_BIN"):
        b = Path(env["QWEN_TTS_BIN"])
        candidates.append(b)
        # exe may live in build\Release\ or build\ depending on the generator
        if b.parent.name.lower() == "release":
            candidates.append(b.parent.parent / b.name)
        else:
            candidates.append(b.parent / "Release" / b.name)
    vendor = REPO_ROOT / "vendor" / "qwentts.cpp" / "build"
    for name in ("qwen-tts.exe", "qwen-tts"):
        candidates += [vendor / "Release" / name, vendor / name, vendor / "bin" / name, vendor / "bin" / "Release" / name]
    for c in candidates:
        if c.is_file():
            return c
    return None


def ffprobe_duration(path: Path) -> float | None:
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration", "-of",
                              "default=noprint_wrappers=1:nokey=1", str(path)],
                             capture_output=True, text=True, check=True).stdout.strip()
        return round(float(out), 3)
    except Exception:
        return None


def main(argv=None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="qwentts.cpp 分段配音")
    ap.add_argument("project")
    ap.add_argument("--voice", help="voices/presets.json 中的预设名（voicedesign 模式）")
    ap.add_argument("--mode", choices=["voicedesign", "customvoice", "clone"])
    ap.add_argument("--speaker", help="customvoice 预置音色名，如 vivian")
    ap.add_argument("--ref-wav", help="clone：参考音频（放 voices/clone/，需本人书面授权）")
    ap.add_argument("--ref-spk", help="clone：qwen-codec 预编码的 .spk")
    ap.add_argument("--ref-rvq", help="clone：qwen-codec 预编码的 .rvq")
    ap.add_argument("--ref-text", help="clone：参考音频的逐字稿 .txt")
    ap.add_argument("--lang", default="Chinese")
    ap.add_argument("--only", help="只生成指定段落，逗号分隔，如 s01,s03")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--dry-run", action="store_true", help="只打印命令，不调用 exe")
    args = ap.parse_args(argv)

    project_dir = resolve_project_dir(args.project)
    project = load_json(project_dir / "project.json")
    env = load_env()
    tts_cfg = project.get("tts", {}) or {}
    mode = args.mode or tts_cfg.get("mode", "voicedesign")
    voice = args.voice or tts_cfg.get("voice", "narrator_male_30")

    models_dir = Path(env.get("QWEN_TTS_MODELS", str(REPO_ROOT / "vendor" / "qwentts.cpp" / "models")))
    talker_name = {
        "voicedesign": env.get("QWEN_TTS_TALKER", "qwen-talker-1.7b-voicedesign-Q8_0.gguf"),
        "customvoice": env.get("QWEN_TTS_CUSTOMVOICE_TALKER", "qwen-talker-1.7b-customvoice-Q8_0.gguf"),
        "clone": env.get("QWEN_TTS_BASE_TALKER", "qwen-talker-1.7b-base-Q8_0.gguf"),
    }[mode]
    talker = models_dir / talker_name
    codec = models_dir / env.get("QWEN_TTS_CODEC", "qwen-tokenizer-12hz-Q8_0.gguf")

    exe = find_exe(env)
    problems = []
    if not exe:
        problems.append(f"找不到 qwen-tts 可执行文件（QWEN_TTS_BIN={env.get('QWEN_TTS_BIN', '未设置')}，已尝试 build\\ 与 build\\Release\\）。{BUILD_HINT}")
    if not talker.is_file():
        problems.append(f"找不到 talker 模型：{talker}" + ("（克隆需 BASE 模型，尚未下载）" if mode == "clone" else ""))
    if not codec.is_file():
        problems.append(f"找不到 codec 模型：{codec}")

    mode_args: list[str] = []
    if mode == "voicedesign":
        presets = load_json(PRESETS_FILE).get("voicedesign", {})
        if voice not in presets:
            print(f"错误：未知音色预设 {voice}，可选：{', '.join(presets)}", file=sys.stderr)
            return 2
        mode_args = ["--instruct", presets[voice]["instruct"]]
    elif mode == "customvoice":
        if not args.speaker:
            print("错误：customvoice 模式需要 --speaker", file=sys.stderr)
            return 2
        mode_args = ["--speaker", args.speaker]
    else:  # clone (placeholder: BASE model not downloaded yet)
        if args.ref_wav:
            mode_args += ["--ref-wav", args.ref_wav]
        elif args.ref_spk and args.ref_rvq:
            mode_args += ["--ref-spk", args.ref_spk, "--ref-rvq", args.ref_rvq]
        else:
            print("错误：clone 模式需要 --ref-wav，或 --ref-spk 与 --ref-rvq", file=sys.stderr)
            return 2
        if args.ref_text:
            mode_args += ["--ref-text", args.ref_text]
        print("⚠️  克隆模式：必须有声音本人的书面授权（放 consent/ 或 voices/clone/），发布时勾选 AI 标注。")

    segments = project.get("narration", {}).get("segments", [])
    only = set(args.only.split(",")) if args.only else None
    audio_dir = project_dir / "audio"
    audio_dir.mkdir(exist_ok=True)

    if problems and not args.dry_run:
        print("❌ 无法生成配音：", file=sys.stderr)
        for p in problems:
            print("   - " + p, file=sys.stderr)
        return 1

    seg_json_path = audio_dir / "segments.json"
    existing = {s["id"]: s for s in load_json(seg_json_path)} if seg_json_path.exists() else {}
    results = []
    for seg in segments:
        sid, text = seg["id"], seg["text"]
        if only and sid not in only:
            if sid in existing:
                results.append(existing[sid])
            continue
        out = audio_dir / f"seg_{sid}.wav"
        cmd = [str(exe or "qwen-tts.exe"), "--model", str(talker), "--codec", str(codec), *mode_args,
               "--lang", args.lang, "-o", str(out)]
        if args.seed is not None:
            cmd += ["--seed", str(args.seed)]
        if args.dry_run:
            print("[dry-run] " + " ".join(f'"{c}"' if " " in c else c for c in cmd) + f"  < (prompt: {text})")
            continue
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False, newline="\n") as tf:
            tf.write(text + "\n")
            prompt_path = tf.name
        print(f"▶ {sid}: {text}")
        try:
            with open(prompt_path, "rb") as stdin:
                proc = subprocess.run(cmd, stdin=stdin)
        finally:
            Path(prompt_path).unlink(missing_ok=True)
        if proc.returncode != 0 or not out.exists():
            print(f"❌ 段落 {sid} 生成失败（exit {proc.returncode}）", file=sys.stderr)
            return 1
        dur = ffprobe_duration(out)
        results.append({"id": sid, "text": text, "file": f"audio/{out.name}", "duration": dur})

    if args.dry_run:
        if problems:
            print("\n注意（实际运行前需解决）：")
            for p in problems:
                print("   - " + p)
        return 0

    save_json(seg_json_path, results)
    project["ai_voice"] = True
    project.setdefault("tts", {})
    project["tts"].update({"mode": mode, "voice": voice if mode == "voicedesign" else (args.speaker or "clone")})
    save_json(project_dir / "project.json", project)
    print(f"✅ 已写入 {seg_json_path.relative_to(REPO_ROOT).as_posix()}（{len(results)} 段），project.json 已标记 ai_voice=true")
    print("📋 发布时记得勾选 AI 生成内容标注。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
