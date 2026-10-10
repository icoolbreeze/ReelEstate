#!/usr/bin/env python3
"""Create a new map-hub 口播 episode skeleton (fixed workflow; see docs/RUNBOOK-map-hub-koubo.md and docs/FOOTAGE-SPEC.md).

usage:
  python scripts/new_episode.py --id ep08-xxx --category rental --listing <beike id or url> [--footage <dir>] [--title 小区名]

Creates projects/map-hub/<id>/ with:
  episode.yaml   single source of truth (listing, category, raw footage list, voice engine, avatar) — edit this, not episode.json
  episode.json   template copy from projects/map-hub/ep07-xihu (listing/map fields are filled by the runbook stages)
  footage/raw/   your own shot footage (房间_序号.mp4, e.g. 客厅_1.mp4); --footage copies matching files in
  footage/, voice/, heygen/, matte/, annotations/seeds/, data/, public/, out/, jobs/
  README.md
Then tell grok:  做视频 <id>   (or run  scripts\\make-video.cmd <id>)
"""
import argparse, json, re, shutil, sys
from datetime import date
from pathlib import Path

for _s in (sys.stdout, sys.stderr): _s.reconfigure(encoding="utf-8", errors="replace")   # Windows cp1252 consoles
REPO = Path(__file__).resolve().parents[1]
CATS = ("rental", "resale", "new-home")
ROOMS = ("客厅", "主卧", "次卧", "卧室", "书房", "厨房", "卫生间", "餐厅", "阳台", "玄关", "外立面", "小区", "大堂", "周边")
NAME = re.compile(r"^(?P<room>[\u4e00-\u9fff]+)_(?P<n>\d{1,2})\.(mp4|mov|MP4|MOV)$")

def yq(s): return json.dumps(s, ensure_ascii=False)   # JSON strings are valid YAML scalars

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", required=True, help="epNN-slug, e.g. ep08-wulin")
    ap.add_argument("--category", required=True, choices=CATS)
    ap.add_argument("--listing", required=True, help="Beike listing id or URL")
    ap.add_argument("--footage", help="folder with raw footage named 房间_序号.mp4")
    ap.add_argument("--title", default="", help="community name (optional, filled by the listing stage otherwise)")
    ap.add_argument("--city", default="杭州")
    a = ap.parse_args()
    if not re.fullmatch(r"ep\d{2,3}-[a-z0-9-]+", a.id): sys.exit("--id must look like ep08-wulin (lowercase pinyin slug)")
    ep = REPO / "projects/map-hub" / a.id
    if ep.exists(): sys.exit(f"{ep} already exists — edit its episode.yaml instead")
    for d in ("footage/raw", "footage/heygen", "voice", "heygen", "matte", "annotations/seeds", "data", "public", "out", "jobs"):
        (ep / d).mkdir(parents=True)
    raw, bad = [], []
    if a.footage:
        for f in sorted(Path(a.footage).iterdir()):
            if not f.is_file(): continue
            m = NAME.match(f.name)
            if m: shutil.copy2(f, ep / "footage/raw" / f.name); raw.append((f.name, m["room"], int(m["n"])))
            elif f.suffix.lower() in (".mp4", ".mov"): bad.append(f.name)
    tpl = json.loads((REPO / "projects/map-hub/ep07-xihu/episode.json").read_text(encoding="utf-8"))
    tpl.update({"id": a.id, "category": a.category, "listingRef": a.listing, "city": a.city, "created": date.today().isoformat()})
    tpl["listing"] = {"community": a.title, "_todo": "filled by runbook stage 1 from the Beike listing"}
    (ep / "episode.json").write_text(json.dumps(tpl, ensure_ascii=False, indent=1), encoding="utf-8")
    y = [f"# episode.yaml — single source of truth for {a.id}. Edit this; grok reads it at every stage.",
         f"id: {a.id}", f"series: map-hub", f"category: {a.category}        # rental | resale | new-home",
         "listing:", f"  ref: {yq(a.listing)}        # Beike id or URL (BeikeMicroservice crm_connector)",
         f"  community: {yq(a.title)}", f"  city: {a.city}",
         "  sample_data: true          # true = 示例数据 (spoken once); false = live listing, follow rules/compliance",
         "footage:",
         "  # raw footage in footage/raw/, named 房间_序号.mp4 (see docs/FOOTAGE-SPEC.md). Muse fills rooms with no raw clip.",
         "  raw:"]
    y += [f"    - {{file: {yq(n)}, room: {r}, n: {k}, use: auto}}" for n, r, k in raw] or ["    []"]
    y += ["  muse: auto                 # auto = generate missing rooms/scenes with Muse; none = raw only",
          "presenter: cool-breeze       # shared profile assets/presenter/<name>/presenter.yaml (avatar, voice ref, F5 seed/speed, matting)",
          "# presenter_override:         # optional per-episode overrides, e.g.",
          "#   voice: {seed: 33, speed_oncam: 1.1}",
          "#   heygen: {look: casual}",
          "oncam_budget_s: 55",
          "render:", "  size: 1440x1080", "  fps: 30", "  lufs: -16", "  on_screen_notes: false     # brand strip only",
          "status: {intake: done}     # grok updates per stage: listing, pois, script, voice, muse, annotate, heygen, matte, render, qa"]
    (ep / "episode.yaml").write_text("\n".join(y) + "\n", encoding="utf-8")
    (ep / "README.md").write_text(f"# {a.id}\n\nmap-hub 口播 episode ({a.category}). Source of truth: `episode.yaml`.\n"
                                  f"Make it: say `做视频 {a.id}` to grok, or run `scripts\\make-video.cmd {a.id}`.\n"
                                  "Runbook: docs/RUNBOOK-map-hub-koubo.md · footage rules: docs/FOOTAGE-SPEC.md\n", encoding="utf-8")
    print(f"created {ep.relative_to(REPO)}  raw clips: {len(raw)}")
    if bad: print("NOT copied (bad names, rename to 房间_序号.mp4):", ", ".join(bad))
    print(f"next:  做视频 {a.id}   |   scripts\\make-video.cmd {a.id}")

if __name__ == "__main__":
    main()
