"""Stage 0 · parse: one sentence → brief.json (rule-based; the agent fills gaps by asking the user).

The parser only extracts what is literally in the sentence. Everything it cannot determine becomes a
question in brief.json["questions"]; each question names the stage it blocks. The agent must ask the
user (rules/workflow.md §一句话成片) and write the answers back with CLI flags or by editing brief.json.
"""
from __future__ import annotations

import hashlib
import re

from .common import now_iso

CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}
CITIES = ["北京", "上海", "广州", "深圳", "成都", "杭州", "重庆", "武汉", "西安", "南京", "苏州", "天津", "长沙", "郑州",
          "青岛", "厦门", "合肥", "昆明", "宁波", "佛山", "东莞", "济南", "沈阳", "大连", "福州", "无锡", "贵阳", "南宁"]
COMMUNITY_RE = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9]{2,12}?(?:小区|花园|家园|苑|府|城|庭|公寓|湾|郡|里|公馆|名邸|广场|雅居|新村|大厦))")
STYLE_WORDS = {"mediastorm": ["影视飓风", "飓风", "mediastorm"], "qiuzhi": ["秋芝", "qiuzhi"]}
ORIENTS = ["南北通透", "朝南", "朝北", "朝东", "朝西", "东南", "西南", "东北", "西北"]

# The complete list of things the agent must settle with the user (rules/workflow.md keeps the same list).
QUESTION_BANK = {
    "category": ("这条视频是 租赁 / 二手房 / 新房 哪一类？", "parse"),
    "listing.target": ("给我房源编号（CRM listing id），或小区名 + 筛选条件（户型/租金或总价/面积/朝向）。", "listing:fetch"),
    "listing.pick": ("列表墙里要重点讲哪一套？（给卡片序号 c01… 或房源编号）", "listing:fetch"),
    "style": ("用哪个风格：qiuzhi（秋芝）还是 mediastorm（影视飓风）？", "script"),
    "voice.mode": ("配音用 AI（edge-tts 草稿 / qwen 本地）还是你自己录？AI 声音需要声音本人书面授权放 consent/，发布时勾 AI 标注。", "tts"),
    "consent.owner": ("业主书面委托/授权书放进 consent/ 了吗？（二手房必须；租赁中介发布同样需要）", "check"),
    "disclosures": ("必须公示的信息：二手房核验码 / 租赁房源核验或登记备案编号（当地要求）、价格有效期、中介机构全称、出镜人是否认证本人。", "check"),
    "flova": ("flova 默认开启（装饰/转场片段 + 地图底图重绘），积分由 flova MCP 自行处理、不设限；需要关闭吗？（不能用于生成户型/实景/景观/周边）", "assets:import"),
    "photos.exclude": ("有没有要排除的实勘照片（有人像、门牌、平台水印、杂乱的）？", "listing:fetch"),
    "platform": ("发布平台：抖音、视频号，还是都发？", "script"),
}


def normalize_flova(brief: dict) -> dict:
    """flova is default-on; credits are handled by the flova MCP and are NOT a limit.

    Old briefs may still carry flova.credit_budget: it is ignored (dropped). An explicit allowed=false is kept.
    """
    fl = brief.setdefault("flova", {})
    fl.pop("credit_budget", None)
    fl.setdefault("allowed", True)
    return brief


def detect_category(s: str) -> str | None:
    if re.search(r"新房|楼盘|期房|开盘|预售|样板间|开发商", s):
        return "new-home"
    if re.search(r"二手|挂牌|总价|首付|满五|满二|[0-9一二三四五六七八九十]+万(?!元/月)", s):
        return "resale"
    if re.search(r"租|月租|整租|合租|押一|房租", s):
        return "rental"
    return None


def detect_style(s: str) -> str | None:
    low = s.lower()
    for name, words in STYLE_WORDS.items():
        if any(w.lower() in low for w in words):
            return name
    return None


