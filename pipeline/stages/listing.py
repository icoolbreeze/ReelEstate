"""Stage 1 · listing:fetch — pull CRM listing → listing.json + raw photos (allowlisted fields only).

Uses local crm_connector HTTP API (127.0.0.1:8020). Never reads run/browser_state.json or any
cookies / tokens. On CRM_AUTH_REQUIRED (or any transport failure) and brief.listing.source=="mock",
writes a clearly fictional fixture so the rest of the pipeline can be tested.
"""
from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from .common import PLACEHOLDER, NeedInput, load_brief, load_json, now_iso, save_json

CRM_BASE = os.environ.get("CC_BASE_URL", "http://127.0.0.1:8020").rstrip("/") + "/api/v1"
# Public CDN needs a size suffix (docs/rental-image-cdn.md); without it img.ljcdn.com returns 403.
IMG_SUFFIX = ".1500x.jpg"
THUMB_SUFFIX = ".450x.jpg"

# Fields that may leave the CRM. Everything else (maintainer phone, exact unit, CRM urls, …) is dropped.
ALLOWLIST = (
    "listing_id", "community", "layout", "area_sqm", "monthly_rent_yuan", "orientation",
    "del_type", "rent_mode_label", "floor_desc", "total_floors", "listed_days",
    "bedroom_amount", "hall_amount", "bathroom_amount", "biz_circle", "resblock_name",
    "title_image_url", "floor_plan_image_url", "maintain_org",
)
# Fields check requires for a rental video; missing ones are written as 待填 so check fails loudly.
REQUIRED_FOR_PROJECT = ("community", "layout", "area_sqm", "monthly_rent_yuan", "orientation", "floor_desc")


def _http(method: str, path: str, body: dict | None = None, timeout: int = 20) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        CRM_BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(detail)
        except Exception:
            payload = {"raw": detail}
        code = (payload.get("detail") or {}).get("code") if isinstance(payload.get("detail"), dict) else payload.get("code")
        raise RuntimeError(f"CRM HTTP {e.code} {code or ''}: {detail[:400]}") from e
    except Exception as e:
        raise RuntimeError(f"CRM unreachable ({e})") from e


def _cdn(url: str | None, suffix: str = IMG_SUFFIX) -> str | None:
    if not url:
        return None
    if any(url.endswith(s) for s in (".450x.jpg", ".750x.jpg", ".800x.jpg", ".1500x.jpg")):
        return url
    return url + suffix


def _download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ReelEstate/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return dest.stat().st_size > 1000
    except Exception:
        return False


def sanitize(raw: dict) -> dict:
    out = {k: raw.get(k) for k in ALLOWLIST}
    out["biz_circle"] = raw.get("biz_circle") or raw.get("bizCircleName")
    out["source"] = "crm"
    out["fetched_at"] = now_iso()
    out["title_image_url"] = _cdn(out.get("title_image_url"))
    out["floor_plan_image_url"] = _cdn(out.get("floor_plan_image_url"))
    # Coarse floor only — never unit / room / building number.
    floor = out.get("floor_desc") or ""
    if any(x in floor for x in ("室", "单元", "号楼", "#")):
        out["floor_desc"] = PLACEHOLDER
    for k in REQUIRED_FOR_PROJECT:
        if out.get(k) in (None, "", 0):
            out[k] = PLACEHOLDER
    return out


def mock_listing(brief: dict) -> dict:
    """Clearly fictional fixture used when CRM is unavailable / not logged in."""
    community = (brief.get("listing") or {}).get("community_keyword") or "示例云栖苑"
    return {
        "listing_id": "MOCK-RENTAL-20260928-001",
        "community": community,
        "layout": "2室1厅1卫",
        "area_sqm": 89.0,
        "monthly_rent_yuan": 4800,
        "orientation": "南北通透",
        "del_type": 2,
        "rent_mode_label": "整租",
        "floor_desc": "中楼层",
        "total_floors": 18,
        "listed_days": 12,
        "bedroom_amount": 2,
        "hall_amount": 1,
        "bathroom_amount": 1,
        "biz_circle": "示例商圈",
        "resblock_name": community,
        "title_image_url": None,
        "floor_plan_image_url": None,
        "maintain_org": "示例星河房地产经纪有限公司",
        "source": "mock",
        "fetched_at": now_iso(),
        "_comment": "虚构示例，不得发布。live CRM 未拉取（未登录或服务未开）。",
    }


def mock_wall(brief: dict, picked: dict) -> list[dict]:
    """6 fictional cards around the picked listing so the wall stage has something to animate."""
    community = picked["community"]
    rents = [4200, 4500, 4800, 5100, 5300, 5600]
    layouts = ["1室1厅1卫", "2室1厅1卫", "2室2厅1卫", "3室1厅1卫", "2室1厅1卫", "3室2厅1卫"]
    areas = [55, 72, 89, 98, 86, 112]
    orients = ["朝南", "南北通透", "南北通透", "朝东", "朝南", "南北通透"]
    floors = ["低楼层", "中楼层", "中楼层", "高楼层", "中楼层", "高楼层"]
    cards = []
    for i in range(6):
        cards.append({
            "listing_id": f"MOCK-RENTAL-20260928-{i+11:03d}",
            "community": community if i != 4 else community + "东区",
            "layout": layouts[i],
            "area_sqm": areas[i],
            "monthly_rent_yuan": rents[i],
            "orientation": orients[i],
            "floor_desc": floors[i],
            "title_image_url": None,
            "source": "mock",
        })
    # Ensure the picked id is in the wall.
    cards[2] = {**picked, "listing_id": picked["listing_id"]}
    return cards


