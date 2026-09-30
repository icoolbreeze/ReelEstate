"""Stage 3 · map:fetch — geocode community → map/geo.json + satellite_4x3.jpg + static.png + pois.json.

Calls the map-tools script configured in config/map-tools.json
(default ~/.agents/skills/map-tools/scripts/map.py; override with MAP_TOOLS_SCRIPT).
Never prints API keys. Falls back to a schematic satellite placeholder when keys / network fail;
live_status is recorded so the sample report is accurate.

The map is a mandatory part of every video. Extra outputs: map/route.json (Amap route distance/duration,
only Amap-returned numbers) and the flova IMAGE repaint hand-off: flova is an MCP that only the agent can call, so
this stage writes map/flova_request.json (generate_image, gpt-image-2.5 family, profile kid4, original:true, reference
map/static.png) and exits 3 (NeedInput) until the agent saved map/base_ai.png; the code then overlays labels/distances.
No video generation for the map (generate_video is off by default everywhere; see brief flova.video_allowed).
--mock / flova.allowed=false / no live Amap data: no repaint, labelled placeholder or real Amap imagery is kept.
Credits are handled by the flova MCP and are never a limit; failures are surfaced to the user, not worked around.
"""
from __future__ import annotations

import json
import shutil
import os
import subprocess
import sys
from pathlib import Path

from .common import NeedInput, load_brief, load_json, now_iso, save_json

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_PY = Path.home() / ".agents" / "skills" / "map-tools" / "scripts" / "map.py"
MAP_CONFIG = REPO_ROOT / "config" / "map-tools.json"
ATTRIBUTION = "地图数据 © 高德地图（示意，非测绘成果）"

# Used when config/map-tools.json is missing or broken: finding the script must never crash the stage.
_FALLBACK_MAP_PY = [
    REPO_ROOT / "vendor" / "map-tools" / "scripts" / "map.py",
    DEFAULT_MAP_PY,
]


def _resolve_map_path(raw: str) -> Path:
    p = Path(raw).expanduser()  # "~" -> user home
    if not p.is_absolute():
        p = REPO_ROOT / p  # relative paths are relative to the repo root
    return p


def _find_map_py() -> Path | None:
    candidates: list[Path] = []
    if os.environ.get("MAP_TOOLS_SCRIPT"):
        candidates.append(_resolve_map_path(os.environ["MAP_TOOLS_SCRIPT"]))
    try:
        cfg = json.loads(MAP_CONFIG.read_text(encoding="utf-8"))
        script = cfg.get("script")
        if isinstance(script, str) and script.strip():
            candidates.append(_resolve_map_path(script.strip()))
        for c in cfg.get("script_candidates") or []:
            if isinstance(c, str) and c.strip():
                candidates.append(_resolve_map_path(c.strip()))
    except (OSError, ValueError):
        pass  # missing or corrupt config: fall back to the hardcoded candidates
    candidates.extend(_FALLBACK_MAP_PY)
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


ATTR_AI = "示意图 / AI 生成底图 / © 高德地图"
ATTR_SCHEMATIC = "示意图 / 示意底图（非真实地图）/ © 高德地图"
# Image generation only (never generate_video): original non-watermarked image. The map repaint is the one place
# that passes profile kid4 (user decision). Model: gpt-image-2.5 family, see config/flova-models.json.
FLOVA_TOOL = "generate_image"
FLOVA_MODEL = "gpt-image-2.5-sunburst"  # polished image edit from a reference image (config/flova-models.json)
FLOVA_PARAMS = {"profile": "kid4", "original": True}
FLOVA_PROMPT = (
    "Restyle this Amap road map into a clean, bright, low-saturation illustrated map for a real-estate short "
    "video. Keep the road network, water bodies, blocks and the centre marker exactly where they are. Do not add, "
    "remove, move or invent roads, buildings, landmarks or text. No labels, no logos, no watermark, no people. "
    "4:3 landscape."
)


def _is_mock(brief: dict, listing: dict) -> bool:
    return (brief.get("listing") or {}).get("source") == "mock" or (listing or {}).get("source") == "mock"


def _sha1_file(p: Path) -> str:
    import hashlib
    return hashlib.sha1(p.read_bytes()).hexdigest()[:12]


def _json_from(out: str):
    a, b = out.find("{"), out.rfind("}")
    return json.loads(out[a: b + 1]) if a >= 0 and b > a else None


