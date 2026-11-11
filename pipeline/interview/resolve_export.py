"""Optional DaVinci Resolve free handoff. Does not drive the GUI and does not render PNG by default."""
import json
import shutil
from pathlib import Path

ALPHA_NOTE = (
    "ProRes 4444 里的 RGB 是未预乘的原色，A 是独立遮罩（straight alpha）。"
    "达芬奇导入时 Alpha Mode 选 Straight。选 Premultiplied 会在边缘出黑边或白边。"
)
RESOLVE_CANDIDATES = (
    Path(r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"),
    Path(r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"),
)
MAX_PNG_FRAMES = 150


def find_resolve():
    for path in RESOLVE_CANDIDATES:
        if path.is_file():
            return str(path)
    found = shutil.which("Resolve") or shutil.which("Resolve.exe")
    return found


def alignment(rgb_frames, mask_frames, width, height, fps, mask_width, mask_height, mask_fps):
    errors = []
    if rgb_frames != mask_frames:
        errors.append("RGB 与遮罩帧数不一致")
    if (width, height) != (mask_width, mask_height):
        errors.append("RGB 与遮罩尺寸不一致")
    if fps != mask_fps:
        errors.append("RGB 与遮罩帧率不一致")
    return errors


def png_allowed(frames):
    if frames > MAX_PNG_FRAMES:
        raise ValueError("PNG 序列只按需生成不超过 %d 帧的短片段，不为整场采访生成" % MAX_PNG_FRAMES)
    return True


def handoff_document(ep, installed, media_ready):
    ep = Path(ep)
    return {
        "episode": ep.name,
        "completed": False,
        "export_status": "ready_to_export" if media_ready else "pending_media",
        "davinci_installed": bool(installed),
        "davinci_gui_import": "pending_manual" if installed else "pending_not_installed",
        "magic_mask_required": False,
        "unattended_scripting": False,
        "scripting_note": "免费版常规合成和调色可以手工完成。未验证无人值守脚本，本流程不提供。",
        "preferred_master": "ProRes 4444 yuva444p10le（与 scripts/matting/matte_local.py 的 _rgba.mov 相同）",
        "alpha_mode": "straight",
        "alpha_note": ALPHA_NOTE,
        "not_a_resolve_handoff": ["*_alpha.webm VP9", "供 Remotion 使用的透明 WebM"],
        "fallback_when_prores_rejected": "同尺寸、同帧率、同帧数、同起点的 RGB 视频 + 独立灰度遮罩。灰度值就是 straight alpha。",
        "png_sequence": "仅在明确要求且帧数不超过 %d 时生成" % MAX_PNG_FRAMES,
        "return_path": "达芬奇导出的合成片放回 edit/graded/，compose 可把它当作 live 背景，字幕和资料卡仍由 Remotion 叠加。",
    }


def write_plan(ep, media_ready=False):
    ep = Path(ep)
    installed = find_resolve()
    document = handoff_document(ep, installed, media_ready)
    target = ep / "out" / "drafts" / "resolve" / "handoff.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return document