def _search(brief: dict) -> list[dict]:
    lst = brief.get("listing", {})
    body: dict = {"scope": (lst.get("filters") or {}).get("scope", "all"), "page": 1, "page_size": 12}
    if lst.get("listing_id"):
        body["listing_id"] = lst["listing_id"]
    elif lst.get("community_keyword"):
        body["community_keyword"] = lst["community_keyword"]
    else:
        raise NeedInput([{"key": "listing.target", "q": "需要房源编号或小区名才能搜。", "blocks": "listing:fetch"}])
    f = lst.get("filters") or {}
    if f.get("rooms"):
        body["rooms"] = f["rooms"]
    if f.get("monthly_rent_yuan"):
        body["monthly_rent_yuan"] = f["monthly_rent_yuan"]
    if f.get("area_sqm"):
        body["area_sqm"] = f["area_sqm"]
    if f.get("orientations"):
        body["orientations"] = f["orientations"]
    page = _http("POST", "/listings/rental/search", body)
    return page.get("items") or []


def _detail(listing_id: str) -> dict:
    return _http("GET", f"/listings/rental/{listing_id}")


def _prospect(listing_id: str) -> dict:
    try:
        return _http("GET", f"/listings/rental/{listing_id}/prospect")
    except Exception:
        return {"photos": [], "floor_plan_url": None, "has_survey_photo": False}


def run(project_dir: Path, force: bool = False) -> dict:
    out_listing = project_dir / "listing.json"
    out_wall = project_dir / "wall_candidates.json"
    raw_dir = project_dir / "raw" / "listing"
    if out_listing.exists() and out_wall.exists() and not force:
        return {"skipped": True, "reason": "listing.json exists"}

    brief = load_brief(project_dir)
    use_mock = (brief.get("listing") or {}).get("source") == "mock"
    live_error = None
    items: list[dict] = []
    if not use_mock:
        try:
            items = _search(brief)
        except Exception as e:
            live_error = str(e)
            if "CRM_AUTH_REQUIRED" in live_error or "unreachable" in live_error.lower():
                use_mock = True
            else:
                raise

    if use_mock:
        picked = mock_listing(brief)
        wall_raw = mock_wall(brief, picked)
        live_status = "untested"
        live_note = live_error or "brief.listing.source=mock"
    else:
        if not items:
            raise NeedInput([{"key": "listing.target", "q": "CRM 搜索结果为空，请换小区名 / 放宽筛选 / 给具体房源编号。", "blocks": "listing:fetch"}])
        pick = (brief.get("listing") or {}).get("pick") or items[0]["listing_id"]
        match = next((x for x in items if x.get("listing_id") == pick), items[0])
        detail = _detail(match["listing_id"])
        picked = sanitize({**match, **detail})
        wall_raw = [sanitize(x) for x in items[:12]]
        live_status = "ok"
        live_note = None
        # Prospect photos (REAL only).
        prospect = _prospect(picked["listing_id"])
        raw_dir.mkdir(parents=True, exist_ok=True)
        photos_meta = []
        exclude = set((brief.get("photos") or {}).get("exclude") or [])
        for i, ph in enumerate(prospect.get("photos") or []):
            if ph.get("image_type") and ph["image_type"] != "REAL":
                continue
            url = _cdn(ph.get("url"))
            if not url:
                continue
            name = f"p{i+1:02d}_{(ph.get('room_name') or 'room').replace('/', '-')}.jpg"
            if name in exclude:
                continue
            dest = raw_dir / name
            if _download(url, dest):
                photos_meta.append({"file": f"raw/listing/{name}", "room": ph.get("room_name"), "url_suffix": IMG_SUFFIX})
        fp_url = _cdn(prospect.get("floor_plan_url") or picked.get("floor_plan_image_url"))
        if fp_url and _download(fp_url, raw_dir / "floorplan.jpg"):
            photos_meta.append({"file": "raw/listing/floorplan.jpg", "room": "户型图", "url_suffix": IMG_SUFFIX})
        picked["photos"] = photos_meta

    if "photos" not in picked:
        picked["photos"] = []
    picked["live_status"] = live_status
    if live_note:
        picked["live_note"] = live_note

    save_json(out_listing, picked)
    save_json(out_wall, {"items": wall_raw, "picked": picked["listing_id"], "fetched_at": now_iso(), "live_status": live_status})
    return {"listing": picked["listing_id"], "wall": len(wall_raw), "live_status": live_status, "photos": len(picked["photos"])}