def _fetch_routes(map_py: Path, geo: dict, pois: list, brief: dict, city: str, route_p: Path) -> None:
    """map/route.json: Amap route distance/duration from the community to the nearest metro (+ map.commute_to)."""
    items, notes = [], []
    origin = f"{geo['lng']},{geo['lat']}"
    targets = []
    metro = [x for x in pois if x.get("location") and x.get("distance_m") and ("地铁" in str(x.get("name")) or "地铁" in str(x.get("type")))]
    if metro:
        m = min(metro, key=lambda x: x["distance_m"])
        targets.append(("nearest_metro", m.get("name"), m["location"], "walking"))
    commute_to = (brief.get("map") or {}).get("commute_to")
    if commute_to:
        code, out = _run(map_py, ["place", str(commute_to), "--city", city, "--limit", "1"])
        try:
            rows = json.loads(out[out.find("["): out.rfind("]") + 1]) if code == 0 else []
        except Exception:
            rows = []
        if rows and rows[0].get("location"):
            targets.append(("commute_to", rows[0].get("name") or commute_to, rows[0]["location"], "all"))
        else:
            notes.append(f"commute_to 未能解析：{commute_to}")
    for kind, name, loc, mode in targets:
        try:
            code, out = _run(map_py, ["route", origin, loc, "--mode", mode, "--city", city])
            data = _json_from(out) if code == 0 else None
            routes = (data or {}).get("routes")
            routes = routes if isinstance(routes, list) else ([routes] if routes else [])
            for rt in routes:
                if rt.get("distance_m") is not None and rt.get("duration_s") is not None:
                    items.append({"kind": kind, "to": name, "mode": rt.get("mode"), "distance_m": int(rt["distance_m"]),
                                  "duration_s": int(rt["duration_s"]), "source": "amap route"})
        except Exception as e:  # network / key problems: no numbers rather than invented ones
            notes.append(f"route {name}: {e}")
    save_json(route_p, {"origin": {"lng": geo["lng"], "lat": geo["lat"]}, "items": items, "notes": notes,
                        "source": "amap", "fetched_at": now_iso()})


def _to_4x3_jpg(src: Path, out: Path) -> None:
    try:
        from PIL import Image
        im = Image.open(src).convert("RGB")
        w, h = im.size
        if w * 3 > h * 4:  # too wide -> crop width
            nw = int(h * 4 / 3)
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:  # too tall -> crop height
            nh = int(w * 3 / 4)
            im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        im.resize((1440, 1080)).save(out, quality=92)
    except ImportError:
        subprocess.run(["ffmpeg", "-y", "-i", str(src), "-vf", "scale=1440:1080:force_original_aspect_ratio=increase,crop=1440:1080",
                        str(out)], check=True, capture_output=True)


