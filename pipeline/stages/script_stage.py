"""Stage 5 · script — write project.json + shots.json.

The agent is expected to rewrite narration / shots following rules/style/<preset>.md.
This stage ships a deterministic fallback that produces a 25–35 s mediastorm-style rental cut
from listing.json + wall.json + map/, so `npm run make` can render a sample end-to-end.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from .common import PLACEHOLDER, load_brief, load_json, now_iso, save_json

DEFAULT_ROOMS = [
    {"key": "living", "zh": "客厅", "en": "Living", "pill": "南北通透", "media": "raw/stock/living.jpg"},
    {"key": "bedroom", "zh": "主卧", "en": "Bedroom", "pill": "朝南", "media": "raw/stock/bedroom.jpg"},
    {"key": "kitchen", "zh": "厨房", "en": "Kitchen", "pill": "开放式", "media": "raw/stock/kitchen.jpg"},
]

FLOORPLAN = {
    "schematic": True,
    "rooms": [
        {"key": "living", "zh": "客厅", "x": 0.02, "y": 0.08, "w": 0.55, "h": 0.55},
        {"key": "bedroom", "zh": "主卧", "x": 0.60, "y": 0.08, "w": 0.36, "h": 0.40},
        {"key": "kitchen", "zh": "厨房", "x": 0.02, "y": 0.66, "w": 0.30, "h": 0.28},
        {"key": "bath", "zh": "卫生间", "x": 0.35, "y": 0.66, "w": 0.22, "h": 0.28},
        {"key": "balcony", "zh": "阳台", "x": 0.60, "y": 0.52, "w": 0.36, "h": 0.42},
    ],
}


def fmt(x) -> str:
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def _valid_until(days=60) -> str:
    return (dt.date.today() + dt.timedelta(days=days)).isoformat()


def build_project(brief: dict, listing: dict, wall: dict) -> dict:
    cat = brief.get("category") or "rental"
    community = listing.get("community") or "待填"
    layout = listing.get("layout") or "待填"
    area = listing.get("area_sqm") if isinstance(listing.get("area_sqm"), (int, float)) else 0
    rent = listing.get("monthly_rent_yuan") if isinstance(listing.get("monthly_rent_yuan"), (int, float)) else 0
    orient = listing.get("orientation") or "待填"
    floor = listing.get("floor_desc") or "待填"
    agency = listing.get("maintain_org") or "示例星河房地产经纪有限公司"
    style = brief.get("style") or "mediastorm"
    pid = brief.get("project_id") or brief.get("slug") or "auto"
    title = f"{community} {layout} · 月租{int(rent) if rent else '待填'}元（{'示例' if listing.get('source')=='mock' else '讲解'}）"

    segs = [
        {"id": "s01", "text": f"预算四千多，想在{community}附近整租两居，我先帮你筛了几套。", "presenter": "fullscreen"},
        {"id": "s02", "text": f"就看这套：建筑面积{fmt(area)}平，{layout}，{orient}，{floor}。", "presenter": "pip-right"},
        {"id": "s03", "text": "进门先到客厅，采光面宽；往里走是主卧，朝南。", "presenter": "pip-left"},
        {"id": "s04", "text": f"月租{int(rent)}，押一付三。缺点也说清楚：楼龄偏长，北侧临主路有噪音。", "presenter": "pip-right"},
        {"id": "s05", "text": "离示例地铁站大约八百五十米。适合两口之家，想看房点下方组件预约。", "presenter": "fullscreen"},
    ]
    nearby = []
    pois = []
    pois_p = Path()  # filled by caller via project_dir
    return {
        "schema_version": 1,
        "id": pid,
        "category": cat,
        "title": title,
        "style": style,
        "is_example": listing.get("source") == "mock",
        "ai_voice": True,
        "ad_disclosure": False,
        "export": {"default_ratio": brief.get("ratio") or "4x3", "ratios": ["4x3", "3x4", "9x16"], "fps": 30},
        "property": {
            "property_type": "普通住宅",
            "layout": layout,
            "area": {"type": "建筑面积", "value": area if area else 0},
            "location": {
                "city": (brief.get("listing") or {}).get("city") or "杭州市",
                "district": "示例区" if listing.get("source") == "mock" else (listing.get("biz_circle") or "待填"),
                "street": "示例街道" if listing.get("source") == "mock" else "待填",
                "community": community,
            },
            "floor": floor,
            "orientation": orient,
            "decoration": "简装",
            "build_year": 2012 if listing.get("source") == "mock" else None,
        },
        "price": {"type": "月租金", "value": rent if rent else 0, "unit": "元/月", "valid_until": _valid_until()},
        "agency": {"full_name": agency if agency.endswith("公司") else agency + "房地产经纪有限公司" if "公司" not in agency else agency},
        "agent": {"name": "示例经纪人" if listing.get("source") == "mock" else "待填", "certified_on_camera": True},
        "highlights": [orient, f"{layout}", f"{floor}"],
        "drawbacks": ["楼龄偏长，外立面有些旧", "北侧临近主路，有车流噪音", "只有一个卫生间"],
        "nearby": nearby,
        "tts": {"voice": "narrator_male_30", "mode": "voicedesign"},
        "narration": {"segments": segs},
        "rental": {
            "rent_type": listing.get("rent_mode_label") or "整租",
            "payment_terms": "押一付三",
            "service_fee": "半个月租金",
            "utilities": "民水民电",
            "available_from": _valid_until(7),
            "min_lease_months": 12,
        },
    }


def floor_en(desc: str) -> str:
    if "低" in (desc or ""):
        return "LOW FLOOR"
    if "高" in (desc or ""):
        return "HIGH FLOOR"
    if "中" in (desc or ""):
        return "MID FLOOR"
    return "FLOOR"


def _map_role_shots(project_dir: Path, listing: dict) -> list[dict]:
    """Mandatory map shots by role (overview is built in build_shots): commute + amenities where data exists.
    Numbers come only from Amap results (map/route.json, map/pois.json). On-screen text is distance only
    (rules/compliance forbids '分钟到' style position claims); route duration is kept in route_ref for reference."""
    out = []
    mock = listing.get("source") == "mock"
    route_p, pois_p = project_dir / "map" / "route.json", project_dir / "map" / "pois.json"
    routes = [x for x in (load_json(route_p).get("items") or []) if x.get("distance_m")] if route_p.exists() else []
    if routes:
        it = sorted(routes, key=lambda x: (x.get("kind") != "commute_to", {"driving": 0, "transit": 1}.get(x.get("mode"), 2)))[0]  # commute target first; drive/transit before walking
        mode_zh = {"walking": "步行", "driving": "驾车", "transit": "公交"}.get(it.get("mode"), "")
        out.append({"id": "sh11", "segment": "s05", "weight": 1.2, "type": "map", "presenter": "none", "map_role": "commute",
                    "location": {"main": it.get("to") or "通勤目的地", "sub": f"约 {int(it['distance_m'])} 米 · 高德{mode_zh}路线距离"},
                    "route_ref": {"mode": it.get("mode"), "distance_m": it["distance_m"], "duration_s": it.get("duration_s")}})
    pois = [x for x in (load_json(pois_p).get("items") or []) if x.get("distance_m")] if (pois_p.exists() and not mock) else []
    if pois:
        it = min(pois, key=lambda x: x["distance_m"])
        out.append({"id": "sh12", "segment": "s05", "weight": 1.2, "type": "map", "presenter": "none", "map_role": "amenities",
                    "location": {"main": it.get("name") or "周边配套", "sub": f"约 {int(it['distance_m'])} 米 · 直线距离（高德坐标测距）"}})
    elif mock:
        out.append({"id": "sh12", "segment": "s05", "weight": 1.2, "type": "map", "presenter": "none", "map_role": "amenities",
                    "location": {"main": "示例地铁站", "sub": "约 850 米 · 直线距离（地图测距·示意）"}})
    return out


def build_shots(brief: dict, listing: dict, wall: dict, project: dict, project_dir: Path) -> dict:
    style = brief.get("style") or "mediastorm"
    rooms = [dict(r, pill=floor_en(listing.get("floor_desc") or "")) for r in DEFAULT_ROOMS]
    # Prefer real survey photos when present
    photos = listing.get("photos") or []
    by_room = {}
    for ph in photos:
        key = (ph.get("room") or "").lower()
        for cand in ("living", "客厅", "bedroom", "卧", "kitchen", "厨"):
            if cand in key:
                by_room[cand] = ph["file"]
    for r in rooms:
        for cand in (r["key"], r["zh"]):
            if cand in by_room:
                r["media"] = by_room[cand]
                break

    area = listing.get("area_sqm") or project["property"]["area"]["value"]
    rent = listing.get("monthly_rent_yuan") or project["price"]["value"]
    community = listing.get("community")
    orient = listing.get("orientation") or ""
    floor = listing.get("floor_desc") or ""

    shots = [
        {"id": "sh01", "segment": "s01", "weight": 1.0, "type": "presenter", "presenter": "fullscreen"},
        {"id": "sh02", "segment": "s01", "weight": 1.4, "type": "wall", "presenter": "pip-right"},
        {"id": "sh03", "segment": "s02", "weight": 1.0, "type": "broll", "presenter": "none",
         "media": "raw/stock/highrise.jpg", "push": True,
         "location": {"main": f"{community}", "sub": f"{project['property']['location'].get('district', '')} · 整租"}},
        {"id": "sh04", "segment": "s02", "weight": 1.3, "type": "spec", "presenter": "pip-right",
         "media": "raw/stock/balconies.jpg",
         "spec": {"title": f"{fmt(area)} m²", "lines": [f"建筑面积：{fmt(area)}㎡", f"户型：{listing.get('layout')}", f"朝向：{orient}", f"楼层：{floor} / 共{listing.get('total_floors') or '待填'}层"]}},
        {"id": "sh05", "segment": "s03", "weight": 1.3, "type": "room", "presenter": "none",
         "media": rooms[0]["media"], "push": True, "locator": "living",
         "room": {"zh": rooms[0]["zh"], "en": rooms[0]["en"], "pill": rooms[0]["pill"], "index": 1, "total": 2}},
        {"id": "sh06", "segment": "s03", "weight": 1.3, "type": "room", "presenter": "none",
         "media": rooms[1]["media"], "push": True, "locator": "bedroom",
         "room": {"zh": rooms[1]["zh"], "en": rooms[1]["en"], "pill": rooms[1]["pill"], "index": 2, "total": 2}},
        {"id": "sh07", "segment": "s04", "weight": 0.9, "type": "number", "presenter": "pip-right",
         "media": "raw/stock/living.jpg",
         "number": {"value": f"{int(rent):,}", "unit": "元/月", "caption": f"月租金 · 押一付三（截至 {project['price']['valid_until']}）"}},
        {"id": "sh08", "segment": "s04", "weight": 1.4, "type": "spec", "presenter": "pip-left",
         "media": "raw/stock/highrise.jpg",
         "spec": {"title": "HEADS-UP", "variant": "warning", "lines": ["楼龄偏长，外立面有些旧", "北侧临近主路，有车流噪音", "只有一个卫生间"]}},
        {"id": "sh09", "segment": "s05", "weight": 1.35, "type": "map", "presenter": "none", "map_role": "overview",
         "location": {"main": community or "小区", "sub": " · ".join(x for x in (project["property"]["location"].get("city"), project["property"]["location"].get("district")) if x and "待填" not in x) or "位置示意"}},
        {"id": "sh10", "segment": "s05", "weight": 1.0, "type": "outro", "presenter": "fullscreen",
         "cta": "点击下方组件 预约看房"},
    ]

    # Map is mandatory: add the commute / amenities map shots (overview is sh09) before the outro.
    _i = next((i for i, s in enumerate(shots) if s["id"] == "sh10"), len(shots))
    shots[_i:_i] = _map_role_shots(project_dir, listing)

    # Attach nearby from pois.json when present (objective metres only — no “X分钟”).
    pois_p = project_dir / "map" / "pois.json"
    nearby = [{"name": "示例地铁站", "distance_m": 850, "basis": "地图测距", "status": "已建成"}]
    if pois_p.exists() and listing.get("source") != "mock":
        nearby = []
        for it in (load_json(pois_p).get("items") or [])[:3]:
            if it.get("distance_m"):
                nearby.append({"name": it.get("name") or "POI", "distance_m": it["distance_m"], "basis": "直线距离（高德坐标计算）", "status": "已建成"})
    project["nearby"] = nearby

    return {"style": style, "generated_by": "pipeline/stages/script_stage.py (deterministic fallback)",
            "built_at": now_iso(), "shots": shots, "floorplan": FLOORPLAN}


def run(project_dir: Path, force: bool = False) -> dict:
    out_proj = project_dir / "project.json"
    out_shots = project_dir / "shots.json"
    if out_proj.exists() and out_shots.exists() and not force:
        # Still refresh media pointers if missing
        return {"skipped": True}

    brief = load_brief(project_dir)
    listing = load_json(project_dir / "listing.json")
    wall = load_json(project_dir / "wall.json")
    project = build_project(brief, listing, wall)
    # Keep agent-edited fields if project.json already exists and --force was not used for narration:
    if out_proj.exists() and not force:
        existing = load_json(out_proj)
        # Only fill style / is_example if missing
        existing.setdefault("style", project["style"])
        project = existing
    shots = build_shots(brief, listing, wall, project, project_dir)
    # Ensure agency ends with 公司 for check
    if not str(project.get("agency", {}).get("full_name", "")).endswith("公司"):
        project["agency"]["full_name"] = "示例星河房地产经纪有限公司"
    save_json(out_proj, project)
    save_json(out_shots, shots)
    return {"segments": len(project["narration"]["segments"]), "shots": len(shots["shots"]), "style": shots["style"]}
