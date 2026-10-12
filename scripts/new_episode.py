#!/usr/bin/env python3
"""Create one map-hub 口播 episode folder.

Folder: projects/map-hub/epNN-<slug>
  ep08-xihu
  ep12-xihu
  ep10-yuedu

The folder is the episode number plus the community pinyin. Category, layout, and the
CRM listing id stay in episode.yaml. New-home has no listing id: the 楼盘 name is --title.
The listing id is never part of the folder name, and it is not written into episode.json.
The user does not run this. The agent runs it after the user gives a listing id or a new-home 楼盘 name.
Omit --episode to take the next free series number.

usage:
  python scripts/new_episode.py --category rental --slug xihu --listing <id> --title 小区名
  python scripts/new_episode.py --category new-home --slug xipai --title 楼盘名
  python scripts/new_episode.py --category knowledge --slug yuedu --topic 选题
  python scripts/new_episode.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
SERIES = REPO / "projects" / "map-hub"
TEMPLATE = SERIES / "ep07-xihu" / "episode.json"
CATS = ("rental", "resale", "new-home", "knowledge")
LISTING_CATS = ("rental", "resale")
NAME = re.compile(r"^(?P<room>[\u4e00-\u9fff]+)_(?P<n>\d{1,2})\.(mp4|mov|MP4|MOV)$")
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
LAYOUT = re.compile(r"^[1-9]\d?b[1-9]\d?l$")
ID_RE = re.compile(r"^ep(?P<ep>\d{2})-(?P<slug>[a-z][a-z0-9]*(?:-[a-z0-9]+)*)$")
SLUG_BANNED = {"rental", "resale", "knowledge", "new", "home"}
DIRS = (
    "footage/raw", "footage/heygen", "voice", "heygen", "matte",
    "annotations/seeds", "data", "public", "out", "jobs", "consent",
)


def yq(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def episode_id(episode: int, slug: str) -> str:
    if not 1 <= episode <= 99:
        raise SystemExit("集数用两位，1–99")
    if not SLUG.fullmatch(slug or ""):
        raise SystemExit("楼盘拼音只用小写字母、数字和连字符，例如 xihu")
    parts = slug.split("-")
    if any(part in SLUG_BANNED or LAYOUT.fullmatch(part) or re.fullmatch(r"\d{4,}", part) for part in parts):
        raise SystemExit("目录名只留楼盘拼音，不写类型、户型或房源编号")
    if "new-home" in slug:
        raise SystemExit("目录名只留楼盘拼音，不写类型、户型或房源编号")
    return f"ep{episode:02d}-{slug}"


def split_id(episode_id_text: str) -> tuple[int, str]:
    m = ID_RE.fullmatch(episode_id_text or "")
    if not m:
        raise SystemExit("目录名要像 ep08-xihu")
    slug = m.group("slug")
    episode = int(m.group("ep"))
    built = episode_id(episode, slug)
    if built != episode_id_text:
        raise SystemExit(f"目录名应为 {built}")
    return episode, slug


def listing_tokens(ref: str) -> list[str]:
    text = (ref or "").strip().lower()
    found = [text] if text else []
    found += re.findall(r"[a-z0-9]{5,}", text)
    return found


def leaks_listing(folder: str, episode: int, ref: str) -> bool:
    padded = f"{episode:02d}"
    hay = folder.lower()
    for tok in listing_tokens(ref):
        if tok in {padded, f"ep{padded}"}:
            continue
        if tok and tok in hay:
            return True
    return False


def resolve_spec(a) -> dict:
    if a.id:
        episode, slug = split_id(a.id)
        if not a.category:
            raise SystemExit("目录名不含类型，请同时给 --category")
        if a.episode is not None and a.episode != episode:
            raise SystemExit("--episode 与 --id 不一致")
        if a.slug and a.slug != slug:
            raise SystemExit("--slug 与 --id 不一致")
        category = a.category
        layout = a.layout or ""
    else:
        if not a.category or not a.slug:
            nxt = next_episode()
            raise SystemExit(
                "建集由 Agent 执行。租赁/二手房给 --listing；新房给 --title 楼盘名，没有房源编号。\n"
                f"下一集序号是 {nxt}。例如：--category rental --slug xihu --listing <编号> --title 小区名"
            )
        episode = a.episode if a.episode is not None else next_episode()
        category, slug, layout = a.category, a.slug, a.layout or ""
    if category not in CATS:
        raise SystemExit("类型只能是 rental、resale、new-home、knowledge")
    if layout and not LAYOUT.fullmatch(layout):
        raise SystemExit("户型只写入 episode.yaml，形如 2b1l")
    folder = episode_id(episode, slug)
    listing = (a.listing or "").strip()
    topic = (a.topic or "").strip()
    title = (a.title or "").strip()
    if category in LISTING_CATS:
        if not listing:
            raise SystemExit("租赁和二手房要提供 --listing 房源编号")
        if topic:
            raise SystemExit("房源期不用 --topic")
        if leaks_listing(folder, episode, listing):
            raise SystemExit("房源编号不能出现在目录名里，只写入本期 episode.yaml")
    elif category == "new-home":
        if listing:
            raise SystemExit("新房没有房源编号，用 --title 写楼盘名")
        if topic:
            raise SystemExit("新房不用 --topic，楼盘名写在 --title")
        if not title:
            raise SystemExit("新房要提供 --title 楼盘名")
    else:
        if listing:
            raise SystemExit("知识和市场分析不绑房源编号，用 --topic")
        if not topic:
            raise SystemExit("知识和市场分析要提供 --topic 选题")
    return {
        "episode": episode,
        "category": category,
        "slug": slug,
        "layout": layout,
        "id": folder,
        "listing": listing,
        "topic": topic,
        "title": title,
        "city": a.city,
        "footage": a.footage,
    }


def next_episode() -> int:
    nums = []
    if SERIES.is_dir():
        for path in SERIES.glob("ep*"):
            m = re.match(r"ep(\d+)", path.name)
            if m:
                nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def blank_template(tpl: dict, spec: dict) -> dict:
    out = json.loads(json.dumps(tpl))
    out["id"] = spec["id"]
    out["episodeTag"] = f"EP.{spec['episode']:02d}"
    out["category"] = spec["category"]
    out["sampleData"] = True
    out["sampleTag"] = "示例数据"
    community = spec["title"]
    out["listing"] = {
        "name": community,
        "community": community,
        "layout": "",
        "area": None,
        "rent": None,
        "lnglat": None,
        "coord": "gcj02",
        "note": (
            "新房无房源编号。楼盘名已填，其余数字待资料回填。"
            if spec["category"] == "new-home"
            else "数字待本期房源查询回填。模板里的示例数字已清空。"
        ),
    }
    for poi in out.get("poiQueries") or []:
        for key in ("query", "pick", "label", "sub"):
            if key in poi:
                poi[key] = ""
    return out


def write_yaml(ep: Path, spec: dict) -> None:
    lines = [
        f"# episode.yaml — single source of truth for {spec['id']}. Edit this; grok reads it at every stage.",
        f"id: {spec['id']}",
        "series: map-hub",
        f"episode: {spec['episode']}",
        f"category: {spec['category']}        # rental | resale | new-home | knowledge",
        "listing:",
        f"  ref: {yq(spec['listing'])}        # 租赁/二手房 CRM 编号。新房留空。不进目录名、口播、字幕、画面",
        f"  community: {yq(spec['title'])}",
        f"  city: {yq(spec['city'])}",
        f"  layout_slug: {yq(spec['layout'])}   # 户型记在这里，不进目录名",
        "  sample_data: true          # true = 示例数据 (spoken once); false = live listing, follow rules/compliance",
        f"topic: {yq(spec['topic'])}          # knowledge / 市场分析选题；房源期留空",
        "footage:",
        "  # raw footage in footage/raw/, named 房间_序号.mp4 (see docs/FOOTAGE-SPEC.md). Muse fills rooms with no raw clip.",
        "  raw:",
    ]
    raw = spec.get("raw") or []
    lines += [f"    - {{file: {yq(n)}, room: {r}, n: {k}, use: auto}}" for n, r, k in raw] or ["    []"]
    lines += [
        "  muse: auto                 # auto = generate missing rooms/scenes with Muse; none = raw only",
        "presenter: cool-breeze       # shared profile assets/presenter/<name>/presenter.yaml",
        "# voice reference stays in voices/clone/ (read-only). This episode's generated wavs stay in voice/.",
        "# presenter_override:",
        "#   voice: {seed: 33, speed_oncam: 1.1}",
        "#   heygen: {look: casual}",
        "oncam_budget_s: 55",
        "render:",
        "  size: 1440x1080",
        "  fps: 30",
        "  lufs: -16",
        "  on_screen_notes: false     # brand strip only",
        "status: {intake: done}     # grok updates per stage: listing, pois, script, voice, muse, annotate, heygen, dewm43, matte, render, qa",
    ]
    (ep / "episode.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def copy_raw(ep: Path, footage: str | None) -> tuple[list, list]:
    raw, bad = [], []
    if not footage:
        return raw, bad
    for f in sorted(Path(footage).iterdir()):
        if not f.is_file():
            continue
        m = NAME.match(f.name)
        if m:
            shutil.copy2(f, ep / "footage" / "raw" / f.name)
            raw.append((f.name, m["room"], int(m["n"])))
        elif f.suffix.lower() in (".mp4", ".mov"):
            bad.append(f.name)
    return raw, bad


def create(root: Path, spec: dict, template: Path) -> Path:
    ep = root / spec["id"]
    if ep.exists():
        raise SystemExit(f"{ep} already exists — edit its episode.yaml instead")
    for d in DIRS:
        (ep / d).mkdir(parents=True)
    spec["raw"], bad = copy_raw(ep, spec.get("footage"))
    tpl = json.loads(template.read_text(encoding="utf-8"))
    (ep / "episode.json").write_text(
        json.dumps(blank_template(tpl, spec), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )
    write_yaml(ep, spec)
    if spec["category"] in LISTING_CATS:
        ref = {
            "listing_id": spec["listing"],
            "category": spec["category"],
            "community": spec["title"],
            "city": spec["city"],
            "layout_slug": spec["layout"],
            "source": "user",
        }
        (ep / "data" / "listing_ref.json").write_text(
            json.dumps(ref, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n",
        )
        id_line = "房源编号只在 `episode.yaml` 的 `listing.ref` 和 `data/listing_ref.json`。\n"
    elif spec["category"] == "new-home":
        project = {
            "category": "new-home",
            "project_name": spec["title"],
            "city": spec["city"],
            "slug": spec["slug"],
            "listing_id": None,
            "source": "user",
        }
        (ep / "data" / "project.json").write_text(
            json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n",
        )
        id_line = "新房没有房源编号。楼盘名在 `listing.community` 和 `data/project.json`。\n"
    else:
        topic = {"category": "knowledge", "topic": spec["topic"], "slug": spec["slug"], "source": "user"}
        (ep / "data" / "topic.json").write_text(
            json.dumps(topic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n",
        )
        id_line = "本期是选题，没有房源编号。选题在 `topic` 和 `data/topic.json`。\n"
    (ep / "consent" / "README.md").write_text(
        "# 本期授权\n\n业主委托或本期单独授权放这里。声音克隆参考音在 `voices/clone/`，不要复制进来。\n",
        encoding="utf-8", newline="\n",
    )
    (ep / "README.md").write_text(
        f"# {spec['id']}\n\n"
        f"map-hub 口播（{spec['category']}）。依据是 `episode.yaml`。\n"
        f"{id_line}"
        f"共用声音与数字人：`voices/clone/`、`assets/presenter/cool-breeze/`。\n"
        f"做片：对 grok 说 `做视频 {spec['id']}`，或运行 `scripts\\make-video.cmd {spec['id']}`。\n",
        encoding="utf-8", newline="\n",
    )
    print(f"created {ep}  raw clips: {len(spec['raw'])}")
    if bad:
        print("NOT copied (bad names, rename to 房间_序号.mp4):", ", ".join(bad))
    print(f"next:  做视频 {spec['id']}   |   scripts\\make-video.cmd {spec['id']}")
    return ep


def self_test() -> None:
    assert episode_id(8, "xihu") == "ep08-xihu"
    assert episode_id(12, "xihu") == "ep12-xihu"
    assert split_id("ep07-xihu") == (7, "xihu")
    assert leaks_listing("ep08-id99887766", 8, "99887766")
    assert not leaks_listing("ep08-xihu", 8, "99887766")
    for bad in ("rental-xihu", "xihu-2b1l", "new-home-xipai"):
        try:
            episode_id(8, bad)
        except SystemExit:
            pass
        else:
            raise SystemExit(f"slug should be refused: {bad}")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        spec = {
            "episode": 8, "category": "rental", "slug": "xihu", "layout": "2b1l",
            "id": "ep08-xihu", "listing": "99887766", "topic": "",
            "title": "西湖文化广场", "city": "杭州", "footage": None,
        }
        ep = create(root, spec, TEMPLATE)
        yaml_text = (ep / "episode.yaml").read_text(encoding="utf-8")
        episode_text = (ep / "episode.json").read_text(encoding="utf-8")
        assert "99887766" in yaml_text
        assert "category: rental" in yaml_text
        assert 'layout_slug: "2b1l"' in yaml_text
        assert "99887766" in (ep / "data" / "listing_ref.json").read_text(encoding="utf-8")
        assert "99887766" not in episode_text
        assert ep.name == "ep08-xihu"
        assert "2b1l" not in ep.name
        assert "rental" not in ep.name
        assert "西湖文化广场站" not in episode_text
        assert '"rent": null' in episode_text
        know = {
            "episode": 10, "category": "knowledge", "slug": "yuedu", "layout": "",
            "id": "ep10-yuedu", "listing": "", "topic": "月度租金怎么看",
            "title": "", "city": "杭州", "footage": None,
        }
        kep = create(root, know, TEMPLATE)
        assert (kep / "data" / "topic.json").is_file()
        assert not (kep / "data" / "listing_ref.json").exists()
        home = {
            "episode": 11, "category": "new-home", "slug": "xipai", "layout": "",
            "id": "ep11-xipai", "listing": "", "topic": "",
            "title": "武侯西派御府", "city": "成都", "footage": None,
        }
        hep = create(root, home, TEMPLATE)
        project = json.loads((hep / "data" / "project.json").read_text(encoding="utf-8"))
        assert project["project_name"] == "武侯西派御府"
        assert project["listing_id"] is None
        assert hep.name == "ep11-xipai"
        assert not (hep / "data" / "listing_ref.json").exists()
        refused = argparse.Namespace(
            id="", episode=11, category="new-home", slug="xipai", layout="",
            listing="123456", topic="", title="武侯西派御府", city="成都", footage=None,
        )
        try:
            resolve_spec(refused)
        except SystemExit as exc:
            assert "新房没有房源编号" in str(exc)
        else:
            raise SystemExit("new-home listing id should be refused")
    print("self-test ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", default="", help="optional full folder, e.g. ep08-xihu; still pass --category")
    ap.add_argument("--episode", type=int, help="series episode number; omit to use the next free number")
    ap.add_argument("--category", choices=CATS)
    ap.add_argument("--slug", default="", help="community pinyin, e.g. xihu")
    ap.add_argument("--layout", default="", help="optional layout stored in episode.yaml only, e.g. 2b1l")
    ap.add_argument("--listing", default="", help="CRM listing id; required for rental and resale; never for new-home")
    ap.add_argument("--topic", default="", help="knowledge / market topic; required for knowledge")
    ap.add_argument("--title", default="", help="Chinese community or 楼盘 name; required for new-home")
    ap.add_argument("--city", default="杭州")
    ap.add_argument("--footage", help="folder of raw clips named 房间_序号.mp4")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    spec = resolve_spec(a)
    create(SERIES, spec, TEMPLATE)


if __name__ == "__main__":
    main()
