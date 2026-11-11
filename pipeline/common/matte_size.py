"""MatAnyone2 short-side cap. Pure function: no torch, no ffmpeg, no file writes.

max_size is the inference short-side limit. Inputs already at or below that
limit stay at their own size and are never upscaled. A 4K frame inferred at
1080p and resized back to 4K is not a native 4K matte.
"""


def inference_size(width, height, max_size):
    width = int(width)
    height = int(height)
    if width < 1 or height < 1:
        raise ValueError("invalid frame size")
    if max_size is None or int(max_size) <= 0:
        inference_width, inference_height = width, height
    else:
        limit = int(max_size)
        short = min(width, height)
        if short > limit:
            inference_height = int(height / short * limit)
            inference_width = int(width / short * limit)
        else:
            inference_width, inference_height = width, height
    if inference_width < 1 or inference_height < 1:
        raise ValueError("inference size collapsed")
    native = (inference_width, inference_height) == (width, height)
    return {
        "input_width": width,
        "input_height": height,
        "inference_width": inference_width,
        "inference_height": inference_height,
        "output_width": width,
        "output_height": height,
        "native_inference": native,
        "mask_interpolated_to_output": not native,
        "native_4k": bool(native and max(width, height) >= 3840 and min(width, height) >= 2160),
    }


def acceptance(requested, actual, fallback_reason):
    reason = fallback_reason or None
    passed = actual == "matanyone2" and not reason
    return {
        "requested_engine": requested,
        "actual_engine": actual,
        "fallback_reason": reason,
        "fallback": bool(reason),
        "matanyone2_passed": passed,
    }


def use_fp16(engine, requested):
    """MatAnyone2 stays FP32 on the Pascal 1070 Ti. FP16 is RVM-only and explicit."""
    if engine == "matanyone2":
        return False
    return bool(requested)


def oom_note(reason):
    text = reason or ""
    if "out of memory" not in text.lower() and "cuda" not in text.lower():
        return None
    if "out of memory" in text.lower() or "CUDA out of memory" in text:
        return "显存不足。未把 max_size 从 1080 自动降到 720。可显式传入更小的 --max-size，或改用 RVM 后备；回退不是 MatAnyone2 通过。"
    return None
