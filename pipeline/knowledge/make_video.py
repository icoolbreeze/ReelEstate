#!/usr/bin/env python3
"""knowledge 口播 series orchestrator (projects/knowledge). Steps, in order:

  voice        build voice/narration.json from episode.yaml segments, then the SHARED voice entry
               (scripts/voice/clone_tts.py -> flova_minimax passage, atempo, pause retime, Whisper timings, -16 LUFS)
  heygen-plan  build the timeline (real voice), then the SHARED HeyGen planner
               (pipeline/maphub/heygen_plan.py plan -> heygen/heygen_audio.wav + segments.json + heygen_segments.md)
  matte        matte the first on-cam segment for the title layering (scripts/matting/matte_local.cmd, shared)
  compose      (re)build data/timeline.json + footage/social/brands (pipeline/knowledge/timeline.py)
  render       preflight + stage the knowledge Remotion workspace + npx remotion render KnowledgeKoubo (1440x1080 30fps)

No listing / POI / map steps exist in this pipeline. HeyGen generation/download and the 7b de-watermark stay
manual agent steps (see docs/RUNBOOK-knowledge-koubo.md): this script never spends HeyGen credits.

usage:
  python pipeline/knowledge/make_video.py <ep> [--step all|voice|heygen-plan|matte|compose|render]
                                             [--check] [--draft] [--force]
  --check   dry-run: validate inputs and print what each step would do; never calls TTS/HeyGen/matting/render.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from pipeline.common.voice_config import read_yaml  # noqa: E402  (shared with map-hub)
from pipeline.common.workspace import stage_episode
from pipeline.common.media import materialize
from pipeline.common.rendering import atomic_output  # noqa: E402  (shared; series-aware template)

import episode as kepi  # noqa: E402
import timeline as ktl  # noqa: E402

STEPS = ("voice", "heygen-plan", "matte", "compose", "render")
COMPOSITION = "KnowledgeKoubo"


def sh(cmd: list, **kw) -> int:
    print("+", " ".join(str(c) for c in cmd))
    return subprocess.call([str(c) for c in cmd], **kw)


def step_voice(ep: Path, cfg: dict, segments: list[dict], check: bool, force: bool) -> int:
    engine = (cfg.get("voice_defaults") or {}).get("engine", "flova_minimax")
    out = ep / "voice" / engine
    narration = ep / "voice" / "narration.json"
    missing = [s["id"] for s in segments if not (out / f"{s['id']}.wav").is_file()]
    if not narration.is_file() or force:
        narration.parent.mkdir(exist_ok=True)
        payload = {"engine": engine, "lines": [{"id": s["id"], "text": s["text"]} for s in segments]}
        narration.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8", newline="\n")
        print("wrote", narration)
    cmd = [sys.executable, REPO / "scripts" / "voice" / "clone_tts.py", narration,
           "--episode", ep, "--out", out]
    if not missing and not force:
        print(f"voice: {len(segments)} 段 wav 已齐（{out}），跳过")
        return 0
    if check:
        print(f"voice: 缺 {len(missing)} 段 ({', '.join(missing) or '无'})；将运行共享配音入口（本步骤会消耗 flova 积分，--check 不执行）:")
        print("+", " ".join(str(c) for c in cmd))
        return 0
    rc = sh(cmd)
    if rc == 21:
        print("flova_minimax 失败（exit 21）。备选：Kaggle IndexTTS-2.5 "
              "scripts/voice/push_indextts25.py --episode <ep> --script <json>；最后手段本地 F5（--engine f5）。")
    return rc


def step_heygen_plan(ep: Path, cfg: dict, segments: list[dict], check: bool, force: bool) -> int:
    oncam = [s for s in segments if s["type"] == "oncam"]
    est = sum(s["est_s"] for s in oncam)
    budget = float(cfg.get("oncam_budget_s", 55))
    print(f"heygen-plan: {len(oncam)} 个露脸段，估算 {est:.1f}s / 预算 {budget:.0f}s")
    if est > budget:
        print("!! 露脸估算超过预算——压稿后再生成配音")
        return 1
    cmd = [sys.executable, REPO / "pipeline" / "maphub" / "heygen_plan.py", ep, "plan"]
    if check:
        look = (cfg.get("heygen") or {}).get("look")
        print(f"heygen-plan: HeyGen look = {look!r}（按名字选已保存 look，找不到就停）")
        print("+", " ".join(str(c) for c in cmd))
        print("  之后是人工/Playwright 步骤：上传 heygen/heygen_audio.wav 生成一条 16:9 视频 -> heygen/export.mp4，"
              "再过 7b 去水印（pipeline/maphub/heygen_43.py），最后 heygen_plan.py <ep> split")
        return 0
    # real run needs clone voice + timeline first
    ktl.build(ep)
    return sh(cmd)


def step_matte(ep: Path, cfg: dict, segments: list[dict], check: bool, force: bool) -> int:
    first = next((s for s in segments if s["type"] == "oncam"), None)
    if first is None:
        print("matte: 无露脸段，跳过")
        return 0
    hg = ep / "footage" / "heygen" / "HG00.mp4"
    alpha = ep / "footage" / "heygen" / "HG00_alpha.webm"
    if alpha.is_file() and not force:
        print("matte: HG00_alpha.webm 已存在，跳过")
        return 0
    if not hg.is_file():
        msg = "matte: 缺 footage/heygen/HG00.mp4（先完成 HeyGen 生成 + 7b + split）"
        print(msg)
        return 0 if check else 2
    pres = read_yaml(REPO / "assets" / "presenter" / str(cfg.get("presenter") or "cool-breeze") / "presenter.yaml")
    mat = (pres.get("matting") or {})
    cmd = ["cmd", "/c", REPO / "scripts" / "matting" / "matte_local.cmd", hg,
           "--out", ep / "matte", "--max-size", str(mat.get("max_size", 1080))]
    if check:
        print("+", " ".join(str(c) for c in cmd))
        print(f"  再 copy matte\\HG00_alpha.webm -> footage\\heygen\\HG00_alpha.webm（引擎 {mat.get('engine', 'matanyone2')}，RVM 自动兜底）")
        return 0
    rc = sh(cmd)
    if rc == 0 and (ep / "matte" / "HG00_alpha.webm").is_file():
        materialize(ep / "matte" / "HG00_alpha.webm", alpha)
        print("matte: ->", alpha)
    return rc


def step_compose(ep: Path, check: bool, draft: bool) -> int:
    if check:
        print("compose: 将重建 data/timeline.json + footage/social/brands（pipeline/knowledge/timeline.py）")
        print("+", sys.executable, REPO / "pipeline" / "knowledge" / "timeline.py", ep, "--draft" if draft else "")
        return 0
    ktl.build(ep, draft=draft)
    return 0


def preflight(ep: Path, draft: bool) -> list[str]:
    errors: list[str] = []
    data = ep / "data"
    for name in ("timeline.json", "footage.json", "episode.json", "brands.json", "social.json"):
        if not (data / name).is_file():
            errors.append(f"missing data/{name} — run the compose step")
    if errors:
        return errors
    tl = json.loads((data / "timeline.json").read_text(encoding="utf-8-sig"))
    footage = json.loads((data / "footage.json").read_text(encoding="utf-8-sig"))
    if not draft and tl.get("audio_mode") != "clone":
        errors.append("final render needs clone voice (audio_mode != clone); use --draft for a draft")
    for row in tl.get("lines", []):
        if row.get("type") == "oncam":
            cid = row.get("clip", "?")
            if footage.get(cid, {}).get("status") != "heygen":
                errors.append(f"on-cam segment missing HeyGen footage: {cid} ({row['id']}) — generate/split first")
        for b in row.get("broll", []):
            if footage.get(b["clip"], {}).get("status") == "pending" and not draft:
                errors.append(f"pending b-roll: {b['clip']} ({b.get('desc', '')}) — fill broll/ or use --draft")
    return errors


def out_target(ep: Path, draft: bool, still: int | None, platform: str) -> Path:
    """Output convention: tests/stills -> out/drafts/<ver>/ ; final platform exports -> out/release/<episode>_<platform>.mp4"""
    if still is not None:
        return ep / "out" / "drafts" / "stills" / f"still_f{still}.png"
    if draft:
        return ep / "out" / "drafts" / "pipeline" / f"draft_{COMPOSITION}_{platform}.mp4"
    return ep / "out" / "release" / f"{ep.name}_{platform}.mp4"


def step_render(ep: Path, check: bool, draft: bool, still: int | None, concurrency: int, platform: str = "shipinhao") -> int:
    errors = preflight(ep, draft)
    if errors:
        for e in errors:
            print("PREFLIGHT:", e)
        if not check:
            return 1
    target = out_target(ep, draft, still, platform)
    props = "--props=" + json.dumps({"platform": platform})
    work_cmd = f"npx remotion still src/index.ts {COMPOSITION} {target} --frame={still} {props}" if still is not None \
        else f"npx remotion render src/index.ts {COMPOSITION} {target} --gl=angle --concurrency={concurrency} {props}"
    if check:
        print("render: 将 stage 工作区并渲染（cwd <ep>/work/remotion）:")
        print("+", work_cmd)
        return 0 if not errors else 1
    work = stage_episode(ep)
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx or not (work / "node_modules").is_dir():
        print("install the template's Remotion dependencies first")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    argv = [npx, "remotion", "still" if still is not None else "render", "src/index.ts", COMPOSITION,
            str(target), props]
    if still is not None:
        argv.append(f"--frame={still}")
    else:
        argv += ["--gl=angle", f"--concurrency={concurrency}"]
    print("+", " ".join(argv), " (cwd", work, ")")
    try:
        with atomic_output(target) as pending:
            argv[5] = str(pending)
            subprocess.run(argv, cwd=work, check=True)
        rc = 0
    except subprocess.CalledProcessError as exc:
        rc = exc.returncode
    if rc == 0:
        print(target)
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode")
    ap.add_argument("--step", choices=("all",) + STEPS, default="all")
    ap.add_argument("--check", action="store_true", help="dry-run: validate and print only")
    ap.add_argument("--draft", action="store_true", help="allow estimated captions / pending footage")
    ap.add_argument("--force", action="store_true", help="re-run even when outputs exist")
    ap.add_argument("--still", type=int, default=None, metavar="FRAME", help="render one frame instead of the video")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--platform", choices=("douyin", "shipinhao"), default="shipinhao", help="final export -> out/release/<episode>_<platform>.mp4")
    a = ap.parse_args()
    ep, cfg, segments = kepi.load_episode(a.episode)
    info = kepi.summary(cfg, segments)
    print(f"{ep.name}: {info['segments']} 段（露脸 {info['oncam']} / 画外音 {info['voiceover']}），"
          f"估算总长 {info['est_total_s']}s（目标 {info['total_target_s']:.0f}s），露脸估算 {info['est_oncam_s']}s / 预算 {info['oncam_budget_s']:.0f}s")
    if not 70 <= info["est_total_s"] <= 100:
        print("!! 估算总长不在 80–90s 附近（70–100 之外）——按需增减段")
    steps = STEPS if a.step == "all" else (a.step,)
    rc = 0
    for st in steps:
        print(f"\n=== step: {st}{' (check)' if a.check else ''} ===")
        if st == "voice":
            rc = step_voice(ep, cfg, segments, a.check, a.force)
        elif st == "heygen-plan":
            rc = step_heygen_plan(ep, cfg, segments, a.check, a.force)
        elif st == "matte":
            rc = step_matte(ep, cfg, segments, a.check, a.force)
        elif st == "compose":
            rc = step_compose(ep, a.check, a.draft or a.check)
        elif st == "render":
            rc = step_render(ep, a.check, a.draft, a.still, a.concurrency, a.platform)
        if rc != 0:
            print(f"step {st} failed (rc={rc}) — stopping")
            return rc
    print("\ndone." if not a.check else "\ncheck done (nothing executed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

