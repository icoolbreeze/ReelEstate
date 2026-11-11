#!/usr/bin/env python3
"""Collect footage + annotation JSON into the Remotion project (run after every Muse download / tracking pass).

usage: python pipeline/common/sync_assets.py projects/listing/<ep> [--proj proj] [--footage footage] [--ann annotations]
For every shot in <episode>/shots.json:
  footage/shots/<ID>.mp4    -> copied to proj/public/footage/, kind "video"; annotations/<ID>.json (tracked) attached
  else footage/raw|selects_dlogm/<ID>.* or the footage/raw_manifest.json row with shot=<ID>
                            -> restored Rec.709 proxy (trimmed into footage/shots/<ID>.mp4 when in/out are set)
  else placeholder image    -> kind "image" (slow Ken Burns), boxes from shots.json in image space
  else placeholder video    -> kind "video" (presenter stand-in, muted)
  else                      -> kind "pending" (labelled card so the cut still renders end-to-end)
Writes proj/src/episode/{footage,annotations}.json and copies episode.json + pois.json into proj/src/episode/.
"""
import argparse, json, subprocess
from pathlib import Path
from .workspace import project_for

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent

from .media import probe, img_size, materialize
from .color_restore import restored_for, VIDEO_EXT
from .raw_manifest import clip_for_shot


def trimmed_shot(src, dst, t_in, t_out):
    """Re-encode the in/out span of a Rec.709 proxy into footage/shots/<ID>.mp4 (frame-accurate)."""
    if dst.is_file() and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name("." + dst.stem + ".tmp.mp4")
    span = ["-ss", "%.3f" % float(t_in or 0)] + (["-to", "%.3f" % float(t_out)] if t_out is not None else [])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), *span, "-map", "0:v:0", "-map", "0:a:0?",
                    "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(dst)
    return dst

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode"); ap.add_argument("--proj", default=None, help="episode-owned workspace only")
    ap.add_argument("--footage", default=None); ap.add_argument("--ann", default=None)
    a = ap.parse_args()
    ep = Path(a.episode).resolve()
    proj = project_for(ep, a.proj)
    fdir = Path(a.footage) if a.footage else ep / "footage"; adir = Path(a.ann) if a.ann else ep / "annotations"
    S = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
    pub = proj / "public"; (pub / "footage").mkdir(parents=True, exist_ok=True)
    footage, anns = {}, {}
    for s in S["shots"]:
        cid, ph = s["id"], s.get("placeholder", {})
        labels = ph.get("labelsOverride") or s.get("annotate", [])
        src = fdir / "shots" / f"{cid}.mp4"
        span = None
        if not src.exists():   # camera clip named <ID>.* in footage/raw or footage/selects_dlogm
            cams = [p for d in ("raw", "selects_dlogm") for p in sorted((fdir / d).glob(f"{cid}.*")) if p.suffix.lower() in VIDEO_EXT]
            if cams:
                src = cams[0]
            else:                # DJI / phone names: footage/raw_manifest.json maps the clip to this shot
                hit = clip_for_shot(ep, cid)
                if hit and hit[0].is_file():
                    src, span = hit[0], hit[1:]
        if src.exists():
            src = restored_for(ep, src, "render")   # D-Log M -> restored H.264 proxy; unrestored D-Log M raises
            if span and (span[0] is not None or span[1] is not None):
                src = trimmed_shot(src, fdir / "shots" / f"{cid}.mp4", *span)
            dst = pub / "footage" / f"{cid}.mp4"
            if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                materialize(src, dst)
            footage[cid] = {"kind": "video", "src": f"footage/{cid}.mp4", "status": "muse", **(probe(dst) or {})}
            af = adir / f"{cid}.json"
            if af.exists():
                anns[cid] = json.loads(af.read_text(encoding="utf-8"))
            elif not labels:
                pass                                    # presenter / no-annotation shot
            else:
                print(f"!! {cid}: footage present but no annotations/{cid}.json yet (run track_annotations.py)")
        elif ph.get("image"):
            footage[cid] = {"kind": "image", "src": ph["image"], "status": "placeholder", **img_size(pub / ph["image"]),
                            "kb": ph.get("kb", {"s0": 1.0, "s1": 1.07, "ox0": 0.5, "oy0": 0.5, "ox1": 0.5, "oy1": 0.45})}
            anns[cid] = {"space": "image", "method": "placeholder (hand-placed boxes on the stand-in still)",
                         "targets": [{"id": f"t{i}", "label": l[0], "sub": l[1], "kf": [[0, *b]]} for i, (l, b) in enumerate(zip(labels, ph.get("boxes", [])))]}
        elif ph.get("video"):
            footage[cid] = {"kind": "video", "src": ph["video"], "status": "placeholder", **(probe(pub / ph["video"]) or {})}
        else:
            footage[cid] = {"kind": "pending", "status": "pending", "label": s["purpose"]}
            anns[cid] = {"space": "frame", "method": "pending (labels only)", "targets": [{"id": f"t{i}", "label": l[0], "sub": l[1], "kf": []} for i, l in enumerate(labels)]}
        footage[cid]["purpose"] = s["purpose"]
    # HeyGen avatar segments: w/h come from ffprobe, so native 1440x1080 segments from export_43.mp4 (runbook 7b) fill the frame 1:1, no crop.
