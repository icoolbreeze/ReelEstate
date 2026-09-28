"""ReelEstate compliance checker.

Usage:  python pipeline/check/check.py projects/<category>/<id> [--json]
Exit code: 0 = PASS, 1 = FAIL, 2 = usage / file error.
Rules: rules/compliance/*.md  (视频号房地产行业公约 2026-05-12, 广告法, 房地产广告发布规定, 住房租赁条例)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from reel_common import CATEGORIES, REPO_ROOT, load_json, resolve_project_dir, setup_console, strip_comments  # noqa: E402
from jsonschema_lite import Validator  # noqa: E402

SCHEMA_DIR = REPO_ROOT / "pipeline" / "schema"
BANNED_FILE = Path(__file__).resolve().parent / "banned_words.json"

# Fields whose values are identifiers / paths; excluded from contact & word scans.
ID_KEYS = {"id", "verification_code", "presale_permit_no", "record_no", "file", "presenter_clip",
           "broll", "valid_until", "available_from", "delivery_date", "voice", "mode", "category",
           "default_ratio", "ratios", "presenter", "unit", "type_hint"}

CONTACT_PATTERNS = [
    (r"(?<!\d)1[3-9]\d{9}(?!\d)", "手机号"),
    (r"(?<!\d)1[3-9]\d[\s-]\d{4}[\s-]\d{4}(?!\d)", "手机号（分隔写法）"),
    (r"(?<![\d-])0\d{2,3}-?\d{7,8}(?!\d)", "座机号"),
    (r"(?<!\d)400[\s-]?\d{3}[\s-]?\d{4}(?!\d)", "400 电话"),
    (r"微信|威信|薇信|v信|V信|vx|VX|wx|WX|加V|加v|V❤|v❤|微❤", "微信/变体"),
    (r"二维码|扫码|扫一扫", "二维码"),
    (r"(?i)\bqq\b|QQ号|扣扣", "QQ"),
    (r"(?i)https?://|www\.|\.com\b|\.cn\b|\.net\b", "网址"),
    (r"电话|手机号|联系方式|热线|致电", "联系方式字样"),
    (r"小红书|快手|贝壳|链家|安居客|58同城|淘宝", "站外平台名"),
]


class Report:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str]] = []  # (level, section, message)

    def ok(self, section: str, msg: str) -> None:
        self.items.append(("ok", section, msg))

    def fail(self, section: str, msg: str) -> None:
        self.items.append(("fail", section, msg))

    def warn(self, section: str, msg: str) -> None:
        self.items.append(("warn", section, msg))

    def todo(self, section: str, msg: str) -> None:
        self.items.append(("todo", section, msg))

    @property
    def failed(self) -> bool:
        return any(level == "fail" for level, _, _ in self.items)


def iter_strings(obj, path="$", key=None):
    """Yield (path, key, text) for every string value, skipping _comment keys."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith("_"):
                continue
            yield from iter_strings(v, f"{path}.{k}", k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_strings(v, f"{path}[{i}]", key)
    elif isinstance(obj, str):
        yield path, key, obj


def nonempty(v) -> bool:
    return isinstance(v, str) and v.strip() != "" and "待填" not in v


def check_mandatory(p: dict, r: Report, project_dir: Path) -> None:
    sec = "公约必填"
    prop = p.get("property", {}) or {}
    if nonempty(prop.get("property_type")):
        r.ok(sec, f"房产类型：{prop['property_type']}")
    else:
        r.fail(sec, "缺少房产类型 property.property_type")

    area = prop.get("area", {}) or {}
    if area.get("type") in ("建筑面积", "套内建筑面积") and isinstance(area.get("value"), (int, float)) and area["value"] > 0:
        r.ok(sec, f"面积：{area['type']} {area['value']}㎡")
    else:
        r.fail(sec, "面积需标明“建筑面积”或“套内建筑面积”且数值 > 0（property.area）")

    loc = prop.get("location", {}) or {}
    if nonempty(loc.get("street")) or nonempty(loc.get("community")):
        r.ok(sec, f"位置：{loc.get('district', '')} {loc.get('street', '')} {loc.get('community', '')}".strip())
    else:
        r.fail(sec, "地址需精确到街道或小区（property.location.street / community）")

    price = p.get("price", {}) or {}
    vu = price.get("valid_until", "")
    try:
        vdate = dt.date.fromisoformat(vu)
    except (TypeError, ValueError):
        vdate = None
    if isinstance(price.get("value"), (int, float)) and price["value"] > 0 and vdate:
        if vdate < dt.date.today():
            r.fail(sec, f"价格有效期已过（截至 {vu}），请更新真实价格与有效期")
        else:
            r.ok(sec, f"价格：{price.get('type', '')} {price['value']}{price.get('unit', '')}（截至 {vu}）")
    else:
        r.fail(sec, "需要真实价格（price.value > 0）和有效期 price.valid_until（YYYY-MM-DD）")

    agency = (p.get("agency", {}) or {}).get("full_name", "")
    if nonempty(agency) and agency.endswith("公司") and len(agency) >= 6:
        r.ok(sec, f"中介机构全称：{agency}")
    else:
        r.fail(sec, "需要中介/销售机构全称（agency.full_name，以“公司”结尾）")

    drawbacks = [d for d in p.get("drawbacks", []) if nonempty(d)]
    if drawbacks:
        r.ok(sec, f"已列出缺点 {len(drawbacks)} 条（兼顾优缺点）")
    else:
        r.fail(sec, "drawbacks 不能为空：公约要求兼顾优点与不足")

    agent = p.get("agent", {}) or {}
    if agent.get("certified_on_camera") is True and nonempty(agent.get("name")):
        r.ok(sec, f"出镜人：{agent['name']}（已确认为视频号认证本人）")
    else:
        r.fail(sec, "主要出镜人必须是视频号房产职业认证本人：确认后将 agent.certified_on_camera 设为 true")


def load_banned() -> dict:
    return load_json(BANNED_FILE)


def check_words(p: dict, r: Report, extra: list[tuple[str, str]] | None = None) -> None:
    sec = "违禁用语"
    banned = load_banned()
    allow = banned.get("allow", [])
    hits = 0
    items = [(path, key, text) for path, key, text in iter_strings(p)] + [(path, "text", text) for path, text in (extra or [])]
    for path, key, text in items:
        if key in ID_KEYS:
            continue
        scan = text
        for a in allow:
            scan = scan.replace(a, "□" * len(a))
        for group, words in banned.items():
            if group.startswith("_") or group in ("allow", "travel_time_regex"):
                continue
            for w in words:
                if w in scan:
                    hits += 1
                    r.fail(sec, f"{path} 含“{w}”（{group}）：{text}")
        for rx in banned.get("travel_time_regex", []):
            m = re.search(rx, scan)
            if m:
                hits += 1
                r.fail(sec, f"{path} 用时间表示位置“{m.group(0)}”，请改为客观距离（约XX米，地图测距）：{text}")
    if not hits:
        r.ok(sec, "未发现绝对化用语、升值承诺、学区落户、时间表示位置、风水、诱导等违禁表述")


def check_contacts(p: dict, r: Report) -> None:
    sec = "联系方式/导流"
    hits = 0
    for path, key, text in iter_strings(p):
        if key in ID_KEYS:
            continue
        for rx, label in CONTACT_PATTERNS:
            m = re.search(rx, text)
            if m:
                hits += 1
                r.fail(sec, f"{path} 疑似{label}“{m.group(0)}”：{text}")
    if not hits:
        r.ok(sec, "未发现电话、微信、二维码、网址、站外平台等导流信息")


def check_placeholders(p: dict, r: Report) -> None:
    sec = "占位内容"
    is_example = p.get("is_example") is True
    hits = 0
    for path, key, text in iter_strings(p):
        if "待填" in text:
            hits += 1
            r.fail(sec, f"{path} 仍是占位：{text}")
        elif not is_example and ("示例" in text or re.search(r"XX|xx", text)):
            hits += 1
            r.fail(sec, f"{path} 含“示例/XX”占位内容：{text}")
    if not hits:
        r.ok(sec, "没有残留“待填”占位")


def consent_files(project_dir: Path) -> list[Path]:
    d = project_dir / "consent"
    if not d.is_dir():
        return []
    return [f for f in d.iterdir() if f.is_file() and f.name not in (".gitkeep", "README.md")]


def check_category(p: dict, r: Report, project_dir: Path) -> None:
    cat = p.get("category")
    sec = {"rental": "租赁专项", "resale": "二手房专项", "new-home": "新房专项"}.get(cat, "分类")
    if cat == "resale":
        rs = p.get("resale", {}) or {}
        if nonempty(rs.get("verification_code")):
            r.ok(sec, f"房源核验编码：{rs['verification_code']}")
        else:
            r.fail(sec, "缺少房源核验编码 resale.verification_code")
        files = consent_files(project_dir)
        if rs.get("owner_consent") is True and files:
            r.ok(sec, f"业主书面委托：consent/{files[0].name} 等 {len(files)} 个文件")
        else:
            r.fail(sec, "二手房需业主书面委托：放入 consent/ 并将 resale.owner_consent 设为 true")
    elif cat == "new-home":
        nh = p.get("new_home", {}) or {}
        if nonempty(nh.get("developer_full_name")):
            r.ok(sec, f"开发企业：{nh['developer_full_name']}")
        else:
            r.fail(sec, "缺少开发企业全称 new_home.developer_full_name")
        if nonempty(nh.get("presale_permit_no")):
            r.ok(sec, f"预售/销售许可证号：{nh['presale_permit_no']}")
        else:
            r.fail(sec, "缺少预售/销售许可证号 new_home.presale_permit_no（无预售证的期房不得做广告）")
        bad = [x for x in nh.get("renderings", []) if not re.search(r"效果图|非实景", str(x.get("label", "")))]
        if bad:
            r.fail(sec, f"{len(bad)} 张效果图未标注“效果图/非实景”（new_home.renderings[].label）")
        else:
            r.ok(sec, "效果图均已标注")
        for f in nh.get("planned_facilities", []):
            if f.get("status") in ("规划中", "在建"):
                r.warn(sec, f"配套“{f.get('name')}”为{f.get('status')}，画面与口播中必须同时标注“{f.get('status')}”")
    elif cat == "rental":
        rt = p.get("rental", {}) or {}
        price = p.get("price", {}) or {}
        if price.get("type") == "月租金" and price.get("unit") == "元/月":
            r.ok(sec, f"月租金：{price.get('value')}元/月")
        else:
            r.fail(sec, "租赁价格需为 price.type=“月租金”、price.unit=“元/月”")
        if nonempty(rt.get("payment_terms")):
            r.ok(sec, f"押付方式：{rt['payment_terms']}")
        else:
            r.fail(sec, "缺少押付方式 rental.payment_terms（如 押一付三）")
        if rt.get("rent_type") == "合租" and not nonempty(rt.get("room_desc")):
            r.fail(sec, "合租需写明出租房间 rental.room_desc")
        bad_words = ["隔断", "群租", "床位", "N+1", "n+1", "阳台房", "客厅房", "客厅出租", "阳台出租", "厨房出租"]
        hits = [(path, w) for path, key, text in iter_strings(p) for w in bad_words if w in text]
        for path, w in hits:
            r.fail(sec, f"{path} 含“{w}”：非居住空间不得单独出租居住（住房租赁条例）")
        if not hits:
            r.ok(sec, "无隔断/群租/床位等违规描述")
        if not consent_files(project_dir):
            r.warn(sec, "consent/ 下没有业主委托/产权证明；中介发布出租广告需持有（房地产广告发布规定第6条）")
    else:
        r.fail(sec, f"未知分类：{cat}（应为 {', '.join(CATEGORIES)}）")


def check_nearby(p: dict, r: Report) -> None:
    for n in p.get("nearby", []) or []:
        if n.get("status") in ("在建", "规划中"):
            r.warn("配套", f"“{n.get('name')}”为{n.get('status')}，画面与口播必须标注“{n.get('status')}”")


def check_media(p: dict, r: Report, project_dir: Path) -> None:
    sec = "素材"
    for seg in p.get("narration", {}).get("segments", []):
        for key in ("presenter_clip", "broll"):
            rel = seg.get(key)
            if rel and not (project_dir / rel).exists():
                r.fail(sec, f"段落 {seg.get('id')} 的 {key} 文件不存在：{rel}")
        if seg.get("visual_label") and not re.search(r"效果图|非实景|样板间|AI", seg["visual_label"]):
            r.warn(sec, f"段落 {seg.get('id')} visual_label 建议写“效果图/非实景/样板间/AI生成”")
    seg_json = project_dir / "audio" / "segments.json"
    if seg_json.exists():
        r.ok(sec, "已有 TTS 分段音频 audio/segments.json")


def publish_todos(p: dict, r: Report, project_dir: Path) -> None:
    sec = "发布时手动"
    ai = p.get("ai_voice") is True or (project_dir / "audio" / "segments.json").exists()
    if ai:
        r.todo(sec, "使用了 AI 配音：发布时勾选 AI 标注（抖音：高级设置→自主声明→内容由AI生成；视频号：添加标注→含AI生成内容），并确认有声音本人书面授权")
    if p.get("ad_disclosure") is True:
        r.todo(sec, "商业推广：画面/标题显著标注“广告”；抖音商单走巨量星图")
    r.todo(sec, "挂合规留资组件（视频号留资组件/企微获客助手；抖音线索小程序），不在画面放联系方式")
    r.todo(sec, "确认脚本与近期视频不雷同，只在一个账号发布（公约禁止模板化/矩阵霸屏）")
    if p.get("is_example") is True:
        r.warn("示例", "这是示例数据（is_example=true），不得发布")


# Extra PII / CRM leakage patterns (on top of CONTACT_PATTERNS): exact floor / unit / room numbers,
# detailed addresses, CRM ids and ke.com / lianjia links or logos, personal names with titles.
PII_PATTERNS = [
    (r"(?<!\d)\d{1,3}\s*(?:栋|幢|座|号楼)", "楼栋号"),
    (r"(?<!\d)\d{1,2}\s*单元", "单元号"),
    (r"(?<!\d)\d{3,4}\s*(?:室|号房)", "房号"),
    (r"(?<!\d)\d{1,3}-\d{1,2}-\d{3,4}(?!\d)", "楼栋-单元-房号"),
    (r"[\u4e00-\u9fa5]{2,}(?:路|街|大道|巷|弄)\d{1,5}号", "详细门牌地址"),
    (r"(?<![共\d])\d{1,2}\s*/\s*\d{1,2}\s*层?", "精确楼层"),
    (r"(?<![共\d])第\s*\d{1,2}\s*层", "精确楼层"),
    (r"(?<!\d)\d{10,}(?!\d)", "CRM 房源编号/长数字 ID"),
    (r"(?i)ke\.com|lianjia|ljcdn|beike|贝壳|链家|自如|我爱我家", "贝壳/链家等平台名称或链接"),
    (r"[\u4e00-\u9fa5](?:先生|女士|小姐)(?![\u4e00-\u9fa5])", "姓氏+称谓（可能是业主/房东姓名）"),
    (r"(?:业主|房东|租客)[\u4e00-\u9fa5]{0,2}[:：]\s*[\u4e00-\u9fa5]{2,3}", "业主/房东姓名"),
]
TEXT_KEYS_SHOTS = {"zh", "en", "pill", "title", "lines", "main", "sub", "caption", "value", "unit", "cta"}
TEXT_KEYS_WALL = {"community", "layout", "area", "rent", "orientation", "floor"}


def rendered_texts(project_dir: Path) -> list[tuple[str, str]]:
    """Every string that can appear on screen from shots.json / wall.json (project.json is scanned separately)."""
    out: list[tuple[str, str]] = []
    shots_p = project_dir / "shots.json"
    if shots_p.exists():
        doc = load_json(shots_p)
        for path, key, text in iter_strings({"shots": doc.get("shots", []), "floorplan": doc.get("floorplan", {})}, "shots.json"):
            if key in TEXT_KEYS_SHOTS or key == "zh":
                out.append((path, text))
    wall_p = project_dir / "wall.json"
    if wall_p.exists():
        for path, key, text in iter_strings({"cards": load_json(wall_p).get("cards", [])}, "wall.json"):
            if key in TEXT_KEYS_WALL:
                out.append((path, text))
    return out


def check_pii(p: dict, r: Report, project_dir: Path) -> None:
    sec = "隐私/PII"
    hits = 0
    texts = [(path, text) for path, key, text in iter_strings(p) if key not in ID_KEYS and key != "name"]
    texts += rendered_texts(project_dir)
    needles: list[str] = []
    listing_p = project_dir / "listing.json"
    if listing_p.exists():
        lid = str(load_json(listing_p).get("listing_id") or "")
        if len(lid) >= 6:
            needles.append(lid)
    wc_p = project_dir / "wall_candidates.json"
    if wc_p.exists():
        for it in load_json(wc_p).get("items") or []:
            lid = str(it.get("listing_id") or "")
            if len(lid) >= 6:
                needles.append(lid)
    for path, text in texts:
        for rx, label in PII_PATTERNS + CONTACT_PATTERNS:
            m = re.search(rx, text)
            if m:
                hits += 1
                r.fail(sec, f"{path} 疑似{label}“{m.group(0)}”：{text}")
        for n in needles:
            if n in text:
                hits += 1
                r.fail(sec, f"{path} 含 CRM 房源编号“{n}”：{text}")
    # wall.json must not carry CRM ids at all (Remotion props are not private)
    wall_p = project_dir / "wall.json"
    if wall_p.exists():
        raw = wall_p.read_text(encoding="utf-8")
        for n in needles:
            if n in raw:
                hits += 1
                r.fail(sec, f"wall.json 含 CRM 房源编号 {n}（CRM id 只能留在 listing.json / wall_candidates.json）")
                break
    if not hits:
        r.ok(sec, "未发现电话/微信/姓名、精确楼层、楼栋单元房号、详细门牌、CRM 编号、贝壳链家字样")


def check_assets(p: dict, r: Report, project_dir: Path) -> None:
    sec = "素材清单"
    man_p = project_dir / "assets" / "manifest.json"
    if not man_p.exists():
        # Legacy projects without the one-sentence workflow are allowed to skip.
        if (project_dir / "shots.json").exists() or (project_dir / "brief.json").exists():
            r.fail(sec, "缺少 assets/manifest.json（一句话成片必须记录每个素材的来源/许可/AI/水印）")
        return
    man = load_json(man_p)
    assets = man.get("assets") or []
    by_file = {a.get("file"): a for a in assets if a.get("file")}
    # Every media referenced by shots / wall / map / presenter must be listed.
    needed: set[str] = set()
    shots_p = project_dir / "shots.json"
    if shots_p.exists():
        for sh in (load_json(shots_p).get("shots") or []):
            if sh.get("media"):
                needed.add(sh["media"])
    wall_p = project_dir / "wall.json"
    if wall_p.exists():
        for c in (load_json(wall_p).get("cards") or []):
            if c.get("cover"):
                needed.add(c["cover"])
    for name in ("map/satellite_4x3.jpg", "map/static.png", "raw/presenter.mp4", "audio/bgm.mp3"):
        if (project_dir / name).exists():
            needed.add(name)
    missing = sorted(n for n in needed if n not in by_file)
    for m in missing:
        r.fail(sec, f"素材未入清单：{m}")
    wm = [a["file"] for a in assets if a.get("watermarked") is True]
    for f in wm:
        r.fail(sec, f"素材带水印，禁止使用（去水印也不行）：{f}")
    required = ("file", "source", "license", "ai", "watermarked")
    for a in assets:
        lack = [k for k in required if a.get(k) in (None, "", "unknown")]
        if lack and a.get("file") in needed:
            r.fail(sec, f"{a.get('file')} 缺少字段 {', '.join(lack)}（来源/许可/AI/水印必须写清）")
        if a.get("ai") is True:
            if not a.get("model") or not a.get("prompt"):
                r.fail(sec, f"{a.get('file')} 是 AI 素材，必须记录 model 与 prompt")
            if a.get("usage") not in ("decorative", "transition"):
                r.fail(sec, f"{a.get('file')} 是 AI 素材，usage 只能是 decorative/transition（不得用于户型/实景/景观/周边）")
    if not missing and not wm:
        r.ok(sec, f"素材清单 {len(assets)} 条，引用文件均已登记且无水印")
    if any(a.get("ai") for a in assets):
        r.todo("发布时手动", "含 AI 生成画面：发布时勾选 AI 标注，并确认画面已打“AI生成”角标")


def check_map(p: dict, r: Report, project_dir: Path) -> None:
    sec = "地图归属"
    geo_p = project_dir / "map" / "geo.json"
    if not geo_p.exists():
        return
    geo = load_json(geo_p)
    attr = geo.get("attribution") or ""
    if not attr or "高德" not in attr and "地图" not in attr:
        r.fail(sec, "map/geo.json 缺少可见的地图归属说明（attribution）")
    else:
        r.ok(sec, f"地图归属：{attr}")
    if not (project_dir / "map" / "satellite_4x3.jpg").exists():
        r.warn(sec, "缺少 map/satellite_4x3.jpg")


def check_style(p: dict, r: Report) -> None:
    sec = "风格"
    style = p.get("style")
    if style in (None, ""):
        r.warn(sec, "未设置 style（qiuzhi / mediastorm）；将回退为 qiuzhi")
    elif style not in ("qiuzhi", "mediastorm"):
        r.fail(sec, f"未知 style：{style}（应为 qiuzhi 或 mediastorm）")
    else:
        r.ok(sec, f"风格：{style}")


def run(project_dir: Path) -> Report:
    r = Report()
    raw = load_json(project_dir / "project.json")
    p = strip_comments(raw)
    cat = p.get("category")
    if cat not in CATEGORIES:
        r.fail("结构", f"category 必须是 {CATEGORIES} 之一，当前：{cat}")
        return r
    errs = Validator(SCHEMA_DIR).validate(p, f"{cat}.json")
    if errs:
        for e in errs:
            r.fail("结构（Schema）", e)
    else:
        r.ok("结构（Schema）", f"project.json 符合 pipeline/schema/{cat}.json")
    check_placeholders(p, r)
    check_mandatory(p, r, project_dir)
    check_category(p, r, project_dir)
    check_words(p, r, rendered_texts(project_dir))
    check_contacts(p, r)
    check_pii(p, r, project_dir)
    check_style(p, r)
    check_nearby(p, r)
    check_media(p, r, project_dir)
    check_assets(p, r, project_dir)
    check_map(p, r, project_dir)
    publish_todos(p, r, project_dir)
    return r


ICON = {"ok": "✅", "fail": "❌", "warn": "⚠️ ", "todo": "📋"}


def print_report(project_dir: Path, r: Report) -> None:
    try:
        rel = project_dir.relative_to(REPO_ROOT)
    except ValueError:
        rel = project_dir
    print(f"\n==== ReelEstate 合规检查：{rel.as_posix() if hasattr(rel, 'as_posix') else rel} ====")
    last = None
    for level, sec, msg in r.items:
        if sec != last:
            print(f"\n[{sec}]")
            last = sec
        print(f"  {ICON[level]} {msg}")
    n_fail = sum(1 for x in r.items if x[0] == "fail")
    n_warn = sum(1 for x in r.items if x[0] == "warn")
    print("\n" + "=" * 48)
    if r.failed:
        print(f"结果：❌ 未通过（{n_fail} 项必须修改，{n_warn} 项提醒）。规则见 rules/compliance/。修改文案，不要修改规则。")
    else:
        print(f"结果：✅ 通过（{n_warn} 项提醒）。发布前请完成 📋 手动事项与 rules/workflow.md 自检清单。")


def main(argv=None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="ReelEstate 合规检查")
    ap.add_argument("project", help="项目目录，如 projects/rental/2026-10-03-lvcheng-2b1l")
    ap.add_argument("--json", action="store_true", help="输出 JSON 结果")
    args = ap.parse_args(argv)
    try:
        project_dir = resolve_project_dir(args.project)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    r = run(project_dir)
    if args.json:
        print(json.dumps({"pass": not r.failed, "items": [dict(level=a, section=b, message=c) for a, b, c in r.items]},
                         ensure_ascii=False, indent=2))
    else:
        print_report(project_dir, r)
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
