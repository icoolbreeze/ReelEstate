"""Turn an already-exported, allowed data file into on-screen cards and a fact checklist.

No network and no crawl. Missing numbers stay missing. Internal ids and contacts
never become on-screen fields.
"""
import json
from pathlib import Path

PRICE_KINDS = {"list": "挂牌价", "transaction": "成交价", "sample": "系统样本", "opinion": "经纪人观点"}
HIDDEN = ("listing_ref", "listing_id", "crm", "phone", "mobile", "wechat", "weixin", "customer", "address", "room_no")


def _blank(value):
    return value is None or str(value).strip() in ("", "待填")


def build_pack(payload):
    if not isinstance(payload, dict):
        raise ValueError("research import must be an object")
    cards = []
    checklist = []
    hidden_dropped = []
    for index, case in enumerate(payload.get("cases") or []):
        label = str(case.get("label") or "案例%d" % (index + 1))
        for key in HIDDEN:
            if case.get(key) not in (None, ""):
                hidden_dropped.append(key)
        if case.get("screenshot"):
            checklist.append("%s：不把内部系统截图直接上屏" % label)
        kind = case.get("price_kind")
        if kind not in PRICE_KINDS:
            checklist.append("%s：价格口径缺失，不推断，不上屏" % label)
            continue
        if _blank(case.get("value")):
            checklist.append("%s：没有%s数值，不推断" % (label, PRICE_KINDS[kind]))
            continue
        if case.get("public") is not True:
            checklist.append("%s：未允许公开，不上屏" % label)
            continue
        missing = [name for name in ("source", "collected_on", "basis") if _blank(case.get(name))]
        if missing:
            checklist.append("%s：缺少%s，不上屏" % (label, "、".join(missing)))
            continue
        cards.append({
            "label": label,
            "price_kind": kind,
            "price_label": PRICE_KINDS[kind],
            "value": str(case["value"]),
            "unit": str(case.get("unit") or ""),
            "source": str(case["source"]),
            "collected_on": str(case["collected_on"]),
            "basis": str(case["basis"]),
        })
    questions = []
    for card in cards:
        questions.append({
            "from_card": card["label"],
            "text": "这组%s的来源和统计口径是什么？" % card["price_label"],
            "status": "suggested_from_data",
        })
    background = {
        "region": payload.get("region") or "待填",
        "collected_on": payload.get("collected_on") or "待填",
        "note": payload.get("background") or "待填",
    }
    if _blank(background["note"]):
        checklist.append("采访背景资料仍是待填")
    return {
        "background": background,
        "cards": cards,
        "questions": questions,
        "checklist": checklist,
        "hidden_dropped": sorted(set(hidden_dropped)),
        "invented": False,
    }


def import_file(source, destination):
    payload = json.loads(Path(source).read_text(encoding="utf-8-sig"))
    pack = build_pack(payload)
    Path(destination).write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return pack
