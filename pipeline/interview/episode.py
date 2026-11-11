"""Load one 小ONE会客厅 episode. Unknown facts stay 待填."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SERIES = REPO / "projects" / "interview"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from pipeline.common.voice_config import read_yaml  # noqa: E402


def episode_path(value) -> Path:
    ep = Path(value)
    if not ep.is_absolute():
        candidate = REPO / ep
        ep = candidate if candidate.exists() else SERIES / str(value)
    ep = ep.resolve()
    if SERIES.resolve() not in ep.parents and ep.parent.resolve() != SERIES.resolve():
        raise ValueError("episode must be inside projects/interview: %s" % ep)
    if not (ep / "episode.yaml").is_file():
        raise ValueError("missing episode.yaml: %s" % ep)
    return ep


def load_episode(value):
    ep = episode_path(value)
    cfg = read_yaml(ep / "episode.yaml")
    if cfg.get("series") != "interview":
        raise ValueError("%s series is %s; interview pipeline only accepts series: interview" % (ep.name, cfg.get("series")))
    if cfg.get("show") != "小ONE会客厅":
        raise ValueError("show 必须是 小ONE会客厅")
    purpose = str(cfg.get("purpose") or "production")
    if purpose not in ("production", "test"):
        raise ValueError("purpose 只能是 production 或 test")
    render = cfg.get("render") or {}
    if int(render.get("width") or 0) != 1920 or int(render.get("height") or 0) != 1080:
        raise ValueError("首版只支持 1920x1080")
    if int(render.get("fps") or 0) not in (25, 30):
        raise ValueError("fps 只能是 25 或 30")
    if str(render.get("background") or "placeholder") not in ("live", "virtual", "placeholder"):
        raise ValueError("background 只能是 live、virtual 或 placeholder")
    voice = cfg.get("voice") or {}
    if voice.get("mode") != "location":
        raise ValueError("访谈只用现场同期声，不默认 TTS、克隆或 HeyGen")
    if float(voice.get("atempo", 1)) != 1.0:
        raise ValueError("访谈不默认 atempo")
    if voice.get("keep_pauses") is not True or voice.get("keep_breaths") is not True:
        raise ValueError("访谈保留自然停顿和呼吸")
    matting = cfg.get("matting") or {}
    if matting.get("fp16") is True:
        raise ValueError("MatAnyone2 在 1070 Ti 上保持 FP32")
    if int(matting.get("max_size") or 1080) < 1080 and matting.get("max_size_explicit") is not True:
        raise ValueError("不会自动把抠像短边降到 720")
    guest = cfg.get("guest") or {}
    for key in ("display_name", "store", "brand", "consent"):
        if key not in guest:
            raise ValueError("guest.%s 缺失" % key)
    return ep, cfg