def _repaint_step(project_dir: Path, brief: dict, listing: dict, geo: dict) -> dict:
    """flova repaint hand-off (agent-performed). Raises NeedInput (exit 3) until map/base_ai.png exists."""
    map_dir = project_dir / "map"
    sat_p, base_ai, req_p, geo_p = map_dir / "satellite_4x3.jpg", map_dir / "base_ai.png", map_dir / "flova_request.json", map_dir / "geo.json"
    amap_copy = map_dir / "amap_satellite_4x3.jpg"
    live = geo.get("live_status") == "ok"
    allowed = bool((brief.get("flova") or {}).get("allowed", True))
    reason = None
    if not live:
        reason = "no live Amap data -> labelled schematic base"
    elif _is_mock(brief, listing):
        reason = "mock -> no repaint"
    elif not allowed:
        reason = "flova.allowed=false -> no repaint"
    if reason:
        if live and geo.get("base") == "ai_repaint" and amap_copy.exists():
            shutil.copy2(amap_copy, sat_p)  # repaint switched off: back to the real Amap imagery
            geo["attribution"] = ATTRIBUTION
        geo["base"] = "amap" if live else "schematic"
        geo["repaint"] = {"status": "skipped", "reason": reason}
        save_json(geo_p, geo)
        return {"base": geo["base"], "repaint": "skipped"}

    rel_dir = project_dir.name
    request = {
        "purpose": "Repaint the Amap static map into a stylised base map (agent-performed via the flova-image MCP; repo Python cannot call MCP). Image only, no video.",
        "tool": FLOVA_TOOL,  # flova-image MCP (declared in the repo .mcp.json / .grok/config.toml): image generation only, never generate_video
        "model": FLOVA_MODEL,
        "prompt": FLOVA_PROMPT,
        "source_image": "map/static.png",
        "output_image": "map/base_ai.png",
        "params": dict(FLOVA_PARAMS),
        "credits": "handled by the flova MCP; not a limit. If generation fails (including for credit reasons) report the error to the user; do not work around it.",
        "label": ATTR_AI,
        "status": "pending",
        "created_at": (load_json(req_p).get("created_at") if req_p.exists() else None) or now_iso(),
    }
    if not base_ai.exists():
        save_json(req_p, request)
        geo["base"] = "amap"
        geo["repaint"] = {"status": "pending", "request": "map/flova_request.json"}
        geo.pop("map_motion", None)  # video map motion is retired (video generation is off by default)
        save_json(geo_p, geo)
        proj = project_dir.as_posix()
        text = (
            f"map:fetch 需要 Agent 用 flova 图像生成重绘地图底图（仓库 Python 调不了 MCP；只生图，不生成视频）：\n"
            f"    1. 读 {proj}/map/flova_request.json（prompt / source_image / output_image / params）\n"
            f"    2. 调 flova-image 的 generate_image（model={FLOVA_MODEL}，gpt-image-2.5 系列）：prompt=request.prompt，参考图={proj}/map/static.png，参数 profile=\"kid4\"、original=true；不要调 generate_video\n"
            f"    3. 把返回的无水印原图保存为 {proj}/map/base_ai.png\n"
            f"    4. 重跑同一命令（或 npm run map:fetch -- {proj}）\n"
            f"    积分由 flova MCP 自行处理，不是限制；若生成失败（含积分原因），把错误原文告诉用户，不要绕过，不要用邀请/多账号等方式。"
        )
        print("\n" + text)
        raise NeedInput([{"key": "map.base_ai", "q": text, "blocks": "map:fetch"}])

    sha = _sha1_file(base_ai)
    if geo.get("base") != "ai_repaint" or geo.get("base_ai_sha1") != sha:
        if geo.get("base") != "ai_repaint" and sat_p.exists():
            shutil.copy2(sat_p, amap_copy)  # keep the real Amap satellite next to the AI base
        _to_4x3_jpg(base_ai, sat_p)
        geo.update({"base": "ai_repaint", "base_ai": "map/base_ai.png", "base_ai_sha1": sha, "attribution": ATTR_AI,
                    "flova_prompt": FLOVA_PROMPT, "flova_params": dict(FLOVA_PARAMS), "flova_model": FLOVA_MODEL})
        geo.pop("map_motion", None)
    request["status"] = "done"
    save_json(req_p, request)
    geo["repaint"] = {"status": "done"}
    save_json(geo_p, geo)
    return {"base": "ai_repaint", "repaint": "done"}


def run(project_dir: Path, force: bool = False) -> dict:
    map_dir = project_dir / "map"
    geo_p = map_dir / "geo.json"
    sat_p = map_dir / "satellite_4x3.jpg"
    static_p = map_dir / "static.png"
    pois_p = map_dir / "pois.json"
    if all(p.exists() for p in (geo_p, sat_p, static_p, pois_p)) and not force:
        _brief = load_brief(project_dir)
        _lst = load_json(project_dir / "listing.json") if (project_dir / "listing.json").exists() else {}
        return {"skipped": True, **_repaint_step(project_dir, _brief, _lst, load_json(geo_p))}

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
                    _fetch_routes(map_py, geo, pois, brief, city, map_dir / "route.json")
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
        attribution = ATTR_SCHEMATIC
    else:
        attribution = ATTRIBUTION

    geo["attribution"] = attribution
    geo["fetched_at"] = now_iso()
    save_json(geo_p, geo)
    # Ensure static.png exists even on success path when only jpg was written
    if not static_p.exists() and sat_p.exists():
        shutil.copy2(sat_p, static_p)
    # Satellite tiles can fail (network/SSL) while the Amap road map worked: the map is mandatory, so use the real road map.
    if not sat_p.exists() and static_p.exists():
        shutil.copy2(static_p, sat_p)
    result = {"live_status": live_status, "query": query, "attribution": attribution}
    result.update(_repaint_step(project_dir, brief, listing, geo))  # may raise NeedInput (exit 3)
    return result
