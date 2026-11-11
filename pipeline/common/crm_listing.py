#!/usr/bin/env python3
"""Read-only rental facts from crm_connector (BeikeMicroservice) for a listing episode.

Moved from the retired pipeline/stages/listing.py (2026-10-30); same allowlist and image rules (docs/crm.md).
Needs the SSH forward first:  ssh -N -L 8020:127.0.0.1:8020 beike-server
Never reads run/browser_state.json, cookies or tokens; never calls house-info.

  python pipeline/common/crm_listing.py projects/listing/<ep> [--force]
reads episode.yaml listing.ref and writes data/listing.json (allowlisted fields only) and
data/listing_prospect.json (survey photo URLs with the CDN size suffix).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLACEHOLDER = "待填"
CRM_BASE = os.environ.get("CC_BASE_URL", "http://127.0.0.1:8020").rstrip("/") + "/api/v1"
# Public CDN needs a size suffix; without it img.ljcdn.com returns 403.
IMG_SUFFIX = ".1500x.jpg"
THUMB_SUFFIX = ".450x.jpg"
SIZED = (".450x.jpg", ".750x.jpg", ".800x.jpg", ".1500x.jpg")

# Fields that may leave the CRM. Everything else (maintainer phone, exact unit, CRM urls, ...) is dropped.
ALLOWLIST = (
    "listing_id", "community", "layout", "area_sqm", "monthly_rent_yuan", "orientation",
    "del_type", "rent_mode_label", "floor_desc", "total_floors", "listed_days",
    "bedroom_amount", "hall_amount", "bathroom_amount", "biz_circle", "resblock_name",
    "title_image_url", "floor_plan_image_url", "maintain_org",
)
# Missing ones are written as 待填 so the compliance check fails loudly.
REQUIRED = ("community", "layout", "area_sqm", "monthly_rent_yuan", "orientation", "floor_desc")


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def http(method: str, path: str, body: dict | None = None, timeout: int = 20) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(CRM_BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(detail)
        except ValueError:
            payload = {"raw": detail}
        code = (payload.get("detail") or {}).get("code") if isinstance(payload.get("detail"), dict) else payload.get("code")
        raise RuntimeError(f"CRM HTTP {e.code} {code or ''}: {detail[:400]}") from e
    except Exception as e:
        raise RuntimeError(f"CRM unreachable ({e})") from e


def cdn(url: str | None, suffix: str = IMG_SUFFIX) -> str | None:
    if not url:
        return None
    return url if url.endswith(SIZED) else url + suffix


def download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ReelEstate/1.0"})
        dest.parent.mkdir(parents=True, exist_ok=True)
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
    out["title_image_url"] = cdn(out.get("title_image_url"))
    out["floor_plan_image_url"] = cdn(out.get("floor_plan_image_url"))
    floor = out.get("floor_desc") or ""                 # coarse floor only, never unit / room / building
    if any(x in floor for x in ("室", "单元", "号楼", "#")):
        out["floor_desc"] = PLACEHOLDER
    for k in REQUIRED:
        if out.get(k) in (None, "", 0):
            out[k] = PLACEHOLDER
    return out


def search(listing_id: str = "", community_keyword: str = "", filters: dict | None = None, page_size: int = 12) -> list[dict]:
    f = filters or {}
    body: dict = {"scope": f.get("scope", "all"), "page": 1, "page_size": page_size}
    if listing_id:
        body["listing_id"] = listing_id
    elif community_keyword:
        body["community_keyword"] = community_keyword
    else:
        raise ValueError("search needs a listing id or a community keyword")
    for key in ("rooms", "monthly_rent_yuan", "area_sqm", "orientations"):
        if f.get(key):
            body[key] = f[key]
    return http("POST", "/listings/rental/search", body).get("items") or []


def detail(listing_id: str) -> dict:
    return http("GET", f"/listings/rental/{listing_id}")


def prospect(listing_id: str) -> dict:
    try:
        return http("GET", f"/listings/rental/{listing_id}/prospect")
    except RuntimeError:
        return {"photos": [], "floor_plan_url": None, "has_survey_photo": False}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode")
    ap.add_argument("--force", action="store_true", help="overwrite data/listing.json")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(REPO))
    from pipeline.common.workspace import episode_path
    from pipeline.common.voice_config import read_yaml
    ep = episode_path(a.episode)
    cfg = read_yaml(ep / "episode.yaml")
    if cfg.get("category") not in ("rental",):
        raise ValueError("crm_listing only serves rental episodes (resale / new-home are not on the connector)")
    ref = str((cfg.get("listing") or {}).get("ref") or "").strip()
    if not ref:
        raise ValueError("episode.yaml listing.ref is empty")
    out = ep / "data/listing.json"
    if out.exists() and not a.force:
        print("exists:", out.relative_to(REPO).as_posix(), "(use --force)")
        return 0
    facts = sanitize(detail(ref))
    pros = prospect(ref)
    photos = [cdn(p.get("url") if isinstance(p, dict) else p) for p in pros.get("photos") or []]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (ep / "data/listing_prospect.json").write_text(json.dumps({
        "photos": [p for p in photos if p], "floor_plan_url": cdn(pros.get("floor_plan_url")),
        "has_survey_photo": bool(pros.get("has_survey_photo")), "fetched_at": now_iso()},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote data/listing.json + data/listing_prospect.json (allowlisted fields only)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)
