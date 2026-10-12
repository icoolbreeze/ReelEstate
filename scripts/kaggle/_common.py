"""Shared helpers for Kaggle offload. Never prints credential contents."""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def kaggle_exe():
    exe = shutil.which("kaggle")
    if exe:
        return exe
    appdata = os.environ.get("APPDATA")
    if appdata:
        for p in Path(appdata, "Python").glob("Python*/Scripts/kaggle.exe"):
            return str(p)
    sys.exit("kaggle CLI not found; install with: pip install --user kaggle")


def _kaggle_home():
    return Path(os.environ.get("KAGGLE_CONFIG_DIR") or Path.home() / ".kaggle")


def _username_in(path):
    """Read only the username field. Never return or log the rest of the file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    user = data.get("username") if isinstance(data, dict) else None
    if isinstance(user, str) and user.strip():
        return user.strip()
    return None


def cred_status():
    home = _kaggle_home()
    if (home / "kaggle.json").is_file():
        return "kaggle.json"
    cred = home / "credentials.json"
    if cred.is_file() and _username_in(cred):
        return "credentials.json"
    if (home / "access_token").is_file() or os.environ.get("KAGGLE_API_TOKEN"):
        return "access_token"
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return "env"
    return None


def username(cli_user=None):
    if cli_user:
        return cli_user
    if os.environ.get("KAGGLE_USERNAME"):
        return os.environ["KAGGLE_USERNAME"]
    home = _kaggle_home()
    for name in ("kaggle.json", "credentials.json"):
        user = _username_in(home / name) if (home / name).is_file() else None
        if user:
            return user
    sys.exit("Cannot determine Kaggle username; pass --user")


def run(args, check=True, capture=True):
    r = subprocess.run([kaggle_exe(), *args], capture_output=capture, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        sys.exit(f"kaggle {' '.join(args[:3])} failed:\n{r.stdout}\n{r.stderr}")
    return r


def episode_dir(ep):
    p = Path(ep)
    if not p.is_absolute():
        p = (REPO / p)
    p = p.resolve()
    projects = (REPO / "projects").resolve()
    if projects not in p.parents or not p.is_dir():
        sys.exit(f"--episode must be an existing folder under projects/: {p}")
    return p


def safe_job(job):
    if not job or job in (".", "..") or "/" in job or "\\" in job or ".." in job:
        sys.exit(f"invalid --job: {job}")
    return job


def sanitize_run(text):
    s = re.sub(r"[^a-z0-9-]+", "-", str(text).lower()).strip("-")
    s = re.sub(r"-+", "-", s)
    if not s:
        sys.exit(f"invalid --run: {text}")
    if len(s) > 24:
        import hashlib
        h = hashlib.sha1(str(text).encode("utf-8")).hexdigest()[:6]
        s = s[:17].rstrip("-") + "-" + h
    return s


def run_token(filename):
    """Stable id for one input file. Same name → same token; different names do not share a slot."""
    import hashlib
    base = re.sub(r"[^a-z0-9-]+", "-", Path(filename).stem.lower()).strip("-")
    base = re.sub(r"-+", "-", base)
    digest = hashlib.sha1(str(filename).encode("utf-8")).hexdigest()[:6]
    if not base:
        return digest
    # Stay within sanitize_run's 24-character limit so pull --run is identity.
    return f"{base[:17].rstrip('-')}-{digest}"


def slug(episode_name, job, run=None):
    import hashlib
    raw = f"reelestate-{episode_name}-{job}"
    if run:
        raw = f"{raw}-{run}"
    s = re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-")
    s = re.sub(r"-+", "-", s)
    if len(s) > 50:
        h = hashlib.sha1(s.encode()).hexdigest()[:6]
        s = s[:43].rstrip("-") + "-" + h
    return s


def job_dir(ep_dir, job, run=None, mkdir=True):
    d = ep_dir / "kaggle" / safe_job(job)
    if run:
        d = d / run
    if mkdir:
        d.mkdir(parents=True, exist_ok=True)
    return d


def resolve_job_dir(ep_dir, job, run=None):
    """Pick the one local slot to read. Never falls through to a sibling run."""
    root = ep_dir / "kaggle" / safe_job(job)
    if run:
        d = root / sanitize_run(run)
        if not (d / "job.json").is_file():
            sys.exit(f"no job.json at {d / 'job.json'}")
        return d
    found = []
    if (root / "job.json").is_file():
        found.append(root)
    if root.is_dir():
        for child in sorted(p for p in root.iterdir() if p.is_dir()):
            if (child / "job.json").is_file():
                found.append(child)
    if not found:
        sys.exit(f"no job.json under {root}; run push_job.py first")
    if len(found) > 1:
        lines = "\n".join(f"  --run {p.name}" if p != root else "  (legacy, no --run)" for p in found)
        sys.exit(f"multiple runs under {root}; pass --run so one download cannot overwrite the other:\n{lines}")
    return found[0]
