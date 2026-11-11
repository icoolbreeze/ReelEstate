#!/usr/bin/env python3
"""Turn <episode>/shots.json into pasteable Muse messages (muse/batchN.txt) + muse/manifest.json.

usage: python pipeline/make_muse_batches.py episodes/ep07-xihu [--out muse] [--per 5]
Each batch file is one complete Chinese message asking Muse for N separate numbered videos, IDs listed
so downloads can be matched back (save each download as footage/<ID>.mp4, then run sync_assets.py).
"""
import argparse, json
from pathlib import Path

ORDER = None  # keep shots.json order

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode"); ap.add_argument("--out", default="muse"); ap.add_argument("--per", type=int, default=5)
    ap.add_argument("--batches", default="", help="explicit grouping, e.g. 'LR1,LR2,BR1,BR2,KB1;KB2,ENV1,...'")
    ap.add_argument("--box-root", default=".", help="only used to fill manifest 'target' (episode root)")
    a = ap.parse_args()
    ep = Path(a.episode); S = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
    shots = {s["id"]: s for s in S["shots"]}
    if a.batches:
        groups = [g.split(",") for g in a.batches.split(";")]
    else:
        ids = [s["id"] for s in S["shots"]]; groups = [ids[i:i + a.per] for i in range(0, len(ids), a.per)]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    manifest = {"episode": ep.name, "note": "Save each Muse download as footage/shots/<ID>.mp4 (targetRel). Then: python pipeline/common/sync_assets.py projects/listing/" + ep.name,
                "count": sum(len(g) for g in groups), "clips": []}
    for bi, g in enumerate(groups, 1):
        n = len(g)
        msg = [f"请帮我生成以下 {n} 条【独立的】视频：每条单独生成、单独输出，不要合并成一条，也不要在视频里加字幕。",
               f"编号用于我下载后对应文件，请按顺序输出并在每条结果旁标注编号（{'、'.join(g)}）。", ""]
        for k, cid in enumerate(g, 1):
            s = shots[cid]
            if s["kind"] == "presenter":
                body = f"{S['presenterSpec']}「{s['say']}」{s.get('extra', '')}"
            else:
                body = f"{s['prompt']}{S['brollSpec']}"
            msg += [f"{k}）【{cid}】{s['purpose']}", body, ""]
            manifest["clips"].append({"id": cid, "batch": bi, "index": k, "kind": s["kind"], "description": s["purpose"], "lines": s["lines"],
                                      "annotate": [{"label": l, "sub": e} for l, e in s.get("annotate", [])],
                                      "targetRel": f"footage/shots/{cid}.mp4", "target": f"{a.box_root}/footage/shots/{cid}.mp4",
                                      "audio": "presenter clips: Muse audio is not lip-synced; final mix uses TTS, clip is muted" if s["kind"] == "presenter" else "unused"})
        msg += [f"一共 {n} 条，请逐条分别输出（{'、'.join(g)}）。"]
        (out / f"batch{bi}.txt").write_text("\n".join(msg) + "\n", encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(groups)} batches, {manifest['count']} clips ->", out)

if __name__ == "__main__":
    main()
