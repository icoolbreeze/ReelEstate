# -*- coding: utf-8 -*-
"""Live proof for the davinci-resolve-mcp server's stabilization call.

This drives the exact feature the compound MCP tool exposes:
    MCP tool : timeline_item_color
    action   : stabilize
    impl     : TimelineItem.Stabilize()

It creates an isolated throwaway Resolve project from a synthetic shaky clip,
runs Stabilize() on the first video clip, reads the stabilization properties
back, then deletes only that project and reloads the previously open project.

Exit codes:
    0  Stabilize() returned true and StabilizationEnable reads back enabled
    1  anything else (failure, not enabled, unexpected error)
    2  external scripting could not connect to Resolve
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime

# ---- Fixed local facts (from the assignment; do not download anything) -------
RESOLVE_EXE = r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"
RESOLVE_SCRIPT_API = (
    r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting"
)
RESOLVE_SCRIPT_LIB = (
    r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"
)
RESOLVE_MODULES = os.path.join(RESOLVE_SCRIPT_API, "Modules")
FFMPEG = r"C:\ProgramData\chocolatey\bin\ffmpeg.exe"

PROJECT_PREFIX = "reelestate-stab-test-"
STAB_PROPS = ("StabilizationEnable", "StabilizationMethod", "StabilizationStrength")


# 1. Resolve env must be present BEFORE importing DaVinciResolveScript. --------
os.environ["RESOLVE_SCRIPT_API"] = RESOLVE_SCRIPT_API
os.environ["RESOLVE_SCRIPT_LIB"] = RESOLVE_SCRIPT_LIB
os.environ["PYTHONPATH"] = (
    RESOLVE_MODULES + os.pathsep + os.environ.get("PYTHONPATH", "")
).rstrip(os.pathsep)
# PYTHONHOME for the live server is the interpreter base prefix; mirror it here.
os.environ.setdefault("PYTHONHOME", sys.base_prefix)
if RESOLVE_MODULES not in sys.path:
    sys.path.insert(0, RESOLVE_MODULES)

import DaVinciResolveScript as dvr  # noqa: E402


def log(msg):
    print("[test_stabilize] " + str(msg), flush=True)


def temp_dir() -> str:
    return os.environ.get("TEMP") or os.environ.get("TMP") or os.path.expanduser("~")


def resolve_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Resolve.exe"],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
        return "Resolve.exe" in out
    except Exception:
        return False


def connect_resolve():
    """Return the live Resolve object, starting Resolve if needed."""
    resolve = dvr.scriptapp("Resolve")
    if resolve:
        return resolve

    if resolve_running():
        log("Resolve.exe is running but scripting is not connected yet; polling.")
    else:
        log("Resolve.exe not running; launching it.")
        subprocess.Popen([RESOLVE_EXE], close_fds=True)

    deadline = time.time() + 120
    while time.time() < deadline:
        resolve = dvr.scriptapp("Resolve")
        if resolve:
            return resolve
        time.sleep(2)
    return None


def wait_pm(resolve, timeout_s=30):
    """Wait until the ProjectManager and a current project are reachable."""
    deadline = time.time() + timeout_s
    pm = None
    while time.time() < deadline:
        pm = resolve.GetProjectManager()
        if pm is not None and pm.GetCurrentProject() is not None:
            return pm
        time.sleep(1)
    return resolve.GetProjectManager()


def generate_shaky_clip(clip_path: str):
    """5s 640x360 30fps H.264 synthetic clip with per-frame crop jitter.

    A moving crop window over testsrc2 produces genuine frame-to-frame
    translation that Resolve's tracker has to stabilize. No audio.
    """
    os.makedirs(os.path.dirname(clip_path), exist_ok=True)
    vf = (
        # crop window inside 640x360 stays in bounds:
        # x in [5,39] (limit 40), y in [1,21] (limit 24)
        "crop=600:336:x='22+12*sin(n/3)+5*sin(n/7)':y='11+6*cos(n/5)+4*cos(n/2)',"
        "scale=640:360,setsar=1"
    )
    cmd = [
        FFMPEG,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=640x360:rate=30:duration=5",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-an",
        clip_path,
    ]
    log("Generating synthetic shaky clip: " + clip_path)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0 or not os.path.exists(clip_path):
        raise RuntimeError("ffmpeg failed:\n" + proc.stderr[-2000:])


def read_stab_props(item) -> dict:
    props = {}
    for key in STAB_PROPS:
        try:
            props[key] = item.GetProperty(key)
        except Exception as exc:  # surface but don't crash the readback
            props[key] = None
            log("GetProperty(%s) raised: %r" % (key, exc))
    return props


def jsval(v):
    """Coerce Resolve-returned property values to JSON-safe primitives."""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float, str)):
        return v
    return str(v)


def js_props(props: dict) -> dict:
    return {k: jsval(v) for k, v in props.items()}


def stabilization_enabled(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, float):
        return abs(value - 1.0) < 1e-6
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true"}
    return False


def main() -> int:
    # 2/3. Connect to Resolve, launching it if it is not running. ---------------
    resolve = connect_resolve()
    if resolve is None:
        print(
            "External scripting did not connect: scriptapp('Resolve') stayed "
            "None for 120s. Preferences were not changed and no bridge was "
            "installed."
        )
        return 2

    pm = wait_pm(resolve)
    if pm is None:
        print("External scripting did not connect: ProjectManager unavailable.")
        return 2

    resolve_version = None
    for getter in ("GetVersion", "GetProductName"):
        try:
            resolve_version = getattr(resolve, getter)()
            if resolve_version:
                break
        except Exception:
            resolve_version = None

    report = {
        "resolve_version": resolve_version,
        "project_created": None,
        "clip_path": None,
        "stabilize_return": None,
        "properties_before": None,
        "properties_after": None,
        "elapsed_s": None,
        "stabilization_enabled": False,
    }

    created_name = None
    prev_name = None
    try:
        # 4. Throwaway synthetic clip under %TEMP%. -----------------------------
        clip_dir = os.path.join(temp_dir(), "reelestate-stab-test")
        clip_path = os.path.join(clip_dir, "shaky.mp4")
        generate_shaky_clip(clip_path)
        report["clip_path"] = clip_path

        # 5. Remember the current project name; never save it. -----------------
        prev_project = pm.GetCurrentProject()
        if prev_project is not None:
            prev_name = prev_project.GetName()
        log("Previous project (left unsaved): %r" % (prev_name,))

        # 6. New isolated project, only the generated clip, one timeline. ------
        created_name = PROJECT_PREFIX + datetime.now().strftime("%Y%m%d%H%M%S")
        log("Creating project: " + created_name)
        new_proj = pm.CreateProject(created_name)
        if new_proj is None:
            raise RuntimeError("CreateProject returned None for " + created_name)
        if not pm.LoadProject(created_name):
            raise RuntimeError("LoadProject failed for " + created_name)
        proj = pm.GetCurrentProject()
        if proj is None or proj.GetName() != created_name:
            raise RuntimeError("Could not make " + created_name + " current")
        report["project_created"] = proj.GetName()

        media_pool = proj.GetMediaPool()
        appended = media_pool.AddItemListToMediaPool([clip_path])
        if not appended:
            raise RuntimeError("Clip import failed: " + clip_path)

        timeline = media_pool.CreateTimelineFromClips(
            created_name + "-timeline", appended
        )
        if timeline is None:
            raise RuntimeError("CreateTimelineFromClips returned None")
        if not proj.SetCurrentTimeline(timeline):
            raise RuntimeError("SetCurrentTimeline failed")
        timeline = proj.GetCurrentTimeline()

        items = timeline.GetItemListInTrack("video", 1)
        if not items:
            raise RuntimeError("No video items on track 1")
        item = items[0]

        # 7. Read stabilization properties before. -----------------------------
        properties_before = read_stab_props(item)
        report["properties_before"] = js_props(properties_before)
        log("before: " + json.dumps(report["properties_before"], ensure_ascii=False))

        # 8. Color page is required, then the feature under test: Stabilize(). -
        resolve.OpenPage("color")
        time.sleep(1)
        started = time.time()
        try:
            ret = item.Stabilize()
        except Exception as exc:
            ret = False
            log("Stabilize() raised: %r" % (exc,))
        stabilize_return = bool(ret)
        report["stabilize_return"] = stabilize_return
        log("Stabilize() returned %r" % (ret,))

        # 9. Stabilize can be asynchronous: poll the props for up to 90s. ------
        properties_after = properties_before
        deadline = started + 90
        while time.time() <= deadline:
            properties_after = read_stab_props(item)
            if stabilization_enabled(properties_after.get("StabilizationEnable")):
                break
            time.sleep(1)
        report["properties_after"] = js_props(properties_after)
        report["elapsed_s"] = round(time.time() - started, 2)
        report["stabilization_enabled"] = stabilization_enabled(
            properties_after.get("StabilizationEnable")
        )
        log("after: " + json.dumps(report["properties_after"], ensure_ascii=False))

    finally:
        # 10. Delete ONLY the project this script created, then reload previous.
        # Resolve will not delete the currently loaded project, so move back to
        # the previous project first; nothing other than `created_name` is ever
        # deleted.
        if created_name is not None:
            try:
                existing = pm.GetProjectListInCurrentFolder() or []
                if prev_name:
                    pm.LoadProject(prev_name)
                    time.sleep(1)
                deleted = False
                if created_name in existing:
                    for _ in range(5):
                        deleted = bool(pm.DeleteProject(created_name))
                        if deleted:
                            break
                        time.sleep(1)
                if prev_name:
                    pm.LoadProject(prev_name)
                log(
                    "cleanup: deleted created project = %r" % (deleted,)
                    + ("; previous project %r reloaded" % prev_name if prev_name else "")
                )
            except Exception as exc:
                report["cleanup_error"] = repr(exc)
                log("cleanup error: %r" % (exc,))

    # 11. Write + print the UTF-8 (LF, no BOM) JSON report under %TEMP%. -------
    report_path = os.path.join(temp_dir(), "reelestate-stabilize-report.json")
    body = json.dumps(report, ensure_ascii=False, indent=2)
    with open(report_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body + "\n")
    print(body)
    log("report written: " + report_path)

    # 12. Real success requires BOTH a true return and enabled readback. -------
    if report["stabilize_return"] and report["stabilization_enabled"]:
        return 0
    log(
        "FAIL: stabilize_return=%r enabled=%r"
        % (report["stabilize_return"], report["stabilization_enabled"])
    )
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        # Still surface a structured failure instead of a raw traceback.
        import traceback

        traceback.print_exc()
        try:
            report_path = os.path.join(temp_dir(), "reelestate-stabilize-report.json")
            payload = {"fatal_error": repr(exc)}
            with open(report_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        except Exception:
            pass
        sys.exit(1)
