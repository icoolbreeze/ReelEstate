#!/usr/bin/env python3
"""Fetch real Amap POIs + routes for an episode and write <episode>/pois.json.

Usage:  python pipeline/amap_fetch.py episodes/ep07-xihu/episode.json [--city 杭州]
Needs the map-tools skill (map.py). Location resolved in this order:
  $MAP_TOOLS_PY, ~/.agents/skills/map-tools/scripts/map.py
API keys are read by map.py itself from ~/.config/map-tools/keys.json  (never printed, never copied).
Every distance written here is an Amap route distance (walking/driving), never straight-line,
and no walking *time* is surfaced to the video (compliance: distances only).
"""
import argparse, json, os, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from coords import Plane, haversine_m

def map_py():
    c = [os.environ.get("MAP_TOOLS_PY"), str(Path.home() / ".agents/skills/map-tools/scripts/map.py")]
    for p in c:
        if p and Path(p).exists():
            return p
    sys.exit("map.py not found: set MAP_TOOLS_PY")

def run(args):
    out = subprocess.run([sys.executable, map_py(), *args], capture_output=True, text=True, encoding="utf-8")
    if out.returncode:
        sys.exit(f"map.py failed: {' '.join(args[:2])}: {out.stderr[-400:]}")
    return json.loads(out.stdout)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--city", default="杭州")
    a = ap.parse_args()
    ep_path = Path(a.episode)
    ep = json.loads(ep_path.read_text(encoding="utf-8"))
    plane = Plane.from_cfg(ep["plane"])
    L = ep["listing"]["lnglat"]
    org = f"{L[0]},{L[1]}"
    rawdir = ep_path.parent / "raw"; rawdir.mkdir(exist_ok=True)
    cache = {}
    pois = []
    for q in ep["poiQueries"]:
        if q["query"] not in cache:
            cache[q["query"]] = run(["place", q["query"], "--source", "amap", "--city", a.city, "--limit", "10"])
        rows = cache[q["query"]]
        hit = next((r for r in rows if r["name"] == q["pick"]), None)
        if not hit:
            print(f"!! {q['id']}: '{q['pick']}' not in results for '{q['query']}': {[r['name'] for r in rows]}", file=sys.stderr)
            continue
        lng, lat = map(float, hit["location"].split(","))
        rec = {k: q[k] for k in ("id", "kind", "label", "sub")}
        rec.update(amapName=hit["name"], address=hit["address"], typecode=hit["typecode"], lnglat=[lng, lat],
                   xy=list(plane.xy(lng, lat)), straight_m=round(haversine_m(L, (lng, lat))))
        for m in q["modes"]:
            r = run(["route", org, f"{lng},{lat}", "--mode", m])["routes"]
            (rawdir / f"route_{q['id']}_{m}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
            rec[f"{m}_m"] = r["distance_m"]
            key = {"walking": "walk_path", "driving": "drive_path"}.get(m)
            if key and r.get("polyline"):
                rec[key] = [list(plane.xy(*p)) for p in r["polyline"]]
        pois.append(rec)
        print(f"{q['id']:9s} {hit['name']}  walk {rec.get('walking_m')} m  drive {rec.get('driving_m', '-')} m  (straight {rec['straight_m']} m)")
    out = {"source": "Amap Web Service via map-tools/map.py (place + route), GCJ-02; xy = episode plane",
           "listing": {"lnglat": L, "xy": list(plane.xy(*L))}, "pois": pois}
    (ep_path.parent / "pois.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", ep_path.parent / "pois.json")

if __name__ == "__main__":
    main()
