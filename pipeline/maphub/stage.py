#!/usr/bin/env python3
"""Prepare an episode-owned Remotion workspace without changing shared links."""
import argparse
from workspace import stage_episode

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode")
    args = parser.parse_args()
    print(stage_episode(args.episode))

if __name__ == "__main__":
    main()
