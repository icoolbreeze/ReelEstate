"""Plan mattes for confirmed edit ranges only. Does not start a model."""
from pipeline.interview.cache import cache_key
from pipeline.interview.timebase import require_ms

HANDLE_MS = 500
CHUNK_MS = 20000
WARMUP_MS = 1000


def annotate_shots(segments):
    previous = None
    rows = []
    for segment in segments:
        row = dict(segment)
        row["reset_matte"] = segment["shot"] != previous
        previous = segment["shot"]
        rows.append(row)
    return rows


def _chunks(segment):
    start = max(0, segment["source_in_ms"] - HANDLE_MS)
    end = segment["source_out_ms"] + HANDLE_MS
    if end - start <= CHUNK_MS:
        return [{
            "segment_id": segment["id"],
            "shot": segment["shot"],
            "source_id": segment["source_id"],
            "source_in_ms": start,
            "source_out_ms": end,
            "emit_in_ms": segment["source_in_ms"],
            "emit_out_ms": segment["source_out_ms"],
            "warmup_ms": 0,
            "reset_matte": segment["reset_matte"],
            "carry_state": False,
        }]
    jobs = []
    cursor = start
    first = True
    while cursor < end:
        chunk_end = min(end, cursor + CHUNK_MS)
        warmup = 0 if first else WARMUP_MS
        jobs.append({
            "segment_id": segment["id"],
            "shot": segment["shot"],
            "source_id": segment["source_id"],
            "source_in_ms": max(0, cursor - warmup),
            "source_out_ms": chunk_end,
            "emit_in_ms": cursor,
            "emit_out_ms": chunk_end,
            "warmup_ms": warmup,
            "reset_matte": bool(segment["reset_matte"] and first),
            "carry_state": not first,
        })
        cursor = chunk_end
        first = False
    return jobs


def furniture_status(matting):
    choice = str((matting or {}).get("keep_furniture") or "待填")
    mask = (matting or {}).get("furniture_mask")
    if choice == "drop":
        return {"keep_furniture": "drop", "ready": True, "note": "明确不保留椅子和桌子。"}
    if choice == "keep" and mask:
        return {"keep_furniture": "keep", "furniture_mask": mask, "ready": True,
                "note": "保留家具依赖辅助遮罩，不依赖人像模型自动判断。"}
    return {"keep_furniture": choice, "ready": False,
            "note": "椅子和桌子是否保留仍是待填。人像模型不会自动正确保留它们。"}


def plan(segments, fingerprint, matting, mask_sha=""):
    matting = matting or {}
    engine = str(matting.get("engine") or "matanyone2")
    max_size = int(matting.get("max_size") or 1080)
    furniture = furniture_status(matting)
    if max_size < 1080 and matting.get("max_size_explicit") is not True:
        raise ValueError("不会自动把 1080 降到更低分辨率")
    jobs = []
    for segment in annotate_shots(segments):
        for job in _chunks(segment):
            require_ms(job["source_in_ms"], "job.in")
            require_ms(job["source_out_ms"], "job.out")
            job["key"] = cache_key(
                input=fingerprint,
                source_in_ms=job["source_in_ms"],
                source_out_ms=job["source_out_ms"],
                engine=engine,
                max_size=max_size,
                mask=mask_sha,
                keep_furniture=furniture["keep_furniture"],
                warmup_ms=job["warmup_ms"],
            )
            job["engine"] = engine
            job["max_size"] = max_size
            job["fp16"] = False
            jobs.append(job)
    return {"engine": engine, "max_size": max_size, "fp16": False, "furniture": furniture, "jobs": jobs,
            "command": "scripts/matting/matte_local.cmd", "executed": False}
