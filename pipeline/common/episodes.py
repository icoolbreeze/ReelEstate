"""One publication sequence across content kinds; tests do not consume release numbers."""
import re
from pathlib import Path
from .voice_config import read_yaml

KINDS = ("listing", "knowledge", "interview")
SERIES_ROUTE = {
    "listing": "listing",
    "knowledge": "knowledge",
    "interview": "interview",
}
TEST_PURPOSES = ("test", "example", "benchmark")


def classify_series(series):
    if series not in SERIES_ROUTE:
        raise ValueError("unknown series: %r; expected listing, knowledge, or interview" % (series,))
    return SERIES_ROUTE[series]


def list_episodes(repo):
    found = {}
    for kind in KINDS:
        root = Path(repo) / "projects" / kind
        if not root.is_dir():
            continue
        for ep in root.glob("ep*-*"):
            if ep.is_dir() and (ep / "episode.yaml").is_file():
                found.setdefault(ep.resolve(), ep)
    return sorted(found)


def next_release_number(repo):
    numbers = []
    for ep in list_episodes(repo):
        cfg = read_yaml(ep / "episode.yaml")
        if cfg.get("purpose") in TEST_PURPOSES:
            continue
        number = cfg.get("release_number", cfg.get("episode"))
        if number is None:
            match = re.match(r"ep(\d+)-", ep.name)
            number = int(match.group(1)) if match else None
        if number is not None:
            if isinstance(number, bool) or not isinstance(number, int) or number < 1:
                raise ValueError("invalid release_number: %s" % ep)
            numbers.append(number)
    return max(numbers, default=0) + 1
