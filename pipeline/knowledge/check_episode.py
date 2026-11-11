"""Read-only preflight for knowledge episodes; never generates narration or assets."""
import argparse
import json
from episode import load_episode
from make_video import preflight
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.common.color_restore import gate  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode")
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args()
    try:
        ep, _, _ = load_episode(args.episode)
        errors = preflight(ep, args.draft)
        color_errors, warnings = gate(ep)   # D-Log M colour gate (all content lines)
        errors = list(errors) + color_errors
    except (OSError, ValueError) as exc:
        errors, warnings = [str(exc)], []
    print(json.dumps({"pass": not errors, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
