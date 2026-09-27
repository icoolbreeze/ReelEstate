"""Create a new property project from a category template.

Usage:  python pipeline/new_project.py <rental|resale|new-home> <slug> [--date YYYY-MM-DD]
Result: projects/<category>/<date>-<slug>/ with project.json, raw/, canva/, audio/, consent/, output/
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reel_common import CATEGORIES, PROJECTS_DIR, REPO_ROOT, load_json, save_json, setup_console  # noqa: E402

SUBDIRS = ("raw", "canva", "audio", "consent", "output")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def main(argv=None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="新建房源视频项目")
    ap.add_argument("category", choices=CATEGORIES, help="rental(租赁) / resale(二手房) / new-home(新房)")
    ap.add_argument("slug", help="英文/拼音短名，如 lvcheng-2b1l（自动加日期前缀）")
    ap.add_argument("--date", help="日期前缀 YYYY-MM-DD，默认今天")
    ap.add_argument("--title", help="中文标题（可选，写入 project.json）")
    args = ap.parse_args(argv)

    slug = args.slug.strip().lower()
    if DATE_PREFIX_RE.match(slug):
        project_id = slug
    else:
        date = args.date or dt.date.today().isoformat()
        try:
            dt.date.fromisoformat(date)
        except ValueError:
            print(f"错误：--date 格式应为 YYYY-MM-DD，收到 {date}", file=sys.stderr)
            return 2
        project_id = f"{date}-{slug}"
    if not SLUG_RE.match(project_id):
        print(f"错误：项目名只能用小写英文/拼音/数字/连字符：{project_id}（中文名请写进 project.json 的 title）", file=sys.stderr)
        return 2

    template = REPO_ROOT / "templates" / args.category / "project.json"
    target = PROJECTS_DIR / args.category / project_id
    if target.exists():
        print(f"错误：项目已存在：{target.relative_to(REPO_ROOT).as_posix()}", file=sys.stderr)
        return 1

    data = load_json(template)
    data["id"] = project_id
    data["category"] = args.category
    if args.title:
        data["title"] = args.title

    target.mkdir(parents=True)
    for sub in SUBDIRS:
        (target / sub).mkdir()
        (target / sub / ".gitkeep").touch()
    save_json(target / "project.json", data)
    (target / "consent" / "README.md").write_text(
        "# consent/\n\n放业主书面委托书/授权书、出镜人与声音本人的授权书（AI 配音/克隆）。\n本目录属于私有项目，不会提交到 git。\n",
        encoding="utf-8", newline="\n")

    rel = target.relative_to(REPO_ROOT).as_posix()
    print(f"✅ 已创建项目：{rel}")
    print(f"   子目录：{', '.join(SUBDIRS)}")
    print("下一步：")
    print(f"  1. 素材放入 {rel}/raw/，Canva 卡片放入 canva/，授权文件放入 consent/")
    print(f"  2. 编辑 {rel}/project.json，替换所有“待填”")
    print(f"  3. npm run check -- {rel}")
    print(f"  4. npm run render -- {rel} --ratio 4x3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
