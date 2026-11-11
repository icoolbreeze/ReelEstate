"""Media inspection and atomic materialization for generated public assets."""
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path


def probe(path):
    try:
        raw = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(path)
        ], capture_output=True, text=True, check=True).stdout
        data = json.loads(raw)
        stream = data["streams"][0]
        a, b = stream["r_frame_rate"].split("/")
        return {"w": stream["width"], "h": stream["height"],
                "fps": float(a) / float(b), "dur": float(data["format"]["duration"])}
    except (OSError, ValueError, KeyError, IndexError, ZeroDivisionError, subprocess.CalledProcessError):
        return {}


def img_size(path):
    from PIL import Image
    with Image.open(path) as image:
        return {"w": image.width, "h": image.height}


def materialize(source, destination):
    """Copy on replacement: an existing hardlinked destination is never overwritten in place.

    New assets remain independent copies. Storage compaction may consolidate verified
    generated copies later; a changed source is materialized as a fresh inode.
    """
    source, destination = Path(source), Path(destination)
    if destination.exists() and os.path.samefile(source, destination):
        return
    if destination.exists():
        a, b = source.stat(), destination.stat()
        if a.st_size == b.st_size and a.st_mtime_ns == b.st_mtime_ns:
            return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(".%s.%s.tmp" % (destination.name, uuid.uuid4().hex))
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
