"""Helpers shared by the make stages (stdlib only)."""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reel_common import REPO_ROOT, load_json, save_json  # noqa: E402,F401

PLACEHOLDER = "待填"
EXIT_NEED_INPUT = 3  # stage stopped: questions for the user (see brief.json "questions")


class NeedInput(Exception):
    """Raised by a stage when it cannot continue without the user's answer."""

    def __init__(self, questions: list[dict]):
        super().__init__("; ".join(q["q"] for q in questions))
        self.questions = questions


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def rel(project_dir: Path, p: Path) -> str:
    return p.resolve().relative_to(project_dir.resolve()).as_posix()


def brief_path(project_dir: Path) -> Path:
    return project_dir / "brief.json"


def load_brief(project_dir: Path) -> dict:
    p = brief_path(project_dir)
    return load_json(p) if p.exists() else {}


def save_brief(project_dir: Path, brief: dict) -> None:
    save_json(brief_path(project_dir), brief)


def get_dotted(obj: dict, key: str, default=None):
    cur = obj
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def set_dotted(obj: dict, key: str, value) -> None:
    parts = key.split(".")
    cur = obj
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def outputs_exist(project_dir: Path, outputs: list[str]) -> bool:
    return all((project_dir / o).exists() for o in outputs)


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
