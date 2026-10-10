# TASK: finish the CosyVoice voice-clone setup (for the local agent on this PC)

State as of 2026-10-09 21:25 PT (left by the remote agent):
- Done: `vendor/cosyvoice/` (repo, .venv on py3.10, torch 2.8 cu126, CUDA OK on the 1070 Ti).
  The full Fun-CosyVoice3-0.5B-2512 weights finished downloading to `vendor/cosyvoice/pretrained_models/Fun-CosyVoice3-0.5B/` (DL_OK, ~9 GB).
  `/vendor/cosyvoice/` is gitignored. Reference files are in `voices/clone/`.
- Remaining blocker: the first test run failed on `ModuleNotFoundError: No module named 'wget'` (the old setup script filtered it out; that is now fixed).
- Other models already on this PC that were NOT used (do not delete them; they belong to QWAN-Terminal):
  `QWAN-Terminal/QWANagent/ModelServices/models/CosyVoice/pretrained_models/CosyVoice2-0.5B` (older generation),
  `.../models/CosyVoice3-2512_Q8_0.gguf` (quantized Q8, needs a separate cpp runtime),
  `.../models/IndexTTS2/` (gpt.pth 3.3 GB), which could serve as an optional IndexTTS2 comparison.

## Steps
1. Install the missing module:
       uv pip install --python vendor\cosyvoice\.venv\Scripts\python.exe wget
   (Optional: set `COSYVOICE_MODEL_DIR` to use weights stored elsewhere; the default is the vendor path above.)
2. Run the test:
       scripts\voice\clone_tts.cmd voices\clone\test_script.json
   Expected output: `voices\clone\test_out\cosy_0.wav`, `cosy_1.wav`, `timings.json`.
3. QA: loudnorm to -16 LUFS, transcribe with Whisper, and compare against the text (watch for 两室 → 粮食).
   Tell the user the timings (rtf) and play the files for them.
4. Optional comparison: qwentts.cpp clone mode. The exes are in `vendor\qwentts.cpp\build\Release\`, but there are no GGUFs yet.
   Download `qwen-talker-1.7b-base-Q8_0.gguf` and `qwen-tokenizer-12hz-Q8_0.gguf` from HF `Serveurperso/Qwen3-TTS-GGUF`
   into `vendor\qwentts.cpp\models\`, then run:
       qwen-tts.exe --model models\qwen-talker-1.7b-base-Q8_0.gguf --codec models\qwen-tokenizer-12hz-Q8_0.gguf --ref-wav ..\..\voices\clone\reference.wav --ref-text ..\..\voices\clone\reference.txt --lang Chinese -o qwen_0.wav < line.txt
5. Do not commit or push without the user asking. Never touch .mcp.json or .grok/.

## Per episode
Write `projects/<type>/<ep>/narration.json` (format in docs/voice-clone.md) containing only the narration NOT covered by the
HeyGen on-camera minute. Run `scripts\voice\clone_tts.cmd projects\...\narration.json`, then normalize, run the Whisper check, and place the clips in Remotion.
