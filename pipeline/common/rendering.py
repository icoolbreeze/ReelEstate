"""Atomic render replacement keeps shared historical exports safe on re-render."""
import os
import uuid
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_output(target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(".%s.%s%s" % (target.stem, uuid.uuid4().hex, target.suffix))
    try:
        yield temporary
        if not temporary.is_file():
            raise RuntimeError("renderer did not create its output: %s" % temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
