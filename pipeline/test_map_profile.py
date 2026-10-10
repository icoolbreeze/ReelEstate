"""Tests for resolve_map_profile — fake dicts only (no disk reads, no network).

Run from the repo root:
  python -c "import sys; sys.path.insert(0, 'pipeline'); import test_map_profile; test_map_profile.main()"
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stages.map_fetch import resolve_map_profile  # noqa: E402


def main() -> None:
    # 1. An existing params.profile wins over everything (registry mother says kid9).
    existing = {"params": {"profile": "kid4", "original": True}}
    registry = {"active_mother_profile": "kid9"}
    assert resolve_map_profile(existing, registry=registry) == "kid4"

    # 2a. Missing existing profile -> registry active_mother_profile.
    assert resolve_map_profile({}, registry={"active_mother_profile": "kid7"}) == "kid7"
    # 2b. Blank / whitespace existing profile -> registry active_mother_profile.
    blank = {"params": {"profile": "   "}}
    assert resolve_map_profile(blank, registry={"active_mother_profile": "kid7"}) == "kid7"

    # 3. No active mother: first role=mother account with api_key_ref flova-profile:<name> -> <name>.
    registry = {
        "accounts": [
            {"role": "child", "api_key_ref": "flova-profile:kid1"},
            {"role": "retired_mother", "api_key_ref": "flova-profile:kid2"},
            {"role": "mother", "api_key_ref": "flova-profile:kid4"},
        ]
    }
    assert resolve_map_profile({}, registry=registry) == "kid4"

    # 4. Empty registry -> policy mother.default_profile.
    policy = {"mother": {"default_profile": "mom-default"}}
    assert resolve_map_profile({}, registry={}, policy=policy) == "mom-default"

    # 5. Nothing set anywhere -> "prod".
    assert resolve_map_profile({}, registry={}, policy={}) == "prod"

    print("all map profile tests passed")


if __name__ == "__main__":
    main()
