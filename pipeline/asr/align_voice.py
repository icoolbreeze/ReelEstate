#!/usr/bin/env python3
"""Generate wav-bound word timestamps from an existing local Whisper model."""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline/maphub"))
from voice_timing import fingerprint, normalized

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", required=True, help="resolved narration JSON, lines[].text")
    parser.add_argument("--voice-dir", required=True)
    parser.add_argument("--model", required=True, help="existing local .pt file (whisper) or model directory (faster-whisper)")
    parser.add_argument("--backend", choices=("whisper", "faster-whisper"), default="whisper")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compute-type", default=None)
    args = parser.parse_args()
    model_path = Path(args.model).resolve()
    voice_dir = Path(args.voice_dir).resolve()
    if REPO not in voice_dir.parents:
        raise SystemExit("--voice-dir must be inside the repo")
    if args.backend == "whisper":
        if not model_path.is_file() or model_path.suffix != ".pt":
            raise SystemExit("--model must be an existing local Whisper .pt file")
        import whisper
        model = whisper.load_model(str(model_path), device=args.device)
    else:
        if not model_path.is_dir():
            raise SystemExit("--model must be an existing local faster-whisper model directory")
        from faster_whisper import WhisperModel
        model = WhisperModel(str(model_path), device=args.device,
                             compute_type=args.compute_type or ("int8" if args.device == "cpu" else "float32"),
                             local_files_only=True)
    data = json.loads(Path(args.script).read_text(encoding="utf-8-sig"))
    failures = []
    for line in data["lines"]:
        lid = str(line["id"])
        if lid != Path(lid).name:
            raise SystemExit("unsafe line id")
        audio = voice_dir / (lid + ".wav")
        if not audio.is_file():
            failures.append(lid + ": missing wav")
            continue
        print("aligning", lid, flush=True)
        if args.backend == "whisper":
            result = model.transcribe(str(audio), language="zh", word_timestamps=True,
                                      fp16=args.device == "cuda" and args.compute_type == "float16")
            words = [{"t": word["word"].strip(), "s": word["start"], "e": word["end"]}
                     for segment in result["segments"] for word in segment.get("words", [])
                     if normalized(word["word"])]
        else:
            segments, info = model.transcribe(str(audio), language="zh", word_timestamps=True, vad_filter=False)
            words = [{"t": word.word.strip(), "s": word.start, "e": word.end}
                     for segment in segments for word in (segment.words or []) if normalized(word.word)]
        payload = {"text": line["text"], "audio_sha256": fingerprint(audio), "words": words,
                   "transcript": "".join(w["t"] for w in words), "backend": args.backend}
        if normalized(payload["transcript"]) != normalized(line["text"]) or any(w["e"] <= w["s"] for w in words):
            target = audio.with_suffix(".review.json")
            failures.append(lid + ": transcript/timing differs; listen and review before accepting")
        else:
            target = audio.with_suffix(".json")
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        raise SystemExit(2)
    print("aligned", len(data["lines"]), "wav files")

if __name__ == "__main__":
    main()
