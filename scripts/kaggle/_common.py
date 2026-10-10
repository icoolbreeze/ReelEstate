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


def cred_status():
    home = Path(os.environ.get("KAGGLE_CONFIG_DIR") or Path.home() / ".kaggle")
    if (home / "kaggle.json").is_file():
        return "kaggle.json"
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
    home = Path(os.environ.get("KAGGLE_CONFIG_DIR") or Path.home() / ".kaggle")
    f = home / "kaggle.json"
    if f.is_file():
        return json.loads(f.read_text(encoding="utf-8"))["username"]  # only this field is read
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


def slug(episode_name, job):
    s = re.sub(r"[^a-z0-9-]+", "-", f"reelestate-{episode_name}-{job}".lower()).strip("-")
    s = re.sub(r"-+", "-", s)
    if len(s) > 50:
        import hashlib
        h = hashlib.sha1(s.encode()).hexdigest()[:6]
        s = s[:43].rstrip("-") + "-" + h
    return s


def job_dir(ep_dir, job):
    d = ep_dir / "kaggle" / job
    d.mkdir(parents=True, exist_ok=True)
    return d