# Fallback (no 7b): footage/heygen/<seg>.mp4 -> clip id <seg>; 16:9 is centre-cropped to 4:3 in
    # Remotion, cx (0..1, default 0.5) from <episode>/heygen/crop.json {"HG03": 0.47} shifts the crop to the face
    hdir = fdir / "heygen"
    if hdir.exists():
        crop = json.loads((ep / "heygen/crop.json").read_text(encoding="utf-8")) if (ep / "heygen/crop.json").exists() else {}
        (pub / "footage/heygen").mkdir(parents=True, exist_ok=True)
        for src in sorted(list(hdir.glob("*.mp4")) + list(hdir.glob("*_alpha.webm"))):
            dst = pub / "footage/heygen" / src.name
            if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime: materialize(src, dst)
            footage[src.stem] = {"kind": "video", "src": f"footage/heygen/{src.name}", "status": "heygen", "cx": crop.get(src.stem, 0.5), **(probe(dst) or {})}
    # map 样板间 cards use a still from their room's clip once the footage exists (hub.json rooms[].clip, still at rooms[].stillT s)
    hubp = proj / "src/episode/hub.json"
    if hubp.exists():
        hub = json.loads(hubp.read_text(encoding="utf-8"))
        (pub / "rooms").mkdir(exist_ok=True)
        for r in hub.get("rooms", []):
            cid = r.get("clip")
            if cid and footage.get(cid, {}).get("status") == "muse":
                out = pub / "rooms" / f"{cid}.jpg"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(r.get("stillT", 1.2)), "-i", str(pub / "footage" / f"{cid}.mp4"),
                                "-frames:v", "1", "-vf", "scale=480:-1", "-q:v", "3", str(out)], check=True)
                footage[cid]["still"] = f"rooms/{cid}.jpg"
    for name in ("episode.json", "pois.json"):          # episode data the composition imports
        if (ep / name).exists():
            materialize(ep / name, proj / "src/episode" / name)
    (proj / "src/episode/footage.json").write_text(json.dumps(footage, ensure_ascii=False, indent=1), encoding="utf-8")
    (proj / "src/episode/annotations.json").write_text(json.dumps(anns, ensure_ascii=False, indent=1), encoding="utf-8")
    # social badge rows: shared presenter profile, overridable per episode (episode.yaml `social:`)
    import yaml
    epy = yaml.safe_load((ep / "episode.yaml").read_text(encoding="utf-8")) if (ep / "episode.yaml").exists() else {}
    epy = epy or {}
    prof = REPO / "assets/presenter" / str(epy.get("presenter") or "cool-breeze") / "presenter.yaml"
    pres = yaml.safe_load(prof.read_text(encoding="utf-8")) if prof.exists() else {}
    rows = epy.get("social") or (pres or {}).get("social") or []
    (proj / "src/episode/social.json").write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    st = {}
    for v in footage.values(): st[v["status"]] = st.get(v["status"], 0) + 1
    print("footage:", st)

if __name__ == "__main__":
    main()

