#!/usr/bin/env python3
"""Create one listing (房源讲解) episode folder: rental, resale or new-home.

Folder: projects/listing/epNN-<slug>
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
  python scripts/new_episode.py --category new-home --slug bangtai --title 楼盘名 --footage D:\\DCIM\\DJI_001
  python scripts/new_episode.py --self-test
knowledge is forwarded to pipeline/knowledge/new_episode.py.

Only the folders every episode needs are created (footage/raw, data, consent, the category's
footage/assets/* and, for new-home, sources/docs). work/, out/, voice/, heygen/, public/, annotations/ and
footage/shots|heygen|matte|restored are created by the tool that first writes them. No data/project.json.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
SERIES = REPO / "projects" / "listing"
TEMPLATE = REPO / "templates/listing/episode.json"
CATS = ("rental", "resale", "new-home", "knowledge")
LISTING_CATS = ("rental", "resale")
EPISODE_CATS = ("rental", "resale", "new-home")
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".mts"}
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
LAYOUT = re.compile(r"^[1-9]\d?b[1-9]\d?l$")
ID_RE = re.compile(r"^ep(?P<ep>\d{2})-(?P<slug>[a-z][a-z0-9]*(?:-[a-z0-9]+)*)$")
SLUG_BANNED = {"rental", "resale", "knowledge", "new", "home"}
BASE_DIRS = ("footage/raw", "data", "consent")
CATEGORY_DIRS = {
    "rental": ("footage/assets/floorplan", "footage/assets/photos", "footage/assets/map"),
    "resale": ("footage/assets/floorplan", "footage/assets/photos", "footage/assets/map"),
    "new-home": ("footage/assets/brochure", "footage/assets/renderings", "footage/assets/sandtable",
                 "footage/assets/map", "sources/docs"),
}
ASSET_README = {
    "rental": ("- `floorplan/`：CRM 户型图原图、清理版、透明抠图、README\n"
               "- `photos/`：采用的 Muse 增强图 `<room>_muse.png` + `sources.md`\n"
               "- `map/`：采用的地图底图、POI 图片\n"),
    "new-home": ("- `brochure/`：楼书页、户型页（开发商资料，注明来源）\n"
                 "- `renderings/`：效果图、鸟瞰图（画面须标注“效果图”）\n"
                 "- `sandtable/`：沙盘、区位图照片\n"
                 "- `map/`：采用的地图底图、POI 图片\n"
                 "开发商原始文件（docx/pdf/价格表）放 `sources/docs/`，只作核对依据。\n"),
}
ASSET_README["resale"] = ASSET_README["rental"]


def listing_block(category: str, community: str) -> dict:
    """episode.json listing facts per category; numbers stay null until verified."""
    block = {"name": community, "community": community, "layout": "", "area": None}
    if category == "rental":
        block["rent"] = None                                    # 元/月
    elif category == "resale":
        block["price"] = {"total_wan": None, "unit_yuan_m2": None}
    else:                                                       # new-home: 备案价/均价 + 有效期
        block["price"] = {"unit_yuan_m2": None, "range": "", "valid_until": ""}
    block.update(lnglat=None, coord="gcj02")
    block["note"] = ("新房无房源编号。楼盘名已填，价格、面积待开发商资料回填。" if category == "new-home"
                     else "数字待本期房源查询回填。模板里的示例数字已清空。")
    return block


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
    if category not in EPISODE_CATS:
        raise SystemExit("房源期类型只能是 rental、resale、new-home；knowledge 走 pipeline/knowledge/new_episode.py")
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
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from pipeline.common.episodes import next_release_number
    return next_release_number(REPO)


def blank_template(tpl: dict, spec: dict) -> dict:
    out = json.loads(json.dumps(tpl))
    out["id"] = spec["id"]
    out["episodeTag"] = f"EP.{spec['episode']:02d}"
    out["category"] = spec["category"]
    out["sampleData"] = False    # all listings are real (CRM/Amap/developer facts); true only when the user asks for simulated data
    out["sampleTag"] = ""
    out["listing"] = listing_block(spec["category"], spec["title"])
    out["plane"] = {"center": None, "zoom": 15, "k": 2.8125, "w": 1440, "h": 1080}
    out["mapBase"] = {"file": "", "ext": [-640, -880, 2080, 1960], "credit": "", "builtBy": ""}
    for poi in out.get("poiQueries") or []:
        for key in ("query", "pick", "label", "sub"):
            if key in poi:
                poi[key] = ""
    return out


def write_yaml(ep: Path, spec: dict) -> None:
    muse = "none" if spec["category"] == "new-home" else "auto"
    lines = [
        f"# episode.yaml — single source of truth for {spec['id']}. Edit this; grok reads it at every stage.",
        f"id: {spec['id']}",
        "series: listing",
        "purpose: production",
        f"release_number: {spec['episode']}",
        f"episode: {spec['episode']}",
        f"category: {spec['category']}        # rental | resale | new-home",
        "listing:",
        f"  ref: {yq(spec['listing'])}        # 租赁/二手房 CRM 编号。新房留空。不进目录名、口播、字幕、画面",
        f"  community: {yq(spec['title'])}",
        f"  city: {yq(spec['city'])}",
        f"  layout_slug: {yq(spec['layout'])}   # 户型记在这里，不进目录名",
        "  sample_data: false         # real listing: facts only from CRM / Amap / developer docs (rules/compliance). true only for user-requested simulated data",
        "footage:",
        "  # camera originals: footage/raw/ (read-only, camera file names kept); room/shot mapping: footage/raw_manifest.json",
        "  # restored Rec.709: footage/restored/{master,proxy}/ (npm run restore); render shots: footage/shots/<ID>.mp4",
        "  manifest: footage/raw_manifest.json",
        f"  muse: {muse}                 # auto = generate missing rooms/scenes with Muse; none = own footage only",
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


def copy_raw(ep: Path, footage: str | None) -> int:
    """Copy camera clips as-is (any name, DJI names kept) into footage/raw/; the source is only read."""
    if not footage:
        return 0
    n = 0
    for f in sorted(Path(footage).iterdir()):
        if f.is_file() and f.suffix.lower() in VIDEO_EXT and not f.name.startswith("."):
            shutil.copy2(f, ep / "footage" / "raw" / f.name)
            n += 1
    return n


def create(root: Path, spec: dict, template: Path) -> Path:
    if spec["category"] not in EPISODE_CATS:
        raise SystemExit("knowledge 走 pipeline/knowledge/new_episode.py")
    ep = root / spec["id"]
    if ep.exists():
        raise SystemExit(f"{ep} already exists — edit its episode.yaml instead")
    for d in BASE_DIRS + CATEGORY_DIRS[spec["category"]]:
        (ep / d).mkdir(parents=True)
    copied = copy_raw(ep, spec.get("footage"))
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from pipeline.common.raw_manifest import init as init_manifest
    init_manifest(ep, probe=bool(copied))
    tpl = json.loads(template.read_text(encoding="utf-8"))
    (ep / "episode.json").write_text(
        json.dumps(blank_template(tpl, spec), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )
    write_yaml(ep, spec)
    compliance = json.loads((REPO / "templates/listing/compliance.example.json").read_text(encoding="utf-8"))
    compliance.update(id=spec["id"], category=spec["category"], title=spec["title"] or "待填")
    category_key = {"rental": "rental", "resale": "resale", "new-home": "new_home"}[spec["category"]]
    for field in ("rental", "resale", "new_home"):
        if field != category_key:
            compliance.pop(field, None)
    if spec["category"] != "rental":
        compliance["price"].update(type="待填", unit="待填")
    compliance["property"]["location"].update(city=spec["city"], community=spec["title"])
    (ep / "compliance.json.draft").write_text(json.dumps(compliance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    else:
        id_line = "新房没有房源编号。楼盘名在 `episode.yaml` 的 `listing.community`；开发商资料放 `sources/docs/`。\n"
    (ep / "consent" / "README.md").write_text(
        "# 本期授权\n\n业主委托或本期单独授权放这里。声音克隆参考音在 `voices/clone/`，不要复制进来。\n",
        encoding="utf-8", newline="\n",
    )
    (ep / "footage" / "assets" / "README.md").write_text(
        f"# {spec['id']} 素材（{spec['category']}）\n\n只放已采用的成品，试验留在 `out/drafts/`。规范见 docs/CONVENTIONS-shared.md §6a。\n\n"
        + ASSET_README[spec["category"]]
        + "原始视频在 `footage/raw/`（只读），对应关系在 `footage/raw_manifest.json`。\n",
        encoding="utf-8", newline="\n",
    )
    (ep / "README.md").write_text(
        f"# {spec['id']}\n\n"
        f"房源讲解（{spec['category']}）。依据是 `episode.yaml`。\n"
        f"{id_line}"
        f"目录规范：docs/FOOTAGE-SPEC.md。共用声音与数字人：`voices/clone/`、`assets/presenter/cool-breeze/`。\n"
        f"做片：对 grok 说 `做视频 {spec['id']}`，或运行 `scripts\\make-video.cmd {spec['id']}`。\n",
        encoding="utf-8", newline="\n",
    )
    print(f"created {ep}  raw clips: {copied}")
    print(f"next:  做视频 {spec['id']}   |   scripts\\make-video.cmd {spec['id']}")
    return ep


def self_test() -> None:
    assert episode_id(8, "xihu") == "ep08-xihu"
    assert episode_id(12, "xihu") == "ep12-xihu"
    assert split_id("ep07-demo") == (7, "demo")
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
            "title": "西湖文化广场", "city": "成都", "footage": None,
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
        assert (ep / "footage/assets/floorplan").is_dir() and not (ep / "footage/listing").exists()
        for lazy in ("heygen", "matte", "jobs", "public", "out", "voice", "annotations", "footage/heygen"):
            assert not (ep / lazy).exists(), lazy
        assert json.loads((ep / "footage/raw_manifest.json").read_text(encoding="utf-8"))["clips"] == []
        cam = root / "card"
        cam.mkdir()
        (cam / "DJI_20261030111005_0271_D.MP4").write_bytes(b"")
        (cam / "DJI_20261030111005_0271_D.LRF").write_bytes(b"")
        home = {
            "episode": 11, "category": "new-home", "slug": "xipai", "layout": "",
            "id": "ep11-xipai", "listing": "", "topic": "",
            "title": "武侯西派御府", "city": "成都", "footage": str(cam),
        }
        hep = create(root, home, TEMPLATE)
        payload = json.loads((hep / "episode.json").read_text(encoding="utf-8"))
        assert "rent" not in payload["listing"] and payload["listing"]["price"]["unit_yuan_m2"] is None
        assert payload["listing"]["community"] == "武侯西派御府"
        assert not (hep / "data" / "project.json").exists()
        assert not (hep / "data" / "listing_ref.json").exists()
        for d in ("footage/assets/brochure", "footage/assets/renderings", "footage/assets/sandtable", "footage/assets/map", "sources/docs"):
            assert (hep / d).is_dir(), d
        assert (hep / "footage/raw/DJI_20261030111005_0271_D.MP4").is_file()
        assert not (hep / "footage/raw/DJI_20261030111005_0271_D.LRF").exists()
        manifest = json.loads((hep / "footage/raw_manifest.json").read_text(encoding="utf-8"))
        assert [c["file"] for c in manifest["clips"]] == ["DJI_20261030111005_0271_D.MP4"]
        assert "muse: none" in (hep / "episode.yaml").read_text(encoding="utf-8")
        hj = json.loads((hep / "episode.json").read_text(encoding="utf-8"))
        assert hj["sampleData"] is False and hj["sampleTag"] == "" and "sample_data: false" in (hep / "episode.yaml").read_text(encoding="utf-8")
        assert hep.name == "ep11-xipai"
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
    ap.add_argument("--city", default="成都")
    ap.add_argument("--footage", help="folder of camera clips (any names, e.g. DJI_*_D.MP4); copied as-is into footage/raw/")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    if a.category == "knowledge":
        forwarded = ["--slug", a.slug, "--topic", a.topic, "--city", a.city]
        for flag, value in (("--id", a.id), ("--episode", a.episode), ("--title", a.title)):
            if value is not None and str(value):
                forwarded += [flag, str(value)]
        if a.listing:
            raise SystemExit("knowledge does not accept --listing")
        raise SystemExit(subprocess.call([sys.executable, str(REPO / "pipeline/knowledge/new_episode.py"), *forwarded]))
    spec = resolve_spec(a)
    create(SERIES, spec, TEMPLATE)


if __name__ == "__main__":
    main()


