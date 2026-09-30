"""Stage 4 · assets:import — seed project stock media + write assets/manifest.json.

flova is NOT called from this stage (the agent calls the flova-image MCP declared in the repo
.mcp.json / .grok/config.toml when the user allowed it in brief.flova). Video: generate_video with
model wan-3.0-prime and a reference image, ONLY when brief.flova.video_allowed is true (default false: no video
generation anywhere, including the map). Images: generate_image, model gpt-image-2.5-sunburst
(final / polished / brand) or gpt-image-2.5-flare (daily / batch / social / quick iteration).
This stage only records whatever is already under raw/ / assets/ and copies the warehouse stock
placeholders used by the sample.
check fails on missing or watermarked entries; AI entries must carry ai=true so the renderer
paints the AI生成 badge.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from .common import REPO_ROOT, load_brief, load_json, now_iso, save_json

WAREHOUSE = REPO_ROOT / "assets" / "warehouse"  # local stock library (media gitignored; see assets/warehouse/README.md)


def _sha1(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def _entry(rel: str, **meta) -> dict:
    return {
        "file": rel,
        "source": meta.get("source", "unknown"),
        "model": meta.get("model"),
        "prompt": meta.get("prompt"),
        "watermarked": bool(meta.get("watermarked", False)),
        "license": meta.get("license", "unknown"),
        "ai": bool(meta.get("ai", False)),
        "usage": meta.get("usage"),
        "attribution": meta.get("attribution"),
        "source_tag": meta.get("source_tag"),
        "sha1": meta.get("sha1"),
        "recorded_at": now_iso(),
    }


STOCK_CATALOG = [
    # (warehouse relative, project relative, meta)
    ("interiors/living.jpg", "raw/stock/living.jpg",
     {"source": "wikimedia/unsplash", "license": "CC0", "attribution": "Jarosław Ceborski / Unsplash via Wikimedia Commons",
      "source_tag": "素材来源：Unsplash · CC0"}),
    ("interiors/bedroom.jpg", "raw/stock/bedroom.jpg",
     {"source": "wikimedia/unsplash", "license": "CC0", "attribution": "Gabriel Beaudry / Unsplash via Wikimedia Commons",
      "source_tag": "素材来源：Unsplash · CC0"}),
    ("interiors/kitchen.jpg", "raw/stock/kitchen.jpg",
     {"source": "wikimedia/unsplash", "license": "CC0", "attribution": "Naomi Hébert / Unsplash via Wikimedia Commons",
      "source_tag": "素材来源：Unsplash · CC0"}),
    ("exteriors/highrise.jpg", "raw/stock/highrise.jpg",
     {"source": "wikimedia/unsplash", "license": "CC0", "attribution": "Jimmy Chang / Unsplash via Wikimedia Commons",
      "source_tag": "素材来源：Unsplash · CC0"}),
    ("exteriors/balconies.jpg", "raw/stock/balconies.jpg",
     {"source": "wikimedia/unsplash", "license": "CC0", "attribution": "Naomi Hutchinson / Unsplash via Wikimedia Commons",
      "source_tag": "素材来源：Unsplash · CC0"}),
    ("presenter/presenter.mp4", "raw/presenter.mp4",
     {"source": "pexels", "license": "Pexels License", "attribution": "cottonbro studio / Pexels #6963825",
      "source_tag": "素材来源：Pexels"}),
    ("audio/bgm.mp3", "audio/bgm.mp3",
     {"source": "mixkit", "license": "Mixkit Free License", "attribution": "Mixkit Sweet September (#282)",
      "source_tag": "BGM：Mixkit"}),
    ("audio/whoosh.mp3", "audio/sfx_whoosh.mp3",
     {"source": "mixkit", "license": "Mixkit Free License", "attribution": "Mixkit swoosh-quick (#166)"}),
    ("audio/click.mp3", "audio/sfx_click.mp3",
     {"source": "mixkit", "license": "Mixkit Free License", "attribution": "Mixkit switch-click-quick (#2582)"}),
]


def seed_warehouse_into_project(project_dir: Path) -> list[dict]:
    entries = []
    for src_rel, dest_rel, meta in STOCK_CATALOG:
        src = WAREHOUSE / src_rel
        dest = project_dir / dest_rel
        if not src.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(src, dest)
        entries.append(_entry(dest_rel, sha1=_sha1(dest), **meta))
    return entries


def scan_existing(project_dir: Path, existing: list[dict]) -> list[dict]:
    """Record files already under raw/ and assets/ that are not yet in the manifest."""
    known = {e["file"] for e in existing}
    out = list(existing)
    for folder in ("raw", "assets"):
        root = project_dir / folder
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm", ".mp3", ".wav"}:
                continue
            rel = p.relative_to(project_dir).as_posix()
            if rel in known:
                continue
            if rel.startswith("raw/wall/"):
                covers = project_dir / "raw" / "wall" / "_covers.json"
                meta = (load_json(covers) if covers.exists() else {}).get(rel, {})
                e = _entry(rel, sha1=_sha1(p), **{k: v for k, v in meta.items() if k != "watermarked"})
                e["watermarked"] = meta.get("watermarked", None)
                out.append(e)
                known.add(rel)
                continue
            if rel.startswith("raw/listing/"):
                lj = load_json(project_dir / "listing.json") if (project_dir / "listing.json").exists() else {}
                mock = lj.get("source") == "mock"
                e = _entry(rel, source="mock" if mock else "crm", sha1=_sha1(p),
                           license="虚构示例" if mock else "经纪机构实勘图（业主委托范围内）",
                           attribution="实勘图" if not mock else "示例", source_tag=None)
                e["watermarked"] = False if mock else None  # CRM photos: human must confirm no ke.com/lianjia watermark
                out.append(e)
                known.add(rel)
                continue
            # Default: assume user-provided real footage (not AI, not watermarked). Agent must correct if wrong.
            out.append(_entry(rel, source="user", license="user-owned", attribution="用户提供",
                              source_tag="素材来源：实拍", sha1=_sha1(p)))
            known.add(rel)
    # Map imagery — when map:fetch repainted the Amap map (map/base_ai.png -> satellite_4x3.jpg) the still frame is an AI asset.
    geo = load_json(project_dir / "map" / "geo.json") if (project_dir / "map" / "geo.json").exists() else {}
    live = geo.get("live_status") == "ok"
    ai_base = geo.get("base") == "ai_repaint"
    for name, tag_ok, tag_mock in (
        ("map/satellite_4x3.jpg", "素材来源：高德卫星", "示意底图（非真实地图）"),
        ("map/static.png", "素材来源：高德路网", "示意底图（非真实地图）"),
    ):
        p = project_dir / name
        if p.exists() and name not in known:
            entry = _entry(name, source="amap" if live else "placeholder",
                           license="map-provider-terms" if live else "internal-placeholder",
                           attribution=geo.get("attribution", "地图数据"),
                           source_tag=tag_ok if live else tag_mock, sha1=_sha1(p),
                           watermarked=False)
            if ai_base and name == "map/satellite_4x3.jpg":  # flova image repaint of the Amap map (labelled AI base)
                # model comes from geo.json (written by map:fetch); never invented here so check can fail a missing one.
                entry.update(source="flova", ai=True, model=geo.get("flova_model"), prompt=geo.get("flova_prompt"),
                             usage="decorative", source_tag="AI生成底图",
                             license="flova-generated original (non-watermarked)")
            out.append(entry)
            known.add(name)
    return out


def run(project_dir: Path, force: bool = False) -> dict:
    man = project_dir / "assets" / "manifest.json"
    brief = load_brief(project_dir)
    if man.exists() and not force:
        return {"skipped": True, "entries": len(load_json(man).get("assets", []))}

    entries = seed_warehouse_into_project(project_dir)
    # Prefer listing survey photos when present (overwrite stock covers later via script).
    entries = scan_existing(project_dir, entries)

    # flova: only document policy; do not call. If the agent already dropped flova files under assets/flova/,
    # they must have been recorded with ai=true / watermarked=… — we re-tag any unknown file there.
    flova_dir = project_dir / "assets" / "flova"
    if flova_dir.is_dir():
        for p in flova_dir.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(project_dir).as_posix()
            for e in entries:
                if e["file"] == rel:
                    e["ai"] = True
                    e["source"] = e.get("source") or "flova"
                    e["source_tag"] = e.get("source_tag") or "AI生成"
                    # Never invent a model here: a video keeps wan-3.0-prime and an image must name its
                    # own gpt-image-2.5 model; a missing image model stays missing so check fails (never "wan").
                    if e.get("watermarked") is None:
                        e["watermarked"] = True  # fail closed when unknown
                    break

    if (brief.get("flova") or {}).get("allowed"):
        note = ("flova image generation allowed (credits are not a limit) — agent calls the flova-image MCP itself: "
                "images via generate_image: gpt-image-2.5-sunburst (final/polished/brand/map repaint) or gpt-image-2.5-flare "
                "(daily/batch/social/quick iteration); the map repaint (map:fetch -> map/base_ai.png) is an image job. ")
        if (brief.get("flova") or {}).get("video_allowed") is True:
            note += "Video generation explicitly allowed by the user (flova.video_allowed=true): generate_video with model wan-3.0-prime and a reference image. "
        else:
            note += "Video generation is OFF (flova.video_allowed is not true): do NOT call generate_video. "
        note += "Then re-run assets:import."
    else:
        note = "flova not allowed for this project (decorative AI clips disabled)."

    save_json(man, {"assets": entries, "built_at": now_iso(), "note": note,
                    "policy": "video generation is OFF by default (brief.flova.video_allowed); when the user explicitly enables it, video AI assets: only generate_video with model wan-3.0-prime (reference image required); "
                              "image AI assets: only generate_image with model gpt-image-2.5-sunburst or gpt-image-2.5-flare; "
                              "both accepted only as original non-watermarked files — never default an image model to wan; "
                              "never for floorplans/interiors/views/neighborhood; every AI asset carries the AI生成 label"})
    return {"entries": len(entries), "flova": bool((brief.get("flova") or {}).get("allowed"))}
