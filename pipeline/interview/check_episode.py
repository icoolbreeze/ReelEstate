"""Read-only interview preflight. Does not start a model, a paid API, or a render."""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from editlist import load_decisions  # noqa: E402
from episode import load_episode  # noqa: E402
from layout import check_layout, layout_document  # noqa: E402
from probe import load_sources  # noqa: E402
from transcript import load_corrected  # noqa: E402
from pipeline.common.color_restore import gate  # noqa: E402


def report(ep, cfg, draft):
    errors = []
    pending = []
    layout_errors = check_layout(layout_document())
    errors.extend(layout_errors)
    decisions = load_decisions(ep / "edit" / "decisions.json")
    if not decisions["segments"]:
        pending.append("剪辑清单还没有采用片段")
    elif not decisions["confirmed"]:
        pending.append("剪辑清单尚未确认，不能抠像")
    roles = {item["id"]: item.get("role") for item in load_sources(ep)}
    transcript = load_corrected(ep / "transcript" / "corrected.json", roles) if (ep / "transcript" / "corrected.json").is_file() else {
        "status": "pending_transcript", "completed": False, "fixture": False, "spans": []}
    if transcript["status"] != "corrected" or not transcript["spans"]:
        pending.append("校正转录待导入")
    elif transcript.get("fixture"):
        pending.append("转录是技术测试夹具，不是真人口播")
    for item in load_sources(ep):
        path = ep / item["path"]
        if item.get("required", True) and not path.is_file():
            pending.append("缺少%s：%s" % (item.get("role") or item["id"], item["path"]))
    guest = cfg.get("guest") or {}
    if str(guest.get("consent") or "待填") != "confirmed":
        pending.append("嘉宾拍摄与使用确认仍是待填")
    if str(guest.get("display_name") or "待填") == "待填":
        pending.append("嘉宾显示名待填")
    if not (ep / "data" / "timeline.json").is_file():
        errors.append("缺少 data/timeline.json，先运行 compose")
    else:
        timeline = json.loads((ep / "data" / "timeline.json").read_text(encoding="utf-8-sig"))
        if timeline.get("series") != "interview":
            errors.append("timeline series 不是 interview")
        if int(timeline.get("width") or 0) != 1920 or int(timeline.get("height") or 0) != 1080:
            errors.append("时间线画幅不是 1920x1080")
        if int(timeline.get("fps") or 0) not in (25, 30):
            errors.append("时间线帧率不是 25 或 30")
    technical = bool(cfg.get("technical_test")) and cfg.get("purpose") == "test"
    if not (draft and technical and (cfg.get("render") or {}).get("background") == "placeholder"):
        from pipeline.interview.production import validation_errors
        errors.extend(validation_errors(ep, cfg, locals().get("timeline", {})))
    live = ["真人抠像", "口型同步", "演播室真实感", "达芬奇免费版 GUI 导入"]
    blockers = list(errors)
    if cfg.get("purpose") == "test" and not draft:
        blockers.append("测试工程禁止正式发布")
    if not (draft and technical):
        blockers.extend(pending)
    return {
        "pass": not blockers,
        "scope": "framework-draft" if draft and technical else "interview",
        "series": "interview",
        "show": "小ONE会客厅",
        "purpose": cfg.get("purpose") or "production",
        "technical_test": technical,
        "errors": errors,
        "pending": pending,
        "live_acceptance": "待实拍验证",
        "live_items": live,
        "completed_stages": [] if blockers else ["routing", "layout", "timeline"],
        "matte": {"completed": False, "matanyone2_passed": False, "status": "待实拍验证" if technical else "pending_media"},
        "sync": {"completed": False, "status": "pending_media"},
        "heygen": False,
        "tts": False,
        "atempo": 1,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode")
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args()
    try:
        ep, cfg = load_episode(args.episode)
        payload = report(ep, cfg, args.draft)
        color_errors, color_warnings = gate(ep)   # D-Log M colour gate (all content lines)
        if color_errors:
            payload["pass"] = False
            payload["errors"] = list(payload.get("errors") or []) + color_errors
        payload["color_warnings"] = color_warnings
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"pass": False, "errors": [str(exc)], "pending": [], "live_acceptance": "待实拍验证"}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
