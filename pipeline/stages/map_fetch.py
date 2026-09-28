"""Stage 3 · map:fetch — geocode community → map/geo.json + satellite_4x3.jpg + static.png + pois.json.

Calls the map-tools skill script. Never prints API keys. Falls back to a schematic satellite
placeholder when keys / network fail; live_status is recorded so the sample report is accurate.
"""
from __future__ import annotations

import json
import shutil
import os
import subprocess
import sys
from pathlib import Path

from .common import load_brief, load_json, now_iso, save_json

DEFAULT_MAP_PY = Path.home() / ".agents" / "skills" / "map-tools" / "scripts" / "map.py"
ATTRIBUTION = "地图数据 © 高德地图（示意，非测绘成果）"


def _find_map_py() -> Path | None:
    candidates = [
        Path(__file__).resolve().parents[2] / "vendor" / "map-tools" / "scripts" / "map.py",
        DEFAULT_MAP_PY,
    ]
    import os
    if os.environ.get("MAP_TOOLS_SCRIPT"):
        candidates.insert(0, Path(os.environ["MAP_TOOLS_SCRIPT"]))
    for c in candidates:
        if c.is_file():
            return c
    return None


def _haversine(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    import math
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _run(map_py: Path, args: list[str]) -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}  # map.py prints Chinese; Windows console is cp1252/gbk
    proc = subprocess.run([sys.executable, str(map_py), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _placeholder_satellite(out: Path, label: str) -> None:
    """Schematic 'night map' placeholder (procedural, no third-party pixels). Clearly labelled 示意."""
    import random
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1d2330:s=2160x1620",
                        "-frames:v", "1", str(out)], check=False, capture_output=True)
        return
    rnd = random.Random(label)
    W, H = 2160, 1620
    im = Image.new("RGB", (W, H), (29, 35, 48))
    d = ImageDraw.Draw(im)
    # blocks
    for _ in range(260):
        x, y = rnd.randrange(0, W), rnd.randrange(0, H)
        w, h = rnd.randrange(40, 180), rnd.randrange(40, 160)
        c = rnd.choice([(44, 52, 68), (40, 47, 62), (52, 60, 76), (38, 58, 52)])
        d.rectangle([x, y, x + w, y + h], fill=c)
    # roads
    for _ in range(14):
        y = rnd.randrange(0, H)
        d.line([(0, y), (W, y + rnd.randrange(-200, 200))], fill=(92, 102, 120), width=rnd.choice([6, 10, 16]))
    for _ in range(12):
        x = rnd.randrange(0, W)
        d.line([(x, 0), (x + rnd.randrange(-200, 200), H)], fill=(92, 102, 120), width=rnd.choice([6, 10, 16]))
    # river
    d.line([(0, int(H * 0.78)), (W * 0.4, int(H * 0.72)), (W, int(H * 0.84))], fill=(40, 70, 96), width=70)
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    d = ImageDraw.Draw(im)
    d.text((40, 30), f"SCHEMATIC MAP / 示意底图 · {label}", fill=(200, 205, 215))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=90)


def run(project_dir: Path, force: bool = False) -> dict:
    map_dir = project_dir / "map"
    geo_p = map_dir / "geo.json"
    sat_p = map_dir / "satellite_4x3.jpg"
    static_p = map_dir / "static.png"
    pois_p = map_dir / "pois.json"
    if all(p.exists() for p in (geo_p, sat_p, static_p, pois_p)) and not force:
        return {"skipped": True}

    brief = load_brief(project_dir)
    listing = load_json(project_dir / "listing.json")
    community = listing.get("community") or (brief.get("listing") or {}).get("community_keyword") or "示例小区"
    city = (brief.get("listing") or {}).get("city") or (brief.get("map") or {}).get("city") or "杭州"
    query = (brief.get("map") or {}).get("query") or community
    map_dir.mkdir(parents=True, exist_ok=True)

    map_py = _find_map_py()
    live_status = "untested"
    live_note = None
    geo = {"query": query, "city": city, "source": "amap", "coord": "gcj02", "live_status": live_status}

    explicit_query = bool((brief.get("map") or {}).get("query"))
    if map_py and (listing.get("source") != "mock" or explicit_query):
        try:
            code, out = _run(map_py, ["place", query, "--city", city, "--limit", "3", "--all-coords"])
            if code == 0:
                text = out[out.find("["): out.rfind("]") + 1]
                rows = json.loads(text) if text else []
                if rows:
                    row = rows[0]
                    loc = row.get("location") or ""
                    lng, lat = [float(x) for x in loc.split(",")]
                    geo.update({"name": row.get("name"), "address": row.get("address"), "lng": lng, "lat": lat,
                                "coords": row.get("coords"), "live_status": "ok"})
                    live_status = "ok"
                    # Satellite
                    _run(map_py, ["satellite", f"{lng},{lat}", "--zoom", "16", "--width", "1440", "--height", "1080",
                                  "--labels", "--out", str(sat_p)])
                    _run(map_py, ["staticmap", f"{lng},{lat}", "--zoom", "15", "--width", "1024", "--height", "768",
                                  "--marker", "--out", str(static_p)])
                    code2, out2 = _run(map_py, ["place", f"{community} 地铁站", "--city", city, "--limit", "5"])
                    pois = []
                    if code2 == 0:
                        t = out2[out2.find("["): out2.rfind("]") + 1]
                        pois = json.loads(t) if t else []
                    for poi in pois:
                        try:
                            plng, plat = [float(x) for x in str(poi.get("location")).split(",")]
                            poi["distance_m"] = round(_haversine(lng, lat, plng, plat) / 10) * 10
                            poi["distance_basis"] = "直线距离（高德 GCJ-02 坐标计算，非步行路程）"
                        except Exception:
                            poi["distance_m"] = None
                    pois = [x for x in pois if x.get("distance_m") and x["distance_m"] <= 3000]
                    save_json(pois_p, {"items": pois, "fetched_at": now_iso()})
        except Exception as e:
            live_note = str(e)
            live_status = "failed"
    else:
        live_note = "mock listing or map.py not found"
        live_status = "untested"

    if live_status != "ok":
        # Fictional Hangzhou-ish GCJ-02 (西湖区附近，示意)
        geo.update({"name": community, "lng": 120.130, "lat": 30.259, "live_status": live_status, "live_note": live_note,
                    "address": f"{city}·示例区（虚构坐标）"})
        if not sat_p.exists() or force:
            _placeholder_satellite(sat_p, community)
        if not static_p.exists() or force:
            shutil.copy2(sat_p, static_p)
        if not pois_p.exists() or force:
            save_json(pois_p, {"items": [
                {"name": "示例地铁站", "address": "距小区约 850 米（地图测距·示意）", "type": "地铁站"},
                {"name": "示例公园", "address": "距小区约 600 米（地图测距·示意）", "type": "公园"},
            ], "fetched_at": now_iso(), "live_status": live_status})
        attribution = "示意底图 · 非真实地图（map:fetch 未联网/未取到坐标）"
    else:
        attribution = ATTRIBUTION

    geo["attribution"] = attribution
    geo["fetched_at"] = now_iso()
    save_json(geo_p, geo)
    # Ensure static.png exists even on success path when only jpg was written
    if not static_p.exists() and sat_p.exists():
        shutil.copy2(sat_p, static_p)
    return {"live_status": live_status, "query": query, "attribution": attribution}
