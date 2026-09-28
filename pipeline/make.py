"""One-sentence → video fixed workflow.

Usage:
  python pipeline/make.py "<一句话>" [--style qiuzhi|mediastorm] [--ratio 4x3]
         [--category rental|resale|new-home] [--mock] [--force] [--until STAGE]
         [--project projects/rental/<id>]   # resume / re-run on an existing project
         [--answer key=value ...]          # fill brief.answers / brief fields

Stages (idempotent; skip if outputs exist unless --force):
  0 parse            → brief.json
  1 listing:fetch    → listing.json + raw/listing/*
  2 listing:wall     → wall.json + raw/wall/*
  3 map:fetch        → map/geo.json + satellite_4x3.jpg + static.png + pois.json
  4 assets:import    → assets/manifest.json (+ seed warehouse stock)
  5 script           → project.json + shots.json  (agent should rewrite; fallback provided)
  6 tts              → audio/seg_*.wav + audio/segments.json
  7 check            → hard gate (extended)
  8 render           → output/<id>_4x3.mp4

When a stage needs the user, it exits 3 and prints the open questions. The agent asks the user,
writes answers back via --answer / by editing brief.json, then re-runs the same command.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reel_common import PROJECTS_DIR, REPO_ROOT, load_json, resolve_project_dir, save_json, setup_console  # noqa: E402
from stages import assets as stage_assets  # noqa: E402
from stages import brief as stage_brief  # noqa: E402
from stages import listing as stage_listing  # noqa: E402
from stages import map_fetch as stage_map  # noqa: E402
from stages import script_stage as stage_script  # noqa: E402
from stages import wall as stage_wall  # noqa: E402
from stages.common import EXIT_NEED_INPUT, NeedInput, load_brief, save_brief  # noqa: E402

STAGES = [
    ("parse", "0 parse"),
    ("listing:fetch", "1 listing:fetch"),
    ("listing:wall", "2 listing:wall"),
    ("map:fetch", "3 map:fetch"),
    ("assets:import", "4 assets:import"),
    ("script", "5 script"),
    ("tts", "6 tts"),
    ("check", "7 check"),
    ("render", "8 render"),
]


def _slugify(text: str) -> str:
    # Keep pinyin-ish latin + digits; fall back to hash via brief.
    s = re.sub(r"[^a-zA-Z0-9\-]+", "-", text.lower()).strip("-")
    return (s[:40] or "auto").strip("-")


def _apply_answers(brief: dict, answers: list[str]) -> None:
    confirmed = set((brief.get("answers") or {}).get("_confirmed", []))
    for raw in answers:
        if "=" not in raw:
            continue
        k, v = raw.split("=", 1)
        k, v = k.strip(), v.strip()
        if k in ("category", "style", "ratio"):
            brief[k] = v
        elif k.startswith("listing."):
            cur = brief.setdefault("listing", {})
            sub = k.split(".", 1)[1]
            if sub == "filters" or sub.endswith("]"):
                continue
            if sub in ("rooms",):
                cur.setdefault("filters", {})[sub] = [int(x) for x in v.split(",") if x]
            elif sub in ("monthly_rent_yuan", "area_sqm"):
                a, b = (v.split(":") + [None])[:2]
                cur.setdefault("filters", {})[sub] = {"min": float(a) if a else None, "max": float(b) if b else None}
            else:
                cur[sub] = v
        elif k.startswith("voice."):
            brief.setdefault("voice", {})[k.split(".", 1)[1]] = v
        elif k.startswith("flova."):
            brief.setdefault("flova", {})[k.split(".", 1)[1]] = (v.lower() in ("1", "true", "yes") if "allow" in k else v)
            if "allow" in k and brief["flova"].get("allowed"):
                confirmed.add("flova")
        elif k.startswith("map."):
            brief.setdefault("map", {})[k.split(".", 1)[1]] = v
        elif k == "platform":
            brief["platform"] = [x for x in v.split(",") if x]
        elif k.startswith("confirm."):
            confirmed.add(k.split(".", 1)[1])
        else:
            brief.setdefault("answers", {})[k] = v
            confirmed.add(k)
    brief.setdefault("answers", {})["_confirmed"] = sorted(confirmed)


def _ensure_project(brief: dict, category: str) -> Path:
    if brief.get("project_id"):
        d = PROJECTS_DIR / category / brief["project_id"]
        d.mkdir(parents=True, exist_ok=True)
        return d
    date = dt.date.today().isoformat()
    community = (brief.get("listing") or {}).get("community_keyword") or "auto"
    slug = f"{date}-{_slugify(community)}-{brief['slug'].split('-')[-1]}"
    brief["project_id"] = slug
    d = PROJECTS_DIR / category / slug
    for sub in ("raw", "canva", "audio", "consent", "output", "map", "assets"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d


def _run_tts(project_dir: Path, brief: dict, force: bool) -> dict:
    from tts import edge_tts_stage
    return edge_tts_stage.run(project_dir, brief=brief, force=force)


def _run_check(project_dir: Path) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "check"))
    import check as checker
    report = checker.run(project_dir)
    checker.print_report(project_dir, report)
    if report.failed:
        raise SystemExit(1)
    return {"pass": True}


def _run_render(project_dir: Path, ratio: str) -> dict:
    import render as renderer
    rc = renderer.main([str(project_dir), "--ratio", ratio])
    if rc != 0:
        raise SystemExit(rc)
    return {"ok": True}


def main(argv=None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="一句话成片")
    ap.add_argument("sentence", nargs="?", help="一句话需求；与 --project 二选一")
    ap.add_argument("--project", help="已有项目目录，续跑 / 重跑")
    ap.add_argument("--style", choices=["qiuzhi", "mediastorm"])
    ap.add_argument("--ratio", choices=["4x3", "3x4", "9x16"], default="4x3")
    ap.add_argument("--category", choices=["rental", "resale", "new-home"])
    ap.add_argument("--mock", action="store_true", help="强制用虚构 listing fixture（不打 CRM）")
    ap.add_argument("--force", action="store_true", help="忽略已有产物，整条流水线重跑")
    ap.add_argument("--until", choices=[s for s, _ in STAGES], help="跑到该阶段为止（含）")
    ap.add_argument("--only", choices=[s for s, _ in STAGES], help="只跑这一阶段")
    ap.add_argument("--answer", action="append", default=[], help="key=value，写入 brief；可重复")
    ap.add_argument("--voice", choices=["edge", "qwen", "own"], help="配音方式（写入 brief.voice.mode）")
    args = ap.parse_args(argv)

    if args.project:
        project_dir = resolve_project_dir(args.project)
        brief = load_brief(project_dir) if (project_dir / "brief.json").exists() else stage_brief.parse_sentence(args.sentence or "")
        if args.sentence and not brief.get("sentence"):
            brief["sentence"] = args.sentence
    else:
        if not args.sentence:
            print("用法：npm run make -- \"一句话\" [--style mediastorm] [--mock]", file=sys.stderr)
            return 2
        brief = stage_brief.parse_sentence(args.sentence)

    if args.style:
        brief["style"] = args.style
    if args.category:
        brief["category"] = args.category
    if args.ratio:
        brief["ratio"] = args.ratio
    if args.mock:
        brief.setdefault("listing", {})["source"] = "mock"
    if args.voice:
        brief.setdefault("voice", {})["mode"] = args.voice
    _apply_answers(brief, args.answer)

    # Defaults for a headless sample run: if --mock, pre-confirm the manual questions.
    if args.mock:
        brief["style"] = brief.get("style") or "mediastorm"
        brief["category"] = brief.get("category") or "rental"
        brief.setdefault("voice", {})["mode"] = brief.get("voice", {}).get("mode") or "edge"
        brief["platform"] = brief.get("platform") or ["douyin", "channels"]
        lst = brief.setdefault("listing", {})
        lst["community_keyword"] = lst.get("community_keyword") or "示例云栖苑"
        lst["pick"] = lst.get("pick") or "MOCK-RENTAL-20260928-001"
        brief.setdefault("answers", {})["_confirmed"] = sorted(set(brief["answers"].get("_confirmed", [])) | {
            "consent.owner", "disclosures", "flova", "photos.exclude", "listing.target", "listing.pick",
            "style", "voice.mode", "platform", "category",
        })

    category = brief.get("category") or "rental"
    project_dir = _ensure_project(brief, category)
    brief["questions"] = stage_brief.open_questions(brief, project_dir)
    save_brief(project_dir, brief)

    print(f"▶ 项目：{project_dir.relative_to(REPO_ROOT).as_posix()}")
    print(f"  句子：{brief.get('sentence', '')}")
    print(f"  分类：{category}  风格：{brief.get('style')}  画幅：{brief.get('ratio')}")

    # Gate: if still missing critical answers and not --mock, stop before stages that need them.
    blocking = [q for q in brief["questions"] if q["key"] in ("category", "listing.target", "style", "voice.mode")]
    if blocking and not args.mock and not args.only:
        print("\n⏸ 还缺以下信息，请先问用户，再用 --answer key=value 回填后重跑：")
        for q in brief["questions"]:
            print(f"  · [{q['blocks']}] {q['key']}: {q['q']}")
        return EXIT_NEED_INPUT

    runners = {
        "parse": lambda: {"ok": True, "questions": len(brief["questions"])},
        "listing:fetch": lambda: stage_listing.run(project_dir, force=args.force),
        "listing:wall": lambda: stage_wall.run(project_dir, force=args.force),
        "map:fetch": lambda: stage_map.run(project_dir, force=args.force),
        "assets:import": lambda: stage_assets.run(project_dir, force=args.force),
        "script": lambda: stage_script.run(project_dir, force=args.force),
        "tts": lambda: _run_tts(project_dir, brief, force=args.force),
        "check": lambda: _run_check(project_dir),
        "render": lambda: _run_render(project_dir, brief.get("ratio") or "4x3"),
    }

    order = [s for s, _ in STAGES]
    if args.only:
        order = [args.only]
    elif args.until:
        order = order[: order.index(args.until) + 1]

    for name in order:
        label = dict(STAGES)[name]
        print(f"\n—— {label} ——")
        try:
            result = runners[name]()
        except NeedInput as e:
            brief["questions"] = e.questions
            save_brief(project_dir, brief)
            print("⏸ 需要用户确认：")
            for q in e.questions:
                print(f"  · {q['key']}: {q['q']}")
            return EXIT_NEED_INPUT
        except SystemExit as e:
            return int(e.code) if isinstance(e.code, int) else 1
        print(f"   {result}")
        if name == "render":
            break

    print(f"\n✅ 完成。项目目录：{project_dir.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
