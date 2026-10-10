"""Poll a pushed kernel and download its outputs into the episode folder only.

python scripts/kaggle/pull_job.py --episode projects/rental/<ep> --job matting [--interval 60] [--timeout 10800] [--no-wait]
"""
import argparse, json, sys, time
from pathlib import Path
from _common import run, episode_dir, job_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--job", required=True)
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--timeout", type=int, default=3 * 3600)
    ap.add_argument("--no-wait", action="store_true", help="print status once and exit")
    a = ap.parse_args()

    ep = episode_dir(a.episode)
    jd = job_dir(ep, a.job)
    jf = jd / "job.json"
    if not jf.is_file():
        sys.exit(f"no job.json at {jf}; run push_job.py first")
    ref = json.loads(jf.read_text(encoding="utf-8"))["ref"]

    t0 = time.time()
    while True:
        st = run(["kernels", "status", ref], check=False).stdout.strip()
        low = st.lower()
        print(time.strftime("%H:%M:%S"), st)
        if "complete" in low or "error" in low or "cancel" in low:
            break
        if a.no_wait:
            return
        if time.time() - t0 > a.timeout:
            sys.exit("timeout waiting for kernel; rerun pull_job.py later")
        time.sleep(a.interval)

    out = jd / "output"
    out.mkdir(exist_ok=True)
    run(["kernels", "output", ref, "-p", str(out), "-o"], check=False)
    files = sorted(p.relative_to(out) for p in out.rglob("*") if p.is_file())
    print(f"downloaded {len(files)} files -> {out}")
    for f in files[:50]:
        print("  ", f)
    if "complete" not in st.lower():
        sys.exit("kernel did not complete; see *.log in output/")


if __name__ == "__main__":
    main()
