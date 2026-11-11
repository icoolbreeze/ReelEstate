"""flova image-request owner for map / mark repaints: keep an explicit owner, else let the MCP pool choose."""


def resolve_map_profile(existing_request, *, registry=None, policy=None):
    """Keep an explicit request owner; otherwise let the image MCP use its pool.

    registry/policy are accepted for older callers but never force a mother account onto a new request.
    """
    params = (existing_request or {}).get("params")
    profile = params.get("profile") if isinstance(params, dict) else None
    return profile.strip() if isinstance(profile, str) and profile.strip() else None
