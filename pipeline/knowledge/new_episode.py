#!/usr/bin/env python3
"""Create one knowledge-series 口播 episode folder.

Folder: projects/knowledge/epNN-<slug> (own numbering, independent from map-hub; both start at ep01).
Knowledge episodes have NO listing id, no map/POI files — only a topic. Default city 成都.
The user does not run this; the agent runs it after the user gives a 选题. Omit --episode for the next free number.

usage:
  python pipeline/knowledge/new_episode.py --slug gongjijin --topic 公积金新政解读 [--title 片名] [--city 成都]
  python pipeline/knowledge/new_episode.py --self-test
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[2]
SERIES = REPO / "projects" / "knowledge"
DIRS = (
    "script", "broll/flova", "broll/muse", "broll/screens",
    "voice", "heygen", "matte", "out", "data", "consent", "jobs",
    "footage/heygen", "public",
)

# Reuse the map-hub slug/id rules (single source: scripts/new_episode.py) without importing its CLI.
_spec = importlib.util.spec_from_file_location("maphub_new_episode", REPO / "scripts" / "new_episode.py")
_maphub_new = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_maphub_new)
episode_id, split_id = _maphub_new.episode_id, _maphub_new.split_id


def yq(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def next_episode(root: Path = SERIES) -> int:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from pipeline.common.episodes import next_release_number
    # A custom root remains useful for isolated self-tests.
    repo = REPO if root == SERIES else root.parent.parent
    return next_release_number(repo)


def resolve_spec(a) -> dict:
    if a.id:
        episode, slug = split_id(a.id)
        if a.episode is not None and a.episode != episode:
            raise SystemExit("--episode 与 --id 不一致")
        if a.slug and a.slug != slug:
            raise SystemExit("--slug 与 --id 不一致")
    else:
        if not a.slug or not a.topic:
            raise SystemExit(
                "建集由 Agent 执行。knowledge 期给 --slug 拼音 + --topic 选题（没有房源编号）。\n"
                f"下一集序号是 {next_episode()}。例如：--slug gongjijin --topic 公积金新政解读"
            )
        episode, slug = (a.episode if a.episode is not None else next_episode()), a.slug
    topic = (a.topic or "").strip()
    if not topic:
        raise SystemExit("knowledge 期要提供 --topic 选题")
    return {
        "episode": episode,
        "slug": slug,
        "id": episode_id(episode, slug),
        "topic": topic,
        "title": (a.title or "").strip() or topic,
        "city": (a.city or "成都").strip(),
    }


def write_yaml(ep: Path, spec: dict) -> None:
    lines = [
        f"# episode.yaml — single source of truth for {spec['id']} (knowledge series). Edit this; the agent reads it at every stage.",
        f"id: {spec['id']}",
        "series: knowledge",
        "purpose: production",
        f"release_number: {spec['episode']}",
        f"episode: {spec['episode']}",
        "category: knowledge",
        f"topic: {yq(spec['topic'])}",
        f"title: {yq(spec['title'])}",
        f"city: {yq(spec['city'])}",
        "map: false               # knowledge 期没有地图 / POI / 房源步骤",
        "presenter: cool-breeze   # shared profile assets/presenter/<name>/presenter.yaml",
        "# presenter_override:",
        "#   voice: {tempo: 1.15}",
        "#   heygen: {look: casual}",
        "oncam_budget_s: 55       # HeyGen 免费版 60s 上限，我们的预算 55s（露脸段合计）",
        "total_target_s: 85       # 全片目标 80–90s",
        "script_md: script/script_v1.md     # 人读稿（段与 segments 一一对应）",
        "research: script/research.md       # 事实来源清单；画面/口播的数字必须能回查到它",
        "voice_defaults:          # mirrors assets/presenter/cool-breeze/presenter.yaml voice:",
        "  engine: flova_minimax",
        "  model: speech-2.8-hd",
        "  voice: Gentle_Youth",
        "  tempo: 1.1",
        "  mode: passage",
        "heygen:",
        '  look: "Professional in suit on sofa"   # 用户已保存的 look，按名字选；找不到就停',
        "  oncam_max_s: 55",
        "render:",
        "  size: 1440x1080",
        "  fps: 30",
        "  lufs: -16",
        "  on_screen_notes: false     # brand strip only",
        "broll_dirs: {flova: broll/flova, muse: broll/muse, screens: broll/screens}",
        "# segments: type oncam = 露脸（HeyGen 数字人）；voiceover = 画外音 + b-roll。",
        "# text 是口播原文（TTS 逐字读）；不要用 —— 或 --（会被读出来），用 ，或 ……。",
        "# broll: ref = broll/<kind>/<ref>.mp4|.png|.jpg；kind ∈ screens(真实截图) / muse(Muse视频) / flova(生图兜底)。",
        "# 下面是占位三段，写稿时替换（脚本规则见 docs/RUNBOOK-knowledge-koubo.md）。",
        "segments:",
        "  - n: 1",
        "    id: S01",
        "    type: oncam",
        "    name: 开场钩子",
        "    est_s: 8",
        '    text: "待填：一句话钩子，点出本期选题。"',
        "  - n: 2",
        "    id: S02",
        "    type: voiceover",
        "    name: 正文",
        "    est_s: 12",
        '    text: "待填：正文，事实必须能在 script/research.md 里查到来源。"',
        "    broll:",
        "      - {ref: B01, kind: flova, desc: 占位：正文配图}",
        "  - n: 3",
        "    id: S03",
        "    type: oncam",
        "    name: 结尾",
        "    est_s: 8",
        "    end: true",
        '    text: "待填：总结 + 关注引导。"',
        "status: {intake: done}   # agent updates per stage: script, voice, broll, heygen, dewm43, matte, compose, render, qa",
    ]
    (ep / "episode.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def create(root: Path, spec: dict) -> Path:
    ep = root / spec["id"]
    if ep.exists():
        raise SystemExit(f"{ep} already exists — edit its episode.yaml instead")
    for d in DIRS:
        (ep / d).mkdir(parents=True)
    write_yaml(ep, spec)
    episode_json = {
        "id": spec["id"],
        "series": "knowledge",
        "channel": "@贝壳-TV",
        "episodeTag": f"EP.{spec['episode']:02d}",
        "format": {"width": 1440, "height": 1080, "fps": 30},
        "category": "knowledge",
        "title": spec["title"],
        "topic": spec["topic"],
        "city": spec["city"],
        "sampleData": False,
        "sampleTag": "",
        "onScreenNotes": False,
    }
    (ep / "episode.json").write_text(
        json.dumps(episode_json, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    topic = {"category": "knowledge", "series": "knowledge", "topic": spec["topic"],
             "slug": spec["slug"], "city": spec["city"], "source": "user"}
    (ep / "data" / "topic.json").write_text(
        json.dumps(topic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (ep / "consent" / "README.md").write_text(
        "# 本期授权\n\n本期单独授权放这里。声音克隆参考音在 `voices/clone/`，不要复制进来。\n",
        encoding="utf-8", newline="\n")
    (ep / "script" / "research.md").write_text(
        f"# {spec['id']} 资料汇总（{spec['topic']}）\n\n"
        "每条事实给出来源链接与发布日期；口播和画面里的数字必须能回查到本文件。查不到的不要写进稿。\n",
        encoding="utf-8", newline="\n")
    (ep / "README.md").write_text(
        f"# {spec['id']}\n\n"
        "knowledge 口播系列（知识类，无地图/房源步骤）。依据是 `episode.yaml`（segments 列表）。\n"
        "本期是选题，没有房源编号。选题在 `topic` 和 `data/topic.json`；事实来源在 `script/research.md`。\n"
        "共用声音与数字人：`voices/clone/`、`assets/presenter/cool-breeze/`。\n"
        f"做片：对 Agent 说 `做视频 {spec['id']}`（按 series 路由到 knowledge 流水线），或运行\n"
        f"`scripts\\make-knowledge-video.cmd {spec['id']}`（先 `--check` 干跑）。\n"
        "流程见 `docs/RUNBOOK-knowledge-koubo.md`。\n",
        encoding="utf-8", newline="\n")
    print(f"created {ep}")
    print(f"next:  写 episode.yaml segments + script/research.md，然后 scripts\\make-knowledge-video.cmd {spec['id']} --check")
    return ep


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        spec = {"episode": 1, "slug": "gongjijin", "id": "ep01-gongjijin",
                "topic": "公积金新政解读", "title": "公积金新政解读", "city": "成都"}
        ep = create(root, spec)
        assert ep.name == "ep01-gongjijin"
        yaml_text = (ep / "episode.yaml").read_text(encoding="utf-8")
        assert "series: knowledge" in yaml_text and "segments:" in yaml_text
        assert "成都" in yaml_text
        assert not (ep / "data" / "listing_ref.json").exists()
        for d in DIRS:
            assert (ep / d).is_dir(), d
        data = json.loads((ep / "episode.json").read_text(encoding="utf-8"))
        assert data["series"] == "knowledge" and data["city"] == "成都"
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import episode as kepi
        with patch_series(kepi, root):
            _ep, cfg, segments = kepi.load_episode(ep)
            assert len(segments) == 3 and segments[1]["type"] == "voiceover"
        try:
            resolve_spec(argparse.Namespace(id="", episode=None, slug="x", topic="", title="", city="成都"))
        except SystemExit:
            pass
        else:
            raise SystemExit("missing --topic should be refused")
        try:
            resolve_spec(argparse.Namespace(id="", episode=None, slug="rental-x", topic="t", title="", city="成都"))
        except SystemExit:
            pass
        else:
            raise SystemExit("banned slug part should be refused")
    print("self-test ok")


def patch_series(kepi, root):
    import unittest.mock
    return unittest.mock.patch.object(kepi, "SERIES", root)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", default="", help="optional full folder, e.g. ep02-gongjijin")
    ap.add_argument("--episode", type=int, help="series episode number; omit for the next free number")
    ap.add_argument("--slug", default="", help="topic pinyin, e.g. gongjijin")
    ap.add_argument("--topic", default="", help="选题（必填）")
    ap.add_argument("--title", default="", help="片名；默认同选题")
    ap.add_argument("--city", default="成都")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    create(SERIES, resolve_spec(a))


if __name__ == "__main__":
    main()

