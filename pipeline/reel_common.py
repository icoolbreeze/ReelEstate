"""Shared helpers for the ReelEstate pipeline (stdlib only)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = REPO_ROOT / "projects"
CATEGORIES = ("rental", "resale", "new-home")
RATIOS = {"4x3": (1440, 1080), "3x4": (1080, 1440), "9x16": (1080, 1920)}
COMPOSITION_NAMES = {"rental": "Rental", "resale": "Resale", "new-home": "NewHome"}


def setup_console() -> None:
    """Make stdout/stderr UTF-8 so Chinese output survives Windows pipes."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def load_env(path: Path | None = None) -> dict[str, str]:
    """Parse .env (KEY=VALUE, # comments). Real environment variables win."""
    env: dict[str, str] = {}
    path = path or REPO_ROOT / ".env"
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            env[key.strip()] = value
    for key in list(env):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def resolve_project_dir(arg: str) -> Path:
    p = Path(arg)
    if not p.is_absolute():
        cand = (Path.cwd() / p)
        p = cand if cand.exists() else (REPO_ROOT / p)
    p = p.resolve()
    if p.is_file() and p.name in ("episode.yaml", "episode.json", "compliance.json"):
        p = p.parent
    if not (p / "episode.yaml").exists() or not (p / "episode.json").exists():
        raise SystemExit("错误：只接受 episode.yaml + episode.json 视频工程，如 projects/listing/ep02-zidong")
    return p


def load_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def cuda_path() -> str | None:
    """Locate the CUDA toolkit bin dir (CUDA_PATH env, else newest standard install)."""
    cuda_path_env = os.environ.get("CUDA_PATH")
    if cuda_path_env and (Path(cuda_path_env) / "bin").is_dir():
        return str(Path(cuda_path_env) / "bin")
    base = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA")
    versions = sorted(p for p in base.glob("v*") if (p / "bin").is_dir()) if base.is_dir() else []
    return str(versions[-1] / "bin") if versions else None


def env_with_cuda() -> dict[str, str]:
    """Env for a CUDA-linked exe: its delay-loaded cudart/cublas need CUDA bin on PATH."""
    env = dict(os.environ)
    cu = cuda_path()
    if cu:
        env["PATH"] = cu + os.pathsep + env.get("PATH", "")
    return env


def strip_comments(obj):
    """Remove keys starting with '_' recursively (comment fields)."""
    if isinstance(obj, dict):
        return {k: strip_comments(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [strip_comments(v) for v in obj]
    return obj

