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

## Default engine: flova_minimax (MiniMax Speech 2.8 HD, voice Gentle_Youth)

Chosen 2026-10-12. It must sound natural and match the Cool Breeze avatar (a man of about 30 with glasses and a suit); the voice only needs a slight resemblance to the user.
- Run: `C:\ProgramData\miniconda3\python.exe scripts\voice\clone_tts.py <script.json> [--episode <EP>] --out <DIR> [--auto-fallback]`. The default engine is `flova_minimax`.
- Route: `scripts/voice/flova_minimax_tts.py` calls the flova MCP tool `generate_speech` (`~/.flova-mcp/server.js`, through `scripts/flova/mcp_call.py call()`). It makes one `flova run` per line with model `speech-2.8-hd` and voice `Chinese (Mandarin)_Gentle_Youth` (profile kid4), downloads the mp3, then loudnorms to -16 LUFS as a mono 44.1 kHz wav at `<DIR>/<id>.wav`.
- Cost: about 10 credits per line. Budget gate: generate_speech is FAIL-CLOSED on the balance (it needs a readable balance of at least `min_balance`, default 20), and it reports the balance delta.
- Other generate_speech options: `model=seed-audio-1.0` with `ref_audio=<wav>` clones a voice (Seed Audio is the only flova audio model that clones), and `model=elevenlabs` uses presets.
- Recipe (approved 2026-10-13): **whole-passage mode by default** (`mode: passage`). All lines are joined, each ending with punctuation, into ONE flova call (about 10 credits) and saved as `<DIR>/passage.wav` plus `passage.json` (line ids and texts). Use light rhythm punctuation (commas before key numbers and hooks). Then `atempo=1.1` (`tempo: 1.1` in presenter.yaml, or `--tempo`; pitch is preserved, range 0.5-2.0), then loudnorm to -16 LUFS. Take line and section timings for the edit from Whisper word timestamps on the sped-up wav. `--mode line` makes one call per line.
- Offline post-steps (no credits, default in passage mode; dependency: `pip install faster-whisper` into conda):
  1. `scripts/voice/passage_timings.py DIR/passage.wav`: faster-whisper word timestamps (the script is passed as the prompt), then fuzzy character alignment (difflib) to the line order in `passage.json`, so mishearings still align. Unheard characters get interpolated times. Writes `timings.json` (per line `start`/`end`, per-character times, `match_ratio`). With `--split` it also cuts `DIR/<id>.wav` per line plus `<id>.json` word sidecars in the `voice_timing.read_alignment` format (`build_vo.py --alignment-dir DIR`).
  2. `scripts/voice/retime_pauses.py DIR/passage.wav`: resizes punctuation pauses to after 。！？ 0.42 s, after ，、 0.31 s, and at a line/section break 0.6 s. Each target gets ±15% variation with seed 7. A per-line override goes in `passage.json` as `"pause_after": 0.7` (e.g. after the hook). It never cuts speech: it keeps 60/40 ms guards, only edits gaps that pass an energy check, lengthens with looped room tone, and uses 30 ms crossfades. Writes `retime_report.json`.
  3. loudnorm -16 LUFS again, then `passage_timings.py --split` again.
  Skip a step with `--no-retime` or `--no-timings` (clone_tts.py and flova_minimax_tts.py).
  Test 2026-10-13 on gentleyouth v1 at tempo 1.2: median pause after 。 0.40 -> 0.42 s, after ， 0.38 -> 0.30 s, at section breaks 0.41 -> 0.57 s; Whisper complete; all 5 sidecars pass `read_alignment`.
- Why atempo: the flova route refuses MiniMax speed/pitch/emotion settings (tested 2026-10-13); `<#x#>` pause markup only lengthened pauses.
- Fallbacks: (1) indextts25 on Kaggle (`push_indextts25.py`, a clone of ref_phone_v1); (2) local F5 as the last resort (`--auto-fallback` runs it after a flova failure, exit 21).
- The rule still applies: never put `——` or `--` in TTS text, because it is read aloud. Use `，` or `…` for pauses. The wrapper rejects such text.

## mimo engine (Xiaomi MiMo voiceclone, cloud)

`python scripts\voice\clone_tts.py script.json --engine mimo --out DIR`

- Model `mimo-v2.5-tts-voiceclone` (override with `"mimo_model"` in the script JSON). No GPU or venv needed, only the Python standard library.
- Key: env `MIMO_API_KEY` (never commit it). Base URL: env `MIMO_BASE_URL`, default `https://token-plan-sgp.xiaomimimo.com/v1` (Token Plan). Pay-as-you-go uses `https://api.xiaomimimo.com/v1`. Keys come from https://platform.xiaomimimo.com.
- Request: POST `/chat/completions`, header `api-key`. Send `messages=[{"role":"user","content":<style instruction>},{"role":"assistant","content":<text>}]` and `audio={"format":"wav","voice":"data:audio/wav;base64,<ref>"}`. The ref must be wav or mp3 and under 10 MB. The reply audio is in `choices[0].message.audio.data`, as base64 wav.
- Style: put `"style"` at the top level or on each line, as natural language, e.g. "像朋友聊天，音高起伏明显，句尾往下收".
- ref_text is not used. TTS is free for a limited time. Keep calls interactive-scale, because the Token Plan forbids automated backends.
- 2026-10-12 test (demo_v6 hook plus metro section, about 30 s): ECAPA 0.87 against ref_phone_v1. Pitch range 10.6 st and about 67% falling ends, but slow (about 4 chars/s, 32.5 s). See /workspace/voice/compare on the box.
