"""Stage 2 · listing:wall — build wall.json (6-12 cards + picked id) and thumbnail files."""
from __future__ import annotations

import shutil
from pathlib import Path

from .common import REPO_ROOT, NeedInput, load_brief, load_json, now_iso, save_json
from .listing import THUMB_SUFFIX, _cdn, _download


def _fmt_area(area):
    if isinstance(area, (int, float)):
        return f"{area:g}㎡"
    return area or None


def _card(item: dict, idx: int, thumb: str | None) -> dict:
    area = item.get("area_sqm")
    rent = item.get("monthly_rent_yuan")
    return {
        "id": f"c{idx:02d}",
        "listing_id": item.get("listing_id"),
        "cover": thumb,
        "community": item.get("community") or item.get("resblock_name") or "待填",
        "layout": item.get("layout"),
        "area": _fmt_area(area),
        "rent": f"{int(rent)}元/月" if isinstance(rent, (int, float)) else None,
        "orientation": item.get("orientation"),
        "floor": item.get("floor_desc"),
    }


def run(project_dir: Path, force: bool = False) -> dict:
    out = project_dir / "wall.json"
    if out.exists() and not force:
        return {"skipped": True}
    wall_raw = load_json(project_dir / "wall_candidates.json")
    listing = load_json(project_dir / "listing.json")
    brief = load_brief(project_dir)
    items = wall_raw.get("items") or []
    if len(items) < 6:
        raise NeedInput([{"key": "listing.target", "q": f"列表墙需要 6–12 套房源，当前只有 {len(items)} 套，请放宽筛选。", "blocks": "listing:wall"}])

    thumbs_dir = project_dir / "raw" / "wall"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    warehouse = sorted((REPO_ROOT / "assets" / "warehouse" / "covers").glob("*.jpg"))
    covers_meta: dict[str, dict] = {}
    cards = []
    for i, item in enumerate(items[:12]):
        rel = f"raw/wall/c{i+1:02d}.jpg"
        dest = project_dir / rel
        thumb = None
        url = item.get("title_image_url")
        if url and item.get("source") != "mock":
            if (dest.exists() and not force) or _download(_cdn(url, THUMB_SUFFIX), dest):
                thumb = rel
                # CRM covers often carry platform watermarks/logos → unknown until a human reviews them.
                covers_meta[rel] = {"source": "crm", "license": "经纪机构房源图（需业主委托）", "watermarked": None,
                                    "source_tag": None, "attribution": "CRM 房源封面（需人工核查水印/logo）"}
        elif warehouse:
            src = warehouse[i % len(warehouse)]
            if not dest.exists() or force:
                shutil.copy2(src, dest)
            thumb = rel
            covers_meta[rel] = {"source": "wikimedia/unsplash", "license": "CC0", "watermarked": False,
                                "attribution": "Unsplash via Wikimedia Commons (CC0) — 示例封面", "source_tag": None}
        cards.append(_card(item, i + 1, thumb))
    save_json(thumbs_dir / "_covers.json", covers_meta)

    pick_id = (brief.get("listing") or {}).get("pick") or listing.get("listing_id") or wall_raw.get("picked")
    picked_card = next((c for c in cards if c["listing_id"] == pick_id), cards[0])
    # CRM ids stay in wall_candidates.json (private); wall.json goes into Remotion props → strip them.
    mapping = {c["id"]: c.pop("listing_id") for c in cards}
    save_json(project_dir / "raw" / "wall_map.json", mapping)
    save_json(out, {
        "cards": cards,
        "picked": picked_card["id"],
        "blur_others": True,
        "built_at": now_iso(),
    })
    return {"cards": len(cards), "picked": picked_card["id"]}
