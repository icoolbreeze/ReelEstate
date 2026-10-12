# Voice clone TTS — for agents

Preferred 口播 clone is IndexTTS-2.5 on one Kaggle T4:

    python scripts/voice/push_indextts25.py --episode <episode-dir> --script <episode-dir>/voice/narration.json

That pushes kernel `tts_indextts25` with accelerator `NvidiaTeslaT4` and `--run indextts25`. T4 uses fp32. Pull with `python scripts/kaggle/pull_job.py --episode <episode-dir> --job tts --run indextts25`. See `docs/kaggle-gpu.md`. The CosyVoice, F5, and local IndexTTS2 instructions below are for an explicit local engine.

Used for narration that has no on-camera presenter (the HeyGen avatar's free tier only covers ~60 s on camera).
The default reference voice is the user's own phone recording (ref_phone_v1). The older HeyGen-generated sample stays available as a fallback. Never use the raw HeyGen training recording.

## One-time setup (Windows, GTX 1070 Ti 8 GB)
    powershell -ExecutionPolicy Bypass -File scripts\voice\setup_cosyvoice.ps1
Installs into `vendor/cosyvoice/` (gitignored): CosyVoice repo, .venv (py3.10, torch 2.8 cu126), and the
Fun-CosyVoice3-0.5B-2512 weights (~9 GB). Pascal GPUs have no bf16, so it runs in fp32 by default (`--fp16` is optional).

## Reference
- **Default (from 2026-10-12):** `assets/presenter/cool-breeze/voice/ref_phone_v1.wav` is the user's own phone recording, provided and approved for cloning. 13.7 s, 44.1 kHz mono: light denoise, trimmed, -16 LUFS.
- `assets/presenter/cool-breeze/voice/ref_phone_v1.txt`: its transcript, checked with Whisper (Whisper garbles 我是贝壳TV, so that phrase is taken from the user).
- The default engine is IndexTTS-2.5 (Kaggle), and the same wav is also the emotion reference:
- Emotion: add `"emo_ref": "ref_phone_v1.wav", "emo_alpha": 1.0` to each line. push_indextts25.py uploads the ref under that name, so the same file is both the speaker and the emotion reference.
- Never put `——` in IndexTTS text, because it is read aloud (heard as “减减”). Use `，` or `……`.
- Fallback (optional, read-only, do not delete): `voices/clone/reference.wav` + `reference.txt` (old HeyGen My Voice sample). Use it only when the script sets `ref_wav` explicitly.

## Model path
Default: `vendor/cosyvoice/pretrained_models/Fun-CosyVoice3-0.5B` (full fp32 weights, downloaded 2026-10-09).
Override with the env var `COSYVOICE_MODEL_DIR`.

## Use
    scripts\voice\clone_tts.cmd projects\<ep>\narration.json [--out DIR] [--fp16]
narration.json:
    {"ref_wav": "assets/presenter/cool-breeze/voice/ref_phone_v1.wav", "ref_text": "assets/presenter/cool-breeze/voice/ref_phone_v1.txt",
     "out": "projects/<ep>/tts",
     "lines": [{"id": "s01", "text": "四千八一个月，西湖文化广场能租到什么样的两室？"}, ...]}
Output: `<out>/<id>.wav` (24 kHz) plus `timings.json`.

## Rules
- Write one line per sentence and spell out numbers the way they should be read (五百七十一米).
- Afterwards, loudnorm to -16 LUFS (`ffmpeg -af loudnorm=I=-16:TP=-1.5`) and check the text with Whisper. Watch homophones such as 两室 → 粮食; use 两居室 if it is misread.
- Label the video 「AI合成声音」 wherever the clone is used.

## Status / finishing the install
See `docs/TASK-voice-clone.md` (step-by-step instructions for the local agent).
Newest CosyVoice as of 2026-10: Fun-CosyVoice3-0.5B-2512 (released 2025-12-11). Nothing newer is official.
Its README table reports zh CER 1.21% / SIM 78.0 (RL variant: 0.81% / 77.4). Inference needs about 4-6 GB VRAM (fp32), which fits 8 GB.
