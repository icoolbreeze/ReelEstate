"""16:9 safe boxes for 小ONE会客厅. Guest on the right, graphics in the open side.

These boxes are what the Remotion template reads. The checker uses the same
numbers, so a card that would cover the face fails before render.
"""

DESIGN = {
    "width": 1920,
    "height": 1080,
    "margin": 48,
    "guest_side": "right",
    "gaze": "left",
    "face": {"x": 1188, "y": 132, "w": 560, "h": 560},
    "gesture": {"x": 1088, "y": 680, "w": 720, "h": 250},
    "bug": {"x": 64, "y": 36, "w": 320, "h": 52},
    "region": {"x": 400, "y": 42, "w": 280, "h": 40},
    "question": {"x": 64, "y": 160, "w": 820, "h": 240},
    "case": {"x": 64, "y": 180, "w": 860, "h": 420},
    "namebar": {"x": 64, "y": 860, "w": 640, "h": 72},
    "caption": {"x": 64, "y": 948, "w": 920, "h": 52},
    "datascreen": {"x": 64, "y": 150, "w": 880, "h": 500},
    "brand": {"x": 48, "y": 1008, "w": 1824, "h": 56},
}
MODES = {
    "question": ["bug", "region", "question", "caption"],
    "name": ["bug", "region", "namebar"],
    "case": ["bug", "region", "case"],
    "data": ["bug", "region", "datascreen", "caption"],
}
RESERVED = ("face", "gesture")


def _intersects(a, b):
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def layout_document():
    return {
        "width": DESIGN["width"],
        "height": DESIGN["height"],
        "margin": DESIGN["margin"],
        "guest_side": DESIGN["guest_side"],
        "gaze": DESIGN["gaze"],
        "boxes": {name: dict(DESIGN[name]) for name in (
            "face", "gesture", "bug", "region", "question", "case", "namebar", "caption", "datascreen", "brand")},
        "modes": {name: list(keys) for name, keys in MODES.items()},
        "human_review": ["肤色", "光线方向", "抠像边缘闪动", "演播室真实感"],
    }


def check_layout(document=None):
    document = document or layout_document()
    errors = []
    width = document["width"]
    height = document["height"]
    boxes = document["boxes"]
    if (width, height) != (1920, 1080):
        errors.append("首版画幅只支持 1920x1080")
    for name, box in boxes.items():
        if box["w"] < 1 or box["h"] < 1:
            errors.append("%s 尺寸无效" % name)
        if name == "brand":
            continue
        if box["x"] < document["margin"] or box["y"] < 24:
            errors.append("%s 超出安全边" % name)
        if box["x"] + box["w"] > width - 24 or box["y"] + box["h"] > height:
            errors.append("%s 超出画面" % name)
    for mode, names in document["modes"].items():
        for name in names:
            for reserved in RESERVED:
                if _intersects(boxes[name], boxes[reserved]):
                    errors.append("%s 布局的 %s 压住了 %s" % (mode, name, reserved))
            if boxes[name]["y"] + boxes[name]["h"] > boxes["brand"]["y"]:
                errors.append("%s 布局的 %s 压住了品牌条" % (mode, name))
    return errors
