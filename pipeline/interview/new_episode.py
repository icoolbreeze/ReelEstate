#!/usr/bin/env python3
"""Create a 小ONE会客厅 episode. Does not copy an existing episode.

  python pipeline/interview/new_episode.py --slug gaoxin --topic 高新区租赁 --purpose production
  python pipeline/interview/new_episode.py --slug techtest --tech-test --topic 技术测试
  npm run new -- interview <slug> --topic <主题> [--purpose test] [--tech-test]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SERIES = REPO / "projects" / "interview"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.common.episodes import next_release_number  # noqa: E402
import editlist  # noqa: E402
import research  # noqa: E402
import timeline  # noqa: E402
import transcript  # noqa: E402

SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
BANNED = {"rental", "resale", "knowledge", "interview", "listing", "new", "home"}
DIRS = (
    "footage/raw", "footage/aux", "footage/proxy", "audio/raw", "audio/tech",
    "transcript", "edit", "matte", "data", "work", "out/drafts", "out/release",
    "public/audio", "consent", "jobs", "research",
)


def folder_id(episode: int, slug: str, purpose: str) -> str:
    if not SLUG.fullmatch(slug or ""):
        raise SystemExit("slug 只用小写字母、数字和连字符")
    if any(part in BANNED for part in slug.split("-")):
        raise SystemExit("目录名不写栏目类型")
    if purpose == "test" and episode == 0:
        return "ep00-%s" % slug
    if not 1 <= int(episode) <= 99:
        raise SystemExit("正式编号用 1–99，由发布序列计算，不写死")
    return "ep%02d-%s" % (episode, slug)


def write_tone(path: Path, seconds: int = 6, rate: int = 48000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for i in range(seconds * rate):
        value = int(900 * math.sin(2 * math.pi * 440 * i / rate))
        frames += struct.pack("<h", value)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames)


def media_sources(tech: bool) -> list:
    rows = [
        {"id": "cam_a", "role": "host_camera", "path": "footage/raw/cam_a.mp4", "required": True},
        {"id": "cam_b", "role": "aux_camera", "path": "footage/aux/cam_b.mp4", "required": False},
        {"id": "mic_host", "role": "interviewer_audio", "path": "audio/raw/host.wav", "required": True},
        {"id": "mic_guest", "role": "guest_audio", "path": "audio/raw/guest.wav", "required": True},
        {"id": "room", "role": "room_tone", "path": "audio/raw/room_tone.wav", "required": True},
    ]
    if tech:
        rows.append({"id": "tech_tone", "role": "tech_mix", "path": "audio/tech/tone.wav", "required": False})
    return rows


def write_yaml(ep: Path, spec: dict) -> None:
    number = ""
    if spec["purpose"] == "production":
        number = "release_number: %d\n" % spec["episode"]
    text = """# episode.yaml — 小ONE会客厅。现场同期声，不默认 HeyGen / TTS / 克隆 / 变速。
id: {id}
series: interview
show: 小ONE会客厅
purpose: {purpose}
{number}episode: {episode}
category: interview
topic: {topic}
title: {title}
region: 待填
city: {city}
technical_test: {tech}
guest:
  display_name: 待填
  store: 待填
  brand: 待填
  consent: 待填
  bio: 待填
voice:
  mode: location
  atempo: 1
  keep_pauses: true
  keep_breaths: true
  heygen: false
  tts: false
  clone: false
render:
  width: 1920
  height: 1080
  fps: 30
  background: placeholder
  lufs: -16
matting:
  engine: matanyone2
  max_size: 1080
  fp16: false
  keep_furniture: drop
sync:
  offsets_ms: {{}}
status:
  intake: pending
  matte: pending
  studio_match: pending
  live_acceptance: 待实拍验证
