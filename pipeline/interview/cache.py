"""Cache identity for interview derivatives. A changed input is a new key."""
import hashlib
import json


def cache_key(**parts):
    blob = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def lookup(index, key):
    if not isinstance(index, dict):
        return None
    row = index.get(key)
    if not isinstance(row, dict) or row.get("key") != key:
        return None
    return row
