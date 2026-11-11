# -*- coding: utf-8 -*-
"""为 Virtual Browser（VB）worker 生成一套全新、自洽的指纹，写入
``%LOCALAPPDATA%\\VirtualBrowser\\Workers\\<id>\\virtual.dat``。

机制（见 docs/virtual-browser-backend.md 第 1、3、6 节，2026-10-19 实测）：

- VB 免费版 2.2.16 的 146 内核启动时按命令行 ``--worker-id=<id>``，在
  ``--user-data-dir`` 下找 ``virtual.dat``，应用其中 ``users[].id == <id>`` 的指纹。
- 内核每次启动都重读该文件、无缓存：启动前重写即可「每次启动一套新指纹」
  （CPU/GPU/canvas/audio/字体/MAC/设备名/时区都会变）。
- 这里只写 worker 目录里的那份，绝不碰 GUI 全局 ``User Data\\virtual.dat``。

模板结构（39 个字段）取自全局 ``User Data\\virtual.dat`` 的第一条 user 深拷贝；
若全局库缺失则回退到 worker 目录已有 dat。标准库 only。

CLI::

    python vb_fingerprint.py 100 --country us
    python vb_fingerprint.py 101 --country jp --name POOL-101
"""
from __future__ import annotations

import argparse
import json
import random
import string
import time
from pathlib import Path

VB_LOCAL = Path.home() / "AppData" / "Local" / "VirtualBrowser"
VB_GLOBAL_DAT = VB_LOCAL / "User Data" / "virtual.dat"

# coherent GPU bundles: (ANGLE renderer, webgl vendor, webgpu vendor, arch)
GPUS = [
    ("ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)", "Google Inc. (NVIDIA)", "nvidia", "ampere"),
    ("ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)", "Google Inc. (NVIDIA)", "nvidia", "turing"),
    ("ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0, D3D11)", "Google Inc. (AMD)", "amd", "gcn-4"),
    ("ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)", "Google Inc. (Intel)", "intel", "gen9-5"),
]
SCREENS = [(1920, 1080), (1536, 864), (1366, 768), (2560, 1440), (1440, 900)]
CPUS = [4, 6, 8, 12, 16]
MEMS = [4, 8, 16]

# country -> (IANA tz, Windows display name, UTC offset, language list)
ZONE = {
    "us": ("America/New_York", "(UTC-05:00) Eastern Time", -5, ["en-US", "en"]),
    "jp": ("Asia/Tokyo", "(UTC+09:00) Osaka, Sapporo, Tokyo", 9, ["ja-JP", "ja", "en-US", "en"]),
}

FONT_POOL = ["Arial", "Calibri", "Cambria", "Candara", "Consolas", "Constantia", "Corbel", "Courier New",
             "Ebrima", "Franklin Gothic Medium", "Gabriola", "Gadugi", "Georgia", "Impact", "Javanese Text",
             "Leelawadee UI", "Lucida Console", "Malgun Gothic", "Marlett", "Microsoft Himalaya",
             "Microsoft JhengHei", "Microsoft New Tai Lue", "Microsoft PhagsPa", "Microsoft Tai Le",
             "Microsoft YaHei", "Microsoft Yi Baiti", "MingLiU-ExtB", "Mongolian Baiti", "MS Gothic",
             "MV Boli", "Myanmar Text", "Nirmala UI", "Palatino Linotype", "Segoe MDL2 Assets",
             "Segoe Print", "Segoe Script", "Segoe UI", "Segoe UI Emoji", "Segoe UI Historic",
             "Segoe UI Semibold", "Segoe UI Symbol", "SimSun", "Sitka", "Sylfaen", "Symbol", "Tahoma",
             "Times New Roman", "Trebuchet MS", "Verdana", "Webdings", "Wingdings", "Yu Gothic"]
VOICE_POOL = [
    ("en-US", "Google US English"), ("en-US", "Microsoft David - English (United States)"),
    ("en-US", "Microsoft Zira - English (United States)"), ("en-GB", "Google UK English Female"),
    ("ja-JP", "Google 日本語"), ("zh-CN", "Google 普通话（中国大陆）"),
    ("fr-FR", "Google français"), ("de-DE", "Google Deutsch"), ("es-ES", "Google español"),
]


def worker_dir(env_id: int) -> Path:
    return VB_LOCAL / "Workers" / str(env_id)


def _rand_mac() -> str:
    return "-".join(f"{random.randint(0, 255):02X}" for _ in range(6))


def _rand_devname() -> str:
    return "DESKTOP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=7))


def _load_template_user(env_id: int) -> dict:
    """取结构模板：优先全局库第一条 user；缺失时回退该 worker 已有 dat。"""
    for src in (VB_GLOBAL_DAT, worker_dir(env_id) / "virtual.dat"):
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
            users = data.get("users") or []
            if users:
                return json.loads(json.dumps(users[0]))
        except FileNotFoundError:
            continue
    raise RuntimeError(
        "no fingerprint template found: need the VB GUI global "
        f"{VB_GLOBAL_DAT} or an existing worker virtual.dat"
    )


