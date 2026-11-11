#!/usr/bin/env python3
"""Prepare an episode-owned Remotion workspace without changing shared links."""
import argparse
import re
from pathlib import Path
from workspace import stage_episode, episode_path

def series_of(ep):
    yaml_path = Path(ep) / "episode.yaml"
    if yaml_path.is_file():
        m = re.search(r"(?m)^\s*series:\s*([a-z0-9-]+)", yaml_path.read_text(encoding="utf-8-sig", errors="replace"))
        if m:
            return m.group(1)
    return "listing"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode")
    args = parser.parse_args()
    ep = episode_path(args.episode)
    series = series_of(ep)
    if series != "listing":
        raise SystemExit(
            "%s is series '%s', not listing. Use the knowledge pipeline instead: "
            "scripts\\make-knowledge-video.cmd %s (runbook docs/RUNBOOK-knowledge-koubo.md)."
            % (ep.name, series, ep.name))
    print(stage_episode(ep))

if __name__ == "__main__":
    main()

