"""Package inputs -> private Kaggle dataset -> push GPU kernel.

python scripts/kaggle/push_job.py --check
python scripts/kaggle/push_job.py --episode projects/rental/<ep> --job matting \
    --kernel matting_rvm --inputs a.mp4 b.mp4 [--param k=v ...] [--dry-run]

One video input gets its own --run (from the filename) so a second video
uses another dataset, kernel, and local directory. A run whose kernel is
still queued or running is not pushed again.

Queue policy (--kind sr|tts|matting|other): after each push the status is polled
briefly (--queue-wait seconds). A kernel still QUEUED is deleted (Kaggle has no
cancel; delete stops the session) and pushed again, up to --max-attempts (10).
When every attempt stays queued or fails the script exits with:
  23 = sr   -> super-res skipped: keep the lanczos version and deliver normally (not a pipeline failure)
  21 = tts  -> caller falls back to local F5 (scripts/voice/clone_tts_f5.cmd)
  22 = other/matting -> stop and report
Test without Kaggle: --dry-run --mock-status queued[,queued,running...]
Run with the conda base python: C:/ProgramData/miniconda3/python.exe
"""
import argparse, datetime, json, os, shutil, sys, tempfile, time
from pathlib import Path
from _common import (REPO, cred_status, username, run, episode_dir, slug,
                     job_dir, kaggle_exe, kaggle_cmd, run_token, sanitize_run)

KERNELS = Path(__file__).resolve().parent / "kernels"
EXIT_SR_SKIPPED, EXIT_TTS_FALLBACK, EXIT_OTHER_STOP = 23, 21, 22   # 2026-10-19: SR failure no longer stops the pipeline (was 20)
KIND_EXIT = {"sr": EXIT_SR_SKIPPED, "tts": EXIT_TTS_FALLBACK}


def infer_kind(kernel):
    k = (kernel or "").lower()
    if k.startswith("seedvr") or "upscale" in k or "sr" == k:
        return "sr"
    if k.startswith("tts"):
        return "tts"
    if "matting" in k:
        return "matting"
    return "other"


def queue_exhausted(kind, attempts, last):
    msg = {"sr": "超分 Kaggle 任务 %d 次都在排队/失败，跳过超分，保留 lanczos 版本照常交付（在报告里注明）。",
           "tts": "语音 Kaggle 任务 %d 次都在排队/失败，改用本地 F5。",
           }.get(kind, "Kaggle 任务 %d 次都在排队/失败，停止并上报。") % attempts
    print(f"QUEUE_POLICY kind={kind} attempts={attempts} last={last}: {msg}", file=sys.stderr)
    sys.exit(KIND_EXIT.get(kind, EXIT_OTHER_STOP))


def push_with_queue_policy(push, status, cancel, kind, max_attempts=10,
                           queue_wait=45, poll=15, sleep=time.sleep):
    """push() -> bool ok; status() -> lowercase text; cancel() deletes the session.
    Returns on the first attempt that leaves the queue; otherwise exits by kind."""
    last = "none"
    for n in range(1, max_attempts + 1):
        if not push():
            last = "push-failed"
            print(f"attempt {n}/{max_attempts}: push failed", file=sys.stderr)
            sleep(5)
            continue
        waited, st = 0, ""
        while True:
            st = status()
            if "queued" not in st or waited >= queue_wait:
                break
            sleep(poll); waited += poll
        if "queued" in st:
            last = "queued"
            print(f"attempt {n}/{max_attempts}: still QUEUED after {waited}s, cancelling and re-pushing",
                  file=sys.stderr)
            cancel()
            sleep(5)
            continue
        if "error" in st or "cancel" in st:
            last = st.strip() or "error"
            print(f"attempt {n}/{max_attempts}: {last}", file=sys.stderr)
            continue
        print(f"attempt {n}/{max_attempts}: {st.strip() or 'started'}")
        return n
    queue_exhausted(kind, max_attempts, last)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="check CLI + credentials, then exit")
    ap.add_argument("--episode")
    ap.add_argument("--job")
    ap.add_argument("--kernel", help="template name in kernels/ (matting_rvm, tts_indextts25, tts_f5, seedvr2_v9)")
    ap.add_argument("--inputs", nargs="+", default=[])
    ap.add_argument("--param", action="append", default=[], help="k=v passed to kernel via job.json")
    ap.add_argument("--user")
    ap.add_argument("--accelerator", default="NvidiaTeslaT4")
    ap.add_argument("--run", help="isolate this session from other runs of the same job")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--kind", choices=["sr", "tts", "matting", "other"],
                    help="job type for the queue policy (default: from --kernel)")
    ap.add_argument("--max-attempts", type=int, default=10)
    ap.add_argument("--queue-wait", type=int, default=45, help="seconds to tolerate QUEUED per attempt")
    ap.add_argument("--mock-status", help="with --dry-run: comma list of statuses to simulate the queue policy")
    a = ap.parse_args()

    if a.check:
        print("cli:", " ".join(kaggle_cmd()))
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
    names = [p.name for p in files]
    if len(names) != len(set(names)):
        sys.exit("inputs share a filename; refuse to pack one over the other")

    if a.run:
        token = sanitize_run(a.run)
    elif len(files) == 1:
        token = run_token(_input_label(ep, files[0]))
    else:
        token = None
    s = slug(ep.name, a.job, token)
    jd = job_dir(ep, a.job, token, mkdir=not a.dry_run)

    job = {"slug": s, "episode": ep.name, "job": a.job, "run": token,
           "kernel": a.kernel, "inputs": names, "params": params,
           "output_dir": (jd / "output").relative_to(ep).as_posix(),
           "pushed_at": datetime.datetime.now().isoformat(timespec="seconds")}
    a.kind = a.kind or infer_kind(a.kernel)
    job["kind"] = a.kind
    print(json.dumps(job, ensure_ascii=False, indent=2))
    if a.dry_run:
        print("dry-run: nothing uploaded")
        if a.mock_status:
            seq = [x.strip().lower() for x in a.mock_status.split(",") if x.strip()]
            it = iter(seq)
            last = [seq[-1]]
            def st():
                last[0] = next(it, last[0]); return last[0]
            n = push_with_queue_policy(lambda: (print("mock push"), True)[1], st,
                                       lambda: print("mock cancel (kernels delete -y)"),
                                       a.kind, a.max_attempts, a.queue_wait, poll=a.queue_wait or 1,
                                       sleep=lambda s: None)
            print(f"mock: left the queue on attempt {n}")
        return

    lock = _acquire_lock(jd / ".push.lock")
    try:
        _refuse_if_busy(jd / "job.json")
        _upload_and_record(a, ep, user, s, files, job, jd, tpl)
    finally:
        _release_lock(lock)

