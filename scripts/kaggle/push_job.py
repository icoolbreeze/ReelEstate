"""Package inputs -> private Kaggle dataset -> push GPU kernel.

python scripts/kaggle/push_job.py --check
python scripts/kaggle/push_job.py --episode projects/rental/<ep> --job matting \
    --kernel matting_rvm --inputs a.mp4 b.mp4 [--param k=v ...] [--dry-run]
"""
import argparse, datetime, json, shutil, sys, tempfile, time
from pathlib import Path
from _common import REPO, cred_status, username, run, episode_dir, slug, job_dir, kaggle_exe

KERNELS = Path(__file__).resolve().parent / "kernels"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="check CLI + credentials, then exit")
    ap.add_argument("--episode")
    ap.add_argument("--job")
    ap.add_argument("--kernel", help="template name in kernels/ (matting_rvm, tts_f5)")
    ap.add_argument("--inputs", nargs="+", default=[])
    ap.add_argument("--param", action="append", default=[], help="k=v passed to kernel via job.json")
    ap.add_argument("--user")
    ap.add_argument("--accelerator", default="NvidiaTeslaT4")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.check:
        print("cli:", kaggle_exe())
        c = cred_status()
        print("credentials:", c or "missing")
        sys.exit(0 if c else 1)

    if not (a.episode and a.job and a.kernel and a.inputs):
        ap.error("--episode, --job, --kernel, --inputs are required")
    if not cred_status() and not a.dry_run:
        sys.exit("credentials: missing (put kaggle.json in %USERPROFILE%\\.kaggle\\)")
    tpl = KERNELS / f"{a.kernel}.py"
    if not tpl.is_file():
        sys.exit(f"unknown kernel template: {tpl}")

    ep = episode_dir(a.episode)
    s = slug(ep.name, a.job)
    user = username(a.user) if not a.dry_run else (a.user or "<user>")
    params = dict(p.split("=", 1) for p in a.param)

    files = []
    for f in a.inputs:
        p = Path(f)
        p = (p if p.is_absolute() else REPO / p).resolve()
        if not p.is_file():
            sys.exit(f"input not found: {p}")
        if REPO.resolve() not in p.parents:
            sys.exit(f"input must be inside the repo: {p}")
        if p.name in ("kaggle.json", "access_token") or p.suffix in (".env",):
            sys.exit("refusing to upload credential-like file")
        files.append(p)

    job = {"slug": s, "episode": ep.name, "job": a.job, "kernel": a.kernel,
           "inputs": [p.name for p in files], "params": params,
           "pushed_at": datetime.datetime.now().isoformat(timespec="seconds")}
    print(json.dumps(job, ensure_ascii=False, indent=2))
    if a.dry_run:
        print("dry-run: nothing uploaded")
        return

    ref = f"{user}/{s}"
    with tempfile.TemporaryDirectory() as tmp:
        dd = Path(tmp, "data"); dd.mkdir()
        for p in files:
            shutil.copy2(p, dd / p.name)
        (dd / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        (dd / "dataset-metadata.json").write_text(json.dumps(
            {"title": s, "id": ref, "licenses": [{"name": "other"}], "isPrivate": True}), encoding="utf-8")
        exists = run(["datasets", "status", ref], check=False).returncode == 0
        if exists:
            run(["datasets", "version", "-p", str(dd), "-m", job["pushed_at"], "-r", "zip", "-q"])
        else:
            run(["datasets", "create", "-p", str(dd), "-r", "zip", "-q"])
        print("dataset", "versioned" if exists else "created", ref)
        for _ in range(60):
            st = run(["datasets", "status", ref], check=False).stdout.strip().lower()
            if "ready" in st:
                break
            time.sleep(10)
        else:
            sys.exit("dataset not ready after 10 min; rerun push later")

        kd = Path(tmp, "kernel"); kd.mkdir()
        shutil.copy2(tpl, kd / "main.py")
        (kd / "kernel-metadata.json").write_text(json.dumps({
            "id": ref, "title": s, "code_file": "main.py", "language": "python",
            "kernel_type": "script", "is_private": True, "enable_gpu": True,
            "enable_internet": True, "dataset_sources": [ref],
            "competition_sources": [], "kernel_sources": []}), encoding="utf-8")
        r = run(["kernels", "push", "-p", str(kd), "--accelerator", a.accelerator], check=False)
        if r.returncode != 0 and "accelerator" in (r.stderr + r.stdout).lower():
            r = run(["kernels", "push", "-p", str(kd)])  # older CLI without --accelerator
        elif r.returncode != 0:
            sys.exit(f"kernel push failed:\n{r.stdout}\n{r.stderr}")
        print(r.stdout.strip())

    job["ref"] = ref
    (job_dir(ep, a.job) / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"next: python scripts/kaggle/pull_job.py --episode {a.episode} --job {a.job}")


if __name__ == "__main__":
    main()
