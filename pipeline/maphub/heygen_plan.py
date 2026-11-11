"""Compatibility entry; implementation lives in pipeline.common.heygen_plan."""
import importlib
import runpy
import sys
from pathlib import Path

_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)
if __name__ == "__main__":
    runpy.run_module("pipeline.common.heygen_plan", run_name="__main__")
else:
    sys.modules[__name__] = importlib.import_module("pipeline.common.heygen_plan")