def _pid_alive(pid):
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _acquire_lock(path):
    """One local push per run directory. A live lock means do not touch that run."""
    for _ in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = 0
            try:
                holder = int(path.read_text(encoding="utf-8").strip() or "0")
            except (OSError, ValueError):
                holder = 0
            if _pid_alive(holder):
                sys.exit(f"push already in progress for {path.parent}; not overwriting it")
            try:
                path.unlink()
            except OSError:
                sys.exit(f"cannot clear stale lock {path}")
            continue
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        return path
    sys.exit(f"cannot lock {path}")


def _release_lock(path):
    try:
        if path.is_file() and path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            path.unlink()
    except OSError:
        pass


def _refuse_if_busy(job_file):
    if not job_file.is_file():
        return
    ref = json.loads(job_file.read_text(encoding="utf-8")).get("ref")
    if not ref:
        return
    st = run(["kernels", "status", ref], check=False)
    low = st.stdout.lower()
    if "running" in low or "queued" in low:
        sys.exit(f"{ref} is still queued or running; not pushing over it and not touching its output")


def _input_label(ep, path):
    try:
        return path.relative_to(ep).as_posix()
    except ValueError:
        return path.relative_to(REPO).as_posix()


# Same pinned image as the account's T4 kernels that leave the queue immediately.
# A new kernel with an empty docker_image stayed queued and was cancelled at 0 seconds.
T4_DOCKER_IMAGE = (
    "gcr.io/kaggle-private-byod/python@sha256:"
    "2757e0c7d1e0a9cb43da657b97e223c321a98f5014bdf64f44f2f6b083ad2b2f"
)


def _kernel_slug(dataset_slug):
    """Kernel title/slug must not reuse the dataset slug. Kaggle returns 409."""
    suffix = "-k"
    if len(dataset_slug) + len(suffix) <= 50:
        return dataset_slug + suffix
    return dataset_slug[:50 - len(suffix)].rstrip("-") + suffix


def _upload_and_record(a, ep, user, s, files, job, jd, tpl):
    ref = f"{user}/{s}"
    kernel_slug = _kernel_slug(s)
    kernel_ref = f"{user}/{kernel_slug}"
    with tempfile.TemporaryDirectory() as tmp:
        dd = Path(tmp, "data"); dd.mkdir()
        for p in files:
            shutil.copy2(p, dd / p.name)
        (dd / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
        (dd / "dataset-metadata.json").write_text(json.dumps(
            {"title": s, "id": ref, "licenses": [{"name": "other"}], "isPrivate": True}) + "\n",
            encoding="utf-8", newline="\n")
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
        meta = {
            "id": kernel_ref, "title": kernel_slug, "code_file": "main.py", "language": "python",
            "kernel_type": "script", "is_private": True, "enable_gpu": True,
            "enable_internet": True, "dataset_sources": [ref],
            "competition_sources": [], "kernel_sources": [],
        }
        if a.accelerator == "NvidiaTeslaT4":
            meta["docker_image"] = T4_DOCKER_IMAGE
        (kd / "kernel-metadata.json").write_text(
            json.dumps(meta) + "\n", encoding="utf-8", newline="\n")
        def push():
            r = run(["kernels", "push", "-p", str(kd), "--accelerator", a.accelerator], check=False)
            if r.returncode != 0 and "accelerator" in (r.stderr + r.stdout).lower():
                r = run(["kernels", "push", "-p", str(kd)], check=False)  # older CLI
            if r.returncode != 0:
                print(f"kernel push failed:\n{r.stdout}\n{r.stderr}", file=sys.stderr)
                return False
            print(r.stdout.strip())
            return True
        status = lambda: run(["kernels", "status", kernel_ref], check=False).stdout.lower()
        cancel = lambda: run(["kernels", "delete", "-y", kernel_ref], check=False)
        job["attempts"] = push_with_queue_policy(push, status, cancel, a.kind,
                                                 a.max_attempts, a.queue_wait)

    job["ref"] = kernel_ref
    (jd / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8", newline="\n")
    pull = f"python scripts/kaggle/pull_job.py --episode {a.episode} --job {a.job}"
    if job.get("run"):
        pull += f" --run {job['run']}"
    print("next:", pull)


if __name__ == "__main__":
    main()