""".format(id=spec["id"], purpose=spec["purpose"], number=number, episode=spec["episode"],
           topic=json.dumps(spec["topic"], ensure_ascii=False),
           title=json.dumps(spec["title"], ensure_ascii=False),
           city=json.dumps(spec["city"], ensure_ascii=False),
           tech="true" if spec["tech"] else "false")
    (ep / "episode.yaml").write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def tech_fixtures(ep: Path) -> None:
    write_tone(ep / "audio" / "tech" / "tone.wav")
    write_json(ep / "edit" / "decisions.json", {
        "confirmed": True,
        "unit": "ms",
        "out_point": "exclusive",
        "note": "技术测试夹具。时间是源媒体上的毫秒，出点不含。",
        "segments": [
            {"id": "E01", "source_id": "cam_a", "shot": "A", "layout": "question", "speaker": "interviewer", "source_in_ms": 0, "source_out_ms": 1500},
            {"id": "E02", "source_id": "cam_a", "shot": "A", "layout": "name", "speaker": "guest", "source_in_ms": 1500, "source_out_ms": 3000},
            {"id": "E03", "source_id": "cam_a", "shot": "A", "layout": "case", "speaker": "guest", "source_in_ms": 3000, "source_out_ms": 4500},
            {"id": "E04", "source_id": "cam_a", "shot": "B", "layout": "data", "speaker": "guest", "source_in_ms": 4500, "source_out_ms": 6000},
        ],
    })
    write_json(ep / "transcript" / "corrected.json", {
        "source": "technical-fixture",
        "fixture": True,
        "invented": False,
        "spans": [
            {"id": "t01", "speaker": "interviewer", "track": "mic_host", "text": "技术测试 问题卡", "source_in_ms": 0, "source_out_ms": 1500},
            {"id": "t02", "speaker": "guest", "track": "mic_guest", "text": "技术测试 姓名条", "source_in_ms": 1500, "source_out_ms": 3000},
            {"id": "t03", "speaker": "guest", "track": "mic_guest", "text": "技术测试 案例卡", "source_in_ms": 3000, "source_out_ms": 4500},
            {"id": "t04", "speaker": "guest", "track": "mic_guest", "text": "技术测试 资料屏", "source_in_ms": 4500, "source_out_ms": 6000},
            {"id": "t05", "text": "这段没有说话人", "source_in_ms": 8000, "source_out_ms": 9000},
        ],
    })
    write_json(ep / "transcript" / "outline.json", {
        "note": "采访提纲不是字幕来源。",
        "questions": ["提纲里的句子不应该变成字幕"],
    })
    write_json(ep / "research" / "allowed.json", {
        "region": "待填",
        "collected_on": "待填",
        "background": "待填",
        "cases": [{
            "label": "技术测试样本",
            "price_kind": "list",
            "value": "待填",
            "unit": "元/月",
            "source": "待填",
            "collected_on": None,
            "basis": "待填",
            "public": False,
            "listing_ref": "INTERNAL",
            "phone": "13800000000",
            "screenshot": "research/do-not-show.png",
        }],
    })


def create(root: Path, spec: dict) -> Path:
    ep = root / spec["id"]
    if ep.exists():
        raise SystemExit("%s already exists" % ep)
    for name in DIRS:
        (ep / name).mkdir(parents=True)
    (ep / "footage" / "raw" / "README.md").write_text("# 原始机位\n\n只读。不要改名、覆写或删除。\n", encoding="utf-8", newline="\n")
    (ep / "audio" / "raw" / "README.md").write_text("# 原始录音\n\n小ONE、嘉宾和环境底噪分轨存放。只读。\n", encoding="utf-8", newline="\n")
    write_yaml(ep, spec)
    write_json(ep / "episode.json", {
        "id": spec["id"],
        "series": "interview",
        "show": "小ONE会客厅",
        "title": spec["title"],
        "topic": spec["topic"],
        "city": spec["city"],
        "technicalTest": spec["tech"],
        "sampleData": False,
        "onScreenNotes": False,
        "format": {"width": 1920, "height": 1080, "fps": 30},
    })
    write_json(ep / "data" / "media_sources.json", media_sources(spec["tech"]))
    write_json(ep / "data" / "clearance.json", {"guest_consent": "待填", "store_shoot_ok": "待填", "facts_checked": False})
    if spec["tech"]:
        tech_fixtures(ep)
    elif not (ep / "edit" / "decisions.json").is_file():
        write_json(ep / "edit" / "decisions.json", {"confirmed": False, "unit": "ms", "out_point": "exclusive", "segments": []})
    allowed = ep / "research" / "allowed.json"
    pack = research.import_file(allowed, ep / "data" / "research_pack.json") if allowed.is_file() else {"cards": [], "questions": [], "checklist": ["没有导入资料"]}
    from pipeline.common.voice_config import read_yaml
    cfg = read_yaml(ep / "episode.yaml")
    decisions = editlist.load_decisions(ep / "edit" / "decisions.json")
    roles = {item["id"]: item.get("role") for item in media_sources(spec["tech"])}
    loaded = transcript.load_corrected(ep / "transcript" / "corrected.json", roles)
    timeline.write_timeline(ep, cfg, decisions, loaded["spans"], pack)
    for name in ("brands.json", "social.json"):
        source = REPO / "templates" / "interview" / name
        if source.is_file():
            (ep / "data" / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    (ep / "data" / "episode.json").write_text((ep / "episode.json").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    (ep / "README.md").write_text(
        "# %s\n\n小ONE会客厅。%s\n流程见 docs/RUNBOOK-interview.md。\n" % (
            spec["id"], "这是技术测试，不占正式发布编号，不是真人验收。" if spec["tech"] else "嘉宾、授权和素材未齐时保持待填。"),
        encoding="utf-8", newline="\n")
    print("created %s" % ep)
    return ep


def resolve_spec(args) -> dict:
    purpose = "test" if args.tech_test else (args.purpose or "production")
    if purpose not in ("production", "test"):
        raise SystemExit("purpose 只能是 production 或 test")
    topic = (args.topic or "").strip()
    if not topic:
        raise SystemExit("需要 --topic")
    if not args.slug:
        raise SystemExit("需要 --slug")
    if args.tech_test and args.episode is None:
        episode = 0
    elif args.episode is not None:
        episode = args.episode
    else:
        episode = next_release_number(REPO)
    return {
        "episode": episode,
        "slug": args.slug,
        "id": folder_id(episode, args.slug, purpose),
        "purpose": purpose,
        "topic": topic,
        "title": (args.title or "").strip() or topic,
        "city": (args.city or "成都").strip(),
        "tech": bool(args.tech_test),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug")
    parser.add_argument("--topic")
    parser.add_argument("--title")
    parser.add_argument("--city", default="成都")
    parser.add_argument("--episode", type=int)
    parser.add_argument("--purpose", choices=("production", "test"), default="production")
    parser.add_argument("--tech-test", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            spec = {"episode": 0, "slug": "techtest", "id": "ep00-techtest", "purpose": "test",
                    "topic": "技术测试", "title": "技术测试", "city": "成都", "tech": True}
            ep = create(Path(tmp), spec)
            text = (ep / "episode.yaml").read_text(encoding="utf-8")
            if "release_number" in text:
                raise SystemExit("test episode must not write release_number")
            if not (ep / "data" / "timeline.json").is_file():
                raise SystemExit("timeline missing")
        print("self-test ok")
        return 0
    spec = resolve_spec(args)
    create(SERIES, spec)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)