def generate_fingerprint(env_id: int, country: str = "us", *,
                         name: str | None = None,
                         seed: int | str | None = None) -> dict:
    """生成一套自洽指纹 user 记录（dict）。country: us|jp。"""
    if country not in ZONE:
        raise ValueError(f"country must be us|jp, got {country!r}")
    if seed is not None:
        random.seed(seed)
    else:
        random.seed(f"vb-{env_id}-{time.time_ns()}")

    u = _load_template_user(env_id)

    renderer, glvendor, wgpu_v, wgpu_arch = random.choice(GPUS)
    w, h = random.choice(SCREENS)
    zone, zname, zval, _langs = ZONE[country]
    fonts = sorted(random.sample(FONT_POOL, random.randint(28, 40)))
    voices = sorted(random.sample(VOICE_POOL, random.randint(4, 6)), key=lambda x: x[0])

    u["id"] = env_id
    u["name"] = name or f"TEP-POOL-{env_id:02d}"
    u["createdAt"] = int(time.time() * 1000)
    u["timestamp"] = u["createdAt"]
    u["os"] = "Win 11"
    u["chrome_version"] = 146
    u["core_version"] = "auto"

    # 代理不在文件里配：启动命令行 --proxy-server 优先（见 vb_backend）。
    u["proxy"] = {"mode": 0, "value": "", "protocol": "HTTP", "host": "", "port": "",
                  "user": "", "pass": "", "API": ""}

    # identity hardware
    u["cpu"] = {"mode": 1, "value": random.choice(CPUS)}
    u["memory"] = {"mode": 1, "value": random.choice(MEMS)}  # deviceMemory 内核不伪装，仅记录
    u["screen"] = {"mode": 1, "width": w, "height": h, "_value": f"{w} x {h}"}
    u["webgl"] = {"mode": 1, "vendor": glvendor, "render": renderer}
    u["webgpu"] = {"mode": 1, "vendor": wgpu_v, "architecture": wgpu_arch}
    u["device-name"] = {"mode": 1, "value": _rand_devname()}
    u["mac"] = {"mode": 1, "value": _rand_mac()}

    # per-install noise（与 GUI 同款小幅 RGBA/float 扰动）
    def rgba() -> dict:
        return {"mode": 1,
                "r": random.choice([-10, -8, -6, -3, -2, 2, 3, 6, 8, 10]),
                "g": random.choice([-10, -8, -6, -3, -2, 2, 3, 6, 8, 10]),
                "b": random.choice([-10, -8, -6, -3, -2, 2, 3, 6, 8, 10]),
                "a": random.randint(2, 9)}

    u["canvas"] = rgba()
    u["webgl-img"] = rgba()
    u["audio-context"] = {"mode": 1,
                          "channel": random.uniform(2e-8, 9e-8),
                          "analyer": random.uniform(0.04, 0.12)}
    u["client-rects"] = {"mode": 1,
                         "width": random.uniform(-0.95, 0.95),
                         "height": random.uniform(-0.95, 0.95)}
    u["media"] = {"mode": 1}
    u["fonts"] = {"mode": 1, "value": fonts}
    u["speech_voices"] = {"mode": 1, "value": [
        {"default": False, "lang": lang, "localService": False, "name": nm, "voiceURI": nm}
        for lang, nm in voices]}

    # geo / language / timezone 与出口国家对齐
    u["ua-language"] = {"mode": 2, "language": ""}
    u["time-zone"] = {"mode": 2, "zone": f"UTC{zval:+d}:00", "utc": zone,
                      "locale": "", "name": zname, "value": zval}
    u["location"] = {"mode": 2, "enable": 1, "precision": random.randint(1200, 9000)}
    u["webrtc"] = {"mode": 0}   # 0 = replace/spoofed（不泄露 host candidate）

    return u


def write_fingerprint(env_id: int, country: str = "us", *,
                      name: str | None = None,
                      seed: int | str | None = None) -> Path:
    """生成并原子写入 Workers/<id>/virtual.dat，返回文件路径。"""
    u = generate_fingerprint(env_id, country, name=name, seed=seed)
    out_dir = worker_dir(env_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "virtual.dat"
    tmp = out.with_suffix(".dat.tmp")
    tmp.write_text(json.dumps({"users": [u]}, ensure_ascii=False),
                   encoding="utf-8", newline="\n")
    tmp.replace(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Write a fresh self-consistent VB worker fingerprint")
    ap.add_argument("env_id", type=int)
    ap.add_argument("--country", choices=["us", "jp"], default="us")
    ap.add_argument("--name", default=None)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    out = write_fingerprint(args.env_id, args.country,
                            name=args.name, seed=args.seed)
    u = json.loads(out.read_text(encoding="utf-8"))["users"][0]
    print(json.dumps({
        "written": str(out), "id": u["id"], "name": u["name"], "country": args.country,
        "cpu": u["cpu"]["value"], "screen": u["screen"]["_value"],
        "gpu": u["webgl"]["render"], "zone": u["time-zone"]["utc"],
        "device": u["device-name"]["value"],
        "fonts": len(u["fonts"]["value"]), "voices": len(u["speech_voices"]["value"]),
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
