"""Integer milliseconds on the source clock.

source_in_ms is inclusive. source_out_ms is exclusive.
Frames at fps F: start = (ms * F) // 1000, end = (out_ms * F) // 1000.
A span keeps the same real duration at 25fps and 30fps. Do not reuse a
30fps frame count on a 25fps timeline. Seconds are not stored in edit fields.
"""

ALLOWED_FPS = (25, 30)
ENTER_S = 10 / 30
EXIT_S = 8 / 30


def require_fps(fps):
    fps = int(fps)
    if fps not in ALLOWED_FPS:
        raise ValueError("interview fps must be 25 or 30")
    return fps


def require_ms(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%s must be integer milliseconds" % name)
    if value < 0:
        raise ValueError("%s must be >= 0" % name)
    return value


def frames_for_span(start_ms, end_ms, fps):
    fps = require_fps(fps)
    start_ms = require_ms(start_ms, "source_in_ms")
    end_ms = require_ms(end_ms, "source_out_ms")
    if end_ms <= start_ms:
        raise ValueError("source_out_ms must be greater than source_in_ms")
    start = (start_ms * fps) // 1000
    end = (end_ms * fps) // 1000
    if end <= start:
        raise ValueError("span is shorter than one frame")
    return start, end


def frames_for_seconds(seconds, fps):
    fps = require_fps(fps)
    if seconds <= 0:
        raise ValueError("duration must be positive")
    return max(1, int(round(float(seconds) * fps)))
