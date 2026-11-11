"""Captions come from corrected speech that overlaps an edit, then move onto the composition clock.

The interview outline is not a caption source.
"""
from pipeline.interview.timebase import frames_for_span


def map_captions(segments, spans, fps):
    cursor = 0
    captions = []
    for segment in segments:
        duration = segment["source_out_ms"] - segment["source_in_ms"]
        for span in spans:
            if span.get("source_id") and span["source_id"] != segment["source_id"]:
                continue
            start = max(span["source_in_ms"], segment["source_in_ms"])
            end = min(span["source_out_ms"], segment["source_out_ms"])
            if end <= start:
                continue
            text = str(span.get("text") or "").strip()
            if not text:
                continue
            comp_in = cursor + (start - segment["source_in_ms"])
            comp_out = cursor + (end - segment["source_in_ms"])
            f0, f1 = frames_for_span(comp_in, comp_out, fps)
            captions.append({
                "text": text,
                "speaker": span.get("speaker") or "unknown",
                "speaker_note": span.get("speaker_note"),
                "f0": f0,
                "f1": f1,
                "comp_in_ms": comp_in,
                "comp_out_ms": comp_out,
                "source_in_ms": start,
                "source_out_ms": end,
                "segment_id": segment["id"],
            })
        cursor += duration
    return captions, cursor
