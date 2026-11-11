#!/usr/bin/env python3
"""小ONE会客厅编排。check / --check 不启动抠像、不调用付费服务、不生成数字人。

步骤：probe → sync → transcript → edit → research → matte → compose → resolve → check → render
渲染先做本期检查，通过后再 stage。测试期不能写入 out/release。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from pipeline.common.rendering import atomic_output  # noqa: E402
from pipeline.common.workspace import stage_episode  # noqa: E402
import check_episode  # noqa: E402
import editlist  # noqa: E402
import episode as epi  # noqa: E402
import matte_plan  # noqa: E402
import probe as probe_mod  # noqa: E402
import research as research_mod  # noqa: E402
import resolve_export  # noqa: E402
import sync as sync_mod  # noqa: E402
import timeline as timeline_mod  # noqa: E402
from pipeline.interview import production
import transcript as transcript_mod  # noqa: E402

STEPS = ("probe", "sync", "transcript", "edit", "research", "matte", "compose", "resolve", "check", "render")
COMPOSITION = "InterviewLounge"


def _dump(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def step_probe(ep, check):
    if check:
        print("probe: ffprobe 只读登记，不改 raw")
    report = probe_mod.run_probe(ep, write=not check)
    print("probe completed=%s pending=%s" % (report["completed"], ",".join(report["pending"]) or "-"))
    return 0 if check or report['completed'] else 3


def step_sync(ep, cfg, check):
    payload = production.sync_ready(ep, cfg)
    print("sync:", json.dumps(payload, ensure_ascii=False))
    if not check:
        _dump(ep / "data/sync.json", payload)
    return 0 if check or payload["completed"] else 3

def step_transcript(ep, check):
    roles = {item["id"]: item.get("role") for item in probe_mod.load_sources(ep)}
    loaded = transcript_mod.load_corrected(ep / "transcript" / "corrected.json", roles)
    if not check:
        _dump(ep / "data" / "transcript_status.json", {k: loaded[k] for k in ("status", "completed", "fixture", "source") if k in loaded})
    if check:
        print("transcript: 不调用 ASR，不根据提纲生成字幕")
    print("transcript status=%s" % loaded["status"])
    return 0 if check or loaded["spans"] else 3


def step_edit(ep, check):
    decisions = editlist.load_decisions(ep / "edit" / "decisions.json")
    print("edit status=%s segments=%d" % (decisions["status"], len(decisions["segments"])))
    if check:
        print("edit: 未确认的清单不会进入抠像")
    return 0 if check or (decisions["confirmed"] and decisions["segments"]) else 3


def step_research(ep, check):
    source = ep / "research" / "allowed.json"
    if not source.is_file():
        print("research: 没有 research/allowed.json，不取数，不推断")
        return 0
    if check:
        print("research: 将整理本地导入，不访问网络")
        return 0
    pack = research_mod.import_file(source, ep / "data" / "research_pack.json")
    print("research cards=%d checklist=%d" % (len(pack["cards"]), len(pack["checklist"])))
    return 0


def step_matte(ep, cfg, check):
    if cfg["render"]["background"] != "virtual":
        print("matte: 当前模式不需要透明人物")
        return 0
    decisions = editlist.load_decisions(ep / "edit/decisions.json")
    if check:
        print("matte: 仅检查计划，不启动 GPU")
        return 0
    if not decisions["confirmed"] or not decisions["segments"]:
        print("matte: 需要已确认剪辑")
        return 3
    result = production.run_matte(ep, cfg, decisions)
    print("matte completed:", len(result))
    return 0

def step_compose(ep, cfg, check):
    if check:
        print("compose: 将按校正转录重映射字幕，不读取采访提纲")
        return 0
    decisions = editlist.load_decisions(ep / "edit" / "decisions.json")
    roles = {item["id"]: item.get("role") for item in probe_mod.load_sources(ep)}
    loaded = transcript_mod.load_corrected(ep / "transcript" / "corrected.json", roles)
    pack_path = ep / "data" / "research_pack.json"
    research = json.loads(pack_path.read_text(encoding="utf-8-sig")) if pack_path.is_file() else {"cards": [], "questions": [], "checklist": []}
    timeline_mod.write_timeline(ep, cfg, decisions, loaded["spans"], research)
    brands = REPO / "templates" / "interview" / "brands.json"
    social = REPO / "templates" / "interview" / "social.json"
    if brands.is_file():
        (ep / "data" / "brands.json").write_text(brands.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    if social.is_file():
        (ep / "data" / "social.json").write_text(social.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    root_episode = ep / "episode.json"
    if root_episode.is_file():
        (ep / "data" / "episode.json").write_text(root_episode.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    print("compose: data/timeline.json")
    return 0


def step_resolve(ep, check, strict):
    if check:
        print("resolve: 将导出实际媒体交接包，不操作达芬奇 GUI")
        return 0
    from pipeline.common.voice_config import read_yaml
    cfg = read_yaml(ep / "episode.yaml")
    result = production.export_resolve(ep, cfg)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["completed"] else 3

def step_check(ep, cfg, draft, check):
    payload = check_episode.report(ep, cfg, draft or check)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["pass"] else 1


def out_target(ep, cfg, draft, still, platform, ver):
    if still is not None:
        return ep / "out" / "drafts" / ver / ("still_f%d.png" % still)
    if draft or cfg.get("purpose") == "test":
        return ep / "out" / "drafts" / ver / ("draft_%s.mp4" % COMPOSITION)
    return ep / "out" / "release" / ("%s_%s.mp4" % (ep.name, platform))


def step_render(ep, cfg, draft, still, platform, ver, background, concurrency, check):
    if cfg.get("purpose") == "test" and not draft:
        print("测试工程不写入 out/release。加 --draft 只渲染技术样片。")
        return 2
    if background and background != cfg["render"]["background"]:
        raise ValueError("先修改 render.background 并重新 compose，再渲染对应背景")
    payload = check_episode.report(ep, cfg, draft)
    if not payload["pass"]:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    target = out_target(ep, cfg, draft, still, platform, ver)
    props = {"platform": platform}
    if background:
        props["background"] = background
    props_path = ep / "jobs" / "render_props.json"
    _dump(props_path, props)
    if check:
        print("render: 检查已通过清单。接下来才会 stage。技术样片不是真人验收。")
        print("target", target)
        return 0
    work = stage_episode(ep)
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        print("npx is required")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    argv = [npx, "remotion", "still" if still is not None else "render", "src/index.ts", COMPOSITION, str(target),
            "--props=" + str(props_path)]
    argv.append("--gl=angle")
    if still is not None:
        argv.append("--frame=%d" % still)
    else:
        argv.append("--concurrency=%d" % concurrency)
    print("+", " ".join(argv))
    try:
        with atomic_output(target) as pending:
            argv[5] = str(pending)
            subprocess.run(argv, cwd=work, check=True)
    except subprocess.CalledProcessError as exc:
        print("render failed exit %s" % exc.returncode)
        return exc.returncode or 1
    print(target)
    print("技术测试渲染完成。真人抠像、口型同步、演播室真实感仍是待实拍验证。")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode")
    parser.add_argument("--step", choices=("all",) + STEPS, default="all")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--still", type=int, default=None)
    parser.add_argument("--platform", choices=("douyin", "shipinhao"), default="shipinhao")
    parser.add_argument("--ver", default="techtest")
    parser.add_argument("--background", choices=("live", "virtual", "placeholder"))
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args(argv)
    ep, cfg = epi.load_episode(args.episode)
    steps = STEPS if args.step == "all" else (args.step,)
    for name in steps:
        print("=== %s ===" % name)
        if name == "probe":
            code = step_probe(ep, args.check)
        elif name == "sync":
            code = step_sync(ep, cfg, args.check)
        elif name == "transcript":
            code = step_transcript(ep, args.check)
        elif name == "edit":
            code = step_edit(ep, args.check)
        elif name == "research":
            code = step_research(ep, args.check)
        elif name == "matte":
            code = step_matte(ep, cfg, args.check)
        elif name == "compose":
            code = step_compose(ep, cfg, args.check)
        elif name == "resolve":
            code = step_resolve(ep, args.check, strict=args.step == "resolve")
        elif name == "check":
            code = step_check(ep, cfg, args.draft, args.check)
        else:
            code = step_render(ep, cfg, args.draft, args.still, args.platform, args.ver, args.background, args.concurrency, args.check)
        if code != 0:
            print("step %s failed exit %s" % (name, code))
            return code
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)