def detect_rooms(s: str) -> list[int]:
    out = []
    for m in re.finditer(r"([一两二三四五六1-6])\s*(?:室|居|房)(?!租)", s):
        v = m.group(1)
        out.append(CN_NUM.get(v, int(v) if v.isdigit() else 0))
    return sorted({r for r in out if 1 <= r <= 5})


def detect_range(s: str, unit_re: str) -> dict | None:
    m = re.search(r"(\d{2,6})\s*(?:-|~|到|至)\s*(\d{2,6})\s*" + unit_re, s)
    if m:
        return {"min": float(m.group(1)), "max": float(m.group(2))}
    m = re.search(r"(\d{2,6})\s*" + unit_re + r"\s*(?:以内|以下|之内|左右)?", s)
    if m:
        v = float(m.group(1))
        if re.search(m.group(0) + r".{0,2}", s) and ("以内" in s or "以下" in s):
            return {"min": None, "max": v}
        return {"min": round(v * 0.85), "max": round(v * 1.15)}
    return None


def parse_sentence(sentence: str) -> dict:
    s = sentence.strip()
    category = detect_category(s)
    listing_id = None
    m = re.search(r"(?:房源编号|编号|id|ID)[:：\s]*([A-Za-z0-9]{6,32})", s) or re.search(r"(?<![\d])(\d{9,20})(?![\d])", s)
    if m:
        listing_id = m.group(1)
    community = None
    m = COMMUNITY_RE.search(s)
    if m:
        community = re.sub(r"^(帮我|给我|做|拍|一条|一个|讲讲|介绍|在|把)+", "", m.group(1))
    city = next((c for c in CITIES if c in s), None)
    rent = detect_range(s, r"(?:元|块)(?:/月|每月)?") if category == "rental" else None
    price_wan = detect_range(s, r"万") if category == "resale" else None
    area = detect_range(s, r"(?:平|㎡|平米|平方)")
    orient = [o for o in ORIENTS if o in s]
    voice = None
    if re.search(r"自己配音|我自己录|我来配|原声|真人配音", s):
        voice = "own"
    elif re.search(r"AI配音|ai配音|配音", s):
        voice = "edge"
    platforms = [p for p, w in (("douyin", "抖音"), ("channels", "视频号")) if w in s]
    slug_hash = hashlib.sha1(s.encode("utf-8")).hexdigest()[:6]
    return {
        "sentence": s,
        "created_at": now_iso(),
        "slug": f"auto-{slug_hash}",
        "category": category,
        "style": detect_style(s),
        "ratio": "4x3",
        "listing": {
            "source": "crm",
            "listing_id": listing_id,
            "community_keyword": community,
            "city": city,
            "filters": {"rooms": detect_rooms(s), "monthly_rent_yuan": rent, "total_price_wan": price_wan,
                        "area_sqm": area, "orientations": orient, "scope": "all"},
            "pick": listing_id,
        },
        "voice": {"mode": voice, "edge_voice": "zh-CN-YunxiNeural", "rate": "+15%"},
        "flova": {"allowed": True},
        "photos": {"exclude": []},
        "platform": platforms,
        "map": {"query": None, "city": city, "source": "amap"},
        "answers": {},
        "questions": [],
    }


def open_questions(brief: dict, project_dir=None) -> list[dict]:
    """Recompute the open questions from the current brief state."""
    qs = []

    def add(key: str):
        q, stage = QUESTION_BANK[key]
        qs.append({"key": key, "q": q, "blocks": stage})

    if not brief.get("category"):
        add("category")
    lst = brief.get("listing", {})
    if not (lst.get("listing_id") or lst.get("community_keyword") or lst.get("source") == "mock"):
        add("listing.target")
    if not lst.get("pick"):
        add("listing.pick")
    if not brief.get("style"):
        add("style")
    if not (brief.get("voice") or {}).get("mode"):
        add("voice.mode")
    if not brief.get("platform"):
        add("platform")
    confirmed = set((brief.get("answers") or {}).get("_confirmed", []))
    for key in ("consent.owner", "disclosures", "flova", "photos.exclude"):
        if key not in confirmed:
            add(key)
    return qs
